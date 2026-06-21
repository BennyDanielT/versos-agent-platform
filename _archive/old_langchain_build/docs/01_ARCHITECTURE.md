# Architecture

> Read this first. It gives you the mental model; the other docs zoom in.

## 1. The one-paragraph pitch

I built a compact **agent-operations platform** that mirrors the surfaces in the
Versos role: AI-assisted **support triage**, an AI **media-enrichment pipeline**
over uploaded assets, and an automated **quality auditor**. They sit on one
substrate — FastAPI (async) + Postgres + S3 + LangGraph — and share a single
deliberate idea: **agents operate at explicit autonomy levels (suggest →
approved → auto), and promotion between levels is governed by evidence, not vibes.**

## 2. System diagram

```
                              ┌────────────────────────────┐
   HTTP client / Swagger ───► │        FastAPI (async)      │
                              │  /tickets /assets /audit    │
                              └───┬───────┬───────────┬─────┘
                                  │       │           │
                  ┌───────────────┘       │           └───────────────┐
                  ▼                       ▼                           ▼
        ┌───────────────────┐   ┌───────────────────┐      ┌───────────────────┐
        │  TRIAGE AGENT     │   │ ENRICHMENT PIPE   │      │  QUALITY AUDITOR  │
        │  (Option A)       │   │ (Option B)        │      │  (trust layer)    │
        │  supervisor +     │   │ parallel fan-out  │      │  rules + LLM      │
        │  specialists      │   │                   │      │                   │
        │                   │   │  transcribe ┐     │      │                   │
        │  classify         │   │  language   ├─►reduce    │  flags bad/       │
        │   ├─ summarize     │   │  keywords   ┘     │      │  incomplete data  │
        │   └─ remediate     │   │                   │      │                   │
        │  → decide(mode)   │   │                   │      │                   │
        └─────────┬─────────┘   └─────────┬─────────┘      └─────────┬─────────┘
                  │                       │                          │
                  ▼                       ▼                          ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │   Provider seam  app/agents/llm.py   →  NVIDIA NIM (swappable)      │
        └──────────────────────────────────────────────────────────────────┘
                  │                       │                          │
   ┌──────────────┴───────────────────────┴──────────────────────────┴────────┐
   │  Postgres  (business records + workflow state)                            │
   │  S3 / LocalStack  (raw media + transcript blobs)                          │
   │  LangSmith / OTel  (agent TELEMETRY — deliberately NOT in Postgres)       │
   └───────────────────────────────────────────────────────────────────────────┘

Legend:  ✅ built = triage agent, schema, FastAPI, provider seam, tests
         ⏳ next  = enrichment pipeline (Step 4), auditor (Step 5), evals (Step 6)
```

## 3. The five design decisions you must be able to defend

### D1 — One platform, not three demos
The connective tissue is the **autonomy model**. Each feature is an agent that
operates at some autonomy level; the auditor is the mechanism that justifies
promoting one. If asked "why these three features?", the answer is that together
they cover Versos' stated surfaces (support, pipelines, data quality) *and* let
one trust story govern all of them.

### D2 — Business records in Postgres, telemetry in LangSmith/OTel
Postgres stores facts the business cares about even if no agent existed (a
ticket, its category, who approved it). Token counts, latencies, traces, prompt
versions, intermediate reasoning — those are **telemetry**, and they go to
LangSmith / OpenTelemetry. Mixing them would bloat the relational store and
confuse "what happened in the business" with "how the model behaved."
*(I originally considered an `agent_actions` table and rejected it — this is a
deliberate, defensible call.)*

### D3 — The autonomy seam lives in the data model
`support_tickets.triage_mode ∈ {suggest, approved, auto}` and `status` model the
graduation path. Autonomy isn't a runtime flag bolted on — it's a column, so it's
queryable, auditable, and visible in the DDL.

### D4 — A provider seam, so orchestration never marries a vendor
`app/agents/llm.py` exposes `get_structured_llm(schema)`. Behind it: real NVIDIA
NIM (`ChatNVIDIA`). The specialists and graph depend on the *interface*, never on
a vendor SDK — so swapping NIM for OpenAI or a local model is a change in that one
file, not a rewrite. This is the "evaluate many, pick the right one, retire
abstractions" posture the role asks for.

### D5 — Two *different* multi-agent patterns on purpose
- **Triage = supervisor + specialists** (Option A): one orchestrator routes to
  single-responsibility specialists, then a supervisor node decides.
- **Enrichment = parallel pipeline** (Option B): independent enrichers run
  concurrently and a reducer merges. *(Step 4.)*

Having both lets me talk about *when* to choose each: supervisor when steps
depend on each other / need routing; parallel when steps are independent and
latency matters.

## 4. Request lifecycle (triage, end to end)

1. `POST /tickets` → row created, `status=new`, `triage_mode=suggest`.
2. `POST /tickets/{id}/triage` → endpoint loads the ticket, calls `run_triage`
   **in a threadpool** (LangGraph `.invoke` is sync; we don't block the event loop).
3. Graph runs: `classify` → (`summarize` ‖ `remediate`) → `decide`.
4. Each specialist calls `get_structured_llm(Schema).invoke(prompt)` → typed object.
5. `decide` maps confidence + severity → recommended mode (critical always held).
6. Endpoint writes `issue_category, severity, ai_summary, ai_remediation,
   ai_confidence, triage_mode` and sets `status=triaged_suggested`.
7. Response is the enriched ticket. **The agent recommended; it did not act.**

## 5. Tech stack and why each piece

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + async | I/O-bound (DB + LLM); async keeps throughput up under concurrent agent runs |
| ORM | SQLAlchemy 2.0 + asyncpg | typed models, async driver, mature |
| DB | Postgres 16 | relational integrity for business records; rich indexing |
| Storage | S3 (LocalStack local) | same boto3 code runs against real AWS |
| Orchestration | LangGraph | explicit stateful graphs → traceable, replayable, testable nodes |
| Abstractions | LangChain | structured outputs, model interfaces |
| Models | NVIDIA NIM (`ChatNVIDIA`) | aligns with Versos' NVIDIA stack; OpenAI-compatible |
| Observability | LangSmith / OTel | agent telemetry, separate from business data |
| Tests | pytest | deterministic regression on the safety-critical promotion policy |
```
