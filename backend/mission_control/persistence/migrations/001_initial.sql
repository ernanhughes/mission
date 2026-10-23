CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'supporting',
    icon TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0,
    display_order INTEGER NOT NULL DEFAULT 100,
    repository_path TEXT,
    additional_paths TEXT NOT NULL DEFAULT '[]',
    working_directory TEXT,
    documentation_paths TEXT NOT NULL DEFAULT '[]',
    output_paths TEXT NOT NULL DEFAULT '[]',
    integration_adapter TEXT,
    adapter_enabled INTEGER NOT NULL DEFAULT 0,
    adapter_config TEXT NOT NULL DEFAULT '{}',
    related_projects TEXT NOT NULL DEFAULT '[]',
    related_books TEXT NOT NULL DEFAULT '[]',
    outcomes TEXT NOT NULL DEFAULT '[]',
    dependencies TEXT NOT NULL DEFAULT '[]',
    control_policy TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT 'default',
    notes TEXT NOT NULL DEFAULT '',
    last_launch_success_at TEXT,
    last_launch_failure_at TEXT,
    last_failure_detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS launch_definitions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    launch_type TEXT NOT NULL DEFAULT 'none',
    executable TEXT,
    arguments TEXT NOT NULL DEFAULT '[]',
    working_directory TEXT,
    env_names TEXT NOT NULL DEFAULT '[]',
    browser_url TEXT,
    health_type TEXT NOT NULL DEFAULT 'none',
    health_url TEXT,
    expected_port INTEGER,
    is_primary INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 0,
    verified INTEGER NOT NULL DEFAULT 0,
    verification_note TEXT NOT NULL DEFAULT '',
    shutdown_behavior TEXT NOT NULL DEFAULT 'terminate',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_launch_definitions_application
    ON launch_definitions(application_id);

CREATE TABLE IF NOT EXISTS process_instances (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    launch_definition_id TEXT REFERENCES launch_definitions(id) ON DELETE SET NULL,
    pid INTEGER,
    create_time REAL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    exit_code INTEGER,
    log_path TEXT,
    working_directory TEXT,
    command_preview TEXT,
    owned INTEGER NOT NULL DEFAULT 1,
    reattached INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS ix_process_instances_application
    ON process_instances(application_id, started_at);

CREATE TABLE IF NOT EXISTS health_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    process_instance_id TEXT,
    state TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'health_check',
    observed_at TEXT NOT NULL,
    stale_after_seconds INTEGER NOT NULL DEFAULT 60
);

CREATE INDEX IF NOT EXISTS ix_health_observations_application
    ON health_observations(application_id, observed_at);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'project',
    status TEXT NOT NULL DEFAULT 'active',
    priority INTEGER NOT NULL DEFAULT 100,
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    display_order INTEGER NOT NULL DEFAULT 100,
    current_milestone TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    last_activity_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    current_milestone TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    manuscript_paths TEXT NOT NULL DEFAULT '[]',
    implementation_paths TEXT NOT NULL DEFAULT '[]',
    published_url TEXT,
    local_url TEXT,
    quality_review_state TEXT NOT NULL DEFAULT 'not_reviewed',
    last_activity_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    url TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL NOT NULL DEFAULT 0.0,
    evidence TEXT NOT NULL DEFAULT '[]',
    source_root TEXT NOT NULL DEFAULT '',
    is_git INTEGER NOT NULL DEFAULT 0,
    branch TEXT,
    commit_hash TEXT,
    last_commit_at TEXT,
    dirty INTEGER,
    accessible INTEGER NOT NULL DEFAULT 1,
    candidate INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_observed_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS project_repositories (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    repository_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'supporting',
    PRIMARY KEY (project_id, repository_id)
);

CREATE TABLE IF NOT EXISTS project_relationships (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_project_relationships_project
    ON project_relationships(project_id);

CREATE TABLE IF NOT EXISTS activity_events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    project_id TEXT,
    application_id TEXT,
    process_id TEXT,
    source TEXT NOT NULL DEFAULT 'mission-control',
    source_id TEXT,
    evidence_ref TEXT,
    provenance TEXT NOT NULL DEFAULT 'user',
    occurred_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS ix_activity_events_occurred
    ON activity_events(occurred_at);
CREATE INDEX IF NOT EXISTS ix_activity_events_project
    ON activity_events(project_id, occurred_at);

CREATE TABLE IF NOT EXISTS work_checkpoints (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    last_completed TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    blockers TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    milestone TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_work_checkpoints_project
    ON work_checkpoints(project_id, created_at);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    priority INTEGER NOT NULL DEFAULT 100,
    source TEXT NOT NULL DEFAULT 'user',
    due_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_tasks_project ON tasks(project_id, status);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '[]',
    source_application TEXT,
    source_ref TEXT,
    external_id TEXT,
    provenance TEXT NOT NULL DEFAULT 'derived_observation',
    review_state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    dedupe_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS ix_recommendations_project
    ON recommendations(project_id, review_state);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'accepted',
    source TEXT NOT NULL DEFAULT 'user',
    decided_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_decisions_project ON decisions(project_id, decided_at);

CREATE TABLE IF NOT EXISTS adapter_statuses (
    id TEXT PRIMARY KEY,
    adapter TEXT NOT NULL,
    application_id TEXT,
    project_id TEXT,
    available INTEGER NOT NULL DEFAULT 0,
    capabilities TEXT NOT NULL DEFAULT '[]',
    detail TEXT NOT NULL DEFAULT '',
    error TEXT,
    last_checked_at TEXT,
    stale_after_seconds INTEGER NOT NULL DEFAULT 300,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_adapter_statuses_project ON adapter_statuses(project_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_roots (
    path TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS briefings (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'deterministic',
    provider TEXT,
    model TEXT,
    status TEXT NOT NULL DEFAULT 'complete',
    content TEXT NOT NULL DEFAULT '',
    items TEXT NOT NULL DEFAULT '[]',
    observations TEXT NOT NULL DEFAULT '[]',
    error TEXT
);
