# My Technical Q&A Log

> **Living document.** Every technical question I ask gets recorded here with a clear
> answer, so I build a personal reference and can revise before the interview. Newest
> at the bottom. Format: the question, a plain-English answer, and a "say-it-in-one-line"
> summary for the interview.

---

## Q1 — What is the `pyproject.toml` file?

**Short answer:** It's the standard configuration file for a Python project. One file
that tells Python's packaging tools (like `pip`) the project's **name, version,
dependencies, and how to build/install it**. Think of it as the "ID card + shopping
list + assembly instructions" for a Python package.

**Why it exists:** Older Python projects scattered this across several files
(`setup.py`, `setup.cfg`, `requirements.txt`, etc.). `pyproject.toml` (introduced by
[PEP 518](https://peps.python.org/pep-0518/) / [PEP 621](https://peps.python.org/pep-0621/))
consolidated it into one standardized file. `.toml` = "Tom's Obvious Minimal Language",
a simple key-value config format (like a cleaner INI file).

**What's inside it (the common pieces):**
```toml
[build-system]                      # which tool builds the package, e.g. setuptools/hatch
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]                           # the package's identity + dependencies
name = "versos_hello"
version = "0.1.0"
dependencies = [                    # what gets installed alongside it
    "nvidia-nat[langchain]",
]

[project.entry-points.'...']        # OPTIONAL: hooks that let other tools discover this package
```

**Why it matters for us / NAT specifically:** When you ran
`pip install -e nat_sandbox/versos_hello`, pip read that package's `pyproject.toml` to
know what to install and — crucially — its **entry points**. NAT discovers your custom
functions through entry points declared in `pyproject.toml`. That's the mechanism that
makes `nat info components` find your `versos_hello` function. So `pyproject.toml` isn't
just bookkeeping here — it's the wiring that registers your tools with NAT.

**`pip install -e` (editable):** the `-e` flag installs the package as a live link to
your source folder, so when you edit the function code, the change takes effect without
reinstalling. Great during a timed build.

**Where you've already seen it:** `nat_sandbox/versos_hello/pyproject.toml` — generated
by `nat workflow create`. Open it and you'll see the `name`, `dependencies`, and the
entry-point block that registers the function with NAT.

**Say-it-in-one-line:** *"`pyproject.toml` is the standardized config that defines a
Python package's identity, dependencies, and build — and in NAT it's also where the
entry points live that register my custom functions so the toolkit can discover them."*

## Q2 — Model vs chat model?

A plain **model** (completion/LLM) = **text in → text out**. A **chat model** =
**a list of role-tagged messages** (`system`/`user`/`assistant`) **in → an assistant
message out**. Modern instruct models are chat models. `builder.get_llm(...)` returns
a chat model; passing it a string wraps it as a user message, and the reply is a
message object whose `.content` holds the text.

**One-liner:** *"Completion models are text-to-text; chat models take role-tagged
messages and return a message — that's what NAT/LangChain hand me."*

## Q3 — Why async functions (and how to explain it)?

Agent work is **I/O-bound**: it spends most of its time *waiting* on the LLM API and
the database, not using CPU. `async`/`await` lets one process **do other work while
waiting** instead of blocking a whole thread per call. So one process serves many
concurrent agent calls. NAT is async-native, so functions are `async`.

**One-liner:** *"LLM and DB calls are I/O-bound; async lets one event loop juggle many
concurrent agent calls without blocking — higher throughput on the same hardware."*

## Q4 — What does `wrapper_type=LANGCHAIN` (in `builder.get_llm`) do?

NAT is **framework-agnostic** and stores the LLM config once. `wrapper_type` says
"hand me this model as a `<framework>` object." `LANGCHAIN` → I get a **LangChain chat
model**, so I can use LangChain's API (`.ainvoke`, etc.). Ask for a different wrapper
and I'd get the same configured model shaped for LlamaIndex/CrewAI/etc. **It's an
adapter** between NAT's config and the framework I'm coding in.

**One-liner:** *"It adapts NAT's single LLM config into the framework object I want to
code against — LANGCHAIN gives me a LangChain chat model."*

## Q5 — How do I export the API key to the shell environment?

"Shell env" = variables the running terminal holds and passes to programs it launches.
NAT reads `NVIDIA_API_KEY` from there — it does NOT auto-load `.env`.
- **PowerShell:** `$env:NVIDIA_API_KEY="nvapi-..."`
- **Git Bash:** `export NVIDIA_API_KEY=nvapi-...`
- **From .env (Git Bash):** `export NVIDIA_API_KEY=$(grep ^NVIDIA_API_KEY= .env | cut -d= -f2- | tr -d '\r"')`
Lasts for that terminal session only.

**One-liner:** *"Set it as an environment variable in the terminal session; NAT reads
the key from the shell env, not from the .env file."*

## Q6 — Explain `ainvoke()`.

LangChain runnables expose **`invoke`** (synchronous) and **`ainvoke`** (asynchronous —
the leading "a"). `await llm.ainvoke(prompt)` **sends the prompt and awaits the reply
without blocking** the event loop. It returns a message object; `.content` is the text.

**One-liner:** *"`ainvoke` is the async version of `invoke` — it calls the model and
awaits the response without blocking, returning a message whose `.content` is the text."*

## Q7 — Why `yield` instead of `return` in a NAT function?

`@register_function` expects an **async generator**. `yield`ing the `FunctionInfo` lets
NAT run my **setup once (before the yield)**, **hold the tool while the workflow runs**,
then **resume after the yield for teardown** (e.g. close a DB pool). It behaves like a
**context manager**: "here's the tool — pause — clean up when done." `return` would exit
immediately with no place to put teardown.

**One-liner:** *"The function is an async generator: code before `yield` is one-time
setup, the `yield` hands NAT the tool, and code after `yield` is teardown — `return`
gives me no cleanup hook."*

## Q8 — Can I use `load_dotenv()` instead of exporting the key?

Yes. `load_dotenv()` (from `python-dotenv`) **reads `.env` and loads its vars into
`os.environ`** at runtime — doing in Python what a shell `export` does. For the `nat`
CLI, call it at the **top of `register.py`**, because NAT imports that file when it
loads the package, BEFORE it builds the LLM — so the key is in the environment in time.
```python
from dotenv import load_dotenv
load_dotenv()
```
Caveat: it only helps if it runs *before* the key is read; `register.py` is the right spot.

**One-liner:** *"`load_dotenv()` loads .env into the process environment at runtime; I
put it at the top of register.py so the key is set before NAT builds the LLM."*

## Q9 — invoke vs ainvoke (clearer): it's about blocking

Both send input to the model and return its output. The difference is what the program
does *while waiting*:
- **`invoke(x)`** = synchronous: the code **stops and waits**, idle, until the reply.
- **`await ainvoke(x)`** = asynchronous: while waiting, the **event loop runs other
  tasks**. The wait isn't wasted. Used inside async functions (like NAT's).

**One-liner:** *"Same call, but `invoke` blocks while it waits and `ainvoke` yields the
wait back to the event loop so other work proceeds."*

## Q10 — What is a generator, and why does `yield` matter for NAT tools?

A **normal function** runs top-to-bottom, hits `return` once, returns **one value and
forgets everything** (locals gone). A **generator function** uses **`yield`**, which:
1. **pauses** the function and hands out a value, keeping **all locals alive**, and
2. on **resume**, continues **right after the `yield`**.

So: code **before `yield` = setup** (runs at start); `yield` **hands out the value and
pauses**; code **after `yield` = teardown** (runs on resume).

NAT uses this to give each tool a **setup → use → cleanup** lifecycle:
- before `yield`: acquire deps (LLM, DB pool) — runs once,
- `yield FunctionInfo(...)`: hand the tool to NAT and **pause** (deps stay in memory
  while the workflow runs),
- after `yield`: cleanup (close pool) — runs when the workflow ends.

`return` would end the function immediately: no place for teardown, and setup objects
could be torn down too early. It's exactly a **context manager** (`with` block):
setup → resource → cleanup. An **async generator** = `async def` + `yield`.

**One-liner:** *"The function is a generator so `yield` can pause it: code before yield
is one-time setup, the yield hands NAT the live tool, and code after yield is teardown —
like a `with` block. `return` gives no cleanup hook."*

## Q11 — Structured output: `with_structured_output` vs prompt+parse, and the enum trap

Two ways to get typed output from an LLM:
1. **Prompt for JSON + `json.loads` + Pydantic `model_validate`** — portable, works with any
   text model, you own parsing/retries.
2. **`llm.with_structured_output(Schema)`** — the provider enforces the shape via
   tool-calling / JSON-mode and returns a typed object. Cleaner; **best practice when the
   model/provider support it reliably.** Still validate with Pydantic as a safety net.

**The trap I hit:** structured output enforces the *shape* (it's a string) but NOT the
*allowed values* or *casing*. A `severity: str` field happily accepted `"Low"` and a
`category: str` accepted `"Minor Issue"` — which silently broke a policy that keyed on
exact lowercase values. Fix: use `Literal["low","medium",...]` so the schema constrains
the model, plus a `field_validator(mode="before")` to normalize case. Principle:
**strictness proportional to risk** — strict `Literal` on safety-critical fields
(severity), lenient + map-to-default on metadata (category).

**One-liner:** *"with_structured_output enforces the schema's shape, not its enum values —
so I use Literal types for the constrained fields and still validate with Pydantic."*

## Q12 — `truststore`: fixing CERTIFICATE_VERIFY_FAILED on a corporate network

A corporate proxy intercepts HTTPS with its own CA. Python doesn't trust that CA by default,
so requests fail with `CERTIFICATE_VERIFY_FAILED` (e.g. the `/v1/models` call that
`with_structured_output` makes). `truststore` makes Python's `ssl` use the **OS certificate
store** (which already trusts the corporate CA): `import truststore; truststore.inject_into_ssl()`
once, before any HTTPS call (top of `register.py`). Likely unnecessary on a clean interview box.

**One-liner:** *"truststore points Python's SSL at the OS trust store, so a corporate
proxy's CA is trusted and HTTPS verification stops failing."*

## Q13 — Why store the autonomy policy in a Postgres table instead of in code?

So humans can steer the agent's autonomy WITHOUT a redeploy. A `triage_policy` table
maps each segment `(severity, category)` to an `approved_mode` ceiling + a
`min_confidence` bar. The tool LOOKS IT UP at runtime; the agent never writes it.
Promotion ("let low/media_quality go auto") becomes a human `UPDATE`, justified by
evals. Two safety layers: the table grants the ceiling, and code keeps a HARD guardrail
regardless (critical is never auto — defense in depth). Every decision is also written
to a `triage_log` table, which doubles as the audit trail and the future evals dataset.

**One-liner:** *"Policy-as-data: humans grant per-segment autonomy in a table the agent
reads; promotion is an UPDATE backed by evals, with a hard code-level guardrail on top."*

## Q14 — How does a NAT tool use Postgres, and where does the pool live?

NAT has no DB opinion — Postgres lives inside the function. Open an `asyncpg` pool in
SETUP (before `yield`), use it in the inner per-call function, close it in TEARDOWN
(after `yield`). That's the generator lifecycle doing real work: one pool, opened once,
reused per call, closed cleanly. DSN format is `postgresql://user:pass@host:5432/db`
(no `+asyncpg`). For JSON columns, pass `json.dumps(value)` and cast `$n::jsonb`.

**One-liner:** *"The asyncpg pool opens before the yield and closes after it — the
function's setup/teardown lifecycle owns the connection, reused across calls."*

## Q15 — The human-review + promotion loop (how autonomy is earned)

Two tables, different grain: `triage_policy` = rules (one row per segment, humans edit,
rare updates); `triage_log` = events (one row per ticket) and it ALSO holds the review.
Flow: agent suggests on every ticket → dev approves/rejects and writes `final_remediation`
(the corrected gold answer) + `review_comment` → metrics accrue per (severity, category)
→ on a PERIODIC governance review (weekly/monthly, not per-request) a human `UPDATE`s a
policy row to raise the segment once it clears the bar → keep sampling auto'd decisions
and AUTO-DEMOTE on regression. Modes: suggest = human writes/sends; approved = agent
drafts, human one-click sends; auto = agent sends alone. Log keeps BOTH the agent's
original `developer_remediation` and the dev's `final_remediation` — original vs gold is
prime eval/training data; `review_comment` is the why.

**One-liner:** *"Policy is rules (rare human edits), the log is events + the dev's review;
promotion is a periodic human UPDATE backed by per-segment metrics, with auto-demote on
regression."*

## Q16 — Confidence calibration: reliability diagram, ECE, vs precision

LLM self-reported confidence is **uncalibrated** (usually overconfident), so don't gate
autonomy on the raw number. Grade it against the dev approve/reject labels:

- **Reliability diagram:** x-axis = confidence the agent claimed (0→1); y-axis = fraction
  actually correct (dev accept-rate) for items in that confidence bin. Diagonal (x=y) =
  honest; dots BELOW = overconfident (the usual case).
- **ECE (Expected Calibration Error)** = weighted-average gap from the diagonal:
  `ECE = Σ (bin_size/total) × |avg_confidence(bin) − accuracy(bin)|`.
  The y value is **accuracy within the bin** (fraction correct), NOT precision.
- **Fix (post-hoc calibration):** learn `raw → true` from history (isotonic / Platt /
  temperature scaling), store `calibrated_confidence`, and gate `auto` on THAT.
- Cheaper signal when no logprobs: **self-consistency** (sample 3–5×, measure agreement).

Calibration ≠ precision. Track both: **ECE** = "is 0.9 really 0.9?" (honest number);
**precision/recall** = "when it acts, how often right / how much it catches" (safe action).
Ground-truth label = the DEVELOPER's approve/reject; customer outcome (resolved/reopened/
CSAT) is a separate, stronger-but-sparser signal layered in later.

**One-liner:** *"Self-reported confidence is uncalibrated; I grade it with a reliability
diagram + ECE against dev labels, apply post-hoc calibration, and gate autonomy on the
calibrated number — ECE checks the number is honest, precision checks the action is safe."*

## Q17 — suggest vs approved vs auto (autonomy ladder)

For a customer-facing action, the difference is WHO executes:
- **suggest** = agent drafts; the HUMAN writes/sends the actual reply. Agent never touches
  the customer.
- **approved** = agent writes the real reply and queues it; human clicks "send" → the
  AGENT sends it. Human is a gate, not the typist.
- **auto** = agent sends it itself, no human.

So: suggest → human does the work; approved → agent does the work after one human yes;
auto → agent alone. Promotion up this ladder is per (severity, category) segment, granted
by a human UPDATE to the `triage_policy` table once evals clear the bar.

**One-liner:** *"suggest = advise, approved = act-after-one-click, auto = act-alone — and a
segment climbs the ladder only when its review metrics earn it."*

## Q18 — Policy stores the calibrated bar; log stores raw AND calibrated

The `triage_policy.min_confidence` bar lives in **calibrated** space — at runtime you gate
the *calibrated* confidence against it. The `triage_log` stores **both**: `raw_confidence`
(needed to refit the calibrator and measure ECE — never lose the original signal) and
`calibrated_confidence` (the number the decision actually used, for audit). Until a
calibrator exists, calibrated = raw.

**One-liner:** *"Policy holds the cured-number bar; the log keeps the lie and the cure —
raw to relearn/measure ECE, calibrated to explain the decision."*

## Q19 — Functions vs workflow in NAT: when is something which?

`workflow:` = the ONE entry point that runs on `nat run`/`nat serve`. `functions:` = the
toolbox it can reach for. Exactly one workflow; zero-or-many functions. "function" vs
"workflow" is a ROLE, not a code difference — the same registered function can be the
workflow (entry point) OR a tool in the box, depending on config.

Decision rule:
- **One job, fixed steps → make the function the workflow** (no LLM picking). e.g. triage.
- **Fixed multi-step pipeline → a custom workflow function that calls sub-functions in
  order** (deterministic, still no agent). e.g. index-hygiene (scan→find→propose→apply).
- **Must choose among tools / path varies → workflow = an agent** (`tool_calling_agent`)
  + the tools in `functions:`. e.g. ops-assistant chat, pipeline self-healer.
- A function can be BOTH: a standalone workflow (direct calls / nat eval / cron) AND a
  tool inside an agent.

**One-liner:** *"Workflow = the boss that runs; functions = the workers it can call. If
the job always goes the same way the worker IS the boss; if someone must decide which
worker, hire an agent boss."*

## Q20 — Why token/cost panels were empty, and how to capture tokens

Phoenix builds token/cost panels from `llm.token_count.*` attributes on an LLM span +
a price table. The empties had three causes:
1. NAT's traces only had `<workflow>` (chain) spans — no LLM span carrying token counts.
2. NAT's tracing pipeline is SEPARATE from the global OpenTelemetry SDK, so manually
   doing `trace.get_current_span().set_attribute(...)` hit a no-op span (didn't reach NAT's).
3. `with_structured_output` on NIM throws away usage (`include_raw` is NotImplemented),
   so even our code couldn't read tokens that way.

Fix: capture usage via **plain `ainvoke`** (the AIMessage has `usage_metadata` — NIM does
return input/output tokens), and add **OpenInference LangChain auto-instrumentation** so a
real `llm` span with token counts is emitted to Phoenix:
`phoenix.otel.register(endpoint=..., auto_instrument=True)` (env-gated by PHOENIX_TRACING).
Cost still shows $0 until a NIM price entry is added (Phoenix has no NIM prices); for
self-hosted NIM "cost" is really compute, so you'd set a custom per-token rate.

**Correction:** OpenInference hooks the UNDERLYING ChatNVIDIA call, so tokens are captured
whether you use `with_structured_output` or plain `ainvoke` — keep the structured-output
path. The `include_raw`/plain-ainvoke trick only matters if you need usage in your OWN code.

**One-liner:** *"NAT traces latency but not tokens; OpenInference LLM instrumentation captures
token usage from the underlying model call (so structured output stays), and cost needs a
manual price entry because Phoenix doesn't know NIM's rates."*

## Q21 — Token tracing config (recap of the working setup)

To get token counts into Phoenix:
1. `pip install arize-phoenix opentelemetry-exporter-otlp openinference-instrumentation-langchain`
2. Run Phoenix: `python -m phoenix.server.main serve` (UI/OTLP-HTTP @ 6006, gRPC @ 4317).
3. In `register.py`, env-gated:
   ```python
   import os
   if os.getenv("PHOENIX_TRACING") == "1":
       from phoenix.otel import register
       register(project_name="versos_triage",
                endpoint="http://localhost:6006/v1/traces", auto_instrument=True)
   ```
4. Run with `PHOENIX_TRACING=1 nat run ...`.
Result: an `llm ChatNVIDIA` span with token counts lands in the **versos_triage** project
(OpenInference). NAT's own tracing (otelcollector → `default` project) shows the `<workflow>`
span but no tokens. Cost stays $0 until a NIM price entry is added.

## Q22 — Why a trace can look "trivial", and which project to read

Trace DEPTH mirrors ARCHITECTURE. A single deterministic tool (one LLM call, no routing)
produces a shallow trace — just input/output — because nothing is *choosing* tools. You
only see Thought→Action→tool→Observation spans when the workflow is an AGENT
(`tool_calling_agent`/`react_agent`) that decides which tools to call. Also: NAT's `default`
project logs only the `<workflow>` span; the richer sub-steps (llm span, parser,
RunnableSequence) are in the OpenInference **versos_triage** project. So "trivial" usually
means (a) single-step agent by design and/or (b) looking at the wrong project.

**One-liner:** *"Trace depth follows architecture — a single tool is shallow by design;
agents produce deep traces. And the LLM sub-steps live in the OpenInference project, not
NAT's default one."*

## Q23 — Latency percentiles (p50/p90/p99/max)

Percentiles describe the DISTRIBUTION of request latency, not the average:
- p50 (median) = half of requests finish faster than this.
- p90 = 9 of 10 finish faster (10% slower).
- p95/p99 = the slow TAIL — 99% finish faster; the 1% worst case.
- max = the single slowest run.
Averages hide outliers; the TAIL (p95/p99) is what users feel on a bad day, so ops teams
alert on the tail, not the mean.

**One-liner:** *"p90 means 9 of 10 runs are faster than that; the high percentiles are the
worst-case tail, which is what actually hurts users — so we watch the tail, not the average."*

## Q24 — Self-hosted NIM vs NVIDIA-hosted for the dark-factory ops?

Not either/or — a phased hybrid, and the choice is a config decision behind the provider seam.

**NVIDIA-hosted (build.nvidia.com) — to start:**
- Team of 5, "ship fast" → no GPU/k8s ops; first agents in prod today.
- Ops agents are low/bursty volume → per-call beats idle GPUs.

**Self-hosted NIM — for the autonomous core in steady state (the stronger long-game):**
- **Model stability protects the autonomy story.** suggest→auto is gated by calibration +
  evals; a hosted model updating silently drifts calibration and a promoted segment can go
  wrong. Self-host = pinned version = stable evals. (The insight most candidates miss:
  **autonomy gated on evals needs a model that doesn't change under you.**)
- **Reliability/independence** — "runs while no one is watching" can't depend on an external
  API's uptime.
- **Data residency** — ops agents read internal DBs/logs/customer data; self-host keeps it in-VPC.
- **Marginal cost** — they likely already run GPUs for their data pipeline; NIM is built to
  self-host, so it's incremental, not a new fleet.

**Answer:** hosted for prototyping + spiky/frontier; self-hosted/pinned NIM for high-volume,
sensitive, autonomous work. And you don't bet the architecture on it — the **provider seam**
(`builder.get_llm` + YAML `llms:`) makes hosted-vs-self-host a per-workload config swap.

**One-liner:** *"Hosted to move fast, self-hosted/pinned NIM for anything I trust to act
autonomously — because autonomy gated on evals needs a model that won't change under me —
and the provider seam keeps it a per-workload config choice, not a rewrite."*

## Q25 — Cost tracking: capturing tokens + computing cost at a provider rate

NVIDIA NIM deployment paths: Free Endpoint (build.nvidia.com, ~40 RPM, dev only — throttles,
not prod), Partner Endpoints (serverless, pay per 1M in/out tokens, e.g. Digital Ocean
$0.90/$1.70 — no infra), Self-Hosted (own GPUs + NVIDIA AI Enterprise license ~$4,500/GPU/yr;
"unlimited GPUs" = no usage cap, throughput bounded by hardware you license).

To track cost in our system:
- Capture token usage with `UsageMetadataCallbackHandler` passed via
  `ainvoke(prompt, config={"callbacks":[cb]})` — it collects usage even THROUGH
  `with_structured_output` (so we keep provider-enforced structured output).
- Price is a CONFIG field (USD per 1M in/out, default = Digital Ocean rate) so swapping
  provider/self-host is a config change, not code.
- Compute `cost = in/1e6*in_rate + out/1e6*out_rate`; store prompt_tokens/completion_tokens/
  cost_usd in triage_log. Then a GROUP BY (severity,category) rollup = the cost-watcher view.

Why DB cost (not just Phoenix): it's queryable business data (cost per customer/segment/day) —
the input to a cost-watcher agent. Phoenix's own cost panel needs the price set in Phoenix
settings; our DB is the source of truth.

**One-liner:** *"I capture tokens with a usage callback (works through structured output),
price them at a configurable per-1M rate, and store cost per decision in Postgres — so cost
is queryable per segment, which is exactly what a cost-watcher agent consumes."*

## Q26 — Self-host NIM cost math (e.g. 10 GPUs)

NVIDIA AI Enterprise license ≈ $4,500 per GPU per year. So 10 GPUs = ~$45k/year — but that
is the SOFTWARE LICENSE ONLY. Total cost of ownership = license + the GPUs themselves (buy
hardware, or rent cloud GPU-hours) + power/ops. The ~$1/GPU-hour cloud figure is a different
bundling: renting GPU + software by the hour instead of an annual license on owned hardware.
Trade-off vs partner endpoints (pay-per-token): self-host wins at high sustained volume and
for control/data-residency/model-pinning; partner/pay-per-token wins at low or bursty volume.

**One-liner:** *"10 GPUs is ~$45k/yr for the AI Enterprise license alone — add the GPUs and
ops on top; it pays off vs pay-per-token only at high sustained volume or when you need
control, data residency, or a pinned model."*

## Q27 — tool_calling_agent: version pins, the None bug, and model fit

The human-facing ops copilot = a `tool_calling_agent` (workflow) with tools in `functions:`.
The agent's reasoning LLM picks a tool via function-calling and extracts its arguments; the
tool runs and the agent summarizes the result for the human.

Three things that bit us (and the fixes):
- **langgraph version:** the env is on langchain 1.x, and NAT 1.8's agents need
  `langgraph>=1.2.5` (they import `langgraph.runtime` + `langgraph.prebuilt.ToolNode`).
  A stale `langgraph==0.2.62` pin from the old project broke ALL agent workflows — fix is
  `pip install "langgraph==1.2.6"`. Lesson: align langgraph with langchain-major + NAT.
- **`with_structured_output` can return `None`** (not raise) when the model's output won't
  parse — dereferencing `result.severity` then crashes. Guard: `if result is None: raise ...`
  so it hits the degradation path.
- **Model fit for structured output:** a tool that REQUIRES structured output needs a model
  that supports it (llama-3.1-8b does natively); the 550B nemotron is "not known to support
  structured output" and degrades intermittently. The agent's reasoning model and a tool's
  model can DIFFER — pick each for its job (agent = good tool-calling; triage tool = reliable
  structured output).

**One-liner:** *"The copilot is a tool_calling_agent that routes to tools; getting it running
meant aligning langgraph with langchain 1.x, guarding structured output that can return None,
and using a structured-output-capable model for the tool while the agent reasons with another."*

## Q28 — Custom FastAPI backend vs `nat serve`; embedding NAT in your own app

`nat serve` exposes ONE workflow per endpoint — fine for a quick demo, but a real app needs
many routes. So build your OWN FastAPI (backend/main.py) and split the work:
- **plain reads/writes** (list tickets, metrics, policy, review) -> asyncpg directly, NO NAT.
- **agentic actions** (triage, copilot ask) -> run NAT workflows IN-PROCESS.

Embed pattern (verified): in the FastAPI `lifespan`, build each workflow ONCE with
`nat.runtime.loader.load_workflow(config_file)` (async context manager → a session_manager),
keep it on `app.state`. Per request:
```python
async with session_manager.session() as session:
    async with session.run(message) as runner:
        result = await runner.result(to_type=str)
```
This keeps full NAT tracing for the agentic routes while reads are just SQL. Add CORS so the
Next.js dev server can call it. Next.js doesn't recreate routes — it just `fetch()`es the
backend; review's approve/reject is a backend route a HUMAN hits, never an agent tool.

**One-liner:** *"nat serve is one-workflow-per-endpoint; for a real app I run my own FastAPI
that does plain SQL for reads and embeds NAT workflows in-process (load_workflow in lifespan,
session.run per request) for the agentic routes — Next.js just fetches it."*

## Q29 — Production-grade FastAPI layering (routers / services / db / schemas)

Don't put everything in main.py. Layer it so each piece has one job:
```
backend/main.py         app factory + lifespan (composition only — no business logic)
backend/core/config.py  typed settings (+ normalize DSN)
backend/db.py           asyncpg pool + get_pool() dependency
backend/schemas.py      Pydantic request models (the contract)
backend/services/       business logic, NO FastAPI imports -> unit-testable, reusable
backend/routers/        thin HTTP layer (paths/status codes) -> calls services
```
Rule: **routers translate HTTP<->Python; services do the work; nothing leaks across.** Because
services import no FastAPI, a test or a cron job can call `tickets_service.list_tickets(pool)`
directly. NAT embedding is isolated in `nat_service` (swap NAT → only that file changes). The
pool is built once in lifespan and injected via `Depends(get_pool)`.

Gotcha hit: `.env` had a SQLAlchemy DSN `postgresql+asyncpg://...`; asyncpg needs plain
`postgresql://`, so config exposes an `asyncpg_dsn` that strips `+asyncpg`.

**One-liner:** *"Routers do HTTP, services do the work with no FastAPI imports (so they're
testable and reusable), db/config/schemas are their own layers, and all NAT embedding is
isolated in one service — so the system is production-grade, not a single fat main.py."*

## Q30 — Why asyncpg instead of SQLAlchemy?

asyncpg = a fast, low-level ASYNC Postgres driver: write SQL, get rows, minimal overhead.
SQLAlchemy = an ORM + toolkit on top (classes<->tables, query builder, relationships,
Alembic migrations, DB-agnostic). Chose asyncpg here because our queries are simple and few
(a handful of SELECT/INSERT/UPDATE), it's lighter + faster (one of the fastest PG drivers),
the NAT tools already use it (consistency), and we're Postgres-only.

Switch to SQLAlchemy when: many tables + relationships to navigate, you want typed models +
Alembic migrations, complex composed queries, or DB-agnostic code. (My old LangGraph-era
`app/` used async SQLAlchemy — both patterns exist in the repo to contrast.)

**One-liner:** *"asyncpg for a small, Postgres-only, simple-query service — speed and
simplicity; SQLAlchemy + Alembic once schema/query complexity or migrations matter."*

## Q31 — Why `async with` (context managers) everywhere in the backend?

The backend leans on context managers (`async with load_workflow(...)`, `session.run(...)`,
the pool, AsyncExitStack). Reasons:
- **RAII (Resource Acquisition Is Initialization)** — Python's clean way to tie a resource's
  lifetime to a block: acquire on enter, release on exit. (The fancy name to drop.)
- **Guaranteed cleanup** — even if an exception/crash happens inside the block, the
  `__aexit__` code still runs (close pool, end session, flush traces).
- **Prevents resource leaks** — stops Postgres from running out of connection slots, sessions
  from piling up, files/sockets from staying open. The `with` block can't "forget" to clean up.

This is the same setup→use→teardown idea as a NAT function's `yield` (Q7/Q10) — both are RAII:
acquire before, guaranteed release after.

**One-liner:** *"Context managers give RAII — acquire on enter, guaranteed release on exit
even on errors — so connections/sessions/files never leak; it's the same setup/teardown
contract as a NAT function's yield."*

## Q32 — Building a custom NAT evaluator (and what our eval found)

`nat eval` runs the workflow over a dataset and scores it. Bundled evaluators (`trajectory`,
`langsmith`/openevals) judge tool-trajectory or fuzzy text — useless on a structured JSON
output. So write a TASK-SPECIFIC custom evaluator that scores the field that GATES AUTONOMY.

Pattern (verified, NAT 1.8):
```python
class SeverityAccuracyConfig(EvaluatorBaseConfig, name="severity_accuracy"): ...
@register_evaluator(config_type=SeverityAccuracyConfig)
async def register_x(config, builder: EvalBuilder):
    async def evaluate(eval_input) -> EvalOutput:
        # eval_input.eval_input_items[i]: .expected_output_obj (dataset 'answer'),
        #   .output_obj (workflow output = our triage JSON string)
        # -> parse JSON, compare severity, build EvalOutputItem(id, score, reasoning)
        return EvalOutput(average_score=avg, eval_output_items=items)
    yield EvaluatorInfo(config=config, evaluate_fn=evaluate, description="...")
```
Dataset = json list of `{id, question, answer}`; eval config = the workflow + an `eval:` block
referencing the evaluator by its `name`. Run `nat eval`.

What our run found (the real prize): severity accuracy = 0.70, and EVERY miss was the model
UNDER-rating severity (critical→high, high→medium). The failure *pattern* > the number: it
says promote low/medium segments toward autonomy, keep high/critical human-gated. Evals exist
to surface exactly this.

**One-liner:** *"I wrote a task-specific evaluator that scores the severity field that gates
autonomy; it found 70% accuracy with a systematic under-rating bias on severe cases — so the
data tells me which segments are safe to promote, rather than guessing."*

## Q33 — Running nat eval, eval-in-Phoenix, and the online metrics + calibration views

OFFLINE eval (regression):
- dataset json `[{id, question, answer}]`; custom `@register_evaluator` scores the
  autonomy-gating field. Put the `eval:` block in your EXISTING workflow config (one file:
  `nat run` uses the workflow, `nat eval` also reads the `eval:` block) — don't make a separate file.
- run: `nat eval --config_file <your_workflow.yml>` → table + `./.tmp/eval/<name>_output.json`.
- send to Phoenix: add a `general.telemetry.tracing` block to that same config
  (`resource_attributes: openinference.project.name: versos_eval`) and run with
  `PHOENIX_TRACING=1` → each golden-set case is a trace in the `versos_eval` project.

ONLINE eval + calibration (SQL views over the review log = real ground truth):
- `segment_metrics`: `accept_rate` (online accuracy, of reviewed) AND `precision_eligible`
  (accuracy on the confidence-≥-bar slice = what actually gates `auto`; bar = policy min_confidence).
- `promotion_readiness`: `reviewed_eligible>=20 AND accept_rate>=0.95 AND precision_eligible>=0.97
  -> eligible_for_auto`.
- `calibration_bins`: reliability diagram — per confidence bin, `avg_confidence` vs `accuracy`.
- `calibration_ece`: ECE = `sum(n*|avg_confidence-accuracy|)/sum(n)` (one number; lower = honester).

How they tie: a human raises a `triage_policy` row (promotion) only when OFFLINE accuracy +
ONLINE `promotion_readiness` clear the bar AND ECE is low. ECE just MEASURES miscalibration;
the fix (isotonic/Platt → `calibrated_confidence`) is a later script, then gate on the calibrated value.

**One-liner:** *"Offline is a custom nat-eval evaluator (traced to Phoenix); online is SQL views
over the review log — accept_rate, precision on the confident slice, a promotion-readiness flag,
and ECE for calibration — and a human promotes a segment only when offline accuracy + online
precision clear the bar with calibrated confidence."*

## Q34 — `nat eval` vs a Phoenix Experiment (can I "run the eval through Phoenix"?)

Two DIFFERENT tools on the SAME golden set — not interchangeable scorers:
- **`nat eval`** (CLI) — reads the `eval:` block in `triage_observed.yml`, scores via our
  `severity_accuracy` evaluator, prints a table + writes `./.tmp/eval/*_output.json`. Pass/fail
  → the **CI regression GATE**. Phoenix is NOT involved in scoring here; it only *shows the
  traces* those runs produce. (So don't say "I configured the eval in Phoenix.")
- **Phoenix Experiment** (`phoenix.client`: `create_dataset` + `run_experiment`) — runs the same
  golden set but results land as a **versioned run in the Phoenix UI**: side-by-side run
  comparison + per-example drill-down. The tool you open while **iterating** on a prompt.

Same exact-match logic, two surfaces. Script: `scripts/phoenix_experiment.py` (no new yml).
Needs Phoenix server + Postgres + NIM up. **Caveat:** it runs the REAL workflow, so it writes
10 rows into `triage_log` (tagged `[phx-exp] `) → purge with
`DELETE FROM triage_log WHERE complaint_text LIKE '[phx-exp]%';`.

API note: in arize-phoenix 17.x the experiments API is under `phoenix.client` (`from phoenix.client
import Client`, `from phoenix.client.experiments import run_experiment`) — NOT the old
`px.Client()`/`phoenix.experiments`. The `phoenix` top-level here is `arize-phoenix-otel`
(tracing only); the experiment API comes from the full `arize-phoenix` + `arize-phoenix-client`.

**One-liner:** *"`nat eval` is my CI gate; the Phoenix experiment is the visual comparison layer
I open while iterating — two surfaces on one golden set, not two scorers."*

## Q35 — How `nat eval` binds to a workflow; one workflow per config

**No explicit wiring.** `nat eval` always runs THE top-level `workflow:` in the same config file,
over the `eval.dataset`, then applies EVERY `eval.evaluators` entry to the outputs. The binding
is **positional, not named**: the evaluator never references `triage_ticket`; it just scores the
`output_obj` the run produced (`severity_accuracy` parses the JSON for `severity`). So an
evaluator is workflow-agnostic by design — it'd score any workflow emitting that shape.

**A config has exactly ONE `workflow:`** (singular key, no list). But unlimited `functions:`.
That's the function-vs-workflow split: functions = toolbox (many), workflow = entry point (one).

Run multiple capabilities:
- **Many tools, agent decides** → one config: `functions:` (triage, index_hygiene, …) + one
  `workflow: tool_calling_agent` with `tool_names: [...]`. Multi-capability from one entry point.
- **Run A vs B independently** → **separate config files**, each its own `workflow:` + `eval:`.
- **Several HTTP endpoints** → each via its own `nat serve`, OR the FastAPI backend calls each
  through `load_workflow` (what we do).

**Eval consequence:** to eval triage AND index-hygiene separately you need **two configs** — one
`nat eval` per `workflow:`. One config cannot eval two workflows. Many evaluators on one workflow
in a single run is fine.

**Build mapping:** triage = its own config; upcoming index-hygiene + pipeline-healer each get
their OWN config (own `nat eval`); only if we want a single "do-anything" agent do we wrap all
three as `functions:` under one `tool_calling_agent`.

**One-liner:** *"Many functions, one workflow per config; the evaluator binds positionally to that
one workflow's output. Multiple top-level workflows = multiple files, or wrap them in an agent."*

## Q36 — Two Postgres idioms I used to seed + promote

**1. Bulk-generate rows: `INSERT … SELECT … FROM generate_series`.**
```sql
INSERT INTO triage_log (complaint_text, category, severity, confidence, ..., decision, ...)
SELECT '[seed] med acct '||g, 'account_access','medium',0.92, ...,
       CASE WHEN g=1 THEN 'reject' ELSE 'approve' END, ...
FROM generate_series(1,40) g;
```
- `generate_series(1,40) g` = a one-column table of numbers 1..40 → the SELECT runs once PER number = 40 rows.
- `INSERT … SELECT` = insert whatever the SELECT yields (no real source table; the series drives it).
- `'...'||g` = string concat → unique text per row (also the `[seed]` purge tag).
- `CASE WHEN g=1 THEN 'reject' ELSE 'approve' END` = per-row if/else → plant exactly 1 reject in 40
  → accept_rate 39/40 = 0.975 (how you dial a segment to *just* clear the promotion bars).

**2. Upsert (promotion): `INSERT … ON CONFLICT(pk) DO UPDATE SET`.**
```sql
INSERT INTO triage_policy(severity,category,approved_mode,min_confidence,updated_by)
VALUES('medium','account_access','auto',0.85,'benny')
ON CONFLICT(severity,category)
DO UPDATE SET approved_mode='auto', min_confidence=0.85, updated_by='benny', updated_at=now();
```
- Insert-or-update in ONE atomic line. `ON CONFLICT(severity,category)` watches the PRIMARY KEY.
- No row yet → plain INSERT (new `auto` row). Row exists → `DO UPDATE SET` overwrites those columns.
- Why not plain `UPDATE`? UPDATE is a silent no-op when the row doesn't exist — and many segments
  start with NO policy row (default `suggest` in code), so upsert promotes them on the first try.
- Mirror idiom: schema seeding uses `ON CONFLICT … DO NOTHING` = "if it exists, leave it alone."

**One-liner:** *"`generate_series` + `CASE` = scripted realistic review data with a dialed accept-rate;
`ON CONFLICT … DO UPDATE` = idempotent promotion that works whether or not the segment was ever configured."*

## Q37 — Eval cadence + the promotion/monitor jobs + the "labels stop" problem + CSAT

**Cadence.** OFFLINE (golden set + `nat eval`) = robot, fast: per-push CI gate + nightly drift
canary. ONLINE (review log + views) = judge, slow: rows accrue passively, views are live SQL,
and two SCHEDULED jobs act on them.

**"Labels stop coming in" (clarified).** The ROW is always INSERTed (auto or not). What stops is
the LABEL column: `decision` is filled later BY A DEV. In `auto` mode no dev reviews → `decision`
stays NULL → `accept_rate` has nothing to average. You go blind to quality exactly where you
removed the human. Two fixes (they stack):
- **5% sampling** — route ~5% of auto'd tickets back to a human → fills `decision` for some auto
  rows → keeps `accept_rate` alive.
- **`customer_satisfied BOOLEAN` column** (+ `feedback_at`) — CSAT on the reply that went out. The
  label that SURVIVES auto mode (customer gives it, no dev needed). `segment_metrics` now also
  exposes `feedback` (count) + `satisfaction_rate` = `avg(customer_satisfied::int)`. For auto'd
  segments, satisfaction_rate is the primary health signal.

**Two jobs** (`nat_sandbox/severity_lab/jobs/`):
- `promotion_job.py` — WEEKLY. Reads `promotion_readiness`, lists segments `eligible_for_auto` &
  not already auto. Default = DRY-RUN (proposes + prints the UPDATE). `--apply` (human-invoked)
  upserts the policy row. Promotion is deliberate + human-gated.
- `monitor_job.py` — HOURLY. The brake. Over a recent window, demotes any `auto` segment whose
  dev `accept_rate` (from sampled reviews) OR `satisfaction_rate` falls below its floor (each
  guarded by a min sample size). Auto-applies — removing trust needs no human.
- Asymmetry on purpose: promote = human + weekly; demote = automatic + hourly + instant.

**Scheduling (Versos = Python + Postgres + AWS).** Best fit: **EventBridge Scheduler → ECS
Fargate task** running the SAME agent image (different command). `rate(1 week)` → promotion_job
(dry-run → Slack proposal → human `--apply`); `rate(1 hour)` → monitor_job (auto-demote). Dev box
= cron / Task Scheduler. Fargate over Lambda because the job needs full Python deps + DB access.

**Portability gotcha hit live:** Windows console is cp1252 → printing `→`/`✓` crashes with
UnicodeEncodeError. Use ASCII (`->`, `[OK]`) in job stdout.

**One-liner:** *"Rows always land; the dev label dries up under auto, so CSAT becomes the auto-mode
ground truth. A weekly human-gated promotion job grants trust; an hourly automatic monitor job
(on accept_rate OR satisfaction) yanks it — both EventBridge→Fargate in Versos' AWS stack."*

## Q38 — Four supporting concepts (view deps, EventBridge/Fargate, dry-run/--apply, CSAT)

**Dropping a dependent view.** `promotion_readiness` is `SELECT *, (...) FROM segment_metrics`.
`CREATE OR REPLACE VIEW` can only APPEND columns, and `SELECT *` is FROZEN at creation (Postgres
expands `*` to the exact column list then and stores it; never re-expands). So reshaping
`segment_metrics` is blocked while a dependent reads it → order: DROP child → rebuild parent →
recreate child (re-freezes `*` against the wider parent). Rule: to reshape a view others read,
drop dependents first.

**EventBridge Scheduler = cloud cron** (the *when*; fires on a schedule, runs nothing itself).
**Fargate = run a container with no server to manage** (the *run*; a "task" = one container run,
billed per second, then it dies). Combined: Scheduler fires hourly → starts a Fargate task running
the agent image with command `monitor_job.py` → it hits Postgres → exits. Fargate over Lambda
because the job needs the full Python image (asyncpg + package), not a zip.

**dry-run vs `--apply`.** `--apply` is a CLI flag the human passes. No flag (default) = DRY-RUN:
the job only PRINTS the segments it would promote + the exact UPDATE, changes nothing. With
`--apply`: it runs the upsert for real. "Where it proposes" = stdout now; in prod pipe that to
Slack/a ticket/a small UI a human reads, who then triggers the `--apply` run (or clicks Approve
calling the same upsert). The flag is the seam between "machine suggests" and "human commits."
Promotion needs it (granting power); demotion has no flag (removing power is instant).

**CSAT = Customer Satisfaction** — the 👍/👎 (or stars) a customer gives after the reply. Stored as
`customer_satisfied BOOLEAN`; `satisfaction_rate` = fraction TRUE per segment. It's the only quality
label that survives `auto` mode (no dev reviews there), so `monitor_job` watches it.

**One-liner:** *"Drop dependents before reshaping a `SELECT *` view; EventBridge=when + Fargate=run;
`--apply` is the human-commit flag on an otherwise harmless dry-run; CSAT is the survives-auto label."*

## Q39 — Deployment topology: ECS vs Fargate, Service vs Task, RDS, frontend

**Misconception fixed:** Fargate is NOT separate from ECS — it's a LAUNCH TYPE of ECS. ECS = the
orchestrator (run + keep containers alive); Fargate = the serverless compute mode (vs EC2 launch
type where you own the boxes). So it's not "backend in ECS, jobs in Fargate" — it's EVERYTHING in
ECS, all on Fargate. The real split is the ECS OBJECT TYPE:

| Component | Runs how | ECS object | Compute | Triggered by |
|---|---|---|---|---|
| Backend (FastAPI + NAT workflows) | always-on | ECS **Service** (keep N alive, behind ALB) | Fargate | always up |
| Jobs (promotion/monitor) | short, exits | ECS **Task** (run-task) | Fargate | EventBridge Scheduler |
| Postgres | always-on, stateful | **RDS** (NOT a container) | managed | — |
| Frontend (Next.js) | always-on | **not ECS** (Vercel/Amplify/S3+CloudFront) | — | — |

- **Service vs Task** = the real distinction: Service keeps copies alive forever (restart, load
  balance) for the backend; Task runs once and exits for the jobs. Both Fargate underneath.
- **Same image, different command:** backend = `uvicorn backend.main:app`; job = `python
  jobs/monitor_job.py`. One image to build/version for a small system (split only if deps diverge).
- **Postgres = RDS in prod** (compose Postgres is dev-only; prod points DATABASE_URL at RDS).
- **Next.js usually NOT ECS** — ships to Vercel/Amplify/S3+CloudFront, calls the backend API over
  HTTPS. Containerize into an ECS Service only if they want everything in ECS.

```
Next.js (Vercel/Amplify) --HTTPS--> ECS Service (Fargate): FastAPI+NAT --> RDS Postgres
EventBridge: rate(1 week)->ECS Task promotion_job ; rate(1 hour)->ECS Task monitor_job  (same image)
```

**One-liner:** *"ECS orchestrates, Fargate is its serverless engine, everything containerized runs on
ECS/Fargate; backend = always-on Service, jobs = one-shot Tasks fired by EventBridge, Postgres = RDS,
Next.js = Vercel/Amplify calling the API."*

## Q40 — Guardrails: layered defense-in-depth (and the input guardrail)

Guardrails aren't one NAT feature — they're LAYERS across in→think→act; if one fails the next
catches it (no single point of trust).

| # | Layer | Stage | Status |
|---|-------|-------|--------|
| 1 | Input validation | before the LLM | ✅ `_screen_input` (reject empty/short, truncate >4000, flag injection→force suggest) |
| 2 | Output validation | after the LLM | ✅ `Literal` severities + `field_validator` + None-guard |
| 3 | Action / autonomy cap | before acting | ✅ `_decide_from_policy` ceiling + confidence bar |
| 4 | Hard-held criticals | before acting | ✅ critical→suggest in code (defense in depth) |
| 5 | Approval gate | before acting | ✅ suggest/approved = human commits the act |
| 6 | Kill switch | global | ✅ `system_flags.kill_switch` checked in `_decide_from_policy` |
| 7 | Topical / safety rails | in + out | ✅ NeMo input rail + Presidio PII-mask, integrated into the agent |

The stack in detail:
1. **Input validation** (before LLM) — ✅ `_screen_input()`: REJECT empty/<3 chars (no LLM call),
   TRUNCATE >4000 chars, FLAG prompt-injection regex. Flagged tickets still triage but are FORCED
   to `suggest` (a manipulated ticket can never auto-act). Reject/flag logged for audit.
2. **Output validation** (after LLM) — ✅ `Literal` severities + `field_validator` + None-guard.
3. **Autonomy cap** — ✅ `_decide_from_policy` ceiling + confidence bar.
4. **Hard-held criticals** — ✅ critical→suggest in code regardless of policy.
5. **Approval gate** — ✅ suggest/approved = human commits the act.
6. **Kill switch** — 🔜 DB/config flag forcing everything to suggest, instantly.
7. **NeMo Guardrails** (optional) — NVIDIA's lib; Colang rules for input/topical/output content rails
   ("no off-topic", "block jailbreak phrases", "no PII out"). Name it as the productized option; our
   code-level checks are more transparent/demonstrable for the build.

**Injection design choice:** not a hard BLOCK (false positives nuke legit tickets) — a soft FLAG that
removes autonomy. The ticket still gets triaged + answered, it just can't act unsupervised. Layers
1 and 3 stack: even if the model is fooled into "critical", layer 4 already hard-holds critical.

**One-liner:** *"Guardrails are layered, not one feature: validate input, validate output, cap
autonomy, hard-hold criticals, gate on approval, global kill switch — each kills a different failure
mode. Injection is flagged (force suggest), not blocked, to avoid false-positive lockouts."*

## Q41 — The kill switch (guardrail layer 6)

`system_flags(name PK, enabled BOOL, updated_by, updated_at)`, seeded `kill_switch=false`. Checked
at the TOP of `_decide_from_policy` (the single chokepoint every autonomy decision passes through):
if `enabled` → return `('suggest', 'Global kill switch engaged…')`, overriding policy + critical +
everything. One `UPDATE system_flags SET enabled=true WHERE name='kill_switch'` disables ALL
autonomy instantly.

**Why DB, not env var/config:** env needs a redeploy/restart to change; a DB row flips LIVE during
an incident and is shared across all backend replicas + jobs (fleet-wide). Incident response wants
the live, shared switch.

**Why one chokepoint:** placed in `_decide_from_policy` so no segment/path can bypass it — can't
forget to add the check somewhere. **Tradeoff:** one extra tiny DB read per decision; cache with a
short TTL only if profiling demands (don't prematurely optimize).

Demoed live: OFF→auto, ON→suggest (everything), OFF→auto restored. Flip via Adminer/psql or a
`PUT /system/kill-switch` backend route wired to an ops button.

**One-liner:** *"A DB-backed flag checked at the one decision chokepoint — one UPDATE forces every
segment to suggest, live and fleet-wide, no redeploy. Env vars can't do live incident response."*

## Q42 — NeMo Guardrails (LLM-powered rails; guardrail layer 7)

Separate NVIDIA library (`nemoguardrails`, pip; NOT part of NAT). You point it at a CONFIG FOLDER
and it wraps your LLM with "rails". Two files:
- `config.yml` — the model (`engine: nvidia_ai_endpoints`, our NIM) + which rails are ON
  (`rails: input: flows: [self check input]`).
- `prompts.yml` — the prompt the built-in `self_check_input` task uses; model answers Yes/No,
  "Yes" => block (main LLM never called, bot refuses).
Five rail types (where a rail sits): INPUT (before LLM), OUTPUT (after), DIALOG (mid-convo),
RETRIEVAL (RAG chunks), EXECUTION (around tool calls). We built an INPUT rail.
Run: `LLMRails(RailsConfig.from_path("guardrails/")).generate(messages=[...])`.

**Demoed live:** genuine complaint PASSED; "ignore all previous instructions…" BLOCKED; "best pizza
topping?" BLOCKED. The off-topic one is the punchline — regex `_screen_input` would let it through;
the LLM rail screens INTENT, not known phrases.

**Regex vs NeMo (the tradeoff):** regex = instant/free/deterministic but brittle (only listed
patterns). LLM rail = catches novel/rephrased/off-topic intent but costs an extra LLM call + latency
and can itself err. **Best practice = both, layered:** cheap regex first, LLM rail second.

**One-liner:** *"NeMo Guardrails wraps the model with config-driven rails; the LLM input rail catches
intent (off-topic, novel jailbreaks) the regex can't — so layer cheap regex first, LLM rail second."*

## Q43 — Rails `flows` options, PII masking, and ATTACHING rails to the real agent

**The `rails:` block** switches on checks per STAGE; each stage takes a `flows:` list:
- `input:` (user msg, before LLM): `self check input`, `jailbreak detection heuristics`,
  `mask sensitive data on input`.
- `output:` (bot answer, before it leaves): `self check output`, `self check facts` (anti-
  hallucination grounding), `mask sensitive data on output`.
- `retrieval:` (RAG chunks): `check retrieval relevance`.
- `dialog:` topical flows — the one case you WRITE Colang (`.co`): canonical user intents + bot
  flows ("off-topic -> refuse"). The `self check *` flows are the no-Colang shortcut.

**Preventing PII leaks = an OUTPUT rail** (input validation can't — the leak is in the answer). Two
ways: (a) `self check output` — LLM judges its own answer for PII (cheap, not airtight); (b) Presidio
`mask sensitive data on output` — NER-based deterministic redaction (`<EMAIL_ADDRESS>` etc.), needs
`presidio-analyzer presidio-anonymizer` + a spaCy model. Best = both layered.

**We INTEGRATED it into the real agent (not just the demo).** Terminology: you "attach guardrails to
the AGENT / wrap the LLM with rails"; the backend is just the host. Right attach point = the NAT TOOL
(the chokepoint every caller hits — backend, CLI, eval), same logic as the kill switch in
`_decide_from_policy`. `guardrails_runtime.py` builds the rails/Presidio ONCE (lru_cache) and the tool
calls `is_input_blocked()` (input rail, env-gated `GUARDRAILS_INPUT_RAIL`) + `mask_pii()` (Presidio,
always on) on `suggested_customer_reply` before logging/returning. Both degrade gracefully (missing
key/model → fall back to regex-only, never crash). NOTE: the previous standalone `guardrails/demo.py`
was a PROTOTYPE; this is the production wiring.

**Why input rail is env-gated but masking isn't:** the input rail costs an extra LLM call (skip it in
bulk `nat eval`); Presidio masking is local + deterministic + cheap, so it's always on.

**One-liner:** *"Rails attach at stages (input/output/retrieval/dialog) via `flows`; PII is an OUTPUT
rail (Presidio mask = deterministic); attach to the agent at the tool chokepoint, build-once, and
degrade gracefully — env-gate the expensive LLM rail, keep deterministic masking always on."*

## Q44 — NeMo flow keywords, Presidio/NER, and the rails `models:` block

**1. `self check input` / `self check output` are LIBRARY KEYWORDS, not my names.** They map to
pre-written flows inside `nemoguardrails`; only the exact spelling works (`check my input` wouldn't
resolve). What's MINE is the PROMPT behind the flow (the `self_check_input` block in prompts.yml).
Naming convention: flow uses SPACES (`self check input`), its prompt task uses UNDERSCORES
(`self_check_input`) — both fixed keywords; the library maps between them. `dialog` flows in `.co`
are the ones you fully author (Colang).

**2. Presidio + NER.** NER = Named Entity Recognition = label spans that are "named things"
(PERSON, LOCATION, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD…). Two ways, Presidio uses both:
model-based (spaCy `en_core_web_sm` net → fuzzy entities like PERSON it's never seen) + rule-based
(regex/checksum → EMAIL/PHONE/CREDIT_CARD, even Luhn-validates cards). Presidio = Microsoft PII
toolkit on top of NER: `AnalyzerEngine` (NER finds spans → findings) → `AnonymizerEngine` (rewrites
spans, default `<ENTITY_TYPE>`). spaCy `sm`=small/fast(12MB) vs `lg`=accurate(400MB); without a
spaCy model you keep regex entities but lose PERSON/LOCATION. Beats "ask the LLM to remove PII"
because it's DETERMINISTIC + AUDITABLE + doesn't depend on the model's goodwill (compliance control).

**3. The `models:` block in rails config.yml** = which LLM the RAILS THEMSELVES use to answer their
Yes/No checks (`self check input` literally asks an LLM). Fields: `type` = role (`main` = primary;
can declare multiple, e.g. a cheap model just for guard checks), `engine` = provider/integration
(`nvidia_ai_endpoints` = NIM via langchain-nvidia-ai-endpoints; others: openai/azure/nim/hf),
`model` = the specific model name. SEPARATE from NAT's `llms:` block (NeMo's own config world) — can
deliberately point at a smaller/cheaper model since a Yes/No guard doesn't need your best model.

**One-liner:** *"Flow names are library keywords (you own the prompt); Presidio = Analyzer(NER finds
PII)+Anonymizer(rewrites), deterministic > trusting the LLM; rails `models:` is the LLM the guards
use to think — role/engine/model, separate from NAT, and can be a cheaper model."*

## Q45 — Env var vs DB flag: why the guardrail toggles live in system_flags

**Env vars are snapshotted at process start.** `os.environ.get()` is re-read each call, but the
process's environment is fixed at launch — changing the OS env afterward doesn't reach a RUNNING
process. So env-var flags = set per environment at deploy, **restart to change.** That's fine for
deploy-time POSTURE and great for CLI/eval (`FLAG=1 nat eval ...`, per-invocation). It is NOT fine
for anything you must change WHILE the app runs.

**So pick the mechanism by change-urgency:**
- live/operational (flip while running, fleet-wide) → **DB flag** (`system_flags`, read per-request).
- per-environment posture / CLI → **env var** (restart ok).

We moved all three runtime guardrail toggles to `system_flags`, read via `_flag_enabled(pool, name)`:
`kill_switch` (disable all autonomy), `input_rail` (run NeMo LLM input rail), `mask_input` (Presidio-
mask the complaint). Demoed live: `UPDATE system_flags SET enabled=true WHERE name='mask_input'` →
next triage stored `Refund <PERSON> at <EMAIL_ADDRESS>…`, no restart. Trade-off: one tiny extra DB
read per decision (cache with short TTL only if profiling demands).

**One-liner:** *"Env vars freeze at process start (restart to change) — right for deploy posture/CLI;
DB flags read per-request flip live & fleet-wide — right for incident/runtime toggles. Choose by how
urgently the value changes."*

## Q46 — `lru_cache`, lazy imports, and the lazy-singleton pattern (from guardrails_runtime.py)

**`lru_cache` = run the function body ONCE, then return the stored result.** It keeps a hidden dict
`{args → result}`; on each call, seen-these-args? yes → return cached, skip body; no → run body, store,
return. For a NO-ARG function (`_input_rails()`, `_input_only_options()`) there's one possible key, so
the body runs at most once ever; `maxsize=1` = remember one result. Caveats: caches by ARG VALUES (must
be hashable); don't use it where the result should change over time (you'd serve a stale value).

**An `import` is CODE THAT RUNS, not a passive declaration — and it runs ONCE.** First execution of
`import X` finds X, runs its `__init__.py`, builds its objects (heavy for nemoguardrails/presidio),
then caches the module in `sys.modules`; later `import X` lines just grab the cached module (near-instant).
So the cost is paid at the FIRST execution of that import line. The question is only WHEN that first
execution happens:
- **Top-of-file import** → runs at MODULE-LOAD time, unconditionally — even on runs that never use the
  feature. Importing `guardrails_runtime` would then drag in nemoguardrails on EVERY `nat eval`/start.
- **Inside-function import** → runs only when that function is first CALLED. If the rail is never used
  (flag off), nemoguardrails is never imported at all. (Not "runs every call" — still once, then cached.)

**Lazy-singleton pattern** = inside-function import + `@lru_cache`. First call: import + construct + cache
the heavy object (the loaded `LLMRails`, the Presidio engines). Later calls: hand back the cached object,
no re-import, no rebuild. That's why `_input_rails()`/`_presidio()` are written as cached no-arg funcs
instead of module-level globals — cheap to import the module, pay the heavy cost only if/when used, and
only once. (`_input_only_options()` follows the same pattern for `GenerationOptions(rails=["input"])`,
which tells NeMo to run ONLY input rails — skip the main-LLM generation. Without it, default = full
pipeline = wasted LLM call AND breaks the echo-vs-refusal block detection.)

**One-liner:** *"`lru_cache` = build once, reuse forever; imports are code that runs once at first
execution (top-of-file = eager/unconditional, inside-function = lazy/on-demand); combine them =
lazy-singleton: pay heavy import+construct cost only when first used, then cache."*

## Lessons learned — running notes

- **Imports are eager unless you hide them.** Heavy optional deps (nemoguardrails, presidio) go in
  inside-function imports + `lru_cache` so unused = unpaid. Keeps `nat eval`/startup fast.
- **Guardrails are LAYERED, not one feature** (the 7-layer table, Q40). Each layer kills a different
  failure mode; injection is FLAGGED (force suggest), not hard-blocked (false positives).
- **Config mechanism by change-urgency** (Q45): live/incident → DB flag (read per request); deploy
  posture/CLI → env var (frozen at process start). Kill switch & guardrail toggles → `system_flags`.
- **Output PII masking is hard-wired & always-on** (no flag) — the reply is the real leak surface;
  input masking is the optional `mask_input` toggle (data-minimization). Presidio (deterministic) >
  asking the LLM to self-redact.
- **Everything degrades gracefully** — missing key/model → guardrail falls back (regex-only / unmasked),
  never crashes the triage path.
- **OneDrive silently drops files** (triage_direct.yml vanished twice) — verify files on disk before
  declaring done; recreate from the canonical version.
- **Windows console is cp1252** — ASCII only in job/script stdout (no `→`/`✓`), or it crashes.

## Q47 — JD gaps to speak to (things the JD names that we haven't built)

If asked, answer crisply — know the shape even if not built:
- **Replays** — re-run a LOGGED decision against a new prompt/model and diff the output. "I'd add it
  by reading a `triage_log` row, re-invoking the tool on its `complaint_text`, and comparing to the
  stored decision — a regression check on real historical traffic, complementary to the golden set."
- **Sandboxed execution** — for agents that take real actions (the pipeline-healer running a fix),
  run the action in an isolated env (container/limited role) so a bad action can't touch prod. "Our
  blast-radius control today is policy-level (hard-hold + approval); sandboxing is the EXECUTION-level
  control I'd add when an agent actually mutates infra — dry-run first, capability-scoped creds, diff
  before apply."
- **Retrieval / RAG** — ground the agent in docs (runbooks, schema, past incidents) via a vector
  store + retrieval rail. "Triage doesn't need it; a pipeline-healer would — retrieve the runbook for
  the failing job before proposing a fix. NeMo Guardrails even has a retrieval rail slot for it."
- **Cost watcher** — Phoenix already captures tokens/cost per call; a cost-watcher agent = the same
  spine over spend metrics (segment = model/endpoint), auto-alert/throttle when a budget bar trips.

**One-liner:** *"The trust-layer + autonomy-graduation core is built and deep; the named gaps
(replays, sandboxed execution, retrieval, cost watcher) are each the SAME spine applied to a new
surface or an execution-level control I can describe precisely."*

## Q48 — JD ↔ build alignment (the one-screen map)

The triage agent is a complete vertical slice of the JD's thesis: "graduate agents suggest→approved→
autonomous as evidence accumulates, with a trust layer that makes autonomy justifiable."
- platform ✅ (NAT + layered backend + deploy topology) · graduation ✅✅ (policy + promotion/monitor
  jobs) · audit/trust ✅ (log + Phoenix + offline/online evals + kill switch + blast-radius) ·
  justifiable autonomy ✅✅ (segment_metrics + calibration/ECE).
- Breadth gap: only triage built; JD wants a FLEET — index-hygiene + pipeline-healer are the next two
  (and they're literally on the JD's day-one list). Same spine, new domain.
- Their day-one is INFRA, not support → expect an infra-flavored sim; map ticket→finding/job/query.

**One-liner:** *"I built the deep vertical (one agent, full trust layer + autonomy graduation); the
JD wants that pattern spread across an infra fleet — which is exactly the reusable spine, re-skinned."*

## Q50 — The index-hygiene agent (second agent, same spine, infra-flavored)

Proof the spine generalizes: a SECOND agent built by re-skinning triage (ticket→finding,
severity→risk, remediation→DDL). Hits the JD's literal day-one job ("missing indexes, slow queries").

Pipeline (deterministic — NO LLM; detection is SQL, "pick the right layer"):
`scan → risk → precision guard → autonomy gate → human approve → apply → efficacy`.
- **scan**: catalog SQL finds unused / missing / duplicate / invalid indexes (pg_stat_user_indexes,
  pg_stat_user_tables, pg_index…).
- **precision guard**: `index_seen` observation window — a newborn index legitimately has 0 scans, so
  flagging it is a false positive. Demoed: precision 1.0 (window on) vs 0.875 (window off).
- **autonomy gate**: `index_policy` (finding_type×risk) + kill switch, code-enforced. **DROP is
  HARD-HELD** — can never reach `auto` even if a policy row says so (CREATE is reversible → may auto).
- **apply**: runs DDL `CONCURRENTLY` for approved/auto findings, records outcome.
- **efficacy** (`index_action_metrics`): `bytes_reclaimed` + **`re_create_rate`** (dropped an index
  then had to rebuild it = the OOPS signal). `re_create_rate ≈ 0` over many drops is the EVIDENCE
  that justifies promoting `unused` suggest→approved→auto — ground truth measured from the DB itself,
  not a human's opinion. Strongest possible "justifiable autonomy" story.
- **eval**: offline = labeled precision/recall regression harness (`jobs/index_hygiene_eval.py`);
  online = the efficacy view. Registered as a NAT workflow (`configs/index_hygiene.yml`).

Files: `index_hygiene.py`, `sql/index_hygiene.sql`, `configs/index_hygiene.yml`,
`jobs/index_hygiene_eval.py`.

**One-liner:** *"Index-hygiene is triage's spine re-skinned onto Postgres catalogs: deterministic
scan, observation-window precision guard, policy gate with DROP hard-held, apply CONCURRENTLY, and a
re-create-rate that makes auto-drop autonomy justifiable from measured outcomes."*

## Q49 — Precision, recall, accuracy, efficacy (with a worked index example)

Build a **confusion matrix** first: agent flags some indexes as "unused/drop"; truth knows which are
really unused. Example — 10 indexes, truth = 4 unused / 6 fine; agent flags 5:

| | Truth: unused (4) | Truth: fine (6) |
|---|---|---|
| Agent flagged (5) | **TP = 3** (caught) | **FP = 2** (false alarm) |
| Agent left alone (5) | **FN = 1** (missed) | **TN = 4** (correct) |

```text
Precision = TP / (TP + FP) = 3 / (3+2) = 0.60   "of what it flagged, how much was right" (FP = dropped a needed index)
Recall    = TP / (TP + FN) = 3 / (3+1) = 0.75   "of all real problems, how many caught"  (FN = slow query lives on)
Accuracy  = (TP + TN) / all = (3+4)/10 = 0.70   "of all judgments, how many correct"
```

**Why accuracy lies:** "keep everything" scores 6/10 = 0.60 accuracy while catching ZERO problems —
because most indexes are fine (class imbalance). So lean on precision + recall, not accuracy.

**The tension (tune by which mistake hurts more):**
- DROP an index → a false positive drops a NEEDED index = disaster → optimize **precision**.
- MISSING index → a false negative leaves a slow query in prod → optimize **recall**.
You can't max both: flag more aggressively → recall ↑, precision ↓.

**Efficacy** = different kind — it judges the ACTION's real effect, measured AFTER acting (not a
classification metric):
```text
created index → query 800ms → 40ms          = high efficacy (worked)
dropped index → 48 kB reclaimed, no slowdown = good
dropped index → monthly report slowed → re-created = efficacy FAILURE (the "re-create rate" gate)
```
Precision/recall = "did it think correctly?" (judged on a labeled list). Efficacy = "did the fix
actually help?" (judged by re-measuring the DB). Same split as offline (judge decision) vs online
(measure outcome) evals.

**One-liner:** *"Precision = right-when-it-flagged; recall = caught-of-all-real; accuracy misleads
under class imbalance; efficacy = did the action measurably help. Tune precision for DROP, recall for
MISSING."*
