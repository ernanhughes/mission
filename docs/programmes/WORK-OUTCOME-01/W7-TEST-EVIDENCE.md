# W7-TEST-EVIDENCE — Focused suites, builds, deferrals

## Backend (SQLite-isolated, hermetic)

- `test_work_corrective.py`: 10 passed — taxonomy mapping, proposal
  create/derive/duplicate/cross-episode rejection, approval gates
  (human+confirm+hash), scope voiding, 13-section commission, handoff
  gates (approved + confirm + manual-only), resolve/reopen with
  history, confirmation decisions + amend versioning, API roundtrip
  (routes/proposals/confirmations + 422 paths).
- Full work loop (observation + episodes + triage + extract + evaluate
  + continuous + corrective + migrations_and_seed): **173 + new
  corrective tests green** (final count recorded in FINAL-REPORT).
- `ruff check`: clean on all touched backend files.
- PG validation: 048 applies cleanly on scratch w6e (schema 47→49
  with unrelated 049; idempotent re-run). Operational 048/049 arrived
  via operator-restart auto-apply (additive, empty tables, counts
  unchanged — see VERIFICATION-AND-CLOSURE).

## Frontend

- `tsc --noEmit`: clean. Production build: succeeds.
- `WorkEvaluation.test.tsx`: 14/14 — 12 standing + proposals-read-only
  + generate-commission flow (create → toast → open proposals).
- Full suite: 167 passed / 1 pre-existing ProjectPage failure
  (another workstream's committed TestsTab; preserved, unrelated).
  InspectPage/LivingBookPage full-run flakes pass in isolation.

## Deferred with reason

Live scheduled-loop soak (loop stays disabled); worker dispatch demo
(no route); semantic commission drafting (explicitly not built);
ecosystem/full-backend suites (policy: focused + neighbours).
