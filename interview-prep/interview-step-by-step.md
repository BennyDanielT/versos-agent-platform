# Interview Day — Step-by-Step Runbook

> **Living document.** Kept in sync with `interview-prompts.md` every time we add or
> change something. This file = what YOU run/understand. That file = what you TYPE to
> Claude Code.

Follow this top to bottom on the day. Every step has: **what to do**, the **command**,
**why** it matters, and **what success looks like**. Don't rush — each step builds on
the last.

Legend: ✅ = we've validated this hands-on already · 🔜 = we'll build/practice it before the day.

> Golden rule for the day: **orient before you build.** The machine, the NAT version,
> and the simulation will have surprises. Spend the first 10 minutes looking, not typing.

---

## DAY-OF STRATEGY (read this first — domain-agnostic)

The sim probably ISN'T customer-support triage. The JD's day-one jobs are INFRA agents:
"missing indexes, slow queries, broken jobs, stale data, customer-visible regressions." You built
the regression one (triage). **The spine below re-skins onto ANY of them — that's the whole point.**

### The reusable spine (stamp this onto whatever the sim is)
1. **Tool with structured output** — one NAT function; `with_structured_output(PydanticModel)`;
   `Literal` enums for the safety-critical field + `field_validator` to normalize; guard `None`.
2. **Policy-as-data autonomy** — a DB table of human-granted ceilings per segment (NOT in the LLM).
   Code reads it, enforces it. The agent never grants itself autonomy.
3. **suggest / approved / auto** — the three modes; confidence bar gates reaching the ceiling;
   high-impact actions hard-held in code regardless (blast-radius control).
4. **Log every decision** — one row per action (input, output, mode, reason, confidence). This row
   is your audit trail AND your eval dataset AND your shadow-mode signal.
5. **Evals, two layers** — OFFLINE (golden set + `nat eval` custom evaluator = CI regression gate);
   ONLINE (SQL views over the review log + outcome signal = ground truth that drives promotion).
6. **Layered guardrails** — input validate, output validate, autonomy cap, hard-hold criticals,
   approval gate, kill switch (DB flag). Each kills a different failure mode.
7. **Kill switch + graceful degradation** — one DB flag forces everything to suggest; every external
   dep (LLM, rail, masker) degrades to a safe default instead of crashing.

Whatever the sim's domain: the "ticket" becomes a finding/job/query; "severity" becomes its
risk/impact; "remediation" becomes the fix the agent proposes; everything else is identical.

### First 30 minutes — orient before you build
1. **Read the sim's data** — which tables/jobs exist? Where's the rot (missing indexes, stale rows,
   failed jobs)? That rot IS your agent's job. Pick the most bounded, highest-leverage one.
2. **Confirm the stack on the box** — `nat --version`, `nat info components`, available NIM models,
   is Postgres up, is Phoenix/telemetry preinstalled. (See "Open questions" in TODO.md.)
3. **Name the autonomy seam** — what action would the agent take, and what's the worst case if it's
   wrong? That defines what's hard-held vs auto-able. Say it out loud early.
4. **Build the thinnest end-to-end slice first** — tool → structured output → log a decision → one
   policy lookup. Get ONE real run green before adding evals/guardrails/breadth.

### JD-alignment cheat-sheet (speak THEIR language in the presentation)
| They say | You point at |
|---|---|
| "dark-factory operations" | the suggest→approved→auto graduation + monitor auto-demote |
| "graduate as evidence accumulates" | `promotion_readiness` (volume + accept-rate + precision bars) |
| "make autonomy justifiable to others" | segment_metrics + calibration/ECE + the decision log |
| "blast-radius controls" | critical hard-held in code + autonomy caps + kill switch |
| "audit and trust layer" | triage_log + Phoenix traces + offline/online evals + kill switch |
| "well-bounded jobs, suggest-only first" | policy seeds everything to `suggest`; evidence earns `auto` |
| "force-multiply the team" | humans steer policy (promote rows), agent works tickets |

---

## TARGET ARCHITECTURE (decide this before coding)

The DarkOps layer is TWO things — don't fuse them:

```
   ┌─ Human ops copilot = ONE tool_calling_agent ──┐   (on-demand, human-facing surface)
   │     tools: triage, index_check, cost_report…  │
   └───────────────────────┬───────────────────────┘
                           │ (calls the SAME functions, on demand)
   ┌───────────────┬───────┴────────┬────────────────┐
   │ triage WF     │ index-hygiene  │ pipeline-healer │  = INDEPENDENT workflows
   │ (on ticket)   │ WF (nightly)   │ WF (on failure) │    (event/cron-triggered, autonomous)
   └───────────────┴────────────────┴────────────────┘
                           │
            Postgres + NIM  /  tracing (observe)  /  nat eval (prove)

Next.js UI ─HTTP→ nat serve (FastAPI) ─→ any of the above
```

**The key decision — hybrid, not one mega-agent:**
- **Autonomous backbone = multiple INDEPENDENT workflows**, each triggered by its own
  event/schedule and running DETERMINISTICALLY (no LLM deciding what to do). Why: each is
  separately observable, evaluable, guarded, and **promotable to autonomy on its own
  evidence** — and triggers call the exact workflow with no LLM-routing tax or extra
  failure point. The factory runs because cron/events fire workflows, not because an agent watches.
- **Human control surface = ONE `tool_calling_agent`** ("ops copilot") whose tools are thin
  wrappers that invoke those same functions on demand ("triage this now", "show cost").
  It's the steering wheel, not the engine. Prefer `tool_calling_agent` (function-calling)
  over `react_agent` (text-parsing).
- **No logic duplication:** a NAT function can be BOTH a standalone workflow AND a tool in
  the agent.
- Don't put the agent on top of the autonomous jobs — that adds an LLM decision (latency,
  cost, bigger blast radius) to work that should be deterministic, and it breaks
  per-capability autonomy promotion.

**Why this matches Versos:** "humans steering policy rather than tending tickets" — the
workflows do the work autonomously; the copilot is how humans steer/intervene.

**Evals (the autonomy gate) — two layers:**
- **Offline** = golden set + `nat eval` with a TASK-SPECIFIC custom evaluator scoring the field
  that gates autonomy (severity/category accuracy). Catches regressions. "Didn't break."
- **Online** = the review log → `accept_rate` per segment (`segment_metrics`). Real ground
  truth. "Good enough to promote."
- Both feed the promotion decision: a human raises a `triage_policy` row only when offline
  accuracy AND online accept-rate (+ volume + calibrated confidence) clear the bar.

- **`nat serve`** exposes a workflow as a FastAPI REST endpoint — the integration seam.
- **Next.js** calls that endpoint (Next API route / server action → `fetch` the serve URL).

Demo strategy: **depth over breadth.** Ship 2 solid workflows (triage + one more) fully
wired with policy + logging + a trace + a small eval. Mention the `tool_calling_agent`
+ Next.js as the capstone; build the UI only if time remains (`nat serve` alone proves it).

---

## PHASE 0 — Orient (first ~10 min on their machine) ✅

**Step 0.1 — See what you're working with.**
```bash
python --version          # need 3.11 / 3.12 / 3.13 for NAT
nat --version             # is NAT already installed? which version?
```
*Why:* NAT moves fast; the version dictates exact command names. Don't assume.
*Success:* you know the Python + NAT versions (or that NAT isn't installed yet).

**Step 0.2 — Read their simulation.** Find its README / entry files. Understand:
what it simulates, how you interact with it (DB? API? function calls?), what a
"good outcome" looks like.
*Why:* your agents act ON their simulation. You can't design tools until you know
its surface.
*Success:* you can say in one sentence what the sim does and how you'll touch it.

**Step 0.3 — Find the database.** Is there a Postgres already? Connection string in
env? Existing tables?
```bash
echo $DATABASE_URL
psql "$DATABASE_URL" -c "\dt"   # list tables, if psql is available
```
*Why:* your agents read/write business state here. Know the schema before coding.
*Success:* you can list the tables and know where state lives.

---

## PHASE 1 — Environment setup ✅

**Step 1.1 — Create an isolated Python environment.**
```bash
python -m venv .venv
# activate it:  (Windows) .venv\Scripts\activate   (Linux/Mac) source .venv/bin/activate
```
*Why:* keeps your installs from colliding with the system / their sim.
*Success:* your prompt shows the venv is active.

**Step 1.2 — Install NeMo Agent Toolkit.**
```bash
pip install "nvidia-nat[langchain]"
```
*Why:* `nvidia-nat` is the core; the `[langchain]` extra adds the LangChain/LangGraph
bridge so you can use LangChain LLMs and tools inside NAT.
*Note:* on a locked-down network add `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.
*Success:* `nat --version` prints a version.

**Step 1.3 — Set your model key.**
```bash
export NVIDIA_API_KEY=nvapi-...      # (Windows PS:  $env:NVIDIA_API_KEY="nvapi-...")
```
*Why:* NAT's `nim` LLM provider calls NVIDIA-hosted models; no key = no LLM calls.
*Success:* `echo $NVIDIA_API_KEY` shows it set.

**Step 1.4 — (If you need your own Postgres) start one with Docker.** The full DEV compose
(Postgres + Adminer). The schema mount auto-loads tables ONLY on a fresh (empty) data dir.
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment: { POSTGRES_USER: versos, POSTGRES_PASSWORD: versos, POSTGRES_DB: versos }
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./nat_sandbox/severity_lab/sql/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U versos -d versos"]
      interval: 5s
      timeout: 3s
      retries: 10
  adminer:                      # clickable DB browser (Postgres has no built-in GUI)
    image: adminer:4
    ports: ["8081:8080"]
    depends_on: [postgres]
volumes:
  pgdata:
```
```bash
docker compose up -d            # starts postgres + adminer
docker compose ps               # postgres should show "healthy"
```
*Why:* a real relational store for business records (tickets, findings, jobs…).
*Success:* `docker compose ps` shows postgres healthy.

**Step 1.4b — (optional) Add Adminer for a clickable DB browser.** Postgres has NO built-in
GUI — `psql` is the only built-in. Add a 6-line Adminer service so you can eyeball tables/views
in a browser (great for demoing `triage_log` + `segment_metrics` live in the presentation):
```yaml
  adminer:
    image: adminer:4
    ports: ["8081:8080"]
    depends_on: [postgres]
```
```bash
docker compose up -d adminer
```
Open http://localhost:8081 → System **PostgreSQL**, Server **postgres** (the SERVICE name, NOT
localhost — Adminer reaches Postgres over the compose network), User/Pass/DB **versos**.
> ⚠️ **Common mistake:** typing `localhost` (or `localhost:5432`) as the Server → "connection
> refused". Inside the Adminer container `localhost` is Adminer itself. Use **`postgres`**.

---

## PHASE 2 — Build a real tool for THEIR simulation ✅

This is the core skill, and it's a **repeatable recipe**: every capability your agent
needs becomes one NAT "function" (a tool). A function = **a config class** (its
settings) + **a registered async function** (its logic) + a **YAML reference** to it.

**Step 2.0 — Name the real requirement first.** From Phase 0, pick ONE concrete task
the agent must do on their simulation (e.g. "read the failing job and decide a fix",
"flag stale records", "draft a remediation"). Write its inputs and output in one
sentence. You build tools to satisfy real requirements — don't invent generic ones.

**Step 2.1 — Scaffold a package to hold your tools.**
```bash
nat workflow create <pkg_name>
```
*Why:* generates the installable package (config class + decorator + `register.py` +
`pyproject.toml` entry point + a sample config) so you skip boilerplate. One package
can hold several tools — add more functions as files and import them in `register.py`.
*Windows caveat:* fails on a symlink step (WinError 1314) unless Developer Mode is on —
BUT it writes all real files first AND skips the auto-install, so you'll need Step 2.3
manually. On Linux it just works and auto-installs.
*Success:* a `<pkg_name>/` folder with `src/<pkg_name>/{<name>.py, register.py, configs/}`.

**Step 2.2 — Write the config class for your real tool.** Open the generated `.py`
and design the settings your tool needs:
```python
class <Thing>Config(FunctionBaseConfig, name="<tool_id>"):   # name= is the YAML _type
    llm_name: str = Field(description="...")                  # REQUIRED: no default
    threshold: float = Field(default=0.6, description="...")  # OPTIONAL: has a default
```
*Design rule:* **no default = "caller must supply this"** (e.g. which LLM, which table);
**default = "sensible value, override if you want."** Pydantic validates the YAML against
these types at startup, so bad config fails fast with a clear error.
*Remember:* `name="<tool_id>"` (the tool's `_type`) is independent of the package name.

**Step 2.3 — Write the function body.** Two scopes, and *when each runs* is the whole
mental model:
```python
@register_function(config_type=<Thing>Config,
                   framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def <thing>(config, builder):
    # SETUP — runs ONCE. Acquire dependencies here:
    #   llm  = await builder.get_llm(config.llm_name, wrapper_type="langchain")
    #   pool = await open_pg_pool(...)            # see Phase 4
    async def _run(<typed args from the requirement>) -> <typed output>:
        # THE WORK — runs EVERY call. Do the real task against their sim here.
        ...
    yield FunctionInfo.from_fn(_run, description="<what the agent reads to decide to call this>")
    # teardown after yield (close pools, etc.)
```
*Read it as:* outer = setup (once); inner = the work (per call); `description` = the
tool's spec the agent sees — **write it like a prompt**, precisely.

**Step 2.4 — Install the package so NAT can discover the tool.**
```bash
pip install -e <pkg_name>
nat info components -t function -q <tool_id>     # filter to YOUR tool by name
```
*Why:* NAT discovers components from *installed* packages via the `nat.components`
entry point in `pyproject.toml`. `-e` (editable) = your code edits take effect live.
*Note:* command is `nat info components` (NOT `list-components`); always filter with
`-q` or you'll scroll past dozens of built-ins.
*Success:* `<tool_id>` appears.

**Step 2.5 — Smoke-test the wiring with NO LLM first.** Before adding model complexity,
prove registration + config + run loop by making the tool itself the workflow:
```yaml
# configs/smoke.yml
functions: {}
workflow:
  _type: <tool_id>
  llm_name: <anything>     # required field must be present even if unused yet
```
```bash
nat run --config_file configs/smoke.yml --input "<a realistic input from their sim>"
```
*Why:* isolate variables — if this fails, it's wiring, not the model. Stub the inner
function to return a constant for this check, then make it real.
*Success:* `Workflow Result: <your value>`.
*Windows caveat:* prefix commands with `PYTHONIOENCODING=utf-8` if you see UnicodeEncodeError.

**Repeat 2.2–2.5 for each capability the agent needs.** That's the loop.

---

## PHASE 3 — Make the tool call a real LLM (NIM) ✅  *(needs NVIDIA_API_KEY)*

**Step 3.0 — Get the key into the environment.** NAT reads `NVIDIA_API_KEY` from the
shell, NOT from `.env` automatically. Two ways:
- Quick: `export NVIDIA_API_KEY=nvapi-...` (Git Bash) / `$env:NVIDIA_API_KEY="nvapi-..."` (PS).
- Permanent in code: put `from dotenv import load_dotenv; load_dotenv()` at the **top
  of `register.py`** — it loads `.env` before NAT builds the LLM, so no export needed.
*Verify:* run with the key unset and confirm it still works.

**Step 3.1 — Declare the LLM in YAML.**
```yaml
llms:
  nim_llm:
    _type: nim
    model_name: meta/llama-3.1-8b-instruct   # verified working; small + fast
    temperature: 0.0
```

**Step 3.2 — Use it inside your function (setup once, call per request).**
```python
# SETUP (runs once):
llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
# INNER (per call):
resp = await llm.ainvoke(prompt)     # async, non-blocking model call
answer = resp.content.strip().lower()
return answer if answer in ALLOWED else config.default_severity   # ← output guard
```
*Why:* `builder.get_llm` is your **provider seam** — the function names no vendor; the
YAML decides the model. `ainvoke` is the async (non-blocking) call. The **output guard**
(validate against an allow-list, else fall back) is a tiny but real guardrail.
*Success:* different inputs yield different, sensible answers (not the fallback).

**Step 3.2b — For structured output, prefer `with_structured_output` + Pydantic.**
For anything beyond one value, define a Pydantic schema and bind it:
```python
structured_llm = llm.with_structured_output(MyResult)   # provider enforces the shape
result = await structured_llm.ainvoke(prompt)           # returns a typed object
```
Gotchas (both real): it enforces the **shape, not the values** — use `Literal[...]` for
enum fields and a `field_validator(mode="before")` to normalize case, and keep a
try/except fallback. If it raises `CERTIFICATE_VERIFY_FAILED` on a corporate network,
add `import truststore; truststore.inject_into_ssl()` at the top of `register.py`.
*Principle:* strictness proportional to risk — strict `Literal` on safety-critical fields,
lenient+map-to-default on metadata.

**Step 3.3 — Promote to an agent orchestrator (the human copilot).** ✅ verified
```yaml
llms:
  agent_llm: { _type: nim, model_name: meta/llama-3.1-8b-instruct }   # needs function-calling
  triage_llm: { _type: nim, model_name: meta/llama-3.1-8b-instruct }  # tool needs reliable structured output
functions:
  triage_ticket: { _type: triage_ticket, llm_name: triage_llm }
workflow:
  _type: tool_calling_agent     # picks tools via function-calling (prefer over react_agent)
  llm_name: agent_llm
  tool_names: [triage_ticket, review_ticket]
```
*Why:* the agent **decides which tool to call** and extracts its args; then summarizes the
result for the human. The agent's reasoning model and a tool's model can DIFFER.
*Gotchas (all real):* (1) NAT 1.8 agents need **`langgraph>=1.2.5`** (`pip install langgraph==1.2.6`)
— a stale 0.2.x pin breaks every agent (`langgraph.runtime` / `ToolNode` import errors).
(2) A tool that requires structured output needs a **structured-output-capable model**
(llama-3.1-8b ✓; nemotron-550B degrades). (3) `with_structured_output` can return **None**
without raising — guard `if result is None: raise ...`.
*Success:* trace shows agent span → tool-call span → tool's LLM span (a deep multi-step trace).

---

## PHASE 4 — Postgres-backed tools ✅

**Step 4.1 — Open a connection pool in setup (before `yield`), close after.** The
async-generator lifecycle owns it — open once, reuse per call, close on teardown:
```python
import asyncpg
@register_function(config_type=Cfg)
async def my_db_fn(config, builder):
    pool = await asyncpg.create_pool(config.database_url)   # SETUP (once)
    async def _inner(...):                                  # uses pool every call
        row = await pool.fetchrow("SELECT ... WHERE x=$1", x)
        await pool.execute("INSERT INTO ... VALUES ($1,$2::jsonb)", a, json.dumps(b))
    yield FunctionInfo.from_fn(_inner, description="...")
    await pool.close()                                      # TEARDOWN (after yield)
```
*Why:* one place owns the connection lifecycle; no leaks. asyncpg DSN is
`postgresql://user:pass@host:5432/db` (no `+asyncpg`). JSON columns: pass
`json.dumps(value)` and cast `$n::jsonb`.
*Rule:* business records go in Postgres; agent telemetry does NOT — that's tracing (Phase 5).

**Step 4.2 — Make policy/config "live" data, not hardcode.** If the agent has an
autonomy/decision policy, store it in a table humans edit (e.g. `policy(segment ->
approved_mode, min_confidence)`) and have the tool LOOK IT UP. Keep a hard guardrail
in code regardless (e.g. critical is never auto). This is the "humans steer policy"
story made literal: promotion = a human `UPDATE`, not a redeploy.

**Step 4.3 — Log every decision, and capture the human review on the same row.** One
row per agent action: input, full structured output (incl. the agent's `developer_remediation`),
the decision, model, timestamp. Then nullable **review columns** filled later when a dev
reviews: `decision` (approve/reject), `final_remediation` (dev's corrected gold answer),
`review_comment` (why), `reviewer`, `reviewed_at`. Keep the review IN this table (one
review per ticket); keep the policy in its OWN table (different grain — rules vs events).
That single log is your audit trail AND your evals dataset (Phase 6).

**The promotion loop (the story):** agent suggests on every ticket → dev approves/rejects
+ writes `final_remediation` → metrics accrue per (severity, category) → on a *periodic*
review (weekly/monthly, not per-request) a human `UPDATE`s a `triage_policy` row to raise
a segment (suggest→approved→auto) once it clears the bar → keep sampling and auto-demote
on regression. Modes: **suggest** = human writes/sends; **approved** = agent drafts, human
one-click sends; **auto** = agent sends alone.

---

## PHASE 5 — Observability ✅

**Step 5.0 — Start Phoenix.** `pip install arize-phoenix opentelemetry-exporter-otlp`
then `python -m phoenix.server.main serve` → UI at http://localhost:6006 (OTLP HTTP
receiver on the same 6006/v1/traces; gRPC on 4317).

**Step 5.1 — Turn on tracing in config (no code changes).**
```yaml
general:
  telemetry:
    logging:
      console:
        _type: console
        level: INFO
    tracing:
      phoenix:
        _type: otelcollector           # 1.8 has no `phoenix` type; otelcollector = OTLP HTTP
        endpoint: http://localhost:6006/v1/traces   # HTTP receiver, NOT the 4317 gRPC port
        project: versos_agents
        resource_attributes:           # ← REQUIRED so NAT spans land in the named project
          openinference.project.name: versos_agents   # Phoenix groups by THIS, not `project:`
```
*Why:* every function/LLM/tool call becomes a trace (latency, tokens, inputs/outputs)
automatically. This is the headline reason to use NAT.
*Success:* traces appear at localhost:6006 in the `versos_agents` project.
*Gotcha — project naming:* Phoenix groups traces by the resource attribute
`openinference.project.name`, NOT by `project:`. Without the `resource_attributes` block,
NAT's spans fall into Phoenix's `default` project. Set BOTH the NAT config attribute AND
the OpenInference `register(project_name=...)` (Step 5.2) to the SAME name so all spans
(NAT chain spans + OpenInference llm spans) land in one project.
*Gotchas:* (1) NAT's otelcollector is OTLP **HTTP** → use 6006/v1/traces, not gRPC 4317.
(2) A `WinError 1225 connection refused` at workflow build is usually **Postgres down**
(the tool opens a DB pool), not telemetry — `docker compose up -d postgres`.

**Step 5.2 — Token/cost capture (NAT alone won't show it).** NAT's `<workflow>` spans
carry latency but NOT token counts, so Phoenix's token/cost panels stay empty. Fix:
add **OpenInference** LLM auto-instrumentation. In `register.py` (env-gated):
```python
if os.getenv("PHOENIX_TRACING") == "1":
    from phoenix.otel import register
    register(project_name="...", endpoint="http://localhost:6006/v1/traces", auto_instrument=True)
```
(`pip install openinference-instrumentation-langchain`). Run with `PHOENIX_TRACING=1`.
This emits an `llm ChatNVIDIA` span WITH token counts (separate project from NAT's spans).
Because OpenInference hooks the UNDERLYING model call, tokens are captured whether you use
`with_structured_output` or plain `ainvoke` — so keep the structured-output path. (If you
ever need usage in your OWN code on NIM, note `with_structured_output(..., include_raw=True)`
is unsupported there — read `resp.usage_metadata` from a plain `ainvoke` instead.)
**Cost stays $0** until you add a price entry for the NIM model (Phoenix has no NIM prices).

**Step 5.3 — Cost tracking in your own DB (better for a cost-watcher).** Capture tokens with
`UsageMetadataCallbackHandler` (`ainvoke(prompt, config={"callbacks":[cb]})` — works THROUGH
`with_structured_output`), price at a CONFIG rate (USD per 1M in/out; default = the partner
rate, e.g. Digital Ocean $0.90/$1.70), and store `prompt_tokens/completion_tokens/cost_usd`
per decision. A `GROUP BY (severity, category)` rollup = the cost-watcher view. This is real
queryable business data (cost per customer/segment/day) — more useful than Phoenix's panel,
and the rate-as-config mirrors the hosted-vs-self-host decision.

---

## PHASE 6 — Evals ✅  (offline custom evaluator + online review loop both built)
<!-- Verified: data/triage_eval.json (10 cases) + custom `severity_accuracy` evaluator
     (severity_lab/evals.py) → `nat eval` = 0.70; all misses UNDER-rate severity (critical→high).
     Pattern > number: promote low/medium, keep high/critical human-gated. -->


**Step 6.0 — The human-feedback loop (built).** Two pieces beyond logging:
- a **`review_ticket`** function: a dev POSTs JSON `{ticket_id, decision, reviewer,
  final_remediation?, review_comment?}`; it `UPDATE`s the triage_log row in place.
- a **`segment_metrics`** SQL view: per (severity, category) → total, reviewed,
  approved, `accept_rate` (of reviewed, fraction approved = the ground truth).
Promotion = a human `UPDATE triage_policy SET approved_mode='auto' ...` once a segment
clears the bar; the agent reads the new policy on the next ticket. Demote on regression.
Note: store `raw_confidence` AND `calibrated_confidence`; gate the policy bar on calibrated.

**Two layers of eval — say this; build both:**
- **Offline (golden set + `nat eval`)** = regression: catch breakage when prompt/model change.
- **Online (the review log)** = real ground truth: dev approve/reject → `accept_rate` per
  segment (`segment_metrics`). THIS gates promotion to autonomy.
- Framing: *offline proves "didn't break"; online proves "good enough to promote."*

**Step 6.1 — Make a dataset** (`data/triage_eval.json`): ~8–10 `{id, question, answer}`
records (`question` = complaint, `answer` = expected severity/category).

**Step 6.2 — Use a TASK-SPECIFIC evaluator, not a generic one.** Our triage output is a
JSON blob, so plain `exact_match` won't work. Write a small **custom evaluator**
(`@register_evaluator`) that parses the JSON and scores **severity/category accuracy** — i.e.
score the exact field that GATES AUTONOMY. (Bundled `trajectory`/`langsmith` evaluators judge
tool-trajectory / fuzzy text; `ragas` needs an extra. Verify the `register_evaluator` API on
the box first.)
```yaml
eval:
  general: { output_dir: ./.tmp/eval/, dataset: { _type: json, file_path: data/triage_eval.json } }
  evaluators:
    severity_accuracy: { _type: severity_accuracy }     # our custom evaluator
```
Register the evaluator in `register.py`, then **run it**. Put the `eval:` block in your
EXISTING workflow config (one file does both — `nat run` uses the workflow, `nat eval` also
reads the `eval:` block); don't make a separate eval config:
```bash
nat eval --config_file nat_sandbox/severity_lab/src/severity_lab/configs/triage_observed.yml
# → prints a table: | severity_accuracy | Avg Score 0.70 | ...output.json |
# → per-item results in ./.tmp/eval/severity_accuracy_output.json
```
*Why:* PROVE the agent works with numbers. Read the FAILURE PATTERN, not just the number —
ours: 0.70, every miss UNDER-rates severity → promote low/medium, hold high/critical.
*Success:* a score report in `output_dir`; quote accuracy + the failure pattern.

**Step 6.3 — Send the eval to Phoenix.** Add a `general.telemetry.tracing` block to the eval
config (same as Phase 5, with `resource_attributes: openinference.project.name: versos_eval`),
then run with `PHOENIX_TRACING=1`. Each golden-set case becomes a trace in the **versos_eval**
project — inspect any case's prompt/output/latency next to its score.

**Step 6.3b — (optional) Same golden set as a Phoenix EXPERIMENT.** Complements `nat eval`,
does NOT replace it. `nat eval` = CLI pass/fail = the CI gate. A Phoenix experiment runs the
same golden set but lands as a **versioned run in the Phoenix UI** — side-by-side run
comparison + per-example drill-down (the tool you open while iterating on a prompt). Script:
`nat_sandbox/severity_lab/scripts/phoenix_experiment.py` (uses `phoenix.client`:
`create_dataset` + `run_experiment`, same exact-match logic as `evals.py`).
```bash
# Phoenix server + Postgres + NIM must be up first.
.venv/Scripts/python.exe nat_sandbox/severity_lab/scripts/phoenix_experiment.py
# → http://localhost:6006 → Datasets → triage_severity_golden → Experiments
```
*Caveat:* it runs the REAL workflow, so it writes 10 rows into `triage_log` (tagged
`[phx-exp] `). Purge them: `DELETE FROM triage_log WHERE complaint_text LIKE '[phx-exp]%';`
*Interview line:* "`nat eval` is my CI gate; the Phoenix experiment is the visual
comparison layer I use while iterating — not two scorers, two surfaces."

**Step 6.4 — The ONLINE eval + calibration (SQL views over the review log).** This is the
ground-truth half. Views (in `sql/schema.sql`):
- `segment_metrics` — per segment: `accept_rate` (online accuracy) AND **`precision_eligible`**
  (accuracy on the confidence-≥-bar slice = what gates `auto`).
- `promotion_readiness` — applies the flip rule: `reviewed_eligible≥20 AND accept_rate≥0.95
  AND precision_eligible≥0.97 → eligible_for_auto`.
- `calibration_bins` — reliability diagram: per confidence bin, `avg_confidence` vs `accuracy`.
- `calibration_ece` — **ECE** = weighted-avg gap between confidence and accuracy (one number).
- `segment_metrics` ALSO exposes `feedback` + **`satisfaction_rate`** (`avg(customer_satisfied::int)`)
  — CSAT is the label that SURVIVES `auto` mode (where `decision` is NULL because no dev reviews).
*Tie-together:* a human promotes a `triage_policy` row only when OFFLINE accuracy + ONLINE
`promotion_readiness` clear the bar, AND confidence is calibrated (low ECE). ECE measures the
miscalibration; fixing it (isotonic/Platt) is a later script, then gate on `calibrated_confidence`.

**Step 6.5 — The cadence: passive log + two scheduled jobs (`jobs/`).** Online eval isn't a job
that "runs" — data accrues passively (agent INSERTs rows; devs UPDATE `decision`; customers fill
`customer_satisfied`), views are live. Two scheduled jobs act on it:
- `jobs/promotion_job.py` — WEEKLY. Reads `promotion_readiness`; DRY-RUN by default (proposes +
  prints the UPDATE), `--apply` (human-invoked) upserts the policy → `auto`. Grants trust.
- `jobs/monitor_job.py` — HOURLY. The brake. Auto-demotes any `auto` segment whose recent dev
  `accept_rate` OR `satisfaction_rate` drops below floor (min-sample guarded). Removes trust, no human.
```bash
.venv/Scripts/python.exe nat_sandbox/severity_lab/jobs/promotion_job.py          # propose
.venv/Scripts/python.exe nat_sandbox/severity_lab/jobs/promotion_job.py --apply  # human approves
.venv/Scripts/python.exe nat_sandbox/severity_lab/jobs/monitor_job.py            # hourly brake
```
*"Labels stop under auto"*: the ROW is always logged; only `decision` (dev label) dries up when no
dev reviews → fix with (a) 5% sampling of auto'd tickets back to humans, (b) the CSAT column as the
auto-mode ground truth. *Scheduling at Versos (AWS):* EventBridge Scheduler → ECS Fargate task on
the SAME image — `rate(1 week)` promotion (dry-run → Slack → human `--apply`), `rate(1 hour)` monitor.
*Asymmetry:* promote = human+weekly+deliberate; demote = automatic+hourly+instant.
*Gotcha:* Windows console (cp1252) crashes on `→`/`✓` in stdout — use ASCII.

---

## PHASE 7 — Guardrails 🚧

Guardrails aren't a single NAT feature — they're LAYERED defense-in-depth across in→think→act.
If one fails, the next catches it. **The layer table (status as built):**

| # | Layer | Stage | Status |
|---|-------|-------|--------|
| 1 | Input validation | before the LLM | ✅ `_screen_input` (reject empty/short, truncate >4000, flag injection→force suggest) |
| 2 | Output validation | after the LLM | ✅ `Literal` severities + `field_validator` normalizers + None-guard |
| 3 | Action / autonomy cap | before acting | ✅ `_decide_from_policy` ceiling + confidence bar |
| 4 | Hard-held criticals | before acting | ✅ critical→suggest in code (defense in depth) |
| 5 | Approval gate | before acting | ✅ suggest/approved = human commits the act |
| 6 | Kill switch | global | ✅ `system_flags.kill_switch` checked in `_decide_from_policy` |
| 7 | Topical / safety rails | in + out | ✅ NeMo input rail + Presidio PII-mask, INTEGRATED into the agent (`guardrails_runtime.py`) |

**Layer 7 is wired into the REAL tool, not just the demo** (`guardrails_runtime.py`, imported by
`severity_lab.py`):
- INPUT: NeMo input rail via `is_input_blocked()` — runs ONLY the input rail (`GenerationOptions(
  rails=["input"])`: allowed msg echoes back, blocked returns refusal). Gated by DB flag
  `system_flags.input_rail` (extra LLM call) so it flips LIVE and bulk runs stay cheap. Demoed:
  off-topic "best pizza topping?" blocked by the live agent.
- OUTPUT: `mask_pii()` (Presidio + spaCy `en_core_web_sm`) redacts PII in `suggested_customer_reply`
  BEFORE it's logged or returned (`John Smith`→`<PERSON>`, email→`<EMAIL_ADDRESS>`, card→`<CREDIT_CARD>`).
  Deterministic, always on, degrades gracefully if the model/engine is missing. WHY output (not input):
  the leak surface is the reply that goes OUT (could echo another customer's PII / hallucinate a card);
  the incoming ticket is the customer's OWN data.
- INPUT masking (optional, DB flag `system_flags.mask_input`, default off) — data-minimization
  posture: masks the complaint before it reaches NIM or `triage_log`. Demoed LIVE: flip the flag in
  Adminer/SQL (no restart) → next triage stored `Refund <PERSON> at <EMAIL_ADDRESS>…`. Trade: privacy
  vs slight context loss. The NeMo rail above still sees the ORIGINAL text for intent.
- **Flag mechanism (interview point):** all three runtime guardrail toggles (`kill_switch`,
  `input_rail`, `mask_input`) live in `system_flags` and are read per-request via `_flag_enabled()`
  → flip LIVE, fleet-wide, no restart. Env vars would need a restart (snapshotted at process start);
  DB flags are right for things you may change WHILE running. Pick the mechanism by change-urgency.

Detail per layer (✅ built):
- ✅ **Input validation** (layer 1, before the LLM) — `_screen_input()` in severity_lab.py:
  REJECT empty/too-short (no LLM call), TRUNCATE > 4000 chars, FLAG prompt-injection patterns →
  flagged tickets are still triaged but FORCED to `suggest` (can never auto-act). Logged for audit.
- ✅ **Output validation** (layer 2) — `Literal` severities + `field_validator` normalizers + None-guard.
- ✅ **Autonomy cap** (layer 3) — `_decide_from_policy` ceiling + confidence bar.
- ✅ **Hard-held criticals** (layer 4) — critical→suggest in code regardless of policy.
- ✅ **Approval gate** (layer 5) — suggest/approved = a human commits the act.
- ✅ **Kill switch** (layer 6) — `system_flags.kill_switch` (DB-backed, not env): checked at the TOP
  of `_decide_from_policy` (the single chokepoint), forces EVERY segment to `suggest` instantly with
  no redeploy. DB so one UPDATE disables autonomy fleet-wide, live during an incident. Demoed:
  OFF→auto, ON→suggest, OFF→auto. Flip via Adminer/psql or a `PUT /system/kill-switch` route.
- ✅ *(optional)* **NeMo Guardrails** (layer 7, separate NVIDIA lib `nemoguardrails`) — LLM-powered
  rails. Built an INPUT rail (`guardrails/config.yml` + `prompts.yml`, built-in `self check input`
  flow over our NIM). Demoed live: genuine complaint PASSED; jailbreak + OFF-TOPIC both BLOCKED
  ("I'm sorry, I can't respond to that"). Key point: the LLM rail caught the off-topic msg that the
  regex `_screen_input` would miss — it screens INTENT, not just known phrases. Run:
  `python nat_sandbox/severity_lab/guardrails/demo.py`. Regex (cheap, first) + LLM rail (catches
  novel/rephrased, second) = layered.
*Why:* "good intuition about autonomy" is in the job ad. Each layer kills a different failure mode;
no single point of trust. Make the safety logic explicit and unit-tested.

---

## INDEX-HYGIENE — second agent on the reusable spine ✅ (built)

**Full vertical built** (`nat_sandbox/severity_lab/index_hygiene.py`) — the SAME spine as triage,
re-skinned onto infra (ticket→finding, severity→risk, remediation→DDL). Hits the JD's day-one list.
```text
scan (deterministic catalog SQL) → risk → precision guard (index_seen observation window)
  → autonomy gate (index_policy; DROP HARD-HELD, never auto) → human approve → apply (DDL
  CONCURRENTLY) → efficacy (index_action_metrics: bytes_reclaimed + re_create_rate)
```
- Tables: `index_findings` (decision log + eval set), `index_policy` (ceiling per finding_type×risk),
  `index_seen` (first-seen observation window), view `index_action_metrics`.
- NAT workflow: `configs/index_hygiene.yml` (NO llms block — detection needs no LLM). `nat run … --input scan`.
- Offline eval = precision/recall regression harness (`jobs/index_hygiene_eval.py`); demoed
  precision 1.0 (guard on) vs 0.875 (guard off — the newborn FP). Online = `index_action_metrics`.
- Autonomy evidence: `re_create_rate ≈ 0` over many drops is what would justify promoting
  `unused` from suggest→approved→auto — ground truth measured from the DB, not opinion.
- Key precision lessons learned live: "missing" only on BIG tables (small tables seq-scan anyway);
  "unused" only after an observation WINDOW (a newborn index legitimately has 0 scans).

### Catalog reference (the agent's data sources)

Detection is DETERMINISTIC SQL over system views — no LLM. The views/columns to scan & monitor:

| Catalog view | Key columns | What it tells you (finding) |
|---|---|---|
| `pg_stat_user_tables` | `seq_scan`, `idx_scan`, `n_live_tup`, `n_dead_tup` | high `seq_scan` vs `idx_scan` on a BIG table (`n_live_tup`) → **missing index**; high `n_dead_tup` → bloat/needs VACUUM |
| `pg_stat_user_indexes` | `idx_scan`, `idx_tup_read` | `idx_scan = 0` (non-PK/unique) → **unused index** |
| `pg_index` | `indisunique`, `indisprimary`, `indisvalid`, `indkey` | exclude PK/unique from drop; `indisvalid = false` → **invalid index**; same `indkey` on a table → **duplicate** |
| `pg_indexes` | `indexdef` | the CREATE statement (for dup/redundancy comparison + rollback) |
| `pg_stat_statements`* | `mean_exec_time`, `calls`, `query` | the ACTUAL **slow queries** → which column wants an index (gold source) |
| `pg_statio_user_indexes` | `idx_blks_read`, `idx_blks_hit` | low cache-hit → index churn / IO pressure |
| sizing fns | `pg_relation_size(oid)`, `pg_size_pretty()` | index/table **size** → feeds risk (a 2 GB unused index matters; 8 kB doesn't) |
| bloat | `pgstattuple`* / bloat-estimate query | dead space in an index → **REINDEX** candidate |

*`pg_stat_statements` / `pgstattuple` are extensions — may be absent on the box; degrade gracefully.*

Quick examples:
```sql
-- unused (droppable) indexes, biggest first
SELECT s.relname, s.indexrelname, s.idx_scan, pg_size_pretty(pg_relation_size(s.indexrelid))
FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid=s.indexrelid
WHERE NOT i.indisunique AND NOT i.indisprimary AND s.idx_scan=0
ORDER BY pg_relation_size(s.indexrelid) DESC;

-- missing-index candidates: big tables scanned sequentially
SELECT relname, seq_scan, idx_scan, n_live_tup
FROM pg_stat_user_tables WHERE seq_scan > idx_scan AND n_live_tup > 10000;

-- duplicate indexes: same table + same column set
SELECT indrelid::regclass, array_agg(indexrelid::regclass)
FROM pg_index GROUP BY indrelid, indkey HAVING count(*) > 1;
```
**Precision guards:** only flag big tables for "missing" (small tables seq-scan anyway); exclude
PK/unique from "unused"; confirm a proposed index with `EXPLAIN`/HypoPG before recommending. Risk
= f(table rows × index size × action): CREATE = low (reversible), DROP = high (destructive, hard-held).

---

## PHASE 8 — Present (the last hour) 🔜

Tell the story in this order (≈3-min spine, then depth on questions):
1. **What the sim is** and what problem your agents solve on it.
2. **Architecture** — agents as NAT functions, Postgres for state, one orchestrator.
3. **Observability** — show a live trace.
4. **Evals** — show the score + the dataset; explain what "good" means.
5. **Guardrails / autonomy** — show the suggest→approved→auto policy + kill switch.
6. **Honesty** — what's stubbed, what you'd do next, what surprised you.
> Closing line: *"The agents recommend; promotion to autonomous is governed by
> evidence from the eval suite and the traces — and high-impact actions stay behind
> a human. The proof they're safe is itself a deliverable."*

---

## BACKEND — custom FastAPI for the Next.js frontend 🔜 (do near the end)

`nat serve` = one workflow per endpoint. A real app needs many routes → build your OWN
FastAPI (`backend/main.py`) and split the work:
- **plain reads/writes** (tickets, metrics, policy, review) → **asyncpg directly**, no NAT.
- **agentic actions** (triage, copilot ask) → **run NAT workflows in-process**.

**Production-grade layering** (don't dump it all in main.py):
```
backend/
  main.py          app factory + lifespan (composition only)
  core/config.py   typed settings (+ normalize DSN: asyncpg needs postgresql://, NOT postgresql+asyncpg://)
  db.py            pool + get_pool dependency
  schemas.py       request models
  services/        business logic, NO FastAPI imports (unit-testable): tickets/policy/nat
  routers/         thin HTTP layer → calls services: tickets/policy/agents
```
Rule: routers translate HTTP↔Python; services do the work; NAT embedding is isolated in
`nat_service` (swap NAT → only that file changes). Inject the pool via `Depends(get_pool)`.

Embed pattern (verified): build each workflow ONCE in `lifespan`, reuse per request.
```python
from nat.runtime.loader import load_workflow
# lifespan: app.state.nat.triage = await stack.enter_async_context(load_workflow(CONFIG))
# per request (in nat_service.run_workflow):
async with session_manager.session() as session:
    async with session.run(message) as runner:
        result = await runner.result(to_type=str)
```
Add CORS so the Next.js dev server can call it. **Next.js doesn't recreate routes** — it
just `fetch()`es the backend; review's approve/reject is a backend route a HUMAN hits, never
an agent tool. Routes: `GET /tickets /metrics /policy`, `POST /triage /ask /tickets/{id}/review`,
`PUT /policy`. Run: `uvicorn backend.main:app --port 8090`.

---

## DEPLOYMENT — containerizing the NAT backend with Postgres 🔜 (do at the end)

Locally NAT runs on your host, so the tool connects to Postgres at
`postgresql://versos:versos@localhost:5432/versos` (localhost works because Postgres
publishes 5432 to the host). **In containers this breaks** — each container's `localhost`
is itself, so NAT's `localhost:5432` points at the NAT container, not Postgres.

Fix (compose, 3 things):
1. **Same network** — compose puts all services on one network automatically.
2. **Address Postgres by its SERVICE NAME**, not localhost:
   `DATABASE_URL=postgresql://versos:versos@postgres:5432/versos`  ← host = `postgres`.
3. **Inject the DSN as an env var** into the NAT container + `depends_on` with a healthcheck
   so NAT waits for Postgres to be ready.
```yaml
services:
  postgres: { image: postgres:16, environment: {POSTGRES_USER: versos, ...}, healthcheck: {...} }
  nat:
    build: .
    environment:
      DATABASE_URL: postgresql://versos:versos@postgres:5432/versos   # service name, not localhost
      NVIDIA_API_KEY: ${NVIDIA_API_KEY}
    depends_on: { postgres: { condition: service_healthy } }
```
Note: publishing 5432 to the host is only so YOUR tools (psql, a host app) can reach it —
container-to-container talk uses the shared network and doesn't need the published port.
Same idea for Next.js → NAT: the Next.js container calls `http://nat:8000/...` (service name).

**Prod topology (the "how would you deploy this" answer).** Fargate is NOT separate from ECS —
it's an ECS launch type. Everything containerized runs on **ECS/Fargate**; the real split is the
ECS object type:
- **Backend** (FastAPI + NAT) = ECS **Service** (always-on, N copies behind an ALB).
- **Jobs** (promotion/monitor) = ECS **Task** (run once, exit), fired by **EventBridge Scheduler**.
  SAME image as backend, different command (`uvicorn …` vs `python jobs/monitor_job.py`).
- **Postgres** = **RDS** (managed, NOT a container; compose Postgres is dev-only — prod points
  DATABASE_URL at the RDS endpoint).
- **Next.js** = usually **NOT ECS** → Vercel/Amplify/S3+CloudFront, calls the backend API over HTTPS.
```
Next.js (Vercel) --HTTPS--> ECS Service (Fargate): FastAPI+NAT --> RDS Postgres
EventBridge: rate(1w)->ECS Task promotion_job ; rate(1h)->ECS Task monitor_job
```

---

## Quick command reference
```bash
nat --version
nat info components -t function        # discover tools (also: evaluator, tracing, llm_provider)
nat validate --config_file f.yml       # check a config before running
nat run   --config_file f.yml --input "..."
nat serve --config_file f.yml          # REST API + built-in chat UI
nat eval  --config_file f.yml
```
