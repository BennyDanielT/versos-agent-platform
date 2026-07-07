"""Guardrails wired into the REAL triage agent (not just the standalone demo).

Two pieces, both built ONCE and reused per call (heavy to construct):
  - input_rails(): a NeMo Guardrails LLM input rail — screens INTENT (off-topic, novel
    jailbreaks) that the regex `_screen_input` can't. `is_input_blocked()` runs ONLY the
    input rail (no wasted main-LLM generation).
  - mask_pii(): dependency-free REGEX redaction of structured PII (email/phone/card/SSN/IP) in
    customer-facing text. No Presidio/spaCy (they'd add hundreds of MB to the image); trade-off is
    no PERSON/LOCATION masking. Always-on, no deps.

The NeMo rail is lazy + cached so importing this module is cheap and a missing package/key
degrades gracefully (the input rail becomes a no-op rather than crashing).
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_GUARDRAILS_DIR = Path(__file__).resolve().parents[2] / "guardrails"   # severity_lab/guardrails


# --- INPUT RAIL (NeMo Guardrails) -------------------------------------------
@lru_cache(maxsize=1)
def _input_rails():
    from nemoguardrails import LLMRails, RailsConfig
    return LLMRails(RailsConfig.from_path(str(_GUARDRAILS_DIR)))


@lru_cache(maxsize=1)
def _input_only_options():
    from nemoguardrails.rails.llm.options import GenerationOptions
    return GenerationOptions(rails=["input"])


async def is_input_blocked(text: str) -> bool:
    """True if the NeMo input rail blocks this message. Input-only run (no main LLM call):
    an ALLOWED message is echoed back unchanged; a BLOCKED one returns a refusal."""
    try:
        rails = _input_rails()
        res = await rails.generate_async(
            messages=[{"role": "user", "content": text}], options=_input_only_options())
        content = (res.response[-1]["content"] if hasattr(res, "response") else str(res))
        return content.strip() != text.strip()
    except Exception as exc:                          # degrade to "not blocked" (regex still ran)
        logger.warning("NeMo input rail unavailable, skipping: %s", exc)
        return False


# --- OUTPUT PII MASKING (regex, no deps) ------------------------------------
# "Lite" masker: deterministic regex for the high-value STRUCTURED entities. No spaCy /
# Presidio (they hard-depend on spaCy → hundreds of MB). Trade: no PERSON/LOCATION masking.
# Order matters: match longer/more-specific patterns before shorter ones.
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("IP_ADDRESS",    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("CREDIT_CARD",   re.compile(r"\b\d(?:[ -]?\d){11,15}\b")),          # 12–16 digits
    ("US_SSN",        re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")),
    ("PHONE_NUMBER",  re.compile(
        r"\b(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b")),
]


def mask_pii(text: str) -> str:
    """Redact structured PII (email/phone/card/SSN/IP) → `<EMAIL_ADDRESS>` etc. Deterministic,
    dependency-free. On any failure, returns the original text (never crash the reply path)."""
    if not text:
        return text
    try:
        for label, pattern in _PII_PATTERNS:
            text = pattern.sub(f"<{label}>", text)
        return text
    except Exception as exc:
        logger.warning("PII masking failed, returning text unmasked: %s", exc)
        return text
