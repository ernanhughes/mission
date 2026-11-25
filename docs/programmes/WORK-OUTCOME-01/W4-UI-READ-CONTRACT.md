# W4-UI-READ-CONTRACT — What W5 will consume (no UI built in W4)

W5 reads only; nothing here triggers inference. All endpoints paginated and
bounded (`limit`/`offset`, validation, 404/422 semantics):

- `GET /api/work-evaluation/episodes/{id}` → `{assessment: {execution,
  outcome, completion (+rationales)}, requirements[], claims[],
  findings[]}` — the compact episode packet from the brief's illustration
  (verdict + counts + next actions, drill-down on demand).
- `GET /api/work-evaluation/findings?episode_id&status&limit` → actionable
  list (kind, severity, status, title, next_action, closure criteria).
- `GET /api/work-evaluation/coverage?project_key` → completion mix,
  counts, project scope.
- `GET /api/work-evaluation/cost` → calls, spend, caps, model identity.

Display rules for W5: `unknown` renders as Unverified (never as failure or
success); `reported_only` renders distinctly from `verified_*`;
`suspected` findings render as suspected; mandatory-vs-optional and
stage/episode/programme completion levels stay visually distinct; stale
evaluations carry their observation timestamps. No composite scores —
the contract forbids them and no endpoint serves one.
