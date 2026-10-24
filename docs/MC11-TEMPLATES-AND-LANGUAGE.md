# MC11 - workflow templates, cancellation and Language observations

## Template contract

`backend/mission_control/workflows/templates.py` defines a small versioned
template registry. Each template declares:

- source kind and source contract;
- sandbox path, permitted file scope and test path;
- entrypoint function;
- worker algorithm/instructions;
- expected result, stop conditions and evaluation criteria;
- measurement success key;
- baseline/result tag family;
- review requirement;
- Human acceptance gates inherited from the workflow service.

Template definitions are code, not browser input. The browser may select a
registered template ID; it cannot provide a command, path or scope.

### Registered templates

| ID | Version | Source | Scope | Measurement |
| --- | --- | --- | --- | --- |
| `trace_reduce_v1` | 1.0 | `next-research-export-v1` | `tracelite/reduce.py` | 21 → 3 events; tests pass |
| `brightness_observation_v1` | 1.0 | `mc11.fixture-evidence.v1` | `brightness/analyze.py` | expected/observed means `[0,128,255]`, max `[0,128,255]`, monotonic |

TraceLite remains the first template. The brightness fixture is a structurally
different, fixture-based experiment. It observes a synthetic raw-grayscale
sequence; it does not touch production media or the Movies repository.

## Lifecycle

```text
proposed
  ├─ cancel → cancelled
  └─ approve (confirm + scope acknowledgement + hash/baseline checks)
       └─ approved
            ├─ cancel → cancelled
            └─ execute (confirm + active lock + stale checks)
                 ├─ cancelled at a safe boundary
                 ├─ failed
                 └─ executed
                      └─ review
                           ├─ cancelled
                           ├─ review_failed
                           └─ reviewed
                                └─ decide
                                     ├─ accept
                                     ├─ reject
                                     └─ investigate
```

`decided` is terminal. `cancelled` is terminal for that attempt. A new attempt
is created with `force_new=true`; the prior result commit is tagged before the
sandbox resets to the template baseline.

## Execution boundary

Generated code runs in Docker, never in the Mission Control process:

- repository mounted read-only at `/work`;
- read-only container root;
- no network;
- non-root UID/GID `65534:65534`;
- no Linux capabilities; `no-new-privileges`;
- 512 MB memory/swap, 0.5 CPU, 64 PID limit;
- 64 MB `tmpfs` at `/tmp`;
- host timeout and forced container removal on timeout.

The image is `mission-control/sandbox-python:3.13` from
`docker/sandbox/Dockerfile` (Python 3.13, pytest 8.4.2 pinned).

If Docker or the image is unavailable, workflow creation reports a validation
error and does not fall back to executing generated code on the host.

## Patch contract

- Exactly one approved path.
- Python AST validation.
- Imports rejected.
- Dunder attributes rejected.
- Dangerous calls rejected (`open` may be allowed only for the brightness
  read-only fixture, with a literal `r`/`rb` mode).
- Required entrypoint checked.
- `git diff --name-only` must exactly equal the approved scope.
- A scope violation restores the working tree and fails the attempt.

## Idempotency

- Replaying create for the same source/template returns the latest workflow.
- Replaying execute on a completed/cancelled workflow returns the stored identity.
- Replaying review returns the stored review execution/artifact.
- A concurrent duplicate execute is rejected by the in-process active guard.
- A different final decision on a decided workflow is rejected.
- New attempts require `force_new`; result commits are tagged before reset.

## Cancellation semantics

Cancellation is cooperative. It is observed:

- before Worker execution;
- after Worker response, before applying a patch;
- after measurement, before committing;
- before/after CoCoder review.

A cancelled workflow restores uncommitted sandbox changes and records a
`cancelled` event. It never claims that a running model call was stopped
mid-flight and never adopts a result.

## Language Level 0

`language.intention.v0` remains unchanged and is still stored in every workflow.
It contains the intent, constraints, scope, expected result and evaluation
criteria, but no inferred interpretation or negotiation.

## Language Level 1

`language.observation.v1` is emitted after deterministic measurement:

```json
{
  "schema": "language.observation.v1",
  "workflow_id": "...",
  "template": "...",
  "intention_ref": "workflow:<id>:language.intention.v0",
  "subject": "<source id>",
  "properties": [
    {
      "id": "reduced_event_count",
      "expected": 3,
      "observed": 3,
      "difference": 0,
      "within_constraint": true
    }
  ],
  "measurement_method": "python scripts/measure.py",
  "evidence": ["sandbox:...", "measurement:..."],
  "provenance": {"source_kind": "...", "source_contract": "...", "source_id": "..."},
  "uncertainty": ["..."],
  "constraint_result": "pass",
  "evaluation_version": "language.observation.v1"
}
```

The brightness template emits three properties: mean brightness, max brightness
and monotonic progression.

Observations:

- are stored in `language_observations`;
- never rewrite the intention, source evidence, review or decision;
- do not control execution;
- do not trigger corrections;
- are linked to the workflow and project evidence timeline.

## Project evidence timeline

`GET /api/projects/{project_id}/evidence-timeline` returns:

- workflows associated with the project;
- their full timelines and observations;
- language observations in a flattened list.

`PATCH /api/workflows/{id}/project` associates a workflow with a project.
The project page renders the workflows and expected/observed properties.

## API additions

```text
POST  /api/workflows/{id}/cancel
PATCH /api/workflows/{id}/project
GET   /api/workflows/{id}/events?after_sequence=N
GET   /api/projects/{id}/evidence-timeline
```

`GET /events` is durable polling over persisted events. It does not invent
progress or heartbeat events.
