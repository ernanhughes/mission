# W7-AUTHORIZATION-AND-EXECUTION — Explicit approval, manual handoff

## Authorization (§10, implemented + tested)

- Draft → ready_for_review: operator click, no confirm needed (still
  no authority conferred).
- ready → approved: human actor (non-empty, not system/model) +
  confirm=True + scope_hash match. Anonymous/system/self approval
  rejected (tested). Scope edits void approval (version bump).
- Scope change after approval: hard block at approve time + re-review
  required; renewed approval binds the new version.

## Execution (§11, adapter, not executor)

- `record_handoff` accepts only `manual` in this environment (worker
  route reports its precise limitation: no configured route). Manual
  handoff requires an approved proposal; it records (never starts) the
  run and moves approved → queued as a bookkeeping state.
- running/reported_complete/verification_pending are subsequent
  operator-recorded states, not sensed automation. No automatic
  commits, pushes, deployments, or repository modifications exist on
  any path; the service layer contains no executor, subprocess runner,
  or model caller.
- Cost: handoff records cost_usd (0.0 default); execution expenditure
  stays with the executing infrastructure. Paid budget remains $0
  and unwirable from W7 surfaces.

## Pilot trace (scratch wp:75beaecfac034332)

draft → ready_for_review → approved (w7-human, bounded read-only git
check) → queued via manual handoff ("no external run") → finding
resolved with cited remote-containment evidence. No code ran, nothing
was modified, the loop still closed — because the work WAS the
evidence recovery.
