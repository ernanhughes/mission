# MC10 - cross-application workflow contract

## Scope

One vertical slice:

```text
Next evidence → Mission Control proposal → human approval
→ Worker local execution → approved patch + deterministic tests
→ CoCoder review → measurement → human decision
```

This is a traceable experiment workflow, not a general autonomous-agent
framework. Work write-back, Writer, Movies and unrestricted conversational
execution remain out of scope.

## Workflow state machine

```text
proposed
  └─ approve (confirm + scope acknowledgement + current baseline hash)
       └─ approved
            └─ execute (confirm + stale checks)
                 ├─ failed   (Worker/patch/scope/commit failure)
                 └─ executed (patch committed + measured)
                      └─ review
                           ├─ review_failed
                           └─ reviewed
                                └─ decide
                                     ├─ accept
                                     ├─ reject
                                     └─ investigate
```

`decided` is terminal. A failed attempt can be rejected/investigated or replaced
by a new workflow created with `force_new=true`.

## Persistent records

Migration `003_experiment_workflows.sql` adds:

### `experiment_workflows`

Durable identity, Next external ID/title, preserved Next evidence, proposal,
Language Level 0 intention, sandbox path, baseline commit, approved scope,
approval hash/time/person, Worker request/status/result, patch, result commit,
measurement, CoCoder execution/artifact/summary, adverse flag, final decision,
failure and idempotency key.

### `workflow_events`

Append-only timeline with sequence, event type, source, summary, payload, source
reference and timestamp. Every stage references its authoritative source.

## Proposal contract

The proposal contains:

- objective and source research hypothesis;
- exact file scope (`tracelite/reduce.py`);
- repository path and baseline commit;
- baseline file hash;
- Worker backend/model/base URL, one-call budget and timeout;
- expected result;
- stop conditions;
- evaluation criteria;
- baseline tests and measurement;
- the exact Worker prompt;
- Next export path/schema/generation time;
- provenance for the Next record.

The baseline is observed before approval. The model is not called at proposal
time.

## Approval contract

Approval requires:

- explicit `confirm=true`;
- `scope_acknowledged=true`;
- a clean sandbox at the proposed baseline commit;
- the approved file content hash to match the proposal.

The approval hash covers objective, scope, repository, baseline commit, baseline
file hash, expected result, stop conditions, evaluation criteria, Worker config
and prompt hash.

Execution re-computes the hash and checks the repository HEAD/file hash. A
changed proposal, baseline or file causes a `409 stale approval` before Worker is
called.

## Worker contract

Mission Control calls Worker's documented HTTP endpoint:

```json
POST /v1/work
{
  "schema": "worker.work-request.v1",
  "app": "mission-control",
  "objective": "<bounded prompt>",
  "workspace": { "root": "<sandbox>", "project_id": "<workflow-id>" },
  "execution": { "backend": "direct", "model": "qwen2.5-coder:latest" },
  "metadata": { "workflow_id": "...", "stage_id": "EXPERIMENT" },
  "options": { "acceptance": "human" }
}
```

The direct executor calls a local Ollama OpenAI-compatible gateway. It is
lower-semantics: Worker returns `AWAITING_ACCEPTANCE`, not Evidence or
Acceptance. This is recorded honestly.

A Worker request ID, status, execution identity, output hash and excerpt are
stored. A missing Worker, non-200 response, blocked/failed status or timeout
produces a failed workflow with a diagnostic.

## Patch and scope enforcement

The model output is accepted as either:

1. a `mc10.patch.v1` JSON object with exactly one approved path; or
2. a complete Python file for the already-approved path.

Before writing:

- strip markdown fences and isolate the code block;
- require exactly `tracelite/reduce.py`;
- parse Python AST;
- reject imports, dunder attributes and dangerous calls (`open`, `eval`, `exec`,
  `compile`, `__import__`, `getattr`, `setattr`, etc.);
- require a `reduce_trace` function.

After writing:

- `git diff --name-only` must equal the approved scope;
- otherwise the sandbox is restored and the workflow fails.

The workflow never accepts a browser-supplied command, path or file scope.

## Measurement

Deterministic gates:

- `python -m pytest -q` must pass;
- `python scripts/measure.py` must exit 0 and report `21 -> 3` events;
- the result commit must contain exactly the approved scope.

Baseline and outcome metrics are stored separately. A worker `AWAITING_ACCEPTANCE`
result does not imply success; tests do.

## CoCoder review

Mission Control starts the existing CoCoder `run_review` action with:

- the sandbox repository path (a registered workflow repository);
- `base=baseline_commit`;
- `head=result_commit`;
- a bounded timeout.

The review artifact is parsed for changed files, finding counts, severities and
sample findings. High or medium findings set `adverse_review=true`. A passing
review is not proof that the research hypothesis succeeded.

## Human decision

`accept` requires:

- deterministic tests and measurement passed;
- no adverse high/medium review finding, unless the human explicitly overrides
  with a reason.

`reject` and `investigate` are always available after execution/review/failure.
Mission Control also writes a normal local Decision and activity entry. No
source application is updated.

## Idempotency and replay

- Replaying `create` for the same Next opportunity returns the latest workflow,
  not a duplicate.
- Replaying `execute` on a completed workflow returns the same Worker request
  and result commit.
- Replaying `review` returns the same review execution/artifact.
- A different final decision on an already-decided workflow is rejected.
- New attempts require `force_new=true`; each result commit is tagged before the
  sandbox is reset to `mc10-baseline`.

## UI

Routes:

- `/workflows` — experiment traces and states;
- `/workflows/:workflowId` — research evidence, proposal, approval, execution,
  measurement, review findings, timeline and human decision;
- `/next?record=...` — a TraceLite candidate exposes **Propose TraceLite
  experiment** without executing anything.

## Language Level 0

Every workflow stores a silent structured intention:

```json
{
  "schema": "language.intention.v0",
  "silent": true,
  "intent": "...",
  "constraints": ["..."],
  "scope": ["tracelite/reduce.py"],
  "expected_result": "...",
  "evaluation_criteria": ["..."],
  "observations": [],
  "decision": null
}
```

No Language model interprets, negotiates or executes it in MC10. It is a stable
representation that can later be connected to Language experimentation.

## Security boundaries

- Loopback-only Mission Control and local Worker.
- Browser sends typed workflow IDs and decisions, never commands.
- Approval hash, baseline HEAD and file hash are rechecked at execution.
- The sandbox is a dedicated Git repository under Mission Control data.
- No source repository is modified; Next only received its own local export
  contract commit.
- No paid inference route is configured; Worker calls local Ollama.
- CoCoder review uses its existing action lifecycle and state redirection.
- The workflow UI never claims that Worker acceptance or CoCoder review proves
  the research hypothesis.

## Honest limitations

- Worker's `direct` executor is lower-parity and does not produce Work
  Evidence/Acceptance.
- The experiment is a proxy spike, not the full TraceLite mechanism.
- Local model output is probabilistic; a failed attempt is preserved rather than
  hidden.
- Scope enforcement is file-level, not a general OS sandbox for arbitrary
  generated Python; static AST checks plus a dedicated repository and test
  timeout are the safeguards in this slice.
- No cancellation endpoint or streaming Worker events yet.
- The workflow is one registered template, not a general workflow builder.
