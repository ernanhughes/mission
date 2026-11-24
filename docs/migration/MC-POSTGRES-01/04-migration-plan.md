# MC-POSTGRES-01 — Migration plan and safety gates (04)

Tool: `scripts/migrate_sqlite_to_postgres.py` (subprocess-safe, stdlib +
SQLAlchemy/psycopg only).

## Commands

- `--inspect` — read-only inventory of source tables/counts and target
  tables/counts/version. Never writes.
- `--dry-run` — read-only: computes FK-topological import order, probes every
  row for compatibility (booleans, JSON validity, NaN, NUL bytes), reports
  target-emptiness. Exit non-zero on any blocker.
- `--execute --yes` — the only writing path. Requires `--yes`; refuses a
  non-empty target unless `--resume` (interrupted-run continuation, skips
  populated tables, still reconciles) or `--allow-nonempty` with an explicit
  `--pg-backup` (pg_dump destination). Steps: consistent SQLite backup API
  snapshot → `integrity_check` + `foreign_key_check` gates → PG schema
  baseline → FK-ordered import (batches of 500, parameterized, PKs preserved,
  no `ON CONFLICT DO NOTHING`) → sequence repair → full reconciliation;
  writes `docs/migration/MC-POSTGRES-01/05-reconciliation.json`.
- `--verify` — read-only reconciliation of any source snapshot vs target.

## Safety properties

- Default operation is non-destructive; `--execute` without `--yes` refuses.
- No credentials in output (redacted DSN), command lines, or logs.
- Repeated runs are idempotent: a matching target reports “already complete”;
  anything else refuses rather than double-importing.
- Failed runs resume with `--resume`; partial tables are skipped only when
  fully populated, and the final reconcile still gates success.
- Sequence repair is part of verification, not an afterthought.

## Gate order actually executed

1. Target verified empty (0 tables) before baseline.
2. Source backups via SQLite backup API (WAL-safe), integrity + FK gates green.
3. Baseline schema version 40 applied.
4. Ordered import of all 90 tables (146465 records), PK-preserving.
5. `health_observations_id_seq` repaired to max(id)=125273; next inserts verified.
6. Full reconciliation: 89/89 tables OK (counts + PK sets + canonical content).
7. Business-level comparison (books/projects/applications/skills/goals/settings): MATCH.
8. Contamination control: one test-harness blog-sync write (1 event row +
   timestamp touches on 331 rows) was identified, proven timestamp-only, and
   caught up explicitly; final backup + verify green.
