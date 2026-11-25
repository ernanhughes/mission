# W8-TEST-EVIDENCE — Focused suites, builds, deferrals

## Backend (SQLite-isolated, hermetic)

- `test_work_envelope.py`: 5 passed — unknown-ref rejection,
  human-auth gates, authorization-bound digest, duplicate collapse,
  version supersession, resolved-only manual links, size probe
  (metadata-only, 671 bytes on the pilot).
- Full work loop (observation + episodes + triage + extract +
  evaluate + continuous + corrective + envelope + migrations):
  **178 passed, 0 failed** (final run).
- `ruff`: clean on all touched files.
- PG validation: 050 + 051 apply cleanly with idempotent re-runs on
  scratch w6e (schema 51); operational stays at v49 (048/049 arrived
  via operator restart, additive, empty tables, counts unchanged).

## Frontend

- `tsc --noEmit`: clean. Production build: succeeds (~2s).
- WorkEvaluation suite: 15/15 (incl. envelope tab read-only test).
- Full suite final run: **175/175 across 31 files**. Earlier runs
  showed moving flakes (ProjectPage eight-tabs once; InspectPage +
  LivingBookPage once) — each passes in isolation and all pass in the
  final full run; attributed to jsdom resource contention under
  parallel workers, not to W6–W8 changes (work-evaluation surfaces
  + additive api types only). No stable failure on record.

## Deferred with reason

Live worker/workbench propagation (designed channels, manual links
used); scheduled-loop soak; semantic drafting; ecosystem/full suites
(policy: focused + neighbours).
