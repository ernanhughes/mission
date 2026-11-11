-- MC-QUALITY-03A: durable whole-book evaluation campaigns.
-- One row per campaign; per-chapter observations stay in quality_evaluations.
-- Progress is persisted after every chapter so interrupted runs resume.
CREATE TABLE IF NOT EXISTS quality_campaigns (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    book_root TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'missing',
    chapter_selection TEXT NOT NULL DEFAULT '[]',
    fingerprints TEXT NOT NULL DEFAULT '{}',
    rubric_id TEXT NOT NULL DEFAULT 'manuscript-prose-v1',
    rubric_version INTEGER NOT NULL DEFAULT 1,
    prompt_version TEXT NOT NULL DEFAULT '1',
    model TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    total INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    remaining INTEGER NOT NULL DEFAULT 0,
    usage TEXT NOT NULL DEFAULT '{}',
    costs_unknown INTEGER NOT NULL DEFAULT 1,
    current_chapter TEXT,
    error TEXT,
    heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_quality_campaigns_project
    ON quality_campaigns (project_id, created_at);
