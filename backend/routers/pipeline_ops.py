"""Pipeline self-healer routes: list jobs, run the healer, read the decision log.

The heal action delegates to the severity_lab LangGraph healer (same code the CLI runs);
reads go through the shared pool.
"""
from fastapi import APIRouter, Depends

from backend.core.config import get_settings
from backend.db import get_pool
from backend.schemas import HealReq
from backend.services import ops_service

router = APIRouter(prefix="/pipeline", tags=["pipeline-healer"])


@router.get("/jobs")
async def jobs(pool=Depends(get_pool)):
    return await ops_service.list_jobs(pool)


@router.get("/heal-log")
async def heal_log(limit: int = 100, pool=Depends(get_pool)):
    return await ops_service.heal_log(pool, limit)


@router.get("/policy")
async def policy(pool=Depends(get_pool)):
    return await ops_service.heal_policy(pool)


@router.post("/heal")
async def heal(body: HealReq):
    """Detect → diagnose → gate → fix/propose/escalate. One job id, or all failed jobs."""
    dsn = get_settings().asyncpg_dsn
    healed = await ops_service.heal(dsn, body.job_ref)
    return {"healed": healed}
