-- MC-PROJECTS-QUALITY-02: evidence-backed software quality evaluation.
-- Additive only. Separate domain from manuscript (quality_*), technical
-- (technical_*) and website (website_post_*) evaluations: own tables, own
-- id namespaces, own rubric. History is append-only; freshness is derived
-- at read time, never by overwriting.
CREATE TABLE IF NOT EXISTS software_charters (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    purpose TEXT NOT NULL DEFAULT '',
    users TEXT NOT NULL DEFAULT '',
    capabilities TEXT NOT NULL DEFAULT '[]',
    interfaces TEXT NOT NULL DEFAULT '[]',
    acceptance TEXT NOT NULL DEFAULT '[]',
    non_goals TEXT NOT NULL DEFAULT '[]',
    constraints TEXT NOT NULL DEFAULT '[]',
    lifecycle TEXT NOT NULL DEFAULT '',
    dependencies TEXT NOT NULL DEFAULT '[]',
    verification_expectations TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    provenance TEXT NOT NULL DEFAULT '{}',
    supersedes TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_software_charters_project
    ON software_charters (project_id, revision);
CREATE TABLE IF NOT EXISTS software_evaluations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    charter_id TEXT,
    charter_revision INTEGER,
    repo_uid TEXT NOT NULL DEFAULT '',
    repo_path TEXT NOT NULL DEFAULT '',
    head_sha TEXT,
    evidence_fingerprint TEXT NOT NULL DEFAULT '',
    evidence_manifest TEXT NOT NULL DEFAULT '{}',
    rubric_id TEXT NOT NULL DEFAULT 'software-quality-v1',
    rubric_version INTEGER NOT NULL DEFAULT 1,
    prompt_version TEXT NOT NULL DEFAULT '1',
    requested_model TEXT,
    observed_model TEXT,
    model_route TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    overall REAL,
    max_attainable REAL NOT NULL DEFAULT 1000,
    coverage_percent REAL,
    dimensions TEXT NOT NULL DEFAULT '{}',
    uncertainty TEXT NOT NULL DEFAULT '',
    limitations TEXT NOT NULL DEFAULT '[]',
    execution TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    prompt_hash TEXT NOT NULL DEFAULT '',
    previous_evaluation_id TEXT REFERENCES software_evaluations(id) ON DELETE SET NULL,
    supersedes TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_software_evaluations_project
    ON software_evaluations (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_software_evaluations_fingerprint
    ON software_evaluations (project_id, evidence_fingerprint);
CREATE TABLE IF NOT EXISTS software_eval_reviews (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES software_evaluations(id) ON DELETE CASCADE,
    reviewer_model TEXT NOT NULL DEFAULT '',
    model_route TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    verdict TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    finding_verdicts TEXT NOT NULL DEFAULT '[]',
    usage_info TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_software_eval_reviews_eval
    ON software_eval_reviews (evaluation_id, created_at);
CREATE TABLE IF NOT EXISTS software_findings (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'medium',
    component TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    expected TEXT NOT NULL DEFAULT '',
    observed TEXT NOT NULL DEFAULT '',
    impact TEXT NOT NULL DEFAULT '',
    proposal TEXT NOT NULL DEFAULT '',
    verification_required TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    source_evaluations TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'proposed',
    resolution_evidence TEXT NOT NULL DEFAULT '[]',
    history TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_software_findings_fingerprint
    ON software_findings (project_id, fingerprint);
CREATE INDEX IF NOT EXISTS idx_software_findings_state
    ON software_findings (project_id, status, severity);
CREATE TABLE IF NOT EXISTS software_finding_reviews (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES software_findings(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    source_digest TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_software_finding_reviews_finding
    ON software_finding_reviews (finding_id, created_at);
CREATE TABLE IF NOT EXISTS software_prompts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    finding_ids TEXT NOT NULL DEFAULT '[]',
    scope TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    provenance TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_software_prompts_project
    ON software_prompts (project_id, created_at);
