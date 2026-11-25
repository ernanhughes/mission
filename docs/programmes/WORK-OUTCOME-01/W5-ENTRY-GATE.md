# W5-ENTRY-GATE — W4 closure, W5 authorization, initial state

## 1. W4 status at W5 entry

W4 CONDITIONAL ACCEPTANCE. Reconciled: deterministic verifier +
assessment service + `api/work_evaluation.py` + migrations 044/045 +
32 focused tests green; bounded pilot (6 episodes, 1 complete packet,
no false completions, 24/30 calls at $0). Operational DBs untouched by
W4 (backend startup advanced operational `mc` to v44 independently;
045 applies on next authorized start).

## 2. W4 obligations: disposition for W5

| Obligation | Evidence status | W5 handling |
| ---------- | --------------- | ----------- |
| Cross-family independent review | Outstanding | Represented in UI as "Independent review pending" wherever a verified-complete label would otherwise appear; never show unqualified verified-complete. |
| Re-verification of 8 fixes | Running (separate agent) | No UI dependency; record outcome on return. |
| Operational migrations 041–045 | Operational at v44 with 20 wo_* tables, 0 rows; 045 pending | W5 builds + tests against contracts; activation plan documents the exact sequence. No operational writes. |
| Full backend regression | 999 passed / 1 environmental (live `gh`) / 17 skipped | Preserved; no test weakened for green. |
| Semantic evaluation reliability | mistral-small passes capability gate; 0.5b quarantined; pilot mostly unknown/incomplete | UI distinguishes demonstrated (deterministic), conditional (semantic pilot, small sample), unavailable (verified-complete exemplar). |
| W5 read contract | Delivered | Only contract-conformant reads; gaps handled per §13. |

The brief's §2 warning stands: W5 must inspect the actual capability and
pilot reports, not assume semantic reliability. Deterministic outputs are
operationally demonstrated; semantic outputs are conditionally accepted;
verified-complete at scale is unavailable.

## 3. Initial state (W5 start)

Branch `main`; W0–W4 files present; pre-existing `publication/*`
modifications preserved, unstaged. No operational writes performed by W4 or
carried out here without authorization.
