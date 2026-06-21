"""Media asset endpoints.

Upload registers the asset row (S3 plumbing lands in Step 4). Enrichment runs
the parallel LangGraph pipeline (Option B) — stubbed until Step 4.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import MediaAsset
from app.schemas import AssetCreate, AssetOut

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetOut, status_code=201)
async def register_asset(payload: AssetCreate, db: AsyncSession = Depends(get_session)):
    # The canonical S3 location this asset will occupy. Step 4 performs the actual
    # upload (presigned PUT) to this key; here we register the real bucket/key.
    settings = get_settings()
    s3_uri = f"s3://{settings.s3_bucket}/{payload.customer_id}/{payload.filename}"
    asset = MediaAsset(
        customer_id=payload.customer_id,
        filename=payload.filename,
        s3_uri=s3_uri,
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)
    return asset


@router.get("", response_model=list[AssetOut])
async def list_assets(
    processing_status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(limit)
    if processing_status:
        stmt = stmt.where(MediaAsset.processing_status == processing_status)
    return (await db.execute(stmt)).scalars().all()


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_session)):
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.post("/{asset_id}/enrich", response_model=AssetOut)
async def enrich_asset(asset_id: int, db: AsyncSession = Depends(get_session)):
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    # TODO(step 4): run parallel enrichment graph (transcribe ‖ language ‖ keywords).
    raise HTTPException(status_code=501, detail="enrichment pipeline not wired yet (Step 4)")
