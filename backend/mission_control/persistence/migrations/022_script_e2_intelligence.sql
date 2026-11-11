-- MC-SCRIPTS-05 Phase E2: whole-library intelligence.
-- Additive only. Batches, tags, and syntheses are new rows; reviews stay
-- append-only and scripts stay untouched. Synthesis freshness is derived
-- from source review fingerprints, never by overwriting history.
CREATE TABLE IF NOT EXISTS script_batches (
    id TEXT PRIMARY KEY,
    library_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    model TEXT NOT NULL DEFAULT '',
    rubric_version TEXT NOT NULL DEFAULT '',
    schema_version TEXT NOT NULL DEFAULT '',
    selection TEXT NOT NULL DEFAULT '{}',
    counts TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_script_batches_library
    ON script_batches(library_key, status, created_at);
CREATE TABLE IF NOT EXISTS script_batch_items (
    batch_id TEXT NOT NULL REFERENCES script_batches(id) ON DELETE CASCADE,
    script_id TEXT NOT NULL REFERENCES script_records(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    review_id TEXT,
    reused INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (batch_id, script_id)
);
CREATE TABLE IF NOT EXISTS script_tags (
    script_id TEXT NOT NULL REFERENCES script_records(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'ai',
    created_at TEXT NOT NULL,
    PRIMARY KEY (script_id, tag, origin)
);
CREATE TABLE IF NOT EXISTS library_syntheses (
    id TEXT PRIMARY KEY,
    library_key TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'full',
    status TEXT NOT NULL DEFAULT 'complete',
    manifest TEXT NOT NULL DEFAULT '{}',
    manifest_hash TEXT NOT NULL DEFAULT '',
    report TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_library_syntheses_library
    ON library_syntheses(library_key, kind, created_at);
