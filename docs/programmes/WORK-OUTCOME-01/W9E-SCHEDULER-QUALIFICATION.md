# W9E-SCHEDULER-QUALIFICATION — Qualified, still off

## Mechanism as implemented (W6, unchanged)

`run_pass` (continuous.py) is a bounded, single-flight, project-scoped
pass: observe → reconstruct → staleness → queue → evaluate → groups.
It is invoked manually (Controls) or by a script; **no timer exists
in code**, so nothing can enable itself. `wo_auto_enabled` (settings)
is the semantic-evaluation flag and defaults off; paid budget is $0
and has no setter.

## Gate results (each verified or tested)

| Gate | Result |
| ---- | ------ |
| Source DB safety | read-only adapter, WAL-consistent, connection refused cleanly when absent |
| Explicit project scope | `project_contains` required for gated behaviour; policies fail closed without it |
| Correct checkpoints | W1 tuple cursors + 5-min overlap; advance only on completed runs (tested) |
| Overlapping-run prevention | single pass per invocation; run rows carry running→failed on exception; no timer to race |
| Bounded execution | sessions/messages/eval caps (500 / defaults / 10 per pass) |
| Error recovery | source/model outages recorded as `blocked`; the pass never raises (tested) |
| Service restart | checkpoints persist; replay is idempotent (pass1/pass2 identical effect, scratch) |
| Idempotence | envelope/proposal/finding digests dedupe; group upserts no-op on replay (tested) |
| Accurate status | `wo_observation_runs` / `wo_eval_runs` / receipt envelope show blocked vs completed |
| No unexpected model calls | deterministic path makes zero calls; semantic gated by flag + policy + budget |
| No automatic corrective execution | no executor exists on any path (structural) |
| Policy gating | observe/reconstruct/evaluate gates enforced (new tests) |

## Status: NOT activated

All gates pass, so the mechanism is qualified for a bounded
operator-controlled activation. It remains disabled because (a) the
commission says do not silently enable it, and (b) the honest load
figures for a 15-minute cadence across two projects do not exist yet
— that measurement is the first thing the operator's activation
produces.

## Activation procedure (when authorized)

1. Choose scope: `ai` only, or `ai` + Wave 1 with policies set.
2. Schedule `run_pass(project_contains=…)` every 15 min using the
   existing maintenance-loop pattern (`pipeline_auto_enabled`
   convention) — no new scheduler.
3. Watch: pass receipt `duration_ms`, `blocked` entries, run rows.
4. Pause = disable the schedule; no state is lost.
5. Semantic evaluation remains off regardless (separate flag,
   separate authorization, budget still $0).
