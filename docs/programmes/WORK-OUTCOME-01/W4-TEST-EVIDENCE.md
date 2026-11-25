# W4-TEST-EVIDENCE — 180 focused green + full suite in flight

Focused suites (all deterministic except the gated semantic paths, which use
fake backends; $0): `test_work_evaluate` (32: 15-case calibration corpus,
claim/commit/review verification, identity/dedupe incl. digest reuse,
rollup strictness, service determinism, missing-work, auto-link, paraphrase/
vacuity/eval-vacuity/ambiguous-upgrade/strength-gate/unknown-ref rejection,
API incl. 404/422). Neighbours re-verified in one process: 180 passed
(work_* + migrations 041–045 + conventions + git activity/daily + cost).

Full backend suite (stable tree): 999 passed / 1 failed / 17 skipped
(22 min). The single failure is `test_cultivation_github.py::
test_live_github_inventory_read_only` — a live authenticated `gh` CLI check
asserting ≥306 GitHub repos; environmental (network/auth-dependent), in a
module W4 never touches. The earlier migration-test failure does not recur
(confirmed as the mid-run edit race). Skips are environmental (no
MC_TEST_DSN, no Writer runner, no Docker daemon), not W4-related.

`ruff` clean on all touched files. Deliberately deferred: `long` corpora
(per policy).
