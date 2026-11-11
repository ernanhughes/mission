-- MC-SCRIPTS-03 Phase C: root-scoped stable identity.
-- Additive. Existing records adopt the current library on next sync.
-- Different libraries may share a relative path without colliding.
ALTER TABLE script_records ADD COLUMN library_key TEXT NOT NULL DEFAULT '';
DROP INDEX IF EXISTS ix_script_records_relpath;
CREATE UNIQUE INDEX IF NOT EXISTS ix_script_records_library_relpath
    ON script_records(library_key, current_relpath);
CREATE INDEX IF NOT EXISTS ix_script_records_library
    ON script_records(library_key, status, archived, missing);
