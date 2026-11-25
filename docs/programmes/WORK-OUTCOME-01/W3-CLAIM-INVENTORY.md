# W3-CLAIM-INVENTORY — 1,202 rows, 50 distinct statements (deterministic)

Source: `wo_claims` in scratch `w3_full` (deterministic extraction over 26
task episodes; no model calls). Multi-label regex categorization; duplicates
by exact-text digest.

| Category | Rows | Notes |
| -------- | ---- | ----- |
| Tests passed | 648 | Batch-repeated assertions; top digest ×48 |
| Committed/pushed/merged | 456 | Reconcilable against Git (W4, deterministic first) |
| Review performed | 72 | Independence NOT established by the claim |
| Integrated | 48 | Cross-system check required (Mission-UI failure class) |
| Defect corrected | 24 | Needs subsequent-verification check |
| Implementation complete | 0 as labeled* | "Complete" phrasing lives inside test/merge claims |
| Deployed | 0 | No deployment claims observed in pilot |
| Limitation/partial | 0 as labeled* | Hedging lives inside longer texts (see below) |
| Other | 338 | Mostly batch-verdict prose |

Key findings:

- **Deduplication first**: 1,202 rows → 50 distinct texts. Any W4 verification
  must dedupe before spending intelligence (24×–48× repeats of identical
  assertions from batch traffic).
- **Zero qualified, zero unsourced**: deterministic path preserves claimant +
  scope + signal ref on every row but does not yet detect qualifier language
  ("partially", "except", "pending") — recorded gap for the model half; W4
  must not treat unqualified-looking rows as unqualified claims.
- **24 claims carry SHAs** → directly bindable to `git_commit` evidence
  (done as candidates in W3 binding).
- **Mechanically verifiable first**: tests-passed (execution records),
  committed/merged (git log), integrated/deployed (interface/operations
  checks). Semantic evaluation reserved for correctness/quality judgements.
  This ordering is the W4 cost control the brief anticipates.
- No outcome judgements made; inventory and binding only.
