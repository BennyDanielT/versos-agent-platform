"""Structured outputs for each triage specialist.

Every specialist returns a typed object, never free text. Structured outputs are
the contract that makes agents auditable and evaluable — you can diff them, score
them, and gate promotion on them. (Job ad: "structured outputs, evals".)
"""
from pydantic import BaseModel, Field


class Classification(BaseModel):
    category: str = Field(description="issue category, e.g. billing, media_quality, account_access, bug, general")
    severity: str = Field(description="one of: low, medium, high, critical")
    confidence: float = Field(description="0..1 confidence in this classification")


class Summary(BaseModel):
    summary: str = Field(description="one or two sentence neutral summary of the complaint")


class Remediation(BaseModel):
    remediation: str = Field(description="concrete, ordered remediation steps for a support engineer")
    draft_reply: str = Field(description="a short customer-facing reply draft")
