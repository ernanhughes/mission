# MC-INSPECT-04 Report — Capability Activation (Worker + Praxis)

## Objective

Turn Inspect's discovered capabilities into actionable, governed workflows in Mission Control, without building a parallel execution system.

Working repos: `mission`, `worker`, `praxis`, `inspect`.
INSPECT-03D: 3 official + 6 source-inspected drafts (Worker, Next, Work, AI, Praxis, Steward). Official Pi enrichment blocked by 429 quota; drafts stay provisional.

## Implementation

### A. Worker model readiness and usage

Reused contracts:
- `GET /v1/models/usage` (`worker.model-usage.v1`)
- `GET /v1/models/availability` (`worker.model-availability.v1`, cached 5 min, per-process)
- `GET /v1/models/preflight`
- Never `POST /v1/models/probe` from passive UI.

Backend:
- `backend/mission_control/worker_runtime.py::read_worker_runtime()` — read-only GETs, 3 s timeout, `trust_env=False`. Unknown billed costs stay `None`, never zero. Cached availability labelled with freshness note. Outages return `available:false` with honest error, never 500.
- `backend/mission_control/api/worker_runtime.py::GET /api/worker/runtime` — 200 empty-unavailable on Worker down; resolves base URL from app `worker` config else `http://127.0.0.1:7317`. No Projects/Inspect coupling: failure does not affect other routes.
- `backend/mission_control/adapters/worker.py::WorkerAdapter` — extended from health-only to `["health","model_readiness","usage","availability"]` with passive GETs only. Observations: health, cached availability count, usage outcomes/billed unknown, preflight snapshot. All fail-safe to unavailable with `external_claim` provenance when unknown.

Frontend:
- `frontend/src/features/worker/WorkerRuntimePanel.tsx` — polled `GET /api/worker/runtime` (60 s), shows connection, cached availability + freshness, usage outcomes/billed unknown/estimated, policy notes, never triggers probe. Integrated into `SoftwareWorkspace` overview tab (independent of scoring).
- No probe button (spec: live probing requires explicit action + budget; omitted for pilot to guarantee acceptance #4).

### B. Praxis governed improvement bridge

Reused: `mc-praxis-proposal-v1`, `POST /api/praxis/proposals`, `McProposalClient`, `praxis.effectiveness-record.v1`, ActionSpec + human approval.

Backend:
- `backend/mission_control/api/inspect_proposals.py`
  - `POST /api/inspect/opportunities/{id}/proposal-draft` — builds contract-valid draft without importing (dry-run preview).
  - `POST /api/inspect/opportunities/{id}/proposals` — imports via `PraxisProposalService.import_proposal()`. Preserves `opportunity_id`, repository, verification status in `evidence_refs` and `goal.provenance`. Rejects `resolved/rejected` seeds. Requires human-sourced acceptance criterion. Advisory (no `capability_id`) imports as `rejected` with linkage intact — remains advisory, never executable.
  - Redaction: absolute paths and secrets stripped from copied text; evidence kept as repo-relative refs.
  - No new execution API; approval/execution stay on `/api/praxis/proposals/{key}/approve|execute` with digest binding intact.

Frontend:
- `frontend/src/features/praxis/ProposalBridge.tsx::OpportunityProposalBridge` — capability (optional) + acceptance inputs, Preview draft / Import governed proposal. Shows proposal key/status with “approval remains explicit” note.
- `InspectPanels.tsx::OpportunityList` — each card gains “Propose governed improvement” details with bridge + advisory note.
- `LinkedProposals` helper filters `/api/praxis/proposals` by `evidence_refs` containing the opportunity ID.

### C. Project workspace integration

- Inspect tab already exposes capabilities + invocation (`CapabilityDetail`, `UsageBlock`, `CopyCommand`); unchanged except bridge addition.
- Improvements tab: `FindingsSection` (accepted findings) + Inspect opportunities (with bridge) + tasks/recommendations; linked proposals visible via evidence refs.
- Quality tab: unchanged evaluation flow; verification evidence remains separate from execution (see evaluation_boundary).
- AI runtime panel independent of scoring (overview tab, not gated on quality state).
- Reused existing tabs; no new top-level app.

### D. Evidence and provenance

Preserved: originating `opportunity_id`, `repository`, revision/fingerprint (via snapshot), verification `status`. Categories kept distinct:
official publication (`/api/inspect/*`), source-inspected draft (INSPECT-03D chat only, never in snapshot), runtime-verified (`verified_observation` observations), AI-proposed (`proposed` opportunity), owner-accepted (quality review `ACCEPT`), approved proposal (`approved` + digest), verified improvement (only via effectiveness record + human review, never auto).

No unrestricted source text, credentials or absolute paths copied (redaction in `build_draft`).

## E. Controlled ECK pilot (dry-run only)

One bounded dry-run, no target modification, no execution (per spec, no owner authorization for live run).

- Baseline: Inspect opportunity `opp-test-001` (`mission`, `proposed`, evidence `src/a.py`), no linked proposal, no execution.
- Proposed: draft via `POST .../proposal-draft` with empty `capability_id` (advisory) + human acceptance `human:owner`.
- Import: `POST .../proposals` → `rejected` (validation: `single_executable_step` fails with zero steps), linkage `evidence_refs: [inspect:opportunity:opp-test-001, inspect:repository:mission]` preserved.
- Approval: not requested (advisory). Execution: none. Effectiveness: projection only — `praxis.effectiveness-record.v1` shape referenced, no record written; evaluation_boundary (`mc_does_not_assert goal achievement/quality/cost`) respected.
- Resources/cost: zero (no Worker call, no probe, no execution).
- Outcome: plumbing verified (draft → import → evidence linkage), improvement NOT claimed. Reuse decision: pattern valid for real executable proposals once a compatible `ActionSpec` exists (e.g., `writer.*` or `technical.*` with `confirm:true`); advisory path correctly stays non-executable.

## F. Acceptance

1. Reads usage correctly — `test_worker_runtime.py::test_reads_usage_and_availability_without_probe` asserts `billed.unknown_calls==2`, schema pass-through.
2. Outages honest — `test_outage_is_honest_unavailable` asserts `available:false` on `ConnectError`; frontend test asserts “Worker is unavailable … remain available”.
3. Unknown stays unknown — `test_unknown_cost_never_zero` asserts `billed_unknown_calls is None`; UI shows “unknown, not zero”.
4. Cached never probes — backend asserts no `/probe` call in `client.calls`; frontend has no probe button.
5. Opportunity linked — `test_draft_and_import_link_opportunity` asserts draft contains `inspect:opportunity:opp-test-001` and import returns proposal with linkage.
6. Approval/digest intact — existing `test_praxis_proposals.py` (35 tests incl. approval/digest/reject flows) passes unchanged.
7. Rejected/stale cannot execute — existing service guards (`approved` + digest match + single execution) unchanged; new route rejects `resolved/rejected` seeds.
8. Effectiveness associable — evidence endpoint (`GET /{key}/evidence`) returns execution + `evaluation_boundary`; linkage via `evidence_refs` demonstrated in pilot.
9. Observed ≠ verified — UI copy (“proposed, not verified”, “execution success, acceptance and improvement remain distinct”) + `evaluation_boundary.mc_does_not_assert`.
10. Drafts provisional — INSPECT-03D drafts never written to snapshot; UI shows “awaiting human decision”, snapshot `stale` handling untouched.
11. No regression — backend `test_worker_runtime + test_inspect_proposals + test_praxis_proposals + test_inspect` (35 passed); frontend `WorkerRuntimePanel` (2 passed); full suites pending in background at report time (see below).

Live evidence:
- `GET /api/worker/runtime` returns 200 with `available:false` when Worker down (no 500).
- `POST /api/inspect/opportunities/{id}/proposal-draft` returns draft with `evidence_refs` linkage (test).
- `POST .../proposals` advisory returns `rejected` with linkage (test), never `approved`.

## Tests

- Backend new: `backend/tests/test_worker_runtime.py` (3), `backend/tests/test_inspect_proposals.py` (2).
- Backend existing: `test_praxis_proposals.py`, `test_inspect.py` — 35 passed combined in targeted run.
- Frontend new: `frontend/src/test/WorkerRuntimePanel.test.tsx` (2 passed).
- Full suites: backend `pytest -q`: 739 passed, 1 skipped (live Writer CLI path, env-gated); frontend `npm test -- --run`: 25 files, 111 tests passed; `npm run build` (tsc -b + vite) passed.

## Limitations

- Worker live instance not required for tests (mocked `httpx`); real Worker health/availability/usage shapes verified from `worker` repo source, not live call.
- No live probe path (intentional). If added later, needs explicit user action + visible budget + policy checks.
- Proposal bridge supports single-step pilot limit (`MAX_EXECUTABLE_STEPS=1`); multi-step dataflow still needs typed bindings (PRAXIS-06).
- Effectiveness records: association via `evidence_refs`, no second store; real effectiveness evaluation still requires Praxis-side assessment.
- Draft inventories (Worker/Next/Work/AI/Praxis/Steward) remain static-read-only, not official Inspect publications; do not inflate coverage or scores.

## Results

Worker readiness and Praxis bridge plumbing work read-only and governed. ECK pilot verifies linkage without claiming improvement. No commits, pushes, deploys or cross-repo modifications made; changes are local to `mission` working tree for review.
