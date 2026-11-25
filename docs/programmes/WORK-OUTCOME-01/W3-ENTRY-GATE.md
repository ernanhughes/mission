# W3-ENTRY-GATE — W2 closure, W3 authorization, initial state

## 1. W2 status at W3 entry

W2 CONDITIONALLY ACCEPTED 2026-11-24. Reconciled: engine (`reconstruct.py`),
service (`episodes.py`), API (`api/work_episodes.py`), migration 042 dual-file,
31 focused tests green, service wired in `main.py`, checkpoints/signals/
episodes as reported. Bounded ai reconstruction reproduced live (30 episodes,
280 links, 73/75 commits) on scratch PG; operational DBs untouched.

## 2. W2 obligations: status at W3 entry

| Obligation | Outcome |
| ---------- | ------- |
| Independent W1/W2 review | CARRIED → W3 §2. Separate-agent review commissioned in parallel with this build; external model commission retained. Implementer self-checks are not presented as independent. |
| Worker unavailable | CARRIED → W3 §3. Dedicated investigation running; no new provider client will be built. |
| Migration 041/042 on operational PG | CARRIED → W3 §4. Simulated-pre-existing validation done (041); 042 same shape. Operational application awaits authorized backend start; asserted at W3 entry. |
| Full backend regression | CARRIED → W3 §4. Focused + neighbour suites green (113 tests W2); full suite deferred per policy until shared paths change. |
| Unmatched SHAs | CLOSED (W2): cross-repo reference + invalid embedding hash, both classified. |
| Historical coverage | CLOSED (W3-UNRESOLVED-COVERAGE-BASELINE): 147 sessions reconciled — 30 signal-bearing/chained (94.6% of messages), 117 exclusively unresolved (5.4% of messages, mostly 3–6-message probes). |

## 3. Initial state (W3 start)

Branch `main`; W1/W2 files present; pre-existing `publication/*` modifications
preserved, unstaged. Operational `mc` + OpenCode DB untouched. 043 migration
drafted (intent domain, additive). Subagents running: independent review,
governed-route investigation.

## 4. W3 gates (from authorization)

Deterministic triage + intent domain + extraction architecture proceed now.
Live semantic (model) extraction is GATED on: (a) governed route demonstrated
with a synthetic probe, (b) ≤20 invocations / $1 ceiling, (c) independent
review findings addressed or explicitly carried. No W4 judgements, no W5 UI,
no ecosystem analysis, no budget breach, no operational writes without
authorization, no commits/pushes/deploys.
