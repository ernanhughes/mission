-- MC-QUALITY-03D: publication readiness & release assurance.
-- Append-only assessment history. Gate results, issues, approvals and
-- calibration reviews reference immutable evidence; nothing here rewrites
-- 03A/03B/03C records.

CREATE TABLE IF NOT EXISTS publication_assessments (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    book_root TEXT NOT NULL DEFAULT '',
    policy_version TEXT NOT NULL DEFAULT 'publication-readiness-v1',
    technical_scope TEXT NOT NULL DEFAULT 'pilot',
    manuscript_fingerprint TEXT NOT NULL DEFAULT '',
    input_manifest_fingerprint TEXT NOT NULL DEFAULT '',
    chapter_count INTEGER NOT NULL DEFAULT 0,
    assessment_status TEXT NOT NULL DEFAULT 'NOT_YET_ASSESSED',
    freshness TEXT NOT NULL DEFAULT 'CURRENT',
    readiness_detail TEXT NOT NULL DEFAULT '',
    preflight_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pub_assess_project
    ON publication_assessments (project_id, created_at);

CREATE TABLE IF NOT EXISTS publication_preflights (
    id TEXT PRIMARY KEY,
    assessment_id TEXT REFERENCES publication_assessments(id) ON DELETE CASCADE,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    schema_id TEXT NOT NULL DEFAULT 'workbench-publication-preflight-v1',
    schema_version TEXT NOT NULL DEFAULT '',
    book_root TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT 'book',
    manuscript_fingerprint TEXT NOT NULL DEFAULT '',
    input_manifest_fingerprint TEXT NOT NULL DEFAULT '',
    chapters_found INTEGER NOT NULL DEFAULT 0,
    findings_count INTEGER NOT NULL DEFAULT 0,
    report_bytes INTEGER NOT NULL DEFAULT 0,
    report_path TEXT NOT NULL DEFAULT '',
    snapshot_consistent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'NOT_RUN',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pub_preflight_assessment
    ON publication_preflights (assessment_id, created_at);

CREATE TABLE IF NOT EXISTS publication_gate_results (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES publication_assessments(id) ON DELETE CASCADE,
    gate_id TEXT NOT NULL,
    gate_version INTEGER NOT NULL DEFAULT 1,
    gate_group TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT 'NOT_RUN',
    blocking INTEGER NOT NULL DEFAULT 0,
    waivable INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT '',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    limitations TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pub_gate_assessment
    ON publication_gate_results (assessment_id, gate_id);

CREATE TABLE IF NOT EXISTS publication_issues (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES publication_assessments(id) ON DELETE CASCADE,
    gate_id TEXT NOT NULL DEFAULT '',
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'advisory',
    verification_method TEXT NOT NULL DEFAULT 'deterministic',
    status TEXT NOT NULL DEFAULT 'OPEN',
    waiver_eligibility TEXT NOT NULL DEFAULT 'waivable',
    author_review_status TEXT NOT NULL DEFAULT 'pending',
    source_refs TEXT NOT NULL DEFAULT '[]',
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pub_issues_assessment
    ON publication_issues (assessment_id, status);

CREATE TABLE IF NOT EXISTS publication_approvals (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES publication_assessments(id) ON DELETE CASCADE,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    manuscript_fingerprint TEXT NOT NULL DEFAULT '',
    input_manifest_fingerprint TEXT NOT NULL DEFAULT '',
    policy_version TEXT NOT NULL DEFAULT 'publication-readiness-v1',
    accepted_limitation_ids TEXT NOT NULL DEFAULT '[]',
    freshness TEXT NOT NULL DEFAULT 'CURRENT',
    reviewer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pub_approvals_assessment
    ON publication_approvals (assessment_id, created_at);

CREATE TABLE IF NOT EXISTS publication_calibration_reviews (
    id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL REFERENCES technical_evidence_requirements(id) ON DELETE SET NULL,
    sample_version INTEGER NOT NULL DEFAULT 1,
    sample_reason TEXT NOT NULL DEFAULT '',
    claim_accurate INTEGER NOT NULL DEFAULT 0,
    requirement_applicable TEXT NOT NULL DEFAULT 'UNDETERMINED',
    necessary INTEGER NOT NULL DEFAULT 0,
    strictness_ok INTEGER NOT NULL DEFAULT 0,
    satisfied_by_evidence TEXT NOT NULL DEFAULT 'unknown',
    gap_justified INTEGER NOT NULL DEFAULT 0,
    priority_proportionate INTEGER NOT NULL DEFAULT 0,
    would_block INTEGER NOT NULL DEFAULT 0,
    qualification_sufficient INTEGER NOT NULL DEFAULT 0,
    duplicate_of TEXT NOT NULL DEFAULT '',
    verdict TEXT NOT NULL DEFAULT '',
    correction TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pub_calib_requirement
    ON publication_calibration_reviews (requirement_id, sample_version);
