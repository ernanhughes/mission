# W2-SEVEN-CASE-PILOT — Frozen fixtures vs reconstruction (scratch `w2_pilot2`)

Expected boundaries were written from W1 census + git evidence before running
the engine; the engine never served as its own ground truth.

| # | Fixture | Expected | Actual | Verdict |
| - | ------- | -------- | ------ | ------- |
| 1 | `ses_e4a7…` evidence-rich | task episodes incl. AI-CORE-08C; 6 verified SHAs link; no forced merge across 24 mentioned tasks | 24 task episodes + 2-session chain; AI-CORE-08C holds verified SHAs; 87 commit links across its episodes; 1 sha rejected (`49d89821`-class) | PASS (multi-objective session correctly spans episodes) |
| 2 | `ses_e47df…` incomplete probe | no task episode; unresolved | unresolved only | PASS (request without execution is not work) |
| 3 | `ses_e01c…` multi-commit | AI-CORE-WEB-01/B episodes; verified SHAs link; embedding hash abstained | task episodes found; 1 sha rejected (invalid reference) | PASS |
| 4 | `ses_e48a…` + 14 children | one chain episode, 15/15 members; task co-links allowed | `ep:chain:ses_e48a…` holds exactly 15/15 (recall 1.0); parent also task-linked | PASS, no incorrect splits |
| 5 | `ses_e342…` claim, 0 SHAs | NOT in any task episode; unresolved (claim alone seeds nothing) | unresolved only | PASS |
| 6 | `ses_e33d…` non-code | representable without commits; unresolved-or-cluster, never a false commit link | unresolved; zero commit links | PASS |
| 7 | `ses_e47f…` ambiguous | abstain; unresolved | unresolved only | PASS |

Exclusions verified: cases 2/5/6/7 have **zero** task-episode memberships
(no false positives). Incorrect associations: none found on fixtures.
Missing: 2/75 commits unassociated (no mentioning session — correctly left,
not forced). Unresolved: 126 sessions, dominated by 2–6-message probe/READY
sessions with no corroboration — abstention, not failure. Explanation quality:
every link carries method/confidence/reason + signal values (spot-checked).
