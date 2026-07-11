"""Ticket + metrics business logic. Pure SQL, no FastAPI — unit-testable."""
import json

import asyncpg


async def list_tickets(pool: asyncpg.Pool, limit: int) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, complaint_text, severity, category, confidence, recommended_mode, "
        "decision, reviewer, customer_satisfied, created_at FROM triage_log "
        "ORDER BY id DESC LIMIT $1", limit)
    return [dict(r) for r in rows]


async def get_ticket(pool: asyncpg.Pool, ticket_id: int) -> dict | None:
    row = await pool.fetchrow("SELECT * FROM triage_log WHERE id = $1", ticket_id)
    if row is None:
        return None
    d = dict(row)
    # asyncpg returns JSONB as a text string — parse the list columns so the API returns arrays.
    for k in ("developer_remediation", "final_remediation"):
        if isinstance(d.get(k), str):
            try:
                d[k] = json.loads(d[k])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


async def segment_metrics(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("SELECT * FROM segment_metrics")
    return [dict(r) for r in rows]


async def record_review(pool: asyncpg.Pool, ticket_id: int, decision: str, reviewer: str,
                        final_remediation: list[str] | None, final_customer_reply: str | None,
                        review_comment: str) -> bool:
    """Returns True if a row was updated, False if the ticket didn't exist.

    A COALESCE on final_customer_reply means an empty edit doesn't blank a prior reply.
    Clears customer_followup — the specialist has now answered the latest follow-up.
    """
    result = await pool.execute(
        "UPDATE triage_log SET decision=$2, final_remediation=$3::jsonb, "
        "final_customer_reply=COALESCE($4, final_customer_reply), "
        "review_comment=$5, reviewer=$6, reviewed_at=now(), customer_followup=NULL "
        "WHERE id=$1",
        ticket_id, decision,
        json.dumps(final_remediation) if final_remediation is not None else None,
        (final_customer_reply or None), review_comment, reviewer)
    return not result.endswith("0")


async def record_csat(pool: asyncpg.Pool, ticket_id: int, satisfied: bool) -> bool:
    """Customer satisfaction on the (auto) reply — the ground-truth signal for auto-mode quality."""
    result = await pool.execute(
        "UPDATE triage_log SET customer_satisfied=$2, feedback_at=now() WHERE id=$1",
        ticket_id, satisfied)
    return not result.endswith("0")


async def escalate(pool: asyncpg.Pool, ticket_id: int, followup: str | None = None) -> bool:
    """Client wants a human — either on an auto reply, or re-opening after a specialist replied.
    Reclassify to 'suggest' and CLEAR the decision so it returns to the Pending queue; record
    the dissatisfaction and any follow-up message (visible to the specialist). Keeps
    final_customer_reply/reviewed_at as history of the prior response."""
    result = await pool.execute(
        "UPDATE triage_log SET recommended_mode='suggest', decision=NULL, "
        "mode_reason='Escalated by the customer for human review.', "
        "customer_satisfied=false, customer_followup=$2, feedback_at=now() "
        "WHERE id=$1", ticket_id, (followup or None))
    return not result.endswith("0")
