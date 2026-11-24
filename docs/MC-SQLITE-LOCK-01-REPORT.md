# MC-SQLITE-LOCK-01 — SQLite Locking During Book Reordering: Investigation Report

- Date: 2026-11-24
- Repository: `C:\Projects\mission`
- Symptom: `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked`
  logged as `Health check failed for workbench`, originating at
  `backend/mission_control/processes/manager.py` `check_health` → `session.flush()`,
  observed while reordering books in the sidebar.

## 1. Root cause

The failure is a **general SQLite write-contention weakness in the background health
monitor**, not a defect in the book-reorder endpoint. Two defects combined:

1. **`check_health` held a database connection and an open transaction across a
   network probe.** The old code opened `with self.database.session()`, ran three
   `SELECT`s, then `await probe(...)` (up to 2 s of network I/O, longer if the event
   loop was already delayed), and only afterwards `INSERT`ed the health observation
   and `flush()`ed. The session — and therefore a pooled SQLite connection with an
   open read transaction — was checked out for the whole probe.
   (`backend/mission_control/processes/manager.py`, old `check_health`, old lines ~878–926.)
2. **The observation write then blocked the asyncio event loop.** `session.flush()`
   is synchronous. Under contention it waits inside SQLite's busy handler for the
   full `PRAGMA busy_timeout` (30 000 ms, verified at runtime) **on the event-loop
   thread**, freezing the monitor loop and delaying every other probe. When the
   busy wait expired, the raw `OperationalError: database is locked` propagated and
   was logged as a health-check failure, conflating *“we could not store the
   observation”* with *“Workbench is unhealthy”*.

The 33-second gap in the report is explained exactly:

- `observed_at` (`07:49:43`) is generated with `now_iso()` **after** the probe
  returns (probe itself took ~2 s and timed out: `state=unavailable`,
  `detail=Health check timed out after 2s`).
- `session.flush()` then waited the full 30 s busy timeout for the write lock and
  failed at `07:50:16` (≈ 2 s probe + 30 s busy wait + overhead).

Reproduction (pre-fix, isolated temp DB) measured **34.5 s** from `check_health`
start to `OperationalError`, with the failing statement being the observation
transaction's first `INSERT` (`INSERT INTO activity_events …`, flushed from
`record_activity` inside the same transaction). After contention ended, the next
`check_health` succeeded — matching the intermittent production symptom.

### Relationship to book reordering: correlated but not causal

Book reordering widens the race window but is neither necessary nor sufficient:

- `POST /api/books/reorder` → `reorder_books_route`
  (`backend/mission_control/api/projects.py:750`) → `reorder_books`
  (`backend/mission_control/projects/service.py:630`) runs in one short
  request-scoped transaction and returns 200 only after commit. It updates only the
  parent `projects` rows (`priority`, `display_order`, `updated_at`) plus one
  `activity_events` row. HTTP 200 therefore means the order **is** durable.
- Controlled test: **30 rapid reorders racing 10 concurrent health checks all
  succeeded** with zero errors — reordering alone cannot produce the lock.
- Any concurrent writer holding the SQLite write lock for longer than the busy
  timeout produces the identical failure. Candidates present in this codebase:
  the publication maintenance pass (holds a session open across chapter
  filesystem scans with a per-book `session.commit()`),
  `refresh_repositories` write phase, Git activity index batch commits, discovery
  scans, and the reorder commit itself racing the health flush. In WAL mode readers
  never block writers, so the concurrent `GET /api/books` polling is innocent;
  the writers are what matter, and SQLite permits only one at a time.

The frontend is also innocent: both reorder controls (`HomePage.tsx:49`,
`BooksPage.tsx:357`) issue **one** `POST /api/books/reorder` per click, disable
the buttons while `reordering`, and reload afterwards. No drag-spam, no duplicate
or overlapping reorder requests, no polling on the book lists (dashboard polls at
45 s only). No UI change was needed.

## 2. Fix (all changes local, uncommitted)

**`backend/mission_control/processes/manager.py`** — health-monitor isolation:

- `check_health` is split into three phases: `_health_snapshot()` loads detached
  probe inputs (`app_name`, `health_type/health_url/expected_port`) in a
  short-lived session that is closed **before** any `await`; `await probe(...)`
  runs with no database resources held; `_persist_health_observation()` writes the
  observation plus the conditional `application_health` activity event in a fresh,
  short, dedicated transaction. Both database phases run via `asyncio.to_thread`,
  so even a 30 s busy wait no longer stalls the event loop.
- A persistence lock failure is converted to `Conflict("Health observation could
  not be persisted because the database is busy", detail="Probe result was
  {state}: {detail}. The monitored application state is unchanged; retry
  shortly.")` chained from the original `OperationalError`. Probe outcomes
  (e.g. `unavailable / timed out`) and storage failures are now distinguishable,
  and a storage failure never rewrites health state.
- The monitor body was extracted to `_monitor_once()` (same semantics, including
  `CancelledError` propagation). It logs persistence contention concisely as
  `health_observation_persistence_failed application_id=… detail=…` without a
  stack trace, logs genuine probe errors as before, and **never stops the loop**
  because one observation could not be persisted.

**`backend/mission_control/projects/service.py`** — shorter reorder transactions:

- `reorder_books` and `reorder_projects` now do one batched `SELECT … WHERE id IN
  (…)` instead of one `session.get` round-trip per row, then apply the updates in
  the same atomic transaction. Semantics preserved: unknown ids ignored,
  unlisted books keep their position, duplicates resolve to the last occurrence,
  `record_activity` still recorded, commit still owned by the request session.
  This shrinks the write-lock window; it does not change ordering rules.

**`backend/mission_control/persistence/db.py`** — configuration made explicit and
testable:

- `Database(..., busy_timeout_ms=30_000)` (default unchanged) is applied to every
  pooled connection via the connect listener; `connect_args` now also sets the
  pysqlite `timeout` to 30 s so behaviour is explicit even before the pragma runs.
  Runtime values verified on Windows: `journal_mode=wal`, `busy_timeout=30000`,
  `foreign_keys=1`. No migration, no PostgreSQL, no WAL change.

Deliberately **not** done: unbounded/broad retries (the 30 s busy timeout already
bounds the wait — retrying would multiply worst-case API latency), longer
timeouts, swallowing the exception, disabling the monitor, UI changes, schema
changes.

## 3. Evidence

| Check | Before fix | After fix |
|---|---|---|
| Pool connections held across `await probe` | 1 (spy-probe) | 0 (same spy-probe) |
| Writer holds `RESERVED` 40 s, then `check_health` | `OperationalError: database is locked` after ~34.5 s, event loop stalled | `Conflict: … database is busy` with probe result in `detail`; event-loop heartbeat max gap 0.52 s over the whole stall |
| 30 reorders + 10 concurrent health checks, no contention | all succeed | all succeed (unchanged) |
| Recovery after contention ends | next `check_health` succeeds | same; `_monitor_once()` completes, interval 30 |
| Failed observation insert | raw `OperationalError`, health history ambiguous | zero new rows, previous state untouched, monitor logs `health_observation_persistence_failed` and continues |

Live production verification (server still running pre-fix code — restart pending,
see §6): swapped the first two of 41 sidebar books via the real API (200, order
changed and persisted), confirmed `/api/applications/workbench`,
`/api/health` (`database: ok`), then restored the original order. Final state
verified twice: 41 unique books, priorities exactly 1–41, id list identical to
the pre-test order. (One intermediate read in the one-liner printed a mismatch
milliseconds after the restore POST; the two follow-up reads confirm the
committed order is correct — reported here for honesty.)

## 4. Tests

New: `backend/tests/test_sqlite_lock_health.py` (7 tests, all pass in 45.6 s).
Contention tests use **real** SQLite file locking (`BEGIN IMMEDIATE` from an
independent connection) with `busy_timeout_ms=500` so the identical code path
fails fast; production default is untouched.

- single reorder persists; reorder-then-reload stable across clients;
  unknown ids ignored with all books kept;
- 4 reorder threads × 10 + 10 concurrent health checks: no errors, no
  lost/duplicated books, sequential priorities, 10 observations;
- no connection held across the probe (pool `checkedout == 0` during `await`);
- contended writer → bounded `Conflict` naming the busy database and preserving
  the probe result; no partial row; pool recovers;
- `_monitor_once()` survives persistence failure (logs
  `health_observation_persistence_failed`), latest health state stays at the
  pre-failure value (`healthy/baseline`), subsequent pass writes again.

Existing suites (from `backend/`):

- `test_sqlite_lock_health.py`: 7 passed
- `test_registry_and_projects.py` + `test_fiction_books.py`: 21 passed
- `test_processes.py` + `test_migrations_and_seed.py` (incl. integration): 14 passed
- `ruff check` on all touched files: clean
- Frontend `HomePage.test.tsx` (reorder contract): 3 passed
- Full backend suite (first pass, `-x`): **383 passed, 1 failed** in ~8.5 min.
  The single failure is `test_mc_websites_cultivation.py::
  test_blog_observation_award_and_recent_ordering` — a **pre-existing,
  weekday-dependent flake unrelated to this fix**: it posts items dated
  `now-1d`/`now-2d` and asserts both fall in the calendar `this_week`, but on
  Tue 2026-11-24, `now-2d` is Sunday 2026-11-22 (previous ISO week), so the
  count is 1, not 2. Neither the test nor `cultivation/sources.py` is touched
  by this change (no worktree modifications; introduced in commit `2341e03`),
  and none of the changed files (`processes/manager.py`,
  `projects/service.py`, `persistence/db.py`) are in its import path.
  Follow-up: fixed in `test_mc_websites_cultivation.py` by pinning the test's
  reference time to a mid-week Wednesday and passing it via
  `blog_observation(..., now=now)` (the function already supports an explicit
  reference time) — the full file now passes (19/19), making the suite
  weekday-independent.
- Full second pass (no `-x`, whole `tests/` tree): **858 passed, 2 skipped, 1
  failed** in ~25 min, the single failure being the weekday flake above
  (since fixed). Skips are environmental (Writer CLI path unconfigured, Docker
  daemon unavailable).

## 5. Before / after

Before: a contended writer during a reorder/monitor overlap made the Workbench
probe result (`unavailable`, timed out after 2 s) unpersistable; the flush
blocked the event loop ~30 s and raised `OperationalError: database is locked`
at `session.flush()` (`manager.py:924`), logged with a full stack trace as
`Health check failed for workbench`, ~33 s after the observation timestamp.

After: the same overlap yields — after the same bounded busy wait, off the event
loop — a 409-style `Conflict` carrying the probe result, a one-line
`health_observation_persistence_failed` warning, unchanged health history, a
surviving monitor loop, and full recovery on the next pass. Book ordering,
health endpoints and existing APIs are behaviour-identical in the uncontended
case.

## 6. Remaining risks / operational impact

- **Restart required**: the running server (PID observed serving `:8790`) still
  executes the old code. Restart Mission Control via its normal local startup
  procedure; no migration or config change is needed (WAL settings persist in
  the DB file; `busy_timeout_ms` default equals the old hardcoded value).
- Worst-case API latency under sustained write contention is still up to the
  30 s busy timeout for the unlucky writer (now classified as 409 instead of
  500, and no longer freezing the event loop). Lowering it globally would trade
  hangs for more frequent transient failures; not recommended without
  production contention metrics.
- The general single-writer limitation of SQLite remains: the publication
  maintenance pass (`publication/maintenance.py:558` — session held across
  chapter filesystem scans with per-book commits) and Git activity batch writes
  are the likeliest long-lock holders. They were documented, not refactored
  (out of scope for the minimal fix); if lock warnings recur, instrument which
  writer holds `RESERVED` and shorten *its* transaction next.
- Browser-side reorder verification (drag/click in `/books` with devtools open)
  was not performed — API-level verification only; UI behaviour is unchanged by
  this fix.
- Full backend suite result pending (background run).
