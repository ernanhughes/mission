-- WORK-OUTCOME-01 W7: corrective proposal domain (SQLite legacy archive).
-- Additive only. Proposals reference findings/requirements/episodes; nothing is deleted.
CREATE TABLE IF NOT EXISTS wo_proposals (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    group_id TEXT,
    project_key TEXT NOT NULL DEFAULT '',
    action_category TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    exclusions TEXT NOT NULL DEFAULT '',
    acceptance_criteria TEXT NOT NULL DEFAULT '',
    required_verification TEXT NOT NULL DEFAULT '',
    suggested_route TEXT NOT NULL DEFAULT '',
    cost_constraints TEXT NOT NULL DEFAULT '',
    risk TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    scope_hash TEXT NOT NULL DEFAULT '',
    closure_status TEXT NOT NULL DEFAULT 'open',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_proposals_episode
    ON wo_proposals (episode_id, status);
CREATE TABLE IF NOT EXISTS wo_proposal_findings (
    proposal_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    PRIMARY KEY (proposal_id, finding_id)
);
CREATE INDEX IF NOT EXISTS idx_wo_proposal_findings_finding
    ON wo_proposal_findings (finding_id);
CREATE TABLE IF NOT EXISTS wo_proposal_events (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    from_status TEXT NOT NULL DEFAULT '',
    to_status TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_proposal_events_proposal
    ON wo_proposal_events (proposal_id);
CREATE TABLE IF NOT EXISTS wo_requirement_confirmations (
    id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL,
    episode_id TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    amended_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_reqconf_req
    ON wo_requirement_confirmations (requirement_id);
CREATE TABLE IF NOT EXISTS wo_execution_links (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    route TEXT NOT NULL DEFAULT '',
    external_ref TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    cost_usd REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_execlinks_proposal
    ON wo_execution_links (proposal_id);
