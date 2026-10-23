# Final engineering report

## Repository state

- Repository: `C:\Projects\mission` (the requested `C:\Projects\mission-control` did not exist)
- Branch: `main`
- Implementation commit: `4ee569d` (`Implement Mission Control first release`)
- Bare `git status --porcelain` before the acceptance-documentation commit: clean
- Pushed: **no** remote push was performed
- Working-tree state: recorded at the end of the acceptance-documentation commit; see `git status`
- Runtime data: `C:\Projects\mission\data` (git-ignored), SQLite schema v1
- No second Git repository was created

## Implementation

### Completed milestones

- **MC01** — real repository inventory, integration map, architecture, bounded discovery, read-only Git observation.
- **MC02** — SQLite migrations, YAML defaults with user-override precedence, application registry, launch definitions, projects, books, outcomes.
- **MC03** — React/Vite dashboard with Today, Projects, Books, Applications, Activity and Settings. Production SPA served by FastAPI.
- **MC04** — Windows native detached process launches, structured arguments, no shell, logs, health probes, owned-process stop, restart reattachment.
- **MC05** — checkpoints, focus, resume, tasks, decisions, activity, persistent priority ordering.
- **MC06** — Language, Inference, Math, Next, CoCoder and Worker adapters plus explicit Work block; failure isolation and dedupe.
- **MC07** — deterministic grounded briefing and optional consent-gated OpenAI-compatible interpretation.
- **MC08** — automated tests, security checks, real UI smoke, screenshots, acceptance report.

### Key architecture decisions

- Mission Control coordinates, does not replace, existing systems.
- Application launch is an allowlist of stored definitions; browser requests can never supply a command or cwd.
- Contradictory or unavailable data is not filled in; adapters expose source and limitations.
- User priority is stored separately and never overwritten by discovery or recency.
- Managed processes are launched detached rather than through an asyncio subprocess transport, because the transport terminates children when its event loop closes on Windows.
- Status, health, ownership and launch failure are separate concepts.

### Backend

FastAPI + SQLAlchemy + SQLite. Versioned SQL migration, Pydantic contracts, loopback-only binding, origin guard, security headers, process manager, background discovery, adapter service and briefing generator. `GET /api/health`, `/docs` and `/openapi.json` are available.

### Frontend

React 19 + TypeScript + Vite. Typed API client, accessible modal/forms, dark/light themes, responsive layout, loading/empty/error states, capability-aware action buttons, application configuration editor with launch definitions.

### Data storage

`data/mission_control.db` and `data/logs/`. SQLite schema version 1. No cloud dependency. Backups require stopping the backend and copying `data/`.

### Launch mechanism

A safe fixture application was registered and launched through the dashboard on an isolated 8791 instance. The UI showed Running with a real PID and streamed fixture logs. Backend integration tests additionally verify launch, stop, duplicate/limit handling, failure diagnostics, log redaction, editor invocation and backend-restart reattachment. See `process-launch-evidence.txt` and `ui-launch-evidence.txt`.

### Available adapters

- Language manuscript evidence — verified
- Inference manuscript/status evidence — verified
- MATH01 qualification evidence — verified
- Next local SQLite snapshot — verified as a snapshot only
- CoCoder review artifact — requires configured artifact
- Worker `/health` — verified endpoint, unavailable when not running
- Work — blocked: no verified read-only export; no fake records

## Verification

- Backend tests: **43 passed**
- Frontend tests: **9 passed**
- Production build: **passed**
- Backend lint (`ruff check backend scripts`): **passed**
- Real discovery: **98 candidates**, 84 unlinked; generated/build/cache exclusions applied
- Real process launch and stop: passed
- Backend restart reattachment: passed
- Configured editor repository + documentation launch: passed
- Real UI checkpoint + backend restart: passed
- Browser smoke: 7 pages, no console errors
- OpenAPI docs: served on `/docs` with route-specific CSP
- AI: deterministic briefing verified; offline fallback verified; no live paid provider call

Commands:

```powershell
.venv\Scripts\ruff.exe check backend scripts
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
```

### Unavailable integrations / known limitations

- Work requires PostgreSQL and a verified read-only export; not displayed.
- Next adapter reads local SQLite, not PostgreSQL.
- CoCoder adapter needs an artifact path.
- Writer, Improve, BookBuilder, Stephanie and Workbench have no adapters.
- No BookBuilder build action is enabled because publishing artifacts can be overwritten.
- No live AI/provider quality test.
- No Playwright E2E; browser smoke plus component tests were used.
- Retention settings are stored but cleanup is not automated.
- Startup profile is explicit, not automatic at login.
- A launcher that exits immediately after spawning a grandchild may be reported lost rather than guessed.
- External repositories changed concurrently during the session; Mission Control only issued read-only Git commands. See `PRE-EXISTING-REPO-STATES.md`.

## User instructions

Start:

```powershell
cd C:\Projects\mission
.\scripts\setup.ps1      # once
.\scripts\start.ps1
```

Open **http://127.0.0.1:8790**.

1. **Open a priority book** — click Books, choose Language/Inference/Math, edit book state or open the project workspace.
2. **Add an application** — Applications → Add application; configure identity, path and a verified launch definition; save.
3. **Launch a tool** — Applications → Launch. If confirmation is required, confirm. Inspect status/logs and use Stop only for owned processes.
4. **Save a next action** — open a project workspace, expand Save a new checkpoint, enter summary/next action/blockers, save.
5. **Resume** — after restarts, Home shows the latest checkpoint from any project; press Continue work or open the project.

Stop with `Ctrl+C` or `.\scripts\stop.ps1`. Managed applications remain running and reattach on restart by design; stop them explicitly in the UI.

## MC09 proposal (not implemented)

1. Add an explicit **cross-application context contract** for selected conversations/work sessions, with user consent, source attribution, retention and no private-file scraping.
2. Add a verified **Work read-only export/endpoint** and a Writer/Improve status contract.
3. Introduce **reviewed execution proposals**: Mission Control attaches evidence and a bounded plan; a person approves; Worker executes; results return with provenance.
4. Add **publishing approval** with previews and explicit confirmation before artifact overwrite.
5. Implement retention execution with dry-run previews and a reviewable backup/export flow.
6. Add browser-level E2E tests and a packaged launcher that honours the saved startup profile.
