-- WRITER-QUALITY-02: author decisions stored separately from AI judgments.
CREATE TABLE quality_reviews (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT REFERENCES quality_evaluations(id) ON DELETE CASCADE,
    finding_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT DEFAULT '' NOT NULL,
    reviewer TEXT DEFAULT '' NOT NULL,
    source_digest TEXT DEFAULT '' NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quality_reviews_eval
    ON quality_reviews (evaluation_id, finding_id);
