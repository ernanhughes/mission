# SC4 Mission improvement workspace

> Historical source-state description from before SC4A execution integration.
> Current bounded execution path and qualification limits are in the linked
> SC4A/SC4B records in the Stephanie programme directory. Operational service
> activation remains off.

## Scope delivered

Mission adds `/improvement`, backed by a read-only `GET /api/improvement/records` projection over the accepted SC3 artifact directory. The page groups work episodes, findings, corrective proposals, envelopes, harness catalogue entries, and Praxis proposals into Overview, Opportunities, Experiments, Experience, and Configuration views. The SC3 evidence view is historical and explicitly isolated/non-operational.

An operator may select an existing open finding to create an inert `REQUEST_USER_DECISION` Work Corrective proposal through Mission's existing API. That proposal is an investigation request only. The page does not authorize or execute an experiment, dispatch Stephanie, invoke Worker, or make a model call.

The artifact projection checks the SC3 candidate, protocol, hypothesis, results, experience, and AI trace relationships. The sidecar `mission-projection-manifest.json` is a post-hoc hash snapshot; it detects later edits only while the manifest is unchanged. It is not a signature, trusted timestamp, or retroactive attestation. Raw AI response bodies are never returned by the projection.

## Changed files

- `backend/mission_control/api/improvement.py`; router registration in `backend/mission_control/main.py`.
- `frontend/src/features/improvement/ImprovementPage.tsx`; route and navigation entries in `frontend/src/app/App.tsx` and `frontend/src/components/Layout.tsx`.
- Focused backend and frontend tests in `backend/tests/test_improvement_api.py` and `frontend/src/test/ImprovementPage.test.tsx`.

## Limits and activation

No database schema change, write-side integration, cross-service dispatch, Worker execution, or live inference was added. The running Mission process at `:8790` predates this change: its health response reports schema 54 and `GET /api/improvement/records` returns 404. Do not treat the local frontend build as deployment. Activation remains off pending a clean controlled package, backup/rollback evidence, and isolated end-to-end verification.

See the Stephanie SC4 programme records under `C:\Projects\stephanie\docs\programmes\STEPHANIE-CONVERGENCE-04` for consolidated evidence and the final gate.
