# Interview Day — Claude Code Prompting Playbook

> **Living document.** Kept in sync with `interview-step-by-step.md` every time we add
> or change something. The runbook = what YOU do/understand. This file = what you
> TYPE TO CLAUDE CODE to get it built fast on the day.

## How to use this
- Paste these prompts to Claude Code **in order**, one phase at a time.
- After each, **read what it did and ask it to explain** before moving on — you have
  to defend this in the last hour. Never accept code you can't narrate.
- Replace `<...>` placeholders with real details from their simulation.

---

## Meta-rules for prompting Claude Code under time pressure

1. **Orient it first, build second.** Your first prompt should make it *read* the
   simulation and report back — not write code.
2. **One phase per prompt.** Small, verifiable chunks beat one giant "build everything."
3. **Always ask for verification.** "Run it and show me the output" > "looks done."
4. **Ask it to explain as it goes.** "Explain each file you create in one line."
5. **Make it state assumptions.** "List what you're assuming about the sim before coding."
6. **Keep it honest.** "If something is stubbed or untested, say so explicitly."
7. **Pin the stack.** Remind it: Python + NeMo Agent Toolkit (NAT, `nat` CLI, v1.8) +
   Postgres. No fakes/mocks for core logic.

---

## THE REUSABLE SPINE (the sim probably isn't support-triage — re-skin this onto it)

JD day-one jobs are INFRA agents (missing indexes, slow queries, broken jobs, stale data,
regressions). The "ticket" becomes a finding/job/query; "severity" → its risk; "remediation" → the
fix the agent proposes. Build, in order:
1. NAT tool + `with_structured_output(model)` (Literal enum for the gating field + validators).
2. Policy-as-data autonomy table (human-granted ceiling per segment; code enforces; LLM never grants).
3. suggest / approved / auto (confidence bar; high-impact hard-held in code).
4. Log every decision (audit trail + eval dataset + shadow signal).
5. Evals: OFFLINE golden set + `nat eval` (CI gate) + ONLINE SQL views over the log (ground truth).
6. Layered guardrails (input/output validate, autonomy cap, critical hold, approval gate, kill switch).
7. Kill switch (DB flag) + graceful degradation on every external dep.
Build the thinnest end-to-end slice FIRST (tool → structured output → log one decision → one policy
lookup), get it green, THEN add evals/guardrails/breadth. See runbook "DAY-OF STRATEGY" for the
first-30-minutes orientation + JD-alignment cheat-sheet.

---

## PHASE 0 — Orient (paste first)

```
You are helping me build an agentic system for a timed interview. Stack is fixed:
Python + NVIDIA NeMo Agent Toolkit (the `nat` CLI, ~v1.8) + Postgres. Do NOT write
code yet.

First, explore this repository and the simulation it contains. Then report back, concisely:
1) What the simulation does and how I interact with it (DB? API? function calls?).
2) Where state lives (Postgres tables / connection string / env vars).
3) The 3–5 highest-leverage agentic tasks I could build on top of it.
4) Anything already installed: run `python --version`, `nat --version`, and list nat
   components. Tell me the versions so we use correct syntax.
List your assumptions explicitly. Ask me anything you need before we plan.
```

---

## PHASE 1 — Environment

```
Set up the environment, explaining each step in one line as you go:
- create a Python venv,
- install `nvidia-nat[langchain]` (add pip --trusted-host flags if the network blocks SSL),
- confirm with `nat --version` and `nat info components -t function`.
If Postgres isn't already running for the sim, create a docker-compose with a postgres
service and bring it up. ALSO add an Adminer service (image adminer:4, ports 8081:8080,
depends_on postgres) so I get a clickable DB browser at http://localhost:8081 — Postgres has
no built-in GUI. (In Adminer: Server=postgres = the service name, not localhost.) Show me the
output proving each piece works. Don't proceed to agents yet.
```

---

## PHASE 2 — Build a real tool for their simulation (the core skill)

```
We're building a real agent tool, not a toy. The requirement: <state ONE concrete
task the agent must do on the simulation, with its inputs and expected output>.

Build it as a NAT function, explaining each step in one line:
- scaffold a package with `nat workflow create` (note: on Windows the symlink step
  errors but files are still written, and auto-install is skipped),
- write the CONFIG CLASS for this tool: required fields (no default) for things the
  caller must supply (e.g. llm_name, target table); optional fields (with defaults)
  for tunables. Use a clear `name="<tool_id>"`.
- write the FUNCTION BODY: outer = setup that runs once (get llm/db via builder);
  inner = the actual work per call against the simulation; yield FunctionInfo with a
  precise description (the agent reads it to decide when to call the tool).
- `pip install -e` the package, then `nat info components -t function -q <tool_id>`
  to confirm it registered.
- smoke-test the WIRING first with a no-LLM config (tool as the workflow), then make
  the inner logic real. Show me the `nat run` output.
Keep the inner logic honest — if a piece isn't wired yet, return a clear placeholder
and say so. Explain the outer-once / inner-per-call distinction as you go.
```
Repeat this prompt for each capability the agent needs.

---

## PHASE 3 — Make the tool call a real LLM (NIM)

```
Now wire a real model call.
- handle the key: add `from dotenv import load_dotenv; load_dotenv()` at the top of
  register.py so NVIDIA_API_KEY loads from .env (NAT does NOT auto-read .env),
- add an `llms:` block (`_type: nim`, a small fast model like meta/llama-3.1-8b-instruct),
- in the function SETUP get the model once:
  `llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)`,
- in the INNER function call it with `await llm.ainvoke(prompt)` to <do X on the sim>,
- GUARD the output: validate the model's answer against allowed values, else fall back,
- return a structured result: prefer `llm.with_structured_output(Schema)` with a Pydantic
  schema; use `Literal[...]` for enum fields (it enforces shape, not values) and keep a
  validation fallback. If you hit CERTIFICATE_VERIFY_FAILED, add
  `import truststore; truststore.inject_into_ssl()` at the top of register.py.
Run it on a couple of contrasting inputs to prove the model (not the fallback) is acting.
Then upgrade the workflow to a `react_agent` with `tool_names: [...]` so an agent decides
which tools to call. Show the agent's reasoning + tool calls. Explain what changed.
```

---

## PHASE 4 — Postgres-backed tools

```
Make the agent read/write the simulation's Postgres state.
- in a NAT function, open an asyncpg connection pool in setup (before `yield`) and
  close it after `yield`; DSN is postgresql://user:pass@host:5432/db,
- implement <a tool that reads X and a tool that writes Y> against the real schema
  (JSON columns: pass json.dumps(value) and cast $n::jsonb),
- if the agent has a decision/autonomy policy, store it in a TABLE humans edit and
  look it up at runtime (keep a hard guardrail in code regardless) — promotion = a
  human UPDATE, not a redeploy,
- LOG every decision to a table (input, full structured output incl. agent remediation,
  the decision, model, timestamp) PLUS nullable review columns filled when a dev reviews:
  decision (approve/reject), final_remediation (dev's gold answer), review_comment,
  reviewer, reviewed_at — that's the audit trail AND the evals dataset. Keep the review
  in this table (one per ticket); keep policy in its own table (rules vs events),
- keep BUSINESS records in Postgres but DO NOT log agent telemetry there (that's tracing).
Show a run that actually changes a row, and the SQL/Pydantic involved. Explain the
connection lifecycle and why policy-as-data matters.
```

---

## PHASE 5 — Observability

```
Turn on tracing via config only (no code changes):
- add `general.telemetry` with console logging and an `otelcollector` tracing exporter
  pointing at Phoenix's OTLP HTTP receiver (http://localhost:6006/v1/traces, NOT the 4317
  gRPC port; v1.8 has no `phoenix` _type),
- IMPORTANT: also add `resource_attributes: { openinference.project.name: <name> }` under
  the exporter — Phoenix groups by THAT, not `project:`; without it NAT spans fall into the
  `default` project. Set it to the SAME name as the OpenInference register() below.
- token/cost panels: NAT alone doesn't emit token counts, so add OpenInference LLM
  auto-instrumentation in register.py (env-gated): `phoenix.otel.register(project_name=<name>,
  endpoint=..., auto_instrument=True)` and `pip install openinference-instrumentation-langchain`.
  Run with PHOENIX_TRACING=1. (Cost panel needs a model price added in Phoenix Settings.)
- start Phoenix if available, run a workflow, and show me a trace with latency + tokens + tool calls.
Explain how NAT produces these traces (IntermediateStep event stream) in 2–3 sentences.
```

---

## PHASE 6 — Evals (the differentiator)

```
Build evals in TWO layers and explain the split:
- OFFLINE (golden set + nat eval) = regression: catch breakage when prompt/model change.
- ONLINE (the review log) = real ground truth: dev approve/reject -> accept_rate per segment
  (segment_metrics). THIS gates promotion. Framing: offline proves "didn't break", online
  proves "good enough to promote".
For the offline eval:
- create a small dataset (json: id/question/answer, ~8-10) of realistic cases from the sim
  (answer = the expected value of the field that gates autonomy, e.g. severity/category),
- the output is a JSON blob so DON'T use plain exact_match — write a TASK-SPECIFIC custom
  evaluator (@register_evaluator; verify the API on the box first) that parses the JSON and
  scores severity/category accuracy (the exact field that gates autonomy),
- add the `eval:` block to your EXISTING workflow config (DON'T make a separate eval file —
  one config does both: `nat run` uses the workflow, `nat eval` also reads the `eval:` block).
  NOTE the binding: `nat eval` runs THE top-level `workflow:` (one per config, positional — the
  evaluator never names it, it just scores that run's output). Many functions, ONE workflow per
  config; to eval a 2nd workflow (index-hygiene, pipeline-healer) = a 2nd config + 2nd `nat eval`.
  Register the evaluator in register.py, and run:
  `nat eval --config_file <your_workflow.yml>` → score table + ./.tmp/eval/<evaluator>_output.json.
- send the eval to Phoenix: add a general.telemetry.tracing block to that same config
  (resource_attributes openinference.project.name: versos_eval) and run with PHOENIX_TRACING=1
  → each golden-set case is a trace in the versos_eval project.
- (optional, time permitting) ALSO run the golden set as a Phoenix EXPERIMENT for a visual
  run-over-run comparison (phoenix.client create_dataset + run_experiment, same exact-match
  logic). Frame it as a SECOND SURFACE not a second scorer: "nat eval = CI gate, Phoenix
  experiment = the diff I eyeball while iterating on a prompt". Standalone script, no new yml.
  Caveat: it runs the real workflow so it writes rows to triage_log — tag + purge them.
For the ONLINE eval (ground truth from the review log), build SQL views:
- segment_metrics: accept_rate (online accuracy) AND precision_eligible (accuracy on the
  confidence-≥-bar slice = what gates auto),
- promotion_readiness: applies the flip rule (reviewed_eligible>=N AND accept_rate>=X AND
  precision_eligible>=Y -> eligible_for_auto),
- calibration_bins (reliability diagram: avg_confidence vs accuracy per confidence bin) and
  calibration_ece (ECE = weighted-avg gap = is the confidence honest?),
- a customer_satisfied BOOLEAN column (+ feedback_at) → segment_metrics also exposes
  satisfaction_rate. CSAT is the label that SURVIVES auto mode (decision is NULL there because no
  dev reviews). Explain "labels stop under auto": the row is still logged, only the dev label
  dries up; fix with 5% sampling of auto'd tickets back to humans + the CSAT column.
Then add the CADENCE as two scheduled jobs (jobs/):
- promotion_job.py WEEKLY: reads promotion_readiness; DRY-RUN proposes, --apply (human) upserts
  policy -> auto. Grants trust, human-gated.
- monitor_job.py HOURLY: the brake; auto-demotes any auto segment whose recent accept_rate OR
  satisfaction_rate drops below floor (min-sample guarded). Removes trust, no human.
- Schedule at Versos (AWS): EventBridge Scheduler -> ECS Fargate task on the same image,
  rate(1 week) promotion + rate(1 hour) monitor. Asymmetry: promote=human+weekly, demote=auto+hourly.
  (Use ASCII in job stdout — Windows cp1252 crashes on arrows.)
Tie it together: a human promotes a triage_policy row only when offline accuracy + online
promotion_readiness clear the bar AND ECE is low (confidence calibrated). Read the eval FAILURE
PATTERN, not just the number. Be honest about sample size.
```

---

## PHASE 7 — Guardrails / autonomy

```
Frame guardrails as LAYERED defense-in-depth across in->think->act (if one fails the next catches):
- INPUT validation (before the LLM): reject empty/too-short (no LLM call), truncate over-long,
  FLAG prompt-injection patterns -> flagged tickets still triage but are FORCED to suggest (a
  manipulated ticket can never auto-act). Flag, don't hard-block (false positives). Log it.
- OUTPUT validation: Literal enums + field_validator normalizers + None-guard.
- AUTONOMY cap: policy function decides suggest/approved/auto from confidence + impact, HARD-HOLDS
  high-impact (critical) behind a human in code (blast-radius control).
- APPROVAL gate (agent recommends; a separate human step authorizes the action).
- KILL switch (a DB/config flag that forces everything to suggest-only, instantly).
- (BUILT + INTEGRATED) NeMo Guardrails (NVIDIA lib `nemoguardrails`): config folder (config.yml =
  NIM model + `rails: input: flows: [self check input]`; prompts.yml = Yes/No block prompt). Attach
  to the AGENT at the tool chokepoint via guardrails_runtime.py (build-once lru_cache): input rail
  `is_input_blocked()` runs ONLY input rails (GenerationOptions(rails=["input"]); allowed echoes,
  blocked refuses), gated by DB flag system_flags.input_rail. Sell it: LLM rail screens INTENT the regex can't.
- PII OUTPUT rail: Presidio (presidio-analyzer/anonymizer + spaCy en_core_web_sm) masks
  suggested_customer_reply (John Smith->`<PERSON>`, email->`<EMAIL_ADDRESS>`, card->`<CREDIT_CARD>`)
  before logging/returning. Deterministic, always on. WHY output: the leak is in the reply that goes
  OUT; the incoming ticket is the customer's own data. Optional INPUT masking behind DB flag
  system_flags.mask_input (default off) = data-minimization (raw PII never reaches NIM/triage_log).
  All 3 runtime toggles (kill_switch/input_rail/mask_input) are DB flags read per-request via
  _flag_enabled() so they flip LIVE (no restart) — env vars freeze at process start; pick by urgency.
  rails flows menu: input(self check input / jailbreak heuristics / mask sensitive data),
  output(self check output / self check facts / mask sensitive data), retrieval, dialog(Colang).
- unit tests for the policy (deterministic, no LLM).
Run the tests. Explain how this maps to "graduating agents from suggest to autonomous", and that
each layer kills a DIFFERENT failure mode = no single point of trust.
```

---

## PHASE 8 — Presentation prep (use near the end)

```
Help me prepare to present this in ~10 minutes. Produce:
1) a 3-minute spoken walkthrough (sim → architecture → observability → evals →
   guardrails → honesty),
2) the single strongest sentence about autonomy/safety,
3) 8 likely questions with crisp answers,
4) an honest list of what's stubbed and what I'd do next.
Base it ONLY on what we actually built and verified today.
```

---

## BACKEND — custom FastAPI for Next.js (use near the end)

```
Build a PRODUCTION-GRADE custom FastAPI backend for the Next.js frontend — NOT nat serve
(that's one-workflow-per-endpoint). Use a LAYERED structure (don't dump it in main.py):
  backend/main.py         app factory + lifespan (composition only)
  backend/core/config.py  typed settings (normalize DSN: asyncpg needs postgresql://, not +asyncpg)
  backend/db.py           pool + get_pool dependency
  backend/schemas.py      request models
  backend/services/       business logic, NO FastAPI imports (unit-testable): tickets/policy/nat
  backend/routers/        thin HTTP layer -> calls services: tickets/policy/agents
Split the work:
- plain reads/writes (tickets, metrics, policy, human review) -> asyncpg in services, no NAT,
- agentic actions (triage, copilot ask) -> run NAT workflows IN-PROCESS, isolated in
  nat_service: build each workflow ONCE in the lifespan with `load_workflow(config)` (from
  nat.runtime.loader), then per request:
  `async with sm.session() as s: async with s.run(msg) as r: result = await r.result(to_type=str)`.
- add CORS so the Next.js dev server can call it.
Rule: routers translate HTTP<->Python; services do the work (importable by tests/cron); NAT
embedding lives only in nat_service. Keep the human approve/reject (review) as a backend route
a HUMAN hits — never an agent tool. Show me each route working with curl.
```

---

## DEPLOYMENT — containerize NAT + Postgres (use at the end, if time)

```
Containerize the NAT backend alongside Postgres with docker-compose.
- Key gotcha: inside containers `localhost` is the container itself, so NAT can't reach
  Postgres at localhost:5432. Put both services on the same compose network and have NAT
  address Postgres by its SERVICE NAME: DATABASE_URL=postgresql://user:pass@postgres:5432/db.
- Inject DATABASE_URL (and NVIDIA_API_KEY) as env vars into the NAT container; add
  depends_on with a Postgres healthcheck so NAT waits until the DB is ready.
- Publishing 5432 to the host is only for my local tools — container-to-container talk uses
  the shared network. Same pattern for Next.js → NAT: call http://nat:8000 (service name).
Show me the compose file and a working run inside containers.
```

---

## Emergency / recovery prompts (if you get stuck)

- **Something broke:** `Stop. Show me the exact error and the failing command. Diagnose
  the root cause before changing anything. Propose the smallest fix.`
- **Falling behind on time:** `We have <N> minutes left. What's the highest-impact thing
  to finish or polish for the presentation? Cut scope ruthlessly and tell me what you're cutting.`
- **Lost the thread:** `Summarize what we've built so far, what's working, what's stubbed,
  and the 3 best next steps. Then wait.`
- **Don't understand the code:** `Explain this file line by line as if teaching me, then
  ask me 2 questions to check I understood.`
```
