# H6 isolated end-to-end evidence

## Environment

- UI: `http://127.0.0.1:8791/harness` (isolated Mission instance).
- Worker fixture: `http://127.0.0.1:7318` (isolated Worker process, injected scripted provider, explicit run-directory ledgers).
- Mission SQLite database: `h6-fixtures/runs/e2e-20261125-b/mission.sqlite3` only.
- Synthetic episode/objective: `ep:h6:synthetic:001` / `obj:h6:synthetic:001`.
- No operational port 8790/7317 was used for this execution. No operational database, usage ledger, or provider inference was used.
- The general Mission startup performed its existing read-only workspace discovery and blog-source sync; Harness-specific persistence was limited to the isolated SQLite database and fixture run directory.

## Observed result

Mission UI authorized one `adaptive.v1` run using route `h6_fixture_local`, policy `h6.fixture`, requested timeout 30,000 ms, requested output cap 256 tokens, and a maximum of two calls. Worker request `wrq_04011f9649890e01e72941b1d9374f2f` completed with `AWAITING_ACCEPTANCE`. The scripted provider supplied fenced JSON; Worker applied `json-fence.v1`, recorded `NORMALIZE_REPRESENTATION`, and returned `{"answer":42}` after one invocation. Raw fenced text, digests, normalized artifact, timeline, decision trace, and resource record are retained in `h6-fixtures/runs/e2e-20261125-b/integration-evidence.json`.

Mission correlated Worker identity to the pre-dispatch Work Envelope (`we:dea016b02bc146b6`) and exact episode/objective. Worker still records its own episode link as `caller_supplied_unverified`; the UI displays both facts. No independent Work Evaluation exists, the episode remains `established`, and acceptance remains pending. This is mechanism/integration evidence, not task correctness or effectiveness evidence.

## UI evidence

The live isolated Harness page was observed in the Codex browser at the URL above. The execution detail showed the Mission Work Envelope correlation, Worker unverified source flag, request/trace, invocation and normalization decisions, final output, raw invocation output, normalized artifact, no independent evaluation, and separate episode/acceptance state. See `h6-fixtures/ui-evidence.md` for the captured visible-state record. The screenshot was captured during the run and displayed to the operator in the task conversation; the persisted machine-readable evidence is the JSON bundle above.

## Setup notes

Run `e2e-20261125-a` records a startup rejected before the SQLite opt-in was enabled. Run `e2e-20261125-c` records a seed attempt made before migration startup completed and is not acceptance evidence. They are retained as setup history; run `e2e-20261125-b` is the successful isolated run.
