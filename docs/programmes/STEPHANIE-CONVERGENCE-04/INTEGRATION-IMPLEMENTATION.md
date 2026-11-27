# SC4 integration implementation

## Current state

The Improvement workspace now has a bounded Mission-to-Stephanie path. Mission uses a fixed local CLI allowlist and a configured isolated run root to request source-bound investigations, inspect frozen experiment details, and dispatch a separately authorized fixture experiment through Stephanie's existing SC3 runner. Worker remains the execution owner; Praxis remains the independent evaluator. Mission owns approval and Work Outcome linkage. No arbitrary command or run-root input is accepted from the HTTP caller.

Investigation detail now queries Stephanie's retained SC3 CaseBook through the existing `sc3-retrieve` CLI command. The response is bounded and read-only, and reports retrieval unavailable rather than manufacturing results on CLI failure. The Improvement UI displays this live retained experience alongside the investigation and experiment evidence. The older `/api/improvement/records` projection remains explicitly historical.

Experiment completion, independent evaluation, Praxis recommendation, human acceptance, objective completion, and production promotion remain separate. After a verified result, Mission now records an explicit human accept/reject decision as a tagged append-only Work Corrective event. The event binds the investigation, source, candidate and digest, experiment, protocol digest, result digest, proposal version/scope hash, and records promotion as unauthorized. It does not alter the proposal lifecycle status, mark the objective complete, or authorize promotion. Repeated identical decisions are idempotent; a contradictory second decision is rejected.

## Qualification and activation

Focused backend checks passed: `test_improvement_api.py` and `test_work_envelope.py` (12 passed); the Improvement UI test file passed (4 passed). The isolated cross-service E2E passed (1 long test, 61.07 seconds) with the approved manual-handoff path included. The E2E remains marked long and is deliberately excluded from ordinary smoke runs; it was run here because it directly qualifies SC4B.

SC4B's current isolated browser flow now passes through approval, manual handoff, matching envelope registration, one exact fixture dispatch, live CaseBook retrieval, C1–C5 comparison display, C6/C7 result read-back, and post-result accept/reject controls. Read-back reported zero model calls, four retained records, a deterministic provider failure recorded for C6, and C7 rejected before execution. No human outcome decision was entered. The full negative-control matrix and concurrent operational dispatch qualification remain incomplete.

SC4C operational activation remains OFF: the normal service on `:8790` is still the pre-SC4 process, and there is no clean attributable activation package, verified operational backup/rollback, full compatibility qualification, or independent activation gate. No operational service restart or activation was performed. No commits or pushes were made.

The free-first product direction and current implementation limitations are recorded in Stephanie's product and routing documents. No conversational model router or provider default was changed as part of this integration.

Mission-specific detail: [workspace report](../../../../mission/docs/programmes/STEPHANIE-CONVERGENCE-04/MC-IMPROVEMENT-WORKSPACE.md).
