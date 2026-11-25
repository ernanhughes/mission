-- WORK-OUTCOME-01 W3: intent domain (operational PostgreSQL delta).
-- Additive only. Mirrors 043_work_intent.sql.
CREATE TABLE IF NOT EXISTS wo_objectives (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    authority TEXT NOT NULL DEFAULT 'inferred',
    status TEXT NOT NULL DEFAULT 'current',
    version INTEGER NOT NULL DEFAULT 1,
    supersedes TEXT,
    source_digest TEXT NOT NULL DEFAULT '',
    extractor TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_objectives_episode
    ON wo_objectives (episode_id, status);
CREATE TABLE IF NOT EXISTS wo_requirements (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    objective_id TEXT,
    text TEXT NOT NULL DEFAULT '',
    authority TEXT NOT NULL DEFAULT 'ambiguous',
    mandatory INTEGER NOT NULL DEFAULT 1,
    kind TEXT NOT NULL DEFAULT 'functional',
    state TEXT NOT NULL DEFAULT 'proposed',
    version INTEGER NOT NULL DEFAULT 1,
    supersedes TEXT,
    source_digest TEXT NOT NULL DEFAULT '',
    extractor TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_requirements_episode
    ON wo_requirements (episode_id, authority);
CREATE TABLE IF NOT EXISTS wo_claims (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    claimant TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    source_ref TEXT NOT NULL DEFAULT '',
    qualified INTEGER NOT NULL DEFAULT 0,
    evidence_available INTEGER NOT NULL DEFAULT 0,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_claims_episode
    ON wo_claims (episode_id);
CREATE TABLE IF NOT EXISTS wo_evidence_links (
    id TEXT PRIMARY KEY,
    requirement_id TEXT,
    claim_id TEXT,
    evidence_kind TEXT NOT NULL DEFAULT '',
    evidence_ref TEXT NOT NULL DEFAULT '',
    source_digest TEXT NOT NULL DEFAULT '',
    method TEXT NOT NULL DEFAULT 'candidate',
    confidence TEXT NOT NULL DEFAULT 'weak',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_evidence_links_req
    ON wo_evidence_links (requirement_id);
CREATE TABLE IF NOT EXISTS wo_triage_results (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'AMBIGUOUS',
    method TEXT NOT NULL DEFAULT 'deterministic',
    reason TEXT NOT NULL DEFAULT '',
    queued_for_model INTEGER NOT NULL DEFAULT 0,
    run_id TEXT,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (session_id, run_id)
);
CREATE TABLE IF NOT EXISTS wo_extraction_runs (
    id TEXT PRIMARY KEY,
    episode_id TEXT,
    schema_version TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    extractor TEXT NOT NULL DEFAULT '',
    input_digest TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'accepted',
    error TEXT NOT NULL DEFAULT '',
    cost_usd REAL NOT NULL DEFAULT 0,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (input_digest, schema_version, prompt_version, extractor)
);
