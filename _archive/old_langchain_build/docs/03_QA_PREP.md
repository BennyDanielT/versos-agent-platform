# Interview Q&A Prep

Anticipated questions with crisp answers. Practice saying these out loud. Each has
a **short answer** (lead with this) and a **follow-up** (depth if they probe).

---

## Project framing

**Q: Walk me through what you built.**
> Short: "A small agent-ops platform with three surfaces — support triage, media
> enrichment, and a quality auditor — on FastAPI + Postgres + S3 + LangGraph. The
> through-line is an autonomy model: agents run at suggest, approved, or auto, and
> promotion is governed by evidence. Triage is fully built; enrichment and the
> auditor are the next two steps."
> Follow-up: walk the triage request lifecycle (see 01_ARCHITECTURE §4).

**Q: Why this project / why these features?**
> "They map to Versos' stated surfaces — customer support, media pipelines, data
> quality. I deliberately kept it small but representative so one trust story could
> govern all three, instead of three disconnected demos."

---

## The autonomy model (lead with this — it's your differentiator)

**Q: What do you mean by 'autonomy levels'?**
> "Every agent action has a mode: **suggest** (writes a recommendation, human does
> everything), **approved** (acts only after a human OKs), **auto** (acts
> unsupervised). It's a column on the ticket, so it's queryable and auditable. An
> agent graduates from suggest → approved → auto as evidence accumulates that it's
> safe."

**Q: How does an agent decide whether it's allowed to act?**
> "It doesn't decide to act — it emits a *recommended* mode. The `decide` node maps
> confidence + severity to a recommendation. Critical severity is hard-pinned to
> suggest no matter the confidence — that's a blast-radius control. Honoring the
> recommendation is a separate policy step outside the agent."

**Q: How would you actually promote an agent to autonomous in production?**
> "Shadow mode first: run it suggest-only and log its recommendation next to what
> the human actually did. When agreement on a slice (say, low-severity media issues)
> clears a bar over enough volume, promote *that slice* to approved, then auto. Keep
> a kill switch that demotes everything to suggest instantly. The auditor and the
> eval suite are what make that bar measurable."

---

## Data & schema

**Q: Why not store agent actions/interactions in Postgres?**
> "Because that's telemetry, not business data. Token counts, latencies, traces,
> prompt versions, intermediate reasoning — those belong in LangSmith / OpenTelemetry.
> Postgres holds facts the business cares about even if no agent existed: the ticket,
> its category, who approved it. I considered an `agent_actions` table and rejected
> it on purpose."

**Q: Talk me through your indexes.**
> "Each index serves a real worklist query. `support_tickets(status, created_at DESC)`
> serves 'open tickets, newest first' with no extra sort — the composite order matches
> the WHERE + ORDER BY. Same logic for `audit_findings(resolved, severity,
> created_at DESC)` = 'open findings, worst first.'"

**Q: Why async SQLAlchemy?**
> "Every request waits on I/O twice — the database and the model. With sync drivers
> I'd block the event loop during those waits and tank concurrency. asyncpg + async
> sessions keep the server handling other requests while an agent is mid-run."

---

## Orchestration & agents

**Q: Why LangGraph instead of just chaining function calls?**
> "Because I want the run to be a first-class object I can trace, replay, and test.
> LangGraph gives explicit nodes and a typed state that's threaded through — so each
> node is unit-testable, the graph is inspectable, and I can snapshot/replay a run.
> A bare function chain gives none of that for free."

**Q: Supervisor+specialists vs parallel pipeline — when each?**
> "Supervisor when steps depend on each other or need routing — triage classifies
> first because severity feeds remediation and the decision. Parallel when steps are
> independent and latency matters — enrichment runs transcription, language
> detection, and keywords concurrently because none needs the others' output."

**Q: Why structured outputs?**
> "Free text isn't auditable or evaluable. Typed outputs you can diff, score, and
> gate on. They're the contract that lets the trust layer exist at all."

**Q: Why NVIDIA NIM, and what if they ask about vendor lock-in?**
> "NIM aligns with Versos' NVIDIA stack and is OpenAI-compatible. The triage agent
> makes real NIM calls — but the orchestration doesn't import `ChatNVIDIA` directly,
> it goes through a provider seam (`get_structured_llm`). There's one backend today;
> the seam exists so swapping to OpenAI or a local model is a change in one file, not
> a rewrite. I kept the abstraction thin and honest — a seam, not a pile of pretend
> backends I'd have to maintain."

**Q: How do you keep tests deterministic if the agent calls a real model?**
> "I split the system at the seam. The safety-critical logic — the promotion policy
> in `decide()` — is pure functions with no model in the loop, so it gets fast,
> deterministic unit tests. The model-dependent quality (classification accuracy,
> remediation usefulness) is measured separately by an eval suite against NIM with a
> fixed dataset (Step 6). I don't fake the model to make tests pass; I test the
> deterministic parts deterministically and *evaluate* the probabilistic parts."

---

## Trust, safety, operations

**Q: How do you know an agent is behaving well enough to trust?**
> "Instrumentation, not gut feel. Structured outputs logged against ground truth,
> an eval suite scoring classification accuracy and remediation quality, traces in
> LangSmith, and regression tests on the safety-critical policy. Autonomy advances
> only as fast as that evidence — and the proof is itself a deliverable."

**Q: What's your blast-radius / kill-switch story?**
> "Today: critical severity is hard-held to suggest no matter what the model says.
> The design intent is a per-agent mode flag a human can slam back to suggest
> instantly, plus scoping autonomy to narrow slices so a bad agent can only touch a
> small surface."

**Q: What did you test, and why that?**
> "I unit-tested the promotion policy — the 'when can an agent act' logic — because
> it's the part where a mistake is most expensive. Five deterministic tests, the key
> one being 'critical never auto-resolves even at 0.99 confidence.' That file is part
> of the trust layer, not an afterthought."

---

## Honesty / self-critique (have these ready — they signal seniority)

**Q: What are the limitations / what would you do next?**
> "Enrichment and the auditor are still stubs (501s) — Steps 4 and 5. The triage
> agent calls real NIM, but there's no eval harness yet to put a number on its
> accuracy (Step 6), and no LangSmith tracing wired. There's also no auth, no rate
> limiting, and no retries/backoff on model calls yet. I built the spine first on
> purpose and I'm honest about what's stubbed."

**Q: A bug / gotcha you hit?**
> "LangGraph's `.invoke` is synchronous, but my FastAPI endpoint is async. Calling it
> directly would block the event loop for the whole model round-trip and serialize
> every request. I caught it reasoning about concurrency and offloaded the graph run
> with `run_in_threadpool`, so the server keeps serving while an agent is mid-flight.
> It's the kind of thing that doesn't fail in a demo but quietly destroys throughput
> under load." 
> (Also a small one: I fumbled Postgres identity syntax — `BIGGENERATED` instead of
> `BIGINT GENERATED ALWAYS AS IDENTITY` — and caught it because the schema failed to
> load in Docker on boot. Cheap to catch *because* the DDL runs at container start.)

**Q: What would break at scale?**
> "Synchronous `.invoke` in a threadpool is fine for low volume; at scale triage
> should be a queue + workers (Celery/Arq/SQS) so model latency doesn't tie up web
> workers, with idempotency keys and retries. The DB design and provider seam already
> support that — it's an execution-substrate change, not a redesign."
```
