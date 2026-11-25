# W9E-ROLLOUT-REPORT — Pilot enabled, Wave 1 prepared, nothing auto-expanded

## Inventory (actual, from the operational registry)

81 projects registered, 0 archived, all `active`: 41 book, 24
application, 9 research, 7 supporting. Seven show activity in the
last 30 days; the rest are dormant or maintenance-only. No project
records were created, renamed or duplicated in this stage.

Classification used for rollout:

| Class | Examples | Treatment |
| ----- | -------- | --------- |
| Pilot | ai | `manual_evaluation` (unchanged capability) |
| Wave 1 (prepared, NOT enabled) | mission, worker, workbench | enable on approval; `manual_evaluation` recommended first |
| Wave 2 (prepared) | writer, aitest, praxis | after Wave 1 review |
| Wave 3 (prepared) | cocoder, next, work, improve | after Wave 2 review |
| Books / publication | 41 book projects | out of scope until a policy is set (default `disabled`) |
| Dormant | remaining applications/research | `disabled` until activity or an explicit decision |

## What was actually enabled

Only the pre-existing pilot: `ai` → `manual_evaluation`. No Wave 1
project was switched on. No historical backfill was run. No
ecosystem-wide observation occurred. The 30-day lookback default is
recorded per policy and is not yet exercised by a schedule.

## Deliberately not done (and why)

- Wave 1 activation: §20 says prepare, review Wave 1 results, then
  expand — and Wave 1 has *no* results yet because it was never on.
  Enabling it silently would repeat the migration-governance mistake
  in a different domain.
- Books: 41 projects with publication semantics (different evidence
  class) — a book policy needs its own acceptance criteria, which is
  Wave 2+ work and outside the programme's pilot scope.

## How an operator expands a wave

```
POST /api/work-evaluation/policies
{"project_key": "mission", "level": "manual_evaluation",
 "actor": "<your name>", "lookback_days": 30}
```

Then run a bounded pass:
`POST /api/work-observation/runs {"project_contains": "mission"}`.
Review the findings and coverage before enabling the next project.
