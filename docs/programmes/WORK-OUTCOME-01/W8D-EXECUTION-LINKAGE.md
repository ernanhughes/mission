# W8D-EXECUTION-LINKAGE — Trace, don't re-execute

`wo_execution_links` (extended by 050 with `session_id`,
`commit_sha`, `test_receipt_ref`, `review_ref`) records, per handoff:
route, external ref, model, status, timestamps, cost, and the four
evidence pointers. Recording ≠ execution — the service starts nothing.

Pilot trace (scratch): proposal-linked manual handoff
(`wx:e3fe5af9aea942c0`, route manual, session `w8e-pilot-session`,
commit `88b7c04`, review ref = re-runnable commands, status
reported_complete, $0). Multiple executions per episode supported
(append rows); parent execution via `parent_work_id` on the envelope.

Status vocabulary is recorded, not sensed: `handed_off`,
`reported_complete`, `verification_pending`, `verified_resolved`,
`failed` are operator/model-reported states. Completion of execution
is never equated with objective completion (evaluation decides that
against the envelope's requirements).
