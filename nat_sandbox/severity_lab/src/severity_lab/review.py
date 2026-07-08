"""Developer review of a triaged ticket — the human-feedback half of the loop.

A dev approves or rejects the agent's suggestion (and, if rejecting, supplies the
corrected 'gold' remediation). This UPDATEs the existing triage_log row in place
(one review per ticket). That review data is what powers the eval metrics and,
ultimately, policy promotion.
"""
import json
import logging
from typing import Literal

import asyncpg
from pydantic import BaseModel, Field, ValidationError

from nat.plugin_api import Builder
from nat.plugin_api import FunctionBaseConfig
from nat.plugin_api import FunctionInfo
from nat.plugin_api import register_function

from .db import default_database_url

logger = logging.getLogger(__name__)


class ReviewTicketConfig(FunctionBaseConfig, name="review_ticket"):
    """Config for the developer-review tool."""
    database_url: str = Field(
        default_factory=default_database_url,
        description="asyncpg DSN for the triage_log table")


class ReviewInput(BaseModel):
    """What a reviewer submits (the UI will POST this as JSON)."""
    ticket_id: int
    decision: Literal["approve", "reject"]
    reviewer: str
    final_remediation: list[str] | None = None   # the dev's gold answer if rejecting
    review_comment: str = ""


@register_function(config_type=ReviewTicketConfig)
async def review_ticket_function(config: ReviewTicketConfig, builder: Builder):
    """Record a developer's review (approve/reject + corrected remediation) for a ticket."""

    pool = await asyncpg.create_pool(config.database_url)   # SETUP

    async def _review(review_json: str) -> str:
        # Validate the incoming payload (string in -> typed object).
        try:
            r = ReviewInput.model_validate_json(review_json)
        except ValidationError as exc:
            return json.dumps({"status": "error", "detail": str(exc)})

        # UPDATE the existing decision row in place.
        result = await pool.execute(
            """UPDATE triage_log
               SET decision = $2,
                   final_remediation = $3::jsonb,
                   review_comment = $4,
                   reviewer = $5,
                   reviewed_at = now()
               WHERE id = $1""",
            r.ticket_id, r.decision,
            json.dumps(r.final_remediation) if r.final_remediation is not None else None,
            r.review_comment, r.reviewer)

        # asyncpg returns e.g. "UPDATE 1" / "UPDATE 0" — surface whether a row matched.
        updated = result.endswith("1")
        return json.dumps({
            "status": "recorded" if updated else "ticket_not_found",
            "ticket_id": r.ticket_id, "decision": r.decision,
        })

    yield FunctionInfo.from_fn(
        _review,
        description=("Record a developer's review of a triaged ticket. Input is JSON: "
                     "{ticket_id, decision: approve|reject, reviewer, "
                     "final_remediation?: [..], review_comment?}."),
    )

    await pool.close()   # TEARDOWN
