# MC-POSTGRES-01 — Complete Mission Control PostgreSQL Migration — Report

## Migration summary

- Source database location: `C:\Projects\mission\data\mission_control.db` (SQLite).
- Target database identity: host `localhost:5432`, database `mc`, user `mc`
  (PostgreSQL 16.8; credentials via `MC_DSN` only — redacted everywhere).
- Number of source tables: **90** (89 application + `schema_migrations`).
- Number of migrated tables: **89** + migration metadata (version 40).
- Total source records: **146465** (146426 operational + 39 version rows).
- Total imported records: **146465** (all preserved; no drops, no dedup).
- Number of verified tables: **89/89 OK** (counts + PK sets + canonical content).
- Number of unexplained discrepancies: **0**.
- Number of transformed records: **0 content transformations**; two documented
  type widenings with values preserved (`script_records.mtime_ns/file_size`
  and `process_instances.exit_code` INT4→BIGINT).
- Backup status: SQLite final snapshot `data/backups/mission_control-pre-pg-migration-FINAL-20261124T090600Z.db`
  (54,579,200 bytes, sha256 `ef3c9e4e…199b6df0`, integrity ok, FK clean);
  PostgreSQL dump `data/backups/mc-pg-pre-cutover-20261124.dump` (39,605,663
  bytes) restore-validated into scratch DB `mc_verify` (dropped after check).
- Migration status: **complete and reconciled**.
- Cutover status: **complete** — Mission Control running on PostgreSQL;
  SQLite retained read-only (verified untouched post-cutover).

## Application changes

- `backend/mission_control/config.py` — `MC_DSN` as authoritative config
  (`MC_DSN` > `MISSION_CONTROL_DATABASE_URL` > SQLite fallback for tests only),
  `normalize_database_url` (libpq→`postgresql+psycopg`), `DatabaseConfigurationError`,
  `is_postgres_url`, redacted-URL helper, `database_backend` property. No
  service constructs its own connection string anymore.
- `backend/mission_control/persistence/db.py` — PG engine path (Psycopg 3,
  pool 5+5, `pool_pre_ping`, timeouts), SQLite path unchanged (PRAGMAs kept
  only for sqlite), `backend`/`is_postgres`/`health_check`.
- `backend/mission_control/persistence/migrations.py` — dual-backend runner:
  legacy `NNN_*.sql` for SQLite; PG baseline from ORM metadata bound to the
  highest legacy version + `NNN_*.pg.sql` deltas; identical
  `schema_migrations` semantics.
- `backend/mission_control/persistence/migrations/040_script_bigint.pg.sql` —
  new PG delta (BIGINT widenings).
- `backend/mission_control/models.py` — three columns `Integer`→`BigInteger`
  (`script_records.mtime_ns/file_size`, `process_instances.exit_code`).
- `backend/mission_control/main.py` — startup DB connectivity check, PG
  enforcement (fails fast without `MC_DSN` outside pytest), redacted startup log.
- `backend/mission_control/api/health.py` — `/api/health` unchanged shape +
  `/api/diagnostics/database` (backend, connectivity, version, pool, redacted
  URL, error category; no credentials/records).
- `backend/mission_control/processes/manager.py` — health-observation
  persistence also recognizes PG transient errors (deadlock/serialization/
  connection) as busy-DB `Conflict`, so the monitor loop logs and continues
  instead of misreporting app health. No blind retries.
- `scripts/migrate_sqlite_to_postgres.py` — new reusable utility
  (`--inspect/--dry-run/--execute/--verify`, backup gates, FK-ordered import,
  sequence repair, reconciliation, resume/refuse semantics).
- `backend/tests/test_postgres_integration.py` — new PG suite (11 tests).
- Dependency changes: none required (`psycopg[binary]` already declared).
- SQLite-specific code retained: PRAGMA listeners (sqlite path only),
  read-only `sqlite3` access to external OpenCode/Next snapshots, isolated
  sqlite unit tests, migration-source reader.

## Data verification

- Per-table counts: 89/89 match (see `docs/migration/MC-POSTGRES-01/05-reconciliation.json`).
- PK comparisons: 89/89 match.
- Content verification: 89/89 canonical-digest match.
- FK integrity: source `foreign_key_check` clean; PG import in dependency
  order with constraints enforced; no orphans possible without abort.
- Sequence verification: `health_observations_id_seq` → 125273; next inserts verified.
- Evidence/digest preservation: byte-identical pass-through; zero transformations.
- Business-level: books (41, order), projects (81), applications (11),
  cultivation skills/goals (15/15), websites (4), workflows (18) — MATCH.

## Operational verification

- Active database backend: **postgresql** (`/api/diagnostics/database`).
- Startup: `Database ready backend=postgresql schema_applied=[] url=postgresql+psycopg://mc:***@…`.
- API verification: health ok v0.1.0 schema 40; books/applications/cultivation/
  websites/workflows endpoints return full pre-migration data.
- Background monitor: `_monitor_once` persists observations to PG
  (125274→125291 in verification pass); monitor task initializes on startup.
- Book reordering: reversed-order write + refresh + restore roundtrip green,
  concurrent with health writes (integration test).
- New writes reach PG: reorder updates + 17 monitor observations confirmed.
- SQLite no longer written: size/mtime/counts identical before/after all
  PG-backed runs.

## Regression results

- Backend suite: `python -m pytest backend/tests -q` — **859 passed,
  13 skipped, 0 failed** (skips: 11 PG tests needing `MC_TEST_DSN`, live
  Writer CLI path, Docker sandbox).
- PostgreSQL integration: **11 passed, 0 failed** (`MC_TEST_DSN` → isolated `mc_test`).
- Frontend: production build pass (`tsc -b && vite build`, 3559 modules);
  unit tests **29 files / 154 tests pass**.
- Lint: `ruff check` clean on all touched/new files; 48 pre-existing findings
  in untouched files left as-is (documented, no drive-by refactoring).

## Recovery

- Backups: see Migration summary. Original `data/mission_control.db` preserved.
- Instructions: `docs/migration/MC-POSTGRES-01/08-recovery-runbook.md`.
- Known limitation: post-cutover SQLite return would lose PG-era writes;
  forward recovery (PG backup → scratch → promote) is the documented path.

## Gates

G01 source inventoried — PASS. G02 backup verified — PASS. G03 target verified
(empty before baseline) — PASS. G04 all tables accounted — PASS (89+metadata).
G05 PG schema validated — PASS. G06 records imported/reconciled — PASS
(146465/146465). G07 PKs preserved — PASS. G08 FKs preserved — PASS. G09 no
unexplained differences — PASS (0). G10 sequences verified — PASS. G11 evidence
preserved — PASS. G12 PG integration pass — PASS (11). G13 regression pass —
PASS (859 passed, 0 failed). G14 reorder+monitor concurrency — PASS. G15 starts on `MC_DSN` —
PASS. G16 new writes to PG — PASS. G17 SQLite not written — PASS. G18 backup
docs — PASS. G19 no credentials exposed — PASS. G20 local & uncommitted — PASS.
