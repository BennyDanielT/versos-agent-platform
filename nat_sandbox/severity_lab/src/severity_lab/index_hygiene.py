"""Index-hygiene SCAN — deterministic catalog scan that produces findings (NO LLM).

Detection is pure SQL over Postgres system views; the LLM earns no place here (more
reliable, faster, cheaper — "pick the right layer"). Each finding carries a deterministic
`risk` (gates autonomy later), the proposed DDL, and a rollback. Findings are written to
`index_findings` (autonomy gating + evals come in later steps).

Run standalone:
    .venv/Scripts/python.exe -m severity_lab.index_hygiene
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import asyncpg
from pydantic import Field

from nat.plugin_api import Builder
from nat.plugin_api import FunctionBaseConfig
from nat.plugin_api import FunctionInfo
from nat.plugin_api import register_function

logger = logging.getLogger(__name__)

# --- precision guards / risk thresholds ------------------------------------
_BIG_TABLE_ROWS = 10_000              # below this, seq scans are NORMAL → don't flag "missing"
_LARGE_INDEX_BYTES = 10 * 1024 * 1024 # ≥10 MB unused index = medium risk (worth more attention)
_BIG_MISSING_ROWS = 100_000          # very big table missing an index = medium risk
_MIN_UNUSED_AGE_DAYS = 7.0           # PRECISION GUARD: only call an index unused after watching it
                                     # this long — a newborn index legitimately has 0 scans.

# Record every currently-existing perf index, so we know when we FIRST saw it. New ones get
# first_seen=now() and are thus too young to be flagged until the window passes.
_RECORD_SEEN_SQL = """
INSERT INTO index_seen (object_table, object_index)
SELECT s.relname, s.indexrelname
FROM   pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE  NOT i.indisunique AND NOT i.indisprimary
ON CONFLICT (object_table, object_index) DO NOTHING
"""

# --- detection queries (system catalogs) -----------------------------------
# pg_stat_user_indexes: one row per index, idx_scan = times used. pg_index: index flags.
# pg_indexes.indexdef: the CREATE statement (we keep it as the DROP's rollback).
# $1 = min age in days. The index_seen JOIN + age filter is the precision guard:
# an index must have been WATCHED for >= the window before we trust its 0 scans.
_UNUSED_SQL = """
SELECT s.relname AS tbl, s.indexrelname AS idx, s.idx_scan AS scans,
       pg_relation_size(s.indexrelid) AS size_bytes, pi.indexdef AS indexdef,
       round(EXTRACT(EPOCH FROM (now() - sn.first_seen_at)) / 86400.0, 1) AS age_days
FROM   pg_stat_user_indexes s
JOIN   pg_index   i  ON i.indexrelid = s.indexrelid
JOIN   pg_indexes pi ON pi.schemaname = s.schemaname AND pi.indexname = s.indexrelname
JOIN   index_seen sn ON sn.object_table = s.relname AND sn.object_index = s.indexrelname
WHERE  NOT i.indisunique AND NOT i.indisprimary AND s.idx_scan = 0
  AND  sn.first_seen_at <= now() - ($1 * interval '1 day')
ORDER  BY size_bytes DESC
"""

# pg_stat_user_tables: one row per table, seq_scan vs idx_scan, n_live_tup ≈ rows.
_MISSING_SQL = """
SELECT relname AS tbl, seq_scan, idx_scan, n_live_tup AS rows
FROM   pg_stat_user_tables
WHERE  seq_scan > idx_scan AND n_live_tup > $1
ORDER  BY seq_scan DESC
"""

# pg_index grouped by (table, column-set): the same indkey twice = duplicate.
_DUPLICATE_SQL = """
SELECT indrelid::regclass::text AS tbl, array_agg(indexrelid::regclass::text) AS idxs
FROM   pg_index
GROUP  BY indrelid, indkey
HAVING count(*) > 1
"""

# pg_index.indisvalid = false: a failed CREATE INDEX CONCURRENTLY left a stub.
_INVALID_SQL = """
SELECT indexrelid::regclass::text AS idx, indrelid::regclass::text AS tbl
FROM   pg_index WHERE NOT indisvalid
"""


def _unused_risk(size_bytes: int) -> str:
    return "medium" if size_bytes >= _LARGE_INDEX_BYTES else "low"


def _missing_risk(rows: int) -> str:
    return "medium" if rows >= _BIG_MISSING_ROWS else "low"


# Findings whose action is a DROP — destructive, high blast radius. Hard-held in CODE so
# they can NEVER reach 'auto', even if a policy row says so (defense in depth, like critical).
_DESTRUCTIVE = {"unused", "duplicate", "invalid"}


async def _decide_index_mode(pool: asyncpg.Pool, finding_type: str, risk: str) -> tuple[str, str]:
    """Autonomy gate: human-owned index_policy ceiling, enforced in code (mirrors triage)."""
    if await pool.fetchval("SELECT enabled FROM system_flags WHERE name = 'kill_switch'"):
        return "suggest", "Global kill switch engaged: all autonomy disabled."
    row = await pool.fetchrow(
        "SELECT approved_mode FROM index_policy WHERE finding_type = $1 AND risk = $2",
        finding_type, risk)
    if row is None:
        return "suggest", f"No policy for {finding_type}/{risk}; suggest-only."
    ceiling = row["approved_mode"]
    if finding_type in _DESTRUCTIVE and ceiling == "auto":   # hard cap: DROP never auto
        return "approved", (f"{finding_type}/{risk}: DROP is destructive — capped to 'approved' "
                            f"(a human commits the drop), never auto.")
    return ceiling, f"Segment {finding_type}/{risk} approved for '{ceiling}'."


async def _collect_findings(pool: asyncpg.Pool, min_unused_age_days: float) -> list[dict]:
    """Run every detector, return a flat list of finding dicts (no DB writes yet)."""
    findings: list[dict] = []

    for r in await pool.fetch(_UNUSED_SQL, min_unused_age_days):
        findings.append({
            "finding_type": "unused", "object_table": r["tbl"], "object_index": r["idx"],
            "detail": {"scans": r["scans"], "size_bytes": r["size_bytes"], "age_days": float(r["age_days"])},
            "risk": _unused_risk(r["size_bytes"]),
            "proposed_action": f"DROP INDEX CONCURRENTLY {r['idx']};",
            "rollback_action": (r["indexdef"] or "") + ";",   # recreate = the original CREATE
        })

    for r in await pool.fetch(_MISSING_SQL, _BIG_TABLE_ROWS):
        findings.append({
            "finding_type": "missing", "object_table": r["tbl"], "object_index": None,
            "detail": {"seq_scan": r["seq_scan"], "idx_scan": r["idx_scan"], "rows": r["rows"]},
            "risk": _missing_risk(r["rows"]),
            "proposed_action": (f"-- {r['tbl']} is scanned sequentially; inspect frequently-filtered "
                                f"columns (pg_stat_statements) and CREATE INDEX CONCURRENTLY on them."),
            "rollback_action": None,
        })

    for r in await pool.fetch(_DUPLICATE_SQL):
        keep, *drop = r["idxs"]
        findings.append({
            "finding_type": "duplicate", "object_table": r["tbl"], "object_index": ", ".join(drop),
            "detail": {"all": r["idxs"], "keep": keep},
            "risk": "low",
            "proposed_action": "; ".join(f"DROP INDEX CONCURRENTLY {d}" for d in drop) + ";",
            "rollback_action": None,
        })

    for r in await pool.fetch(_INVALID_SQL):
        findings.append({
            "finding_type": "invalid", "object_table": r["tbl"], "object_index": r["idx"],
            "detail": {"reason": "indisvalid = false (failed concurrent build)"},
            "risk": "low",
            "proposed_action": f"DROP INDEX CONCURRENTLY {r['idx']};  -- then rebuild cleanly",
            "rollback_action": None,
        })

    return findings


async def scan_indexes(database_url: str, min_unused_age_days: float = _MIN_UNUSED_AGE_DAYS) -> list[dict]:
    """Scan, refresh the OPEN findings (un-reviewed, un-applied), and return them."""
    pool = await asyncpg.create_pool(database_url)
    try:
        await pool.execute(_RECORD_SEEN_SQL)          # observe first (new indexes start the clock)
        findings = await _collect_findings(pool, min_unused_age_days)
        # Re-runnable: clear only OPEN findings; keep reviewed/applied history intact.
        await pool.execute("DELETE FROM index_findings WHERE decision IS NULL AND applied_at IS NULL")
        for f in findings:
            mode, reason = await _decide_index_mode(pool, f["finding_type"], f["risk"])
            f["recommended_mode"], f["mode_reason"] = mode, reason
            await pool.execute(
                """INSERT INTO index_findings
                   (finding_type, object_table, object_index, detail, risk,
                    proposed_action, rollback_action, recommended_mode, mode_reason)
                   VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9)""",
                f["finding_type"], f["object_table"], f["object_index"],
                json.dumps(f["detail"]), f["risk"], f["proposed_action"], f["rollback_action"],
                mode, reason)
        return findings
    finally:
        await pool.close()


async def apply_findings(database_url: str, allow_auto: bool = False) -> list[dict]:
    """Execute the proposed DDL for ELIGIBLE findings and record the outcome (efficacy).

    Eligible = a human approved it (`decision='approve'`), or it's `auto` and allow_auto=True.
    `suggest` is never applied here (a human runs it). DROP/CREATE CONCURRENTLY runs outside a
    transaction (asyncpg autocommit), so it won't lock the table.
    """
    pool = await asyncpg.create_pool(database_url)
    try:
        rows = await pool.fetch(
            """SELECT id, object_index, proposed_action FROM index_findings
               WHERE applied_at IS NULL
                 AND (decision = 'approve' OR ($1 AND recommended_mode = 'auto'))""",
            allow_auto)
        results = []
        for r in rows:
            # BEFORE: index size (the bytes we expect to reclaim on a DROP). Single index only.
            before = None
            if r["object_index"] and "," not in r["object_index"]:
                before = await pool.fetchval(
                    "SELECT pg_relation_size($1::regclass)", r["object_index"])
            try:
                await pool.execute(r["proposed_action"])           # the real DDL
                outcome = {"bytes_reclaimed": before or 0, "re_created": False}
                await pool.execute(
                    "UPDATE index_findings SET applied_at = now(), outcome = $2::jsonb WHERE id = $1",
                    r["id"], json.dumps(outcome))
                results.append({"index": r["object_index"], "status": "applied", "bytes": before or 0})
            except Exception as exc:                               # honest failure, recorded
                await pool.execute(
                    "UPDATE index_findings SET outcome = $2::jsonb WHERE id = $1",
                    r["id"], json.dumps({"error": str(exc)}))
                results.append({"index": r["object_index"], "status": f"failed: {exc}"})
        return results
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# NAT TOOL — register the scan as a first-class workflow (deterministic; NO LLM).
# ---------------------------------------------------------------------------
class IndexHygieneConfig(FunctionBaseConfig, name="index_hygiene"):
    """Config for the index-hygiene scan. No LLM — detection is pure SQL."""
    database_url: str = Field(
        default="postgresql://versos:versos@localhost:5432/versos",
        description="asyncpg DSN for the index_findings / index_policy / index_seen tables")
    min_unused_age_days: float = Field(
        default=_MIN_UNUSED_AGE_DAYS,
        description="observation window before a 0-scan index may be called unused")


@register_function(config_type=IndexHygieneConfig)
async def index_hygiene_function(config: IndexHygieneConfig, builder: Builder):
    """Scan Postgres for index-hygiene findings, risk-rate, gate autonomy, log them."""

    async def _scan(trigger: str = "") -> str:                 # input ignored; it scans the DB
        findings = await scan_indexes(config.database_url, config.min_unused_age_days)
        summary = [{"type": f["finding_type"], "table": f["object_table"],
                    "index": f["object_index"], "risk": f["risk"],
                    "mode": f.get("recommended_mode"), "action": f["proposed_action"]}
                   for f in findings]
        return json.dumps({"count": len(findings), "findings": summary}, indent=2)

    yield FunctionInfo.from_fn(_scan, description=(
        "Scan Postgres for index-hygiene findings (unused/missing/duplicate/invalid indexes), "
        "risk-rate each, recommend an autonomy mode, and log to index_findings. Returns JSON."))


async def _main() -> None:
    dsn = os.environ.get("DATABASE_URL", "postgresql://versos:versos@localhost:5432/versos")
    age = float(os.environ.get("MIN_UNUSED_AGE_DAYS", _MIN_UNUSED_AGE_DAYS))
    findings = await scan_indexes(dsn, age)
    print(f"{len(findings)} finding(s)  (unused window = {age} days):")
    for f in findings:
        idx = f["object_index"] or "-"
        print(f"  [{f['risk']:6}] {f.get('recommended_mode','?'):8} {f['finding_type']:9} {f['object_table']}.{idx}")


if __name__ == "__main__":
    asyncio.run(_main())
