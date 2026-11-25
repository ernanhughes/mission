# W3-CLAIM-AND-EVIDENCE-BINDING — Candidates only

- Claims come only from CLAIMED signals (`test_claim`, `completion_claim`)
  with claimant defaulting to `assistant` (the observed author role) and
  `qualified` set when the source text contains qualifiers (partial/pending/
  try/should). No claim row asserts its own truth; `evidence_available`
  flips only when a W2 link or artifact row references the same source digest.
- Evidence candidates come from W2 associations (`git_commit` links carry
  the association confidence) plus requirement-scoped signal excerpts
  (redacted, ≤800 chars). Links are `method=candidate` until W4 judges them.
- Stale-revision rule: an evidence ref pins its revision (`repo:sha`);
  a newer source state never silently re-points an old link — re-observation
  creates a new link and marks the old one for W4 review.
- Pilot yield (deterministic, w3_full): 26 inferred objectives (task episodes
  only — chains/clusters abstained, no invented intent), 1,202 claims
  (test/completion assertions with session locators), 0 requirements
  (deliberate abstention: requirement drafting needs judgement), evidence
  candidates = all 73 linked commits carried forward from W2 rows.
