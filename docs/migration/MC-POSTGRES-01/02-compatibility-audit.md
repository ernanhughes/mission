# MC-POSTGRES-01 — Compatibility audit (02)

## Method

Every source column was classified against the ORM-declared PostgreSQL type
(SQLAlchemy `String`/`Text`/`Integer`/`BigInteger`/`Float`/`Boolean`/`JSON`)
and every row probed by `scripts/migrate_sqlite_to_postgres.py --dry-run`.
The import canonicalizes (never silently repairs): any probe failure aborts
that table with evidence.

## Findings

| Area | Verdict | Detail |
| ---- | ------- | ------ |
| Primary keys (TEXT) | Compatible | All string PKs pass through unchanged; `health_observations.id` INTEGER → PG identity/serial + `setval` repair, verified. |
| Primary keys (INTEGER overflow) | Required schema change | `script_records.mtime_ns` (ns timestamps ~1.8e18) and `file_size`, plus `process_instances.exit_code` (Windows unsigned 32-bit up to 4294967295) exceed PG INT4. ORM types changed to `BigInteger`; PG delta `040_script_bigint.pg.sql`. Documented transformation, values preserved exactly. |
| Booleans | Compatible | SQLite 0/1 → PG native boolean via ORM `Boolean`; canonical comparison normalizes both sides. All boolean columns round-tripped. |
| Timestamps | Compatible | Stored as ISO-8601 TEXT on both backends (ORM `String`); byte-identical, no timezone conversion. |
| JSON | Compatible | SQLite TEXT JSON → PG `JSON` (not JSONB, deliberate: no semantic rewrite, formatting preserved on write path; verification canonicalizes key order/whitespace only for comparison). All JSON parsed successfully; zero invalid documents. |
| Binary (BLOB/BYTEA) | Not applicable | No BLOB columns in the schema. |
| Numeric | Compatible | REAL → `Float`; no NaN values found (import rejects NaN explicitly). |
| Defaults | Compatible | Python-side defaults (`now_iso`, `list`/`dict`) behave identically; server defaults not relied upon. |
| Foreign keys | Compatible | Zero pre-existing violations (`PRAGMA foreign_key_check` clean, verified again on PG by full PK/FK-graph import order). PG enforces strictly; see note below on flush ordering. |
| Unique/NULL semantics | Compatible | `dedupe_key`, `idempotency_key`, `correlation_id`, composite keys preserved; NULL-vs-empty-string preserved byte-identically (no normalization). |
| Text comparison | Requires care (no change) | `LIKE`/`ilike` via SQLAlchemy map to `LIKE`/`ILIKE` on PG. SQLite `LIKE` is case-insensitive for ASCII while PG `LIKE` is case-sensitive; code already uses `ilike` where case-insensitivity matters (search paths) and `like` only for case-sensitive prefixes (`gh-`, shas). No behavior change required. |
| SQL functions | Compatible | No SQLite-only functions (`strftime`, `datetime('now')`, `last_insert_rowid`) in production paths; remaining `strftime` uses are Python-level filename stamps. |
| Upserts | Compatible | Production uses no `INSERT OR IGNORE/REPLACE`; idempotency is via select-then-insert/seed guards. |
| Pagination/ordering | Compatible | All listings order by stable keys (`display_order, priority, title/id`). |
| Migration scripts | Required schema change | The 39 legacy `NNN_*.sql` files are SQLite-dialect (`AUTOINCREMENT`, typeless JSON). They are retained as the legacy archive; PG uses an ORM-metadata baseline bound to version 39 plus `NNN_*.pg.sql` deltas (currently `040_script_bigint.pg.sql`). `schema_migrations` semantics are identical on both backends. |
| `research_chat_messages` CHECKs | Not carried (documented) | SQLite DDL has `CHECK (role IN …)` / `CHECK (status IN …)`; the ORM does not declare them so PG baseline lacks them (application validates at the API layer). No data violates them. |

## Flush-ordering note (pre-existing, backend-independent)

Creating a transient parent and child in a single session flush (e.g.
`Project` + `Book` without an intermediate `flush()`) emits the child INSERT
first on **both** SQLite and PostgreSQL. SQLite only masks this when FK
enforcement would otherwise fire; PG raises `ForeignKeyViolation`. All
production code already flushes parents first (see `seed_defaults`, service
layers); the new PG integration tests encode this convention. No production
code change was required.

## Owner decisions required

None outstanding. The two `BigInteger` changes are value-preserving type
widenings, not transformations.
