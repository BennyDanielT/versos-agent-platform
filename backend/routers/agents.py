"""Agentic routes — these run NAT workflows in-process (everything else is SQL)."""
import json

from fastapi import APIRouter, Depends

from backend.schemas import AskReq, TriageReq
from backend.services import nat_service

router = APIRouter(tags=["agents"])


@router.post("/triage")
async def triage(body: TriageReq, sm=Depends(nat_service.get_triage)):
    out = await nat_service.run_workflow(sm, body.complaint)
    try:
        return json.loads(out)              # the triage tool returns a JSON string
    except json.JSONDecodeError:
        return {"raw": out}


@router.post("/ask")
async def ask(body: AskReq, sm=Depends(nat_service.get_agent)):
    """Human-facing copilot: free-form question, the agent decides which tool to call."""
    answer = await nat_service.run_workflow(sm, body.message)
    return {"answer": answer}
