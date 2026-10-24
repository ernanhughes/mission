# MC10 - reality audit

Captured: 2026-10-24

Starting baseline: `C:\Projects\mission`, branch `main`, commit `da22636`.
The reported MC09 acceptance was treated as the baseline; it was not re-run as new work.

## Mission Control baseline

| Check | Result |
| --- | --- |
| Repository | `C:\Projects\mission` |
| Branch | `main` |
| Baseline HEAD | `da22636` (`Record MC09 acceptance evidence and engineering report`) |
| Backend suite at audit start | 50 passed |
| Frontend suite at audit start | 23 passed |
| Live service | `http://127.0.0.1:8790` healthy |
| SQLite schema | migrations 001 + 002 before MC10 |
| Existing engines | Next, Work, CoCoder integrations from MC09 |

No MC09 behaviour was removed. The compatibility Next database adapter remains available.

## Source repository states

| Repository | Branch | HEAD | Changed paths | Interpretation |
| --- | --- | --- | ---: | --- |
| `C:\Projects\next` | `main` | `cbacf17` | 0 | Clean; suitable for a source-owned export contract |
| `C:\Projects\worker` | `main` | `0aecefa` | 33 | Pre-existing user changes; preserved |
| `C:\Projects\cocoder` | `cc-r06-p0-codeai-qualification` | `f4e90d6` | 36 | Pre-existing user changes; preserved |
| `C:\Projects\work` | `main` | `e79e68c` | 1 | Pre-existing change in `work/dashboard.py`; preserved |

No push was performed in any repository.

## Next

### Verified contract before MC10

- Research data lives in PostgreSQL when `NEXT_DSN` is set, with SQLite fallback.
- The MC09 adapter used SELECT-only PostgreSQL because Next had no stable JSON
  resource API.
- `ResearchStore` is a Next-owned class; its constructor applies schema
  migrations. It is not a safe read contract for Mission Control.
- The public CLI exposes discovery, review, gap analysis, research and
  reassessment commands, but no research export.

### MC10 source-side contract

A minimal, source-owned command was added:

```powershell
python -m next export --output FILE --limit 200
```

It writes `next-research-export-v1` with:

- candidate identity, title, status, queue, score and timestamps;
- mechanism/hypothesis fields, proposed experiment and falsification;
- source item identity, URL, title, summary and source metadata;
- evidence-gap records when present;
- discovery runs and decision history;
- `source.read_only=true` and the Next store schema version.

Implementation: `next/export.py`, `next/cli.py`; tests:
`tests/test_export_contract.py` (2 passed). Local Next commit: **`491b501`**.

Live export: 130 opportunities, 12 runs, 130 decisions, 1,082,976 bytes. The
TraceLite candidate `32e30df92070ef58c36324e400b2f6d54aacc375c9f14fd0b0de542630ce6c06`
is preserved with its proposed experiment and falsification.

Mission Control's MC09 PostgreSQL adapter was deliberately retained. MC10 uses
the export for the workflow's immutable research evidence.

Caveat: the export command opens Next's own `ResearchStore`, whose constructor
applies Next's schema initialization/migrations. The export changes no research
rows, but it is not a no-migrate read-only connection. If strict read-only schema
behaviour is required, Next should add a no-migrate export mode. This is recorded
as a Phase 1 limitation, not hidden behind the contract name.

## Worker

### Verified interface

- Worker is a Bun HTTP service at `127.0.0.1:7317`.
- `GET /health` reports executors and model diagnostics.
- `POST /v1/work` accepts `worker.work-request.v1` and returns
  `worker.work-result.v1`.
- `GET /v1/work/:request_id` and `GET /v1/jobs` expose execution state.
- Supported executors include `opencode`, `opencode-work`, optional `pi`, and
  `direct` through an OpenAI-compatible gateway.
- Gateway tests at audit: **210 passed, 8 skipped, 0 failed**.

### Execution constraint discovered

The hosted free route is not usable through this Worker path: a live probe and
an `opencode-work` attempt both returned OpenCode free-tier
`permission_denied`. The available paid/subscription routes were not authorised.

A local Ollama service is running at `http://127.0.0.1:11434/v1`. Worker's
supported `direct` executor can call it through an OpenAI-compatible gateway.
OpenCode tool execution against the local model did not execute the model's
file-write action, so MC10 used the lower-semantics `direct` executor:

- Worker performs the local model inference.
- Worker returns `AWAITING_ACCEPTANCE`; it does not claim Evidence or Acceptance.
- Mission Control applies only the approved file scope.
- Deterministic tests and measurement are the actual gate.
- CoCoder independently reviews the resulting commit.

This is intentionally labelled lower-parity. It is not represented as Worker
Work/Acceptance verification.

Worker source was not modified. Its 33 pre-existing changes were preserved.

## CoCoder

- Existing MC09 artifact and action contract was reused:
  `cocoder review --repo PATH --base REF --head REF --format json --output FILE`.
- Reviews run with state redirected under Mission Control's data directory.
- The real MC10 result commit was reviewed as a one-file diff.
- Review artifact schema `0.2`; zero findings for the accepted result.
- CoCoder source was not modified. Its 36 pre-existing changes were preserved.

## Sandbox

A dedicated Git repository was created under
`data/experiments/tracelite-spike` (git-ignored runtime data):

- `tracelite/reduce.py` baseline returns the trace unchanged.
- `tests/test_reduce.py` defines deterministic compaction behavior.
- `scripts/measure.py` measures a 21-event duplicate-heavy fixture.
- Baseline: 2 tests failed; trace stayed 21 events; reduction 0.0.
- The sandbox is tagged `mc10-baseline`; every new attempt resets to that tag.
- Result commits are tagged `mc10-result-<workflow_id>` before retries, preserving
  prior evidence while keeping the next attempt honest.

## Key decisions

1. Add a source-owned Next export rather than pretending the database is a stable API.
2. Keep the MC09 Next compatibility adapter; use the export for workflow evidence.
3. Use Worker's actual HTTP interface with a **local, non-paid** direct executor.
4. Never treat Worker's direct output as accepted evidence.
5. Enforce the approved file scope and baseline hash at execution time.
6. Reset new attempts to a tagged baseline; preserve result commits.
7. Use CoCoder as an independent reviewer, not as proof of the research hypothesis.
8. Require a human decision; adverse high/medium findings block automatic adoption.
9. Introduce Language only as a silent structured intention (`language.intention.v0`).
10. Keep Work write-back, Writer, Movies and unrestricted conversational autonomy out of this slice.
