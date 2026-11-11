-- MC-SCRIPTS-04 Phase D: organisation, safe renumbering, version relationships.
-- Additive only. Extends script_links with evidence/confidence; adds durable
-- migration manifests. No changes to file content or cultivation semantics.
ALTER TABLE script_links ADD COLUMN evidence TEXT NOT NULL DEFAULT '';
ALTER TABLE script_links ADD COLUMN confidence TEXT NOT NULL DEFAULT 'unconfirmed';
ALTER TABLE script_links ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS script_migrations (
    id TEXT PRIMARY KEY,
    library_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'preview',
    manifest TEXT NOT NULL DEFAULT '{}',
    manifest_hash TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    applied_at TEXT,
    rolled_back_at TEXT,
    error TEXT,
    report TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_script_migrations_library
    ON script_migrations(library_key, status, created_at);
