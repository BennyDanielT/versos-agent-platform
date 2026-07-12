"""Idempotent DB init — load the schema SQL on an EMPTY database (first boot on RDS).

The docker-compose dev flow loads schema via init scripts; RDS has no such hook, so the app
self-initializes. Guarded on a sentinel table so it runs ONCE (the pipeline_healer seed isn't
ON CONFLICT-safe, so we never re-run it on an already-provisioned DB).
"""
import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger("versos.migrate")

_FILES = ["schema.sql", "index_hygiene.sql", "pipeline_healer.sql"]

# Additive, idempotent column adds for ALREADY-provisioned DBs. The initial load is
# guarded by a sentinel (so the healer seed never re-runs), which means new columns in
# schema.sql never reach an existing RDS. These ALTERs are safe to run every boot.
_ADDITIVE = [
    "ALTER TABLE triage_log ADD COLUMN IF NOT EXISTS final_customer_reply TEXT",
    "ALTER TABLE triage_log ADD COLUMN IF NOT EXISTS customer_followup TEXT",
    # Re-create the promotion view every boot so threshold changes reach the live RDS
    # (the view is defined in the sentinel-guarded schema.sql, which won't re-run).
    # DEMO-relaxed thresholds; production would be ~ (20, 0.95, 0.97).
    """CREATE OR REPLACE VIEW promotion_readiness AS
       SELECT *,
              (reviewed_eligible >= 3
               AND accept_rate >= 0.66
               AND precision_eligible >= 0.66)  AS eligible_for_auto
       FROM segment_metrics""",
]


async def run_migrations(pool: asyncpg.Pool, sql_dir: str) -> None:
    # Sentinel: if the core table exists, the DB is already provisioned — only apply the
    # additive column migrations (cheap, idempotent), then stop.
    if await pool.fetchval("SELECT to_regclass('public.triage_log')") is not None:
        for stmt in _ADDITIVE:
            await pool.execute(stmt)
        logger.info("schema present; applied %d additive column migration(s)", len(_ADDITIVE))
        return
    base = Path(sql_dir)
    for name in _FILES:
        path = base / name
        if not path.exists():
            logger.warning("migration file missing: %s", path)
            continue
        # asyncpg's argument-less execute() uses the simple-query protocol → runs the whole file.
        await pool.execute(path.read_text(encoding="utf-8"))
        logger.info("applied migration %s", name)
    logger.info("migrations complete")
