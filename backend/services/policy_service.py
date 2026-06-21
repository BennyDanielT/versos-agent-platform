"""Autonomy-policy business logic — the 'humans steer policy' surface. Pure SQL."""
import asyncpg


async def get_policy(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch(
        "SELECT severity, category, approved_mode, min_confidence, updated_by, updated_at "
        "FROM triage_policy ORDER BY severity, category")
    return [dict(r) for r in rows]


async def upsert_policy(pool: asyncpg.Pool, severity: str, category: str,
                        approved_mode: str, min_confidence: float, updated_by: str) -> None:
    await pool.execute(
        "INSERT INTO triage_policy (severity, category, approved_mode, min_confidence, updated_by) "
        "VALUES ($1,$2,$3,$4,$5) "
        "ON CONFLICT (severity, category) DO UPDATE SET "
        "approved_mode=$3, min_confidence=$4, updated_by=$5, updated_at=now()",
        severity, category, approved_mode, min_confidence, updated_by)
