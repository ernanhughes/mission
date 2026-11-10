-- MC-CULTIVATION-03: project/application lifecycle and repository mastery.
-- All additive. Cultivation never writes Activity tables; Activity rows are
-- read by stable identity (git_repositories.id / repo_uid). Owner decisions
-- live here; source observations live here too, separately.

CREATE TABLE IF NOT EXISTS cultivation_repo_states (
    repo_id TEXT PRIMARY KEY,
    repo_uid TEXT NOT NULL DEFAULT '',
    qualification TEXT NOT NULL DEFAULT 'discovered',
    lifecycle_stage TEXT,
    classification TEXT NOT NULL DEFAULT 'unclassified',
    rationale TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '{}',
    decided_by TEXT NOT NULL DEFAULT 'undecided',
    decided_at TEXT,
    accessible INTEGER NOT NULL DEFAULT 1,
    last_seen_at TEXT,
    last_head TEXT,
    last_commit_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_repo_states_qualification
    ON cultivation_repo_states(qualification, classification);

CREATE TABLE IF NOT EXISTS cultivation_applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    lifecycle_stage TEXT NOT NULL DEFAULT 'idea',
    release_evidence TEXT NOT NULL DEFAULT '{}',
    completed_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cultivation_app_repos (
    app_id TEXT NOT NULL REFERENCES cultivation_applications(id) ON DELETE CASCADE,
    repo_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (app_id, repo_id)
);

CREATE INDEX IF NOT EXISTS ix_cultivation_app_repos_repo
    ON cultivation_app_repos(repo_id, app_id);
