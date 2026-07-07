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


class FlagReq(BaseModel):
    name: str                           # kill_switch | input_rail | mask_input
    enabled: bool
    updated_by: str = "console"


class CsatReq(BaseModel):
    satisfied: bool                     # customer thumbs up/down on the auto reply


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


# --- simulator (all optional: send only the knobs you're changing) ---------
class SimConfigReq(BaseModel):
    speed: float | None = None
    triage_enabled: bool | None = None
    triage_per_min: float | None = None
    pipeline_enabled: bool | None = None
    jobs_per_min: float | None = None
    job_fail_rate: float | None = None
    auto_heal: bool | None = None
    index_enabled: bool | None = None
    index_ops_per_min: float | None = None
    auto_scan: bool | None = None
