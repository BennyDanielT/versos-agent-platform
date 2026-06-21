-- Versos internal agent-ops platform — schema
--
-- Design notes (interview talking points):
--   * These are BUSINESS records and workflow state. Agent telemetry (token
--     counts, traces, prompt versions, intermediate reasoning) does NOT live
--     here — that goes to LangSmith / OTel. Postgres stores facts the business
--     cares about even if no agent existed.
--   * Every AI-written column is nullable: a row exists the moment a human or
--     pipeline creates it, and gets enriched later. The agent never blocks the
--     record from being created.
--   * `status` / `*_mode` columns are the human-in-the-loop seam:
--     suggest -> approved -> auto. The autonomy-graduation story, in data.

-- ===========================================================================
-- Feature 1: Support triage  (Option A — supervisor + specialists)
-- ===========================================================================
CREATE TABLE support_tickets (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id       TEXT        NOT NULL,
    complaint_text    TEXT        NOT NULL,

    -- AI-enriched (nullable until the triage agent runs)
    issue_category    TEXT,
    severity          TEXT,                 -- low | medium | high | critical
    ai_summary        TEXT,
    ai_remediation    TEXT,
    ai_confidence     REAL,                 -- 0..1, gates promotion eligibility

    -- human-in-the-loop seam
    status            TEXT        NOT NULL DEFAULT 'new',
                                            -- new | triaged_suggested | approved | resolved
    triage_mode       TEXT        NOT NULL DEFAULT 'suggest',
                                            -- suggest | approved | auto
    approved_by       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Worklist query: "show me open tickets, newest first" -> (status, created_at)
CREATE INDEX idx_tickets_status_created   ON support_tickets (status, created_at DESC);
-- Per-customer history (used by the auditor / copilot later)
CREATE INDEX idx_tickets_customer_created ON support_tickets (customer_id, created_at DESC);

-- ===========================================================================
-- Feature 2: Media enrichment  (Option B — parallel pipeline)
-- ===========================================================================
CREATE TABLE media_assets (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id       TEXT        NOT NULL,
    s3_uri            TEXT        NOT NULL,
    filename          TEXT        NOT NULL,
    duration_seconds  REAL,                 -- enrichment output
    language          TEXT,                 -- enrichment output
    keywords          TEXT[],               -- enrichment output (parallel branch)
    processing_status TEXT        NOT NULL DEFAULT 'uploaded',
                                            -- uploaded | enriching | enriched | failed
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pipeline worker poll: "what needs enriching, oldest first"
CREATE INDEX idx_assets_status_created ON media_assets (processing_status, created_at);

CREATE TABLE transcripts (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id          BIGINT      NOT NULL REFERENCES media_assets (id) ON DELETE CASCADE,
    transcript_text   TEXT        NOT NULL,
    confidence_score  REAL,                 -- 0..1, used by the auditor
    speaker_count     INT,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transcripts_asset ON transcripts (asset_id);

-- ===========================================================================
-- Feature 3: Quality auditor  (the trust layer)
-- ===========================================================================
CREATE TABLE audit_findings (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id      BIGINT      NOT NULL REFERENCES media_assets (id) ON DELETE CASCADE,
    finding_type  TEXT        NOT NULL,     -- empty_transcript | low_confidence |
                                            -- missing_language | duration_mismatch | ...
    severity      TEXT        NOT NULL,     -- low | medium | high
    description   TEXT        NOT NULL,
    detected_by   TEXT        NOT NULL DEFAULT 'rules',  -- rules | llm
    resolved      BOOLEAN     NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auditor worklist: "open findings, worst first"
CREATE INDEX idx_findings_open ON audit_findings (resolved, severity, created_at DESC);
CREATE INDEX idx_findings_asset ON audit_findings (asset_id);
