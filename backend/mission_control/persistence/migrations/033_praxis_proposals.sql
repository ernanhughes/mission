-- MC-PRAXIS-07: governed Praxis proposal import, approval and correlation.
-- Additive only. Praxis proposals are advisory artifacts until an identified
-- human approves the exact immutable snapshot; execution then goes through the
-- existing IntegrationService and every ActionSpec's own confirmation gates.
-- A proposal row never stores execution results: those remain authoritative in
-- integration_executions and are joined by execution_id.

CREATE TABLE IF NOT EXISTS praxis_proposals (
    proposal_key TEXT PRIMARY KEY,
    praxis_id TEXT NOT NULL,
    version TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    recipe_digest TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'imported',
    correlation_id TEXT NOT NULL UNIQUE,
    goal_id TEXT NOT NULL DEFAULT '',
    goal_source TEXT NOT NULL DEFAULT '',
    goal_title TEXT NOT NULL DEFAULT '',
    goal_provenance TEXT NOT NULL DEFAULT '',
    steps_json TEXT NOT NULL DEFAULT '[]',
    capability_versions_json TEXT NOT NULL DEFAULT '{}',
    pi_model TEXT NOT NULL DEFAULT '',
    protocol TEXT NOT NULL DEFAULT '',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    expected_benefits_json TEXT NOT NULL DEFAULT '[]',
    assumptions_json TEXT NOT NULL DEFAULT '[]',
    risks_json TEXT NOT NULL DEFAULT '[]',
    estimated_cost_json TEXT NOT NULL DEFAULT '{}',
    observed_composition_cost_usd REAL,
    acceptance_criteria_json TEXT NOT NULL DEFAULT '[]',
    acceptance_provenance TEXT NOT NULL DEFAULT '',
    validation_json TEXT NOT NULL DEFAULT '[]',
    approved_by TEXT,
    approved_at TEXT,
    approval_digest TEXT,
    rejected_by TEXT,
    rejected_at TEXT,
    rejection_reason TEXT,
    execution_id TEXT,
    execution_requested_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_praxis_proposals_status
    ON praxis_proposals (status, updated_at);
CREATE INDEX IF NOT EXISTS idx_praxis_proposals_goal
    ON praxis_proposals (goal_id);
CREATE INDEX IF NOT EXISTS idx_praxis_proposals_execution
    ON praxis_proposals (execution_id);
