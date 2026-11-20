-- MC-PRAXIS-09: advisory preflight findings, execution configuration
-- provenance, and proposal ownership for safe test lifecycle.
-- Additive only. Preflight is advisory; it never changes execution eligibility.

ALTER TABLE praxis_proposals ADD COLUMN preflight_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE praxis_proposals ADD COLUMN execution_config_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE praxis_proposals ADD COLUMN ownership_kind TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE praxis_proposals ADD COLUMN owner TEXT NOT NULL DEFAULT '';
ALTER TABLE praxis_proposals ADD COLUMN withdrawn_at TEXT;
