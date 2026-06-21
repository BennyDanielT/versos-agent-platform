# Code Walkthrough

A file-by-file tour. For each file: what it is, why it exists, and the line an
interviewer might point at.

## Project layout

```
versos-platform/
├── docker-compose.yml          infra: Postgres + LocalStack (S3)
├── requirements.txt
├── .env.example                config template
├── sql/schema.sql              DDL + indexes (source of truth for the DB)
├── app/
│   ├── config.py               typed settings (pydantic-settings)
│   ├── db.py                   async engine + session dependency
│   ├── models.py               SQLAlchemy ORM (4 tables)
│   ├── schemas.py              Pydantic API contracts
│   ├── main.py                 FastAPI app + lifespan
│   ├── routers/
│   │   ├── tickets.py          /tickets  (+ triage endpoint)
│   │   ├── assets.py           /assets   (+ enrich stub)
│   │   └── audit.py            /audit    (+ run stub)
│   └── agents/
│       ├── llm.py              PROVIDER SEAM: real NVIDIA NIM (swappable)
│       └── triage/
│           ├── schemas.py      structured outputs per specialist
│           ├── state.py        TriageState (graph state)
│           ├── specialists.py  classify / summarize / remediate nodes
│           └── graph.py        supervisor graph + decide() policy
└── tests/
    └── test_promotion_policy.py  regression tests on autonomy gating
```

---

## Infrastructure

### `docker-compose.yml`
Two services: **postgres** (schema auto-loads via the `docker-entrypoint-initdb.d`
mount — DDL runs on first boot of an empty volume) and **localstack** (a local S3
API on :4566). Both have healthchecks.
- *Talking point:* "LocalStack means the exact boto3 code path I run locally also
  works against real AWS S3 — no mocking, no separate code."

### `sql/schema.sql`
Four tables, with comments explaining the business-vs-telemetry split. Indexes are
chosen for **real worklist queries**, not reflexively:
- `support_tickets(status, created_at DESC)` → "open tickets, newest first."
- `support_tickets(customer_id, created_at DESC)` → per-customer history.
- `media_assets(processing_status, created_at)` → pipeline poll "what's pending, oldest first."
- `audit_findings(resolved, severity, created_at DESC)` → "open findings, worst first."
- *Talking point:* a composite index's column order matches the query's filter +
  sort. `(status, created_at DESC)` serves `WHERE status=? ORDER BY created_at DESC`
  without a sort step.

---

## Application core

### `app/config.py`
`pydantic-settings` loads + validates env vars at startup (fail fast if misconfigured).
Holds DB URL, S3/AWS settings, and the NIM config
(`nvidia_api_key`, `nvidia_model`, `nvidia_base_url`).

### `app/db.py`
- Async engine via `create_async_engine` (asyncpg driver).
- `get_session()` is the FastAPI dependency: yields a session, **commits on success,
  rolls back on exception**. One transaction per request.
- *Talking point:* async because every request waits on I/O twice — the DB and the
  model. Blocking the event loop there would crush concurrency.

### `app/models.py`
SQLAlchemy 2.0 typed ORM (`Mapped[...]`). Mirrors the DDL. Relationships:
`MediaAsset` → `transcripts` and `findings` with cascade delete.
- *Talking point:* DDL is the source of truth (it owns the indexes); the ORM is how
  the app reads/writes. In production, Alembic would generate one from the other.

### `app/schemas.py`
Pydantic request/response models, separate from the ORM so the wire format and the
storage format evolve independently. `from_attributes=True` lets us return ORM
objects directly.

### `app/main.py`
Creates the app, includes the three routers, exposes `/health`. The **lifespan**
runs `SELECT 1` on startup so a bad DB connection fails immediately instead of
500ing on the first request.

---

## Routers

### `app/routers/tickets.py`
CRUD + the **triage endpoint**. The endpoint:
1. loads the ticket (404 if missing),
2. runs the graph via `run_in_threadpool(run_triage, ...)` — LangGraph `.invoke`
   is synchronous, so we offload it instead of blocking the async loop,
3. writes the structured results back and sets `status=triaged_suggested`.
- *Talking point:* the endpoint persists a **recommendation** (`triage_mode`). It
  does not auto-resolve. Honoring the recommendation is a separate policy/human step.

### `app/routers/assets.py` and `audit.py`
CRUD is real; the `enrich`/`audit run` endpoints return **501** until Steps 4–5.
Returning an honest 501 (not a fake 200) is deliberate.

---

## The agent layer

### `app/agents/llm.py` — the provider seam (most important file to understand)
- `get_structured_llm(schema)` returns a runnable with `.invoke(prompt) -> schema_instance`.
- **One real backend — NIM:** `ChatNVIDIA(...).with_structured_output(schema)` —
  LangChain coerces the model's tool/JSON output into our Pydantic type. Requires
  `NVIDIA_API_KEY`; if it's missing the call raises a clear error (surfaced as a
  503 by the triage endpoint) rather than degrading silently.
- *Talking point:* "There's one backend today — real NIM — but the specialists and
  graph depend on the seam, never on `ChatNVIDIA` directly. The seam exists so
  swapping to OpenAI or a local model is a change in this one file. I kept the
  abstraction thin and honest: it's a seam, not a pile of pretend alternatives."

### `app/agents/triage/schemas.py`
`Classification`, `Summary`, `Remediation` — Pydantic models = the **structured
output contract**. Structured outputs are what make agents auditable and evaluable:
you can diff them, score them, and gate promotion on them.

### `app/agents/triage/state.py`
`TriageState` (a `TypedDict`). LangGraph threads one state object through the graph;
each node returns a partial update that gets merged. Typed state is what makes runs
traceable, replayable, and snapshottable.

### `app/agents/triage/specialists.py`
Three single-responsibility functions `(state) -> partial state`:
`classify`, `summarize`, `remediate`. Each builds a prompt and calls the seam.
Plain functions → unit-testable in isolation, recomposable by the supervisor.

### `app/agents/triage/graph.py` — the supervisor + the policy
- `build_triage_graph()` wires the `StateGraph`:
  `START → classify → {summarize, remediate} → decide → END`
  (a fan-out after classify, a fan-in at decide). Compiled once via `lru_cache`.
- `decide(state)` is the **autonomy policy** — the safety-critical heart:
  - `severity == "critical"` → **always `suggest`** (blast-radius control).
  - `confidence ≥ 0.85` and severity low/medium → `auto`.
  - `confidence ≥ 0.60` → `approved`.
  - else → `suggest`.
- *Talking point:* the policy is explainable (thresholds, not a black box) and the
  worst-case action is pinned behind a human.

---

## Tests

### `tests/test_promotion_policy.py`
Five deterministic unit tests on `decide()`, isolated from any model. They assert
the safety invariants — most importantly "critical is never auto, even at 0.99
confidence." 
- *Talking point:* "The safety-critical logic gets fast, deterministic regression
  tests so nobody can quietly loosen a threshold. That test file *is* part of the
  trust layer the role asks me to build."
```
