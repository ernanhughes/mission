CREATE TABLE IF NOT EXISTS integration_records (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT '',
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    source_version TEXT,
    source_timestamp TEXT,
    observed_at TEXT NOT NULL,
    stale_after_seconds INTEGER NOT NULL DEFAULT 900,
    evidence TEXT NOT NULL DEFAULT '[]',
    data TEXT NOT NULL DEFAULT '{}',
    search_text TEXT NOT NULL DEFAULT '',
    current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (application_id, resource_type, external_id)
);

CREATE INDEX IF NOT EXISTS ix_integration_records_app_type
    ON integration_records(application_id, resource_type, current);
CREATE INDEX IF NOT EXISTS ix_integration_records_project
    ON integration_records(project_id);

CREATE TABLE IF NOT EXISTS integration_decisions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    sync_state TEXT NOT NULL DEFAULT 'local_only',
    source_decision_id TEXT,
    decided_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_integration_decisions_resource
    ON integration_decisions(application_id, resource_type, external_id, decided_at);

CREATE TABLE IF NOT EXISTS integration_executions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    parameters TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    risk TEXT NOT NULL DEFAULT 'read_only',
    approval_required INTEGER NOT NULL DEFAULT 0,
    approved_at TEXT,
    started_at TEXT,
    ended_at TEXT,
    exit_code INTEGER,
    output TEXT NOT NULL DEFAULT '',
    error TEXT,
    result TEXT NOT NULL DEFAULT '{}',
    artifact_ref TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_integration_executions_app
    ON integration_executions(application_id, created_at);
