# W1-TEST-EVIDENCE — 41 focused tests + neighbours, zero model calls

Suite: `backend/tests/test_work_observation.py` (41 tests, synthetic SQLite
fixtures under `tmp_path`; real OpenCode DB never touched):

- RO access: missing / not-a-file / incompatible-schema / older-schema-without-parts.
- Parsing: assistant observed (model/cost/tokens/excerpt/tools), malformed→`parse_error`,
  user-text-without-parts is content.
- Signals: SHA + task-id candidates (INFERRED), invalid SHAs ignored,
  Windows + relative paths, test/completion claims (CLAIMED, never VERIFIED),
  tool invocations OBSERVED, workbench refs, provenance on every signal.
- Evidence: secret redaction (`[REDACTED-SECRET]`), claim/verified separation,
  allow-list matrix (16 cases) + relativization.
- Incremental: run + checkpoint advance, idempotent replay (`signals_new: 0`),
  timestamp ties, late arrivals, updated-session redelivery without dupes,
  locked-run checkpoint freeze, source-replacement fingerprint, SQL-side
  project filter.
- Git: unresolvable/non-repo directories recorded (found + fixed the
  `toplevel` bug + filter-must-be-SQL bug via these tests).
- API: status/runs/get/run-404/param-422/signals/coverage/checkpoints.

Results: 41/41 pass; `test_migrations_and_seed` + `test_persistence_conventions`
updated/passing (041 expectations + wo tables); neighbours
`test_git_activity` + `test_git_daily` + `test_opencode_cost*` 35/35 pass
(125 s — environment, not a `long` marker); `ruff check` clean on all touched files
(48 remaining hits are pre-existing in untouched files).

Deliberately deferred: full-backend suite and any `long`-marked corpus
(per test policy); PG-delta application to a pre-existing PG (no isolated PG
available — recorded in W1-PERSISTENCE-REPORT).
