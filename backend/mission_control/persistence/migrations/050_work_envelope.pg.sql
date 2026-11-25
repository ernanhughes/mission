-- WORK-OUTCOME-01 W8: prospective work envelopes + execution linkage (PostgreSQL).
-- Additive only. Envelope rows bind pre-authorized intent; link columns reference external evidence.
CREATE TABLE IF NOT EXISTS wo_work_envelopes (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 'work-envelope.v1',
    programme_id TEXT NOT NULL DEFAULT '',
    stage_id TEXT NOT NULL DEFAULT '',
    objective_ref TEXT NOT NULL DEFAULT '',
    requirement_refs TEXT NOT NULL DEFAULT '[]',
    repositories TEXT NOT NULL DEFAULT '[]',
    commission_digest TEXT NOT NULL DEFAULT '',
    authorization_ref TEXT NOT NULL DEFAULT '',
    acceptance_policy_ref TEXT NOT NULL DEFAULT '',
    parent_work_id TEXT,
    originating_findings TEXT NOT NULL DEFAULT '[]',
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    supersedes TEXT,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_envelopes_episode
    ON wo_work_envelopes (episode_id, status);
ALTER TABLE wo_execution_links ADD COLUMN IF NOT EXISTS session_id TEXT NOT NULL DEFAULT '';
ALTER TABLE wo_execution_links ADD COLUMN IF NOT EXISTS commit_sha TEXT NOT NULL DEFAULT '';
ALTER TABLE wo_execution_links ADD COLUMN IF NOT EXISTS test_receipt_ref TEXT NOT NULL DEFAULT '';
ALTER TABLE wo_execution_links ADD COLUMN IF NOT EXISTS review_ref TEXT NOT NULL DEFAULT '';
