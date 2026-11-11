-- MC-QUALITY-02 Stage E: section-level evaluation identity.
-- Section scores reference the same table; whole-chapter rows keep
-- section_* NULL. Section identity is the planner's stable unit hash plus
-- the source hash of the section bytes; staleness is derived at read time.
ALTER TABLE quality_evaluations ADD COLUMN section_id TEXT;
ALTER TABLE quality_evaluations ADD COLUMN section_title TEXT;
ALTER TABLE quality_evaluations ADD COLUMN char_span TEXT DEFAULT '[]';
ALTER TABLE quality_evaluations ADD COLUMN section_sha TEXT;
CREATE INDEX IF NOT EXISTS idx_quality_evals_section
    ON quality_evaluations (chapter_id, section_id, created_at);
