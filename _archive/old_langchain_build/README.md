# Versos Agent-Ops Platform

A compact internal platform that mirrors the operational surfaces in the Versos
"Lead Agentic Engineer" role: AI-assisted **support triage**, an AI **media
enrichment** pipeline over uploaded assets, and an automated **quality auditor** —
all on one substrate (FastAPI + Postgres + S3 + LangGraph), with a human-in-the-loop
autonomy seam baked into the data model.

## The one-sentence story

> "I didn't build three demos — I built one small agent-ops platform where agents
> operate at different autonomy levels (suggest → human-approved → auto), and the
> auditor is the trust layer that justifies promoting one of them."

## Architecture

```
                 ┌──────────────── FastAPI (async) ────────────────┐
                 │  /tickets   /assets   /audit   /health           │
                 └───┬───────────────┬───────────────┬─────────────┘
                     │               │               │
        Option A     │   Option B    │               │ trust layer
   supervisor +      │   parallel    │               │
   specialists       │   pipeline    │               │
        ▼            │      ▼        │               ▼
   Triage agent      │  Enrichment   │          Quality auditor
   (LangGraph)       │  (LangGraph)  │          (rules + LLM)
        │            │      │        │               │
        └────────────┴──────┴────────┴───────────────┘
                          │
              Postgres (business records + workflow state)
              S3 / LocalStack (raw media + transcript blobs)
              LangSmith / OTel (agent telemetry — NOT in Postgres)
```

### Two multi-agent patterns (deliberately different)
- **Support triage = supervisor + specialists.** One orchestrator routes a ticket
  to a classifier, a summarizer, and a remediation drafter, then writes results back.
- **Media enrichment = parallel pipeline.** Transcription ‖ language detection ‖
  keyword extraction run concurrently, then a reducer merges into one asset record.

### Where data lives (a deliberate design call)
Postgres holds **business records and workflow state** — facts the company would
care about even if no agent existed. Agent **telemetry** (tokens, latency, traces,
prompt versions, intermediate reasoning) goes to LangSmith/OTel, *not* relational
tables. That separation is intentional and a talking point.

### The autonomy seam
`support_tickets.triage_mode` ∈ {suggest, approved, auto} and `status` model the
graduation path. An agent earns promotion as the auditor accumulates evidence it
behaves; a kill switch demotes it back to `suggest`.

## Schema
4 tables — see [`sql/schema.sql`](sql/schema.sql). Indexes chosen for real worklist
queries (e.g. `support_tickets(status, created_at DESC)` for "open tickets, newest
first"; `audit_findings(resolved, severity, created_at DESC)` for "open findings,
worst first").

## Run it locally

```bash
docker compose up -d            # Postgres (schema auto-loads) + LocalStack (S3)
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8077
# open http://localhost:8077/docs
```

## Interview prep
Full prep materials live in [`docs/`](docs/00_START_HERE.md): architecture +
design decisions, file-by-file code walkthrough, a Q&A bank, and a concepts glossary.

## Build status / roadmap
- [x] **Step 1** — Postgres schema + indexes
- [x] **Step 2** — FastAPI skeleton (CRUD for tickets/assets/audit, agent endpoints stubbed)
- [x] **Step 3** — Support triage agent (LangGraph supervisor + specialists; real
      NVIDIA NIM calls behind a provider seam; promotion policy + regression tests)
- [ ] **Step 4** — Media enrichment pipeline (S3 + parallel LangGraph)
- [ ] **Step 5** — Quality auditor (rules + LLM explanation)
- [ ] **Step 6** — Observability + evals (LangSmith; NeMo/AIQ discussion layer)
```
