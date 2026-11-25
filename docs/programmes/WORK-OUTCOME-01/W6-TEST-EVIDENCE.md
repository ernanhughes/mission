# W6-TEST-EVIDENCE — Focused suites, builds, and what was deferred

## Backend (SQLite-isolated, hermetic)

- Backend: `test_work_continuous` 19 passed (grouping, severity
  reconcile + idempotence + contradiction preservation, staleness
  lifecycle, manual requirement validation, auto-link resolvable refs,
  cross-scope recon idempotence, auto-flag, run_pass, tightened
  objective-authority); `test_work_evaluate` 36; full focused work loop
  (observation + episodes + triage + extract + evaluate + continuous +
  migrations_and_seed): **164 passed, 0 failed**.
- `test_work_extract.py`: full file green with continuous (34 combined).
- `test_work_episodes.py`, `test_work_observation.py`,
  `test_work_triage.py`: ran with the work-focused loop (see below).
- `ruff check`: clean on all touched backend files.
- Full backend suite: NOT run as default (policy: focused + neighbours;
  `long`/model/integration excluded). Shared-infrastructure change
  (models.py additive tables, evaluate overview join) is additive-only;
  migration test file updated? No — 047 needs a registry assertion.
  Recorded below as a gap: add 047 to the migration-count test before
  merge (uncommitted state, no merge performed).

## Frontend

- `tsc --noEmit`: clean. Production build: ran in W6E validation
  (see W6E-OPERATIONAL-VALIDATION).
- `WorkEvaluation.test.tsx`: 12/12 — 9 standing (incl. zero-POST) + 3
  new: groups aggregation display + drill-down, Controls no-POST-on-open,
  stale badge render. Full frontend suite: 165/166 — the single failure
  is the pre-existing ProjectPage eight-tabs expectation (another
  workstream's committed TestsTab makes 9; unrelated file, preserved
  as-is, not fixed). Pre-existing ProjectPage/TestsTab state preserved,
  not run in isolation, not fixed.

## Deferred with reason

- Ecosystem-wide or full-suite runs: out of scope for a stage loop.
- Live scheduled-loop soak: loop stays disabled; manual passes +
  unit-tested guards substitute (documented in W6D).
