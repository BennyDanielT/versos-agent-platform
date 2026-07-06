# Versos Ops Console (Next.js)

A human-in-the-loop console over the FastAPI backend. It visualizes the **trust layer** across
all three agents — what each decided, *why* the autonomy gate landed there, and where the human
stays in control — plus a live **Simulation** panel that drives real data into the system.

Next.js 16 (App Router) · Tailwind v4 · TanStack Query · shadcn-style hand-built component kit
(no CLI/Radix, zero extra deps) · light/dark theme.

## Run

```bash
# 1. backend (from repo root) — see root README for full setup
uvicorn backend.main:app --port 8090

# 2. frontend
cd frontend
npm install
npm run dev                            # http://localhost:3000
```

`BACKEND_URL` (server env, default `http://localhost:8090`) is where the proxy forwards `/api/*`.

## Screens

| Route | Backend | What it shows |
|-------|---------|---------------|
| `/` **Dashboard** | reads all verticals | KPI tiles + recent activity across triage / index / pipeline |
| `/copilot` **Copilot** | `POST /triage` | Triage a complaint; the **autonomy decision + why** is the hero |
| `/review` **Review queue** | `GET /tickets`, `POST /tickets/{id}/review` | Human approve/reject of triage decisions |
| `/index` **Index Hygiene** | `/index/*` | Scan findings (risk + mode badges), approve, apply; efficacy tiles |
| `/pipeline` **Pipeline Healer** | `/pipeline/*` | Jobs, heal-all/one, and the LangGraph decision-log trace |
| `/policy` **Policy & Metrics** | `GET/PUT /policy`, `GET /metrics` | Edit the human-owned policy table; segment metrics |
| `/simulation` **Simulation** | `/sim/*` | Start/Stop + live sliders (speed, per-vertical rates, toggles) + live stats |

## Structure

- `app/` — one folder per route (`page.tsx`), plus `layout.tsx` (nav shell), `providers.tsx`
  (TanStack Query), and `api/[...path]/route.ts` (the server-side proxy).
- `components/ui.tsx` — the kit: `Card`, `Button`, badges (`ModeBadge`/`SeverityBadge`/`RiskBadge`/
  `OutcomeBadge`), `Table`, `Stat`, `Confidence`, `Code`, and loading/error/empty states.
- `components/nav.tsx` — active-aware top nav. `components/theme-toggle.tsx` — light/dark.
- `lib/api.ts` — one typed client (every call routes through the proxy).
- `lib/types.ts` — types mirroring the FastAPI contract.

## Design decisions (say these out loud)

- **Server-side proxy** — the browser only talks to Next.js, which forwards to the backend.
  Keeps the backend URL off the client, sidesteps CORS, natural seam for auth later.
- **TanStack Query for all server state** — caching + explicit loading/error/empty states, not
  hand-rolled `useEffect` fetches. The Simulation page polls `/sim/status` on an interval.
- **The autonomy decision is the hero** — `recommended_mode` + `mode_reason` in plain English,
  traceable to confidence vs the policy bar. The model assesses; **code** enforces the policy.
- **Simulation feeds the real pipeline** — sliders change the config live (no restart); the
  engine creates genuine upstream conditions, so every logged decision is real.
- **shadcn-style, hand-built kit** — same aesthetic, no CLI/Radix, so there's nothing extra to
  install and the Docker image stays lean. Token-based theme drives light/dark.

## Notes

- Types are hand-written but faithful to the contract; in a longer project I'd generate them
  from `/openapi.json` via `openapi-typescript`.
- `output: "standalone"` (see `next.config.ts`) is set for the containerized deploy.
- `AGENTS.md` here flags that this is a modified Next.js 16 — check `node_modules/next/dist/docs/`
  before using unfamiliar Next APIs.
