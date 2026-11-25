# H6 implementation report

## Delivered

- Backend adapter: `backend/mission_control/api/harness.py`, registered in `main.py`.
- Optional loopback Worker URL setting: `MISSION_CONTROL_WORKER_URL`; default behavior remains the existing Worker Application configuration.
- Frontend Harness route/sidebar, six tabs (Overview, Strategies, Execute, Executions, Decisions, Experiments), and project-level Harness tab.
- Work Envelope pre-authorization, bounded model-only request, duplicate protection, uncertain-outcome latch, H3 ledger/job projection, request-scoped artifact access, and verified Work Outcome correlation.
- Synthetic Worker and Mission fixtures under `h6-fixtures/`; no H6 schema migration.

## Controls

The adapter permits only configured free/local-only routes with a compatible local-only policy and at most two attempts per route. Request ceiling is 60 seconds and 2,048 requested output tokens per invocation. The UI submits no workspace, filesystem, network, or external tools. Route catalogue availability is not qualification. Worker-reported token enforcement, billing, provider inference, and remote termination remain unknown unless directly evidenced.

## Qualification boundary

One isolated UI launch exercised the full Mission-to-Worker route using an injected scripted provider with **zero actual inference**. The result demonstrates the integration and deterministic normalization surface only. It does not qualify a production provider, model answer, general effectiveness, operational activation, or the historical H4 comparison bundles.
