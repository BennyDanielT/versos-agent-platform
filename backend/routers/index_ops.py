"""Index-hygiene routes: scan the catalog, review findings, apply approved DDL.

Reads go through the shared pool; the scan/apply actions delegate to the severity_lab
package (same code the CLI runs), so they get their DSN from settings.
"""
from fastapi import APIRouter, Depends, HTTPException

from backend.core.config import get_settings
from backend.db import get_pool
from backend.schemas import ApplyReq, IndexReviewReq
from backend.services import ops_service

router = APIRouter(prefix="/index", tags=["index-hygiene"])


@router.get("/findings")
async def findings(limit: int = 100, pool=Depends(get_pool)):
    return await ops_service.list_findings(pool, limit)


@router.get("/metrics")
async def metrics(pool=Depends(get_pool)):
    return await ops_service.index_metrics(pool)


@router.get("/policy")
async def policy(pool=Depends(get_pool)):
    return await ops_service.index_policy(pool)


@router.post("/scan")
async def scan():
    """Run the deterministic catalog scan; refreshes open findings and returns them."""
    dsn = get_settings().asyncpg_dsn
    findings = await ops_service.run_scan(dsn)
    return {"count": len(findings), "findings": findings}


@router.post("/apply")
async def apply(body: ApplyReq):
    """Execute the DDL for approved (and optionally auto) findings; records efficacy."""
    dsn = get_settings().asyncpg_dsn
    results = await ops_service.apply_findings(dsn, body.allow_auto)
    return {"applied": results}


@router.post("/findings/{finding_id}/review")
async def review(finding_id: int, body: IndexReviewReq, pool=Depends(get_pool)):
    ok = await ops_service.review_finding(
        pool, finding_id, body.decision, body.reviewer, body.review_comment)
    if not ok:
        raise HTTPException(status_code=404, detail="finding not found")
    return {"status": "recorded", "finding_id": finding_id}
