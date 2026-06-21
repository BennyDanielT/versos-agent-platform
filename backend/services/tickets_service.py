"""Ticket + metrics business logic. Pure SQL, no FastAPI — unit-testable."""
import json

import asyncpg


async def list_tickets(pool: asyncpg.Pool, limit: int) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, complaint_text, severity, category, confidence, recommended_mode, "
        "decision, reviewer, created_at FROM triage_log ORDER BY id DESC LIMIT $1", limit)
    return [dict(r) for r in rows]


async def get_ticket(pool: asyncpg.Pool, ticket_id: int) -> dict | None:
    row = await pool.fetchrow("SELECT * FROM triage_log WHERE id = $1", ticket_id)
    return dict(row) if row else None


async def segment_metrics(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("SELECT * FROM segment_metrics")
    return [dict(r) for r in rows]


async def record_review(pool: asyncpg.Pool, ticket_id: int, decision: str, reviewer: str,
                        final_remediation: list[str] | None, review_comment: str) -> bool:
    """Returns True if a row was updated, False if the ticket didn't exist."""
    result = await pool.execute(
        "UPDATE triage_log SET decision=$2, final_remediation=$3::jsonb, "
        "review_comment=$4, reviewer=$5, reviewed_at=now() WHERE id=$1",
        ticket_id, decision,
        json.dumps(final_remediation) if final_remediation is not None else None,
        review_comment, reviewer)
    return not result.endswith("0")
