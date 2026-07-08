"""Pipeline self-healer as a LangGraph StateGraph (wrapped by NAT in step 3).

Why a graph (not the deterministic index-hygiene pipeline): the PATH VARIES with the
diagnosis. stale_lock -> clear_lock; oom -> scale; transient -> retry; corrupt_input ->
escalate. Plus a retry CYCLE and a conditional escalate branch - control flow a straight
pipeline can't express. Same spine still wraps it: heal_policy autonomy gate (kill switch +
DROP-equivalent destructive fixes hard-held) and a heal_log decision log.

Run standalone:
    .venv/Scripts/python.exe -m severity_lab.pipeline_healer
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional, TypedDict

import asyncpg
from langgraph.graph import END, StateGraph
from pydantic import Field

from nat.plugin_api import Builder
from nat.plugin_api import FunctionBaseConfig
from nat.plugin_api import FunctionInfo
from nat.plugin_api import register_function

from .db import default_database_url

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2

# Deterministic diagnosis: error_class -> (fix_type, risk, human-readable reason).
# (An LLM could do fuzzy diagnosis from raw logs for unknown classes - this is the reliable core.)
_DIAGNOSIS = {
    "stale_lock":    ("clear_lock", "low",    "Stale lock from a dead worker; clear it and re-queue."),
    "oom":           ("scale",      "medium", "Worker ran out of memory; add capacity and re-queue."),
    "transient":     ("retry",      "low",    "Transient failure; a simple retry should clear it."),
    "corrupt_input": ("escalate",   "low",    "Corrupt input - no safe automated fix; escalate."),
}


class HealState(TypedDict, total=False):
    job_id: int
    job_name: str
    error_class: Optional[str]
    diagnosis: str
    fix_type: str
    risk: str
    mode: str
    mode_reason: str
    attempts: int
    outcome: str          # resolved | escalated | proposed | skipped
    log: list[str]


def _build_graph(pool: asyncpg.Pool):
    """Compile the healer graph. Nodes close over the DB pool."""

    async def detect(state: HealState) -> dict:
        row = await pool.fetchrow(
            "SELECT job_name, status, error_class, attempts FROM pipeline_jobs WHERE id = $1",
            state["job_id"])
        if row is None or row["status"] != "failed":
            return {"outcome": "skipped", "log": [f"job {state['job_id']} not failed; nothing to heal"]}
        return {"job_name": row["job_name"], "error_class": row["error_class"],
                "attempts": row["attempts"],
                "log": [f"detected failed job '{row['job_name']}' (error={row['error_class']})"]}

    async def diagnose(state: HealState) -> dict:
        fix_type, risk, dx = _DIAGNOSIS.get(
            state.get("error_class"), ("escalate", "low", "Unknown error class; escalate."))
        return {"fix_type": fix_type, "risk": risk, "diagnosis": dx,
                "log": state["log"] + [f"diagnosed -> {fix_type} ({dx})"]}

    async def gate(state: HealState) -> dict:
        if await pool.fetchval("SELECT enabled FROM system_flags WHERE name = 'kill_switch'"):
            return {"mode": "suggest", "mode_reason": "kill switch engaged",
                    "log": state["log"] + ["gate: kill switch -> suggest"]}
        row = await pool.fetchrow(
            "SELECT approved_mode FROM heal_policy WHERE fix_type = $1 AND risk = $2",
            state["fix_type"], state["risk"])
        mode = row["approved_mode"] if row else "suggest"
        return {"mode": mode, "mode_reason": f"{state['fix_type']}/{state['risk']} -> {mode}",
                "log": state["log"] + [f"gate: {state['fix_type']}/{state['risk']} -> {mode}"]}

    async def apply_fix(state: HealState) -> dict:
        ft, jid = state["fix_type"], state["job_id"]
        if ft == "clear_lock":
            await pool.execute("UPDATE pipeline_jobs SET locked_by = NULL, status = 'queued', "
                               "attempts = attempts + 1, updated_at = now() WHERE id = $1", jid)
        else:  # retry | requeue | scale -> recover the job back to the queue
            await pool.execute("UPDATE pipeline_jobs SET status = 'queued', "
                               "attempts = attempts + 1, updated_at = now() WHERE id = $1", jid)
        return {"attempts": state.get("attempts", 0) + 1,
                "log": state["log"] + [f"applied fix: {ft}"]}

    async def verify(state: HealState) -> dict:
        status = await pool.fetchval("SELECT status FROM pipeline_jobs WHERE id = $1", state["job_id"])
        if status != "failed":
            return {"outcome": "resolved", "log": state["log"] + [f"verify: status={status} -> resolved"]}
        return {"log": state["log"] + [f"verify: still failed (attempt {state['attempts']})"]}

    async def propose(state: HealState) -> dict:
        return {"outcome": "proposed",
                "log": state["log"] + [f"proposed '{state['fix_type']}' (mode={state['mode']}); awaiting human"]}

    async def escalate(state: HealState) -> dict:
        return {"outcome": "escalated", "log": state["log"] + ["escalated to a human"]}

    # --- routers (conditional edges) ---
    def after_detect(state: HealState):
        return END if state.get("outcome") == "skipped" else "diagnose"

    def after_gate(state: HealState):
        if state["fix_type"] == "escalate":
            return "escalate"
        return "apply_fix" if state["mode"] == "auto" else "propose"

    def after_verify(state: HealState):
        if state.get("outcome") == "resolved":
            return END
        return "apply_fix" if state["attempts"] < _MAX_ATTEMPTS else "escalate"

    g = StateGraph(HealState)
    for name, fn in [("detect", detect), ("diagnose", diagnose), ("gate", gate),
                     ("apply_fix", apply_fix), ("verify", verify),
                     ("propose", propose), ("escalate", escalate)]:
        g.add_node(name, fn)
    g.set_entry_point("detect")
    g.add_conditional_edges("detect", after_detect)
    g.add_edge("diagnose", "gate")
    g.add_conditional_edges("gate", after_gate)
    g.add_edge("apply_fix", "verify")
    g.add_conditional_edges("verify", after_verify)     # the retry cycle + escalate branch
    g.add_edge("propose", END)
    g.add_edge("escalate", END)
    return g.compile()


async def heal_job(database_url: str, job_id: int) -> dict:
    """Run the healer graph on one job and log the attempt to heal_log."""
    pool = await asyncpg.create_pool(database_url)
    try:
        app = _build_graph(pool)
        final: dict = await app.ainvoke({"job_id": job_id, "attempts": 0, "log": []})
        action = "escalate" if final.get("outcome") == "escalated" else final.get("fix_type")
        await pool.execute(
            """INSERT INTO heal_log (job_id, job_name, error_class, diagnosis, fix_type, risk,
                   recommended_mode, mode_reason, action_taken, outcome, attempts)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
            job_id, final.get("job_name"), final.get("error_class"), final.get("diagnosis"),
            final.get("fix_type"), final.get("risk"), final.get("mode"), final.get("mode_reason"),
            action, final.get("outcome"), final.get("attempts", 0))
        return final
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# NAT TOOL — wrap the LangGraph healer as a first-class NAT workflow.
# This is the "NAT + LangGraph" point: LangGraph expresses the control flow; NAT gives
# it config, the tool registry, tracing, evals, and guardrails around it.
# ---------------------------------------------------------------------------
class PipelineHealerConfig(FunctionBaseConfig, name="pipeline_healer"):
    """Config for the pipeline self-healer (a LangGraph graph wrapped by NAT)."""
    database_url: str = Field(
        default_factory=default_database_url,
        description="asyncpg DSN for pipeline_jobs / heal_log / heal_policy")


@register_function(config_type=PipelineHealerConfig)
async def pipeline_healer_function(config: PipelineHealerConfig, builder: Builder):
    """Heal failed pipeline jobs: detect -> diagnose -> gate -> fix/propose/escalate."""

    async def _heal(job_ref: str = "") -> str:               # digit = one job; else all failed
        pool = await asyncpg.create_pool(config.database_url)
        try:
            if job_ref.strip().isdigit():
                ids = [int(job_ref)]
            else:
                ids = [r["id"] for r in await pool.fetch(
                    "SELECT id FROM pipeline_jobs WHERE status = 'failed' ORDER BY id")]
        finally:
            await pool.close()
        results = []
        for jid in ids:
            final = await heal_job(config.database_url, jid)
            results.append({"job_id": jid, "job": final.get("job_name"),
                            "fix": final.get("fix_type"), "mode": final.get("mode"),
                            "outcome": final.get("outcome")})
        return json.dumps({"healed": results}, indent=2)

    yield FunctionInfo.from_fn(_heal, description=(
        "Detect failed pipeline jobs, diagnose the cause, and heal/propose/escalate per the "
        "heal_policy autonomy gate. Input: a job id, or empty to sweep all failed. Returns JSON."))


async def _main() -> None:
    dsn = os.environ.get("DATABASE_URL", "postgresql://versos:versos@localhost:5432/versos")
    pool = await asyncpg.create_pool(dsn)
    # reset demo jobs to failed so the run is repeatable
    await pool.execute("""UPDATE pipeline_jobs SET status='failed', attempts=0,
                          locked_by = CASE WHEN error_class='stale_lock' THEN 'worker-3' END
                          WHERE error_class IS NOT NULL""")
    ids = [r["id"] for r in await pool.fetch("SELECT id FROM pipeline_jobs WHERE status='failed' ORDER BY id")]
    await pool.close()
    for jid in ids:
        final = await heal_job(dsn, jid)
        print(f"\njob {jid} -> {final.get('outcome', '?').upper()}")
        for line in final["log"]:
            print(f"    {line}")


if __name__ == "__main__":
    asyncio.run(_main())
