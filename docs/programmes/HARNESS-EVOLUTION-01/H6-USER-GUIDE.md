# H6 user guide

## Navigation and prerequisites

Open Mission Control and choose **Harness** in the left navigation. The Harness requires the Mission backend, a loopback Worker with `/health`, `/v1/strategies`, `/v1/models/catalogue`, `/v1/work`, `/v1/executions`, and `/v1/jobs`, plus current Work Outcome episodes/objectives. Mission can use `MISSION_CONTROL_WORKER_URL` or its existing Worker Application configuration. Only configured free/local-only routes are offered. A green catalogue connection is not provider qualification.

## Tabs

- **Overview:** current Worker catalogue and H3 ledger window, active jobs, and known evidence limits.
- **Strategies:** Worker-authored behavior, invocation limits, validation/correction behavior, limitations, and digest.
- **Execute:** choose a current episode/objective, strategy, configured local-only route and compatible policy; set time/output bounds; enter actor and authorization note; inspect the preview; confirm the request. The Worker uses the objective text resolved by Mission. In a project Harness view, episodes are filtered by exact project key and the backend rejects out-of-scope launch attempts.
- **Executions:** read-only Worker H3 history. Select a request to inspect request identity, timeline, invocations, decisions, artifacts, independent Work Evaluation, and episode state. Mission links evaluation only after envelope correlation; Worker episode fields are explicitly marked caller supplied.
- **Decisions:** inspect Worker intervention decisions and observed states.
- **Experiments:** group only verified same-objective runs with matching recorded route, backend, policy, timeout, output cap, data policy, temperature, reasoning effort, and executor. Multiple distinct strategies are required to call the group a strategy comparison. No ranking or effectiveness claim is generated.

## Evaluation and acceptance

Execution completion is not correctness, independent evaluation, objective achievement, or formal acceptance. H6 reads an existing evaluation where present. Formal accept/reject must use the existing Work Outcome authority where that capability is available; this Harness does not add an acceptance button or endpoint and never auto-accepts.

## Connectivity and uncertain outcomes

If Worker is unavailable, confirm its loopback service and configured URL. If a request times out or returns a transport/protocol error after authorization, do not submit under a new ID. Refresh the Worker execution ledger and inspect the request; Worker may have accepted it. Raw artifacts can be unavailable after Worker restart, while H3 summaries remain in the ledger read window. Missing history is not zero activity.
