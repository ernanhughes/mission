-- WRITER-QUALITY-01: record the evaluation strategy per observation and campaign.
-- deterministic = no model; direct = one bounded review; bounded_judge = review + typed judgment.
ALTER TABLE quality_evaluations ADD COLUMN strategy TEXT DEFAULT 'direct' NOT NULL;
ALTER TABLE quality_campaigns ADD COLUMN strategy TEXT DEFAULT 'direct' NOT NULL;
