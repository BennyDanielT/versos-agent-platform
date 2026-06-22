"""The decision loop: perceive -> decide -> gate -> act -> verify -> terminate.

The bet: the LLM is the PLANNER, not the executor. Every action is typed, validated,
gated, and logged before it touches the simulation.
"""
from __future__ import annotations

import json

from gate import gate
from sim_adapter import Observation, SimAdapter
from tools import REGISTRY, Action, tool_specs
from trace import Trace

MAX_STEPS = 25


def decide(obs: Observation, llm):
    """LLM chooses ONE tool. Structured output -> never free text into the sim."""
    prompt = (
        "You control a simulation. Choose ONE tool to move toward the goal "
        "(all units healthy or escalated).\n"
        f"State: {json.dumps(obs.state)}\n"
        f"Diagnostics: {json.dumps(obs.info)}\n"
        f"Tools: {json.dumps(tool_specs())}\n"
        'Reply JSON: {"reason": "...", "tool": "name", "args": {...}}'
    )
    raw = llm.complete_json(prompt)
    tool = REGISTRY[raw["tool"]]                 # KeyError -> unknown tool -> rejected
    action = Action(name=tool.name, args=raw.get("args", {}), risk=tool.risk)
    tool.validate(action.args)                   # ValueError -> bad args -> rejected
    return action, raw["reason"]


def run(sim, llm) -> dict:
    adapter, trace = SimAdapter(sim), Trace()
    obs = adapter.observe()
    for step in range(MAX_STEPS):
        if obs.done:
            trace.log(step, "TERMINATE", "sim reports done (goal reached)", None, obs)
            break
        try:
            action, reason = decide(obs, llm)
        except (ValueError, KeyError) as e:                  # bad / hallucinated action
            trace.log(step, "REJECT", f"invalid action: {e}", None, obs)
            continue
        mode, gate_reason = gate(action)
        if mode == "block":
            trace.log(step, "BLOCK", gate_reason, action, obs)
            continue
        if mode == "suggest":
            trace.log(step, "PROPOSE", gate_reason, action, obs)   # human-in-loop
            continue
        obs = adapter.act(action)                            # mode == "auto"
        trace.log(step, "ACT", reason, action, obs)
    return {"trace": trace.rows, "metric": trace.summary()}
