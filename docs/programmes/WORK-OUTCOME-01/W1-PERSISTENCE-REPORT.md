# W1-PERSISTENCE-REPORT — Additive PG tables, growth, policy

Migration `041` (dual-file, version 41): `041_work_observation.sql`
(SQLite/tests legacy path) + `041_work_observation.pg.sql` (operational PG
delta). The runner's applied-set guard makes the shared version safe on both
backends (fresh PG: ORM baseline + mark; existing PG: pg delta; SQLite: sql).
No alterations, no destructive statements, `IF NOT EXISTS` throughout.

Tables (ORM `Wo*` in `models.py`, no `relationship()`, no FKs — nothing to
order): `wo_observation_sources(kind,identity)`, `wo_observation_runs`
(append-only, stats + error), `wo_checkpoints(source,cursor → (ms,id))`,
`wo_signals` (stable id, `UNIQUE(source_ref,type,digest)`).

Storage (measured, scratch PG): 2,398 signals + 4 runs + checkpoints ≈
5.1 MB in `wo_*` (excerpts ≤800 chars + provenance JSON) vs 16.2 MB database
total. Growth is linear in signals (~2 kB/row); raw payloads stay in the
source. Full-history backfill is out of scope for W1 (bounded runs only).

Retention (owner-approved): durable derived records + evidence references;
minimise duplicated conversation content. Historical records carry
`source_ref` locators; vanished sources are flagged `source_missing`
(re-census rule) rather than deleted. No janitor in W1 (matches current
no-auto-delete posture); W6 defines enforcement.

Deviation recorded: no isolated PG test infrastructure exists
(`MC_TEST_DSN` unset), so the pg delta was validated via ORM-baseline fresh
install on scratch PG `w1_pilot` + the full SQLite suite — not against a
pre-existing PG. Risk accepted as low (additive, `IF NOT EXISTS`); the
operational `mc` database has NOT been migrated by this commission (scratch
only; next backend start applies 041 automatically).
