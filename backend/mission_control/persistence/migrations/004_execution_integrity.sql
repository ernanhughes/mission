ALTER TABLE experiment_workflows ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0;
ALTER TABLE experiment_workflows ADD COLUMN cancelled_at TEXT;

CREATE TABLE IF NOT EXISTS language_observations (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES experiment_workflows(id) ON DELETE CASCADE,
    schema TEXT NOT NULL,
    template TEXT NOT NULL,
    intention_ref TEXT NOT NULL,
    subject TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '[]',
    measurement_method TEXT,
    evidence TEXT NOT NULL DEFAULT '[]',
    provenance TEXT NOT NULL DEFAULT '{}',
    uncertainty TEXT NOT NULL DEFAULT '[]',
    constraint_result TEXT NOT NULL,
    evaluation_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_language_observations_workflow
    ON language_observations(workflow_id, created_at);
