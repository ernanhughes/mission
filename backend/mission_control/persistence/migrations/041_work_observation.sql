-- WORK-OUTCOME-01 W1: work observation foundation (SQLite legacy archive).
-- Additive only. New tables, no alterations, no destructive statements.
-- Operational PostgreSQL upgrades use 041_work_observation.pg.sql; fresh PG
-- installs build these tables from the ORM metadata and record this version
-- as applied. Timestamps are TEXT ISO-8601; JSON columns are JSON-encoded TEXT.
CREATE TABLE IF NOT EXISTS wo_observation_sources (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    identity TEXT NOT NULL,
    fingerprint TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (kind, identity)
);
CREATE TABLE IF NOT EXISTS wo_observation_runs (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL DEFAULT 'opencode',
    status TEXT NOT NULL DEFAULT 'running',
    window_from_ms INTEGER NOT NULL DEFAULT 0,
    window_to_ms INTEGER NOT NULL DEFAULT 0,
    sessions_seen INTEGER NOT NULL DEFAULT 0,
    messages_seen INTEGER NOT NULL DEFAULT 0,
    parts_seen INTEGER NOT NULL DEFAULT 0,
    signals_produced INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wo_checkpoints (
    source_kind TEXT NOT NULL,
    cursor_key TEXT NOT NULL,
    cursor_value_ms INTEGER NOT NULL DEFAULT 0,
    tiebreak_id TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    PRIMARY KEY (source_kind, cursor_key)
);
CREATE TABLE IF NOT EXISTS wo_signals (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    source_kind TEXT NOT NULL DEFAULT 'opencode',
    source_ref TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    value_digest TEXT NOT NULL DEFAULT '',
    evidence_class TEXT NOT NULL DEFAULT 'inferred',
    provenance TEXT NOT NULL DEFAULT '{}',
    observed_at TEXT NOT NULL,
    UNIQUE (source_ref, signal_type, value_digest)
);
CREATE INDEX IF NOT EXISTS idx_wo_signals_type
    ON wo_signals (signal_type, observed_at);
CREATE INDEX IF NOT EXISTS idx_wo_signals_source
    ON wo_signals (source_ref);
