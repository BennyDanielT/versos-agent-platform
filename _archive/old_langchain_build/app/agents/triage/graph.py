"""Supervisor + specialists triage graph (Option A).

Flow:

        ┌──────────┐
        │ classify │              (must run first: severity/confidence feed the rest)
        └────┬─────┘
       ┌─────┴──────┐
       ▼            ▼
 ┌──────────┐  ┌───────────┐      (summarize ‖ remediate — independent, fan-out)
 │summarize │  │ remediate │
 └────┬─────┘  └─────┬─────┘
      └──────┬───────┘
             ▼
       ┌──────────┐
       │  decide  │              (supervisor: pick recommended autonomy mode)
       └──────────┘

The `decide` node is the interview centerpiece: it turns confidence + severity
into a *recommended* autonomy mode. The agent never silently acts — it recommends,
and the endpoint/human decides whether to honor it. That's the suggest → approved
→ auto graduation made concrete.
"""
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.triage.specialists import classify, remediate, summarize
from app.agents.triage.state import TriageState

# Promotion policy (deliberately conservative + explainable, not a black box).
_CONF_AUTO = 0.85
_CONF_APPROVE = 0.60


def decide(state: TriageState) -> TriageState:
    conf = state.get("confidence", 0.0)
    severity = state.get("severity", "medium")

    # Critical issues never auto-resolve, regardless of confidence — a blast-radius
    # control. The worst-case action stays behind a human.
    if severity == "critical":
        return {"recommended_mode": "suggest",
                "notes": "Critical severity is always held for human review."}

    if conf >= _CONF_AUTO and severity in ("low", "medium"):
        return {"recommended_mode": "auto",
                "notes": f"High confidence ({conf:.2f}) on non-critical issue."}
    if conf >= _CONF_APPROVE:
        return {"recommended_mode": "approved",
                "notes": f"Moderate confidence ({conf:.2f}); recommend human approval."}
    return {"recommended_mode": "suggest",
            "notes": f"Low confidence ({conf:.2f}); suggest-only."}


@lru_cache(maxsize=1)
def build_triage_graph():
    """Compile once and reuse. Returns a runnable LangGraph app."""
    g = StateGraph(TriageState)
    g.add_node("classify", classify)
    g.add_node("summarize", summarize)
    g.add_node("remediate", remediate)
    g.add_node("decide", decide)

    g.add_edge(START, "classify")
    g.add_edge("classify", "summarize")
    g.add_edge("classify", "remediate")
    g.add_edge("summarize", "decide")
    g.add_edge("remediate", "decide")
    g.add_edge("decide", END)
    return g.compile()


def run_triage(ticket_id: int, complaint_text: str) -> TriageState:
    app = build_triage_graph()
    return app.invoke({"ticket_id": ticket_id, "complaint_text": complaint_text})
