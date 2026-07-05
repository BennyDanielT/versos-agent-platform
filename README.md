# versos-agent-platform

A compact **agent-ops platform** built on **Python + NVIDIA NeMo Agent Toolkit (NAT) + Postgres** —
three agents (support **triage**, **index-hygiene**, **pipeline-healer**) that each graduate from
**suggest → human-approved → autonomous** as evidence accumulates, with observability, evals, and
guardrails as first-class concerns. A Next.js ops console and a controllable live simulator sit on top.

Built as interview prep for a Lead Agentic Engineer role, but it's a real, runnable system (no mocks).

## What's here
- **`nat_sandbox/severity_lab/`** — the NAT package: the `triage_ticket` tool (structured output +
  policy-as-data autonomy + layered guardrails), the `index_hygiene` scan, the `pipeline_healer`
  LangGraph workflow, a custom evaluator, the offline/online eval SQL, and the scheduled jobs.
- **`backend/`** — a layered FastAPI app (routers / services / core) that embeds the NAT workflows
  and exposes all three verticals + a controllable live **simulator** (`/sim/*`).
- **`frontend/`** — a Next.js + Tailwind ops console: dashboard, Copilot (triage), Index Hygiene,
  Pipeline Healer, Policy/Metrics, and a Simulation control panel.
- **`interview-prep/`** — the design docs, build runbook, Q&A bank, and architecture diagrams.
- **`docs/nemo/`** — a NeMo Agent Toolkit primer.
- **`DEPLOY-AWS.md`** — deploy to AWS (App Runner + RDS) for a public URL.

## The three verticals (one shared spine)
Each *assesses* → a human-owned **policy gate** (code, not the model) decides autonomy → every
decision is **logged** → destructive actions are held for a human.

| Vertical | Needs | Endpoint |
|---|---|---|
| **Triage** (support Copilot) | Postgres + `NVIDIA_API_KEY` | `POST /triage`, `POST /ask` |
| **Index Hygiene** (DB optimization) | Postgres only | `/index/*` |
| **Pipeline Healer** (self-healing jobs) | Postgres only | `/pipeline/*` |

## The idea in one breath
A tool assesses each ticket (structured output) → code (not the LLM) decides autonomy from a
human-owned policy table → every decision is logged → offline (`nat eval` golden set) and online
(SQL views over dev reviews + CSAT) evals prove behaviour → a human promotes a segment to more
autonomy only when the evidence clears the bar → a kill switch and per-stage guardrails bound the
blast radius.

See **[interview-prep/README.md](interview-prep/README.md)** for the full walkthrough and diagrams.

## Run it locally (full stack)

**Prerequisites:** Docker + Docker Compose, Python 3.11–3.13, Node.js 20+ (22 recommended).

### 0. Secrets
```bash
cp .env.example .env
# edit .env → set NVIDIA_API_KEY=... (free at https://build.nvidia.com)
# Needed for Triage/Copilot only; Index Hygiene + Pipeline Healer run without it.
```
> Secrets live in `.env` (git-ignored). Never commit real keys.

### 1. Database (Postgres + Adminer)
```bash
docker compose up -d
```
Postgres on `:5432`; Adminer DB browser on http://localhost:8081 (System=PostgreSQL,
Server=`postgres`, User/Pass/DB=`versos`). All three schemas (triage, index-hygiene,
pipeline-healer — incl. seeded demo jobs) load automatically on first boot.

### 2. Backend (FastAPI on :8090)
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt                        # or requirements-deploy.txt for the slim set
pip install -e nat_sandbox/severity_lab
uvicorn backend.main:app --port 8090 --reload
```
Check: `curl localhost:8090/health` → `{"status":"ok"}`. API docs at http://localhost:8090/docs.

### 3. Frontend (Next.js on :3000)
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000**. The frontend proxies `/api/*` to the backend
(`BACKEND_URL`, default `http://localhost:8090`) — no CORS setup needed.

### 4. Simulator (live, controllable data feed)
No separate process — the engine runs inside the backend. Drive it from the UI:

- Open **http://localhost:3000/simulation** → set the sliders → **Start**.
- Then watch the **Dashboard** / vertical pages fill with real decisions.

Or via the API directly:
```bash
curl -X POST localhost:8090/sim/start -H 'content-type: application/json' \
  -d '{"speed":2,"jobs_per_min":40,"triage_per_min":4}'
curl localhost:8090/sim/status            # live stats
curl -X POST localhost:8090/sim/config -H 'content-type: application/json' -d '{"speed":5}'
curl -X POST localhost:8090/sim/stop
```
It creates the **real** upstream conditions each agent reacts to (failing jobs, index
problems, customer complaints) — it does not insert fake log rows. Triage generation needs
`NVIDIA_API_KEY`; toggle it off to run Index + Pipeline at zero cost.

### Try a single agent from the CLI (optional)
```bash
nat run --config_file nat_sandbox/severity_lab/src/severity_lab/configs/index_hygiene.yml --input "scan"
nat run --config_file nat_sandbox/severity_lab/src/severity_lab/configs/pipeline_healer.yml --input ""
nat run --config_file nat_sandbox/severity_lab/src/severity_lab/configs/triage_observed.yml --input "My export has no audio"
```

## Deploy to a public URL
See **[DEPLOY-AWS.md](DEPLOY-AWS.md)** — containerized backend + frontend on AWS App Runner
with an RDS Postgres, via AWS CloudShell.
