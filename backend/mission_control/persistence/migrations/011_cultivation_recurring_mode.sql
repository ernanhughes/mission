-- MC-CULTIVATION follow-up: weekly-cadence goals.
-- Adds an explicit recurring mode. Default 'daily' preserves the existing
-- per-day threshold semantics; 'period' measures total output in the window
-- (e.g. at least one new script per 7-day window).
ALTER TABLE cultivation_goals ADD COLUMN recurring_mode TEXT NOT NULL DEFAULT 'daily';
