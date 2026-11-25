# H6 integration design

## Decision

Mission Control is the governance and operator surface; Worker remains the strategy runtime and owner of strategy decisions, invocation composition, runtime boundaries, and H3 execution evidence. H6 adds a thin Mission adapter and one Harness area to the existing app. It introduces no second execution ledger, task lifecycle, strategy engine, or migration.

## Flow

1. Mission lists Worker health, versioned strategies, configured model routes, and policies through read-only Worker HTTP contracts.
2. The operator selects an existing current Work Outcome episode/objective, a Worker strategy, a configured free/local-only route, and a compatible policy. The preview shows the actual objective resolved by Mission.
3. The operator supplies an actor and authorization note and confirms in the UI. Mission validates the episode/objective and optional exact project scope, records the existing Work Envelope, then sends a model-only `worker.work-request.v1` with bounded time/output, no workspace/tools, and the envelope ID as `operation_id`.
4. Worker executes and retains authoritative strategy evidence. Mission projects bounded H3 history, jobs, decisions, and request-scoped artifacts.
5. Mission marks Work Outcome correlation verified only when `operation_id` resolves to its envelope and Worker `episode_id` and `task_id` match the envelope episode and objective. Otherwise the execution remains unmatched; no Work Evaluation link is offered.

## Boundary

Inspect discovery is not an execution grant. H6 does not turn discovered capabilities into Worker tools. An Inspect capability would need a stable invocation contract, explicit permissions, a bounded Worker adapter, and an independent evaluator before a separately authorized integration. No Inspect mutation or execution surface was found necessary for H6.

## Retention and failure

Worker H3 summaries are authoritative but limited to the Worker ledger read window. Raw outputs are exposed only by request ID from the current Worker process's retained job result and may disappear after restart. A Worker timeout/transport/protocol failure after Work Envelope creation is outcome-unknown; the UI latches submission and tells the operator to inspect the Worker ledger. Duplicate submission envelopes do not dispatch twice.

No H6 database schema migration is required. `MISSION_CONTROL_WORKER_URL` is an optional loopback override; absent it, Mission retains its existing configured Worker URL resolution.
