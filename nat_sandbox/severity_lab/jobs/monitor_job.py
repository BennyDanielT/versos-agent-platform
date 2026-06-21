"""HOURLY monitor job — the brake. Auto-DEMOTES any 'auto' segment that has decayed.

Asymmetry on purpose: promotion is human + weekly (promotion_job.py); demotion is automatic
+ hourly (here). Removing trust must be instant and needs no human.

A segment is demoted to 'suggest' if, over a RECENT window, EITHER signal falls below its floor:
  - dev accept_rate   (from the ~5% of auto'd tickets sampled back to humans), OR
  - customer satisfaction_rate (CSAT — the label that survives auto mode, where decision is NULL).
Each guarded by a minimum sample size so one bad ticket can't nuke a good segment.

  python jobs/monitor_job.py            # auto-applies demotions (this IS the brake)

Schedule: AWS EventBridge Scheduler (rate = 1 hour) → ECS Fargate task. Dev box: cron hourly.
"""
from __future__ import annotations

import asyncio
import os

import asyncpg

DSN = os.environ.get("DATABASE_URL", "postgresql://versos:versos@localhost:5432/versos")

WINDOW_DAYS = 30          # only look at recent traffic, not all-time history
MIN_REVIEWS = 10          # need this many sampled reviews before trusting accept_rate
MIN_FEEDBACK = 10         # need this many CSAT responses before trusting satisfaction
ACCEPT_FLOOR = 0.90       # below this dev-accept → demote
SATISFACTION_FLOOR = 0.85 # below this CSAT → demote


async def run() -> None:
    pool = await asyncpg.create_pool(DSN)
    try:
        # Recent per-segment health, computed ONLY over segments currently at 'auto'.
        rows = await pool.fetch(
            f"""
            SELECT p.severity, p.category,
                   count(l.decision)                                   AS reviews,
                   round(avg((l.decision='approve')::int)::numeric, 3) AS accept_rate,
                   count(l.customer_satisfied)                         AS feedback,
                   round(avg(l.customer_satisfied::int)::numeric, 3)   AS satisfaction_rate
            FROM triage_policy p
            JOIN triage_log l
              ON l.severity = p.severity AND l.category = p.category
             AND l.created_at >= now() - interval '{WINDOW_DAYS} days'
            WHERE p.approved_mode = 'auto'
            GROUP BY p.severity, p.category
            """
        )
        demoted = 0
        for r in rows:
            reasons = []
            if r["reviews"] and r["reviews"] >= MIN_REVIEWS and r["accept_rate"] < ACCEPT_FLOOR:
                reasons.append(f"accept_rate {r['accept_rate']} < {ACCEPT_FLOOR} (n={r['reviews']})")
            if r["feedback"] and r["feedback"] >= MIN_FEEDBACK and r["satisfaction_rate"] < SATISFACTION_FLOOR:
                reasons.append(f"satisfaction {r['satisfaction_rate']} < {SATISFACTION_FLOOR} (n={r['feedback']})")
            if reasons:
                await pool.execute(
                    """UPDATE triage_policy SET approved_mode='suggest',
                       updated_by='monitor_job', updated_at=now()
                       WHERE severity=$1 AND category=$2""",
                    r["severity"], r["category"],
                )
                demoted += 1
                print(f"DEMOTED {r['severity']}/{r['category']} -> suggest :: " + "; ".join(reasons))
        if not demoted:
            print("All 'auto' segments healthy; nothing demoted.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
