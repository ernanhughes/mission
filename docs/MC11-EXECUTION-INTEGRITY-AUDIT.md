# MC11 - execution integrity audit

Captured: 2026-10-24

Starting baseline: `C:\Projects\mission`, branch `main`, commit `43caf94`.
The MC10 accepted TraceLite workflow and its evidence were preserved.

## Baseline verification

| Check | Result |
| --- | --- |
| Mission Control backend before MC11 changes | 53 passed |
| Mission Control frontend before MC11 changes | 26 passed |
| Live Mission Control | healthy on `127.0.0.1:8790` |
| Worker | healthy on `127.0.0.1:7317`, `direct` executor |
| Next | `main` at `491b501`, clean |
| Worker | `main` at `0aecefa`, 33 pre-existing changes preserved |
| CoCoder | `cc-r06-p0-codeai-qualification` at `f4e90d6`, 36 pre-existing changes preserved |
| Work | `main` at `e79e68c`, 1 pre-existing change preserved |
| Docker | Docker Desktop 29.8.0 available; `python:3.13-slim` present |

## What MC10 left unresolved

### Generated code ran in a local subprocess

MC10 applied a model-generated file to a dedicated sandbox and ran `pytest` with
the host Python interpreter. That did not provide a filesystem/network/CPU/
memory boundary.

**MC11 change:** generated code now runs in a Docker container:

```text
--network none
--read-only
--tmpfs /tmp:rw,noexec,nosuid,size=64m
--cap-drop ALL
--security-opt no-new-privileges
--memory 512m --memory-swap 512m
--cpus 0.5
--pids-limit 64
--user 65534:65534
-v <sandbox>:/work:ro
```

The repository is mounted read-only. The image `mission-control/sandbox-python:3.13`
is built from `docker/sandbox/Dockerfile` with pinned `pytest==8.4.2`. The host
enforces a timeout and removes the container on timeout.

**Verified:** the existing TraceLite tests pass inside the container, and the
repository remains byte-for-byte unchanged. A dedicated sandbox test asserts
those properties and skips only if Docker is genuinely unavailable.

### Retry baseline was fixed in MC10 but not regression-tested across templates

MC10 exposed an earlier UI smoke run starting from an already-patched baseline.
The MC10 fix tagged a baseline and result commits, but the new template layer
needed to preserve that behavior for every sandbox.

**MC11 change:** template-specific baseline tags (`mc10-baseline`,
`mc11-brightness-baseline`) and result tags (`mc11-result-<workflow>`). A
`force_new` attempt tags the current result, resets to the baseline and cleans
the worktree. Tests assert the next attempt's baseline equals the original.

### Duplicate execute commands could race

MC10 checked persisted status but two in-process execute calls could both pass
the approved-state check before either wrote `executing`.

**MC11 change:** an in-process active-workflow guard rejects a concurrent execute
as `409 already executing`. The test proves only one Worker call occurs.

### Cancellation was absent

MC10 had no cancellation state or endpoint.

**MC11 change:** `cancel_requested`/`cancelled_at` and a `cancelled` status.
Cancellation before execution is immediate. During execution/review it is
cooperative: the workflow observes it at the next safe boundary, never applies
an uncommitted patch, restores the sandbox, and records the cancellation in the
timeline. It does not invent progress or claim that a Worker call was stopped
mid-flight. Browser acceptance cancelled a proposed workflow and showed the
truthful state.

### Patch parsing and scope enforcement needed hardening

MC10 handled fenced Python or a one-file JSON patch, but a model could add
commentary before a fenced block, and invalid JSON was rejected late.

**MC11 change:** parser extracts the fenced block or the entrypoint, accepts only
the template's exact scope, validates Python AST, rejects imports/dunder
attribute access/dangerous calls, and permits `open(..., "rb"|"r")` only for the
brightness template. Scope expansion is rejected before writing.

### Worker acceptance parity

`opencode-work` was evaluated against the available local/free path:

- A live `opencode-work` request with `review_mimo_free` and the free
  acceptance policy returned `BLOCKED` with a 403 FreeTierError: the OpenCode
  free tier cannot be used outside OpenCode.
- The hosted free route is not a verified local/free Worker route.
- Worker's `direct` executor with local Ollama was the only verified non-paid
  route available.

**MC11 decision:** retain `direct` and never fabricate Work Evidence, Verify,
Proof or Acceptance. Direct results remain `AWAITING_ACCEPTANCE`; deterministic
tests are the gate. This is a parity gap, not a hidden success.

Evidence: `docs/acceptance/mc11/worker-executor-evaluation.json`.

### Generalisation

MC10 had one hard-coded template. MC11 adds a versioned template registry and a
second structurally different experiment: a local raw-grayscale brightness
fixture with expected means/max values and a monotonicity constraint.

### Language and project evidence

`language.intention.v0` is unchanged. A new `language.observation.v1` records
expected versus observed properties, measurement method, evidence, uncertainty
and constraint result. Observations never rewrite intentions or decisions. A
project evidence timeline links workflows, observations and decisions.

## Threat model covered by the Docker boundary

In scope:

- untrusted model-generated Python;
- accidental or induced writes outside the approved file;
- network access during tests;
- unbounded CPU/memory/process creation;
- privilege escalation inside the container;
- test hangs beyond the host timeout.

Not claimed:

- a malicious Docker daemon or a compromised host;
- a malicious base image;
- kernel/container escapes;
- side channels;
- data exfiltration through the Docker daemon itself.

The generated file is still written on the host, but only after AST/scope
validation. It is executed only in the container. Broader execution remains
disabled outside the two dedicated sandboxes.

## Regression coverage added

- Docker sandbox read-only/no-network/limits test.
- retry baseline reset and result-tag preservation.
- modified approved file rejected before Worker.
- stale approval / changed baseline rejected.
- concurrent duplicate execute rejected.
- cancellation after Worker response leaves no patch and reports `cancelled`.
- scope expansion rejected before writing.
- adverse review blocks automatic acceptance.
- brightness template fixture and Language observation.
- project evidence timeline.

## Operational dependencies

- Docker Desktop must be running for generated-code execution.
- Worker at `127.0.0.1:7317` with its `direct` Ollama gateway.
- Ollama with `qwen2.5-coder:latest` for the local model.
- Without Docker, experiment creation fails clearly instead of falling back to
  untrusted host execution.

## Verdict

The execution integrity gates are met for the two bounded sandboxes. The
remaining gaps are Worker Work/Acceptance parity and operational Docker
dependence; neither is hidden or converted into a false acceptance claim.
