"""Regression tests for the autonomy promotion policy.

This is intentionally a *unit* test of the `decide` node, isolated from the LLM.
The promotion policy is the safety-critical part of the system — "when is an
agent allowed to act unsupervised" — so it gets deterministic, fast tests that
fail loudly if someone loosens a threshold by accident.

Run:  .venv/Scripts/python -m pytest -q
"""
from app.agents.triage.graph import decide


def test_critical_is_always_held_even_at_high_confidence():
    out = decide({"confidence": 0.99, "severity": "critical"})
    assert out["recommended_mode"] == "suggest"


def test_high_confidence_noncritical_can_auto():
    out = decide({"confidence": 0.90, "severity": "low"})
    assert out["recommended_mode"] == "auto"


def test_moderate_confidence_needs_human_approval():
    out = decide({"confidence": 0.70, "severity": "medium"})
    assert out["recommended_mode"] == "approved"


def test_low_confidence_is_suggest_only():
    out = decide({"confidence": 0.30, "severity": "low"})
    assert out["recommended_mode"] == "suggest"


def test_high_severity_high_confidence_does_not_auto():
    # "high" severity is not in the auto allow-list; should not reach auto.
    out = decide({"confidence": 0.95, "severity": "high"})
    assert out["recommended_mode"] != "auto"
