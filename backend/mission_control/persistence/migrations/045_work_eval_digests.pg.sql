-- WORK-OUTCOME-01 W4: provenance digests on assessment rows (operational PG delta).
-- Additive only. Mirrors 045_work_eval_digests.sql. IF NOT EXISTS keeps this
-- safe on fresh installs (ORM baseline already declares the columns) and on
-- databases where 044 already carried them.
ALTER TABLE wo_claim_verifications ADD COLUMN IF NOT EXISTS source_digest TEXT NOT NULL DEFAULT '';
ALTER TABLE wo_requirement_assessments ADD COLUMN IF NOT EXISTS source_digest TEXT NOT NULL DEFAULT '';
