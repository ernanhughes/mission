# H6 activation and rollback plan

**Not activated.** H6 is qualified only in isolation. Do not tell operators that the feature is available on operational Mission port 8790. No operational database write, migration, service restart, or deployment occurred.

## Activation prerequisites

1. Review and accept this isolated-only H6 result; separately authorize operational activation.
2. Preserve the current operational Mission and Worker artifacts/configuration and database backup under the existing operations procedure. No H6 schema migration is required.
3. Prepare a controlled deployment from a recorded Mission/Worker source identity. Current worktrees contain uncommitted concurrent changes, so do not deploy the entire shared dirty tree as an H6 package. Select and review only the H6 source changes in a clean deployment artifact.
4. Build frontend from `C:\Projects\mission\frontend` with `npm ci` and `npm run build`; run the focused Mission backend/frontend and Worker checks recorded in `H6-TEST-EVIDENCE.md`.
5. Deploy the Mission adapter/UI and the compatible existing Worker strategy/catalogue implementation together. Ensure Worker binds loopback and advertises `/v1/strategies`, model `approved` routes, and the H3 APIs. Configure `MISSION_CONTROL_WORKER_URL=http://127.0.0.1:7317` only if that differs from the existing Worker Application configuration. Keep paid routes unavailable to the H6 launcher.

## Operator activation sequence (after separate approval)

From the chosen clean deployment directory, use the installation's established virtual environment and service supervisor. A direct local smoke invocation is:

```powershell
Set-Location C:\Projects\mission
$env:MISSION_CONTROL_WORKER_URL = 'http://127.0.0.1:7317'
C:\Projects\mission\.venv\Scripts\python.exe -m mission_control --host 127.0.0.1 --port 8790
```

Do not start a second listener if the service supervisor already owns port 8790. Worker’s repository serve command is `bun run serve` from `C:\Projects\worker`; it uses the existing `WORKER_CONFIG` / `WORKER_HOST` / `WORKER_PORT` configuration (default port 7317) and refuses incompatible/non-loopback listeners. Use the installed supervisor rather than launching a duplicate Worker.

## Post-activation smoke checks

1. Confirm Mission health and `/api/harness/catalogue` show the expected Worker version, strategy IDs, configured routes and policy, without changing route qualification labels.
2. Open `/harness`; inspect Strategies and confirm no paid/non-local route is offered.
3. Verify project-scoped episodes and API rejection of an episode outside that exact project key.
4. Use a previously approved synthetic objective and local free route only if separately authorized for a live operation; inspect Work Envelope, Worker H3 record, correlation, resource evidence, artifacts, evaluation and acceptance as separate states.
5. Confirm the operational database backup remains available and that no schema version changed.

## Rollback

If compatibility, isolation, or correlation checks fail, stop the newly deployed Mission service through the existing supervisor, restore the prior Mission application artifact and frontend bundle, and remove the optional `MISSION_CONTROL_WORKER_URL` override if it was newly added. Leave Worker and its configuration unchanged unless its deployment itself caused the fault; then restore the previously captured Worker artifact/configuration through its supervisor. Do not reverse shared-tree edits with `git checkout`, clean, or reset: concurrent dirty/unmerged work exists. Restore only a separately packaged H6 deployment artifact. No database rollback or migration reversal is expected because H6 adds no schema.
