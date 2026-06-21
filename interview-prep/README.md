# Interview prep — Versos Lead Agentic Engineer

Living docs for the 4-hour final round (3h build + 1h present). Stack: **Python + NeMo Agent
Toolkit (NAT) + Postgres**.

## Read in this order
1. [JOB_DESCRIPTION.md](JOB_DESCRIPTION.md) — the actual role + what they value.
2. [interview-step-by-step.md](interview-step-by-step.md) — the runbook: **DAY-OF STRATEGY**
   (reusable spine, first-30-minutes, JD-alignment cheat-sheet), target architecture, phase-by-phase
   build with commands + "why" + success checks.
3. [interview-prompts.md](interview-prompts.md) — the prompts to paste into Claude Code, in order.
4. [my-technical-qa.md](my-technical-qa.md) — Q&A bank (Q1–Q48) to defend every decision.
5. [TODO.md](TODO.md) — backlog + open questions to verify on the box.

## Diagrams
- [01 — Deployment topology](diagrams/01-deployment-topology.svg) — where everything runs (ECS/Fargate, RDS, NIM, Phoenix, EventBridge).
- [02 — Request architecture](diagrams/02-request-architecture.svg) — the call stack for one triage (frontend → backend → NAT tool internals → stores).
- [03 — Guardrails + evals trust layer](diagrams/03-guardrails-evals-trust-layer.svg) — where each guardrail and eval plugs into the pipeline.

> The working code lives at the repo root: `nat_sandbox/severity_lab/` (NAT package) and
> `backend/` (FastAPI). The sim probably isn't customer-support triage — the **reusable spine**
> in the runbook re-skins onto whatever it is.
