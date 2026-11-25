-- WORK-OUTCOME-01 W4: provenance digests on assessment rows (follow-up delta).
-- Additive only. 044 is already applied on the operational database
-- (backend startup advanced it to v44 with 20 wo_* tables), so the new
-- source_digest columns ship here rather than by editing the applied 044.
ALTER TABLE wo_claim_verifications ADD COLUMN source_digest TEXT NOT NULL DEFAULT '';
ALTER TABLE wo_requirement_assessments ADD COLUMN source_digest TEXT NOT NULL DEFAULT '';
