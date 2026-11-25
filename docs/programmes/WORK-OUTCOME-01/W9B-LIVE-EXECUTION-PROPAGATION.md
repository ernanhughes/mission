# W9B-LIVE-EXECUTION-PROPAGATION — What runs, what was proven

## Worker route: REACHABLE, dry-run proven, no execution performed

- Server started locally for the test (`bun src/cli/cli.ts serve`,
  :7317; stopped afterwards — environment left as found).
- `POST /v1/work {objective, task_id, episode_id: ep:task:W8-PILOT-
  VERIFY-08C, workspace, execution:{backend:opencode},
  options:{dry_run:true}}` → 200 `worker.work-result.v1`,
  `request_id wrq_60dab...`, status `AWAITING_ACCEPTANCE`,
  `DRY_RUN_NO_EXECUTOR_INVOKED`; readback via `/v1/work/{id}` and
  `/v1/jobs` confirms the job ledger.
- Propagated and echoed: `project_id: ai`, `worker_request_id`.
  NOT echoed in the dry-run receipt: `task_id`/`episode_id`
  (accepted, not reflected). Full identity echo lives on the
  execution-summary path, which requires a real executor.
- Blockers for live execution: opencode CLI absent (executor
  `available:false`), no paid model authorization sought. No live
  model invocation was performed or is claimed.

Honest status: transport + acceptance demonstrated; end-to-end
identity echo through a real executor remains unproven. Manual
handoff remains the demonstrated path (§11 fallback, not a gap
in the record).

## Workbench route: BLOCKED (documented, not worked around)

UP on :7420, but workflow runtime unconfigured (needs
`WORKBENCH_WORKFLOW_*` env + restart) and every run/evidence call
requires a paired owner session (403 otherwise). Precise
dependencies recorded; no action taken (operator-owned service).

## AITest route: LIVE and exercised

- `POST /api/tests/projects/proj_20e7dc7333078dd1/run
  {"operation":"fast"}` on operational :8790 → run
  `run-fd6d75a78b154463` completed in ~11s (no changed tests:
  0/0/0, verification_status CANCELLED — an honest empty result,
  not a pass).
- Receipt `exe_9054fcca10044918` retrieved with execution identity,
  timestamps, counters, duration. Project row updated
  (`last_receipt_id`, `last_status: CANCELLED`).
- This receipt is ambient project state, NOT pilot verification —
  the pilot's requirements are git-evidence, not test outcomes.
  Conflating them would be evidence laundering; the distinction is
  preserved in W9D-TEST-EVIDENCE-INTEGRATION.
