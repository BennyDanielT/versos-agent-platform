# Concepts Glossary

Plain-English definitions of every term in this project, so you can explain any of
them cold. Ordered roughly from foundational → advanced.

## Web / backend

**FastAPI** — a modern async Python web framework. You declare endpoints as
functions; it handles validation (via Pydantic), dependency injection, and
auto-generates Swagger docs at `/docs`.

**async / event loop** — Python's way of handling many requests on one thread by
switching tasks whenever one is *waiting* on I/O (DB, network, model). Critical here
because every agent request waits on both the DB and the LLM.

**`run_in_threadpool`** — runs a *synchronous* function (like LangGraph's `.invoke`)
on a background thread so it doesn't block the async event loop.

**Pydantic** — data validation library. You define a class with typed fields; it
validates/coerces input and serializes output. Used for both API contracts
(`schemas.py`) and structured LLM outputs.

**Dependency injection (`Depends`)** — FastAPI passes shared resources (like a DB
session) into endpoints automatically, and handles their setup/teardown.

## Database

**Postgres** — relational database. Stores our business records.

**SQLAlchemy (2.0, async)** — Python ORM: map Python classes to tables, write
queries in Python. The async flavor pairs with `asyncpg`.

**asyncpg** — a fast async Postgres driver.

**ORM vs DDL** — DDL (`schema.sql`) is the raw `CREATE TABLE` SQL, the source of
truth for structure + indexes. The ORM (`models.py`) is the Python mirror the app
reads/writes through.

**Composite index** — an index on multiple columns, e.g. `(status, created_at DESC)`.
Order matters: it accelerates queries that filter on the leading column(s) and sort
on the next — here, `WHERE status=? ORDER BY created_at DESC` needs no sort step.

**Transaction** — a group of DB operations that commit together or roll back
together. Our `get_session` dependency makes one transaction per request.

## Storage

**S3** — AWS object storage (files/blobs by key). We store raw media + transcript
blobs there.

**LocalStack** — runs AWS APIs (including S3) locally in Docker, so the same boto3
code works locally and against real AWS.

**boto3** — the AWS SDK for Python.

## Agents / LLM

**LLM** — large language model (e.g. Llama via NVIDIA NIM). Takes text in, produces
text (or structured JSON) out.

**NVIDIA NIM** — NVIDIA Inference Microservices: hosted, OpenAI-compatible model
endpoints (`build.nvidia.com` / `integrate.api.nvidia.com`). `ChatNVIDIA` is the
LangChain client for it.

**LangChain** — a library of abstractions over LLMs: prompts, model interfaces,
structured-output coercion, tools, retrieval.

**LangGraph** — LangChain's framework for **stateful, multi-step agent workflows**
as a graph of nodes. You define nodes (functions), edges (flow), and a shared state;
it runs them and threads the state through. Gives you traceability and replay.

**Node / edge / state** — a *node* is one step (a function); an *edge* connects steps
(flow/order); *state* is the typed dict carried through and updated by each node.

**Fan-out / fan-in** — fan-out = one node branches to several that can run
independently; fan-in (a "reduce"/join) = several branches converge into one node.
Triage fans out to summarize‖remediate then fans into `decide`.

**Structured output** — forcing the model to return data matching a schema (a
Pydantic class) instead of free text. Makes results diffable, scorable, gateable.

**Provider seam / abstraction** — our `get_structured_llm(schema)` interface. Code
depends on the seam, not on a specific model vendor, so backends are swappable.

**Supervisor + specialists** — a multi-agent pattern: one orchestrator routes work
to single-responsibility sub-agents and combines results. (Triage.)

**Parallel pipeline** — independent agents run concurrently on the same input; a
reducer merges outputs. (Enrichment, Step 4.)

## Trust / ops

**Autonomy levels (suggest / approved / auto)** — how much an agent is trusted to
act: recommend only / act with human OK / act unsupervised.

**Promotion (graduation)** — moving an agent up the autonomy ladder as evidence
shows it's safe; demotion is the reverse.

**Blast radius** — how much damage a wrong action could do. Controlled by holding
high-impact actions (critical tickets) behind humans and scoping autonomy to narrow
slices.

**Kill switch** — an instant control to demote/disable agents (e.g. flip everything
to suggest).

**Eval / eval harness** — a repeatable way to score agent quality (e.g.
classification accuracy, remediation usefulness) against known-good data.

**Regression test** — an automated test that fails if previously-correct behavior
breaks; here, the promotion-policy tests guard the safety invariants.

**Shadow mode** — running an agent's recommendations alongside real human actions
without acting, to gather evidence before promotion.

**LangSmith** — LangChain's observability product: traces, inputs/outputs, latency,
cost per run. Where agent *telemetry* lives (not Postgres).

**OpenTelemetry (OTel)** — vendor-neutral standard for traces/metrics/logs.

**NeMo Toolkit / NVIDIA AIQ (AgentIQ)** — NVIDIA's agent/eval/observability tooling;
mentioned as the "productionized agent platform" discussion layer for later.
```
