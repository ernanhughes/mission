# W7-EVIDENCE-RECOVERY — Recover first, modify never (by default)

Principle (§7): the first response to a verification gap is evidence
recovery, not another AI rewrite. Action taxonomy enforces it:
provenance/test/requirement gaps map to RECOVER_*/REPRODUCE_*;
code-change categories require confirmed defects or verified-missing
requirements and are never the default.

## Recovery sources used in the pilot (deterministic, read-only)

- Git history: `git log --grep`, `merge-base --is-ancestor`,
  `branch -r --contains` against the ai repo (e.g. de28820 ∈
  origin/main at the exact claimed remote → push proven).
- Existing reviews/qualifications: R1-REVIEW + qualification gates as
  requirement + evidence provenance (W6A, reused in W7 confirmations).
- AITest receipts/inventory: per-test records with timestamps/counters
  (surveyed; available as execution evidence for REPRODUCE_VERIFICATION
  without re-running suites).
- Workbench receipts / worker usage ledgers: surveyed, read-only.

## What a new verification run proves (and does not)

A fresh passing run establishes current state; it does NOT corroborate
the original historical claim (different revision, different run).
The commission template states this explicitly (§10); verification
records the new evidence alongside — never rewriting — the old claim.
The 08C exemplar closed on contemporaneous remote containment, not on a
re-run.

## Pilot recoveries

- 05-R1: 4 evidence commits associated; 13 human-attested file links;
  bare-SHA mechanism repaired (W6) → 6 reported + 1 verified.
- 08C: push proven for linked de28820 at the claimed remote →
  finding f7089844 closed with cited evidence (scratch-validated flow,
  replicated operationally with identical evidence).
