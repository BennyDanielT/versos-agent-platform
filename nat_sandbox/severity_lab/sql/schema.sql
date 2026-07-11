-- Triage agent persistence: two tables.
--   triage_log    = every decision the agent makes (business record + evals dataset).
--   triage_policy = the human-owned grant of how autonomous each segment may be.

-- ---------------------------------------------------------------------------
-- Every triage decision is logged here. `human_label` is filled in LATER by a
-- developer reviewing the decision — that column is what turns this log into an
-- evaluation dataset and a shadow-mode agreement signal.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS triage_log (
    id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    complaint_text           TEXT        NOT NULL,
    category                 TEXT,
    severity                 TEXT,
    confidence               REAL,
    summary                  TEXT,
    developer_remediation    JSONB,
    suggested_customer_reply TEXT,
    recommended_mode         TEXT,        -- suggest | approved | auto
    mode_reason              TEXT,
    model_name               TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- --- developer review (filled later; NULL until a human reviews) ---
    decision                 TEXT,         -- 'approve' | 'reject'
    final_remediation        JSONB,        -- the dev's corrected remediation (gold answer)
    final_customer_reply     TEXT,         -- the dev's edited customer-facing reply (what actually goes out)
    review_comment           TEXT,         -- why it was right/wrong
    reviewer                 TEXT,
    reviewed_at              TIMESTAMPTZ,

    -- --- client follow-up (lightweight re-open after a specialist replied) ---
    customer_followup        TEXT,         -- latest client message when they ask for another look

    -- --- customer feedback (filled later; the GROUND TRUTH for auto'd tickets where
    -- no dev reviews). CSAT on the reply that went out. NULL until feedback arrives. ---
    customer_satisfied       BOOLEAN,      -- TRUE/FALSE = customer happy with the response
    feedback_at              TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_triage_log_created ON triage_log (created_at DESC);

-- ---------------------------------------------------------------------------
-- Humans grant the MAX autonomy per (severity, category) segment. The agent
-- reads this; it never writes it. `approved_mode` is the ceiling; `min_confidence`
-- is the bar to reach that ceiling. Critical is hard-held in code regardless.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS triage_policy (
    severity        TEXT        NOT NULL,
    category        TEXT        NOT NULL,
    approved_mode   TEXT        NOT NULL DEFAULT 'suggest',  -- suggest | approved | auto
    min_confidence  REAL        NOT NULL DEFAULT 0.85,
    updated_by      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (severity, category)
);

-- Seed: conservative. Only a couple of low-impact segments may auto, and only at
-- high confidence. Everything not listed defaults to suggest (safest). Over time,
-- evals justify INSERTing/raising rows here.
INSERT INTO triage_policy (severity, category, approved_mode, min_confidence, updated_by) VALUES
  ('low',    'media_quality', 'auto',     0.85, 'seed'),
  ('low',    'bug',           'approved', 0.80, 'seed'),
  ('medium', 'media_quality', 'approved', 0.85, 'seed')
ON CONFLICT (severity, category) DO NOTHING;

-- ---------------------------------------------------------------------------
-- GUARDRAIL — global feature flags. `kill_switch` = the big red button: when
-- enabled, _decide_from_policy forces EVERY segment to 'suggest' instantly (no
-- redeploy). DB-backed so one UPDATE disables all autonomy fleet-wide.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_flags (
    name        TEXT        PRIMARY KEY,
    enabled     BOOLEAN     NOT NULL DEFAULT false,
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- kill_switch = disable ALL autonomy (force suggest). input_rail = run NeMo LLM input rail.
-- mask_input = Presidio-mask the complaint before LLM/DB (data minimization). All DB-backed so
-- they flip LIVE (no restart), checked per-request in the tool via _flag_enabled().
INSERT INTO system_flags (name, enabled, updated_by) VALUES
  ('kill_switch', false, 'seed'),
  ('input_rail',  false, 'seed'),
  ('mask_input',  false, 'seed')
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- ONLINE EVAL — per-segment metrics from the review log. This is the real
-- ground truth a human (or a promotion job) consults before raising a policy row.
--   accept_rate        = of REVIEWED tickets, fraction approved (online accuracy).
--   precision_eligible = of reviewed tickets ABOVE the segment's confidence bar,
--                        fraction approved. THIS is what gates `auto` (you only act
--                        on the confident slice). Bar = the policy min_confidence
--                        (default 0.85 if no policy row yet).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW segment_metrics AS
SELECT l.severity,
       l.category,
       count(*)                                            AS total,
       count(l.decision)                                   AS reviewed,
       count(*) FILTER (WHERE l.decision = 'approve')      AS approved,
       round(avg((l.decision = 'approve')::int)::numeric, 3) AS accept_rate,
       count(l.decision) FILTER (
           WHERE l.confidence >= coalesce(p.min_confidence, 0.85))   AS reviewed_eligible,
       round(avg((l.decision = 'approve')::int) FILTER (
           WHERE l.confidence >= coalesce(p.min_confidence, 0.85))::numeric, 3)
                                                            AS precision_eligible,
       -- customer-satisfaction signal (the label that survives auto mode, where
       -- decision is NULL because no dev reviewed). feedback = how many CSAT replies.
       count(l.customer_satisfied)                          AS feedback,
       round(avg(l.customer_satisfied::int)::numeric, 3)    AS satisfaction_rate
FROM triage_log l
LEFT JOIN triage_policy p ON p.severity = l.severity AND p.category = l.category
GROUP BY l.severity, l.category
ORDER BY l.severity, l.category;

-- Promotion readiness: applies the flip rule. A human promotes a segment to `auto`
-- only when it clears volume + accept-rate + precision bars (thresholds are knobs).
CREATE OR REPLACE VIEW promotion_readiness AS
SELECT *,
       (reviewed_eligible >= 20
        AND accept_rate >= 0.95
        AND precision_eligible >= 0.97)  AS eligible_for_auto
FROM segment_metrics;

-- ---------------------------------------------------------------------------
-- CALIBRATION — is the model's confidence honest? Bin reviewed tickets by
-- confidence; compare avg confidence vs actual accuracy (accept-rate) per bin =
-- the reliability-diagram data. ECE = weighted-average gap from the diagonal.
-- (Fixing miscalibration = a separate isotonic/Platt fit; these views MEASURE it.)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW calibration_bins AS
SELECT width_bucket(confidence, 0, 1, 10)                  AS bin,        -- 10 bins, width 0.1
       round(((width_bucket(confidence, 0, 1, 10) - 1) * 0.1)::numeric, 1) AS bin_low,
       count(*)                                            AS n,
       round(avg(confidence)::numeric, 3)                  AS avg_confidence,
       round(avg((decision = 'approve')::int)::numeric, 3) AS accuracy
FROM triage_log
WHERE decision IS NOT NULL AND confidence IS NOT NULL
GROUP BY 1, 2
ORDER BY 1;

CREATE OR REPLACE VIEW calibration_ece AS
SELECT round((sum(n * abs(avg_confidence - accuracy)) / nullif(sum(n), 0))::numeric, 4) AS ece
FROM calibration_bins;
