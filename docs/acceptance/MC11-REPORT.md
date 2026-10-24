# MC11 - acceptance and engineering report

## Recommendation

**ADOPT for bounded local experiments; REFINE before broadening.**

MC11 meets the execution-integrity, two-template, Language-observation and
project-evidence gates for the two registered sandboxes. It does not establish
Worker Work/Acceptance parity, arbitrary-repository safety, or general
productivity. Broader execution should remain disabled until those refinements
are addressed.

## Summary

MC11 hardens the MC10 workflow and generalises it:

- generated code runs in a real Docker sandbox, not the host;
- retries are anchored to tagged baselines and preserve result commits;
- duplicate execute and cancellation states are explicit and durable;
- a second, structurally different brightness template executes successfully;
- `language.intention.v0` is unchanged;
- `language.observation.v1` records expected/observed properties without
  controlling execution;
- a project evidence timeline connects workflows, observations and decisions.

## Repository state

| Item | State |
| --- | --- |
| Mission Control | `C:\Projects\mission`, branch `main` |
| MC10 reported baseline | `43caf94` |
| MC11 implementation commit | `e6555d5` (`Implement MC11 hardened experiments and Language observations`) |
| Acceptance evidence commit | this documentation/evidence commit; hash in the final delivery note |
| Next | `main` at `491b501`, clean; no MC11 source change |
| Worker | `main` at `0aecefa`, 33 pre-existing changes preserved |
| CoCoder | `cc-r06-p0-codeai-qualification` at `f4e90d6`, 36 pre-existing changes preserved |
| Work | `main` at `e79e68c`, 1 pre-existing change preserved |
| Push | **none** |
| Paid inference | none |

## Real results

### TraceLite reproducibility

| Field | Value |
| --- | --- |
| Workflow | `wf-94ab93391db64780` |
| Template | `trace_reduce_v1` 1.0 |
| Baseline | `ca5dfb3` — 21 events, 2 failing tests |
| Result | `ce7e5271d3187901984afd75d6c3c21f0cadc308` |
| Measurement | 21 → 3 events; 85.7% reduction; tests pass |
| Worker | `direct` / `qwen2.5-coder:latest`; `AWAITING_ACCEPTANCE` |
| CoCoder | 1 file, 0 findings |
| Language | `reduced_event_count` expected 3, observed 3, pass |
| Decision | accept (browser) |
| Sandbox | Docker, network none, repo read-only, 512 MB memory, 0.5 CPU |

The original MC10 accepted workflow `wf-72d32f9abfaa4144` remains intact.

### Brightness template

| Field | Value |
| --- | --- |
| Workflow | `wf-e88029132bc24f28` |
| Template | `brightness_observation_v1` 1.0 |
| Source | local synthetic `mc11.fixture-evidence.v1` |
| Baseline | `8f997f4` — 0,0,0 observed |
| Result | `8b3b978c29e5ae7d973abeb63718352b57b426a5` |
| Expected | means `[0,128,255]`, max `[0,128,255]`, monotonic |
| Observed | means `[0,128,255]`, max `[0,128,255]`, monotonic |
| Tests | pass |
| CoCoder | 1 file, 0 findings |
| Language | three properties, all constraint pass |
| Decision | accept (browser) |
| Sandbox | same Docker boundary |

This is structurally different from TraceLite: a local fixture manifest, a
different file/entrypoint, a different measurement shape and different
Language properties.

### Cancellation

Workflow `wf-aad909c4b5b34806` was created through the browser and cancelled
before execution. It records status `cancelled`, `cancel_requested=true`,
`cancelled_at`, four timeline events and no Worker result. A unit test also
cancels during a slow Worker call and verifies the patch is not applied.

### Project evidence

Project `mc11-experiments` contains:

- the accepted MC10 TraceLite workflow;
- the reproducible MC11 TraceLite workflow;
- the accepted brightness workflow;
- the cancelled brightness attempt, preserved as failure evidence;
- two `language.observation.v1` records;
- the human decision entries.

`GET /api/projects/mc11-experiments/evidence-timeline` returns 4 workflows and
2 observations.

## Tests and evidence

| Check | Result |
| --- | --- |
| Mission Control backend | **58 passed** |
| Mission Control frontend | **26 passed** |
| Production build | passed |
| Ruff | passed |
| Next export contract | 2 passed |
| Worker gateway | 210 passed, 8 skipped, 0 failed |
| Docker sandbox test | passed (read-only, no-network, limits) |
| Browser E2E | **5 steps passed**, 0 console/page errors |
| Worker `opencode-work` evaluation | BLOCKED by 403 FreeTierError |
| Paid inference | none |

Browser steps:

1. two templates visible;
2. brightness review and human acceptance;
3. TraceLite review and human acceptance;
4. project evidence timeline;
5. cancellation in the UI.

Evidence:

- [Backend tests](backend-tests-mc11.txt)
- [Frontend tests](frontend-tests-mc11.txt)
- [Frontend build](frontend-build-mc11.txt)
- [Ruff](ruff-mc11.txt)
- [Next export tests](next-export-tests-mc11.txt)
- [Worker gateway tests](worker-gateway-tests-mc11.txt)
- [Docker sandbox test](docker-sandbox-test-mc11.txt)
- [Browser E2E](mc11/browser-e2e.json)
- [Runtime state](mc11/runtime-state.json)
- [Worker executor evaluation](mc11/worker-executor-evaluation.json)
- [Source repository state](mc11/source-repositories.txt)

## Docker isolation

Image: `mission-control/sandbox-python:3.13`, built from
`docker/sandbox/Dockerfile` with Python 3.13 and pinned pytest 8.4.2.

Per execution:

```text
--network none
--read-only
--tmpfs /tmp:rw,noexec,nosuid,size=64m
--cap-drop ALL
--security-opt no-new-privileges
--memory 512m --memory-swap 512m
--cpus 0.5 --pids-limit 64
--user 65534:65534
-v <sandbox>:/work:ro
```

The generated file is AST/scope-validated on the host and written only to the
approved path; it is executed only in the container under a host timeout. If the
Docker daemon or image is unavailable, workflow creation fails rather than
falling back to host execution.

## Worker evaluation

`opencode-work` with `review_mimo_free` and
`improvement.strengthen.acceptance_free` returned `BLOCKED`:

```text
MODEL_RUNTIME_BLOCKED: permission_denied: 403: FreeTierError
OpenCode's free tier can only be used from within OpenCode.
```

No verified local/free `opencode-work` route was available. The `direct`
executor with local Ollama was retained. Its results stay
`AWAITING_ACCEPTANCE`; no Work Evidence, Verify, Proof or Acceptance identity is
fabricated. This is the main REFINE item.

## Acceptance gates

| # | Gate | Result |
| --- | --- | --- |
| 1 | MC10 TraceLite remains reproducible | **Pass** — new `wf-94ab...` accepted |
| 2 | Approved operation cannot execute against a changed baseline | **Pass** — stale HEAD/file tests |
| 3 | Cancellation and retries preserve truthful state | **Pass** — cancellation UI/unit; baseline tags; duplicate guard |
| 4 | Generated-code isolation meets documented threat model before broader execution | **Pass for the two dedicated sandboxes**; broad execution remains disabled |
| 5 | Two distinct templates execute successfully | **Pass** — TraceLite + brightness |
| 6 | Research/execution/test/review provenance connected | **Pass** — 15-event timelines, source refs, project timeline |
| 7 | Language Level 0 behaviorally unchanged | **Pass** — v0 preserved; tests assert it |
| 8 | Language Level 1 reports real observations without controlling execution | **Pass** — `language.observation.v1`, no execution path |
| 9 | Unsupported Worker acceptance never fabricated | **Pass** — direct stays `AWAITING_ACCEPTANCE` |
| 10 | Browser acceptance and failure-injection tests pass | **Pass** — browser 5 steps, cancellation, stale/scope/duplicate tests |
| 11 | Existing Worker/CoCoder/Work dirty states preserved | **Pass** — 33/36/1 unchanged |
| 12 | No code pushed or external inference purchased | **Pass** — no push, local Ollama only |

## Performance and cost

| Measurement | Result |
| --- | --- |
| Docker sandbox image | local `mission-control/sandbox-python:3.13` |
| Docker sandbox test | ~1 s in this environment |
| TraceLite workflow | 89.8 s (first local model call after cold start) |
| Brightness workflow | 15.0 s |
| CoCoder review | 1 file, 0 findings, ~10 s |
| Paid inference | none; local Ollama |
| External network during generated tests | none |

The 89.8 s TraceLite time includes local model inference and Docker/model warm-up;
it is not a productivity measurement.

## Changed files (Mission Control)

- migration `004_execution_integrity.sql` — cancellation, Language observations.
- `workflows/sandbox.py` — Docker boundary.
- `workflows/templates.py` — versioned template registry.
- `workflows/service.py` — template dispatch, Docker execution, cancellation,
  idempotency, Language observations, project timeline.
- `api/workflows.py` — cancel/project/events/timeline endpoints.
- `models.py`, `schemas.py` — cancel and observation records.
- Workflow UI, project evidence timeline, template creation button.
- `docker/sandbox/Dockerfile`.
- Tests for Docker, templates, cancellation, stale approval, duplicate execute,
  adverse review, Language observations.

## Honest limitations

- Worker `opencode-work`/Work Acceptance parity is not achieved.
- Docker Desktop is an operational dependency; the daemon is a trust boundary.
- Generated code executes only in the two dedicated sandboxes; arbitrary project
  repositories are not enabled.
- One local model (`qwen2.5-coder:latest`) and one fixture for the second template.
- Cancellation is cooperative; it is observed at safe boundaries rather than
  forcibly terminating a model call.
- The UI execute request is synchronous; durable events exist but are polled
  after the operation returns. Streaming Worker events are not implemented.
- Language Level 1 is an observation contract only; no interpretation,
  negotiation or corrective execution exists.
- Project association is local and additive; no source application is modified.
- Work write-back, Writer, Movies production and autonomous publishing remain
  out of scope.

## Proposed next steps

1. Evaluate a verified local `opencode-work`/Work-Acceptance route; only then
   replace `direct`.
2. Add asynchronous execution/cancellation with event streaming and explicit
   cancellation acknowledgement from Worker.
3. Add more registered templates and repositories, with per-template threat
   models.
4. Add a template schema/API so conventional templates can be registered without
   code changes (while still validating scope/commands server-side).
5. Harden the Docker host: image signature/digest pinning, daemon health and
   resource monitoring.
6. Expand project evidence to include related Next findings, CoCoder findings
   and Work decisions in one query.
7. Keep Language v1 read-only; experiment with interpretation only after the
   observation contract has multiple domains.

## Reproduce

```powershell
# Docker sandbox image
docker build -t mission-control/sandbox-python:3.13 `
  -f docker\sandbox\Dockerfile docker\sandbox

# Mission Control
.\scripts\start.ps1

# Worker direct local executor
$env:WORKER_CONFIG='C:\Projects\mission\data\integrations\worker\worker-config.json'
bun src/cli/cli.ts serve   # from C:\Projects\worker

# Tests
.venv\Scripts\python.exe -m pytest -q
cd frontend; npm test; npm run build; cd ..
```

Accepted workflows remain inspectable at:

- `/workflows/wf-94ab93391db64780` — TraceLite
- `/workflows/wf-e88029132bc24f28` — brightness
- `/workflows/wf-72d32f9abfaa4144` — preserved MC10 accepted workflow
- `/projects/mc11-experiments` — project evidence timeline
