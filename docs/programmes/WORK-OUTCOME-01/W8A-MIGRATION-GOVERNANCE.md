# W8A-MIGRATION-GOVERNANCE — Presence is not approval

## How 048/049 reached operational (verified in code)

`create_app` lifespan unconditionally runs `apply_migrations(database)`
(main.py:167) at every backend startup. Discovery is by directory scan
of the working tree (`migrations.py:_migration_files`,
`_pg_migration_files`) — committed or not, any workstream. The only
operator signal is a log line (`schema_applied=[...]`). There is no
pending-list, no ownership check, no approval watermark, no per-
workstream namespace (046/049 aitest interleave with 047/048 work-
outcome by bare version ordering).

So: migration code present in the tree == migration applied on next
restart. Programme "approvals" (W5A §045, W7 048) were doc statements
with no enforcement point. Harmless so far (all additive, validated on
scratch first) — but the property is accidental, not governed.

## Recommendation (no new system)

1. Startup banner: list pending migrations (version + filename +
   inferred workstream prefix) in logs BEFORE applying.
2. Approval watermark: record the highest programme-approved version
   (e.g. in the ledger + a `settings` row); startup applies beyond it
   only with explicit env opt-in (`MISSION_CONTROL_AUTO_MIGRATE=1`)
   or fails closed with the pending list. Default closed.
3. Read-only visibility: expose applied-vs-present versions (cheap
   read of schema_migrations + file scan) so the operator sees drift.
4. Convention: one workstream prefix per migration pair; never reuse
   a version number across workstreams (046/049 vs 047/048 already
   comply by luck).

Explicitly NOT in W8: another migration framework, runner, or
scheduler. The above is process + a small amount of existing-code
wiring, for the operator to schedule.
