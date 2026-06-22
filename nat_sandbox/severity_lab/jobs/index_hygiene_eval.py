"""OFFLINE eval for the index-hygiene scanner = a labeled precision/recall harness.

Detection is deterministic, so its "eval" is a REGRESSION SUITE over labeled ground truth
(not an LLM nat-eval). We know which indexes are truly unused; we run the scanner, compare to
truth, and compute precision/recall (see Q49). Running at two observation windows shows how the
precision guard moves the numbers.

Run:
    .venv/Scripts/python.exe nat_sandbox/severity_lab/jobs/index_hygiene_eval.py
"""
from __future__ import annotations

import asyncio
import os

import asyncpg

from severity_lab.index_hygiene import _collect_findings, _RECORD_SEEN_SQL

DSN = os.environ.get("DATABASE_URL", "postgresql://versos:versos@localhost:5432/versos")

# Ground truth over NON-PK indexes: should the scanner flag it as UNUSED?
GROUND_TRUTH = {
    "idx_demo_unused":              True,   # we made it, nothing uses it
    "idx_findings_open":            True,   # archived-project leftovers, all dead
    "idx_findings_asset":           True,
    "idx_assets_status_created":    True,
    "idx_tickets_status_created":   True,
    "idx_tickets_customer_created": True,
    "idx_transcripts_asset":        True,
    "idx_triage_log_created":       False,  # genuinely USED (has scans) → must NOT flag
    "idx_index_findings_detected":  False,  # NEWBORN → the window guard must protect it
}
_TRUE = [k for k, v in GROUND_TRUTH.items() if v]
_FALSE = [k for k, v in GROUND_TRUTH.items() if not v]


async def _setup_observations(pool: asyncpg.Pool) -> None:
    """Make the eval reproducible: established-unused indexes look 10 days old; the
    newborn stays fresh. (Eval fixture, like seeding triage reviews.)"""
    await pool.execute(_RECORD_SEEN_SQL)
    await pool.execute("UPDATE index_seen SET first_seen_at = now() - interval '10 days' "
                       "WHERE object_index = ANY($1)", _TRUE)
    await pool.execute("UPDATE index_seen SET first_seen_at = now() WHERE object_index = ANY($1)", _FALSE)


def _metrics(flagged: set[str]) -> dict:
    tp = sum(1 for k, v in GROUND_TRUTH.items() if v and k in flagged)
    fp = sum(1 for k, v in GROUND_TRUTH.items() if (not v) and k in flagged)
    fn = sum(1 for k, v in GROUND_TRUTH.items() if v and k not in flagged)
    tn = sum(1 for k, v in GROUND_TRUTH.items() if (not v) and k not in flagged)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(precision, 3), "recall": round(recall, 3)}


async def main() -> None:
    pool = await asyncpg.create_pool(DSN)
    try:
        await _setup_observations(pool)
        for window in (7.0, 0.0):
            findings = await _collect_findings(pool, window)
            flagged = {f["object_index"] for f in findings if f["finding_type"] == "unused"}
            m = _metrics(flagged)
            label = "guard ON " if window else "guard OFF"
            print(f"window={window:>4} days ({label}): "
                  f"TP={m['TP']} FP={m['FP']} FN={m['FN']} TN={m['TN']}  "
                  f"precision={m['precision']}  recall={m['recall']}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
