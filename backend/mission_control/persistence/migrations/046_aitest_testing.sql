-- AITEST-02 R12: central testing visibility (additive only).
-- Projects register here; full inventory + receipts + issues follow.
CREATE TABLE IF NOT EXISTS aitest_projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    root TEXT NOT NULL DEFAULT '',
    remote_url TEXT NOT NULL DEFAULT '',
    mc_project_id TEXT NOT NULL DEFAULT '',
    integration_state TEXT NOT NULL DEFAULT 'observation',
    policy TEXT NOT NULL DEFAULT 'observe',
    aitest_version TEXT NOT NULL DEFAULT '',
    last_receipt_id TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS aitest_tests (
    project_id TEXT NOT NULL,
    logical_id TEXT NOT NULL,
    relpath TEXT NOT NULL DEFAULT '',
    class_name TEXT NOT NULL DEFAULT '',
    func_name TEXT NOT NULL DEFAULT '',
    duration_ms REAL NOT NULL DEFAULT 0,
    band TEXT NOT NULL DEFAULT 'UNASSESSED',
    lifecycle TEXT NOT NULL DEFAULT 'DISCOVERED',
    last_outcome TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (project_id, logical_id)
);
CREATE INDEX IF NOT EXISTS idx_aitest_tests_project ON aitest_tests(project_id, lifecycle);
CREATE TABLE IF NOT EXISTS aitest_receipts (
    execution_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    discovered INTEGER NOT NULL DEFAULT 0,
    executed INTEGER NOT NULL DEFAULT 0,
    passed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    quarantined INTEGER NOT NULL DEFAULT 0,
    deferred INTEGER NOT NULL DEFAULT 0,
    timed_out INTEGER NOT NULL DEFAULT 0,
    unobserved INTEGER NOT NULL DEFAULT 0,
    duration_ms REAL NOT NULL DEFAULT 0,
    receipt_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_aitest_receipts_project ON aitest_receipts(project_id, created_at);
CREATE TABLE IF NOT EXISTS aitest_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    test_logical_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'UNKNOWN',
    title TEXT NOT NULL DEFAULT '',
    detail_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_aitest_issues_project ON aitest_issues(project_id, status);
CREATE TABLE IF NOT EXISTS aitest_events_seen (
    event_id TEXT PRIMARY KEY,
    received_at TEXT NOT NULL DEFAULT ''
);
