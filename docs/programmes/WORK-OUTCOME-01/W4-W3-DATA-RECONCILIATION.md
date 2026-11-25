# W4-W3-DATA-RECONCILIATION — Counting semantics + identity rules

## 1248 vs 1202 (resolved: overlapping categories, not an error)

W3-CLAIM-INVENTORY reported 1,202 claim rows but category counts summing to
1,248 (648 + 456 + 72 + 48 + 24). Recount on live data confirms the
mechanism: categories are **multi-label**, not a partition. A claim like
"merged to main, all tests passed" hits both `committed_pushed_merged` and
`tests_passed`. Recomputed on the W4 pilot store: 51 rows → 53 category
hits, with 13 multi-labeled rows (e.g. 8× {committed, tests_passed}, 2×
{committed, review, tests_passed}). Applied to W3: 1,248 hits − 1,202 rows
= **46 multi-label assignments**. Denominators: rows = 1,202; distinct
statements = 50; category hits = 1,248 (non-additive across categories).
No figures were silently adjusted; the W3 table now carries this note.

## Claim identity (implemented rule)

`claim_identity = sha1(normalized_text | scope | source_revision)`.
Identical wording across revisions/scopes/sessions yields **distinct**
identities; identical (text, scope, revision) yields one identity.
Consequences: the 1,152 duplicate rows collapse to 50 identities for
evaluation purposes, while all 1,202 occurrences keep provenance.
Verification is cached per identity: re-verifying "all tests passed" for
commit A never re-runs for its 47 repeats, but commit B gets its own
verification. Tested (`test_09`, `test_10`).

## Machine activity vs operational noise (taxonomy adopted)

- **Purposeful work** → Work Episodes (task/chain/cluster, corroborated).
- **Machine-generated evidence** → addressable by reference (scoring batches,
  verdict batches, extraction runs) but never auto-promoted to episodes or
  verified outcomes. Their verdicts (e.g. CONSISTENT/OVERGENERALIZED) are
  claims with claimant=machine-harness, verifiable like any other claim.
- **Operational noise** → probe pings and content-free interactions;
  retained as triaged, excluded from evaluation denominators only with an
  explicit, reported exclusion rule (none applied in W4 pilot).
