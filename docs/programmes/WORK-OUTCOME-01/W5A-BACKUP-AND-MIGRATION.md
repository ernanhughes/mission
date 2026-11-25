# W5A-BACKUP-AND-MIGRATION — Controlled, additive, verified

## Backup (before any write)

- File: `data\backups\mc-pre-w5a-20261124T181022Z.dump` (5.8 MB,
  custom format, `pg_dump` 17.6, password via `PGPASSWORD` env only).
- SHA-256: `EE3010BB79D9B8BB65A5F632826600BCA6D38DA21578CDDBD3ED96DB919A16D6`.
- Verified by restore into scratch `w5a_verify`: version 44, 81 projects,
  12,779 git commits — matches live. Restore warning only:
  `transaction_timeout` unknown on the PG16 server (PG17 client artifact,
  ignored, 0 data errors).
- No existing backups overwritten. Recovery path: restore dump into a
  recovery database and promote (per MC-POSTGRES-01 runbook); no SQLite
  involvement.

## Migration (repo runner, no new mechanism)

- Ran `apply_migrations` via the repository's own runner against
  operational `mc`: applied `[45, 46]` → version 46.
- **Discrepancy recorded (§2)**: `046_aitest_testing.*` (another
  workstream, AITEST-02 central testing visibility: 5 additive tables)
  was pending alongside 045 and applied in the same run. Verified
  additive-only (`CREATE TABLE IF NOT EXISTS`, separate `aitest_*`
  namespace); existing records untouched (81/12,779 before and after);
  no shared tables with WORK-OUTCOME-01. Not silently ignored — recorded
  here and left intact.
- 045 marker: `045_work_eval_digests.pg.sql`. Digest columns verified
  present on both assessment tables. Re-run: `[]` (idempotent).
- SQLite path unaffected (fresh-file semantics; 045 plain `ADD COLUMN`
  applies after 044; PG delta uses `IF NOT EXISTS` for the
  already-applied-operational case on other clones).
- No operational records were deleted or modified to recover from
  anything; no failure occurred.
