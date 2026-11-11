-- MC-SCRIPTS-05 Phase E1: script intelligence foundation.
-- Additive only. Review history is append-only; CURRENT vs STALE is derived
-- at read time by comparing content hashes, never by overwriting.
-- Effectiveness columns are reserved metadata only: NULL/empty means
-- "not measured". No score is ever invented.
CREATE TABLE IF NOT EXISTS script_reviews (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL REFERENCES script_records(id) ON DELETE CASCADE,
    content_sha256 TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    route TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    assessment TEXT NOT NULL DEFAULT '{}',
    raw_response TEXT NOT NULL DEFAULT '',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_script_reviews_script
    ON script_reviews(script_id, created_at);
ALTER TABLE script_records ADD COLUMN usage_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE script_records ADD COLUMN personal_rating REAL;
ALTER TABLE script_records ADD COLUMN personal_target TEXT NOT NULL DEFAULT '';
ALTER TABLE script_records ADD COLUMN personal_effect TEXT NOT NULL DEFAULT '';
ALTER TABLE script_records ADD COLUMN last_used_at TEXT;
