# TODO — Versos final-round prep

Running backlog of things to **do** and to **learn**. Newest context at top of each
section; check items off as we go. (Interview = 4h: 3h build on their simulation +
1h present. Stack: Python + NeMo Agent Toolkit + Postgres. Win on observability,
evals, guardrails.)

## Now / in progress
- [x] Install NeMo Agent Toolkit in the venv and verify the primer hands-on
      (installed v1.8.0; ran a real custom function via `nat run`; corrected primer).
- [ ] Get NVIDIA_API_KEY (build.nvidia.com) so we can run LLM-backed NAT workflows.

## Learn (ordered)
- [~] **NeMo Agent Toolkit basics** — primitives + custom function + `nat run`
      verified hands-on (nat_sandbox/versos_hello). Still to drill: builder.get_llm
      with a real NIM call, observability via otelcollector, `nat eval` harness,
      guardrail patterns. (Primer: docs/nemo/00_NEMO_PRIMER.md.)
- [ ] **Port the practice project from LangChain/LangGraph to NeMo Agent Toolkit**
      — triage specialists → registered functions; provider seam → builder.get_llm;
      decide() policy → registered function (still unit-tested); telemetry → config.
- [ ] **Build an MVP on NAT** end-to-end (agents + Postgres + observability + evals +
      guardrails) as a dry run of the 3-hour sprint.
- [ ] **Learn LangChain + LangGraph basics** — AFTER NeMo + porting + MVP. Understand
      what NAT wraps: chains, runnables, tools, structured output (LangChain) and
      StateGraph/nodes/edges/state (LangGraph). Goal: explain the layer NAT sits on.
- [ ] **Learn how the AIQ Blueprint works** — NVIDIA's reference blueprint built on the
      toolkit (docs.nvidia.com/aiq-blueprint). Understand its structure and how it
      extends NAT (e.g. adding tools/workflows), to borrow proven patterns.

## Build sequence (agreed order before the interview)
- [x] Triage agent: tool + structured output + Postgres policy/log
- [x] Human-review → metrics → policy-promotion loop (review_ticket, segment_metrics view)
- [x] **Observability** (Phoenix via otelcollector OTLP HTTP @ 6006/v1/traces; traces land in `default` project)
- [x] **Evals** — `nat eval` + custom `severity_accuracy` evaluator (scores the autonomy-gating
      field); golden set (10 cases) → 0.70, misses all under-rate severity. Online accept-rate via
      segment_metrics. TODO later: calibration script (raw/calibrated conf, ECE, isotonic).
- [ ] **Guardrails** (autonomy caps ✓, approval gate ✓, kill switch; note NeMo Guardrails)
- [~] **API integration** — production-grade LAYERED FastAPI backend DONE (backend/: main +
      core/config + db + schemas + services/ + routers/). Reads via asyncpg services, triage/ask
      via NAT in-process (isolated in nat_service), review/policy via SQL, CORS. TODO: Next.js UI + containerize.
- [ ] **Index-hygiene agent** (deterministic pipeline: scan → find missing indexes → propose → apply)
- [ ] **Pipeline self-healer agent** (agent workflow: detect broken job → diagnose → fix, path varies)

## Practice / present
- [ ] Mock 3-hour build sprint against a stand-in simulation
- [ ] 1-hour presentation script + mock Q&A (reuse docs/03_QA_PREP.md)
- [ ] Fold benny's own dev/presentation notes into the build playbook

## Open questions / verify on the day
- [ ] Exact NAT version + available components on the interview machine
- [ ] Whether Phoenix/telemetry extras are preinstalled there
- [ ] Available NIM model names for their NVIDIA_API_KEY
- [ ] Whether installed NAT exposes any first-class guardrail component

## Done
- [x] Postgres schema + indexes (Step 1)
- [x] FastAPI skeleton (Step 2)
- [x] LangGraph triage agent + promotion policy + tests (Step 3)
- [x] Switch model layer to real NVIDIA NIM (no fakes)
- [x] Interview prep docs (architecture, walkthrough, Q&A, glossary)
- [x] NeMo Agent Toolkit primer researched + written
