"""System feature-flag business logic — the live runtime toggles (kill switch, guardrails).

Flags are rows in `system_flags`, read PER-REQUEST by the agents, so a change here takes effect
immediately and fleet-wide with no redeploy. Pure SQL.
"""
import asyncpg


async def get_flags(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch(
        "SELECT name, enabled, updated_by, updated_at FROM system_flags ORDER BY name")
    return [dict(r) for r in rows]


async def set_flag(pool: asyncpg.Pool, name: str, enabled: bool, updated_by: str) -> dict:
    """Flip a KNOWN flag. Returns the updated row; raises ValueError for an unknown flag
    (we never create arbitrary flags from the API)."""
    row = await pool.fetchrow(
        "UPDATE system_flags SET enabled=$2, updated_by=$3, updated_at=now() "
        "WHERE name=$1 RETURNING name, enabled, updated_by, updated_at",
        name, enabled, updated_by)
    if row is None:
        raise ValueError(f"unknown flag: {name}")
    return dict(row)
