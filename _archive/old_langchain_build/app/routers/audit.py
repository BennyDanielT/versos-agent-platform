"""Quality auditor endpoints — the trust layer.

Step 5 implements rules + optional LLM explanation. Listing open findings is
already real so the worklist query/index can be demoed.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuditFinding
from app.schemas import FindingOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/findings", response_model=list[FindingOut])
async def list_findings(
    resolved: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_session),
):
    stmt = (
        select(AuditFinding)
        .where(AuditFinding.resolved == resolved)
        .order_by(AuditFinding.severity, AuditFinding.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/assets/{asset_id}/run", response_model=list[FindingOut])
async def run_audit(asset_id: int, db: AsyncSession = Depends(get_session)):
    # TODO(step 5): run rule checks (+ optional LLM) over the asset's transcript.
    raise HTTPException(status_code=501, detail="auditor not wired yet (Step 5)")
