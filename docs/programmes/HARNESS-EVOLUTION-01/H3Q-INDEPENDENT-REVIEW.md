# H3Q independent acceptance review

## Scope and result

Fresh read-only review by an independent `gpt-6.2-astra` agent of the Worker H3 changes, Mission evaluator, run artifacts, and corrective changes. The reviewer did not edit files, run tests, access services, or access operational databases. Final verdict: **ACCEPTED OFFLINE ONLY**. A second narrow re-review confirmed the internal-timeout/abort correction closes the last finding.

## Findings and closure

| Finding | Closure | Evidence |
|---|---|---|
| Chat adapter used the wrong token-cap field for Ollama-compatible chat. | Fixed: chat uses `max_tokens`; Responses retains `max_output_tokens`. | `C:\Projects\worker\src\models\providers\opencode.ts`; `tests/model-runtime.test.ts` |
| Local base URL doubled `/v1` and caused the first two HTTP 404s. | Fixed in runner; third and final authorized local attempt used the provider's actual path and produced an observed response. | `h3-fixtures/run-worker-baseline.mjs`; live report |
| Baseline/negative executor scenarios did not enforce their manifest watchdog. | Fixed: runner applies the manifest timeout to every scenario. | `h3-fixtures/run-worker-baseline.mjs`; current baseline and N1-N3 bundles |
| A fallback could get a fresh timeout or start after cancellation. | Fixed: one request-wide deadline is measured across attempts; canceled requests stop before a later route; Pi refuses an already-aborted request before spawning. | `C:\Projects\worker\src\models\runtime\engine.ts`, `src\models\providers\pi.ts`; focused tests |
| Evaluator did not bind scenario, terminal reason, or exact configuration-digest schema. | Fixed and regression-tested. | `h3-fixtures/evaluate.py`, `test_evaluate.py` |
| Re-running Mission fixture resolution could insert the same episode twice. | Fixed by making fixture creation idempotent. | `h3-fixtures/resolve-mission-episode.py`; repeated run resolution |
| An internal Worker timeout need not set the caller's abort flag. | Fixed after review: enforce matching `EXECUTOR_TIMEOUT` termination while allowing `abort_requested: false`; caller cancellation still requires abort evidence. | `h3-fixtures/evaluate.py`; timeout-without-caller-abort regression test |

## Fresh independent verdict

The reviewer independently recomputed request, normalized input, output, fixture, configuration, trace, ledger and evaluator hashes for the four final deterministic runs. All four matched current pins, Worker request/operation identities and Mission episode identifiers. The final evaluator change allows `EXECUTOR_TIMEOUT` when its terminal reason is `timeout` even if `abort_requested` is false; `CANCELLED` still requires caller-abort evidence. The reviewer confirmed this rule and its regression. No residual defect blocked deterministic-only acceptance.

The live model task was not accepted: the actual answer fails semantic scoring. Its artifact is valid under its execution-time evaluator pin (`12c987a2…`); the current live manifest pins the later evaluator (`86273e82…`), so current-pin bundle verification is correctly inconclusive. Current semantic scoring of the archived raw response is still FAIL.

