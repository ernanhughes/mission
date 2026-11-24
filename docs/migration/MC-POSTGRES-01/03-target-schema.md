# MC-POSTGRES-01 — Target schema and migration design (03)

## Target

- Host `localhost:5432`, database `mc`, user `mc` (credentials via `MC_DSN`
  only, never committed or logged; diagnostics print redacted forms).
- PostgreSQL 16.8, encoding/database locale as provisioned, public schema.
- Pre-migration state: **empty** (0 tables) — independently verified, so no
  unrelated data was at risk and no backup of PG content was required.

## Schema construction

Fresh PG installs build the schema from the SQLAlchemy ORM metadata
(`mission_control.models.Base` + `praxis_proposals.models`, which together
cover all 89 application tables) via `create_all`, then record the 39 legacy
migration versions into `schema_migrations` as a baseline. Rationale:

- The ORM mirrors the full SQLite migration history (verified: ORM tables ==
  SQLite tables minus `schema_migrations`, which the runner owns).
- SQLite DDL is dialect-specific (`AUTOINCREMENT` etc.) and cannot run on PG.
- `schema_migrations` keeps identical semantics; `schema_version()` is
  comparable across backends. Current PG version: **40**.

Native PG types: `TEXT`/`VARCHAR` for strings and ISO timestamps (unchanged
semantics), `BOOLEAN`, `INTEGER`/`BIGINT` (see 02), `DOUBLE PRECISION`,
`JSON` (deliberately not JSONB). Constraints carried: PKs (incl. composite),
FKs with `ON DELETE` actions, UNIQUEs (single, composite, and
`uq_integration_resource` / `uq_workflow_event_sequence` /
`uq_research_chat_message_*`). `health_observations.id` is PG-serial with
sequence repair (`setval(..., max(id))`) verified after import.

## Source → target disposition

Every source table: migrated directly with values preserved byte-identically,
except the two documented `INT4`→`BIGINT` widenings (values unchanged).
Empty tables migrated as empty schemas. No table omitted, merged, or
deduplicated. Evidence/digest-bearing TEXT (fingerprints, hashes, approval
digests) passed through with zero transformation.

## Future migrations

- Legacy `NNN_*.sql` remain the SQLite archive (still used by isolated sqlite
  tests and the migration source reader).
- New PG changes ship as `NNN_*.pg.sql` in the same directory, applied in
  version order and recorded in `schema_migrations`. Current: `040_script_bigint.pg.sql`.
