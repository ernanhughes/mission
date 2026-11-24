# MC-POSTGRES-02 — Independent Migration Audit and Operational Hardening — Report

## 1. Independent review verdict

**Verdict: READY_TO_COMMIT_WITH_DOCUMENTED_LIMITATIONS** (pending final
background regression results; all targeted suites green at draft time).

The MC-POSTGRES-01 implementation was inspected file by file against its
documentation. The headline claims hold: 90 tables / 146,465 records
migrated, 89/89 tables reconciled with zero unexplained differences, schema
version 40, PG backup restore-validated, cutover complete with the live
instance healthy on PostgreSQL.

Confirmed defects were found in exactly the two areas the review flagged
(test isolation, flush ordering) plus one minor diagnostics gap. All are
addressed below with regression tests. No data re-migration was performed;
the live database was only ever read (plus its own normal operational
writes).

## 2. Verified migration claims

- Source inventory (90 tables, 146,465 records): verified against the final
  backup; counts reproduce exactly.
- Schema baseline: fresh-install probe on a disposable database
  (created/verified/dropped) applied versions 1–40 with zero SQLite
  involvement; 90 tables; BIGINT widenings present. A new installation does
  not need the SQLite file.
- Migration tracking: `schema_migrations` semantics identical; version 40
  live; 040 delta applies exactly once and is a safe no-op rerun.
- Sequences: `health_observations_id_seq` at migrated max; verified live.
- Evidence/digest fields: byte-identical pass-through confirmed for
  `praxis_proposals` digests, publication fingerprints, extraction manifest
  hashes, script/content hashes (spot-checked in restored scratch DB).
- Credentials: no DSN/password in code, docs, or tests (only commented
  local-dev placeholders in `.env.example`, consistent with its purpose).
- SQLite retained read-only: live file size/mtime/counts unchanged across
  all PG-backed verification runs.

## 3. Unsupported or partially verified claims

- “859 backend tests passed” (MC-POSTGRES-01): the full-suite log was not
  retained as an artifact. Re-running the full suite under MC-POSTGRES-02
  with counts recorded (see §13). No failures were observed in any run.
- Live row counts now exceed the migration snapshot (expected post-cutover
  operational writes: health observations, blog syncs). Reconciliation
  distinguishes these explicitly (§7).

## 4. Test isolation findings and corrections

**Root cause of the MC-POSTGRES-01 incident:** `create_app(RuntimeSettings())`
with the default `data_dir` pointed a test lifespan at the live repository
SQLite file; startup blog-sync wrote 1 event row and touched 331 timestamps.
A second, more dangerous hole existed post-cutover: any test constructing
production-like settings while `MC_DSN` is set would connect to the
operational `mc` database.

**Corrections (all fail-before-write):**
1. `backend/tests/conftest.py`: autouse fixture strips `MC_DSN` and
   `MISSION_CONTROL_DATABASE_URL` for every test — no implicit inheritance.
2. `Database.__init__`: under `PYTEST_CURRENT_TEST`, PostgreSQL is allowed
   only on exact equality with `MC_TEST_DSN`; SQLite is refused when it
   resolves to the repository production file. Raised before engine use.
   Production path (no `PYTEST_CURRENT_TEST`) is byte-identical.
3. `test_postgres_integration.py`: fixture validates the *actual connected*
   database (`current_database()` vs `MC_TEST_DSN`, refusal of `mc`);
   subprocess migration tests run with a scrubbed env proving no fallback.
4. New `backend/tests/test_db_isolation.py` (5 tests): strip proof,
   production-file refusal, non-test-PG refusal, explicit-test-DSN
   acceptance without connecting, tmp-SQLite acceptance.
5. `test_persistence_conventions.py` + PG subprocess paths use explicit
   isolated settings only.
6. Artifact hygiene: the migration utility wrote its reconciliation report
   to the repo docs dir even for toy test runs, and a PG test subprocess
   overwrote the committed `05-reconciliation.json` with test counts.
   Fixed with `--report-path` (tests redirect to tmp; production default
   unchanged) and the committed artifact restored from git.

**Regression proof:** `test_db_isolation.py` 5/5 pass with no server and no
`MC_TEST_DSN`; full PG file green with `MC_TEST_DSN` set.

## 5. ORM flush-ordering findings

**Root cause:** expected SQLAlchemy behaviour, not a bug and not
PG-specific. The unit of work orders pending inserts via relationship
dependency processors; Mission Control declares column-level `ForeignKey`s
but zero `relationship()`s, so a single flush mixing transient parent+child
emits the child INSERT first. Proven with vanilla SQLAlchemy mappers +
enforced FKs (identical `IntegrityError`), while unenforced SQLite masked
it. No FK cycles exist in the metadata; all parent-child pairs behave the
same.

**Correction chosen:** no broad ORM change (adding relationships would alter
cascade semantics across 90 tables) and no scattered `flush()` calls.
Instead: the convention (flush parents before adding children, as
`seed_defaults` and services already do) is documented in a new
`models.py` module docstring and pinned by
`backend/tests/test_persistence_conventions.py` (1 boundary test proving
single-flush nesting is rejected + 3 convention tests for representative
pairs). Suite-wide evidence: the entire backend suite passes on
FK-enforcing SQLite, so no production path violates the convention.

## 6. PostgreSQL migration architecture findings

- Fresh init: verified on disposable `mc_fresh` (production path): 40
  versions, 90 tables, constraints + BIGINTs + version tracking correct.
- Transactional DDL: single `engine.begin()` per `apply_migrations`; a
  mid-baseline failure rolls back to empty (observed during MC-POSTGRES-01).
- Failure recovery: `--resume` skips populated tables and still reconciles;
  `--allow-nonempty` requires an explicit pg_dump backup.
- FK enforcement: PG enforces all constraints; import order is
  FK-topological; self-references are nullable with two-pass-safe ordering.
- Indexes: UNIQUEs (incl. composite and named constraint
  `uq_integration_resource`) carried via ORM metadata; spot-verified live.
- Connection pool: 5 + 5 overflow, 30 s timeout, `pool_pre_ping`; surfaced
  read-only in diagnostics.
- Session cleanup: request-scoped sessions commit/rollback/close; background
  sessions independently scoped; engine disposed on shutdown; verified in
  lifespan code review.

## 7. Data reconciliation results

Independent pass (MC-POSTGRES-02): restored the verified pre-cutover dump
into scratch `mc_audit` and compared all 89 tables against the final SQLite
backup — **89/89 counts match, 0 mismatches**; BIGINT spot checks intact
(`mtime_ns` max 1794326779210685600, `exit_code` max 4294967295);
`health_observations_id_seq` at migrated max; praxis digest samples
byte-identical; scratch dropped. Result: **PHASE5-VERIFY OK**.

Post-cutover drift (legitimate operational writes, not discrepancies):
health_observations 125273 → 125410+ (monitor), cultivation blog-sync rows.
Live exact-match is not expected; the pre-cutover dump is the historical
reference and it verifies exactly.

## 8. Operational diagnostics changes

Extended `GET /api/diagnostics/database` (existing architecture, no new
subsystem): `latency_ms`, `postgresql.size_bytes`,
`active_connections` / `idle_in_transaction` (self excluded),
`long_transactions` + `longest_transaction_seconds` (>60 s threshold),
`waiting_locks`, `last_verified_backup` (from
`data/backups/last_verified_backup.json`, else `unknown`). Read-only
queries; counts/durations only; unknown stays unknown; no polling added.

## 9. Backup and recovery verification

- SQLite final snapshot: integrity ok, FK clean (re-verified).
- PG dump: re-restored into scratch `mc_audit` under MC-POSTGRES-02 with
  full table comparison (see §7); `last_verified_backup.json` sidecar
  records bytes/sha256/method for the diagnostics endpoint.
- New `scripts/pg_backup.py`: timestamped `pg_dump` via `MC_DSN`
  (password via `PGPASSWORD`, auto-discovers `pg_dump`/`psql`), optional
  `--verify` (scratch restore + full comparison + sidecar update).
- Recovery runbook (08) remains accurate; backup creation is now a single
  convenient command. No scheduler added (per boundaries); recommended
  policy: weekly verified backup, sidecar reviewed via diagnostics.

## 10. Remaining risks

1. Tests can still *read* the live SQLite file (only writes are blocked);
   acceptable: it is a frozen recovery asset and reads are harmless.
2. `research_chat_messages` CHECKs still ORM-absent (carried over, documented).
3. Unix-timestamp INT4 columns other than the widened three (2038 boundary).
4. `LIKE`/`ILIKE` dialect semantics (audited, no change).
5. No automatic backup scheduling (deliberate; policy recommended above).
6. `MC_DSN` must exist in every startup environment (fails fast by design).

## 11. Changed files

- `backend/mission_control/persistence/db.py` — test-isolation guard.
- `backend/mission_control/models.py` — persistence-convention docstring.
- `backend/mission_control/api/health.py` — extended PG diagnostics.
- `backend/tests/conftest.py` — autouse operational-env strip.
- `backend/tests/test_db_isolation.py` — new (5 tests).
- `backend/tests/test_persistence_conventions.py` — new (4 tests).
- `backend/tests/test_postgres_integration.py` — fixture identity checks,
  monkeypatch isolation, scrubbed subprocess env, 4 new resilience tests.
- `scripts/pg_backup.py` — new verified-backup helper.
- `data/backups/last_verified_backup.json` — new sidecar (git-ignored dir).
- `docs/MC-POSTGRES-02-REPORT.md` — this report.

## 12. Regression results

- PostgreSQL integration (`MC_TEST_DSN` → isolated `mc_test`):
  **15 passed, 0 failed** — 11 MC-POSTGRES-01 tests (fixture hardened with
  connected-identity validation, monkeypatch isolation, scrubbed subprocess
  env) + 4 new resilience tests (connection recovery after dispose, failed
  transaction rollback, unreachable-PG surfaces PG error without SQLite
  fallback, monitor recovery after failure). Final re-run also covers the
  `--report-path` change and confirms the committed reconciliation artifact
  is no longer modified by test runs.
- Isolation + conventions (normal suite, no server): `test_db_isolation.py`
  5/5, `test_persistence_conventions.py` 4/4.
- Backend suite (with all MC-POSTGRES-02 changes, including the test-gated
  `Database` guard and conftest strip): **868 passed, 17 skipped, 0 failed**
  (skips: 15 PG tests requiring `MC_TEST_DSN`, live Writer CLI path, Docker
  sandbox). The 9 new tests (5 isolation + 4 conventions) are included.
- Frontend: unchanged since MC-POSTGRES-01 (29 files / 154 tests pass,
  production build green).
- Lint: `ruff check` clean on all touched/new files.

Note: one resilience test initially exposed that the PG engine had no
`connect_timeout` (unreachable-server check hung past the 60 s test
timeout). Fixed with `connect_args={"connect_timeout": 10}` — a genuine
resilience improvement (health checks fail fast instead of hanging on TCP
retransmits). The live instance predates this change and picks it up on its
next normal restart; its current pool behaviour is otherwise identical.

## 13. Final verdict

**READY_TO_COMMIT_WITH_DOCUMENTED_LIMITATIONS**

- All three review issues addressed with fail-before-write safeguards and
  regression tests; independent reconciliation confirms zero data
  discrepancies; fresh-install, diagnostics, backup, and resilience
  objectives verified on disposable resources only.
- Full regression evidence: backend 868/0, PG integration 15/0, isolation
  5/5, conventions 4/4, frontend 154/154, build green, ruff clean.
- Limitations: live instance predates `connect_timeout` (picks up on next
  normal restart); `research_chat_messages` CHECKs and INT4 timestamp
  columns remain as documented in 09-remaining-risks.
