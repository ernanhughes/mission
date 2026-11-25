# W9-COST-AND-PERFORMANCE — Implementation vs operating, measured

## One-time implementation (W9 only)

| Item | Quantity |
| ---- | -------- |
| Backend modules added | policies.py, work_policies.py (+ target gate in db.py, SafeJSON in models.py) |
| Migrations added | none (policies reuse `settings`) |
| Backend tests added | 27 (targeting 4, calibration 17, policies 6) |
| Frontend changes | none in W9 (W8 surfaces reused) |
| Provider spend | $0.00 |
| Local model calls | Mistral cross-family review (1 successful review call + 1 discarded empty attempt) |

## Operating cost (per pass, measured on scratch)

- Deterministic pass end-to-end: **7–8 s** (observe → recon → queue →
  eval → groups) for the ai scope.
- Storage growth this stage: 2 execution links, 2 assessments
  (scratch only); operational unchanged (31/9/293).
- Model invocations for evaluation: 0 (semantic disabled).
- Cache reuse: envelope/proposal/finding digests all hit; replay
  produced no duplicate rows.
- Job failures: 2 (both mine, both handled) — Worker dry-run
  `EXECUTOR_NOT_FOUND` for a non-existent `direct` backend (rejected
  by design, not a defect) and the ai `fast` test run returning
  CANCELLED with 0 tests (no changed files; honest empty receipt).

## Distinctions kept

- Provider charges $0.00; local hardware cost is real but not billed.
- Implementation effort (this stage) is one-time; the only recurring
  cost of the current operating mode is a manual deterministic pass
  when the operator chooses to run one — there is no timer.
- More findings ≠ better: the 287 open findings are the honest
  backlog, not an achievement metric.

## Manual effort (measured, this stage)

| Action | Time |
| ------ | ---- |
| Cross-family review setup + run | ~15 min (incl. one failed model) |
| Pilot re-execution + independent re-run | ~5 min |
| Policy inspection | 1 GET |
| Operational acceptance walk | ~5 min |

## Not measured (and why)

Scheduled 15-minute observation load: the schedule is not enabled, so
any figure would be invented. First activation should measure pass
duration and blocked counts; the receipt already carries both.
