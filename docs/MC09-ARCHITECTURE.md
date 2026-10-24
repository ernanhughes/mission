# MC09 - unified application interface architecture

## Principle

Mission Control is the human interface and coordination layer. Next, Work and
CoCoder remain independent engines and own their domain data. Mission Control
absorbs workflows, not source code or algorithms.

```text
                    MISSION CONTROL
   Search · Inbox · Decisions · Actions · Project context · History
             |                |                 |
        mc09.1 adapter    mc09.1 adapter    mc09.1 adapter
             |                |                 |
           Next             Work             CoCoder
      research store   opportunity CLI    review artifacts
```

No application codebase, database schema or business rule was merged into
Mission Control. Movies is out of scope.

## Adapter protocol (`mc09.1`)

Implemented in `backend/mission_control/adapters/base.py`.

An adapter declares:

- `capabilities`: health, list/get/search resources, list/validate/execute
  actions, execution status, cancellation, events. Not every adapter implements
  every capability.
- `actions`: registered `ActionSpec` records with stable ID, parameter schema,
  risk, side effect, approval requirement and an explicit enabled/unavailable
  reason.
- `refresh(target)`: returns availability, diagnostics, observations and typed
  resources.
- `validate_action(...)`: rejects invalid parameters synchronously.
- `execute_action(...)`: runs only a registered action with an explicit context.

### Resource envelope

Every resource has:

| Field | Purpose |
| --- | --- |
| `resource_type` | Application-specific type, e.g. `next_opportunity` |
| `external_id` | Stable source identity |
| `title`, `summary`, `state` | Presentation fields |
| `source_version` | Contract/artifact version |
| `source_timestamp` | Time claimed by the source |
| `observed_at` | Time Mission Control read it |
| `stale_after_seconds` | Freshness threshold |
| `evidence` | Source references or paths |
| `data` | Full typed payload for detail views |

Mission Control's persisted read model retains the original application ID,
resource type and external ID. It does not rewrite source state.

## Integration methods

| Application | Method | Write behaviour |
| --- | --- | --- |
| Next | Read-only PostgreSQL session, SELECT only; SQLite fallback | No writes |
| Work | Documented JSON CLI (`work opportunities --json`) | No writes |
| CoCoder | CLI JSON artifact plus registered review action | Writes only its own artifacts/state under Mission Control data |

### Next

- Connection uses `NEXT_DSN` by name; the value is never stored or returned.
- `default_transaction_read_only=on` is set on the PostgreSQL session.
- The adapter does not instantiate Next's `ResearchStore`, because that
  constructor runs migrations.
- Reads are bounded: 200 opportunities by default (max 500), 20 runs, 50 evidence
  gaps, 50 experiments, up to 500 source item references.
- SQLite fallback opens the file in `mode=ro`.

### Work

- Executable and arguments are configuration, validated as a native executable
  and structured argument list. No shell is used.
- Environment is allowlisted; only configured names such as
  `WORK_DATABASE_URL` are inherited.
- UTF-8 is forced so Windows code pages cannot corrupt JSON.
- The output root must be a JSON list; malformed output is an unavailable
  integration, not fabricated data.

### CoCoder

- Artifacts are read from Mission Control's data directory or explicitly
  configured files.
- The review action validates a registered repository, Git refs and timeout.
- CoCoder is launched with an explicit `--config` that redirects its SQLite and
  artifact directories under `data/integrations/cocoder/engine`. This config
  uses CoCoder defaults apart from `[cqrs]`; repository-local CoCoder config is
  not merged in this release.
- Review output is written under `data/integrations/cocoder/review-*.json` with a
  sidecar metadata file recording repository, base, head and intent.
- Review does not modify tracked source files. Acknowledging a finding is not
  code verification.

## Persistence

Migration `002_integration_foundation.sql` adds three tables.

### `integration_records`

Current and historical cached resources. Unique on
`(application_id, resource_type, external_id)`. Includes project association,
source version/timestamp, observation time, staleness, evidence, full JSON data,
a searchable text projection and a `current` flag. A refresh marks the previous
snapshot historical and upserts the new one.

### `integration_decisions`

Append-only human decisions with application/resource identity, reason,
`sync_state` (currently always `local_only`), prior decision reference and time.
Recording a decision also writes a normal Mission Control decision and activity
event, preserving one human history across the product.

### `integration_executions`

Full action lifecycle: queued, running, succeeded or failed; risk, approval,
timestamps, exit code, bounded output, structured result, artifact reference and
error. An action is never displayed as complete while queued. On shutdown,
unfinished executions are marked failed with an explicit reason.

## Controlled actions

| Classification | Example | Approval |
| --- | --- | --- |
| Read-only inspection | Refresh a read model | Not needed for safe reads |
| Bounded local computation | CoCoder review | Explicit confirmation |
| Local state modification | Local decision/association | Deliberate UI action |
| Repository modification | None implemented | N/A |
| External communication | None implemented | N/A |
| Publishing/irreversible | None implemented | N/A |

Guards:

- The browser sends an action ID and typed parameters, never a command line.
- The action must be registered by the adapter and enabled.
- Parameter schema rejects unknown fields and type/range violations.
- Adapter-level validation rejects unregistered repository paths and unsafe refs
  before queueing.
- `confirm=true` is required for actions with approval requirements.
- Only one queued/running execution of the same action per application is
  allowed.
- The execution context contains only registered repository paths, Mission
  Control's data directory and an allowlisted environment.

Not implemented: explicit cancellation, streaming logs, idempotency keys. These
are MC10 candidates. Shutdown is the only current cancellation path.

## API surface

All routes are under `/api`:

```text
GET    /integrations
GET    /integrations/{application_id}
PATCH  /integrations/{application_id}
POST   /integrations/{application_id}/test
POST   /integrations/{application_id}/refresh

GET    /integrations/{application_id}/resources
GET    /integrations/{application_id}/resources/{record_id}
PATCH  /integrations/{application_id}/resources/{record_id}
POST   /integrations/{application_id}/resources/{record_id}/decision
GET    /integrations/{application_id}/decisions

POST   /integrations/{application_id}/actions/{action_id}/execute
GET    /integrations/executions
GET    /integrations/executions/{execution_id}

GET    /inbox
GET    /search?q=...
GET    /projects/{project_id}/integration-context
```

State-changing browser requests require the existing local-origin guard and
`X-Mission-Control-Request: 1`.

## Frontend

| Route | Purpose |
| --- | --- |
| `/next` | Overview, candidates, recommendations, experiments, evidence gaps, decisions, operations |
| `/work` | Overview, opportunities, qualifications, pursuits, results, decisions, operations |
| `/cocoder` | Overview, repositories, assessments, findings, decisions, operations |
| `/inbox` | Unified items from Next, Work, CoCoder and Mission Control tasks |
| `/search` | Federated search across application resources, projects, repositories, tasks, checkpoints and decisions |
| `/integrations` | Diagnostics, configuration, connection tests, capabilities and actions |
| `/projects/:id` | Existing project workspace plus cross-application context |
| any page | `Ctrl+K` command palette: navigation, project shortcuts, available refresh commands and federated search |

The workspaces distinguish:

- source state vs Mission Control decision;
- cached observation time vs source timestamp;
- stale observations;
- unavailable integrations with the actual diagnostic;
- listed compensation vs realised income (Work results remain empty rather than
  inferred);
- finding severity/confidence vs human acknowledgement.

## Unified inbox

The inbox is a normalised read model over current integration records plus open
Mission Control tasks. It preserves `source_application`, source name, external
identity and a deep link. Filters: application, project and priority. Items that
already have a local decision are removed from the pending queue. Per-source
caps prevent one noisy engine from hiding the others. Titles are never merged
across sources.

## Search

Federated SQL text search over:

- current integration resources (title, summary, state, JSON payload);
- projects and repositories;
- tasks, checkpoints and decisions.

Results preserve source attribution and route directly to the relevant
workspace/detail. No vector database was introduced.

## Shared project context

Integration records can be associated with a project. The project detail page
loads `/api/projects/{id}/integration-context` and displays source records with
freshness and local decision state. Source systems remain authoritative; only
the association is stored by Mission Control.

## Failure isolation and freshness

- An adapter failure returns an unavailable status and diagnostic; it does not
  raise through the dashboard.
- Other applications remain usable when one is unavailable.
- Adapter refreshes have a 30-second service timeout; Work and CoCoder commands
  have their own bounded timeouts.
- Expensive work is never polled. CoCoder review is an explicit action; the UI
  polls only its execution record while it runs.
- Records carry an observation timestamp and stale-after threshold. The UI marks
  stale records rather than implying live freshness.
- Refresh is explicit or triggered after a successful action, not on a fast
  dashboard interval.

## Security model

- Loopback binding and existing origin/security headers remain.
- No shell, no arbitrary executable and no browser-supplied arguments.
- Integration executables must be native; `.cmd`, `.bat` and `.ps1` are rejected.
- CoCoder repository selection is validated against the registry; paths outside
  the allowlist return 422 before queueing.
- CoCoder Git refs are validated against a restricted character set.
- Secret-like configuration keys are removed from API responses; the frontend
  applies the same filter defensively.
- Environment variable values for DSNs are never persisted, returned or logged.
- No automatic repository modification, job application, outreach, publishing or
  spending exists.

See [MC09-INTEGRATION-AUDIT.md](MC09-INTEGRATION-AUDIT.md) for source contracts
and [acceptance/MC09-REPORT.md](acceptance/MC09-REPORT.md) for verification.
