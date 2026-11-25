# W9E-PROJECT-POLICIES — Six levels, existing storage, enforced

## Implementation

`work_observation/policies.py` + `/api/work-evaluation/policies`.
Stored in the existing `settings` key/value store under
`wo_policy:<project_key>` — no new table, no migration, no duplicate
policy infrastructure.

Levels (ladder; each permits everything below it):

| Level | Permits |
| ----- | ------- |
| disabled | nothing |
| observe | deterministic observation |
| reconstruct | + episode reconstruction/association + triage/extraction |
| manual_evaluation | + on-demand evaluation (mechanical; semantic-on-demand too, since W9 review F11) |
| continuous_mechanical | + scheduled deterministic evaluation |
| continuous_semantic | + scheduled semantic evaluation (still gated by global auto flag, capability, budget) |

Separate switches preserved (§18): historical backfill, incremental
observation, reconstruction, mechanical evaluation, semantic
evaluation, corrective execution. **A policy level never authorizes
corrective execution** — that remains an explicit human approval per
proposal (W7).

## Enforcement points (all tested)

| Path | Gate | Behaviour when denied |
| ---- | ---- | --------------------- |
| `run_pass` observation | `observe` | skipped + `observation:policy_disallows` |
| `run_pass` reconstruction | `reconstruct` | skipped + `reconstruct:policy_disallows` |
| `run_pass` queue evaluation | `evaluate_mechanical` | skipped + `evaluate_mechanical:policy_disallows` |
| `run_pass` semantic | `evaluate_semantic_scheduled` | flag forced false + `semantic:policy_disallows` |
| `POST /api/work-observation/runs` | `observe` | 403 naming capability |
| `POST /api/work-episodes/runs` | `reconstruct` | 403 |
| `POST /api/work-intent/triage/runs` | `reconstruct` | 403 |
| `POST /api/work-evaluation/runs` | `evaluate_manual` (+ `evaluate_semantic_manual` if semantic) | 403 |

Unscoped manual actions (no `project_contains`) stay allowed — that is
the operator explicitly asking for the whole store, and no single
project policy can speak for it. Documented rather than implied.

## Safety properties (tested)

- Unknown project → `disabled` (the other 79 registered projects are
  not silently in scope).
- Unknown level or capability → refused (fail closed).
- **Semantic is never granted without both a policy service and a
  project scope** (W9 review F1).
- Policy change requires a human actor; `system`/`model` rejected.
- Optional operator allowlist via `MC_WORK_EVAL_PROJECTS`.
- Scope canonicalization: `ai`, `Projects/ai`, `work/ai` all resolve to
  the `ai` policy (W9 review F10); verified live.

## Defaults shipped

`ai` → `manual_evaluation` — the pilot keeps exactly the capability it
has today. Wave 1 (`mission`, `worker`, `workbench`) deliberately NOT
enabled; enabling is a one-line human action.

## Test evidence

`test_work_policies.py` (10 tests) includes the reviewer-requested
proof that an **explicit** policy changes the outcome: downgrading
`ai` to `disabled` blocks observation; upgrading an unknown project to
`observe` allows it; deleting the policy service does not grant
semantic; a disabled project is refused at the HTTP endpoint.
