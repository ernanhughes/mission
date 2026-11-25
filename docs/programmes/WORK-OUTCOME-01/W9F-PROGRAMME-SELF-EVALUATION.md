# W9F-PROGRAMME-SELF-EVALUATION — The product graded its own programme

## Method (genuine, not a demo script)

Created `ep:task:WORK-OUTCOME-01` (kind `programme`) in an isolated
copy of the operational database. Recovered its requirements from the
programme's own §31 acceptance criteria + stage table — 15 criteria,
authority `explicit_user` (the owner authored them), provenance =
the ledger file with a sha256 digest, reviewer `w9-self-eval`. Then
linked 19 real artifacts that exist in the tree (service.py,
verify.py, proposals.py, the W6–W9 evidence docs, the calibration
test) as `file` evidence with method `human-reviewed`, confidence
`weak`. Then ran the ordinary deterministic evaluation. No special
path, no hand-written verdict.

## Result: **incomplete** (not complete, not unknown)

| Verdict | Count | Meaning |
| ------- | ----- | ------- |
| satisfied_reported | 11 | evidence exists; correctness not independently judged |
| not_satisfied | 3 | mandatory criterion with no evidence while siblings have it |
| insufficient_evidence | 1 | judgment-shaped criterion with no evidence class |

The three `not_satisfied` are, verbatim from the run:

1. **Cross-family assurance is complete.**
2. **At least one complete Work Episode has been independently verified.**
3. **Controlled multi-project operation has been demonstrated.**

Those are *exactly* the three gaps the human reviewer named in the W8
review, derived independently by the system from its own records. The
`insufficient_evidence` one is "The live product is genuinely useful"
— correctly abstained: usefulness is a judgment, and no evidence
class in the rubric can settle it.

## Why this matters

This is the acceptance test the commission asked for: can the product
tell you **what we intended, what we actually achieved, how good the
result was, and what remains to be done** — about itself?

Yes, and it does not flatter itself. It reports 11 criteria as
*reported only* (never verified), and refuses to close the three
genuine gaps. A system that graded its own programme "complete" here
would be worthless; this one produced the same verdict as its
external reviewer.

## Limitations of this self-evaluation

- Same system assessing its own artifacts: circular for *correctness*,
  valid for *coverage and honesty* (it did not over-claim).
- `not_satisfied` here means "mandatory, no linked evidence, siblings
  have some" — a real gap, not proof of wrongdoing.
- The requirements were authored from the programme's own closure
  gate, so the test is fair rather than adversarial.
