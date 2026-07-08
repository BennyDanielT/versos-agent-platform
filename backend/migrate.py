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


async def run_migrations(pool: asyncpg.Pool, sql_dir: str) -> None:
    # Sentinel: if the core table exists, the DB is already provisioned — do nothing.
    if await pool.fetchval("SELECT to_regclass('public.triage_log')") is not None:
        logger.info("schema already present; skipping migrations")
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
