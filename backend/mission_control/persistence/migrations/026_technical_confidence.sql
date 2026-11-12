-- MC-QUALITY-03B: technical claim inventory, evidence and verification.
-- Append-only history. Staleness derived at read time by comparing stored
-- source_revision with the live manuscript; nothing is overwritten.
CREATE TABLE IF NOT EXISTS technical_claims (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    chapter_id TEXT NOT NULL,
    source_path TEXT NOT NULL DEFAULT '',
    source_revision TEXT NOT NULL,
    source_start_line INTEGER,
    source_end_line INTEGER,
    source_excerpt TEXT NOT NULL DEFAULT '',
    claim_text TEXT NOT NULL,
    normalized_assertion TEXT NOT NULL DEFAULT '',
    claim_type TEXT NOT NULL,
    epistemic_role TEXT NOT NULL,
    assumptions TEXT NOT NULL DEFAULT '[]',
    qualifications TEXT NOT NULL DEFAULT '[]',
    extraction_method TEXT NOT NULL DEFAULT 'llm_extract_v1',
    model_id TEXT,
    prompt_version TEXT NOT NULL DEFAULT '1',
    extraction_status TEXT NOT NULL DEFAULT 'CURRENT',
    quote_validated INTEGER NOT NULL DEFAULT 0,
    campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_claims_chapter
    ON technical_claims (project_id, chapter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tech_claims_revision
    ON technical_claims (chapter_id, source_revision);

CREATE TABLE IF NOT EXISTS technical_evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES technical_claims(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    source_location TEXT NOT NULL,
    source_revision TEXT NOT NULL DEFAULT '',
    source_span TEXT NOT NULL DEFAULT '',
    evidence_excerpt TEXT NOT NULL DEFAULT '',
    discovery_method TEXT NOT NULL DEFAULT '',
    verification_method TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'NOT_RUN',
    limitations TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_evidence_claim
    ON technical_evidence (claim_id, created_at);

CREATE TABLE IF NOT EXISTS technical_verifications (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES technical_claims(id) ON DELETE CASCADE,
    evidence_id TEXT REFERENCES technical_evidence(id) ON DELETE SET NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    spec_id TEXT NOT NULL DEFAULT '',
    spec_version INTEGER NOT NULL DEFAULT 1,
    model_id TEXT,
    prompt_version TEXT NOT NULL DEFAULT '',
    prompt_hash TEXT,
    token_usage TEXT NOT NULL DEFAULT 'unknown',
    input_tokens INTEGER,
    output_tokens INTEGER,
    campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech_verifications_claim
    ON technical_verifications (claim_id, created_at);

ALTER TABLE quality_campaigns ADD COLUMN assessment_type TEXT NOT NULL DEFAULT 'prose';
