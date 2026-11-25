# W9-TEST-EVIDENCE — Final regression + adversarial coverage

## Backend (SQLite-isolated, hermetic)

**218 passed, 0 failed** across the full work loop:
test_work_observation, test_work_episodes, test_work_triage,
test_work_extract, test_work_evaluate, test_work_continuous,
test_work_corrective, test_work_envelope, test_work_calibration,
test_work_policies, test_db_targeting, test_db_isolation,
test_migrations_and_seed.

New in W9 (31 tests):
- `test_db_targeting.py` (4): PG without `target=` refuses; error
  hides credentials; explicit target constructs; SQLite label-free.
- `test_work_calibration.py` (17): the hand-annotated corpus —
  insufficient vs failure, sibling evidence, existence-verified vs
  functional-reported, ambiguous abstention, terminal authorities,
  non-code work, claim verdicts, completion rollup (complete only
  when all mandatory verified; reported → partial; contradicted →
  incomplete; empty → unknown), minor-vs-major finding severity,
  dedupe, plus a size pin.
- `test_work_policies.py` (10): ladder semantics, fail-closed unknown
  level/capability, human-only policy change, continuous-pass gating,
  **explicit policy changes the outcome** (downgrade blocks, upgrade
  allows), semantic never granted without a policy service,
  scope canonicalization, manual endpoint 403, API roundtrip.

Additions after the W9 implementation review: four negative controls
(F1 semantic fail-open, F2 silent mechanical skip, F3 manual endpoint
bypass, F10 scope aliasing) plus the F5 PG test fix.

## PostgreSQL-specific

- `test_postgres_integration.py`: 15 skipped (requires MC_TEST_DSN by
  design); helper updated for the new target gate.
- Real PG exercised this stage: 050/051 apply + idempotent re-run on
  scratch (schema 51); SafeJSON verified against live PG (JSON-over-
  TEXT now returns lists); policy endpoints live on operational :8790.

## Frontend

- `tsc --noEmit`: clean.
- `npx vitest run`: **175/175 across 31 files**.
- Production build: succeeds (~1.4 s).
- No frontend changes in W9 (W8 surfaces reused); WorkEvaluation
  suite including the zero-POST assertions still green.

## Adversarial coverage map (§28)

| Required negative test | Where |
| ---------------------- | ----- |
| Database-target isolation | test_db_targeting, test_db_isolation |
| Migration authorization | W9A-MIGRATION-GOVERNANCE procedure + applied-vs-present audit |
| Invalid serialization | test_safejson_*, `_jl` test |
| False completion | calibration rollup + pilot verdict stable at partial |
| Unauthorized requirement confirmation | test_work_corrective (reviewer required, system/model refused) |
| Invalid Work Envelopes | test_work_envelope (unknown refs, unknown repo) |
| Incorrect execution linkage | test_work_envelope (bad session/commit/receipt/review) |
| Unresolvable Git references | same + W6 regression |
| Incorrect test receipt binding | envelope link rejects missing receipt |
| Review independence | W9A doc grading + W9B records (no inflation) |
| Stale evidence | W6 staleness tests |
| Duplicate proposals | test_work_corrective duplicate |
| Unauthorized handoff | test_work_corrective (approved + confirm) |
| Unattended execution | structural (no executor) + worker dry-run test |
| Budget enforcement | test_work_extract/evaluate budget tests |
| Scheduler concurrency | single-flight by construction; no timer exists |
| No model calls on page load | WorkEvaluation.test.tsx zero-POST |

## Preserved failures

None. Earlier W8-era jsdom flakes (ProjectPage tabs, InspectPage,
LivingBookPage) did not recur in the final run; they pass in
isolation and in the full suite. No test was modified to make a
result green.
