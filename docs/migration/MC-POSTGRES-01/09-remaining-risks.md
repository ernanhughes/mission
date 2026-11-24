# MC-POSTGRES-01 — Remaining risks (09)

1. **Single-host locality.** PG runs on localhost; the pool is sized for one
   local app (5+5). Multi-host or heavy analytics growth needs re-tuning, not
   a redesign.
2. **`research_chat_messages` CHECK constraints** exist in SQLite DDL but not
   in the ORM/PG schema; enforcement is at the API layer. Consider a future
   `NNN_*.pg.sql` adding them if defense-in-depth is wanted.
3. **Unix-timestamp INT4 columns** (`git_commits.author_ts`, etc.) fit today
   but share the 2038 boundary; `script_records`/`process_instances` were
   widened proactively, the rest left as-is deliberately.
4. **`LIKE` vs `ILIKE` semantics** (SQLite case-insensitive ASCII `LIKE` vs PG
   case-sensitive `LIKE`): audited, code already uses `ilike` for search; no
   change needed, but future raw SQL must respect it.
5. **No automatic PG backup scheduler** was added (per scope: no new
   always-running services). Backups remain a manual/ops step per the runbook.
6. **`MC_DSN` must exist in every startup environment** (service, scheduled
   tasks). Without it the app fails fast with a clear message — by design —
   but that also means a bare shell without the variable cannot start the app.
