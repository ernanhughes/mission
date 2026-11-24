# MC-POSTGRES-01 — Recovery runbook (08)

## Assets (do not delete without owner authorization)

- Live SQLite (frozen at cutover):
  `data/mission_control.db` — retained, no longer written by Mission Control.
- Verified snapshots in `data/backups/` (excluded from Git):
  - `mission_control-pre-pg-migration-FINAL-20261124T090600Z.db` (authoritative
    pre-cutover snapshot; sha256
    `ef3c9e4e72eabe3330f7b36294cfa455dca4df9c3bfa2f17bd34772b199b6df0`).
  - Earlier rehearsal backups `mission_control-pre-pg-migration-20261124T*.db`.
- PG logical backup: `pg_dump -h localhost -U mc -d mc -f <dest>` with the
  password supplied via `PGPASSWORD` (or a pgpass file), never on the command
  line. Restore into a scratch DB first and run
  `scripts/migrate_sqlite_to_postgres.py --verify` semantics before promoting.

## Pre-cutover rollback (no PG writes yet)

Stop the PG-backed app, unset/ignore `MC_DSN` (or set
`MISSION_CONTROL_ALLOW_SQLITE=1` for an emergency start), restart: the app
serves the preserved SQLite file again.

## Failed-cutover rollback

Same as above; the SQLite file was never written after the final snapshot
(verified by mtime + count comparison), so no data loss.

## Post-cutover recovery (PG has new writes)

Prefer forward recovery: restore the PG backup into a recovery database,
verify, promote. Do NOT copy the stale SQLite file over PG or vice versa —
after cutover the SQLite snapshot is missing all PG-era writes. Returning to
SQLite is only possible by re-running the migration forward again (SQLite →
fresh PG), never by downgrading.

## Diagnostics

- `GET /api/diagnostics/database`: backend, connectivity, schema version,
  pool status, redacted URL, last error category. No credentials, no records.
- PG: check `pg_stat_activity` for long-running transactions/locks,
  connection counts vs pool settings (size 5 + overflow 5).
