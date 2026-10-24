# Mission Control

Mission Control is a local-first control centre for an existing ecosystem of AI applications, books, research programmes and commercial projects. It does not replace those systems. It coordinates them: what matters today, where work stopped, which evidence exists, what can be launched safely, and what should happen next.

![Today](docs/acceptance/screenshots/home.png)

## What is implemented

- **Three priority books** — Language, Inference and Math — with persistent workspaces, next actions, priorities and checkpoints.
- **A real application registry** — add or edit applications in the UI, including structured launch definitions, monitoring, documentation actions and relationships. No code change is required.
- **Windows process control** — launch stored commands without a shell, capture logs, stop only Mission Control-owned process trees, detect port conflicts, and reattach to detached servers after a backend restart.
- **Daily continuity** — project focus, checkpoints, tasks, decisions, activity and a resume card based on the latest saved checkpoint.
- **Read-only discovery** — bounded scans of `C:\Projects` and `C:\books`, classification with evidence, exclusions, cancellation and persisted candidates. Discovery never enables a launch command.
- **Unified engine workspaces (MC09)** - Next, Work and CoCoder expose their real data inside Mission Control: candidates and evidence, opportunities and qualification, repository findings and review operations.
- **Unified inbox and federated search** - one attention queue and one search surface across Next, Work, CoCoder, projects, repositories, tasks, checkpoints and decisions. Source identity is preserved.
- **Controlled application actions** - registered, validated operations with approval and durable execution history. CoCoder reviews can be launched from Mission Control; Next and Work write operations remain explicitly blocked.
- **Shared project context** - associate Next candidates, Work opportunities and CoCoder findings with projects without copying ownership away from the source engines.
- **Cross-application experiments (MC10)** - one traceable Next → approval → Worker → CoCoder → human-decision workflow, with scope enforcement, local inference and durable evidence.
- **Evidence adapters** - Language, Inference, Math, live read-only Next, Work JSON CLI, CoCoder artifacts and Worker health. Unavailable integrations are shown as unavailable; they are not filled with sample data.
- **Grounded daily briefing** - deterministic by default. Optional OpenAI-compatible AI interpretation only after explicit configuration, consent and request. AI remains advisory.
- **Local API and OpenAPI docs** - FastAPI at `/api/*` and `/docs`.

## Unified application interface (MC09)

Mission Control is the interface; Next, Work and CoCoder remain independent
engines. The workspaces are real application surfaces, not shortcuts.

| Workspace | What is usable |
| --- | --- |
| **Next** | Live opportunities, runs and evidence gaps; searchable candidates; scores and experiment detail; local decisions; project association. Discovery launch is blocked pending a reviewed contract. |
| **Work** | Live opportunities and qualification; filtering; buyer/location/compensation context; local shortlist, defer, reject or investigate decisions. Source synchronisation is blocked. |
| **CoCoder** | Repositories, assessments and findings; severity/evidence/affected paths; local dispositions; a registered, confirmed review action with execution history. |
| **Inbox** | Pending items from Next, Work, CoCoder and Mission Control tasks, with source filters, priority and functional detail links. |
| **Search** | Federated results from application resources, projects, repositories, tasks, checkpoints and decisions. |
| **Project context** | Next, Work and CoCoder records associated with a project, with freshness and local decision state. |
| **Command palette** | `Ctrl+K` navigation, project shortcuts, available refresh commands and federated search. |

Decisions made in Mission Control are stored locally with
`sync_state=local_only`. They never claim that Next, Work or CoCoder was updated.
The UI distinguishes source state, cached observation time and human decisions.

### Integration modes

- **Next** - SELECT-only PostgreSQL session through the environment variable
  named by `dsn_env` (default `NEXT_DSN`), with
  `default_transaction_read_only=on`. If no DSN is configured, a configured
  SQLite file is opened read-only. This is a database compatibility integration,
  not a stable Next API.
- **Work** - the documented `work opportunities --json` CLI. Mission Control
  never invokes `work decide` or writes Work's database.
- **CoCoder** - JSON review artifacts plus the `cocoder review` CLI. Mission
  Control redirects CoCoder's own SQLite/artifact state into
  `data/integrations/cocoder/engine` so reviewing a repository does not create a
  repository-local `.cocoder` directory.

See [the integration audit](docs/MC09-INTEGRATION-AUDIT.md) for verified source
contracts and missing interfaces, and [the acceptance report](docs/acceptance/MC09-REPORT.md)
for real data, browser evidence and limitations.

## Cross-application experiments (MC10)

MC10 adds one complete, evidence-preserving workflow rather than another
dashboard:

```text
Next evidence
  -> Mission Control proposal with exact scope, budget and stop conditions
  -> human approval (scope acknowledgement + approval hash)
  -> Worker local execution
  -> approved one-file patch + deterministic tests/measurement
  -> CoCoder review of the actual result commit
  -> human accept / reject / investigate
```

The first template is a bounded TraceLite proxy experiment derived from a real
Next candidate. It implements `reduce_trace` in a dedicated Git sandbox and
measures a duplicate-heavy trace (`21 -> 3` events; 85.7% reduction).

Open **Experiments** in the navigation. A TraceLite candidate in Next also shows
**Propose TraceLite experiment**; nothing executes until the exact file scope is
approved.

### Requirements for MC10 experiments

- A running Worker service at `http://127.0.0.1:7317`.
- A local OpenAI-compatible model endpoint; the acceptance run used Ollama at
  `http://127.0.0.1:11434/v1` with `qwen2.5-coder:latest`.
- Worker's `direct` executor configured with that local gateway. No hosted paid
  route is used.
- The experiment sandbox under `data/experiments/tracelite-spike` and the
  Next export under `data/integrations/next/`.

Worker's `direct` executor is explicitly lower-parity: it returns model output
with `AWAITING_ACCEPTANCE`, not Work Evidence or Acceptance. MC10 never presents
that output as verified. Deterministic tests are the gate, and CoCoder reviews
the resulting commit independently.

### Next research export

Next now owns a versioned read-only export:

```powershell
C:\Projects\next\.venv\Scripts\python.exe -m next export `
  --output C:\Projects\mission\data\integrations\next\next-research-export-v1.json `
  --limit 200
```

The MC09 read-only PostgreSQL adapter remains in place; MC10 uses the export as
the immutable research evidence for a workflow.

### Safety guarantees

- Approval is bound to a hash of objective, exact file scope, repository,
  baseline commit, file hash, Worker config and prompt.
- Execution rejects stale approval, a changed baseline/file, or a dirty sandbox.
- The model may change only `tracelite/reduce.py`; extra paths are rejected.
- Generated Python is AST-checked; imports and dangerous calls are rejected.
- A new attempt resets to the tagged `mc10-baseline`; prior result commits are
  tagged before reset.
- CoCoder high/medium findings block automatic acceptance; an explicit human
  override with a reason is required.
- Replaying a completed create/execute/review returns the same identities; it
  does not create duplicate Worker requests or commits.

See [the MC10 audit](docs/MC10-REALITY-AUDIT.md), [workflow contract](docs/MC10-WORKFLOW-CONTRACT.md)
and [acceptance report](docs/acceptance/MC10-REPORT.md).

## Requirements

Tested on Windows 11 with:

- Python **3.13** (3.12 or newer required)
- Node.js **25** used and tested on this machine. Node 24 LTS is recommended. `npm install` may print engine warnings from the dev-only vitest/jsdom packages on Node 25; the test suite and production build still pass.
- npm 11
- PowerShell 5.1 or PowerShell 7+
- Git on `PATH` for read-only repository observation
- **Optional for MC10 experiments:** Bun 1.x for Worker and a local
  OpenAI-compatible model endpoint (Ollama was used for acceptance)

No Docker, Kubernetes, hosted database or cloud service is required. Mission
Control itself stores state in SQLite. A PostgreSQL connection is optional and
used only for a read-only Next integration when `NEXT_DSN` is configured; the
SQLite snapshot remains the fallback. Hosted paid inference is not required for
MC10 experiments.

## Install

From PowerShell in the repository root:

```powershell
.\scripts\setup.ps1
```

If script execution is disabled:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The script creates `.venv`, installs the backend in editable mode with test dependencies, installs frontend packages, and builds the production frontend. It uses `uv pip` when uv created the environment (uv virtual environments do not contain pip) and stops on a failed native install/build instead of reporting a false success.

## Start

```powershell
.\scripts\start.ps1
```

URL: **http://127.0.0.1:8790**

The script verifies dependencies, rebuilds the frontend if `frontend/dist` is missing, starts the backend on loopback, and opens the URL.

For frontend development:

```powershell
.\scripts\dev.ps1
```

That starts the API on port 8790 and Vite on http://127.0.0.1:5173. The Vite proxy forwards `/api` to the backend.

## Stop

Press `Ctrl+C` in the window running `start.ps1`.

Or, from another PowerShell window:

```powershell
.\scripts\stop.ps1
```

`stop.ps1` refuses to stop a process on port 8790 unless its command line looks like Mission Control.

**Managed application processes are intentionally left running when Mission Control stops.** They are launched detached so that a backend restart does not kill a server. Mission Control reattaches to owned processes on the next start using the recorded PID and process creation time. Use the Applications page to stop them explicitly.

## First use

1. Open **Today**.
2. Choose a priority book or project, or open its workspace and press **Set focus**.
3. In a project workspace, save a checkpoint with a summary and next action.
4. Open **Applications** to launch configured tools or register new ones.
5. Open **Settings** to configure an editor, add discovery roots, manage exclusions and optionally configure AI.

The Home screen shows:

- current human-selected focus;
- the most recent checkpoint from any project, clearly attributed to that project;
- pending adapter recommendations;
- pinned priority books in user-defined order;
- pinned core applications with real runtime state;
- recent activity and supported outcomes.

## Everyday use

**Open a priority book**
1. Click **Books** in the navigation, or **Open** on a book card on Today.
2. Select Language, Inference or Math in the left rail.
3. The workspace shows the user-maintained status, milestone, next action, checkpoint and manuscript paths.

**Use an engine workspace**
1. Open **Next**, **Work** or **CoCoder** under **Engines**.
2. Use the tabs for candidates/opportunities/findings, evidence, decisions and operations.
3. Open a record to inspect source evidence and record a local decision or project association.
4. In CoCoder, **Operations** can launch a bounded review against a registered repository after confirmation.

**Run a cross-application experiment**
1. Open the TraceLite candidate in **Next** and press **Propose TraceLite experiment**, or open an existing trace under **Experiments**.
2. Inspect the original research evidence, exact file scope, Worker model, budget, stop conditions and evaluation criteria.
3. Tick the scope acknowledgement and approve. No Worker call occurs before approval.
4. Execute with confirmation. Mission Control applies only the approved patch, runs deterministic tests/measurement and requests a CoCoder review of the actual result commit.
5. Inspect the review and record **Accept**, **Investigate** or **Reject**. CoCoder high/medium findings require an explicit override to accept.

**Review the inbox and search**
1. Open **Inbox** to see pending Next candidates, qualified Work opportunities, CoCoder findings and tasks together.
2. Filter by source or priority; **Open** goes to the functional detail view.
3. Open **Search** or press `Ctrl+K` to search application resources, projects, tasks, checkpoints and decisions.

**Add an application**
1. Open **Applications → Add application**.
2. Fill identity and paths, then add a launch definition.
3. Enable it only after you have verified the command yourself.
4. Save. The new application appears without restarting Mission Control.

**Launch a tool**
1. Open **Applications** (or a pinned app on Today).
2. Press **Launch**. If the control policy requires confirmation, confirm the native dialog.
3. The status becomes Running and the process appears in the managed process table.
4. Press **Logs** for output or **Stop** to terminate the owned process tree.

**Save a next action and resume**
1. Open a project workspace.
2. Under **Checkpoint and resume**, expand **Save a new checkpoint**.
3. Enter what happened, the next intended action and optional blockers/evidence; save.
4. The project becomes the current focus. The Home resume card shows the latest checkpoint across all projects.
5. After restarting Mission Control, open the project or press **Continue work** on Today.

## Data storage, backup and reset

Default local data:

```text
data/
  mission_control.db      SQLite database (registry, continuity, workflows)
  integrations/
    next/
      next-research-export-v1.json  Versioned Next research evidence
    worker/
      worker-config.json  Local Worker direct-executor configuration
    cocoder/
      cocoder-config.toml CoCoder state redirection
      review-*.json       Real review artifacts
      engine/             CoCoder SQLite and internal artifacts
  experiments/
    tracelite-spike/      Git sandbox for the MC10 experiment
  logs/
    mission-control.log   Rotating application log
    proc-*.log            Managed process output, redacted on read
```

The directory is git-ignored. Override it with `MISSION_CONTROL_DATA_DIR`.

**Backup:** stop the backend, then copy the entire `data` directory. Process reattachment is not guaranteed if you move the database to another machine.

**Reset user configuration and history:** stop the backend, stop managed applications, rename or delete `data`, then start Mission Control again. Shipped defaults under `config/defaults` are re-seeded. No other repository is touched.

## Configuration precedence

1. **Shipped YAML defaults** in `config/defaults/` are inserted only when an ID does not exist.
2. **Discovery metadata** updates repository observation fields and candidate classification.
3. **User edits in the registry and settings are stored in SQLite and always win.** Re-running discovery or restarting never overwrites priority, pinning, names, launch definitions or notes.

The YAML files are defaults, not a live configuration source. To change a seeded application, use the UI or API. This prevents a future release's default file from silently undoing user work.

## Adding an application

In **Applications → Add application**:

1. Give it a name, category and optional repository/documentation paths.
2. Add a **launch definition**:
   - **Command** for a bounded CLI action.
   - **Server** for a long-running process.
   - **URL only** for an already-running web interface.
3. Set an executable (native `.exe`, or a command resolvable on `PATH`), an argument array, working directory, and optional health check.
4. Mark it **Verified** only after you have run the command yourself and confirmed it starts the intended system.
5. Enable the definition. A launch request uses only the stored definition; it can never supply an executable, working directory or shell command from the browser.

Example registry shape (illustrative only — not a claimed working command for your machine):

```yaml
id: example-tool
name: Example Tool
category: supporting
repository: 'C:\Projects\example'
enabled: true
pinned: false
launch:
  type: command
  working_directory: 'C:\Projects\example'
  executable: 'C:\Tools\example.exe'
  arguments: ['--help']
  enabled: false
  verified: false
  verification_note: 'Replace this example after verifying the real command.'
monitoring:
  type: none
integration:
  adapter: null
  enabled: false
```

The default registry intentionally contains no invented launch commands. Work and Worker definitions are disabled and unverified until you choose to configure them.

### Windows launch rules

- `shell=False` always. Argument arrays are passed directly.
- `.cmd`, `.bat` and `.ps1` files are rejected as launch executables. Configure the native executable instead.
- Paths may contain spaces; they are passed as structured arguments.
- Environment variables are copied only from an allowlist (Windows essentials) plus explicitly named variables in the launch definition. The full parent environment, including unrelated credentials, is not inherited.
- Health checks only run for **enabled** definitions. A responding port does not prove that the configured application owns it; external findings are labelled accordingly.
- Mission Control will not stop an externally detected listener or a process it did not launch.

## Adding a project or book

**Projects → Add project** supports a project kind, description, milestone, next action, one primary repository path and optional book title.

For a book project, Mission Control also creates a book workspace. Book status, milestone, next action, quality review state and URLs are user-maintained until a verified Writer/BookBuilder integration exists. Git activity is never treated as completion evidence.

## Priorities and ordering

Priority is always human-controlled.

- Use the up/down controls on **Today** or **Books** to reorder books.
- Use **Projects** up/down controls to reorder all projects.
- Pin or unpin a project in its workspace or in the projects list.
- Ordering and pin state are persisted in SQLite and survive restarts.
- Discovery never promotes a repository because it was recently modified.

## Checkpoints and resume

A checkpoint records:

- what happened;
- the last completed action;
- the next intended action;
- blockers;
- evidence references;
- an optional milestone.

Saving a checkpoint makes that project the current focus, updates its next action, and survives backend restarts. The Home resume card is based on the **latest checkpoint across all projects**, not just the selected focus, so changing focus does not hide where work actually stopped.

## Status meanings

- **Running** — a managed child is alive, or an enabled health endpoint currently responds.
- **Running (external)** — an endpoint responds, but Mission Control does not own it. A responding port does not prove application identity.
- **Stopped** — a launch action exists; no managed process is running.
- **Unavailable** — no verified/configured capability, or a health probe failed.
- **Misconfigured** — an enabled definition has a missing executable, working directory or health URL.
- **Not checked** — health history has not been collected.
- **Stale** — the last observation is older than its freshness window.
- **Launch failed** — the most recent attempt failed; inspect the failure detail and log.

User-entered state (book status, next action, focus) and observed state (process, Git, adapter evidence) are stored separately.

## Editor configuration

Mission Control never assumes an editor path. Configure a **native** executable in Settings, for example:

```text
C:\Users\<you>\AppData\Local\Programs\Microsoft VS Code\Code.exe
```

`code.cmd` is rejected because the launcher is a shell script. With no valid editor configured, repository buttons are disabled and explain why.

## Integrations and adapters

Adapter reads are read-only and independent. Each records source, timestamp and
evidence. Only registered actions can write, and only under Mission Control's
data directory or local state.

| Integration | State | What it reads / does |
| --- | --- | --- |
| Language book | Verified | `content/books/language` chapter files and `planning/STATUS.md` |
| Inference book | Verified | `C:\books\inference` chapter files and the README's dated status claim |
| Math book | Verified | `artifacts/math01/report.json` assessments, capabilities and unresolved obligations |
| Next | Verified read-only | Live PostgreSQL through `NEXT_DSN` with a read-only transaction; configured SQLite fallback. Labelled a compatibility integration, not a stable Next API. Discovery launch is blocked. |
| Work | Verified read-only | Documented `work opportunities --json`; 130 live opportunities in acceptance. Decisions remain local; no Work write path. |
| CoCoder | Verified | JSON review artifacts and a registered bounded `run_review` action. Engine state and artifacts stay under `data/integrations/cocoder`. |
| Worker | Verified HTTP + local executor | `GET /health` for status; MC10 workflows can call `POST /v1/work` with the local `direct` Ollama executor. The adapter health surface does not submit work by itself. |
| Writer / Improve / BookBuilder / Stephanie / Workbench | Not integrated | Repository/documentation access only; build and launch actions remain disabled until verified |

Adapters fail in isolation. An unavailable adapter, timeout or malformed artifact produces an unavailable status and diagnostics, not a dashboard failure.

## Optional AI integration

AI is disabled by default and requires:

1. `ai.enabled = true`;
2. explicit `ai.consent = true`;
3. an OpenAI-compatible base URL and model;
4. the API key, if needed, in the named environment variable (for example `OPENAI_API_KEY`).

API keys are never stored in SQLite, returned by the API or logged. The key name — not the value — is configuration.

The deterministic briefing always works. If the provider is offline or fails, the deterministic briefing is retained and the failure is reported. AI can only summarise, compare and recommend. It cannot launch tools, modify repositories, publish, submit applications or spend money. AI suggestions retain evidence references and never overwrite human priorities.

## API

- OpenAPI UI: http://127.0.0.1:8790/docs
- OpenAPI JSON: http://127.0.0.1:8790/openapi.json
- Health: http://127.0.0.1:8790/api/health

Browser-originated state-changing requests must come from an allowlisted local origin and include `X-Mission-Control-Request: 1`. The backend binds to loopback only and rejects non-local hosts at startup. Launch requests accept only a launch definition ID and confirmation flag — never an executable or shell command.

## Tests

```powershell
.\scripts\test.ps1
```

Or directly:

```powershell
.venv\Scripts\ruff.exe check backend scripts
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
```

Current result: **53 backend tests passing, 26 frontend tests passing, production build succeeds.** The suite includes real local process launch/stop/log capture, a backend restart reattachment test, real configured-editor invocation, discovery exclusions, migrations, checkpoint persistence, adapter failure isolation, integration decisions/inbox/search, action parameter and repository validation, workflow approval/scope/stale-approval/adverse-review/replay tests, origin/security checks and secret redaction. MC10 additionally passed a real Chrome acceptance workflow; see [the MC10 report](docs/acceptance/MC10-REPORT.md).

## Troubleshooting

**Application will not launch**
- Open the application's failure line and **Logs**.
- Check the executable resolves on `PATH` or is an absolute native executable.
- Check working directory exists.
- `.cmd`, `.bat` and `.ps1` launchers are rejected by design; point to the native executable.
- If the expected port is already in use, Mission Control refuses to claim or stop the foreign listener.

**Repository button is disabled**
- Configure a native editor executable in Settings.
- The button title/why-actions panel gives the specific reason.

**Status is stale**
- Click **Refresh** on the page or configure a health check and enable its definition.
- External listeners are never treated as Mission Control-owned.

**Managed process shows reattached**
- The backend restarted while the process stayed alive. This is expected. Stop it from the Applications page if it is still Mission Control-owned.

**Managed process shows lost**
- The process ended or its identity no longer matches the recorded PID/creation time. Mission Control will not kill a process on identity mismatch.

**Discovery misses something**
- Check excluded names/patterns. Add a root in Settings.
- Classification is advisory; use the candidate evidence, then register an application or project explicitly.

**Frontend build missing**
- Run `.\scripts\start.ps1 -Rebuild` or `cd frontend; npm run build`.

**Browser origin rejected**
- Use `http://127.0.0.1:8790` or `http://localhost:8790`. Do not access through arbitrary origins.

## Security model

- Loopback binding only; non-local host startup is refused.
- No unrestricted shell endpoint.
- No arbitrary executable from request payloads.
- Process environment is allowlisted.
- Only owned processes can be stopped, and only after PID creation-time verification.
- Path traversal, relative roots and device paths are rejected.
- Secrets are redacted in logs and never included in API responses.
- Discovery and Git observation are read-only.
- Integration actions are registered, schema-validated and adapter-validated before queueing. The browser sends an action ID and typed parameters, never a command.
- CoCoder repository paths must match the registered allowlist; invalid paths return 422 before an execution exists.
- CoCoder review state is redirected under Mission Control data; a review does not create `.cocoder` in the reviewed repository.
- MC10 workflow approval is bound to an exact file scope, baseline commit, file hash, Worker config and prompt hash. Execution rejects stale approval, a changed baseline/file, or a dirty sandbox.
- Worker output is applied only to the approved path; extra paths and dangerous Python constructs are rejected before writing.
- MC10 acceptance used a local Ollama model and no paid inference route.
- External publishing, repository mutation, model spending and destructive actions are not implemented as autonomous operations.

See [docs/MC01-ARCHITECTURE.md](docs/MC01-ARCHITECTURE.md) and [docs/SECURITY.md](docs/SECURITY.md).

## Repository policy

Mission Control was built in `C:\Projects\mission`. Integration repositories were inspected read-only during MC09. For MC10, Next received one local, tested source contract (`491b501`) adding `next export`; it was not pushed. The export command uses Next's own `ResearchStore`, which may apply Next's own schema initialization/migrations; the export itself changes no research rows. Work, Worker and CoCoder source files were not modified. Pre-existing dirty states are recorded separately in [docs/acceptance/PRE-EXISTING-REPO-STATES.md](docs/acceptance/PRE-EXISTING-REPO-STATES.md).

## Documentation map

- [MC01 inventory](docs/MC01-INVENTORY.md)
- [MC01 integration map](docs/MC01-INTEGRATION-MAP.md)
- [Architecture](docs/MC01-ARCHITECTURE.md)
- [Security](docs/SECURITY.md)
- [Milestone evidence](docs/milestones/README.md)
- [MC09 integration audit](docs/MC09-INTEGRATION-AUDIT.md)
- [MC09 architecture](docs/MC09-ARCHITECTURE.md)
- [MC09 acceptance report](docs/acceptance/MC09-REPORT.md)
- [MC09 browser/runtime evidence](docs/acceptance/mc09/README.md)
- [MC10 reality audit](docs/MC10-REALITY-AUDIT.md)
- [MC10 workflow contract](docs/MC10-WORKFLOW-CONTRACT.md)
- [MC10 acceptance report](docs/acceptance/MC10-REPORT.md)
- [MC10 browser/runtime evidence](docs/acceptance/mc10/README.md)
- [First-release acceptance report](docs/acceptance/REPORT.md)
- [First-release final engineering report](docs/acceptance/FINAL-ENGINEERING-REPORT.md)
- [UI smoke evidence](docs/acceptance/UI-SMOKE.md)
