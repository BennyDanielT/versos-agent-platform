# versos-agent-platform

A compact **agent-ops platform** built on **Python + NVIDIA NeMo Agent Toolkit (NAT) + Postgres** —
a customer-support triage agent that graduates from **suggest → human-approved → autonomous** as
evidence accumulates, with observability, evals, and guardrails as first-class concerns.

Built as interview prep for a Lead Agentic Engineer role, but it's a real, runnable system (no mocks).

## What's here
- **`nat_sandbox/severity_lab/`** — the NAT package: the `triage_ticket` tool (structured output +
  policy-as-data autonomy + layered guardrails), a custom evaluator, the offline/online eval SQL,
  and the scheduled `promotion_job` / `monitor_job`.
- **`backend/`** — a layered FastAPI app (routers / services / core) that embeds the NAT workflow.
- **`interview-prep/`** — the design docs, build runbook, Q&A bank, and architecture diagrams.
- **`docs/nemo/`** — a NeMo Agent Toolkit primer.

## The idea in one breath
A tool assesses each ticket (structured output) → code (not the LLM) decides autonomy from a
human-owned policy table → every decision is logged → offline (`nat eval` golden set) and online
(SQL views over dev reviews + CSAT) evals prove behaviour → a human promotes a segment to more
autonomy only when the evidence clears the bar → a kill switch and per-stage guardrails bound the
blast radius.

See **[interview-prep/README.md](interview-prep/README.md)** for the full walkthrough and diagrams.

## Run (local)
```bash
docker compose up -d                      # Postgres (+ Adminer on :8081)
pip install -r requirements.txt
pip install -e nat_sandbox/severity_lab
# put NVIDIA_API_KEY=... in a .env (git-ignored)
nat run --config_file nat_sandbox/severity_lab/src/severity_lab/configs/triage_observed.yml --input "My export has no audio"
```

> Secrets live in `.env` (git-ignored). Never commit real keys.
