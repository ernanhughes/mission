# W6B-FINDING-INVENTORY — Full census before/after aggregation

Source: live operational DB, schema v47 (read-only queries + recorded
passes only). No finding deleted; 5 status-changed to resolved with cited
closure evidence (§21); all rows preserved.

## Before (W5A baseline, verified)

278 findings, all open/suspected: 217 `unsupported_claim`/major (78.1%)
+ 61 `verification_gap`/minor (21.9%). Zero resolved, zero confirmed.
Volume driver: identical assertions repeated across sessions/episodes
(e.g. one merge/push line in 25 episodes).

## After W6A recovery + W6B passes (2026-11-24)

293 finding rows: 217 `unsupported_claim`/minor (w6b-v1 downgrade, same
rows, severity+rationale updated, titles kept), 71
`verification_gap`/minor (+10 from newly recovered requirements lacking
links, then linked), 5 `missing_requirement`/major → **resolved**
(requirements now satisfied; closure cites assessment ids).

- Original: 278. Active (open/suspected): 288. Resolved: 5.
- Unresolved ambiguity: none hidden — 8 findings added by W6A
  re-evaluations are ordinary verification gaps on the new requirements,
  listed in the aggregation report.
- Unsupported severities: every remaining major was checked for
  counter-evidence language; the only `defect`-class rows are none —
  there are still zero contradicted claims in the corpus, so no confirmed
  defect exists to prioritize above gaps. The policy keeps `major` for
  contradicted/missing-mandatory, of which the live set now holds only
  resolved history.

## Repeats and shared gaps

- Largest group: 25 identical "merge to main and push" assertions across
  25 episodes (1 distinct title). Cross-episode repetition is a
  presentation fact, not a merge of episodes: members keep episode ids.
- 4-member merge-corroborated group spans ep:chain + 3 task episodes —
  same wording, distinct episodes, correctly one group.
- No finding was suppressed, edited for convenience, or closed without
  per-row closure evidence.
