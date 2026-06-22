"""The planner. Two implementations behind one `complete_json(prompt) -> dict` method:

- FakeLLM: deterministic, no API key, so the skeleton runs anywhere. It mimics what a
  real model returns (a {reason, tool, args} JSON) -- including the occasional invalid
  action, so you can demo the agent REJECTING bad output.
- ClaudeLLM: the real thing. In the interview, point at this and say "swap FakeLLM for
  ClaudeLLM and it's live on Opus 4.8 with structured output." Kept import-light so the
  package runs without the SDK installed.
"""
from __future__ import annotations

import json


class FakeLLM:
    """Stand-in planner: picks the obvious fix from diagnostics. Deterministic."""

    def __init__(self):
        self._mischief_done = False

    def complete_json(self, prompt: str) -> dict:
        state = _extract_json(prompt, "State:")
        info = _extract_json(prompt, "Diagnostics:")

        # Demo the reject path ONCE: propose a malformed action the validate hook rejects.
        if not self._mischief_done:
            self._mischief_done = True
            return {"reason": "(intentional bad call to show rejection) scale with no amount",
                    "tool": "scale_workers", "args": {"target": "ingest"}}

        # Corrupt units have no safe fix -> escalate (don't thrash).
        for name in info.get("corrupt", []):
            return {"reason": f"{name} is corrupt; no safe automated fix",
                    "tool": "escalate", "args": {"target": name}}

        for name in info.get("unhealthy", []):
            status = state.get(name, {}).get("status")
            if status == "overloaded":
                u = state[name]
                amount = max(1, u["load"] - u["capacity"])
                return {"reason": f"{name} overloaded (load>{u['capacity']}); add capacity",
                        "tool": "scale_workers", "args": {"target": name, "amount": amount}}
            if status == "stuck":
                return {"reason": f"{name} stuck on a stale lock; clear it",
                        "tool": "clear_lock", "args": {"target": name}}
            if status == "flaky":
                return {"reason": f"{name} flaky; a retry should clear it",
                        "tool": "retry", "args": {"target": name}}

        return {"reason": "nothing actionable", "tool": "escalate", "args": {"target": "none"}}


class ClaudeLLM:                                       # pragma: no cover - needs the SDK + key
    """Real planner on Claude Opus 4.8 with structured (JSON) output."""

    def __init__(self, model: str = "claude-opus-4-8"):
        from anthropic import Anthropic        # lazy import so FakeLLM path needs nothing
        self._client = Anthropic()
        self._model = model

    def complete_json(self, prompt: str) -> dict:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(msg.content[0].text)


def _extract_json(prompt: str, label: str) -> dict:
    """Pull the JSON blob that follows `label` on its line in the prompt."""
    for line in prompt.splitlines():
        if line.startswith(label):
            try:
                return json.loads(line[len(label):].strip())
            except json.JSONDecodeError:
                return {}
    return {}
