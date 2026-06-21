"""Shared state passed between nodes in the triage graph.

LangGraph threads one state dict through the graph; each node returns a partial
update that gets merged. Keeping it a TypedDict (not free-floating args) is what
lets us trace, replay, and snapshot a run — the audit-layer primitives.
"""
from typing import TypedDict


class TriageState(TypedDict, total=False):
    # input
    ticket_id: int
    complaint_text: str

    # specialist outputs (filled as the graph runs)
    category: str
    severity: str
    confidence: float
    summary: str
    remediation: str
    draft_reply: str

    # supervisor decision
    recommended_mode: str  # suggest | approved | auto
    notes: str
