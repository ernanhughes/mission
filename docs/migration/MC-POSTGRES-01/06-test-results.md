# MC-POSTGRES-01 — Test results (06)

## Backend regression suite

`python -m pytest backend/tests -q` — **859 passed, 13 skipped, 0 failed**
(skips: 11 PG integration tests requiring `MC_TEST_DSN`, 1 live Writer CLI
path, 1 Docker-dependent sandbox test). The SQLite-backed path is unchanged
for isolated tests. Targeted pre-migration checks also passed:
`test_migrations_and_seed`, `test_sqlite_lock_health`,
`test_registry_and_projects` (17 passed).

## PostgreSQL integration (`backend/tests/test_postgres_integration.py`)

Isolated database `mc_test` (owned by `mc`), gated on `MC_TEST_DSN`, with an
explicit refusal to run against the operational `mc` database.
Run with `MC_TEST_DSN` set: **11 passed, 0 failed**. Covers: configuration
loading, driver normalization, credential redaction, missing config failure,
fresh PG init + repeated startup, full schema presence, empty-source and
populated-source migration, PK preservation, sequence repair,
populated-target refusal, idempotent re-run, book listing/reordering,
health-observation writes, reorder-concurrent-with-health-writes, and
no-SQLite-fallback. (Initial failures during development were test-harness
bugs — env lifetime for the lazy lifespan, and unflushed transient parents —
fixed in the test file; production code needed no changes for them.)

## Frontend

- Production build: `npm run build` (`tsc -b && vite build`) — **pass**
  (3559 modules transformed, built in ~1s).
- Unit tests: `npm test` (vitest) — **29 files, 154 tests, all pass**.

## Lint

- `ruff check` on all touched/new files (`config.py`, `persistence/db.py`,
  `persistence/migrations.py`, `models.py`, `main.py`, `api/health.py`,
  `processes/manager.py`, `scripts/migrate_sqlite_to_postgres.py`,
  `tests/test_postgres_integration.py`) — **clean**.
- Full-repo `ruff check` reports 48 findings, all in files untouched by this
  migration (pre-existing) — left as-is, no drive-by refactoring.
