"""Ticket + metrics + review routes. Thin: translate HTTP <-> service calls."""
from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_pool
from backend.schemas import ReviewReq
from backend.services import tickets_service

router = APIRouter(tags=["tickets"])


@router.get("/tickets")
async def list_tickets(limit: int = 50, pool=Depends(get_pool)):
    return await tickets_service.list_tickets(pool, limit)


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, pool=Depends(get_pool)):
    ticket = await tickets_service.get_ticket(pool, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket


@router.get("/metrics")
async def metrics(pool=Depends(get_pool)):
    return await tickets_service.segment_metrics(pool)


@router.post("/tickets/{ticket_id}/review")
async def review(ticket_id: int, body: ReviewReq, pool=Depends(get_pool)):
    ok = await tickets_service.record_review(
        pool, ticket_id, body.decision, body.reviewer,
        body.final_remediation, body.review_comment)
    if not ok:
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"status": "recorded", "ticket_id": ticket_id}
