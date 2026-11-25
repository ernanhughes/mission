-- WORK-OUTCOME-01 W8: execution-linkage hardening (SQLite legacy archive).
-- Additive only. Gives execution links a real envelope parent.
ALTER TABLE wo_execution_links ADD COLUMN envelope_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_wo_execlinks_envelope
    ON wo_execution_links (envelope_id);
