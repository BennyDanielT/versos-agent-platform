# Interview Prep — Start Here

Everything you need to explain this project. Read in order.

1. **[01_ARCHITECTURE.md](01_ARCHITECTURE.md)** — the mental model, system diagram,
   the 5 design decisions, request lifecycle, stack rationale.
2. **[02_CODE_WALKTHROUGH.md](02_CODE_WALKTHROUGH.md)** — every file: what & why.
3. **[03_QA_PREP.md](03_QA_PREP.md)** — anticipated questions + answers to rehearse.
4. **[04_GLOSSARY.md](04_GLOSSARY.md)** — every term, in plain English.

---

## 60-second cheat sheet (memorize this)

**What it is:** "A small agent-ops platform mirroring Versos' surfaces — support
triage, media enrichment, quality auditing — on FastAPI + Postgres + S3 + LangGraph,
unified by an autonomy model where agents earn the right to act."

**The 3 features:**
1. Support triage — supervisor + specialists (built ✅)
2. Media enrichment — parallel pipeline (next)
3. Quality auditor — rules + LLM trust layer (next)

**The 5 things I can defend:**
1. One platform, not three demos — the autonomy model is the glue.
2. Business records in Postgres; agent telemetry in LangSmith/OTel (not the DB).
3. Autonomy is a **column** (`triage_mode`: suggest/approved/auto), not a bolt-on.
4. A **provider seam** (real NIM today, swappable) so orchestration never marries a vendor.
5. Two multi-agent patterns on purpose (supervisor vs parallel).

**The killer sentence:**
> "The agent never acts on its own — it emits a recommendation. Promotion from
> suggest to approved to auto is governed by evidence from the auditor and the eval
> suite, and critical actions are hard-pinned behind a human. The proof that an
> agent is safe is itself my deliverable."

**If asked what's NOT done (be honest):** enrichment + auditor are stubs (501);
evals + LangSmith tracing are designed, not wired; no auth/retries yet. Spine first.

---

## Live demo script (if you screen-share)

```bash
docker compose up -d
# one-time: put a real NVIDIA NIM key in .env  (NVIDIA_API_KEY=nvapi-...  from build.nvidia.com)
.venv/Scripts/python -m uvicorn app.main:app --port 8077
# open http://localhost:8077/docs
```
1. `POST /tickets` with a "minor subtitle sync" complaint → show it lands `new/suggest`.
2. `POST /tickets/{id}/triage` → show category, severity, summary, remediation,
   and `triage_mode=approved`.
3. `POST /tickets/{id}/triage` on an "URGENT data loss" complaint → show it's pinned
   to `suggest` despite the model — the blast-radius control.
4. `python -m pytest -q` → 5 green tests on the promotion policy.

That sequence tells the whole story in ~3 minutes.
```
