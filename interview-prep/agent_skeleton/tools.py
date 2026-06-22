"""Tool registry: typed, named, safe actions. Risk feeds the autonomy gate.

The `validate` hook raises on bad args BEFORE the sim ever sees them -- so a
hallucinated tool call is rejected, never executed. "I never trust model text into
the simulation raw."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Action:
    name: str
    args: dict
    risk: str = "low"          # low | medium | high  -> gate uses this


@dataclass
class Tool:
    name: str
    description: str           # the LLM reads this; write it like a prompt
    risk: str
    validate: Callable[[dict], None]


REGISTRY: dict[str, Tool] = {}


def register(name, description, risk="low", validate=lambda a: None):
    REGISTRY[name] = Tool(name, description, risk, validate)


def _need_target(a: dict):
    if not a.get("target"):
        raise ValueError("missing 'target'")


def _scale_args(a: dict):
    _need_target(a)
    if not 1 <= a.get("amount", 0) <= 4:
        raise ValueError("amount must be 1-4")


# --- the action menu the agent can choose from --------------------------
register("scale_workers",
         "Add capacity to an OVERLOADED unit. args: {target:str, amount:int 1-4}",
         risk="medium", validate=_scale_args)
register("clear_lock",
         "Clear a stale lock on a STUCK unit. args: {target:str}",
         risk="low", validate=_need_target)
register("retry",
         "Retry a FLAKY unit; a transient failure usually clears. args: {target:str}",
         risk="low", validate=_need_target)
register("escalate",
         "Hand a unit with no safe automated fix (e.g. CORRUPT) to a human. args: {target:str}",
         risk="low", validate=_need_target)
register("wipe_all",
         "Destroy and rebuild every unit. DESTRUCTIVE / irreversible. args: {}",
         risk="high", validate=lambda a: None)


def tool_specs() -> list[dict]:
    """What you hand the LLM as the tool menu."""
    return [{"name": t.name, "description": t.description} for t in REGISTRY.values()]
