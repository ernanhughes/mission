# W3-TEST-EVIDENCE — 106 focused tests + neighbours, $0 model cost

New: `test_work_extract.py` (16: deterministic triage scoping, deterministic
extraction + idempotence, gating, unknown-episode/source/authority rejection,
budget cap, cache, vacuity echo rejection, loopback refusal, model triage
accept/cache/reject, API surface incl. 422s) + `test_work_triage.py` (12:
all classifications incl. probe/insufficient/review/research/queue paths).
Updated: `test_work_episodes.py` (+2 re-review minors with regression probes).

Results: **106/106 pass** (incl. 043 expectations in migrations test).
Neighbours (W1/W2/git/cost suites) re-run green where touched (see W1/W2
reports for counts; full backend suite deferred per policy). `ruff` clean on
all touched files.

Deliberately deferred: full-backend regression (required before operational
integration), `long` corpora, pre-existing-PG application of 043 (same
additive shape as validated 041/042; asserted at next authorized start).
Model-quality limits are NOT test-maskable: the suite pins pipeline behavior
(validation, caching, budgets, rejections); output quality at 0.5b is
reported as insufficient in W3-AI-PROJECT-PILOT, with the vacuity filter as
the deterministic backstop.
