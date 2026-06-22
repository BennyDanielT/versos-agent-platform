"""Autonomy gate: the guardrail that makes this an *agent*, not a while-loop.

Kill switch freezes all autonomous action. Risk policy hard-holds destructive /
irreversible actions to 'suggest' (human-in-loop) no matter what the LLM wants.
"""
from __future__ import annotations

from tools import Action

# Flip to True to freeze all autonomous action -> everything proposes instead of acting.
# This is the "break it on purpose" demo: engage live, show the agent keep reasoning but
# stop touching the sim, then release and watch it recover.
KILL_SWITCH = False

POLICY = {                 # risk -> mode
    "low":    "auto",
    "medium": "auto",
    "high":   "suggest",   # destructive / irreversible -> always human-in-loop
}


def gate(action: Action) -> tuple[str, str]:
    """Return (mode, reason). mode in {auto, suggest, block}."""
    if KILL_SWITCH:
        return "suggest", "kill switch engaged -> propose only"
    mode = POLICY.get(action.risk, "suggest")
    return mode, f"{action.name}/{action.risk} -> {mode}"
