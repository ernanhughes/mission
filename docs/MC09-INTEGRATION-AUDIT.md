# MC09 - integration audit

Captured: 2026-10-24

Scope: Mission Control, Next, Work and CoCoder. Movies is explicitly out of scope.
No source repository was modified. Inspection used read-only commands, the
documented CLIs, read-only SQLite access and a SELECT-only PostgreSQL session.

## Baseline

| Check | Result |
| --- | --- |
| Mission Control repository | `C:\Projects\mission`, branch `main` |
| Baseline commit at audit start | `c589bd2` |
| Existing backend suite | 43 passed |
| Existing frontend suite | 9 passed |
| Live service | `http://127.0.0.1:8790` |
| SQLite runtime data | `data/mission_control.db` |
| Windows launcher/reattachment | preserved; existing tests passed before MC09 changes |

The first-release features were preserved: application registry, Windows process
launch/stop/reattachment, discovery, projects, books, checkpoints, tasks,
decisions, activity, adapters and optional AI briefing.

## Capability matrix

Ratings use the requested scale: 1 discover, 2 observe, 3 interact, 4 operate,
5 coordinate. "MC09" is the state delivered by this milestone.

| Application | Native contract | Before MC09 | MC09 target | Delivered |
| --- | --- | --- | --- | --- |
| Next | PostgreSQL/SQLite research store; HTML web dashboard; CLI | Level 1-2 via stale SQLite snapshot | Level 2-3, safe operation where available | **Level 3** - live read-only PostgreSQL, searchable candidates/evidence, local decisions, project association. Discovery operation remains blocked. |
| Work | `work opportunities --json`; `work decide` writes PostgreSQL | Level 1; adapter blocked | Level 2-3 | **Level 3** - live opportunity JSON, qualification/pursuit views, local decisions. Source decision sync remains blocked. |
| CoCoder | `cocoder review --format json --output`; schema `0.2` artifact | Level 2 via manually configured artifact | Level 2-4 | **Level 4** - real review action, execution lifecycle, findings/detail, local dispositions. |

## Next

### Verified sources

- Repository: `C:\Projects\next`, branch `main`, HEAD `cbacf17`, clean.
- The research store supports SQLite and PostgreSQL (`next/db.py`,
  `next/store.py`). The configured `NEXT_DSN` reaches database `next`.
- Live read-only snapshot at audit time:
  - 130 opportunities
  - 567 items
  - 12 discovery runs
  - 130 decision records
  - 31 evidence-gap records
- The web layer (`next/web.py`) serves HTML pages and a JSON `/health` endpoint.
  It does **not** expose JSON resources for opportunities, runs or evidence.
- `ResearchStore.__init__` executes schema creation and migrations. It is not a
  safe read contract for a read-only consumer.

### Chosen contract

Mission Control reads PostgreSQL with a session-level read-only transaction
(`default_transaction_read_only=on`) and SELECT statements only. It never
constructs `ResearchStore`, never writes, and never falls back to invented data.
The existing SQLite file remains an explicit fallback when `NEXT_DSN` is absent.

Opportunity data includes source item titles/URLs, score dimensions, queue type,
research status, evidence gaps, source decision history and item metadata.
No scores or rankings are invented by Mission Control.

### Missing source contract

The smallest contract that would remove the database compatibility dependency is
a versioned, read-only export:

```text
GET /api/export/v1/research
  ?cursor=<opaque>&limit=<1..500>

{
  "schema": "next-research-export-v1",
  "generated_at": "<ISO-8601>",
  "items": [ ... ],
  "opportunities": [ ... ],
  "runs": [ ... ],
  "evidence_gaps": [ ... ],
  "next_cursor": "<opaque|null>"
}
```

Minimum fields: stable IDs, title, source/URL, discovered timestamp, mechanism,
scores and evaluation basis, status, evidence references, run status and gap
records. The contract should be read-only and versioned. No Next source change
was made or authorised.

### Actions

`run_discovery` is registered but disabled. It would fetch the network, call
models and write Next's authoritative store. No reviewed bounded operation
contract exists, so Mission Control points users to Next's own interface.

## Work

### Verified sources

- Repository: `C:\Projects\work`, branch `main`, HEAD `e79e68c`.
- Pre-existing modification: `M work/dashboard.py` (one changed path before and
  after inspection; Mission Control did not touch it).
- `work opportunities --json` returns a JSON list; the live run produced 130
  opportunities (about 1.09 MB), of which 63 are qualified by Work's recorded
  `commercial-v3` / `track-aware-v3` policy.
- Each record contains `id`, `state`, `observation` and `qualification`.
  Observation includes source URL, buyer, title, track, compensation, location
  fields, evidence URLs and timestamps. Qualification includes qualified flag,
  score, bucket, blockers, unknowns, evidence mode and next action.
- `work decide` exists but writes Work's authoritative PostgreSQL state. It was
  not invoked.

### Chosen contract

The documented CLI JSON is the integration contract. Mission Control executes
only the configured `opportunities --json` argument list with a bounded timeout,
UTF-8 output, no shell, an allowlisted environment and a fixed working directory.
The full 130-record export is ingested; UI lists are paginated by the API.

### Missing source contract

A stable read-only HTTP endpoint or a documented CLI version marker would make
the adapter less sensitive to CLI changes. A write contract is required before
source synchronisation of decisions:

```text
POST /api/export/v1/decisions
{
  "schema": "work-decision-v1",
  "opportunity_id": "...",
  "decision": "shortlist|defer|reject|investigate",
  "reason": "...",
  "idempotency_key": "..."
}
```

Until that is reviewed and approved, all Work decisions are stored by Mission
Control with `sync_state=local_only` and never claim a Work update.

### Actions

`sync_decision` is registered but disabled. No automatic applications, outreach
or spending exist.

## CoCoder

### Verified sources

- Repository: `C:\Projects\cocoder`, branch `cc-r06-p0-codeai-qualification`, HEAD
  `f4e90d6`.
- Pre-existing 36 changed paths; unchanged before and after MC09.
- `cocoder review --repo PATH --base REF --head REF --format json --output FILE`
  produces a schema `0.2` artifact with `findings`, `evidence`, `changed_files`,
  `change_shape`, `structural_analysis`, `unknowns` and limitations.
- Full Mission Control range `HEAD~2..HEAD`: 146 changed files, 478 findings,
  158.8 seconds, 714 KB artifact. Mission Control retains the first 400 findings
  per artifact to bound its read model.
- Small `HEAD~1..HEAD` verification: 5 changed files, 0 findings, 33.1 seconds.

### State isolation

CoCoder's `[cqrs] database` and `artifact_directory` default to paths under the
reviewed repository (`.cocoder/...`). Mission Control now writes an explicit
`cocoder-config.toml` under its own data directory and passes it with
`--config`, redirecting both to:

```text
data/integrations/cocoder/engine/cocoder.db
data/integrations/cocoder/engine/artifacts
```

The review output is written to `data/integrations/cocoder/review-*.json`. A
real review after this change created no `.cocoder` directory in the reviewed
repository.

Trade-off: the explicit config sets `[cqrs]` and otherwise uses CoCoder's
defaults. A repository-local `.cocoder/config.toml` is not merged for
Mission Control-launched reviews. Repositories that depend on custom CoCoder
configuration should be reviewed through CoCoder's own interface until a safe
config-merge contract exists.

### Actions

`run_review` is registered and enabled with:

- risk: `bounded_local_computation`
- side effect: `local_generated_artifacts`
- approval required: yes
- repository: must exactly match a registered repository path
- base/head: validated Git-ref syntax
- timeout: bounded to 10-300 seconds
- working directory: Mission Control's CoCoder data directory
- source state: CoCoder reads Git history; it does not modify tracked files

Invalid repositories, injected parameters and unconfirmed requests are rejected
before an execution is queued.

## Ownership boundaries

| Data | Authority | Mission Control role |
| --- | --- | --- |
| Next opportunities, runs, evidence | Next | Read-only cached read model with freshness |
| Work opportunities, qualification | Work | Read-only cached read model |
| Work decisions/outcomes | Work | Local Mission Control decisions, explicitly unsynchronised |
| CoCoder findings and artifacts | CoCoder | Artifact consumer; artifact path retained |
| CoCoder repository contents | Source repository | Never modified by the integration |
| Projects, tasks, checkpoints, associations | Mission Control | Authoritative local records |
| Action executions | Mission Control | Authoritative lifecycle for actions it launched |

## Read-only verification

- No source repository was fetched, reset, cleaned, checked out or written.
- Next: clean before and after.
- Work: one pre-existing modified file before and after.
- CoCoder: 36 pre-existing changed paths before and after.
- Mission Control's `.cocoder` directory generated during early probing was
  removed; the adapter now prevents it.
- `NEXT_DSN` and `WORK_DATABASE_URL` values were never printed or persisted.

## Decisions carried into implementation

1. Use read-only database access for Next, clearly labelled a compatibility
   integration rather than a stable API.
2. Use Work's documented JSON CLI; keep all decisions local.
3. Use CoCoder's JSON artifact and register one bounded review action.
4. Model all three as the same `mc09.1` adapter envelope while retaining source
   identity and application-specific detail.
5. Never merge source records merely because titles are similar.
6. Require explicit confirmation for actions with side effects.
7. Keep Movies out of scope.
