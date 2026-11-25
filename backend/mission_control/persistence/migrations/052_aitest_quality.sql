-- AITEST-03: per-project quality assessment summaries (derived, additive).
CREATE TABLE IF NOT EXISTS aitest_quality (
    project_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT '',
    snapshot TEXT NOT NULL DEFAULT '',
    tests_evaluated INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '{}',
    redundancy_candidates INTEGER NOT NULL DEFAULT 0,
    coverage_percent REAL,
    mutations_attempted INTEGER NOT NULL DEFAULT 0,
    mutations_killed INTEGER NOT NULL DEFAULT 0,
    latest_at TEXT NOT NULL DEFAULT '',
    cost_ms REAL NOT NULL DEFAULT 0
);
