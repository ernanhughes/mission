-- MC-QUALITY-03A: attribute campaign evaluations for resume/attribution.
ALTER TABLE quality_evaluations ADD COLUMN campaign_id TEXT REFERENCES quality_campaigns(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_quality_evals_campaign
    ON quality_evaluations (campaign_id, chapter_id);
