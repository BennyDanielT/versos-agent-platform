"""The specialist nodes — each does exactly one job and returns structured data.

Three specialists:
  * classifier  -> category + severity + confidence
  * summarizer  -> neutral summary
  * remediator  -> remediation steps + draft reply

Each is a plain function (state) -> partial state. That keeps them unit-testable
in isolation and trivially recomposable by the supervisor.
"""
from app.agents.llm import get_structured_llm
from app.agents.triage.schemas import Classification, Remediation, Summary
from app.agents.triage.state import TriageState


def classify(state: TriageState) -> TriageState:
    prompt = (
        "You are a support triage classifier. Classify the customer complaint.\n"
        "Return category, severity (low|medium|high|critical), and confidence (0..1).\n\n"
        f"Complaint:\n{state['complaint_text']}"
    )
    out: Classification = get_structured_llm(Classification).invoke(prompt)  # type: ignore[assignment]
    return {"category": out.category, "severity": out.severity, "confidence": out.confidence}


def summarize(state: TriageState) -> TriageState:
    prompt = (
        "Summarize this support complaint in one or two neutral sentences.\n\n"
        f"Complaint:\n{state['complaint_text']}"
    )
    out: Summary = get_structured_llm(Summary).invoke(prompt)  # type: ignore[assignment]
    return {"summary": out.summary}


def remediate(state: TriageState) -> TriageState:
    prompt = (
        "Given this complaint (category: "
        f"{state.get('category', 'unknown')}, severity: {state.get('severity', 'unknown')}),"
        " propose ordered remediation steps for a support engineer and a short "
        "customer-facing reply draft.\n\n"
        f"Complaint:\n{state['complaint_text']}"
    )
    out: Remediation = get_structured_llm(Remediation).invoke(prompt)  # type: ignore[assignment]
    return {"remediation": out.remediation, "draft_reply": out.draft_reply}
