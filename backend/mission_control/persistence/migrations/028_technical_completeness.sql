-- MC-QUALITY-03C: region coverage, evidence requirements, gaps, objectives.
-- Append-only assessment history. Coverage and satisfaction are derived
-- from these rows at read time; nothing here rewrites 03A/03B records.

CREATE TABLE IF NOT EXISTS technical_regions (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    chapter_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL DEFAULT '',
    source_hash TEXT NOT NULL DEFAULT '',
    char_start INTEGER NOT NULL DEFAULT 0,
    char_end INTEGER NOT NULL DEFAULT 0,
    byte_start INTEGER NOT NULL DEFAULT 0,
    byte_end INTEGER NOT NULL DEFAULT 0,
    unit_hash TEXT NOT NULL DEFAULT '',
    parent_region_id TEXT REFERENCES technical_regions(id) ON DELETE SET NULL,
    depth INTEGER NOT NULL DEFAULT 0,
    source_kind TEXT NOT NULL DEFAULT 'section',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_regions_chapter
    ON technical_regions (project_id, chapter_id, char_start);

CREATE TABLE IF NOT EXISTS technical_extraction_coverage (
    id TEXT PRIMARY KEY,
    region_id TEXT NOT NULL REFERENCES technical_regions(id) ON DELETE CASCADE,
    campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL,
    source_hash TEXT NOT NULL DEFAULT '',
    extractor_version TEXT NOT NULL DEFAULT 'technical-claim-v1',
    model_id TEXT,
    prompt_version TEXT NOT NULL DEFAULT '1',
    requested_limit INTEGER NOT NULL DEFAULT 40,
    returned_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    limit_reached INTEGER NOT NULL DEFAULT 0,
    truncated INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_coverage_region
    ON technical_extraction_coverage (region_id, created_at);

CREATE TABLE IF NOT EXISTS technical_evidence_requirements (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES technical_claims(id) ON DELETE CASCADE,
    requirement_key TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    requirement_type TEXT NOT NULL DEFAULT '',
    acceptance_rule TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    spec_version INTEGER NOT NULL DEFAULT 1,
    applicability TEXT NOT NULL DEFAULT 'UNDETERMINED',
    applicability_reason TEXT NOT NULL DEFAULT '',
    satisfaction TEXT NOT NULL DEFAULT 'NOT_ASSESSED',
    satisfaction_detail TEXT NOT NULL DEFAULT '',
    waived_reason TEXT NOT NULL DEFAULT '',
    campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_req_claim
    ON technical_evidence_requirements (claim_id, requirement_key);

CREATE TABLE IF NOT EXISTS technical_requirement_links (
    id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL REFERENCES technical_evidence_requirements(id) ON DELETE CASCADE,
    evidence_id TEXT REFERENCES technical_evidence(id) ON DELETE SET NULL,
    relation TEXT NOT NULL DEFAULT 'satisfies',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_reqlink_req
    ON technical_requirement_links (requirement_id, relation);

CREATE TABLE IF NOT EXISTS technical_claim_links (
    id TEXT PRIMARY KEY,
    from_claim_id TEXT NOT NULL REFERENCES technical_claims(id) ON DELETE CASCADE,
    to_claim_id TEXT NOT NULL REFERENCES technical_claims(id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'depends_on',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_claimlink_from
    ON technical_claim_links (from_claim_id, relation);

CREATE TABLE IF NOT EXISTS technical_gaps (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    chapter_id TEXT NOT NULL,
    claim_id TEXT REFERENCES technical_claims(id) ON DELETE SET NULL,
    requirement_id TEXT REFERENCES technical_evidence_requirements(id) ON DELETE SET NULL,
    gap_type TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    searched_scope TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN',
    priority_rationale TEXT NOT NULL DEFAULT '',
    campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_gaps_chapter
    ON technical_gaps (project_id, chapter_id, status);

CREATE TABLE IF NOT EXISTS technical_objectives (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    chapter_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'inferred',
    status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS technical_objective_claims (
    objective_id TEXT NOT NULL REFERENCES technical_objectives(id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL REFERENCES technical_claims(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'supports',
    created_at TEXT NOT NULL,
    PRIMARY KEY (objective_id, claim_id)
);
