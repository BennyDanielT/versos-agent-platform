"""Autonomy-policy routes — view and edit the per-segment approved mode."""
from fastapi import APIRouter, Depends

from backend.db import get_pool
from backend.schemas import PolicyReq
from backend.services import policy_service

router = APIRouter(tags=["policy"])


@router.get("/policy")
async def get_policy(pool=Depends(get_pool)):
    return await policy_service.get_policy(pool)


@router.put("/policy")
async def upsert_policy(body: PolicyReq, pool=Depends(get_pool)):
    await policy_service.upsert_policy(
        pool, body.severity, body.category, body.approved_mode,
        body.min_confidence, body.updated_by)
    return {"status": "ok"}
