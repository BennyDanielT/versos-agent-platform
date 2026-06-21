"""ONE source of truth for severity scoring — imported by BOTH eval surfaces.

  - evals.py            (the NAT `nat eval` evaluator)
  - scripts/phoenix_experiment.py (the Phoenix experiment evaluator)

NAT and Phoenix want differently-SHAPED evaluators (different plug), but the brain
inside — "pull severity out, does it match the gold?" — is identical and lives here.
"""
from __future__ import annotations

import json
from typing import Any


def extract_severity(output_obj: Any) -> str:
    """Pull the `severity` field out of a triage workflow output (JSON str or dict).

    Returns "" on anything malformed (→ scores as a miss, never raises).
    """
    try:
        data = json.loads(output_obj) if isinstance(output_obj, str) else output_obj
        return str((data or {}).get("severity", "")).strip().lower()
    except (json.JSONDecodeError, AttributeError, TypeError):
        return ""


def severity_matches(got: str, expected: Any) -> bool:
    """True if predicted severity equals the expected severity (case/space-insensitive)."""
    g = str(got).strip().lower()
    e = str(expected).strip().lower()
    return bool(g) and g == e
