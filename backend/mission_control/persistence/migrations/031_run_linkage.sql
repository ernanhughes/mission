-- MC-QUALITY-04A-04-00: claim-to-run linkage + run wall-time metering.
-- Blocker 4 (arm attribution for B1/B2 claim-level reconciliation) and
-- blocker 5 (per-call wall time, NOT_RECORDED in 04A-03E).
-- Append-only, nullable: historical rows keep NULL (unknown), which must
-- never be read as unattributed-by-design.

ALTER TABLE technical_claims ADD COLUMN extraction_run_id TEXT
    REFERENCES technical_extraction_runs(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_tech_claims_run
    ON technical_claims (extraction_run_id, chapter_id);

ALTER TABLE technical_extraction_runs ADD COLUMN duration_ms INTEGER;
ALTER TABLE technical_extraction_runs ADD COLUMN transport TEXT NOT NULL DEFAULT '';
