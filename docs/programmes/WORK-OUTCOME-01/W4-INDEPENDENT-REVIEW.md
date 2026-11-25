# W4-INDEPENDENT-REVIEW — 8 findings, all fixed in code + tests

## Separate-agent review (same model family, not cross-family)

Verdict: CONDITIONAL (accept with fixes). Deterministic core verified sound;
model-gated paths bounded. All 8 findings reproduced and fixed:

1. F1 sibling over-fire (unresolved sibling counted as corroboration) →
   fixed: `siblings = any(e.resolved …)` + regression test.
2. F2 ambiguous→verified path → fixed: semantic eligibility excludes
   `ambiguous`; validator caps upgrades; test pins both layers.
3. F3 eval-instruction echo → fixed: `EVAL_VACUITY_PHRASES` + validation.
4. F4 satisfied_verified without corroboration → fixed: strength gate
   (resolved git_commit/review/test_report ref required).
5. F5 claim-identity doc overclaim + stale-row risk → fixed: `source_digest`
   columns (045, additive, validated on simulated pre-existing v44),
   digest-keyed reuse, doc corrected (per-occurrence rows, per-identity compute).
6. F6 unsanitized requirement text in eval packets + absolute file refs
   persisted → fixed: packet sanitizer, basename normalization at persist,
   auto-link basenames; test asserts no `C:\` survives.
7. F7 finding collapse across distinct claims → fixed: fid includes claim id.
8. F8 staleness tracking absent → fixed: `source_digest` on both assessment
   tables (F5's columns do double duty).

## Self-check (implementer, not independent)

Completion strictness, missing-work rule, identity/dedupe, laundering
resistance, authority handling, vacuity/paraphrase gates, stale handling,
finding dedupe, budgets pre-call, privacy (no bodies; paths sanitized),
infra reuse — all covered by passing tests. Disagreements: none beyond the
review's list; all 8 adopted.

## Outstanding

Cross-family independent review (standing obligation, external commission
updated to include W4 surface). Awaited: separate-agent re-verification of
the 8 fixes (commissioned); full-suite rerun result.
