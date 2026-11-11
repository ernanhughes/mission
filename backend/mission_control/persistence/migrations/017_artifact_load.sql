-- ARTIFACT-EXPO-01 Stage 08: independent Artifact Load observations.
-- Append-only history, kept separate from the six-dimension prose-quality
-- scores in quality_evaluations. Staleness is derived at read time, never
-- by overwriting. Higher weighted_load means more confirmed burden (not a
-- 0-100 health score and never a percentage).
CREATE TABLE IF NOT EXISTS artifact_load_observations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL DEFAULT '',
    chapter_id TEXT NOT NULL,
    source_path TEXT NOT NULL DEFAULT '',
    chapter_revision TEXT NOT NULL,
    aggregation_version TEXT NOT NULL DEFAULT 'artifact-load-v1',
    detector_version TEXT NOT NULL DEFAULT 'expo-v1',
    status TEXT NOT NULL DEFAULT 'CURRENT',
    eligible_words INTEGER NOT NULL DEFAULT 0,
    evaluated_units INTEGER NOT NULL DEFAULT 0,
    total_candidates INTEGER NOT NULL DEFAULT 0,
    confirmed INTEGER NOT NULL DEFAULT 0,
    high INTEGER NOT NULL DEFAULT 0,
    medium INTEGER NOT NULL DEFAULT 0,
    low INTEGER NOT NULL DEFAULT 0,
    unreviewed INTEGER NOT NULL DEFAULT 0,
    invalid_evidence INTEGER NOT NULL DEFAULT 0,
    affected_regions INTEGER NOT NULL DEFAULT 0,
    findings_per_1k REAL,
    findings_per_100_units REAL,
    region_rate REAL,
    coverage_mechanical REAL NOT NULL DEFAULT 0.0,
    coverage_semantic REAL NOT NULL DEFAULT 0.0,
    weighted_load REAL,
    mechanical_pressure REAL,
    baseline_eligible_words INTEGER NOT NULL DEFAULT 0,
    revised_eligible_words INTEGER NOT NULL DEFAULT 0,
    findings TEXT NOT NULL DEFAULT '[]',
    regions TEXT NOT NULL DEFAULT '[]',
    limitations TEXT NOT NULL DEFAULT '[]',
    execution TEXT NOT NULL DEFAULT '{}',
    previous_observation_id TEXT REFERENCES artifact_load_observations(id) ON DELETE SET NULL,
    supersedes TEXT,
    workbench_url TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifact_load_project_chapter
    ON artifact_load_observations (project_id, chapter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_artifact_load_revision
    ON artifact_load_observations (chapter_id, chapter_revision);
