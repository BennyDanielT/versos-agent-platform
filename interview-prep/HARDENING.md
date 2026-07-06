# Hardening backlog — from demo to comprehensive

Honest list of what's built vs. what a production-grade version would add, per vertical.
Kept deliberately candid: knowing the difference between a demo and a real system is the
point. Each item notes **why it matters** and a rough **effort**.

Legend: 🟢 small (hours) · 🟡 medium (a day) · 🔴 large (multi-day)

---

## Feature 1 — Support Triage

- [ ] 🟡 **Automatic, evidence-based promotion.** Today promotion is *manual* via the Policy
  page. The scheduled `promotion_job` / `monitor_job` exist in `nat_sandbox/.../jobs/` but
  aren't wired into the backend API or the simulator. *Why:* the "autonomy is earned" thesis
  is currently told by hand, not demonstrated by the system promoting a segment on its own
  once metrics clear the bar.
- [ ] 🟡 **Simulated reviews + CSAT.** The simulator generates tickets but not reviewer
  decisions or customer-satisfaction signals, so `segment_metrics` online evidence doesn't
  accrue at scale. *Why:* without it, the promotion loop has no data to act on in a demo.
- [ ] 🟢 **Offline eval hook in the UI.** `nat eval` golden-set runs exist but aren't surfaced
  in the console. *Why:* "prove behaviour offline before trusting online" is a core claim; a
  visible eval score makes it real.

---

## Feature 2 — Index Hygiene

- [ ] 🟡 **Per-finding apply + before/after panel in the UI.** There's a bulk "Apply approved"
  button but no "apply this one" action, and the efficacy view (`index_action_metrics`:
  bytes reclaimed, re-create rate) isn't surfaced on the page beyond the stat tiles.
  *Why:* the "did acting actually help?" online-eval story is the payoff and should be visible.
- [ ] 🟢 **`invalid`-index findings are undemonstrated.** The detector is real, but the
  simulator can't easily force a failed `CREATE INDEX CONCURRENTLY`, so that path never fires
  in a live demo. *Why:* completeness of the detector story.
- [ ] 🟡 **No `bloated`-index detector.** The schema lists `bloated` as a finding type but it
  isn't implemented (needs `pgstattuple` or an estimate query). *Why:* bloat is one of the
  most common real index problems.

---

## Feature 3 — Pipeline Healer

- [ ] 🟡 **Human review of `propose` / `escalate` in the UI.** Triage and Index both have
  Approve/Reject; the heal_log has `decision`/`reviewer` columns but no endpoint or UI.
  *Why:* symmetry — the human-in-the-loop step is missing for the one vertical that most
  needs it (a proposed fix should be approvable).
- [ ] 🟡 **`verify` models no re-execution latency.** It checks job status immediately after
  re-queue, so a "retry" reads as resolved instantly rather than modeling a real re-run.
  *Why:* the retry-cycle / escalate-on-exhaustion branch rarely fires in the sim.
- [ ] 🟢 **`scale` / `oom` has no resource dimension.** It re-queues like every other fix;
  there's no simulated capacity that scaling actually changes. *Why:* diagnosis realism.

---

## Cross-cutting

- [ ] 🔴 **Close the promotion loop end-to-end.** Evidence is logged everywhere
  (`segment_metrics`, `index_action_metrics`, `heal_log`) but the system never promotes a
  segment's autonomy on its own once metrics clear the bar — it's always a human editing a
  policy table. Wiring `promotion_job`/`monitor_job` into the backend + simulator is the
  single highest-leverage item: it turns the central thesis from *told* into *demonstrated*.
- [ ] 🟡 **AuthN/AuthZ.** No auth on the API or console. Fine for a local/demo, required for
  anything real (reviewer identity is currently a hardcoded string).
