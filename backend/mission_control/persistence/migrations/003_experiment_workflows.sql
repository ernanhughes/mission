CREATE TABLE IF NOT EXISTS experiment_workflows (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    template TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    next_record_id TEXT REFERENCES integration_records(id) ON DELETE SET NULL,
    next_external_id TEXT NOT NULL,
    next_title TEXT NOT NULL,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    next_evidence TEXT NOT NULL DEFAULT '{}',
    proposal TEXT NOT NULL DEFAULT '{}',
    language_intention TEXT NOT NULL DEFAULT '{}',
    repository_path TEXT NOT NULL,
    baseline_commit TEXT NOT NULL,
    approved_scope TEXT NOT NULL DEFAULT '[]',
    approval_hash TEXT,
    approved_at TEXT,
    approved_by TEXT,
    worker_request_id TEXT,
    worker_status TEXT,
    worker_result TEXT NOT NULL DEFAULT '{}',
    patch TEXT NOT NULL DEFAULT '{}',
    result_commit TEXT,
    measurement TEXT NOT NULL DEFAULT '{}',
    review_execution_id TEXT,
    review_artifact_path TEXT,
    review_summary TEXT NOT NULL DEFAULT '{}',
    adverse_review INTEGER NOT NULL DEFAULT 0,
    final_decision TEXT,
    final_reason TEXT NOT NULL DEFAULT '',
    override_adverse INTEGER NOT NULL DEFAULT 0,
    failure TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_experiment_workflows_status
    ON experiment_workflows(status, created_at);

CREATE TABLE IF NOT EXISTS workflow_events (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES experiment_workflows(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    source_ref TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (workflow_id, sequence)
);

CREATE INDEX IF NOT EXISTS ix_workflow_events_workflow
    ON workflow_events(workflow_id, sequence);
