"""WEEKLY promotion job — proposes segments ready for more autonomy. HUMAN approves.

Promotion is deliberate: this job NEVER flips a row on its own. Default run = dry-run that
PRINTS the segments that cleared the bar + the exact UPDATE a human would run. Pass --apply
(a human running it, knowingly) to actually upsert the policy rows.

  dry-run (default):  python jobs/promotion_job.py
  apply (human gate): python jobs/promotion_job.py --apply

Schedule in Versos: AWS EventBridge Scheduler (rate = 1 week) → ECS Fargate task running this
in dry-run, posting the proposals to Slack/a ticket. A human then re-runs with --apply (or
clicks approve in a small UI that calls the same upsert). Dev box: cron / Task Scheduler.
"""
from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg

DSN = os.environ.get("DATABASE_URL", "postgresql://versos:versos@localhost:5432/versos")


async def run(apply: bool) -> None:
    pool = await asyncpg.create_pool(DSN)
    try:
        # Segments that cleared the bar AND aren't already at 'auto'.
        rows = await pool.fetch(
            """
            SELECT pr.severity, pr.category, pr.reviewed_eligible, pr.accept_rate,
                   pr.precision_eligible, coalesce(p.approved_mode, 'suggest') AS current_mode
            FROM promotion_readiness pr
            LEFT JOIN triage_policy p ON p.severity = pr.severity AND p.category = pr.category
            WHERE pr.eligible_for_auto
              AND coalesce(p.approved_mode, 'suggest') <> 'auto'
            ORDER BY pr.severity, pr.category
            """
        )
        if not rows:
            print("No segments eligible for promotion right now.")
            return

        print(f"{len(rows)} segment(s) eligible for promotion to 'auto':\n")
        for r in rows:
            print(f"  {r['severity']}/{r['category']}: now '{r['current_mode']}' -> 'auto' "
                  f"(n={r['reviewed_eligible']}, accept={r['accept_rate']}, "
                  f"precision={r['precision_eligible']})")
            if apply:
                await pool.execute(
                    """
                    INSERT INTO triage_policy(severity, category, approved_mode, min_confidence, updated_by)
                    VALUES($1, $2, 'auto', 0.85, 'promotion_job')
                    ON CONFLICT(severity, category)
                    DO UPDATE SET approved_mode='auto', updated_by='promotion_job', updated_at=now()
                    """,
                    r["severity"], r["category"],
                )
                print("    [OK] APPLIED")
            else:
                print(f"    (dry-run) approve with: UPDATE triage_policy SET approved_mode='auto' "
                      f"WHERE severity='{r['severity']}' AND category='{r['category']}';")
    finally:
        await pool.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually promote (human-invoked)")
    asyncio.run(run(ap.parse_args().apply))
