"""Support ticket endpoints.

The triage endpoint is a stub for now — Step 3 wires in the LangGraph
supervisor+specialists agent (Option A). The DB plumbing is real already.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.triage.graph import run_triage
from app.db import get_session
from app.models import SupportTicket
from app.schemas import TicketCreate, TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=201)
async def create_ticket(payload: TicketCreate, db: AsyncSession = Depends(get_session)):
    ticket = SupportTicket(
        customer_id=payload.customer_id,
        complaint_text=payload.complaint_text,
    )
    db.add(ticket)
    await db.flush()  # populate id without ending the transaction
    await db.refresh(ticket)
    return ticket


@router.get("", response_model=list[TicketOut])
async def list_tickets(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_session)):
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket


@router.post("/{ticket_id}/triage", response_model=TicketOut)
async def triage_ticket(ticket_id: int, db: AsyncSession = Depends(get_session)):
    """Run the supervisor+specialists triage graph and persist its output.

    Key autonomy rule: the agent only ever produces a *recommendation*. We always
    land the ticket in `triaged_suggested` and store the recommended mode. Whether
    that recommendation is honored (auto-resolve) is a separate human/policy step —
    suggest → approved → auto is governed outside the agent, not by the agent itself.
    """
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")

    # LangGraph invoke is sync; run it off the event loop so we don't block other requests.
    try:
        result = await run_in_threadpool(run_triage, ticket.id, ticket.complaint_text)
    except RuntimeError as exc:  # e.g. NVIDIA_API_KEY not configured
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    ticket.issue_category = result.get("category")
    ticket.severity = result.get("severity")
    ticket.ai_summary = result.get("summary")
    ticket.ai_remediation = result.get("remediation")
    ticket.ai_confidence = result.get("confidence")
    ticket.triage_mode = result.get("recommended_mode", "suggest")
    ticket.status = "triaged_suggested"
    await db.flush()
    await db.refresh(ticket)
    return ticket
