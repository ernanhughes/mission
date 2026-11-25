# W4-OUTCOME-EVALUATION-ARCHITECTURE — Three perspectives, no composite

```
W3 intent (objectives/requirements/claims, authorities)
W2 associations (sessions/commits, methods, confidence)
W1 signals + git index + reviews
        │ deterministic verify.py
        ▼
requirement verdicts (10 states) + claim verifications (5 states)
        │ gated semantic assessor (evidence-bound, validated, budgeted)
        ▼
rollup_completion (mandatory-gated) + execution/outcome views (rule-based)
        ▼
findings (missing/defect/verification-gap/unsupported-claim) deduplicated
by (episode, requirement, kind)
```

Perspectives stay independent: execution (restriction compliance, evidence
honesty, review handling), outcome (correctness signals from reviews/tests,
maintainability unknown unless evidenced), completion (mandatory-gated
rollup). No arithmetic across perspectives; the compact episode packet
presents all three side-by-side with limitations. History is append-only
(new assessment rows; supersession via validity, never rewrites).
