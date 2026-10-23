# Mission Control architecture

## Position in the ecosystem

Mission Control is a coordination and presentation layer, not a replacement for Next, CoCoder, Work, Writer, Improve, BookBuilder, Worker, Stephanie or Workbench.

```text
               +---------------------------------------------+
               |              Mission Control                |
               |  Today · Projects · Books · Applications    |
               |  Activity · Settings · Briefing              |
               +----------------------+----------------------+
                                      |
        +-----------------------------+-----------------------------+
        |                             |                             |
  Registry + SQLite          Read-only adapters            Process control
  priorities, checkpoints,   Next snapshot · CoCoder       detached Windows
  tasks, decisions,          artifacts · Math report       processes, logs,
  observations, settings     Language/Inference files      health, ownership
        |                     Worker /health                |
        |                             |                      |
        +-----------------------------+-----------------------------+
                                      |
             Existing local systems, repositories and books
             (never imported or modified by Mission Control)
```

The key boundary: **Mission Control decides what should be presented and coordinated; the existing systems keep doing their own work.**

## Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, SQLite, PyYAML, httpx, psutil.
- **Frontend:** React 19, TypeScript, Vite, React Router, custom CSS, Lucide icons.
- **Persistence:** SQLite at `data/mission_control.db`; versioned SQL migrations in `backend/mission_control/persistence/migrations/`.
- **Packaging:** one local process serves the built SPA and API on `127.0.0.1:8790`. Vite runs separately only in development.

No Docker, hosted database, cloud service or message broker is required.

## Implemented structure

```text
mission/
  backend/
    mission_control/
      api/              FastAPI routers by resource
      adapters/         read-only integration framework + real adapters
      activity/         activity recording and dedupe
      briefing/         deterministic + optional AI briefing
      core/             paths, errors, security, logging, Git, editor
      discovery/        bounded scanner, classifier, background service
      persistence/      database, migration runner, seed loader, SQL
      processes/        managed Windows process lifecycle, health probes
      projects/         projects, books, continuity, reviews, activity
      registry/         application CRUD, status, capability actions
      settings/         validated settings and roots
      config.py         runtime paths/environment
      main.py           application factory and lifespan
      models.py         SQLAlchemy models
      schemas.py        Pydantic request/response contracts
    tests/              backend, integration and security tests
  frontend/
    src/
      api/              typed local API client + query hook
      app/              routes
      components/       layout, modal, toast, theme, accessible UI
      features/         application cards and registry form
      pages/            Today, Projects, Books, Applications, Activity, Settings
      test/             Vitest fixtures and UI tests
      types/            API contracts
  config/defaults/      shipped YAML defaults
  docs/                 inventory, integration map, architecture, milestones, acceptance
  scripts/              setup, start, dev, stop, test, repo-state capture
```

The brief allowed adaptation. The structure keeps the same concerns but avoids empty abstraction layers.

## Backend request flow

```text
Browser / local client
   |
   | Origin + X-Mission-Control-Request on mutations
   v
FastAPI middleware: origin guard, security headers, CORS
   |
   v
Routers (typed Pydantic contracts)
   |
   +--> Registry service ----------> ApplicationRead with computed status/actions
   +--> Project service -----------> ProjectDetail, books, checkpoints, tasks
   +--> Process Manager -----------> detached child, log, lifecycle, health
   +--> Discovery Service ---------> background thread scan, persisted repositories
   +--> Adapter Service -----------> isolated refresh, observations, recommendations
   +--> Briefing service ----------> grounded items + optional provider call
   |
   v
SQLAlchemy / SQLite + filesystem logs
```

Nothing in this path executes a browser-supplied executable. The launch endpoint reads a stored launch definition and passes only its structured fields to the process manager.

## Persistence model

Core tables:

| Table | Purpose |
| --- | --- |
| `applications` | User-editable application identity, paths, relationships, adapter config, control policy |
| `launch_definitions` | Named, structured launch/monitoring definitions; enabled and verified separately |
| `process_instances` | Managed or externally observed process records; PID, creation time, status, exit code, log path |
| `health_observations` | Timestamped probe results with source and freshness |
| `projects` | Bodies of work with priority, pin, milestone, next action |
| `books` | Book workspaces linked one-to-one to a project |
| `outcomes` | Publishing/product/business destinations |
| `repositories` | Filesystem-backed repositories and discovery metadata |
| `project_repositories` | Project ↔ repository many-to-many with role |
| `project_relationships` | Typed project associations (outcomes etc.) |
| `activity_events` | Normalised timeline with source, provenance, evidence, dedupe key |
| `work_checkpoints` | Persisted work summaries and next actions |
| `tasks` | Explicit user actions |
| `recommendations` | Reviewable proposals with provenance and evidence |
| `decisions` | Accepted/deferred/rejected/revised human choices |
| `adapter_statuses` | Availability, capabilities, diagnostics, freshness per adapter target |
| `settings` | Validated non-secret configuration |
| `discovery_roots` | Editable bounded scan roots |
| `briefings` | Generated deterministic/AI-assisted briefings and their evidence |

Repositories and applications have stable IDs; filesystem paths are not primary keys. An application may relate to multiple repositories, projects, books and outcomes.

### Migrations

Migrations are numbered SQL files applied once and recorded in `schema_migrations`. The runner is deliberately explicit and tested for repeatability. This avoids hidden create-all drift while keeping the first release small.

### Configuration precedence

```text
shipped defaults (only if ID absent)
        ↓
discovered repository metadata
        ↓
user edits in SQLite (always authoritative)
```

Discovery updates repository observation fields. It never changes priority, pinned state, application names, launch definitions or notes.

## Application status and action computation

The registry service computes presentation and capabilities from persisted state:

- Inputs: enabled launch definitions, latest owned process, latest health observation, last launch success/failure, repository existence, editor configuration.
- Outputs: a typed status (running, external, stopped, unavailable, misconfigured, not checked, stale, launch failed) and per-action enablement with a reason.
- The UI never enables a launch because a folder exists. It requires an enabled launch definition.
- Health probes only run for **enabled** definitions. A responding port produces an external observation, not ownership.
- Disabled actions display a reason in a "Why some actions are unavailable" disclosure.

This keeps the frontend honest: buttons reflect backend capability, not optimistic assumptions.

## Windows process model

Mission Control initially used `asyncio.create_subprocess_exec`, but acceptance exposed a Windows-specific lifecycle bug: asyncio's subprocess transport kills its child when the event loop closes. That would prevent backend restart reattachment.

The implemented model:

1. Validate registry definition: native executable, arguments array, working directory, allowed env names.
2. Check duplicate ownership, process limit and port conflict.
3. Start a detached native `subprocess.Popen` with:
   - `shell=False`
   - `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` on Windows
   - stdout/stderr redirected to a per-process log file
   - stdin `DEVNULL`
   - a minimal allowlisted environment plus explicitly named variables
4. Record PID + psutil creation time; monitor via non-blocking polling.
5. Stop only owned records whose PID and creation time still match; terminate children recursively with psutil.
6. On restart, reattach if the process identity still matches; otherwise mark it lost and never kill a guessed PID.

A child launched from a launcher wrapper that immediately exits can be reported as lost even if its grandchild remains. Users should point to the native long-lived executable. This is documented as a limitation.

## Security design

- Loopback-only binding; the app refuses non-local host startup.
- Origin guard for unsafe methods: allowlisted local origin plus `X-Mission-Control-Request: 1`.
- Security headers including CSP; a relaxed CSP only for Swagger docs.
- No shell execution, no arbitrary executable from browser payloads.
- Path validation rejects relative paths, traversal and device paths.
- Only named environment variables are copied; no broad credential inheritance.
- Stop requires ownership, PID and creation-time match.
- Logs are redacted for API keys, bearer tokens and password/token assignments.
- API keys are never stored or returned; only an environment variable name is config.
- External publishing, repository mutation, model spend and destructive actions are not automated.

See [SECURITY.md](SECURITY.md).

## Discovery

- Roots are configured and editable.
- Immediate children default depth 1, bounded by count and time.
- Exclusions cover generated/build/editor/cache directories and configurable patterns.
- Symlinks/junctions are skipped; inaccessible paths are recorded, not fatal.
- Git observation uses read-only commands with timeouts.
- Scans run asynchronously; status can be polled and cancelled.
- Candidates are persisted with classification, confidence and evidence.
- Classification is advisory; it never creates an application or launch automatically.

## Adapters

An adapter accepts a target (application or project), repository/documentation paths, and JSON config. It returns:

- availability;
- capability names;
- observation list (title, detail, external id, evidence, provenance, time);
- recommendation seeds;
- diagnostics/error.

The service adds timeout/error isolation, persists status, deduplicates observations using a source key, and creates recommendations only when new. Adapter failure never crashes the dashboard.

Initial adapters:

- Language manuscript evidence.
- Inference manuscript/status claim.
- Math MATH01 evidence and derived obligations.
- Next local SQLite snapshot.
- CoCoder configured review artifact.
- Worker health.
- Work reports a blocked contract rather than inventing records.

## Daily briefing and provenance

Deterministic briefing:
1. Reads user priority projects, latest checkpoints, tasks, pending recommendations and adapter availability.
2. Produces ranked items with explicit provenance: recorded checkpoint, user priority/task, external claim, derived observation.
3. Saves a briefing record; no AI is required.

Optional AI:
- Explicit `use_ai` request; requires configured provider + consent.
- Model receives only the grounded items; prompt forbids invented facts and replacing human decisions.
- Response is parsed as JSON; only valid items are appended after the deterministic items, tagged `ai_recommendation`.
- Any timeout, HTTP error or invalid response retains the deterministic briefing and reports the failure.
- API keys stay in the environment and are never sent to the frontend or stored.

## Frontend architecture

- Typed API client adds the local-request header to mutations and normalises errors.
- `useApi` handles loading, errors, polling and abort on navigation.
- Pages:
  - **Today** assembles priority, focus, resume, reviews, books, apps, briefing, activity, outcomes.
  - **Projects** filters/pins/reorders and opens a workspace.
  - **Project workspace** handles checkpoint, tasks, decisions, recommendations, adapters, Git, outcome relationships.
  - **Applications** supports registry CRUD, launch/stop/restart, logs and full launch configuration.
  - **Books** is a first-class three-book workspace with explicit user status.
  - **Activity** filters and differentiates provenance.
  - **Settings** covers discovery roots/exclusions, editor/browser, limits, adapters, AI, startup profile and retention.
- Accessibility: semantic headings, keyboard focus in dialogs, focus-visible outlines, labels, disabled reasons, responsive layout, light/dark themes, reduced-motion support.
- No hardcoded dashboard data; every page uses the API.

## Reliability

- Background discovery and adapter refresh; dashboard remains available if they fail.
- Timeouts around external commands, health probes and adapters.
- Process states are reconciled on read/startup to avoid stale "running" records.
- SQLite foreign keys enabled; explicit migrations.
- Logs rotate; secrets redacted.
- No routine Git fetch or heavyweight repository scan.
- No dependency installation in other projects.
- `page`/network errors surface with retry actions rather than frozen screens.

## Deliberate omissions

- No global knowledge graph, autonomous planner, universal workflow language or chatbot controlling all tools.
- No cross-repository write operations.
- No publishing action or paid model call.
- No full conversation capture from other applications.
- No Work/Writer/Improve/Stephanie adapters because no verified read-only contract was available.

These are future extensions, not reasons to fake capability.
