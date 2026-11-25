# W6B-AGGREGATION-REPORT — 293 findings → 24 groups, 0 hidden

Mechanism (`grouping.py`, pure + tested): key = (project, gap class,
subject digest of claim text / title-embedded first 80 chars).
Identical wording aggregates; distinct wordings stay distinct. Groups
are upserted with member links (idempotent); members never deleted;
closing a group requires per-member closure evidence (not implemented as
auto-close — by design).

## Result (operational, recorded passes)

24 groups over 288 open findings (5 resolved excluded, listed in
inventory). All severities now minor; group severity = max member.

| Gap class | Groups | Members |
| --------- | ------ | ------- |
| missing_test_evidence | 7 | 126 |
| missing_merge_provenance | 4 | 96 |
| missing_push_proof | 2 | 50 |
| verification_gap (new req. gaps) | 5 | 5 |
| merge_corroborated_push_unproven | 4 | 7 |
| unresolved_review | 1 | 1 |

Largest: 25 identical merge assertions (1 distinct title) across 25
episodes. Every group carries a human-readable sample title, affected
episode list, why-it-matters, and closure criteria (see Outstanding →
Groups in W6-USER-GUIDE). Drill-down lists member episodes; individual
findings view unchanged.

## Limits (explicit)

- Subject derives from titles (first 80 chars) because stored W4 rows
  carry no claim linkage. Two distinct suites sharing an 80-char prefix
  could co-group; spot-checks (largest group: 1 distinct title / 25
  members) show clean aggregation, and members stay individually
  inspectable, so the failure mode is visible, not silent.
- No arbitrary reduction target was set or chased; the count fell out of
  the data.
