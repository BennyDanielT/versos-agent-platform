# agent_skeleton — runnable agentic-layer template

Pure-stdlib, no API key, runs anywhere. The companion to
[`../agentic-layer-skeleton.md`](../agentic-layer-skeleton.md) — that doc explains the
design; this package *runs* it so you can rehearse a real trace.

```bash
python run_demo.py            # one narrated episode + the metric
python run_demo.py --kill     # kill switch engaged -> agent proposes, never acts
python run_demo.py --eval 5   # N episodes -> completion rate + avg steps-to-goal
```

## The seams you swap in the interview

| Stub | Replace with | File |
|------|--------------|------|
| `FakeSim` | the simulation they hand you | `fake_sim.py` -> only `SimAdapter` touches it |
| `FakeLLM` | `ClaudeLLM` (Opus 4.8, structured output) | `llm.py` |

Everything else — adapter, tool registry, decision loop, gate, trace, metric — stays.

## The spine

```
observe → decide (LLM plans) → validate → gate → act → verify → log
```

- `sim_adapter.py` — black-box wrapper (observe/act/reset). The only file that knows the sim's API.
- `tools.py` — typed action registry; `validate` rejects bad args before the sim sees them.
- `agent.py` — the loop. Guards: MAX_STEPS, done-check, reject-and-continue.
- `gate.py` — kill switch + risk policy; destructive actions hard-held to human-in-loop.
- `trace.py` — decision log + `summary()` metric.
- `llm.py` — FakeLLM (deterministic, demos the reject path) / ClaudeLLM (real).

## What each run demonstrates (rubric → moment)

- **step 00 REJECT** — model proposed a malformed `scale_workers`; validate caught it. *(robustness / model-honesty)*
- **escalate archive** — corrupt unit has no safe fix; agent escalates instead of thrashing. *(judgment)*
- **`--kill`** — agent keeps reasoning but stops acting; flip back and it recovers. *(guardrails — the live "break it" moment)*
- **`--eval`** — completion rate + steps-to-goal. *(evaluation — the senior signal)*
