import json
import logging
import re
from typing import Literal

import asyncpg
from pydantic import BaseModel, Field, field_validator

from nat.plugin_api import Builder
from nat.plugin_api import FunctionBaseConfig
from nat.plugin_api import FunctionInfo
from nat.plugin_api import LLMFrameworkEnum
from nat.plugin_api import register_function

from .guardrails_runtime import is_input_blocked, mask_pii   # NeMo input rail + Presidio PII mask

logger = logging.getLogger(__name__)

# Allowed issue categories. Anything else the model invents maps to "other".
_CATEGORIES = {"billing", "media_quality", "account_access", "bug", "other"}

# --- INPUT GUARDRAIL (layer 1: screen the complaint BEFORE the LLM) ---------
_MIN_COMPLAINT_CHARS = 3       # below this = empty/garbage → reject, don't spend a call
_MAX_COMPLAINT_CHARS = 4000    # above this → truncate (legit long tickets exist)
# Cheap prompt-injection sniff. Not a hard block (false positives) — a FLAG that forces
# 'suggest' so a possibly-manipulated ticket can never auto-act. Defense in depth with policy.
_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(all\s+|the\s+)?(previous|prior|above)|disregard\s+(previous|prior|the\s+above)"
    r"|system\s+prompt|you\s+are\s+now|reveal\s+your|forget\s+(your|all)\s+(instructions|rules)",
    re.IGNORECASE,
)

# --- Input Screening ---
def _screen_input(complaint: str) -> tuple[bool, str, str, bool]:
    """Input guardrail. Returns (rejected, reason, cleaned_complaint, suspicious)."""
    text = (complaint or "").strip()
    if len(text) < _MIN_COMPLAINT_CHARS:
        return True, "Complaint is empty or too short to triage.", text, False
    suspicious = bool(_INJECTION_PATTERNS.search(text))
    if len(text) > _MAX_COMPLAINT_CHARS:
        text = text[:_MAX_COMPLAINT_CHARS]      # sanitize: cap blast radius / token cost
    return False, "", text, suspicious


# ---------------------------------------------------------------------------
# 1) CONFIG — the tool's settings (tunable from YAML)
# ---------------------------------------------------------------------------
class TriageTicketConfig(FunctionBaseConfig, name="triage_ticket"):
    """Config for the customer-support triage tool."""
    # Required: which model does the assessment.
    llm_name: str = Field(description="which configured LLM to use for triage")
    # Where to read the autonomy policy and write the decision log.
    database_url: str = Field(
        default="postgresql://versos:versos@localhost:5432/versos",
        description="asyncpg DSN for the triage_policy and triage_log tables")


# ---------------------------------------------------------------------------
# 2) STRUCTURED OUTPUT — what the LLM must return (typed, auditable, evaluable)
# ---------------------------------------------------------------------------
class TriageResult(BaseModel):
    """The LLM's assessment of a ticket. Note: the model does NOT decide autonomy."""
    # STRICT (safety-critical): Literal forces one of these exact values, and the
    # before-validator normalizes case/whitespace so "Low" -> "low".
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="low | medium | high | critical")
    # LENIENT (metadata): normalize, and map anything off-taxonomy to "other".
    category: str = Field(description="billing | media_quality | account_access | bug | other")
    confidence: float = Field(description="0..1 confidence in this assessment")
    summary: str = Field(description="one-sentence neutral summary of the complaint")
    developer_remediation: list[str] = Field(description="ordered steps for a developer to fix/triage")
    suggested_customer_reply: str = Field(description="a short, polite draft reply to the customer")

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v):
        return v.lower().strip() if isinstance(v, str) else v

    @field_validator("category", mode="before")
    @classmethod
    def _norm_category(cls, v):
        if isinstance(v, str):
            v = v.lower().strip().replace(" ", "_")
            return v if v in _CATEGORIES else "other"
        return v

    # Models sometimes return remediation as one string instead of a list — accept both.
    @field_validator("developer_remediation", mode="before")
    @classmethod
    def _coerce_to_list(cls, v):
        return [v] if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# 3) AUTONOMY POLICY — humans grant the ceiling per segment (a DB table);
#    CODE enforces it. The LLM never decides its own autonomy.
# ---------------------------------------------------------------------------
# Stepping down one autonomy level when confidence is below the segment's bar.
_STEP_DOWN = {"auto": "approved", "approved": "suggest", "suggest": "suggest"}


async def _flag_enabled(pool: asyncpg.Pool, name: str) -> bool:
    """Read a runtime feature flag from system_flags (DB-backed → flips live, no restart)."""
    return bool(await pool.fetchval("SELECT enabled FROM system_flags WHERE name = $1", name))


async def _decide_from_policy(pool: asyncpg.Pool, severity: str, category: str,
                              confidence: float) -> tuple[str, str]:
    """Look up the human-approved ceiling for this segment and enforce it."""
    # GUARDRAIL layer 6 — global KILL SWITCH. One DB flag forces ALL segments to suggest,
    # instantly, with no redeploy. Checked first because it overrides everything below.
    if await _flag_enabled(pool, "kill_switch"):
        return "suggest", "Global kill switch engaged: all autonomy disabled."

    # Hard guardrail (defense in depth): critical never auto-acts, policy or not.
    if severity == "critical":
        return "suggest", "Critical severity is always held for human review."

    row = await pool.fetchrow(
        "SELECT approved_mode, min_confidence FROM triage_policy "
        "WHERE severity = $1 AND category = $2",
        severity, category)

    # No human has granted autonomy for this segment -> safest default.
    if row is None:
        return "suggest", f"No approved policy for {severity}/{category}; suggest-only."

    ceiling, bar = row["approved_mode"], row["min_confidence"]
    if confidence >= bar:
        return ceiling, (f"Segment {severity}/{category} approved for '{ceiling}' "
                         f"at confidence >= {bar:.2f} (got {confidence:.2f}).")
    stepped = _STEP_DOWN.get(ceiling, "suggest")
    return stepped, (f"Confidence {confidence:.2f} below bar {bar:.2f} for "
                     f"{severity}/{category}; stepped down to '{stepped}'.")


# ---------------------------------------------------------------------------
# 4) THE TOOL — register + setup (once) + work (per call)
# ---------------------------------------------------------------------------
@register_function(config_type=TriageTicketConfig,
                   framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def triage_ticket_function(config: TriageTicketConfig, builder: Builder):
    """Triage a customer support ticket: assess it, draft remediation, and recommend
    an autonomy mode (suggest/approved/auto)."""

    # SETUP (runs once): the model (schema-bound) AND a Postgres connection pool.
    # The pool is opened here and closed after the `yield` — that's exactly what the
    # generator lifecycle is for.
    llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    # Provider-enforced structured output (the professional path). Token usage is still
    # captured: OpenInference instruments the underlying ChatNVIDIA call, so it reads the
    # response's usage regardless of this wrapper. Pydantic remains the safety net.
    structured_llm = llm.with_structured_output(TriageResult)
    pool = await asyncpg.create_pool(config.database_url)

    # THE WORK (runs every call). Returns a JSON STRING (NAT tool outputs are strings).
    async def _triage(complaint: str) -> str:
        # GUARDRAIL layer 1 — screen input before spending an LLM call.
        rejected, reject_reason, complaint, suspicious = _screen_input(complaint)
        if rejected:
            return json.dumps({
                "category": "other", "severity": "low", "confidence": 0.0,
                "summary": "Rejected by input guardrail.",
                "developer_remediation": [reject_reason],
                "suggested_customer_reply": "",
                "recommended_mode": "suggest",
                "mode_reason": reject_reason,
            }, indent=2)

        # GUARDRAIL layer 7 — NeMo input rail (LLM): catches off-topic / novel jailbreaks the
        # regex misses. DB-flag-gated (extra LLM call) so it flips live and bulk runs stay cheap.
        if await _flag_enabled(pool, "input_rail") and await is_input_blocked(complaint):
            reason = "Blocked by NeMo input rail (off-topic or manipulation attempt)."
            return json.dumps({
                "category": "other", "severity": "low", "confidence": 0.0,
                "summary": "Rejected by NeMo input rail.",
                "developer_remediation": [reason], "suggested_customer_reply": "",
                "recommended_mode": "suggest", "mode_reason": reason,
            }, indent=2)

        # GUARDRAIL (optional, data minimization) — mask PII in the complaint BEFORE it reaches
        # the LLM provider or triage_log. Off by default; the rail above already saw the original
        # text for intent detection. Trade: privacy posture vs slight context loss.
        if await _flag_enabled(pool, "mask_input"):
            complaint = mask_pii(complaint)

        prompt = (
            "You are a customer-support triage assistant for a media-processing company. "
            "Assess the complaint and fill every field; be honest about confidence. "
            "developer_remediation must be a list of short step strings.\n\n"
            f"Complaint: {complaint}"
        )
        try:
            result: TriageResult = await structured_llm.ainvoke(prompt)   # typed object
            if result is None:  # structured output can return None instead of raising
                raise ValueError("model returned no parseable structured output")
        except Exception as exc:  # honest degradation, not a fake answer
            logger.warning("triage structured output failed: %s", exc)
            return json.dumps({
                "category": "other", "severity": "high", "confidence": 0.0,
                "summary": "Triage failed; needs human review.",
                "developer_remediation": [f"Model/structured-output error: {exc}"],
                "suggested_customer_reply": "",
                "recommended_mode": "suggest",
                "mode_reason": "Triage error — defaulting to human review.",
            }, indent=2)

        # Autonomy comes from the human-owned policy table, enforced in code.
        mode, reason = await _decide_from_policy(
            pool, result.severity, result.category, result.confidence)

        # GUARDRAIL layer 1 (cont.) — a flagged ticket may have manipulated the model,
        # so it can NEVER auto-act; force human review regardless of policy.
        if suspicious:
            mode, reason = "suggest", ("Input flagged as possible prompt injection; "
                                       "held for human review.")

        # GUARDRAIL layer 7 (output) — Presidio redacts PII from the customer-facing reply
        # before it's ever logged or returned (emails/phones/names/cards -> <ENTITY>).
        safe_reply = mask_pii(result.suggested_customer_reply)

        # Log the full decision — this row is also a future evals/shadow-mode datapoint.
        await pool.execute(
            """INSERT INTO triage_log
               (complaint_text, category, severity, confidence, summary,
                developer_remediation, suggested_customer_reply,
                recommended_mode, mode_reason, model_name)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10)""",
            complaint, result.category, result.severity, result.confidence,
            result.summary, json.dumps(result.developer_remediation),
            safe_reply, mode, reason, config.llm_name)

        out = result.model_dump()
        out["suggested_customer_reply"] = safe_reply       # masked reply leaves the tool
        out["recommended_mode"] = mode
        out["mode_reason"] = reason
        return json.dumps(out, indent=2)

    yield FunctionInfo.from_fn(
        _triage,
        description=("Triage a customer support ticket: returns category, severity, confidence, "
                     "summary, developer remediation steps, a suggested customer reply, and a "
                     "recommended autonomy mode (suggest/approved/auto)."),
    )

    # TEARDOWN (runs after the workflow ends): release the DB connections.
    await pool.close()
