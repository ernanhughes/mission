# MC-POSTGRES-01 — Data reconciliation (05)

Machine-readable detail: `05-reconciliation.json` (generated from the final
pre-cutover backup against the operational `mc` database).

- Tables compared: **89/89 OK** (the 90th source table, `schema_migrations`,
  is version metadata tracked separately: PG version **40**).
- Row counts: source **146426** (excl. migration metadata) vs target **146426**.
  Including metadata: 146465 both sides.
- Primary-key sets: match on all tables.
- Content: canonical digest match on all tables (booleans normalized 0/1↔bool,
  JSON canonicalized for comparison only; stored bytes preserved).
- Foreign keys: SQLite source had zero violations; PG import followed the FK
  topological order and enforces all constraints (any orphan would have
  aborted the import).
- Sequences: `health_observations_id_seq` set to max(id) = 125273; next
  insert verified to not collide.
- Evidence/digest fields: byte-identical (no canonicalization applied on the
  write path).
- Unexplained differences: **0**.
