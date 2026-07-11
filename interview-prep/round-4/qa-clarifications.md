# Round-4 Q&A clarifications (interview-ready)

Concept answers built up while testing/deploying. Each is phrased so you can say it out loud.

---

## Triage: the three text fields

| Field | Audience | Purpose |
|---|---|---|
| `suggested_customer_reply` | the **customer** | friendly, PII-masked message that goes out; must be **standalone** (never "see steps above") |
| `developer_remediation` | your **engineers** | technical fix steps; **never** shown to the customer |
| `final_remediation` | evals | the human's **corrected** remediation = the **gold answer** (ground-truth label) |

**Line:** *"I split the customer message from the engineering remediation, and capture the human's correction as the gold label — that's how I measure whether the agent was actually right."*

---

## Confidence — where it comes from & how to optimize

- **Source:** *self-reported* — the LLM returns `confidence` as a field in the structured output. It's the model's own estimate, **not** a calibrated probability. Raw 0.90 ≠ "right 90% of the time."
- **Why it matters:** you only auto where high confidence *empirically* = high accuracy. The lever is the per-segment `min_confidence` bar in the policy table.
- **Optimize by binning (calibration):** bucket past tickets by confidence (0.7–0.8, 0.8–0.9, 0.9–1.0); in each bin compute actual correctness from ground truth. Build a **reliability curve**. Overconfident bin (says 0.85, only 70% right) → **raise the bar**. Under-used bin (0.80 already 95% right) → **lower it, auto more**.
- **Beyond self-report (if pushed):** self-consistency (sample N, use agreement), logprob scoring, or an LLM-judge second pass.

**Line:** *"Confidence is the model's self-estimate — I don't trust it raw. I bin historical predictions against ground truth to find where it's actually calibrated, and set the per-segment auto threshold there. Autonomy is earned by measured accuracy, not the model's say-so."*

---

## Accept-rate & the two ground-truth signals

- **accept-rate = approved / (approved + rejected)**, computed **only over reviewed tickets** (`decision IS NOT NULL`).
  - `approve` = human agreed with the agent; `reject` = didn't. It's the **online accuracy** signal for the `suggest`/`approved` path.
- **Two signals, two modes — don't conflate:**
  - **accept-rate** (`decision`) → quality of tickets a human *reviewed*.
  - **CSAT** (`customer_satisfied`) → quality of tickets that went out on **auto** (no human checked → the customer is the judge).
- **Selection bias:** accept-rate only sees the subset a human reviewed, and the policy sends the **harder** cases (low-confidence / high-severity / no-policy) to humans. So accept-rate measures the agent on the **hard tickets you didn't trust it with** — pessimistic for overall accuracy; the easy auto tickets are invisible to it.
- **"All traffic"** = every triaged ticket across `auto` + `approved` + `suggest`. Neither metric alone estimates accuracy across all of it.
- **Unbiased fix:** a **random hold-out / shadow audit** — force a small random % of *all* tickets (including ones that would've auto'd) into human review, regardless of mode. Catches an overconfident `auto` segment before CSAT complaints roll in.

**Line:** *"Accept-rate is accuracy on the subset a human reviewed, which the policy skews toward hard cases; auto is measured separately by CSAT. To estimate true accuracy across all traffic I'd add a random shadow-audit sample."*

---

## Auto response — how it's decided & how to trigger it

- Mode (`auto` / `approved` / `suggest`) comes from the **policy table**, not the text. A ticket auto-resolves only if: its `severity/category` segment is `approved_mode=auto` **AND** confidence ≥ that segment's `min_confidence` **AND** severity ≠ critical **AND** kill switch off.
- **Seeded auto segment:** `low / media_quality @ 0.85` (only one). `low/bug` and `medium/media_quality` are `approved`.
- **To demo auto:** either submit a clearly-minor media-quality complaint (needs good classification + confidence ≥ bar), or — stronger story — open **Policy & Metrics** and flip a segment to `auto` live: *"autonomy is data a human controls; I change one row and behavior changes, no redeploy."*
- **Hard caps (defense in depth):** `critical` severity and any destructive action (index `DROP`) can **never** be auto, even if policy says so — enforced in code.

---

## Classifier quality (why media_quality mis-filed as "other")

- **Root cause:** the prompt listed category *names* with no definitions, so the model guessed and dumped ambiguous tickets into `other` — which broke the `low/media_quality` auto path.
- **Fix (shipped):** explicit per-category definitions + examples in the prompt ("export/render/color/audio → media_quality"), "pick the most specific; `other` is last resort," plus a calibration nudge on confidence.
- **Further levers:** few-shot labeled examples; measure confusion against `decision`/`final_remediation` to target the categories it actually confuses.

---

## Index Hygiene (the no-LLM vertical)

- **What:** an agent that keeps Postgres indexes healthy — finds **unused / missing / duplicate / invalid** indexes, risk-rates them, proposes a fix; the policy gate decides autonomy.
- **Deterministic, no LLM:** reads system catalogs — `pg_stat_user_indexes`, `pg_stat_user_tables`, `pg_index`, `pg_indexes` (+ an `index_seen` table for the 7-day "unused" precision guard). *"You don't need an LLM to read a system catalog — determinism buys auditability."*
- **Safety:** `DROP` is hard-capped in code to `approved` (a human commits it), never `auto`; every drop carries a rollback (the original `CREATE`).
- **Trust metric:** **re-create rate** — if it drops indexes and someone recreates them, that's the "oops" signal; must be ~0 to trust `auto`.
- **Verify end-to-end:** plant a known problem → `POST /index/scan` → confirm the finding matches a real catalog object → Approve/Apply → confirm the index is actually gone + `bytes_reclaimed` ticks up + re-create rate stays 0.

---

## Client ⇄ specialist conversation (round-4e)

- Specialist can **edit the customer reply** before approving → saved to `final_customer_reply` (client sees it, falls back to the model draft).
- Client can **re-open after a reply**: a follow-up calls `escalate`, which clears `decision` (→ back to **Pending**), reclassifies to `suggest`, stores the note in `customer_followup`; specialist sees a blue follow-up banner.

---

## Deployment: two independent pipelines

- **Backend → GitHub Actions → ECS.** Path-filtered: only fires on `backend/**`, `nat_sandbox/**`, `Dockerfile`, `requirements-deploy.txt`, or the workflow file. A **frontend-only** push does **not** trigger it.
- **Frontend → Amplify.** Its own webhook on any push to `main`; builds only `frontend/` (its `appRoot`).

| Change | ECS | Amplify |
|---|---|---|
| only `frontend/**` | ❌ | ✅ |
| `backend/**` or `nat_sandbox/**` | ✅ | ✅ (no-op) |
| both | ✅ | ✅ |
| docs only | ❌ | ✅ (no-op) |

- **Asymmetry to remember:** GitHub Actions is path-filtered; Amplify is **not** (rebuilds on every `main` push → occasional harmless no-op frontend builds).
- **Cost control:** ~$2/day. Pause = scale ECS to 0 + `rds stop-db-instance`; resume in the morning. **Never delete the ALB** (its DNS is baked into Amplify's `BACKEND_URL`). Full commands in `DEPLOY-AWS.md`.

---

## Gotchas hit this session (worth a mention if asked)

- **`/index` route collided with the dashboard** — this Next version treats an `app/index/` folder as the root route. Renamed to `/index-hygiene`.
- **Bad `NVIDIA_API_KEY` failed silently** — the triage catch-block returned "Triage failed" without raising, so the simulator counted success and no tickets persisted (`triage_errors:0`, 0 rows). Fix: correct key; follow-up idea: count a "Triage failed" return as an error so it's visible.
- **2 GB ECS task OOM-killed** under simulator load → bumped to 4 GB + zero-downtime rollovers.
- **NAT configs ignored `DATABASE_URL`** (hardcoded localhost default) → crashed on boot; now read from env.
