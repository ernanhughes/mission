# W5-OPERATIONAL-ACTIVATION-PLAN — From scratch to production, safely

Current state (verified 2026-11-24): operational `mc` is at schema v44 with
20 `wo_*` tables present and **zero rows** (pilot data lives only in scratch
DBs). 045 is written and tested but NOT yet applied operationally.

## Activation procedure (requires explicit authorization; not performed in W5)

1. **Verify**: `SELECT MAX(version) FROM schema_migrations` (expect 44);
   confirm `wo_*` tables exist and are empty of production rows
   (`SELECT COUNT(*) …` per table).
2. **Backup**: `pg_dump -h localhost -U mc -d mc -f <dest>` (password via
   PGPASSFILE/pgpass, never CLI); validate by restoring into a scratch DB.
3. **Stop writers**: stop the Mission Control backend (managed apps stay
   running by design; confirm no in-flight `wo_*` writes).
4. **Migrate**: start the backend normally — `apply_migrations` applies
   `045_work_eval_digests.pg.sql` (additive, `IF NOT EXISTS`-guarded).
   Confirm version 45 and that 041–044 tables are untouched in content.
5. **Health**: `/api/health`, `/api/work-evaluation/coverage`,
   `/api/work-observation/status`; expect empty-but-available (not errors).
6. **Populate**: run bounded observation → reconstruction → triage →
   deterministic extraction through the API/CLI in small windows (ai first);
   semantic steps only with an authorized budget. No bulk backfill.
7. **Verify**: spot-check counts against scratch-pilot expectations;
   confirm no auto-execution paths exist (evaluator has no write scope).

## Rollback

Drop nothing: 045 adds nullable-equivalent columns with defaults; rollback
is "stop backend, restore dump". Migrations 041–045 never alter or delete
existing tables. If 045 misbehaves, the backend from the pre-W5 build runs
unchanged against v44 (new columns are ignored by old code paths that do
not select them explicitly — ORM `select *` on missing columns WOULD fail;
prefer full restore over version skew).

## Post-activation

First open of Activity → Work Evaluation will show empty states with
reasons until the first observation/reconstruction run completes. That is
correct behaviour, not a failure to fix.
