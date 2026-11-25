# W6B-SEVERITY-POLICY — w6b-v1: consequence, not absence

## Problem (§2, §10)

W5A labelled all 217 uncorroborated historical assertions major. A
missing SHA in a years-old conversation is an evidence limitation, not
an engineering emergency. Severity must reflect the consequence of the
underlying issue; confidence and completeness are separate dimensions.

## Policy w6b-v1 (implemented in `_synthesize_findings` + one recorded pass)

| Situation | Kind | Severity |
| --------- | ---- | -------- |
| Contradicted material claim with counter-evidence | defect | major |
| Missing mandatory requirement (no evidence, sibling has) | missing_requirement | major |
| Unsupported completion claim, no counter-evidence, historical only | unsupported_claim (preserved, retitled "Unverified…") | minor |
| Merge corroborated (`merge-base --is-ancestor`), push unproven | verification_gap | minor |
| Test report without execution record | verification_gap | minor |

Epistemic status stays `suspected` (nothing auto-confirmed); consequence
sets severity. Downgrade applied to stored rows only where rationale
carries no contradiction language (217/217 qualified; 0 contradicted
claims exist in the corpus). Kinds and titles of stored rows kept stable
(history); new evaluations use the "Unverified completion claim" title.

## What was NOT done

No suppression: 278 rows → 288 open + 5 resolved-with-evidence.
Significant claims keep their next actions (supply SHA / push record /
execution record). A future contradicted claim still lands major.
