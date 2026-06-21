"""Pydantic request/response models — the API contract.

Kept separate from the ORM models so the wire format and the storage format can
evolve independently (e.g. we never expose internal columns we don't want to).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --- tickets ---
class TicketCreate(BaseModel):
    customer_id: str
    complaint_text: str


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: str
    complaint_text: str
    issue_category: str | None
    severity: str | None
    ai_summary: str | None
    ai_remediation: str | None
    ai_confidence: float | None
    status: str
    triage_mode: str
    approved_by: str | None
    created_at: datetime


# --- assets ---
class AssetCreate(BaseModel):
    customer_id: str
    filename: str


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: str
    s3_uri: str
    filename: str
    duration_seconds: float | None
    language: str | None
    keywords: list[str] | None
    processing_status: str
    created_at: datetime


# --- audit ---
class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    finding_type: str
    severity: str
    description: str
    detected_by: str
    resolved: bool
    created_at: datetime
