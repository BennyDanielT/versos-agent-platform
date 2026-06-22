-- Pipeline self-healer persistence.
--   pipeline_jobs = a stand-in for versos-processor jobs (the thing the agent heals).
--   heal_log      = one row per healing attempt (decision log + eval dataset).
--   heal_policy   = human-owned autonomy ceiling per (fix_type, risk).

CREATE TABLE IF NOT EXISTS pipeline_jobs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_name    TEXT        NOT NULL,
    status      TEXT        NOT NULL,        -- queued | running | failed | done
    error_class TEXT,                        -- stale_lock | oom | transient | corrupt_input | NULL
    locked_by   TEXT,                        -- set when a stale lock is held
    attempts    INT         NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS heal_log (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id           BIGINT,
    job_name         TEXT,
    error_class      TEXT,
    diagnosis        TEXT,
    fix_type         TEXT,                   -- retry | clear_lock | scale | requeue | escalate
    risk             TEXT,
    recommended_mode TEXT,                   -- suggest | approved | auto
    mode_reason      TEXT,
    action_taken     TEXT,
    outcome          TEXT,                   -- resolved | failed | escalated
    attempts         INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- review (filled later by a human)
    decision         TEXT, reviewer TEXT, reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS heal_policy (
    fix_type      TEXT        NOT NULL,
    risk          TEXT        NOT NULL,
    approved_mode TEXT        NOT NULL DEFAULT 'suggest',
    updated_by    TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fix_type, risk)
);
INSERT INTO heal_policy (fix_type, risk, approved_mode, updated_by) VALUES
  ('retry',      'low',    'auto',     'seed'),   -- idempotent, safe → can auto
  ('clear_lock', 'low',    'approved', 'seed'),
  ('requeue',    'low',    'approved', 'seed'),
  ('scale',      'medium', 'approved', 'seed'),
  ('escalate',   'low',    'suggest',  'seed')    -- escalation always surfaces to a human
ON CONFLICT (fix_type, risk) DO NOTHING;

-- Seed broken jobs with DIFFERENT causes (so the agent's path varies), plus one healthy.
INSERT INTO pipeline_jobs (job_name, status, error_class, locked_by) VALUES
  ('transcode_batch_17', 'failed', 'stale_lock',    'worker-3'),
  ('embed_shard_04',     'failed', 'oom',           NULL),
  ('export_job_22',      'failed', 'transient',     NULL),
  ('ingest_feed_09',     'failed', 'corrupt_input', NULL),
  ('thumbnail_gen_55',   'done',   NULL,            NULL);
