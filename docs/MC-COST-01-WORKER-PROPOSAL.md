# MC-COST-01 — Future Worker / ECK cost budgeting (proposal only)

No control loop is implemented in this release. The Cost dashboard stays
observational. When budgeting is wanted, feed measured cost/allowance back
into Worker so it chooses the cheapest **effective execution strategy**
(context size, cache reuse, concurrency, expected calls) — not just the
cheapest model.

## Proposed signals (all already measurable locally)

- Per-project/session `requests`, `input/output/reasoning/cache_read/write`,
  `recorded_cost` from `GET /api/cost/*`.
- Deterministic spike findings: `high-call-rate`, `go-limit`, `zero-cost-volume`,
  `low-cache-reuse`, `parallel-agents`.
- Optional provider meter (`GET /inference/go/v1/usage`: rolling/weekly/monthly
  `percent`, `resetsAt`) — separate source, explicit staleness, never mixed
  into local dollar totals.

## Proposed policy (separate milestone, owner approval required)

1. **Budgets as data, not enforcement:** per-project soft limits
   (requests/day, input/day, recorded_cost/day) stored in Mission Control;
   breach = Inbox item + evidence link, never an automatic kill.
2. **Pre-flight estimate:** before a Worker run, estimate calls × median input
   for the chosen template/model from Cost history; refuse only on explicit
   user confirmation when estimate > budget.
3. **Client hygiene first:** prefer stable `x-opencode-session`/Pi sessions,
   smaller serialized contexts, bounded parallelism; measure cache_read ratio
   before/after.
4. **No automatic model switching, no provider credential exposure, no silent
   Extra Usage toggles.** Any spend-affecting change requires the same
   approval-hash discipline as MC10/MC11 workflows.
5. **Audit:** every budget decision links to Cost session IDs, minutes and
   provider meter snapshots; unknowns stay `Unknown / unattributed`.

## Instrumentation needed before enforcement

- Persist per-call `opencode.allowance`, `opencode.list_cost`,
  `opencode.billing_source` (response `usage.opencode`) for Worker/Pi routes;
- record sent session identifiers and `--no-session` usage;
- reconcile local rows against provider CSV/meter for unattributed calls.

Until then: observe, batch, cache, bound concurrency — do not auto-throttle.
