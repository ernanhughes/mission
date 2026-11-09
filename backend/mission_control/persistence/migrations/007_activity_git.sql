-- MC-ACTIVITY-01: persistent Git activity index and review evidence.
-- Activity collection (git history) is factual evidence; AI review is an
-- assessment of that evidence. Tables below store both separately.

ALTER TABLE discovery_roots ADD COLUMN display_name TEXT NOT NULL DEFAULT '';
ALTER TABLE discovery_roots ADD COLUMN category TEXT NOT NULL DEFAULT 'software';
ALTER TABLE discovery_roots ADD COLUMN git_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE discovery_roots ADD COLUMN last_git_sync_at TEXT;
ALTER TABLE discovery_roots ADD COLUMN last_git_error TEXT;

CREATE TABLE IF NOT EXISTS git_repositories (
    id TEXT PRIMARY KEY,
    root_path TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    git_dir TEXT NOT NULL DEFAULT '',
    repo_uid TEXT NOT NULL DEFAULT '',
    branch TEXT,
    head_sha TEXT,
    refs_snapshot TEXT NOT NULL DEFAULT '',
    accessible INTEGER NOT NULL DEFAULT 1,
    is_bare INTEGER NOT NULL DEFAULT 0,
    is_shallow INTEGER NOT NULL DEFAULT 0,
    last_indexed_at TEXT,
    backfill_complete INTEGER NOT NULL DEFAULT 0,
    backfill_before TEXT,
    total_commits INTEGER NOT NULL DEFAULT 0,
    has_agents INTEGER NOT NULL DEFAULT 0,
    has_description INTEGER NOT NULL DEFAULT 0,
    context_status TEXT NOT NULL DEFAULT 'missing',
    error TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_git_repositories_root
    ON git_repositories(root_path);
CREATE INDEX IF NOT EXISTS ix_git_repositories_uid
    ON git_repositories(repo_uid);

CREATE TABLE IF NOT EXISTS git_commits (
    repo_id TEXT NOT NULL REFERENCES git_repositories(id) ON DELETE CASCADE,
    sha TEXT NOT NULL,
    short_sha TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    author_name TEXT NOT NULL DEFAULT '',
    author_email TEXT NOT NULL DEFAULT '',
    author_ts INTEGER NOT NULL DEFAULT 0,
    author_tz TEXT NOT NULL DEFAULT '',
    committer_ts INTEGER NOT NULL DEFAULT 0,
    committer_tz TEXT NOT NULL DEFAULT '',
    parents TEXT NOT NULL DEFAULT '[]',
    branches TEXT NOT NULL DEFAULT '[]',
    files_changed INTEGER NOT NULL DEFAULT 0,
    insertions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    is_merge INTEGER NOT NULL DEFAULT 0,
    is_root INTEGER NOT NULL DEFAULT 0,
    reachable INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (repo_id, sha)
);

CREATE INDEX IF NOT EXISTS ix_git_commits_committer
    ON git_commits(committer_ts DESC, sha);
CREATE INDEX IF NOT EXISTS ix_git_commits_repo_time
    ON git_commits(repo_id, committer_ts DESC);
CREATE INDEX IF NOT EXISTS ix_git_commits_author
    ON git_commits(author_email, committer_ts DESC);

CREATE TABLE IF NOT EXISTS git_reviews (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES git_repositories(id) ON DELETE CASCADE,
    review_type TEXT NOT NULL DEFAULT 'single',
    commit_sha TEXT,
    base_sha TEXT,
    target_sha TEXT,
    commit_shas TEXT NOT NULL DEFAULT '[]',
    reviewer_type TEXT NOT NULL DEFAULT 'local',
    requested_model TEXT NOT NULL DEFAULT '',
    observed_model TEXT,
    model_route TEXT NOT NULL DEFAULT '',
    profile TEXT NOT NULL DEFAULT 'code',
    status TEXT NOT NULL DEFAULT 'queued',
    verdict TEXT,
    findings TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    tests TEXT NOT NULL DEFAULT '{}',
    architecture TEXT NOT NULL DEFAULT '{}',
    limitations TEXT NOT NULL DEFAULT '[]',
    prompt TEXT NOT NULL DEFAULT '',
    prompt_hash TEXT NOT NULL DEFAULT '',
    diff_hash TEXT NOT NULL DEFAULT '',
    context_fingerprint TEXT NOT NULL DEFAULT '',
    evidence_coverage TEXT NOT NULL DEFAULT '{}',
    usage_info TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS ix_git_reviews_repo_commit
    ON git_reviews(repo_id, commit_sha);
CREATE INDEX IF NOT EXISTS ix_git_reviews_status
    ON git_reviews(status, created_at);

CREATE TABLE IF NOT EXISTS git_review_feedback (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES git_reviews(id) ON DELETE CASCADE,
    rating TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_git_review_feedback_review
    ON git_review_feedback(review_id, created_at);
