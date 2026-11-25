# H2 Current Contract Reconciliation

Inspection refreshed 2026-11-24 at baseline HEADs recorded below; Mission and Worker files listed as WIP are uncommitted and not release-qualified.

| Concern | Current contract/evidence | Finding |
|---|---|---|
| Mission episode | Uncommitted `backend/mission_control/work_observation/episodes.py`; `WoEpisode.id`, parent, type/status and `WoEpisodeAssociation` links | Durable Mission identity exists in WIP. Associations provide the right extension point; do not create a Worker episode. |
| Intent/outcome/evaluation | Uncommitted Mission `work_intent.py`, `work_observation.py`, `work_evaluation.py`, migrations 041–045 and tests | Objective/requirements/claims/evidence/verifications/outcome and independent assessment are modeled; changes remain under active development. |
| Mission observation | WIP `opencode_adapter.py`, `reconstruct.py`, `observations.py` etc. | Existing historical runtime observations can be linked; do not alter ingestion or infer an episode from timestamps. |
| Worker request | `worker.work-request.v1`, `src/schema/request.ts`; generated unique `wrq_…` request ID; `execution.backend/model/policy`; arbitrary `metadata`; objective, workspace, parameters, resources | Request ID is a per-attempt identity. There is no validated dedicated Mission episode field or task manifest. Metadata is already the route for operation/stage correlation. |
| Worker job/events | `src/core/worker.ts` `JobState`; request ID used as `job_id`; optional metadata `operation_id`; timestamps and executor observer events; `/v1/jobs` | Job/event view is process-local and bounded to 100 jobs. Not a durable execution record. |
| Worker result | `worker.work-result.v1`, `src/schema/result.ts`; optional `work_id`, `run_id`, acceptance ID, output, artifacts, backend/model, provenance | Actual OpenCode Work IDs are preserved; raw OpenCode result has session ID. Generic `execution_id`, effective policy/config digest, input/output digest, Mission episode link are absent. |
| Model runtime | `ModelExecutionResult` in `src/models/runtime/types.ts`; requested vs observed route/model/provider, attempts, fallback path, usage/cost, execution state | Good observed model evidence when the `model` executor is used. The `execution.policy` request can be explicit; default policy is configured and already documented. |
| Executor identity | `WorkExecutor` registry; executor IDs in result; health may include runtime version | Executor actual ID is checked against result. Engine version is generally unavailable or not retained in results. |
| Usage persistence | `UsageLedger` append-only `worker.usage-record.v1` | Durable after completion but intentionally excludes prompt/output and does not persist full request/result/events/config. It cannot alone reconstruct conditions. |
| Evidence/proof | Worker Evidence, Verify, Proof, VFS packages and OpenCode Work artifacts | Existing domains own evidence and causal provenance. Reuse references; Worker must not invent verification or acceptance. |
| Experiment/evaluation | Praxis effectiveness records/manifests; Mission outcome evaluation | Separate experiment/evaluation from execution. Praxis has no universal positive harness result; H05 false recovery is a guardrail. |

## Gate implication

The correlation baseline can reuse `request_id` as attempt/job identity and existing optional Mission `episode_id` as the cross-system relationship. It needs an additive, versioned execution summary that distinguishes requested, resolved, and observed values and persists redacted reconstruction metadata. It must refer to existing Worker result/evidence artifacts rather than copy domain records. Any Worker schema addition must remain backward compatible with v1 consumers; if compatibility cannot be demonstrated, use an adjacent versioned summary artifact and retain `worker.work-result.v1` unchanged.
