# H5 user guide

## Inspect the Worker strategy catalogue

With the Worker service already running on its configured local port:

```powershell
Invoke-RestMethod 'http://127.0.0.1:<port>/v1/strategies'
```

Confirm `adaptive.v1` advertises `json-fence.v1` and its two-invocation ceiling.

## Submit one explicitly selected adaptive request

Create a request JSON with a unique `task_id`, objective, and structural `output_schema`. Its execution fields must explicitly select `strategy_id: "adaptive.v1"`, `normalization_policy: "json-fence.v1"`, `model: "h5_mistral7b_local"`, and `policy: "h5.local"`; parameters should set `data_policy: "local_only"`, a timeout no greater than 60000 ms, and `max_output_tokens` no greater than 2048. The sample qualified fixture and manifest live under `h4-fixtures/live-local/`. Keep the task and its evaluator independent; structural validation is not semantic verification.

Before each run, create a new isolated directory and four empty JSONL ledger files. Point Worker to those paths and the checked-in model map, then use the Worker CLI:

```powershell
$run = 'C:\path\to\new-run'
$env:WORKER_EXECUTION_LEDGER = Join-Path $run 'executions.jsonl'
$env:WORKER_USAGE_LEDGER = Join-Path $run 'usage.jsonl'
$env:WORKER_USAGE_CALLS_LEDGER = Join-Path $run 'usage-calls.jsonl'
$env:WORKER_EVIDENCE_LEDGER = Join-Path $run 'evidence.jsonl'
$env:WORKER_MODELS_CONFIG = 'C:\Projects\worker\worker.models.yaml'
bun C:\Projects\worker\src\cli\cli.ts run --file C:\path\to\request.json
```

The CLI syntax is based on the checked-in CLI parser and focused tests; no additional live CLI invocation was spent for this guide. Worker also needs its normal local service configuration (`WORKER_CONFIG` or the default user config) to resolve the selected route. Do not set a paid route or share local model prompts externally.

Inspect `strategy_execution.invocations[].output` for retained raw bytes, `strategy_execution.normalized_artifact` for an applied transform, and `strategy_execution.validation.attribution` / `decisions` for bounded evidence. `AWAITING_ACCEPTANCE` is not an independent correctness verdict. The paired experiment evaluator is specific to the captured fixture; `python h5-fixtures/evaluate_h5.py <bundle-dir>` verifies only a complete bundle produced by the harness runner, not an arbitrary CLI result.
