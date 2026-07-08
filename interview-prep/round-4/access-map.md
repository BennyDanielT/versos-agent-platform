# Access map — Versos agent platform

## 🚀 LIVE ON AWS (share this with Versos)
**https://main.d2z7m08sbque97.amplifyapp.com/**

| Piece | Where | Notes |
|---|---|---|
| Frontend | AWS Amplify (`main` branch, auto-deploys on push) | reads `BACKEND_URL` env var |
| Backend | ECS Fargate behind ALB — `http://versos-alb-1284193883.us-east-1.elb.amazonaws.com` | cluster `versos`, service `versos-backend` |
| Database | RDS Postgres `versos-db` (us-east-1) | schema self-migrates on first boot |
| CI/CD | GitHub Actions → ECR → `ecs update-service --force-new-deployment` | OIDC, no stored AWS keys |

- **Backend health:** `curl http://versos-alb-1284193883.us-east-1.elb.amazonaws.com/health`
- **Swagger:** http://versos-alb-1284193883.us-east-1.elb.amazonaws.com/docs
- **Toggle flags in prod:** the **Settings** page (writes `system_flags` in RDS) — kill switch, `input_rail`, `mask_input`.
- **Seed demo data:** Clients → Simulation → Start (~2-3 min) → Stop. Each complaint = a real LLM call.
- **Teardown (stop the meter):** see `DEPLOY-AWS.md` → Teardown.

> The ALB is plain HTTP on purpose: the Next.js proxy calls it **server-side**, so the browser
> never talks to it directly and there's no mixed-content problem.

---

## Local access map

How to reach every surface when running the stack locally. Full stack:
`Next.js :3000 → proxy → FastAPI :8090 → Postgres (Adminer :8081)`.

## Bring it up
```bash
docker compose up -d                                   # Postgres (+ Adminer on :8081)
# .env must have a real NVIDIA_API_KEY=nvapi-...  (OneDrive can blank it — re-check)
.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8090   # backend
cd frontend && npm run dev                             # frontend on :3000
```

## The app (start here)
**http://localhost:3000** — the Next.js ops console.

| Page | URL | What |
|---|---|---|
| Home | http://localhost:3000 | overview / dashboard |
| **Simulation** | http://localhost:3000/simulation | **start/stop + tune the live data simulator** (speed, rates, fail %, auto-heal) — the money page |
| Copilot | http://localhost:3000/copilot | ask / triage surface |
| Review | http://localhost:3000/review | human review queue (approve/reject → drives autonomy) |
| Policy | http://localhost:3000/policy | the autonomy policy tables |
| Index | http://localhost:3000/index | index-hygiene findings + apply |
| Pipeline | http://localhost:3000/pipeline | failed jobs + healer log |

## Supporting tools
- **API + Swagger docs:** http://localhost:8090/docs — every endpoint, clickable "Try it out"
- **Health check:** http://localhost:8090/health → `{"status":"ok"}`
- **DB browser (Adminer):** http://localhost:8081 — System **PostgreSQL**, Server **`postgres`**
  (the compose service name, NOT `localhost`), User/Pass/DB **`versos`**

## Key backend endpoints (also via /docs)
| Method | Path | What |
|---|---|---|
| POST | `/triage` | triage a complaint (LLM) |
| POST | `/ask` | copilot / agent ask |
| POST | `/index/scan` | scan for index findings |
| POST | `/index/apply` | apply an approved finding |
| POST | `/index/findings/{id}/review` | approve/reject a finding |
| POST | `/pipeline/heal` | heal failed jobs (sweep, or one id) |
| GET | `/pipeline/jobs` · `/pipeline/heal-log` | job + heal state |
| GET | `/index/findings` · `/index/metrics` · `/index/policy` | index reads |
| GET | `/metrics` · `/policy` · `/tickets` | triage reads |
| POST | `/sim/start` · `/sim/stop` · `/sim/config` | simulator control |
| GET | `/sim/status` | simulator running-state + live stats |

## Simulator
Runs all three agents against a controllable stream of fake-but-real work (real rows,
real LLM triage, real healing). Tune it on `/simulation` or via `/sim/config`.
- **Stop it** when done — it makes real NIM calls: click stop on `/simulation`, or
  `curl -X POST http://localhost:8090/sim/stop`. Free NIM endpoint ≈ 40 req/min.

## Gotchas
- **`.env` NVIDIA_API_KEY**: OneDrive can sync a blank `.env` from another machine. If triage
  returns `401 Unauthorized` / "Triage failed", the key is blank — restore it. On AWS, set it as a
  real env var (not from `.env`).
- **Adminer Server**: use `postgres`, not `localhost` (localhost inside the container is Adminer itself).
- **Fresh DB → 0 index findings**: the observation-window guard means newborn indexes aren't flagged.
  Seed a couple of unused indexes (or let the sim's index-ops run) so `/index` isn't empty:
  ```sql
  CREATE INDEX idx_demo_unused_summary ON triage_log (summary);
  INSERT INTO index_seen (object_table, object_index, first_seen_at)
    VALUES ('triage_log','idx_demo_unused_summary', now() - interval '10 days')
    ON CONFLICT (object_table,object_index) DO UPDATE SET first_seen_at = EXCLUDED.first_seen_at;
  ```
- **Restart backend after changing `.env`**: it loads env at startup (no `--reload` = kill + rerun).
