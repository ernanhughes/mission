-- WORK-OUTCOME-01 W4: evaluation domain (operational PostgreSQL delta).
-- Additive only. Mirrors 044_work_evaluation.sql.
CREATE TABLE IF NOT EXISTS wo_requirement_assessments (
    id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    verdict TEXT NOT NULL DEFAULT 'insufficient_evidence',
    rationale TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    method TEXT NOT NULL DEFAULT 'deterministic',
    evaluator TEXT NOT NULL DEFAULT '',
    rubric_version TEXT NOT NULL DEFAULT 'w4-v1',
    confidence TEXT NOT NULL DEFAULT 'weak',
    limitations TEXT NOT NULL DEFAULT '',
    missing_evidence TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_reqassess_req
    ON wo_requirement_assessments (requirement_id, verdict);
CREATE TABLE IF NOT EXISTS wo_claim_verifications (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    verdict TEXT NOT NULL DEFAULT 'reported_only',
    rationale TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    method TEXT NOT NULL DEFAULT 'deterministic',
    evaluator TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (claim_id, method, evaluator)
);
CREATE TABLE IF NOT EXISTS wo_episode_assessments (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    execution_verdict TEXT NOT NULL DEFAULT 'unknown',
    execution_rationale TEXT NOT NULL DEFAULT '',
    outcome_verdict TEXT NOT NULL DEFAULT 'unknown',
    outcome_rationale TEXT NOT NULL DEFAULT '',
    completion_verdict TEXT NOT NULL DEFAULT 'unknown',
    completion_rationale TEXT NOT NULL DEFAULT '',
    evaluator TEXT NOT NULL DEFAULT '',
    rubric_version TEXT NOT NULL DEFAULT 'w4-v1',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wo_findings (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    requirement_id TEXT,
    kind TEXT NOT NULL DEFAULT 'verification_gap',
    severity TEXT NOT NULL DEFAULT 'minor',
    status TEXT NOT NULL DEFAULT 'suspected',
    title TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    next_action TEXT NOT NULL DEFAULT '',
    closure_evidence TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wo_findings_episode
    ON wo_findings (episode_id, status);
CREATE TABLE IF NOT EXISTS wo_eval_runs (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'running',
    episodes_evaluated INTEGER NOT NULL DEFAULT 0,
    requirements_assessed INTEGER NOT NULL DEFAULT 0,
    claims_verified INTEGER NOT NULL DEFAULT 0,
    findings_raised INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
