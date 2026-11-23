# MC-COST-01 — Implementation report

## What was built

Read-only **Cost** under System navigation (`/cost`), backed by a narrow
`mode=ro` SQLite adapter over the local OpenCode database.

- Backend:
  - `backend/mission_control/config.py`: `opencode_db_path`
    (`MISSION_CONTROL_OPENCODE_DB`, default
    `C:\Users\ernan\.local\share\opencode\opencode.db`).
  - `backend/mission_control/opencode_cost/__init__.py`: `OpencodeCostStore`
    (raw `sqlite3` `mode=ro`, per-query open/close, no WAL/migration changes),
    Dublin calendar bounds (`resolve_bounds`), message-level aggregation
    (session rollups never added to message sums), bounded scans (100k cap,
    5k session-meta cap, 5k message cap for detail).
  - `backend/mission_control/api/cost.py`: `GET /api/cost/status|summary|
    sessions|sessions/{id}|spikes` — GET-only, no model calls.
  - `backend/mission_control/schemas.py`: `Cost*Read` mirrors.
  - `backend/mission_control/main.py`: `app.state.opencode_cost` + router.
  - `backend/tests/test_opencode_cost.py`: 7 hermetic tests (synthetic DB,
    aggregation without double counting, Dublin boundaries, pagination,
    parent/child, failures, unavailable source, deterministic spikes).
- Frontend:
  - `frontend/src/pages/CostPage.tsx`, route `/cost`, System nav with Wallet
    icon, `types/api.ts` Cost mirrors, `src/test/CostPage.test.tsx`
    (GET-only on load, unavailable state).

## Verification

- `ruff check` passes for backend cost files.
- `pytest backend/tests/test_opencode_cost.py` — 7 passed.
- Broader: `test_opencode_cost + test_git_activity + test_security` — 23 passed.
- Frontend: `CostPage.test` 2 passed; `npm run build` succeeds.
- Independent SQL check (real DB, `mode=ro`):
  - Dublin 2026-11-22: store 7,096 req / 5.397842812 vs SQL 7,096 / 5.397842812.
  - Dublin 2026-11-21: store 762 req / 0.337832452 vs SQL identical.
  - Token in/out sums match.

## Behaviour and limits

- Missing/locked/incompatible sources return `available:false` with reason;
  never silent zeros. Locked WAL reports `locked` with retry hint.
- Provenance strings state: `cost` is balance charge; Go allowance use is
  cost 0 locally and not convertible to percent.
- Normal operation performs no AI calls; opening Cost never consumes allowance
  (asserted in frontend test).

## Follow-ups (not in this release)

- Optional provider meter (`/v1/usage`) as a separate, explicit source.
- CSV import for provider logs to reconcile unattributed usage.
- Worker/ECK budgeting proposal: `docs/MC-COST-01-WORKER-PROPOSAL.md`.
