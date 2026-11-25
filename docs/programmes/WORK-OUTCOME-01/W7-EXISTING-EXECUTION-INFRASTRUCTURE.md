# W7-EXISTING-EXECUTION-INFRASTRUCTURE — Reuse map + ownership boundaries

Surveyed read-only 2026-11-24 (mission, workbench, worker, ai, praxis,
writer, cocoder, mission aitest). No code copied; patterns mirrored.

## Approval pattern (mirrored in wo_proposals, not reused by reference)

- mission `workflows/service.py:approve` (confirm + scope_acknowledged +
  approval_hash pinning) and `praxis_proposals/service.py:approve`
  (human-only SELF_APPROVAL_DENYLIST, confirm, approval_digest) are the
  template: W7 transitions require confirm for all approval gates,
  human actor for approve, scope_hash re-verified at approval time.
- mission `integrations/service.py:start_action` (confirm-gated queue)
  and `workflows/service.py:execute` (approved snapshot + confirm) are
  the handoff template: W7 `record_handoff` only accepts approved
  proposals and records — never starts — execution.

## Execution routes (reused, not duplicated)

- Primary: **manual copy** — commission text assembled deterministically
  (§9), copied by the operator, executed wherever they choose, linked
  back by hand (`wo_execution_links`, route=manual). Always available;
  demonstrated in the pilot.
- Candidate: **worker `POST /v1/work`** (worker work-request.v1 +
  receipt/work-result schemas, usage ledgers). Status: designed, NOT
  demonstrated — no configured route in this environment; the routes
  endpoint reports it unavailable with that reason. No competing
  executor, queue, or task platform was created.
- Readiness evidence: mission `worker_runtime` passive GETs only;
  AITest receipts (`aitest_receipts` counters + timestamps) as test-
  evidence sources for REPRODUCE_VERIFICATION; cocoder read-only
  verification + ai frozen protocols/RESULTS as evidence patterns.

## Review/verification sources (read, not duplicated)

- mission `GitReview` records, ai `docs/reviews/*-REVIEW.md` +
  `docs/qualification/*` gate tables, writer/cocoder governed
  execution receipts. W7 proposals cite these; they do not re-run them.

## Ownership boundary

Mission Control coordinates and presents corrective work (proposals,
approvals, handoffs, verification state, closure). Execution belongs to
existing infrastructure (worker/workbench/OpenCode/manual). The day W7
starts executing code itself is the day it has violated its charter —
the service layer contains no executor, only records.
