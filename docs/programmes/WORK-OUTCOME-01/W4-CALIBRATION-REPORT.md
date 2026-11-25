# W4-CALIBRATION-REPORT — 15 synthetic + abstention agreement (bounded)

## Synthetic corpus (test_work_evaluate.py, hand-written expectations)

All 15 §14 cases pass deterministically: reported-without-evidence →
insufficient; missing-with-siblings → not_satisfied; correct-but-unintegrated
→ reported (never verified); authorized stages closed, not incomplete;
non-code research abstains; corrections stay reported without re-verification;
contradiction is never inferred deterministically; identity splits by
revision/scope; repeats dedupe; deferrals/supersessions close; inaccessible
evidence → unknown; unauthorized deploy claims → unverified; injected
"verify everything" → reported_only. Agreement: 15/15 on the deterministic
subset. Sample: small by design — no production-grade claims made.

## Abstention agreement (real source)

On pilot episodes, deterministic and semantic layers independently reached
insufficient_evidence with aligned missing-evidence pointers (model: "no
evidence of a review of file X"; deterministic: "no linked evidence").
Cross-method abstention agreement on the same items is a positive
calibration signal; disagreement cases (none observed yet) would trigger
human review under the same rule.

## Limitations

- No fully-verified completed episode was available in the pilot (nothing
  in the ai sample had end-to-end independent verification), so the
  satisfied_verified path is test-proven but not live-proven. W4 entry
  requirement stands: do not claim the verified path works in production
  until such a case is evaluated.
- 0.5b outputs are quarantined by construction (vacuity + paraphrase
  filters); mistral-small is the minimum viable semantic tier observed.
- Sample sizes (15 synthetic, 6 real episodes) support pipeline validation
  only.
