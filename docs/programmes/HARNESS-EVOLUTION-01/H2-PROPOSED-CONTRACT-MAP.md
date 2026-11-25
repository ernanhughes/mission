# H2 Proposed Contract Map

This is a mapping proposal, not a new schema specification. Reuse current contracts where they fit; investigate gaps before adding DTOs.

| Concern | Existing owner / candidate source | Boundary to settle in H2 |
|---|---|---|
| Goal and requirements | Mission intent / Work Outcome; Worker Work request | One stable task/episode/programme identity linked across records. |
| Execution request | Worker `worker.work-request.v1` | Versioning, idempotency, policy/config digests, caller authority. |
| Execution state | Worker job/result; Mission episode (WIP); Praxis `HarnessState` | Lifecycle mapping and durable source of truth. |
| Policy | Worker model/runtime policy; Praxis `HarnessPolicy`; Mission approvals | Separate selection advice from enforced authority and explicit approval. |
| Engine | Worker executor and Pi/OpenCode runtime composition | Engine/version/config digest and no silent fallback. |
| Context | Writer, Workbench and optional retrieval providers | Provenance, token/size accounting, access boundary. |
| Memory | Worker Remembering/Relate and shared `ai.*`; Writer ECK context | Domain-specific interfaces; no duplicate global memory contract without evidence. |
| Actions/effects | Mission ActionSpec/confirmation; Praxis action executor | Capability vs authority, approval scope, idempotency and reconciliation. |
| Trace | Worker Work/VFS/observability; Mission observations | Correlation identity, event ordering, redaction and retention. |
| Evidence | Worker Evidence/Proof; Mission verification/outcome | Provenance and immutable references; separate evidence from generated narrative. |
| Evaluation | Praxis effectiveness; Mission outcome evaluation; Worker acceptance | Domain correctness, execution acceptance, and comparative effectiveness remain distinct. |
| Failure attribution | Worker errors; Praxis H05 taxonomy | Process/content/environment/evaluator categories and abstention. |
| Candidate | Praxis/ECK experiment records; possible Stephanie proposer | Immutable candidate bundle and predicted outcome; proposer has no promotion authority. |
| Acceptance/promotion | Mission governance; Worker declared acceptance; Praxis recommendation | Explicitly separate task acceptance from strategy promotion. |

H2 should define a minimal correlation envelope and compatibility tests only after verifying current concrete schemas and data stores across dirty worktrees.
