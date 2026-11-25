# W9D-CALIBRATION-REPORT — 17-case corpus, both directions

`backend/tests/test_work_calibration.py`: hand-annotated fixtures
with independently set expected verdicts (never model-generated),
plus a size pin so silent case deletion fails loudly.

## What it measures (selected)

- Requirement assessment: missing-evidence→insufficient (not
  failure); sibling-evidence→not_satisfied; existence+resolved→
  verified; functional+resolved→reported (never verified);
  ambiguous→abstain despite evidence; deferred/superseded/excluded
  terminal; non-code without commits→insufficient.
- Claim verification: unresolvable SHA→reported_only (not failed);
  resolvable SHA (bare form, as the engine passes it)→
  verified_commit_exists; test report without record→reported_only.
- Completion: complete requires ALL mandatory verified; any
  reported→at most partial; contradicted/missing→incomplete;
  unevaluated→unknown (never complete by default).
- Findings: uncorroborated completion→minor unsupported_claim (never
  major without counter-evidence); contradicted requirement→major
  defect; identical wording dedupes; distinct splits.

## Results

17/17 pass. Known limits: corpus is unit-level (pure functions +
  in-memory synthesis); no live-DB calibration run (would need
  ground-truth labels for 26+ episodes — recorded as the W9 follow-up
  sampling frame, not executed here); semantic extraction quality is
  NOT covered (model capability below); no production accuracy
  claims are made — the corpus pins the contract, not the world.
