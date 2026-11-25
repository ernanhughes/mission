# H2 First Vertical Slice Proposal

## Candidate slice

Create a reproducible execution baseline with explicit effective policy and trace identity. Select one bounded, non-effecting task family already supported by Worker. Preserve its existing request/result contract; record the exact task, engine, model route, policy/config digests, budget, and linked trace/evidence IDs. Compare the current direct and Pi/OpenCode paths only if they can run the same task and capability set under matched budgets.

## Acceptance evidence

- Independent replayable task manifest and frozen evaluator.
- Every run has a stable correlation identity spanning Mission and Worker records where both currently exist.
- Effective executor/model/policy/configuration are explicit, including error/unknown values; no silent fallback.
- Evidence distinguishes generated claims, declared checks, and independently verified outcome.
- Cost and budgets are reported with unknown values preserved.
- A negative or inconclusive result remains a valid outcome; no strategy is promoted.

## Scope boundaries

No new general harness framework, autonomous strategy mutation, Stephanie integration, memory migration, book implementation, or broad task suite. First verify whether existing Work Outcome WIP already supplies enough identity and evidence. Implementation is not authorized by this report.
