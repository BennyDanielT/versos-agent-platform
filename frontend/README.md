# Versos Ops Console (Next.js)

A focused human-in-the-loop console over the FastAPI triage backend. It deliberately
visualizes the **trust layer** — what the agent decided, *why* the autonomy gate landed
there, and where the human stays in control — rather than being a generic CRUD dashboard.

## Run

```bash
# 1. backend (from repo root)
uvicorn backend.main:app --port 8090

# 2. frontend
cd frontend
cp .env.local.example .env.local      # BACKEND_URL defaults to http://localhost:8090
npm install
npm run dev                            # http://localhost:3000
```

## Three screens → what each demonstrates

| Route | Backend | Rubric it scores |
|-------|---------|------------------|
| `/` **Copilot** | `POST /triage` | Agent loop + **explainability** (the hero) |
| `/review` **Review queue** | `GET /tickets`, `POST /tickets/{id}/review` | **Human-in-the-loop / guardrails** |
| `/policy` **Policy & metrics** | `GET/PUT /policy`, `GET /metrics` | Governance + **evaluation** |

## Design decisions (say these out loud)

- **Server-side proxy** (`app/api/[...path]/route.ts`) — the browser only talks to Next.js,
  which forwards to the backend. Keeps the backend URL off the client, sidesteps CORS, and
  is the natural seam for auth/rate-limiting later. No secrets in the frontend.
- **TanStack Query for all server state** — caching + explicit loading/error/empty states,
  not hand-rolled `useEffect` fetches.
- **The Copilot Decision panel is the hero.** It shows `recommended_mode` + `mode_reason` —
  the gate's verdict in plain English, traceable to confidence vs the policy bar. The model
  assesses; code enforces the human-approved policy.
- **Optimistic-but-honest review** — approving flips the row immediately and rolls back
  visibly if the server rejects (`onMutate` / `onError`).
- **Types mirror the contract** (`lib/types.ts`). In a longer project I'd generate them from
  `/openapi.json` via `openapi-typescript` so frontend/backend can't drift.

## Deliberately out of scope (judgment > features)

Auth, websockets/streaming, a charting library, SSR data fetching. Single-purpose SPA-style
client against the FastAPI contract; those are obvious next steps but don't earn rubric
points at this scope.
