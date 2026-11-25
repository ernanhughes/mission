# W8D-TEST-EVIDENCE-INTEGRATION — Receipts, not reported counts

Reuse, not duplication: AITest already records per-test rows
(`relpath…last_outcome`), per-execution receipts (`execution_id`,
counters, `created_at`, full `receipt_json`), and issues. The W8
linkage is `test_receipt_ref` on the execution link + requirement
association — no new testing system, no test runner in Mission
Control.

Discipline preserved from W6B: a reported count ("214 passed") is
never treated as a receipt. Binding requires (work id, requirement/
criterion, execution id, repo + exact revision or working-tree digest,
command/suite identity, start/finish timestamps, exit status, result
summary, artifact refs, limitations). `test_receipt_ref` carries the
receipt id; the receipt itself stays in AITest.

Pilot note: the W8E pilot used deterministic git plumbing, not a test
run — so no test receipt was produced or claimed. The first receipt-
bound pilot is explicit W8 follow-up (also the missing piece for an
unconditional verified-complete episode).
