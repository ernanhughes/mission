# W9A-DATABASE-TARGET-SAFETY — Fail closed at the ORM boundary

## Incident (W8, verified and repaired)

A diagnostic one-liner ran without `MC_DSN` set in its environment and
`Database()` resolved the machine-wide inherited DSN, inserting 3
fixture rows into operational `mc`. Zero dependents existed; all 3
rows removed after dependency checks; counts re-verified (31/9/293).
No programme record was altered.

Root cause (systemic): the DSN default chain silently resolves to
whatever the process inherited, and nothing distinguished "the
operator meant this database" from "this script never thought about
it". Conftest guards cover pytest only.

## Fix implemented (tested)

`Database(..., target=...)` is now **required** for every PostgreSQL
connection through the ORM. Without it, construction raises before any
engine use, naming the (redacted) host/database and how to declare
intent: `target='server'` (application startup), `target='migration'`
(the PG migration utility), `target='scratch:<name>'` (isolated work),
`target='script:<name>'` (one-off scripts). SQLite paths need no label.

- Application startup: `target="server"` (main.py).
- Migration utility: `target="migration"` (scripts/migrate_sqlite_to_postgres.py).
- Dev scripts: `target="script:<name>"` (demo_live_review,
  gen_prompt_example, prove_restart, smoke_git_activity).
- Tests: `_enforce_test_database` still runs first; PG integration
  helper passes an explicit label.
- Secrets never appear in the error (`test_pg_error_hides_credentials`);
  `_redact_url` also redacts password-like query parameters.

## Coverage — precise, after review (F4)

The gate covers **the `Database`/ORM boundary**, which is where the
incident occurred and where every application data path goes. It does
**not** wrap raw `psycopg.connect` call sites:

| Raw psycopg site | Purpose | Gate status |
| ---------------- | ------- | ----------- |
| `scripts/migrate_sqlite_to_postgres.py:253` | reads the SQLite source | outside (read-only source) |
| `scripts/pg_backup.py:98,114,122` | operator backup/restore | outside (operator tool, explicit DSN) |
| `adapters/next.py:183`, `publication/publishing.py:989` | external stores, different env vars | outside (not Mission Control's DB) |

Honest statement: the new gate makes the *accident* structurally
impossible on the application path and forces deliberate declaration in
scripts. It is an **intent marker, not an authorization token** — any
caller can write `target="server"`. Real authorization is the
operator's, and this is documented rather than implied.

## Negative controls (no live connections made; engine creation is lazy)

Missing target → refuse; credentials absent from messages; SQLite
label-free; test-DSN path still guarded. `test_db_targeting.py`: 4
passed, and the reviewer verified the suite fails if the gate is
removed.
