# H2 Identity and Lifecycle Map

| Identity | Authority / current source | Scope and linkage |
|---|---|---|
| Programme | Mission programme record | Groups objectives/experiments; not an execution identifier. |
| Objective/task | Mission intent or frozen task manifest | Defines desired outcome and requirements. Use its stable ID/digest, not a display title. |
| Work episode | Mission `WoEpisode.id` (WIP) | Durable objective/outcome episode; association links artifacts, sessions, evaluations. Worker does not mint one. |
| Execution attempt | Worker `request_id` / `job_id` | Unique for each normalized request. Repeated POST creates a fresh attempt; retrieving an archived result preserves the original ID. |
| Engine session | Engine-native session ID, e.g. OpenCode provenance `session_id`, if exposed | Child identity; may be absent. Never use as Mission episode. |
| Model invocation | Runtime `execution_id` or receipt request/response IDs | Runtime-owned; one Worker attempt may include multiple model attempts/fallbacks. |
| Trace | Worker ordered observer/job events and runtime receipt | Diagnostic event set; ordering by recorded timestamps is not causal proof. |
| Evidence artifact | Worker/VFS/Proof artifact IDs and digests | Artifact owner remains Worker domain package; digest is integrity linkage, not truth. |
| Evaluation | Mission Work Evaluation run ID, Praxis effectiveness record ID, or domain evaluator ID | Evaluator owns semantics; reference it from episode/experiment, do not alias. |
| Experiment | Praxis experiment/manifest identity | Groups matched execution attempts and frozen evaluation; not an execution ID. |

## Relationship

`programme → objective/task → Mission episode → {execution attempt(s) → engine session/model invocation → trace/output/evidence} → outcome/evaluation → experience/improvement proposal`.

Existing IDs should be preserved. The Worker attempt ID is the canonical execution-attempt key. Mission `episode_id` is an optional foreign correlation supplied by the caller, and is unverified until resolved against Mission episode records. Worker `operation_id` remains a caller operation scope and must not be silently repurposed. Timestamps are descriptive only. A matching `request_id` and `episode_id` link is explicit; absent links remain unknown. Parent attempt linkage is recorded only when a real retry/continuation relation is supplied. The offline H3 demonstration creates no Mission association unless a temporary Mission database can be isolated; it never invents an episode ID.
