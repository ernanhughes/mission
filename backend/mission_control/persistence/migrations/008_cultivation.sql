-- MC-CULTIVATION-01: persistent achievement paths, goal tracking and progress HUD.
-- Evidence model: GoalDefinition (intent), GoalItem (artefact), GoalMembership
-- (item-in-goal lifecycle), GoalMeasurement (metric observations), GoalEvent
-- (append-only history), GoalEvidence (verification references). Counts are
-- recomputed from stored rows; estimates are labelled, never invented.

CREATE TABLE IF NOT EXISTS cultivation_goals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    unit TEXT NOT NULL DEFAULT 'items',
    target_value REAL NOT NULL DEFAULT 100,
    measurement_type TEXT NOT NULL DEFAULT 'count',
    baseline_value REAL,
    baseline_note TEXT NOT NULL DEFAULT '',
    baseline_provenance TEXT NOT NULL DEFAULT 'none',
    qualifying_stage TEXT NOT NULL DEFAULT 'published',
    window_days INTEGER,
    priority INTEGER NOT NULL DEFAULT 100,
    state TEXT NOT NULL DEFAULT 'active',
    pinned INTEGER NOT NULL DEFAULT 0,
    pin_order INTEGER NOT NULL DEFAULT 100,
    privacy TEXT NOT NULL DEFAULT 'standard',
    completion_criteria TEXT NOT NULL DEFAULT '',
    milestones TEXT NOT NULL DEFAULT '[]',
    dependencies TEXT NOT NULL DEFAULT '[]',
    evidence_source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_goals_state
    ON cultivation_goals(state, pinned, pin_order);

CREATE TABLE IF NOT EXISTS cultivation_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'work',
    notes TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    provenance TEXT NOT NULL DEFAULT 'unclassified',
    source_application TEXT,
    source_project_id TEXT,
    source_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_items_title
    ON cultivation_items(title);

CREATE TABLE IF NOT EXISTS cultivation_memberships (
    item_id TEXT NOT NULL REFERENCES cultivation_items(id) ON DELETE CASCADE,
    goal_id TEXT NOT NULL REFERENCES cultivation_goals(id) ON DELETE CASCADE,
    stage TEXT NOT NULL DEFAULT 'idea',
    evidence_status TEXT NOT NULL DEFAULT 'none',
    quality_evidence TEXT NOT NULL DEFAULT '{}',
    qualified INTEGER NOT NULL DEFAULT 0,
    qualified_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (item_id, goal_id)
);

CREATE INDEX IF NOT EXISTS ix_cultivation_memberships_goal
    ON cultivation_memberships(goal_id, stage);

CREATE TABLE IF NOT EXISTS cultivation_measurements (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL REFERENCES cultivation_goals(id) ON DELETE CASCADE,
    value REAL NOT NULL,
    observed_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_measurements_goal
    ON cultivation_measurements(goal_id, observed_at);

CREATE TABLE IF NOT EXISTS cultivation_events (
    id TEXT PRIMARY KEY,
    goal_id TEXT REFERENCES cultivation_goals(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES cultivation_items(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_value TEXT,
    to_value TEXT,
    note TEXT NOT NULL DEFAULT '',
    evidence_ref TEXT,
    occurred_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_events_goal
    ON cultivation_events(goal_id, created_at);

CREATE TABLE IF NOT EXISTS cultivation_evidence (
    id TEXT PRIMARY KEY,
    goal_id TEXT REFERENCES cultivation_goals(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES cultivation_items(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'reference',
    reference TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cultivation_evidence_item
    ON cultivation_evidence(goal_id, item_id, created_at);
