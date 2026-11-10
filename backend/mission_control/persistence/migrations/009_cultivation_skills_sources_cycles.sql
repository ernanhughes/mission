-- MC-CULTIVATION-02: Skills, live sources, 100-day cycles.
-- All additive and backward compatible. Existing goals keep skill_id NULL
-- (shown as unassigned) until the user or seed assigns them. Live source
-- observations are stored separately from user-attested baselines; a source
-- going stale never replaces data with zero.

CREATE TABLE IF NOT EXISTS cultivation_skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT 'sprout',
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT NOT NULL DEFAULT '',
    pinned INTEGER NOT NULL DEFAULT 0,
    pin_order INTEGER NOT NULL DEFAULT 100,
    state TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_skills_state
    ON cultivation_skills(state, pinned, pin_order);

ALTER TABLE cultivation_goals ADD COLUMN skill_id TEXT REFERENCES cultivation_skills(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS cultivation_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'hugo_blog',
    skill_id TEXT REFERENCES cultivation_skills(id) ON DELETE SET NULL,
    goal_id TEXT REFERENCES cultivation_goals(id) ON DELETE SET NULL,
    path TEXT NOT NULL DEFAULT '',
    config TEXT NOT NULL DEFAULT '{}',
    last_sync_at TEXT,
    last_status TEXT NOT NULL DEFAULT 'never_synced',
    last_error TEXT,
    fingerprint TEXT NOT NULL DEFAULT '',
    observed TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_sources_goal
    ON cultivation_sources(goal_id, last_sync_at);

CREATE TABLE IF NOT EXISTS cultivation_cycles (
    id TEXT PRIMARY KEY,
    number INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    length_days INTEGER NOT NULL DEFAULT 100,
    start_date TEXT,
    snapshot_day INTEGER,
    snapshot_note TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'active',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cultivation_cycle_goals (
    cycle_id TEXT NOT NULL REFERENCES cultivation_cycles(id) ON DELETE CASCADE,
    goal_id TEXT NOT NULL REFERENCES cultivation_goals(id) ON DELETE CASCADE,
    PRIMARY KEY (cycle_id, goal_id)
);
