-- MC-PROJECTS-QUALITY-01 Phase 1 cutover: software project identity.
-- Additive only. Existing project ids, book rows, launch definitions, Git
-- history and reviews are untouched. Identity decisions are an audit trail:
-- automatic registration is idempotent and every owner decision is recorded.
ALTER TABLE repositories ADD COLUMN repo_uid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_repositories_repo_uid ON repositories (repo_uid);
ALTER TABLE projects ADD COLUMN origin TEXT NOT NULL DEFAULT 'curated';
UPDATE projects SET origin = 'seeded' WHERE id IN ('language', 'inference', 'math');
CREATE TABLE IF NOT EXISTS project_identity_decisions (
    id TEXT PRIMARY KEY,
    repo_uid TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL,
    path_norm TEXT NOT NULL,
    project_id TEXT,
    decision TEXT NOT NULL DEFAULT 'auto_registered',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_identity_decisions_path
    ON project_identity_decisions (path_norm);
CREATE INDEX IF NOT EXISTS idx_project_identity_decisions_uid
    ON project_identity_decisions (repo_uid);
