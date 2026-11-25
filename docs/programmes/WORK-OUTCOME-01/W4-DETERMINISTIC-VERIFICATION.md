# W4-DETERMINISTIC-VERIFICATION — Mechanical checks first, judgement never faked

Order of operations per episode: existence/reachability/linkage checks →
claim verification → requirement assessment (rules) → auto-link (mechanical
SHA/file matching) → semantic layer only for requirements with evidence →
rollups → findings. Every step short-circuits to an explicit unknown or
gap state rather than guessing.

Verified mechanics (all passing tests): commit existence via index,
mention-vs-execution (unresolvable SHA → reported, never verified),
abbreviated-prefix discipline inherited from W2, claim categories
(tests/review/integration/deploy/correction) defaulting to reported_only or
unverified without corroborating records, review-existence checks against
`git_reviews` rows, identity rules (statement/scope/revision), rollup
strictness (reported ≠ complete; absence ≠ failure).

What deterministic evaluation cannot do (explicitly out of scope):
correctness/quality judgements, integration usability, re-verification of
corrections, completion claims adjudication beyond existence checks. Those
are semantic or human tasks; the pipeline marks them insufficient/unknown
and records what evidence would close them.
