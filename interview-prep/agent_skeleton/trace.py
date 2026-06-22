"""Trace logger: observability + the metric.

Logs every decision with its reasoning -- the single highest-leverage artifact. It makes
the demo legible and proves the agent reasons rather than hallucinates. `summary()`
doubles as the evaluation metric.
"""
from __future__ import annotations


class Trace:
    def __init__(self):
        self.rows: list[dict] = []

    def log(self, step, kind, reason, action, obs):
        self.rows.append({
            "step": step, "kind": kind, "reason": reason,
            "action": None if action is None else {"tool": action.name, "args": action.args},
            "done": obs.done,
        })
        line = f"[{step:02d}] {kind:9} {reason}"
        if action is not None:
            line += f"  -> {action.name}({action.args})"
        print(line)

    def summary(self) -> dict:
        acts = [r for r in self.rows if r["kind"] == "ACT"]
        return {
            "steps": len(self.rows),
            "actions_taken": len(acts),
            "rejected": sum(r["kind"] == "REJECT" for r in self.rows),
            "blocked_or_proposed": sum(r["kind"] in ("BLOCK", "PROPOSE") for r in self.rows),
            "resolved": any(r["done"] for r in self.rows),
        }
