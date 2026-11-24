# MC-POSTGRES-01 — Cutover report (07)

## Pre-cutover state

- No Mission Control backend process running (port 8790 free); no writers.
- Target `mc` verified empty before baseline; schema version now **40**.
- Final consistent source backup
  `data/backups/mission_control-pre-pg-migration-FINAL-20261124T090600Z.db`
  (54,579,200 bytes, sha256
  `ef3c9e4e72eabe3330f7b36294cfa455dca4df9c3bfa2f17bd34772b199b6df0`,
  integrity ok, FK violations none).

## Cutover

1. `MC_DSN` provided as a persistent Windows environment variable (no secret
   in repo, startup scripts, docs, or logs).
2. Application starts with `Database.backend == postgresql`; startup logs the
   redacted URL and applied migration versions. SQLite fallback is refused in
   production (`MC_DSN`-required guard; `MISSION_CONTROL_ALLOW_SQLITE=1` can
   only re-enable it explicitly and is not set).
3. Startup confirms schema version 40, all API routers mounted, background
   services (health monitor, maintenance, discovery, git activity) initialize
   against PG.

## Post-cutover verification (http://127.0.0.1:8790)

Measured against the live PG-backed backend:

- `/api/health`: `{"status": "ok", "version": "0.1.0", "database": "ok",
  "schema_version": 40, "ai_enabled": true, "monitor_enabled": true}`.
- `/api/diagnostics/database`: `{"backend": "postgresql", "connectivity": "ok",
  "database": "mc", "server_version": "16.8", "schema_version": 40, ...}`
  with redacted URL and healthy pool.
- Books page: all **41** books, original order; reversed-order write +
  refresh + restore roundtrip green through the live API.
- Applications: **11** registered; Workbench health checks running.
- Cultivation: **15** goals (+ skills/history) visible.
- Websites: **4** registered sites with inventory.
- Execution/governance: **18** workflows with history.
- Background monitor pass persisted **17** new `health_observations` to PG.
- New writes confirmed in PG; the SQLite file's size/mtime/counts are
  identical before and after all PG-backed runs (retained read-only).
