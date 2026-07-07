"""Admin routes — flip the live runtime flags (kill switch + guardrail toggles).

DB-backed flags read per-request → these take effect instantly, fleet-wide, no redeploy.
(In prod this is the same UPDATE you'd otherwise run against RDS by hand.)
"""
from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_pool
from backend.schemas import FlagReq
from backend.services import admin_service

router = APIRouter(tags=["admin"])


@router.get("/admin/flags")
async def list_flags(pool=Depends(get_pool)):
    return await admin_service.get_flags(pool)


@router.post("/admin/flags")
async def set_flag(body: FlagReq, pool=Depends(get_pool)):
    try:
        return await admin_service.set_flag(pool, body.name, body.enabled, body.updated_by)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
