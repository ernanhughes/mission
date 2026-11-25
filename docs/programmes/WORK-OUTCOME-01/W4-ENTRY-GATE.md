# W4-ENTRY-GATE — W3 closure, W4 authorization, initial state

## 1. W3 status at W4 entry

W3 CONDITIONAL ACCEPTANCE 2026-11-24. Reconciled: triage/extract/intent
modules, `api/work_intent.py`, migration 043 dual-file, 106 focused tests
green, deterministic full-scope pilot ($0), bounded semantic pilot (19/20
calls, $0; pipeline proven, 0.5b quality insufficient with vacuity filter
enforced). Operational DBs untouched.

## 2. W3 obligations and W4 entry requirements (from W3-FINAL-REPORT)

| # | Requirement | Disposition at W4 entry |
| - | ----------- | ----------------------- |
| 1 | Cross-family independent review | CARRIED → W4 §20. Separate-agent reviews closed W1/W2 findings; cross-family still open with commission. |
| 2 | Assert 041–043 on pre-existing PG at next authorized start | CARRIED → W4 §18. Simulated-pre-existing validation done for 041/042/043. Operational application awaits authorized start (not this commission). |
| 3 | Stronger model or human-supervised drafting | GATES W4 semantic work → W4 §2 capability benchmark now. |
| 4 | Qualifier detection for claims | W4 scope (§6/§7: qualified/conditional verdicts + claim qualification field use). |
| 5 | Full-backend regression before shared-path changes | RUNNING in background at W4 entry; reported in W4-TEST-EVIDENCE (bounded execution, explicit outcome). |
| 6 | Unresolved-bucket surfacing decision | W4 §17 read contract (not UI). |

## 3. Initial state (W4 start)

Branch `main`; W0–W3 files present (85 tracked/untracked items, only intended
W-files + pre-existing `publication/*` mods, unstaged). Migrations 041–043
dual-file present, version 43. Operational `mc` + OpenCode DB untouched.

## 4. W4 gates (from authorization)

Capability benchmark before authoritative judgements; 0.5b transport-only;
deterministic verification first; no W5 UI; no ecosystem evaluation;
≤30 semantic calls / $2; no operational writes without authorization; no
commits/pushes/deploys; stop at W4 gate.
