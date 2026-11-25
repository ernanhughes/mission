# W2-TEST-EVIDENCE — 74 focused + neighbours, zero model calls

New: `backend/tests/test_work_episodes.py` — 25 engine tests (multi-objective
split, shared-task grouping, task-shape classification incl. W2/WORK-OUTCOME,
artefact rejection, explicit/cross-repo/ambiguous/unresolved commit handling,
unique-prefix resolution, timestamp-only rejection, common-file insufficiency,
review_of without resolution inference, hierarchy + cycle rejection, non-code,
uncommitted, missing-evidence abstention, conflicts recorded, identity
stability, chain+task coexistence) + 6 service/API tests (task episode with
explicit commit link, idempotent replay, incremental join, interrupted run,
hierarchy, full HTTP pipeline incl. 404/422 + unresolved/coverage endpoints).

Results: 74/74 pass (`test_work_episodes` 31 + `test_work_observation` 43 incl.
2 new extractor-pattern tests + `test_migrations_and_seed` 042 expectations).
Neighbours: git activity/daily + opencode cost ×2 + persistence conventions
39/39 green; `ruff` clean on all touched files. Tests caught 5 real bugs:
`top_level`→`toplevel`, global-scan vs project filter (SQL-side fix), slash in
bucket ids (URL 404), `_connect_ro` patch path, degenerate-SHA entropy guard
working as designed.

Deliberately deferred: full-backend suite, `long` corpus (per test policy);
pre-existing-PG application of 042 (same additive shape as validated 041;
asserted at W3 entry).
