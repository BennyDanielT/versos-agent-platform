"""Index-hygiene + pipeline-healer business logic.

Two kinds of call live here:
  * READS (findings, jobs, logs, metrics, policy) — plain SQL over the shared pool.
    Deterministic, no NAT/LLM, unit-testable.
  * ACTIONS (scan, apply, heal) — delegate to the pure functions in the `severity_lab`
    package (the same code the standalone `nat run` uses), so the API and the CLI can
    never diverge. These create their own pool from the DSN, exactly like the CLI.

The autonomy story is identical to triage: the model/scan proposes, a human-owned policy
table + code decides the mode, every decision is logged, and destructive actions are held.
"""
import json

import asyncpg


# ---------------------------------------------------------------------------
# INDEX HYGIENE — reads
# ---------------------------------------------------------------------------
async def list_findings(pool: asyncpg.Pool, limit: int) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, finding_type, object_table, object_index, detail, risk, "
        "proposed_action, rollback_action, recommended_mode, mode_reason, "
        "detected_at, decision, reviewer, reviewed_at, applied_at, outcome "
        "FROM index_findings ORDER BY id DESC LIMIT $1", limit)
    return [_jsonable(r) for r in rows]


async def index_metrics(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch("SELECT * FROM index_action_metrics")
    return [dict(r) for r in rows]


async def index_policy(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch(
        "SELECT finding_type, risk, approved_mode, updated_by, updated_at "
        "FROM index_policy ORDER BY finding_type, risk")
    return [dict(r) for r in rows]


async def review_finding(pool: asyncpg.Pool, finding_id: int, decision: str,
                         reviewer: str, review_comment: str) -> bool:
    """Record a human approve/reject on a finding. Returns False if it didn't exist."""
    result = await pool.execute(
        "UPDATE index_findings SET decision=$2, reviewer=$3, reviewed_at=now() "
        "WHERE id=$1", finding_id, decision, reviewer)
    return not result.endswith("0")


# ---------------------------------------------------------------------------
# INDEX HYGIENE — actions (delegate to the package)
# ---------------------------------------------------------------------------
async def run_scan(dsn: str) -> list[dict]:
    from severity_lab.index_hygiene import scan_indexes
    return await scan_indexes(dsn)


async def apply_findings(dsn: str, allow_auto: bool) -> list[dict]:
    from severity_lab.index_hygiene import apply_findings as _apply
    return await _apply(dsn, allow_auto=allow_auto)


# ---------------------------------------------------------------------------
# PIPELINE HEALER — reads
# ---------------------------------------------------------------------------
async def list_jobs(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, job_name, status, error_class, locked_by, attempts, updated_at "
        "FROM pipeline_jobs ORDER BY id")
    return [dict(r) for r in rows]


async def heal_log(pool: asyncpg.Pool, limit: int) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, job_id, job_name, error_class, diagnosis, fix_type, risk, "
        "recommended_mode, mode_reason, action_taken, outcome, attempts, created_at "
        "FROM heal_log ORDER BY id DESC LIMIT $1", limit)
    return [dict(r) for r in rows]


async def heal_policy(pool: asyncpg.Pool) -> list[dict]:
    rows = await pool.fetch(
        "SELECT fix_type, risk, approved_mode, updated_by, updated_at "
        "FROM heal_policy ORDER BY fix_type, risk")
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# PIPELINE HEALER — actions (delegate to the package's LangGraph healer)
# ---------------------------------------------------------------------------
async def heal(dsn: str, job_ref: str) -> list[dict]:
    """Heal one job (numeric ref) or sweep every failed job. Returns per-job results."""
    from severity_lab.pipeline_healer import heal_job

    pool = await asyncpg.create_pool(dsn)
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
        final = await heal_job(dsn, jid)
        results.append({
            "job_id": jid, "job_name": final.get("job_name"),
            "error_class": final.get("error_class"), "diagnosis": final.get("diagnosis"),
            "fix_type": final.get("fix_type"), "risk": final.get("risk"),
            "mode": final.get("mode"), "mode_reason": final.get("mode_reason"),
            "outcome": final.get("outcome"), "attempts": final.get("attempts", 0),
            "log": final.get("log", []),
        })
    return results


# ---------------------------------------------------------------------------
def _jsonable(row: asyncpg.Record) -> dict:
    """asyncpg returns JSONB columns as strings; decode them so the API emits real JSON."""
    d = dict(row)
    for key in ("detail", "outcome"):
        if isinstance(d.get(key), str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d
