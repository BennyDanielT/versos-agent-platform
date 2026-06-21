# NeMo Agent Toolkit — Verified Primer

> Researched against official docs (v1.6) AND **verified hands-on against
> v1.8.0** installed in this repo's venv (June 2026). NAT moves fast; re-check the
> interview machine with `nat --version`.

## ✅ Hands-on verification log (v1.8.0, nvidia-nat[langchain])
What I confirmed by actually running it here — and where the docs/my first draft
were wrong (version drift is real; trust the live machine):

- **CLI is `nat`**, package `nvidia-nat`, version came back `1.8.0`.
- **`nat info components`** is the command — NOT `nat info list-components` (old
  docs). Filter with `-t function|evaluator|tracing|llm_provider|...`.
- **Custom function pattern works** end-to-end: scaffolded with
  `nat workflow create`, ran via `nat run` → got our function's output. Confirmed.
- **Canonical imports in 1.8 come from `nat.plugin_api`** (one aggregator):
  `Builder, FunctionBaseConfig, FunctionInfo, LLMFrameworkEnum, register_function`.
- Decorator takes a **`framework_wrappers=[LLMFrameworkEnum.LANGCHAIN]`** arg.
- A function can be the **workflow entrypoint** (`workflow._type: <your_fn>`), so you
  can run/test with **no LLM and no API key**.
- **Evaluators actually bundled here:** `trajectory`, `langsmith` (openevals).
  ⚠️ **`ragas` is NOT bundled** with `[langchain]` — needs a separate extra/plugin.
- **Tracing exporters bundled:** `file`, `otelcollector`, `langfuse`, `langsmith`,
  `galileo`. ⚠️ **No `phoenix` type in 1.8** — point `otelcollector` at Phoenix's
  OTLP endpoint instead. (Older docs show a `phoenix` `_type`.)
- **LLM providers:** `nim`, `openai`, `aws_bedrock`, `azure_openai`.
- **Windows gotchas:** (1) `nat workflow create` fails on a symlink step (WinError
  1314) unless Developer Mode/admin is on — but it still writes all the real files
  first. (2) Console output can hit `UnicodeEncodeError` on ✓/✗ glyphs; prefix
  commands with `PYTHONIOENCODING=utf-8`. Neither should affect a Linux interview box.

## 0. Naming (so you're not confused)
Same product, renamed twice: **AgentIQ → AIQ → NeMo Agent Toolkit (NAT)**. Old
docs/blogs say `aiq ...`; current CLI is `nat ...`. PyPI package is `nvidia-nat`.
The toolkit's Python namespace is `nat`.

---

## 1. What it actually is (mental model)

NAT is **not** a new agent framework that competes with LangGraph. It's an
**orchestration + instrumentation layer that sits *around* agents** built in any
framework (LangChain/LangGraph, LlamaIndex, CrewAI, Semantic Kernel, Google ADK,
or plain Python). Its value proposition is the three things Versos cares about:

- **Observability** — trace every function/LLM/tool call, latency, tokens.
- **Evaluation** — offline eval harness with datasets + scorers.
- **Profiling/optimization** — find bottlenecks down to the token.

The unifying idea: you describe your system **declaratively in a YAML config**
(which functions, which LLMs, which workflow), and register your Python logic as
**functions**. NAT wires them together (dependency injection), runs them, and
instruments everything automatically.

> One-liner for the interview: *"NAT lets me describe an agent system as config +
> registered functions, and gives me tracing, evals, and profiling for free because
> every call flows through its instrumented event stream."*

### How it differs from LangGraph (you're coming from LangGraph)
| LangGraph | NeMo Agent Toolkit |
|---|---|
| You build a `StateGraph` in Python | You declare a `workflow` in YAML; logic lives in registered functions |
| Nodes = Python functions you wire with edges | Functions registered via `@register_function`, composed by config |
| Observability = you add LangSmith yourself | Observability is built-in via telemetry exporters (Phoenix/OTel/etc.) |
| Evals = you bolt on | `eval` section in config + `nat eval` command |
| Framework *is* the runtime | Framework-agnostic; can even *wrap* a LangGraph agent as a function |

Key insight: **NAT and LangGraph aren't mutually exclusive.** You can build the
agent logic in LangGraph and run/instrument it inside NAT. (`pip install
"nvidia-nat[langchain]"`.)

---

## 2. Install & prerequisites
```bash
pip install nvidia-nat                 # core
pip install "nvidia-nat[langchain]"    # + LangChain/LangGraph integration
pip install "nvidia-nat[telemetry]"    # + observability exporters (Phoenix, OTel)
export NVIDIA_API_KEY=nvapi-...        # required (build.nvidia.com)
```
Python 3.11 / 3.12 / 3.13.

Sanity check the install: `nat --version`, then `nat info list-components`
(lists every registered function/llm/evaluator type available to you).

---

## 3. The five primitives

1. **LLMs** — declared in YAML under `llms:`, referenced by name. `_type: nim`
   for NVIDIA NIM models.
2. **Functions** (== tools) — reusable units agents call. Built-in ones (e.g.
   `wiki_search`) or your own custom Python. Declared under `functions:`.
3. **Workflow** — the top-level orchestration under `workflow:`. Often an agent
   type like `react_agent`, `tool_calling_agent`, or `reasoning_agent`, OR your
   own custom function as the entry point.
4. **Builder** — NAT's **dependency-injection** system. Inside a function you get
   a `builder` to fetch LLMs (`builder.get_llm(...)`) and other functions
   (`builder.get_function(...)`) instead of constructing them yourself.
5. **Config (YAML)** — the single source of truth tying it all together.

---

## 4. THE key skill — writing a custom function (verbatim pattern)

This is what you'll do most in the interview. A function = a config class +
a registered async generator that **yields** a `FunctionInfo`.

```python
from pydantic import Field
# v1.8 canonical import surface — one aggregator module (verified hands-on):
from nat.plugin_api import (
    Builder, FunctionBaseConfig, FunctionInfo, LLMFrameworkEnum, register_function,
)


# 1) Config class — inherits FunctionBaseConfig, the name= is the _type in YAML
class TriageTicketConfig(FunctionBaseConfig, name="triage_ticket"):
    llm_name: str = Field(description="which configured LLM to use")
    max_severity_auto: str = Field("medium", description="cap for auto mode")


# 2) Register it. framework_wrappers tells NAT to expose this to LangChain too.
@register_function(config_type=TriageTicketConfig,
                   framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def triage_ticket(config: TriageTicketConfig, builder: Builder):

    # Grab dependencies from the builder, not by hand:
    llm = await builder.get_llm(config.llm_name, wrapper_type="langchain")

    # 3) The actual callable the agent/workflow invokes:
    async def _inner(complaint_text: str) -> str:
        # ... your logic: prompt the llm, hit Postgres, etc. ...
        return result

    # 4) Yield a FunctionInfo (description is what the agent "sees" as the tool doc)
    yield FunctionInfo.from_fn(
        _inner,
        description="Classify a support ticket and recommend an autonomy mode.",
    )
    # code after the yield runs on cleanup/teardown
```

Why each piece matters (say this out loud):
- **Config class** → your function is configurable from YAML, so behavior is
  declarative and reviewable.
- **`builder.get_llm`** → DI means the same function works with any LLM/provider
  the config points at — that's your "provider seam" for free.
- **`FunctionInfo.from_fn(description=...)`** → the description IS the tool spec the
  agent uses to decide when to call it. Treat it as prompt engineering.
- **async generator + `yield`** → setup before yield, teardown after; clean
  resource lifecycle (e.g. open/close a DB pool).

The class lives *inside or alongside* registration; NAT matches `config_type` to
the YAML `_type` via the `name=`.

---

## 5. Workflow YAML (the config that ties it together)

```yaml
llms:
  nim_llm:
    _type: nim
    model_name: nvidia/llama-3.3-nemotron-super-49b-v1
    temperature: 0.0

functions:
  triage_ticket:              # matches name="triage_ticket"
    _type: triage_ticket
    llm_name: nim_llm
    max_severity_auto: medium

workflow:
  _type: react_agent          # built-in ReAct agent as the orchestrator
  tool_names: [triage_ticket] # the functions it can call
  llm_name: nim_llm
  verbose: true
```

Run it:
```bash
nat run --config_file configs/triage.yml --input "Audio drops at 0:30 on my export"
```

For a custom orchestrator, set `workflow._type` to your own registered function
instead of `react_agent`.

---

## 6. Observability (Pillar 1) — built-in, config-only

```yaml
general:
  telemetry:
    logging:
      console:
        _type: console
        level: WARN
    tracing:
      phoenix:
        _type: phoenix
        endpoint: http://localhost:6006/v1/traces
        project: versos_agents
```

- Spin up Phoenix locally (`pip install arize-phoenix`, `phoenix serve`) and every
  function/LLM/tool call shows up as a trace: latency, tokens, inputs/outputs.
- Mechanism: NAT publishes **`IntermediateStep`** events to a reactive event
  stream (Subject/Observer); telemetry exporters subscribe and ship them
  **asynchronously, off the hot path**. Also supports OpenTelemetry collector,
  Langfuse, Weave, Catalyst.
- *Interview line:* "Observability isn't bolted on — every call is an
  IntermediateStep on an event stream, so tracing, logging, and profiling all read
  the same source of truth."

---

## 7. Evaluation (Pillar 2) — the part most candidates skip

```yaml
eval:
  general:
    output_dir: ./.tmp/versos_eval/
    dataset:
      _type: json
      file_path: data/triage_eval.json
  evaluators:
    triage_accuracy:
      _type: ragas
      metric: AnswerAccuracy
      llm_name: nim_judge_llm
    tool_trajectory:
      _type: trajectory          # did it call the right tools in the right order?
      llm_name: nim_judge_llm
```

Dataset is JSON/JSONL/CSV/Parquet with `id` / `question` / `answer` style records
(input + expected output). Run:
```bash
nat eval --config_file configs/triage_eval.yml
```

Built-in evaluators: **`ragas`** (AnswerAccuracy, ContextRelevance,
ResponseGroundedness), **`trajectory`** (judges intermediate steps/tool choices
0–1), **`tunable_rag`**, **`swe_bench`**, plus **custom evaluators** via the plugin
system. A custom evaluator is itself a registered component that scores
input/output pairs.

- *Interview line:* "I don't fake the model to test it. The deterministic policy
  gets unit tests; the probabilistic agent gets a dataset + `nat eval` with an
  LLM-judge for accuracy and a trajectory scorer for tool use."

---

## 8. Guardrails (Pillar 3) — be precise here
NAT's three native pillars are observe/evaluate/profile. **Guardrails** are
realized two ways, and you should name both:
1. **In-system guardrails you build** — implement them as functions/wrappers:
   input validation, an allow-list of actions, a human-approval gate, a
   confidence/severity policy that caps autonomy (your `decide()` logic), kill
   switches as config flags. These are the highest-value, framework-agnostic ones.
2. **NeMo Guardrails** (a *separate* NVIDIA library) — for input/output rails
   (topical, safety, jailbreak). It can be wrapped as a NAT function/tool. Mention
   it as the "rails for content"; don't claim it's the same package as NAT.

> ⚠️ Verify on the day whether the installed NAT exposes a first-class guardrail
> component (`nat info list-components` will tell you). Don't assert an API you
> haven't seen.

---

## 9. CLI cheat sheet
```bash
nat --version
nat info list-components          # discover available functions/llms/evaluators
nat run    --config_file f.yml --input "..."   # one-shot run
nat serve  --config_file f.yml                 # REST endpoint + built-in chat UI
nat eval   --config_file f.yml                 # run the eval harness
nat configure telemetry --status               # telemetry consent
```

---

## 10. Postgres in this picture
NAT has no opinion about your database — Postgres lives **inside your functions**.
Pattern: open an async pool in the function's setup (before `yield`), use it in
`_inner`, close it after `yield`. Keep the **business-records-vs-telemetry split**:
domain rows (tickets, assets, findings) in Postgres; agent telemetry in
Phoenix/OTel via NAT. (Same principle as the LangGraph version — it transfers 1:1.)

---

## 11. LangGraph → NAT translation (for porting the practice project)
| Practice project (LangGraph) | NAT equivalent |
|---|---|
| `StateGraph` + nodes in `graph.py` | a custom workflow function, or `react_agent` over tools |
| each specialist (`classify`, etc.) | each a `@register_function` |
| `get_structured_llm()` provider seam | `builder.get_llm(name)` + YAML `llms:` |
| `decide()` promotion policy | a registered function (still pure logic, still unit-tested) |
| manual LangSmith wiring | `general.telemetry.tracing` (config only) |
| pytest only | pytest (policy) + `nat eval` (agent quality) |
| FastAPI endpoints | `nat serve` (or keep FastAPI calling NAT) |

---

## 12. What to verify live on the interview machine (don't trust this doc blindly)
- `nat --version` → adjust for the installed version's syntax.
- `nat info list-components` → see the real functions/evaluators/telemetry types.
- Whether `[telemetry]` / Phoenix are installed (if not, console tracing still works).
- The exact NIM model names available with their `NVIDIA_API_KEY`.
```
