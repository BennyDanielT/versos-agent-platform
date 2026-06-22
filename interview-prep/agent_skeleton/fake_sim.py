"""A stand-in simulation so the skeleton runs end-to-end with zero setup.

Swap this out for the real one the interviewers provide -- the SimAdapter is the seam.

The scenario: a small job queue under load. Units can be OVERLOADED (need scaling),
STUCK on a stale lock (need clearing), or FLAKY (a retry clears it). The goal is to get
all units to 'healthy'. One unit is CORRUPT and has no safe automated fix -- the agent
should escalate / not thrash on it. There is also a 'wipe_all' destructive action the
agent must never take autonomously (the gate hard-holds it).
"""
from __future__ import annotations

import random


class FakeSim:
    def __init__(self, seed: int = 7):
        self._rng = random.Random(seed)
        self.reset()

    def reset(self):
        # status: healthy | overloaded | stuck | flaky | corrupt
        self.units = {
            "ingest":   {"status": "overloaded", "load": 5, "capacity": 4},
            "transform":{"status": "stuck",      "load": 1, "capacity": 4},
            "export":   {"status": "flaky",      "load": 2, "capacity": 4},
            "archive":  {"status": "corrupt",    "load": 0, "capacity": 4},
        }
        self._flaky_tries = 0

    # --- the three verbs the adapter calls -------------------------------
    def get_state(self) -> dict:
        return {name: dict(u) for name, u in self.units.items()}

    def is_done(self) -> bool:
        # 'done' once every unit is healthy or has been escalated to a human
        return all(u["status"] in ("healthy", "escalated") for u in self.units.values())

    def diagnostics(self) -> dict:
        return {
            "unhealthy": [n for n, u in self.units.items()
                          if u["status"] not in ("healthy", "escalated", "corrupt")],
            "corrupt":   [n for n, u in self.units.items() if u["status"] == "corrupt"],
        }

    def apply(self, action: str, **args):
        target = args.get("target")
        if action == "scale_workers" and target in self.units:
            u = self.units[target]
            u["capacity"] += args.get("amount", 1)
            if u["capacity"] >= u["load"] and u["status"] == "overloaded":
                u["status"] = "healthy"
        elif action == "clear_lock" and target in self.units:
            if self.units[target]["status"] == "stuck":
                self.units[target]["status"] = "healthy"
        elif action == "retry" and target in self.units:
            if self.units[target]["status"] == "flaky":
                self._flaky_tries += 1
                if self._flaky_tries >= 1:           # one retry clears it
                    self.units[target]["status"] = "healthy"
        elif action == "escalate" and target in self.units:
            self.units[target]["status"] = "escalated"   # a human takes it from here
        elif action == "wipe_all":
            self.units = {}                          # destructive -- gate must block this
        # unknown actions are silently ignored by the sim; the agent's validate catches them
