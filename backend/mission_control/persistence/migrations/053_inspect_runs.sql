-- MC-INSPECT-04: operational inspection jobs (durable, cancellable runs).
-- Additive only. One row per requested Inspect CLI operation; reconciliation
-- happens on read (pid liveness), never by guessing. Failed/cancelled runs
-- never replace published Inspect outputs (jobs only read them).
CREATE TABLE IF NOT EXISTS inspect_runs (
    run_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL DEFAULT '',
    mission_application_id TEXT NOT NULL DEFAULT '',
    operation TEXT NOT NULL DEFAULT 'inspect',
    scope TEXT NOT NULL DEFAULT 'full',
    status TEXT NOT NULL DEFAULT 'queued',
    pid INTEGER,
    command TEXT NOT NULL DEFAULT '',
    log_path TEXT NOT NULL DEFAULT '',
    head_sha TEXT NOT NULL DEFAULT '',
    requested_at TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    exit_code INTEGER,
    validation_status TEXT NOT NULL DEFAULT '',
    result_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_inspect_runs_repo ON inspect_runs(repository_id, requested_at);
CREATE INDEX IF NOT EXISTS idx_inspect_runs_status ON inspect_runs(status);
CREATE INDEX IF NOT EXISTS idx_inspect_runs_app ON inspect_runs(mission_application_id, requested_at);
