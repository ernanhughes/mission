# W5-W4-OBLIGATION-RECONCILIATION — Capability truth table for the UI

Verified against the W4 reports and implementation (not assumed):

| Capability | State | Evidence |
| ---------- | ----- | -------- |
| Observation (W1) | Operationally demonstrated | Live OpenCode reads, checkpoints, idempotent replay |
| Reconstruction (W2) | Operationally demonstrated | 30 episodes, 73/75 commits, fixtures 7/7 |
| Triage (W3) | Operationally demonstrated (deterministic) | 147 sessions classified; audit clean |
| Requirement extraction (W3) | Conditionally accepted | mistral-small validated; 0.5b quarantined; 19-call pilot |
| Claim inventory (W3) | Operationally demonstrated | 1,202 rows, 50 distinct, multi-label semantics fixed |
| Deterministic verification (W4) | Operationally demonstrated | 15-case calibration + service tests green |
| Semantic assessment (W4) | Conditionally accepted | mistral-small passes gate; 2/2 pilot evals abstained correctly; small sample |
| Verified-complete outcomes | Unavailable | No production `complete` observed; pilot honestly unknown/incomplete |
| Independent review | Pending | Separate-agent rounds done; cross-family outstanding |
| Migrations 041–045 | Operational at v44, 045 pending | Validated pattern; activation plan documents the sequence |

UI rule derived from this table: every verdict, badge and color in W5 maps
to one of these states, using the exact vocabulary of §12 (completed,
conditionally accepted, review pending, evidence unavailable, semantic
unavailable, verification pending, stale, source unavailable, blocked).
