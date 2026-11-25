# W5A-OPERATIONAL-PREFLIGHT — Read-only findings 2026-11-24

- Database `mc`: reachable, healthy, 7 connections, 0 ungranted locks.
- Schema version at entry: **44**; 045 pending; 046 present-but-unapplied
  (`046_aitest_testing.{sql,pg.sql}`, another workstream's additive
  central-testing-visibility tables — no shared tables, no data touched).
- `wo_*` tables: 18 present (041:4 + 042:3 + 043:6 + 044:5), all EMPTY
  (0 rows in every derived table) — no historical state to preserve, none
  to migrate.
- Existing records: 81 projects, 110 git repositories, 12,779 git commits;
  `C:\Projects\ai` indexed (75 commits, backfill complete, branch main).
- Active backend: PID on :8790 (operator-owned; never restarted or
  disturbed by this commission). Ollama loopback up (11434).
- OpenCode source DB: live, WAL-consistent; read-only access verified.

No blockers to controlled migration. Operational `mc` was NOT written by
W1–W4 (all pilots ran on scratch DBs, since dropped).
