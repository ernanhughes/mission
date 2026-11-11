-- MC-SCRIPTS-02 Phase B: configurable script registry with stable identity.
-- Additive only. Existing cultivation tables untouched. New tables live in the
-- same SQLite database (no new persistence technology). File existence never
-- implies completion: new records start at 'discovered' and only explicit
-- user action moves them to 'completed' with a durable timestamp.
CREATE TABLE IF NOT EXISTS script_records (
    id TEXT PRIMARY KEY,
    current_relpath TEXT NOT NULL,
    original_relpath TEXT NOT NULL,
    script_number INTEGER,
    title TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    file_size INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'discovered',
    archived INTEGER NOT NULL DEFAULT 0,
    missing INTEGER NOT NULL DEFAULT 0,
    discovered_at TEXT NOT NULL,
    last_seen_at TEXT,
    completed_at TEXT,
    review_status TEXT NOT NULL DEFAULT 'none',
    last_review_at TEXT,
    legacy_item_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_script_records_relpath
    ON script_records(current_relpath);
CREATE INDEX IF NOT EXISTS ix_script_records_number
    ON script_records(script_number);
CREATE INDEX IF NOT EXISTS ix_script_records_status
    ON script_records(status, archived, missing);
CREATE TABLE IF NOT EXISTS script_events (
    id TEXT PRIMARY KEY,
    script_id TEXT REFERENCES script_records(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_value TEXT,
    to_value TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_script_events_script
    ON script_events(script_id, created_at);
CREATE TABLE IF NOT EXISTS script_links (
    source_id TEXT NOT NULL REFERENCES script_records(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES script_records(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'possible_duplicate',
    confirmed INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, kind)
);
