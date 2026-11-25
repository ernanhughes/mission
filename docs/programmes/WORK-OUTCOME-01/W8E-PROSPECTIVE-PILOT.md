# W8E-PROSPECTIVE-PILOT — Registered before execution, evaluated after

Objective (pre-registered): establish whether 08C-linked commit
88b7c04 reached the claimed remote. Episode
`ep:task:W8-PILOT-VERIFY-08C` + objective + 3 acceptance requirements
created BEFORE any check ran (registration receipt, scratch w6e).

| Step | Evidence |
| ---- | -------- |
| Registration | envelope `we:2b1799d176934a41` v1, digest-bound, human-authorized |
| Requirements | 3 explicit_user acceptance reqs (merge-base / branch -r / URL match) |
| Execution | deterministic read-only git plumbing (no model, no writes) |
| Linkage | execution link `wx:e3fe5af9aea942c0` (session, commit, review ref, $0) |
| Evaluation | 3/3 `satisfied_reported` (evidence linked; correctness unjudged) |
| Completion | **partial** (reported, not verified — rubric-honest) |
| Envelope size | 671 bytes, metadata-only (measured) |

Deviations encountered and handled: my own pilot re-runs duplicated
3 requirements on scratch (double execution of the script); cleaned
on scratch with the dupes recorded here (operational untouched — no
pilot rows exist on mc). URL-match requirement needed the new
`remote_ref` evidence kind (added with regression test) — the pilot
improved the mechanism, exactly the intended feedback direction.

What this proves: the 10-step lifecycle (§19) runs end to end on a
real task with all links intact. What it does not prove: general
performance (§21 comparison below), worker/workbench live propagation
(designed channels, manual links used), unconditional completion.
