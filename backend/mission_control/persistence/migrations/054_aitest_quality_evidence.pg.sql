-- AITEST-03: expose deterministic recommendations and verification gaps.
ALTER TABLE aitest_quality ADD COLUMN recommendations_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE aitest_quality ADD COLUMN verification_gaps INTEGER NOT NULL DEFAULT 0;
