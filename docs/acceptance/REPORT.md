# Mission Control acceptance report

Date: 23 October 2026

Repository: `C:\Projects\mission` (the requested `C:\Projects\mission-control` did not exist)

## Verdict

The first release is usable. Priority books, application registry, real Windows process launching, persistent checkpoints, read-only adapters and a grounded daily briefing work against the real API and local filesystem.

Not every ecosystem integration is available. Work, Writer, Improve, BookBuilder, Stephanie and Workbench do not have verified read-only adapters, so they show explicit limitations rather than invented data. This is reported below and in the UI.

## Scenario results

| Scenario | Result | Evidence |
| --- | --- | --- |
| **A. Start the application** | **Pass** | `.\scripts\setup.ps1` and `.\scripts\start.ps1` documented and exercised; setup output in `setup-output.txt`; production SPA served at http://127.0.0.1:8790; `/api/health` status ok, schema v1. |
| **B. Initial workspace** | **Pass** | Language, Inference and Math are pinned and visible; Next, CoCoder and Work are registered. Missing/unconfigured capabilities render safely. |
| **C. Discover applications** | **Pass** | Real scan of `C:\Projects` + `C:\books`: 98 candidates, 84 unlinked, generated directories excluded; no application/launch was auto-created. See `discovery-summary.json`. |
| **D. Configure and launch** | **Pass** | Real fixture process launched from the dashboard on an isolated 8791 instance; status reached Running; logs visible; backend integration test launched/stopped a real process. See [UI launch evidence](ui-launch-evidence.txt). |
| **E. Open a repository** | **Pass** | Integration test configured a native editor executable, invoked it, and verified the registered repository path was received. No hardcoded editor path. |
| **F. Resume work** | **Pass** | Saved a Math checkpoint through the UI, switched focus to Language, stopped and restarted the backend, returned to Math; checkpoint/next action/blocker/evidence persisted. Home shows focus and resume separately. |
| **G. Application failure** | **Pass** | Invalid executable produced HTTP 422 with diagnostics; application status became launch failed; API/dashboard remained healthy; no secrets appeared. |
| **H. Adapter unavailable** | **Pass** | CoCoder unavailable without an artifact; Worker unavailable offline; Work blocked without a verified export; no recommendations or statuses were fabricated. |
| **I. Priority ordering** | **Pass** | UI reorder persisted; backend test restarted the application and confirmed the selected book order and priorities. |
| **J. Existing repository protection** | **Pass with pre-existing dirt** | Read-only Git snapshot; no target repository was written to. Existing dirty states are recorded separately. |

## Test results

```text
Backend:   43 passed
Frontend:   9 passed
Build:      TypeScript + Vite production build passed
```

Commands:

```powershell
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
```

Test coverage highlights:

- registry CRUD, validation, default/user precedence, relationships;
- SQLite migrations, repeatability and table creation;
- discovery classification, exclusions, duplicate roots, bounds and cancellation;
- real process launch, logs, stop, duplicate launch, process limit, failure, health timeout;
- backend restart reattachment using a detached process;
- configured editor launch for a repository and a documentation file;
- external process ID cannot be stopped;
- checkpoint/focus/resume across restart;
- task/decision/recommendation review;
- adapter valid/malformed artifacts, unsafe paths, failure isolation, dedupe;
- origin guard, headers, path traversal, unsafe executables, secret handling, log redaction;
- home, priority reorder, launch failure, configuration editing, book selection, checkpoint creation, task completion, empty states.

## Real process evidence

See [process-launch-evidence.txt](process-launch-evidence.txt). Summary:

```text
POST /api/applications/acceptance-process/launch -> 201
process_id=proc-... pid=50796 status=running
fixture-start pid=50796
fixture-arg=acceptance
application status while running: running / managed
POST .../stop -> 200 status=stopped
final process status: stopped
/api/health -> ok
```

The fixture is a genuine local Python process launched through Mission Control's process manager, not a mock. The dashboard launch path was independently exercised through the browser on port 8791 on an isolated data directory.

## Discovery evidence

- Roots: `C:\Projects`, `C:\books`.
- 98 candidate records; 84 unlinked, 14 already linked.
- Classification counts: book 41, executable application 14, library 14, supporting repository 12, research project 8, unknown 4, background service 2, publishing site 1, experiment 1, generated artifact 1.
- 6 top-level directories excluded; generated/build/cache names are excluded by default.
- Scan duration: 3.241 s in the recorded run; bounded and cancellable.
- No candidate automatically received a launch definition.
- Classification is explicitly advisory with evidence and confidence.

## UI smoke results

Full report: [UI-SMOKE.md](UI-SMOKE.md).

- Pages loaded: Today, Books, Projects, Math workspace, Applications, Activity, Settings.
- Browser console errors: none.
- Theme toggle: dark → light, persisted to local storage.
- Priority reorder UI: executed and restored; API reflected the order.
- Checkpoint UI: saved and survived a real backend restart.
- UI launch: isolated dashboard launched a real process, showed Running and rendered logs.
- Deterministic briefing: generated from real persisted evidence and provider-ready fallback.
- Screenshots: `docs/acceptance/screenshots/`.

## Repository state

- Repository root: `C:\Projects\mission`
- Branch: `main`
- Implementation commit: `4ee569d`
- Implementation working tree at commit time: clean
- Acceptance documentation is committed separately after this report.
- Nothing was pushed.
- Integration repositories were inspected with read-only Git commands. Several were already dirty before this work; they were not fetched, cleaned, reset or modified.
- External repositories changed concurrently during the session; Mission Control has no write path into them. Compare the committed initial snapshot with [PRE-EXISTING-REPO-STATES.md](PRE-EXISTING-REPO-STATES.md).

## Unavailable integrations and known limitations

- **Work**: requires PostgreSQL and has no verified read-only export; no opportunities are shown.
- **Next**: adapter reads the local SQLite snapshot; it does not inspect the active PostgreSQL store (`NEXT_DSN` present).
- **CoCoder**: requires a configured review JSON artifact; none was set during acceptance.
- **Worker**: health-only; not running at acceptance; no job submitted.
- **Writer / Improve / BookBuilder / Stephanie / Workbench**: no adapter; repository/documentation access only.
- **BookBuilder**: CLI shape verified, but no per-book build is enabled because artifacts can be overwritten.
- **AI**: not configured; only deterministic and offline/failure fallback were verified. No paid model call or model-quality claim.
- **Playwright**: no browser E2E framework was added; browser smoke used the local browser harness/DOM inspection plus component tests.
- **Retention**: settings are stored but automatic deletion is not implemented.
- **Startup profiles**: opt-in and explicitly activated; nothing starts automatically at login.
- **Launcher wrappers**: a wrapper that exits while leaving a grandchild can be marked lost rather than guessed; configure native long-lived executables.

## Next milestone (MC09)

A bounded cross-application coordination milestone, not autonomous control:

1. Add a **conversation/context adapter contract** for writer/worker sessions with explicit user consent, source attribution and no scraping of private chat files.
2. Add a **read-only Work export** (or documented local endpoint) so opportunities can be shown with genuine source and readiness states.
3. Add **reviewed execution proposals**: Mission Control proposes a bounded action with evidence; the user approves; Worker executes through its existing API; the result/evidence returns to Mission Control. No automatic repository mutation.
4. Add **publishing/build approval** for BookBuilder with a preview diff before any artifact overwrite.
5. Add **scheduled freshness policy** and retention execution with dry-run previews.
6. Add browser-level E2E tests and a packaged launcher that reads the stored startup profile.
