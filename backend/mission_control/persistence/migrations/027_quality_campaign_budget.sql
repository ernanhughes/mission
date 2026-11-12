-- WRITER-QUALITY-03: optional catalog-estimate budget per campaign (0 = uncapped).
ALTER TABLE quality_campaigns ADD COLUMN max_cost_usd FLOAT DEFAULT 0.0 NOT NULL;
