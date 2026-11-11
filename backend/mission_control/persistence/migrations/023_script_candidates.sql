-- MC-SCRIPTS-06 Phase E3: Ascendance production and repeatable script creation.
-- Additive only. Candidates are versioned drafts with provenance; promotion
-- allocates the next safe filename and registers (never completes) the script.
CREATE TABLE IF NOT EXISTS script_candidates (
    id TEXT PRIMARY KEY,
    library_key TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT 'v1',
    kind TEXT NOT NULL DEFAULT 'ascendance',
    status TEXT NOT NULL DEFAULT 'draft',
    content TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    est_seconds INTEGER NOT NULL DEFAULT 0,
    validation TEXT NOT NULL DEFAULT '{}',
    critique TEXT NOT NULL DEFAULT '{}',
    source_manifest TEXT NOT NULL DEFAULT '{}',
    provenance TEXT NOT NULL DEFAULT '{}',
    parent_candidate_id TEXT,
    promoted_script_id TEXT,
    promoted_relpath TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_script_candidates_library
    ON script_candidates(library_key, status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS ix_script_candidates_title_version
    ON script_candidates(library_key, title, version);
