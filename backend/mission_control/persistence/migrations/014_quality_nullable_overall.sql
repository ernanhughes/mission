-- MC-QUALITY-02 Stage C/H: terminal non-scored states (BLOCKED, ERROR,
-- RUNNING, CANCELLED, NOT_RUN) must be storable without fabricating scores.
-- SQLite cannot drop NOT NULL directly, so rebuild the table. Existing six
-- CURRENT rows are preserved verbatim.
CREATE TABLE quality_evaluations_new (
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
    overall REAL,
    aggregation_method TEXT NOT NULL DEFAULT 'mean_equal_weights_v1',
    dimensions TEXT NOT NULL DEFAULT '{}',
    findings TEXT NOT NULL DEFAULT '[]',
    uncertainty TEXT NOT NULL DEFAULT '',
    limitations TEXT NOT NULL DEFAULT '[]',
    execution TEXT NOT NULL DEFAULT '{}',
    previous_evaluation_id TEXT REFERENCES quality_evaluations(id) ON DELETE SET NULL,
    supersedes TEXT,
    workbench_url TEXT,
    section_id TEXT,
    section_title TEXT,
    char_span TEXT DEFAULT '[]',
    section_sha TEXT,
    created_at TEXT NOT NULL
);
INSERT INTO quality_evaluations_new
    (id, project_id, book_id, chapter_id, source_path, chapter_revision,
     rubric_id, rubric_version, prompt_version, requested_model, actual_model,
     status, overall, aggregation_method, dimensions, findings, uncertainty,
     limitations, execution, previous_evaluation_id, supersedes, workbench_url,
     section_id, section_title, char_span, section_sha, created_at)
    SELECT id, project_id, book_id, chapter_id, source_path, chapter_revision,
     rubric_id, rubric_version, prompt_version, requested_model, actual_model,
     status, overall, aggregation_method, dimensions, findings, uncertainty,
     limitations, execution, previous_evaluation_id, supersedes, workbench_url,
     section_id, section_title, char_span, section_sha, created_at
    FROM quality_evaluations;
DROP TABLE quality_evaluations;
ALTER TABLE quality_evaluations_new RENAME TO quality_evaluations;
CREATE INDEX IF NOT EXISTS idx_quality_evals_project_chapter
    ON quality_evaluations (project_id, chapter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_quality_evals_revision
    ON quality_evaluations (chapter_id, chapter_revision);
CREATE INDEX IF NOT EXISTS idx_quality_evals_section
    ON quality_evaluations (chapter_id, section_id, created_at);
