# W9B-AITEST-EVIDENCE — Receipts bound, not manufactured

Mechanism (existing, reused): AITest runs record per-execution
receipts (`execution_id`, project, snapshot, status, counters,
duration, timestamps); per-test rows; issues. Mission Control reads
them via `GET .../receipts`; `wo_execution_links.test_receipt_ref`
binds a receipt to an execution. No new testing system; no test
runner in Mission Control.

Demonstrated 2026-11-25 on operational :8790 (approved testing
infrastructure, bounded `fast` operation on the ai pilot):
run-fd6d75a78b154463 → receipt exe_9054fcca10044918 (0/0/0,
CANCELLED — no changed tests existed; recorded as-is, never
upgraded to a pass). First-ever ai receipt (`last_receipt_id` was
empty): the project now has baseline ambient evidence.

Unit coverage: `link_execution` accepts present receipts, rejects
missing ones (`test_link_execution_accepts_present_receipt_and_
review`). What remains: binding a receipt to a genuine test-
requirement (no ai requirement currently demands a test run;
manufacturing one to complete the pilot is forbidden).
