"""Adapter: wrap the provided simulation as a black box. The agent only sees this.

If the real sim has a different API, THIS is the only file that changes -- that is the
whole point of the adapter (separation of concerns / decomposition rubric).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Observation:
    state: dict[str, Any]      # whatever the sim exposes
    done: bool
    info: dict[str, Any]       # errors, scores, anything diagnostic


class SimAdapter:
    """Thin, stable interface over the simulation: observe / act / reset."""

    def __init__(self, sim):
        self._sim = sim

    def observe(self) -> Observation:
        return Observation(
            state=self._sim.get_state(),
            done=self._sim.is_done(),
            info=self._sim.diagnostics(),
        )

    def act(self, action) -> Observation:
        self._sim.apply(action.name, **action.args)
        return self.observe()

    def reset(self) -> Observation:
        self._sim.reset()
        return self.observe()
