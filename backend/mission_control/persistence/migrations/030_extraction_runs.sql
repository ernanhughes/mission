-- MC-QUALITY-04A-03: strategy extraction runs + source anchoring columns.
-- Append-only; historical claim rows keep anchor_method='none' (unanchored),
-- which must never be read as verified.

CREATE TABLE IF NOT EXISTS technical_extraction_runs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL,
    strategy TEXT NOT NULL DEFAULT 'whole_continuation',
    chapter_id TEXT NOT NULL,
    region_ids TEXT NOT NULL DEFAULT '[]',
    requested_limit INTEGER NOT NULL DEFAULT 40,
    returned_count INTEGER NOT NULL DEFAULT 0,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'NOT_RUN',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    model_id TEXT,
    prompt_version TEXT NOT NULL DEFAULT '1',
    source_revision TEXT NOT NULL DEFAULT '',
    manifest_hash TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_runs_campaign
    ON technical_extraction_runs (campaign_id, chapter_id);

ALTER TABLE technical_claims ADD COLUMN anchor_method TEXT NOT NULL DEFAULT 'none';
ALTER TABLE technical_claims ADD COLUMN source_char_start INTEGER;
ALTER TABLE technical_claims ADD COLUMN source_char_end INTEGER;
