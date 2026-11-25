# W2-AI-PROJECT-RECONSTRUCTION — Bounded run over 147 ai sessions

Scope `project_contains="Projects/ai"`, scratch PG `w2_pilot2` (ai git index:
75 commits copied as a factual snapshot from operational `mc`; operational
data untouched). Wall 17 s end-to-end (observe 6,390 msgs + reconstruct).

| Metric | Value |
| ------ | ----- |
| Sessions / messages / signals considered | 147 / 6,390 / 7,959 (6,660 new) |
| Candidate → established episodes | 30 (26 task, 2 chain, 1 cluster, 1 unresolved) |
| Single-session episodes | 24 (task singletons + cluster) |
| Multi-session episodes | 6 (incl. 15-member chain, 24-task mega-session) |
| Cross-repository episodes | 1+ (Stephanie SHA → cross-repo candidate, correctly not same-repo) |
| Associated commits | 73/75 indexed (explicit 148, candidate 127, derived 1) |
| Unassociated commits | 2 (no mentioning session; left, not forced) |
| Unresolved observations | 126 sessions in one bucket |
| Conflicting associations (commit → >1 episode) | 18 (recorded, not merged; W3+ adjudicates) |
| Rejected markers | 36 (artefacts, ambiguous prefixes, unresolvable SHAs) |
| Duplicate episodes prevented | replay adds 0; supersession path tested |
| Reconstruction duration | 2.9 s (observe 14 s) |
| Storage growth | ≈213 kB `wo_*` |
| Model calls / cost | 0 / $0 |

Target-table shape achieved: most work resolves to task episodes with
explicit links; research/probe traffic sits honestly in Unidentified
development activity. No ecosystem reconstruction, no quality/completion
judgements (W3/W4 own those).
