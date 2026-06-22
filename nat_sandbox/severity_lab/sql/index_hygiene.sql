-- Index-hygiene agent persistence. Mirrors the triage design:
--   detection fills the TOP of the row; a human fills `decision` LATER; applying the
--   action fills `outcome` LATER. So this log doubles as the eval dataset.

CREATE TABLE IF NOT EXISTS index_findings (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- --- what the scan found (deterministic) ---
    finding_type     TEXT        NOT NULL,   -- unused | missing | duplicate | invalid | bloated
    object_table     TEXT        NOT NULL,   -- table the finding is about
    object_index     TEXT,                   -- index name (NULL for a missing-index finding)
    detail           JSONB,                  -- raw signal: scans, size_bytes, rows, columns…
    risk             TEXT        NOT NULL,    -- low | medium | high  (this GATES autonomy)
    proposed_action  TEXT,                   -- the DDL we'd run (CREATE/DROP/REINDEX …)
    rollback_action  TEXT,                   -- how to undo it (blast-radius control)

    -- --- autonomy decision (code-enforced, like triage) ---
    recommended_mode TEXT,                   -- suggest | approved | auto
    mode_reason      TEXT,
    detected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- --- human review (filled later; NULL until a human reviews) ---
    decision         TEXT,                   -- approve | reject
    reviewer         TEXT,
    reviewed_at      TIMESTAMPTZ,

    -- --- outcome (filled after the action runs = the efficacy / re-create signal) ---
    applied_at       TIMESTAMPTZ,
    outcome          JSONB                   -- before/after latency, bytes reclaimed, re_created?
);
CREATE INDEX IF NOT EXISTS idx_index_findings_detected ON index_findings (detected_at DESC);

-- Observation log: the FIRST time the scanner saw each index. "unused" requires an index
-- to have been watched for >= a window — a brand-new index legitimately has 0 scans, so
-- flagging it would be a false positive. This table is the time dimension that prevents it.
CREATE TABLE IF NOT EXISTS index_seen (
    object_table  TEXT        NOT NULL,
    object_index  TEXT        NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (object_table, object_index)
);

-- Autonomy policy per (finding_type, risk) — human-owned ceiling, code enforces.
-- Seeded conservative: only low-risk CREATE may ever auto; DROP is never auto (destructive).
CREATE TABLE IF NOT EXISTS index_policy (
    finding_type     TEXT        NOT NULL,
    risk             TEXT        NOT NULL,
    approved_mode    TEXT        NOT NULL DEFAULT 'suggest',  -- suggest | approved | auto
    updated_by       TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (finding_type, risk)
);
INSERT INTO index_policy (finding_type, risk, approved_mode, updated_by) VALUES
  ('missing',   'low',    'approved', 'seed'),   -- adding an index is reversible
  ('missing',   'medium', 'suggest',  'seed'),
  ('duplicate', 'low',    'approved', 'seed'),
  ('unused',    'low',    'suggest',  'seed'),    -- DROP is destructive → never auto
  ('unused',    'medium', 'suggest',  'seed')
ON CONFLICT (finding_type, risk) DO NOTHING;

-- ONLINE EFFICACY — did acting actually help? Measured from applied findings' outcomes.
--   bytes_reclaimed = space freed by drops; re_created = the OOPS signal (we dropped an
--   index then had to rebuild it). re_create_rate must be ~0 to ever trust auto-drop.
CREATE OR REPLACE VIEW index_action_metrics AS
SELECT finding_type,
       count(*) FILTER (WHERE applied_at IS NOT NULL)                       AS applied,
       coalesce(sum((outcome->>'bytes_reclaimed')::bigint)
                FILTER (WHERE applied_at IS NOT NULL), 0)                   AS bytes_reclaimed,
       count(*) FILTER (WHERE (outcome->>'re_created')::boolean)            AS re_created,
       round(avg(((outcome->>'re_created')::boolean)::int)
             FILTER (WHERE applied_at IS NOT NULL)::numeric, 3)            AS re_create_rate
FROM index_findings
GROUP BY finding_type;
