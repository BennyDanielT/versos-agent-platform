"""Pydantic request models — the API contract the frontend POSTs."""
from pydantic import BaseModel


class TriageReq(BaseModel):
    complaint: str


class ReviewReq(BaseModel):
    decision: str                       # approve | reject
    reviewer: str
    final_remediation: list[str] | None = None
    review_comment: str = ""


class PolicyReq(BaseModel):
    severity: str
    category: str
    approved_mode: str                  # suggest | approved | auto
    min_confidence: float = 0.85
    updated_by: str = "api"


class AskReq(BaseModel):
    message: str


# --- index-hygiene ---------------------------------------------------------
class IndexReviewReq(BaseModel):
    decision: str                       # approve | reject
    reviewer: str
    review_comment: str = ""


class ApplyReq(BaseModel):
    allow_auto: bool = False            # also run findings whose mode is 'auto'


# --- pipeline healer -------------------------------------------------------
class HealReq(BaseModel):
    job_ref: str = ""                   # a job id as string, or "" to sweep all failed
