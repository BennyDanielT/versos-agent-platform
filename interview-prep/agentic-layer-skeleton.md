# Agentic-Layer Skeleton — a reusable spine to wrap any simulation

A template to walk in with, so the interview is "adapt", not "design from scratch".
It mirrors the spine already proven in `pipeline_healer.py`:

> **adapter → perceive → decide (deterministic core + LLM for the fuzzy part) → autonomy gate → act → verify → decision log**

The whole bet: **the LLM is the planner, not the executor.** Every action is typed,
validated, gated, and logged before it touches the simulation. That single sentence is
your framing slide.

---

## 0. The 6 parts and which rubric each one buys you

| Part | File | Rubric it scores |
|------|------|------------------|
| **Adapter** | `sim_adapter.py` | Decomposition / separation of concerns |
| **Tool registry** | `tools.py` | Tool & interface design (safe, typed) |
| **Decision loop** | `agent.py` | Agent-loop correctness, termination |
| **Autonomy gate** | `gate.py` | Robustness / safety / guardrails |
| **Trace logger** | `trace.py` | Observability + evaluation |
| **Metric** | `metric.py` | Evaluation (almost nobody does this → senior signal) |

Build the smallest end-to-end loop first with a **dumb policy**, then deepen. A working
skeleton in the first hour beats a half-built brilliant design.

---

## 1. Adapter — wrap the sim as a black box

Do not edit the simulation internals. Wrap it in three verbs.

```python
# sim_adapter.py
from typing import Any
from dataclasses import dataclass

@dataclass
class Observation:
    state: dict[str, Any]      # whatever the sim exposes
    done: bool
    info: dict[str, Any]       # errors, scores, anything diagnostic

class SimAdapter:
    """Thin, stable interface over the provided simulation. The agent only sees this."""
    def __init__(self, sim):
        self._sim = sim

    def observe(self) -> Observation:
        s = self._sim.get_state()          # adapt to their API
        return Observation(state=s, done=self._sim.is_done(), info=self._sim.diagnostics())

    def act(self, action: "Action") -> Observation:
        self._sim.apply(action.name, **action.args)   # adapt to their API
        return self.observe()

    def reset(self) -> Observation:
        self._sim.reset()
        return self.observe()
```

Why it matters: when they ask "what if the sim changes?", you point here. One file changes.

---

## 2. Tool registry — typed, named, safe actions

Small set of well-scoped actions with a risk label. Risk feeds the gate (part 4).

```python
# tools.py
from dataclasses import dataclass, field
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
    validate: Callable[[dict], None]   # raise on bad args BEFORE the sim sees them

REGISTRY: dict[str, Tool] = {}

def tool(name, description, risk="low", validate=lambda a: None):
    def deco(_):
        REGISTRY[name] = Tool(name, description, risk, validate)
        return _
    return deco

# Example — adapt the verbs to the actual sim:
@tool("scale_workers", "Add capacity when a unit is overloaded. args: {amount:int 1-4}",
      risk="medium", validate=lambda a: (_ for _ in ()).throw(ValueError("amount 1-4"))
                     if not 1 <= a.get("amount", 0) <= 4 else None)
def _scale(): ...

def tool_specs() -> list[dict]:
    """What you hand the LLM as the tool menu."""
    return [{"name": t.name, "description": t.description} for t in REGISTRY.values()]
```

Talking point: the `validate` hook is why the agent can't push garbage into the sim even
if the model hallucinates args. "I never trust model text into the simulation."

---

## 3. Decision loop — perceive / decide / act / verify / terminate

Deterministic core for the known cases; LLM only for the fuzzy "which action, what args".

```python
# agent.py
import json
from sim_adapter import SimAdapter, Observation
from tools import Action, REGISTRY, tool_specs
from gate import gate
from trace import Trace

MAX_STEPS = 25

def decide(obs: Observation, llm) -> Action:
    """LLM is the planner. Structured output -> never free text into the sim."""
    prompt = (
        "You control a simulation. Choose ONE tool to move toward the goal.\n"
        f"State: {json.dumps(obs.state)}\n"
        f"Diagnostics: {json.dumps(obs.info)}\n"
        f"Tools: {json.dumps(tool_specs())}\n"
        'Reply JSON: {"reason": "...", "tool": "name", "args": {...}}'
    )
    raw = llm.complete_json(prompt)          # use Claude Opus 4.8 structured output
    t = REGISTRY[raw["tool"]]
    action = Action(name=t.name, args=raw["args"], risk=t.risk)
    t.validate(action.args)                  # raises -> caught by loop -> retry/skip
    return action, raw["reason"]

def run(sim, llm) -> dict:
    adapter, trace = SimAdapter(sim), Trace()
    obs = adapter.observe()
    for step in range(MAX_STEPS):
        if obs.done:
            trace.log(step, "TERMINATE", "sim reports done", None, obs)
            break
        try:
            action, reason = decide(obs, llm)
        except (ValueError, KeyError) as e:        # bad/hallucinated action
            trace.log(step, "REJECT", f"invalid action: {e}", None, obs)
            continue
        mode, gate_reason = gate(action)           # autonomy gate
        if mode == "block":
            trace.log(step, "BLOCK", gate_reason, action, obs)
            continue
        if mode == "suggest":
            trace.log(step, "PROPOSE", gate_reason, action, obs)   # human-in-loop
            continue
        obs = adapter.act(action)                  # mode == "auto"
        trace.log(step, "ACT", reason, action, obs)
    return {"trace": trace.rows, "metric": trace.summary()}
```

Note the three loop guards graders look for: **MAX_STEPS** (no infinite loop),
**done check** (termination), **reject-and-continue** (graceful degrade on bad output).

---

## 4. Autonomy gate — the guardrail that makes it an *agent*, not a while-loop

Kill switch + risk policy. High-risk / destructive actions are hard-held to "suggest".

```python
# gate.py
from tools import Action

KILL_SWITCH = False     # flip to freeze all autonomous action -> everything proposes

POLICY = {              # (risk) -> mode
    "low":    "auto",
    "medium": "auto",
    "high":   "suggest",     # destructive / irreversible -> always human-in-loop
}

def gate(action: Action) -> tuple[str, str]:
    if KILL_SWITCH:
        return "suggest", "kill switch engaged -> propose only"
    mode = POLICY.get(action.risk, "suggest")
    return mode, f"{action.name}/{action.risk} -> {mode}"
```

This is your "break it on purpose" demo: engage the kill switch live, show the agent
keep reasoning but stop touching the sim, then release it and watch it recover.

---

## 5. Trace logger — observability + the metric

Log every decision with its reasoning. This is the single highest-leverage artifact:
it makes the demo legible and proves the agent reasons, not hallucinates.

```python
# trace.py
class Trace:
    def __init__(self):
        self.rows: list[dict] = []

    def log(self, step, kind, reason, action, obs):
        self.rows.append({
            "step": step, "kind": kind, "reason": reason,
            "action": None if action is None else {"tool": action.name, "args": action.args},
            "done": obs.done,
        })
        print(f"[{step:02d}] {kind:9} {reason}"
              + (f"  -> {action.name}({action.args})" if action else ""))

    def summary(self) -> dict:
        acts = [r for r in self.rows if r["kind"] == "ACT"]
        return {
            "steps": len(self.rows),
            "actions_taken": len(acts),
            "rejected": sum(r["kind"] == "REJECT" for r in self.rows),
            "blocked": sum(r["kind"] in ("BLOCK", "PROPOSE") for r in self.rows),
            "resolved": any(r["done"] for r in self.rows),
        }
```

---

## 6. Metric — define success and measure it

Pick one crude, defensible number and report it. This reads as senior because almost
nobody does it.

- **Task completion %** — did the sim reach `done` in the goal state?
- **Steps-to-goal** — efficiency; fewer is better.
- **Recovery rate** — of injected failures, how many did the agent recover from?
- **Rejected-action rate** — how often the LLM proposed something invalid (model-honesty).

`trace.summary()` already emits these. In the demo, run 3–5 episodes and show the number.

---

## Demo script (≈12 min)

1. **Framing (2 min)** — one architecture diagram (sim ↔ adapter ↔ agent: tools, loop,
   gate, trace) + the one-line bet: "LLM as planner, every action typed/gated/logged".
2. **Live run (5–7 min)** — run it, narrate the trace: "observed X, reasoned Y, chose
   tool Z, sim responded W." Then **inject a failure / flip the kill switch** and show
   graceful recovery. Recovering live is the most memorable thing you can do.
3. **Reflection (2–3 min)** — the metric across a few episodes, where it's brittle, what
   you'd add with more time (memory across episodes, multi-agent only if it earns its
   coordination cost).

**Fallback:** record one clean run beforehand in case the live demo flakes.

---

## Trade-offs to volunteer (judgment > complexity)

- "Considered multi-agent; rejected it — added coordination cost for no benefit at this scale."
- "Deterministic core for known cases, LLM only for fuzzy diagnosis — reliability where I can get it, flexibility where I need it." (exactly the `_DIAGNOSIS` split in `pipeline_healer.py`)
- "Structured output + validate hook so model text never reaches the sim raw."
- "Risk policy + kill switch so destructive actions stay human-in-loop."

## Rubric → artifact map (say this if they ask how you covered the rubric)

decomposition → adapter · tool design → registry+validate · loop correctness → MAX_STEPS/done/reject ·
robustness → gate+kill switch · observability → trace · evaluation → metric · communication → this script.
