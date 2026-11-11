-- MC-QUALITY-02: durable manuscript-quality evaluation history.
-- One row per evaluation observation; history is append-only. Staleness is
-- derived at read time (a newer CURRENT row on another revision supersedes
-- older rows), never by overwriting.
CREATE TABLE IF NOT EXISTS quality_evaluations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    chapter_id TEXT NOT NULL,
    source_path TEXT NOT NULL DEFAULT '',
    chapter_revision TEXT NOT NULL,
    rubric_id TEXT NOT NULL DEFAULT 'manuscript-prose-v1',
    rubric_version INTEGER NOT NULL DEFAULT 1,
    prompt_version TEXT NOT NULL DEFAULT '1',
    requested_model TEXT,
    actual_model TEXT,
    status TEXT NOT NULL DEFAULT 'CURRENT',
    overall REAL NOT NULL,
    aggregation_method TEXT NOT NULL DEFAULT 'mean_equal_weights_v1',
    dimensions TEXT NOT NULL DEFAULT '{}',
    findings TEXT NOT NULL DEFAULT '[]',
    uncertainty TEXT NOT NULL DEFAULT '',
    limitations TEXT NOT NULL DEFAULT '[]',
    execution TEXT NOT NULL DEFAULT '{}',
    previous_evaluation_id TEXT REFERENCES quality_evaluations(id) ON DELETE SET NULL,
    supersedes TEXT,
    workbench_url TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quality_evals_project_chapter
    ON quality_evaluations (project_id, chapter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_quality_evals_revision
    ON quality_evaluations (chapter_id, chapter_revision);
