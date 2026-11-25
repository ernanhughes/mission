# W5A-FIRST-FINDINGS-REVIEW — The two highlighted episodes, investigated

## AI-CORE-05 (representative of the unsupported-claim family)

- Objective (inferred): "Achieve AI-CORE-05". No extracted requirements
  (semantic extraction abstained; deterministic extraction found no
  requirement-shaped statements beyond claims).
- Reported implementation: 11 unsupported merge/push/test claims
  ("merged into main and pushed…", "117/214/260/279 tests pass…").
  No associated commits (0 linked). No SHAs in the claim texts.
- Evidence: none linked (no execution records, no review rows, no resolvable SHAs).
- Why the gap: the claims assert specific outcomes (merges, pushes, test
  results) without the identifiers that would let anyone check them.
- Currency: the underlying work likely happened (repo history contains
  AI-CORE-08B merges), but *these claims* cannot be tied to it — the gap is
  real and remains open.
- Later activity: the ai repo's main branch contains related 08B merge
  commits, but without claimed SHAs no finding can be closed by them.
- Actionable: YES. Next: attach test execution records for the claimed runs
  and identify the actual merge SHAs; then re-evaluate (deterministic
  verification will confirm or refute automatically).
- Not a false alarm: the system does not claim the work didn't happen —
  it claims the completion *assertions* are unverified. That distinction
  held up under inspection.

## AI-CORE-08C (representative of the evidence-rich case)

- Objective: "Achieve AI-CORE-08C" (inferred). 19 linked commits
  (explicit, same-repo, verified present).
- Same claim family as 05 (merge/push/test assertions without SHAs or
  execution records) → same unsupported/verification-gap findings.
- Actionable: YES — and closer to closure than 05, since 19 commits are
  already linked: attaching the claimed test runs and identifying which
  claimed merge corresponds to which linked commit would resolve most of
  these findings mechanically.

## General conclusion (§9 + §6 answers)

The findings are genuine verification gaps, not noise and not false
missing-work alarms: every one cites the exact claim text, the missing
evidence class, and a concrete next action. The 278-finding volume reflects
repeated identical assertions across sessions (deduped per episode, not
across episodes — a W6 aggregation opportunity, explicitly not silent
exclusion). No finding warrants automatic corrective execution; all await
evidence or human judgement.
