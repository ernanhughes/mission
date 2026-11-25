# H6 ownership and contracts

| Concern | Owner / contract | H6 use |
|---|---|---|
| Objectives and episodes | Mission Work Outcome (`/api/work-episodes`, `/api/work-intent/objectives`) | Existing current objective text is resolved server-side; caller text is never accepted. |
| Authorization | Mission Work Envelope (`register_envelope`) | Human actor/note, objective, episode, acceptance policy, and operation ID are recorded before dispatch. |
| Strategy and route catalogue | Worker `/v1/strategies`, `/v1/models/catalogue`, `/health` | Mission exposes Worker metadata; `approved` is interpreted as configured route list, not effectiveness or provider qualification. |
| Runtime and decisions | Worker `worker.work-request.v1`, H3 execution summary, `/v1/jobs` | Worker selects and executes strategy and records invocations/interventions. Mission does not reimplement it. |
| Execution identity | Worker request ID plus `operation_id` | Mission Work Envelope is the correlation authority. Worker `episode_link=caller_supplied_unverified` remains visible; Mission correlation is a separate field and requires exact envelope/episode/objective match. |
| Evaluation and acceptance | Existing Work Evaluation and acceptance surfaces | Evaluation is read-only and separate. H6 has no accept/reject mutation endpoint and never auto-accepts or promotes. |
| Artifacts | Worker retained job result, scoped by Worker request ID | Mission strips unrelated job fields and labels process-memory retention. H3 summary remains available when raw result does not. |
| Project view | Mission `project_key` and verified envelope correlation | Exact project key only; scoped selector is filtered and launcher rechecks scope. No project-name inference. |
| Inspect | Inspect inventory and contract, when established | H6 documents the boundary; discovery alone never authorizes execution. |
| Effectiveness | Praxis / independent evaluator | No effectiveness score or strategy ranking is calculated by H6. |

All Worker URLs used by Harness must be loopback. Requests use `trust_env=False`; external, credential-bearing, and non-HTTP(S) Worker URLs fail closed.
