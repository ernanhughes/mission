-- MC-CULTIVATION-APPS-01: GitHub repository inventory snapshot.
-- All additive. Cultivation never mutates GitHub; this table is the local
-- read-only observation cache. Owner judgement (qualification, lifecycle,
-- classification, rationale) continues to live in cultivation_repo_states;
-- GitHub facts live here, keyed by the stable GitHub node id (not the name,
-- so renames never duplicate or lose history).

CREATE TABLE IF NOT EXISTS cultivation_github_repos (
    node_id TEXT PRIMARY KEY,
    numeric_id INTEGER,
    owner TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'PUBLIC',
    is_private INTEGER NOT NULL DEFAULT 0,
    is_fork INTEGER NOT NULL DEFAULT 0,
    is_archived INTEGER NOT NULL DEFAULT 0,
    language TEXT,
    languages TEXT NOT NULL DEFAULT '[]',
    topics TEXT NOT NULL DEFAULT '[]',
    default_branch TEXT,
    pushed_at TEXT,
    created_at_github TEXT,
    updated_at_github TEXT,
    missing INTEGER NOT NULL DEFAULT 0,
    observed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_cultivation_github_repos_full_name
    ON cultivation_github_repos(full_name);

CREATE INDEX IF NOT EXISTS ix_cultivation_github_repos_visibility
    ON cultivation_github_repos(visibility, is_archived);
