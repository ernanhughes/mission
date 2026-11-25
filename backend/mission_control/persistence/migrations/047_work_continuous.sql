-- WORK-OUTCOME-01 W6: requirement provenance, finding groups, eval state (SQLite legacy archive).
-- Additive only. Groups reference findings; staleness references assessments; nothing is deleted.
CREATE TABLE IF NOT EXISTS wo_requirement_sources (
    id TEXT PRIMARY KEY,
    requirement_id TEXT,
    episode_id TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'repo_doc',
    path TEXT NOT NULL DEFAULT '',
    revision TEXT NOT NULL DEFAULT '',
    digest TEXT NOT NULL DEFAULT '',
    authority_basis TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_reqsrc_episode
    ON wo_requirement_sources (episode_id, source_kind);
CREATE TABLE IF NOT EXISTS wo_finding_groups (
    id TEXT PRIMARY KEY,
    project_key TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    gap_class TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'minor',
    status TEXT NOT NULL DEFAULT 'open',
    member_count INTEGER NOT NULL DEFAULT 0,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wo_finding_group_members (
    group_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    PRIMARY KEY (group_id, finding_id)
);
CREATE INDEX IF NOT EXISTS idx_wo_fgmember_finding
    ON wo_finding_group_members (finding_id);
CREATE TABLE IF NOT EXISTS wo_eval_state (
    episode_id TEXT PRIMARY KEY,
    last_assessment_id TEXT NOT NULL DEFAULT '',
    stale INTEGER NOT NULL DEFAULT 0,
    stale_reason TEXT NOT NULL DEFAULT '',
    queue_status TEXT NOT NULL DEFAULT 'current',
    last_observed_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
