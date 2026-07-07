# Page-by-page guide (round 4 testing)

Explanations + data-provenance notes as we test each console page. Golden rule verified in code:
**the UI has NO hardcoded/mock data** — `frontend/lib/api.ts` is a thin `fetch` wrapper; every value
renders from a real backend endpoint that reads Postgres.

---

## Dashboard (`/`)

The "one screen tells the story" page: three agents on one spine (assess → policy gate → log →
guardrails). Fully data-driven (empty DB → tiles show `—` / "No … yet").

**Top row — 4 KPI tiles** (live count + a browser-derived hint):

| Tile | Value (source) | Hint |
|---|---|---|
| Tickets logged | `triage_log` count (`GET /tickets`) | # awaiting review (`decision` null) |
| Index findings | `index_findings` count (`GET /index/findings`) | # open (`decision` null) |
| Failed jobs | `pipeline_jobs` status=`failed` (`GET /pipeline/jobs`) | total jobs |
| Heal attempts | `heal_log` count (`GET /pipeline/heal-log`) | "logged" |

The awaiting/open/failed numbers are computed client-side by filtering the fetched rows — not extra
hardcoded fields.

**Bottom — 3 vertical cards** (latest 5 rows + "Open →" link):
- Support Triage → recent tickets (complaint + mode badge) → `/copilot`
- Index Hygiene → recent findings (type + table + risk badge) → `/index`
- Pipeline Healer → recent heal attempts (job name + outcome badge) → `/pipeline`

### Data provenance — is it real?
Yes, all from Postgres. Three sources fill the tables:
- **Simulator (main):** triage_log (real LLM calls), new pipeline_jobs, heal_log — fully live.
- **Schema seed (first DB boot):** 5 demo `pipeline_jobs` (4 broken/1 done) + the 3 autonomy policy
  tables (`triage_policy`/`index_policy`/`heal_policy`). Initial state/config, not fake metrics.
- **Manually seeded (this session):** 2 genuinely-unused indexes (`idx_demo_unused_summary` on
  triage_log, `idx_demo_unused_jobname` on pipeline_jobs) + backdated `index_seen`, so the index
  detector has real "dirt" to find. The DETECTION is real; the indexes were planted because a fresh
  DB shows 0 index findings (observation-window guard + no junk indexes).

**Nothing in the UI is faked.** Only real DB rows render. To go 100% simulator-driven: drop the
schema's demo jobs (let the sim create all jobs) and let the sim's index-ops generate index churn
instead of hand-seeding indexes.

---

## How the simulator works (`backend/services/simulator.py`)

**Key idea: the sim makes the MESS; the real agents CLEAN it. The AI lives in the cleaning, not the
mess-making.** The sim does NOT use AI to generate work, and it NEVER writes fake rows into the
decision logs — it creates the real upstream conditions each agent reacts to, so every
`triage_log` / `index_findings` / `heal_log` row is produced by the real agent.

Runs as background asyncio loops inside the FastAPI process; config is a live mutable dataclass
(UI slider changes take effect next tick, no restart).

### The three feeds
| Feed | Sim makes (templates + dice) | Real agent does (writes the log) |
|---|---|---|
| **Triage** | a templated complaint (`_make_complaint`) | runs the REAL triage LLM → `triage_log` |
| **Pipeline** | inserts jobs, rolls dice to fail w/ weighted cause | real healer graph → `heal_log`, updates `pipeline_jobs` |
| **Index** | builds a real `sim.events` table (12k rows) + real bad indexes | real catalog scan → `index_findings` |

### Where the "realism" comes from — templates + weighted dice (NOT AI)
All generators are in `simulator.py` lines ~81–139:
- `_COMPLAINTS` (l.87) — `(category, [templates])` with `{amt}/{plan}/{res}/{action}` slots; pools
  `_PLANS/_AMOUNTS/_RES/_ACTIONS` (l.81) fill them → hundreds of combos from a few templates.
- `_make_complaint` (l.123) — 4% return a prompt-injection probe (exercises the guardrail), else a
  filled template. So triage sees varied tickets + occasional attacks.
- Jobs (l.132) — `_JOB_PREFIXES` × random number; `_ERROR_CLASSES` **weighted** (transient×5,
  stale_lock×3, oom×2, corrupt_input×1) → the healer's path mix looks like a real incident stream.
- Index (l.277–312) — no templates; real SQL creates a 12k-row `sim.events` + duplicate/unused
  indexes + forced seq-scans, then the periodic loop runs the real scan (short unused-window) + heal.

**Trick: templates give variety, weighted dice give distribution.** That combo mimics a real support
inbox + job queue with zero AI in the generator. Once the sim runs, index findings come from its own
`sim.events` churn — the 2 hand-seeded indexes aren't needed anymore.

### Controls (all live, via `/simulation` or `/sim/config`)
`speed` (global multiplier), `triage_per_min` (real LLM calls — keep modest), `jobs_per_min`,
`job_fail_rate`, `auto_heal`, `index_ops_per_min`, `auto_scan`. Bounded by `_MAX_OPEN_JOBS=400`.
Stop it when idle — triage makes real NIM calls (free endpoint ≈ 40 req/min).

---

## Copilot (`/copilot`)

Paste a complaint → the real triage agent assesses it → the autonomy gate (not the model) decides
mode and explains why. Renders the structured output: severity, category, confidence, summary,
developer remediation, PII-masked customer reply, and the autonomy-decision hero (mode + reason).

### Fix (round 4): off-topic / non-support requests were being processed
**Symptom:** "What is Chick-fil-A?" got real developer-remediation steps as if it were a ticket.
**Root cause:** `developer_remediation` is a required schema field + the prompt said "fill every
field", so the LLM invented steps for ANY input. The NeMo input rail (which blocks off-topic) is
DB-flag-gated (default off) and degrades to no-op if `nemoguardrails` isn't in the slim image.
**Fix (deploy-friendly, no new deps):** added an `is_support_request` field to `TriageResult`; the
model marks off-topic/spam/chit-chat as `false`. When false, the tool blanks remediation
(`["Not a customer-support request; no developer action."]`), forces severity `low`, and holds mode
at `suggest` with reason "Off-topic / not a support request; flagged, no action taken." The UI shows
an amber **Off-topic** banner (`is_support_request === false`). Verified: Chick-fil-A / world-cup
queries → flagged; real audio complaint → is_support_request true, 3 remediation steps.
Files: `severity_lab.py` (schema + prompt + relevance gate), `frontend/lib/types.ts`,
`frontend/app/copilot/page.tsx`.

### Still to improve
- **Categorization**: "no audio" sometimes lands `other` instead of `media_quality` — a prompt/taxonomy
  tweak spot, not a correctness bug.

### Guardrails + deploy-image decision (round 4)
Nothing was deleted — the other session split packages into `requirements-deploy.txt` (slim) +
`requirements-extras.txt`. Final posture (defense in depth, deploy-friendly):

| Layer | Runs | Cost / image |
|---|---|---|
| regex injection screen (`_screen_input`) | always-on | free |
| `is_support_request` field | always-on | free (inside the existing triage call) |
| **NeMo input rail** (hard-block off-topic/jailbreak) | **flag-gated** `system_flags.input_rail` (off by default) | shipped in image; +1 LLM call/triage when on |
| **PII masking** (email/phone/card/SSN/IP) | always-on | **dependency-free regex** (no Presidio/spaCy) |

Key calls:
- **Kept the field** — it's the free always-on floor; don't remove it to lean on NeMo (if NeMo is
  stripped/down you'd lose relevance entirely). The layers complement; they don't compete.
- **NeMo = flag-gated, not always-on** — it's an extra LLM call per triage; always-on ~doubles NIM
  usage (hits the 40 req/min free cap faster, esp. with the sim running). Flip on for demos/high-risk.
- **PII = regex, not Presidio** — `presidio-analyzer` HARD-depends on spaCy, so "no spaCy" means no
  Presidio. The regex masker (`guardrails_runtime.mask_pii`) covers the high-value structured entities
  with zero deps. Trade-off: no PERSON/LOCATION masking. Restore Presidio+spaCy if names matter (bigger image).
- **Image optimization** (instead of dropping guardrails): multi-stage Dockerfile (builder venv →
  slim runtime, no gcc/pip-cache), `.dockerignore` (no `.venv`/`node_modules`/`_archive`/`frontend`),
  ship NeMo but not Presidio/spaCy/Phoenix.

Verified locally: NeMo flag ON → off-topic hard-blocked before the triage LLM; regex masker →
email/phone/card/SSN/IP redacted; field → off-topic flagged even with NeMo off.

---

## Settings (`/settings`) — live flag toggles

New page (round 4): browser toggles for the three runtime flags (`kill_switch`, `input_rail`,
`mask_input`), with the **kill switch** as a prominent red hero switch ("Engaged" badge when on).
- Backend: `GET/POST /admin/flags` (`backend/routers/admin.py` + `services/admin_service.py`) →
  reads/updates the `system_flags` table. POST only flips KNOWN flags (404 otherwise).
- Because flags are DB-backed + read per-request, a toggle takes effect **instantly, fleet-wide, no
  redeploy** — the whole reason we chose DB flags over env vars.

### How to toggle flags once deployed on AWS
The flags are rows in `system_flags` in **RDS**; toggling = one `UPDATE` (or the new POST endpoint).
Ways to reach a private RDS, easiest first:
- **This Settings page** (the POST /admin/flags route) — one click, nothing else to run.
- `aws ecs execute-command` into the backend task → run the UPDATE (task already has RDS creds/network).
- `aws ssm start-session` port-forward → local psql/Adminer against RDS (no bastion, no open ports).
- Bastion host → SSH tunnel → psql. / RDS Query Editor (Aurora + Data API only).
The kill switch as a one-click button is also a strong "blast-radius control" demo for the JD.
> Note: `/admin/flags` has no auth yet — fine for a demo behind a private ALB; add an API key / IAM
> before exposing it publicly.

---

## Review (`/review`) — human-in-the-loop queue

The control the autonomy gate defers to: for each proposal a human approves/rejects.
- List = `GET /tickets` → `triage_log` (all real, same source as the dashboard). Approve/Reject =
  `POST /tickets/{id}/review` → UPDATEs `triage_log.decision`/`reviewer` (optimistic UI).
- **The loop:** these decisions feed `segment_metrics.accept_rate` → `promotion_readiness` → a segment
  earns promotion suggest→auto. This page IS the evidence-gathering engine of the autonomy story.

### Refinements (DONE, round 4)
1. **Dark-mode fixed** — swapped hardcoded `bg-white`/`text-zinc-*` for theme tokens
   (`bg-card`/`text-muted-foreground`/`border-input`/`border-border`). Works in light + dark now.
2. **Expandable full assessment** — click a row to fetch `GET /tickets/{id}` and see mode_reason,
   summary, suggested reply, and remediation BEFORE deciding (no more approving blind). Approve/Reject
   moved into the expanded panel.
3. **Corrected-remediation capture** — the expanded panel has an editable remediation textarea
   (seeded from the agent's proposal); Approve sends it as `final_remediation` (the gold answer) →
   stored in `triage_log.final_remediation`. Verified end-to-end.

**Bug found + fixed while testing:** `GET /tickets/{id}` returned `developer_remediation` as a JSON
*string* (asyncpg returns JSONB as text), not an array — would have crashed the expand's `.join()`.
Fixed in `tickets_service.get_ticket` (parse `developer_remediation`/`final_remediation` to lists).

Files: `frontend/app/review/page.tsx` (rebuilt), `frontend/lib/types.ts` (TicketDetail),
`frontend/lib/api.ts` (getTicket→TicketDetail, review + final_remediation),
`backend/services/tickets_service.py` (JSONB parse).
