-- WORK-OUTCOME-01 W2: episode reconstruction (SQLite legacy archive).
-- Additive only. New tables, no alterations, no destructive statements.
-- Operational PostgreSQL upgrades use 042_work_episodes.pg.sql; fresh PG
-- installs build these tables from the ORM metadata and record this version
-- as applied. No completion semantics here: status is reconstruction status
-- (candidate/established), never outcome completion.
CREATE TABLE IF NOT EXISTS wo_episodes (
    id TEXT PRIMARY KEY,
    project_key TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'cluster',
    status TEXT NOT NULL DEFAULT 'candidate',
    parent_id TEXT,
    first_seen_ms INTEGER NOT NULL DEFAULT 0,
    last_seen_ms INTEGER NOT NULL DEFAULT 0,
    source_digest TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_episodes_project
    ON wo_episodes (project_key, updated_at);
CREATE INDEX IF NOT EXISTS idx_wo_episodes_parent
    ON wo_episodes (parent_id);
CREATE TABLE IF NOT EXISTS wo_episode_associations (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    assoc_type TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'candidate',
    confidence TEXT NOT NULL DEFAULT 'weak',
    reason TEXT NOT NULL DEFAULT '',
    signals TEXT NOT NULL DEFAULT '[]',
    recon_version INTEGER NOT NULL DEFAULT 1,
    valid INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (episode_id, assoc_type, target_ref, method)
);
CREATE INDEX IF NOT EXISTS idx_wo_epassoc_episode
    ON wo_episode_associations (episode_id, valid);
CREATE INDEX IF NOT EXISTS idx_wo_epassoc_target
    ON wo_episode_associations (assoc_type, target_ref);
CREATE TABLE IF NOT EXISTS wo_recon_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'running',
    scope TEXT NOT NULL DEFAULT '{}',
    episodes_found INTEGER NOT NULL DEFAULT 0,
    associations_made INTEGER NOT NULL DEFAULT 0,
    unresolved_observations INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
