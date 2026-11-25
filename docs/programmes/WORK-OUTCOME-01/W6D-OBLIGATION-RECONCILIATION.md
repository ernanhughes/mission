# W6D-OBLIGATION-RECONCILIATION — Findings close on evidence, not on age

Rule (§21): an open finding resolves only with cited closure evidence;
later commits alone never close anything. Implemented as
`reconcile_resolved` (manual POST, recorded): `missing_requirement`
findings whose requirement now carries a satisfied assessment move to
`resolved` with the assessment id + verdict + timestamp in
`closure_evidence`. Rows and history preserved.

Operational result: 5/5 stale `missing_requirement` findings from the
intermediate 05 run resolved against the satisfied assessments (4
reported + 1 verified); 0 auto-closures elsewhere — the 288 open gaps
still lack execution/push/SHA records, so they stay open no matter how
much later code exists. Deferred/superseded requirements remain
distinguishable (verdict-carried, never rewritten as complete).
