-- AITEST-02D-UI: durable, cancellable testing executions requested from the UI.
-- Additive only.
CREATE TABLE IF NOT EXISTS aitest_runs (
    run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    pid INTEGER,
    command TEXT NOT NULL DEFAULT '',
    requested_at TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    exit_code INTEGER,
    receipt_execution_id TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT '',
    counts_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    log_path TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_aitest_runs_project ON aitest_runs(project_id, requested_at);
CREATE INDEX IF NOT EXISTS idx_aitest_runs_status ON aitest_runs(status);
