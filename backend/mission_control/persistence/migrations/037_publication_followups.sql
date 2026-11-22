-- MC-PUBLISH-03: governed follow-ups promoting blockers to explicit work.
-- Append-only history; closing never deletes. Re-checks compare the stored
-- fingerprint against fresh evidence without mutating the original row.
CREATE TABLE IF NOT EXISTS publication_followups (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    book_id TEXT NOT NULL DEFAULT '',
    evidence_type TEXT NOT NULL,
    source_reference TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL DEFAULT '',
    target_type TEXT NOT NULL DEFAULT 'task',
    target_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    reviewer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_publication_followups_project
    ON publication_followups (project_id, status, created_at);
