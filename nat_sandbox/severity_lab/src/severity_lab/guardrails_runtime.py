"""Guardrails wired into the REAL triage agent (not just the standalone demo).

Two pieces, both built ONCE and reused per call (heavy to construct):
  - input_rails(): a NeMo Guardrails LLM input rail — screens INTENT (off-topic, novel
    jailbreaks) that the regex `_screen_input` can't. `is_input_blocked()` runs ONLY the
    input rail (no wasted main-LLM generation).
  - mask_pii(): deterministic Presidio redaction of PII in customer-facing text, so the
    `suggested_customer_reply` never leaks emails/phones/names/cards.

Construction is lazy + cached so importing this module is cheap and a missing model/key
degrades gracefully (the tool falls back to regex-only rather than crashing).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_GUARDRAILS_DIR = Path(__file__).resolve().parents[2] / "guardrails"   # severity_lab/guardrails
_PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
                 "US_SSN", "IP_ADDRESS", "IBAN_CODE", "LOCATION"]


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


# --- OUTPUT PII MASKING (Presidio) ------------------------------------------
@lru_cache(maxsize=1)
def _presidio():
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    nlp_engine = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    return analyzer, AnonymizerEngine()


def mask_pii(text: str) -> str:
    """Redact PII (email/phone/name/card/…) → `<EMAIL_ADDRESS>` etc. Deterministic.
    On any failure, returns the original text (never crash the reply path)."""
    if not text:
        return text
    try:
        analyzer, anonymizer = _presidio()
        found = analyzer.analyze(text=text, language="en", entities=_PII_ENTITIES)
        return anonymizer.anonymize(text=text, analyzer_results=found).text
    except Exception as exc:
        logger.warning("Presidio masking unavailable, returning text unmasked: %s", exc)
        return text
