# H4 user guide

Run commands from `C:\Projects\worker`. The local routes are explicit H4 routes and do not change Worker’s default model policy.

For an isolated local Worker process with an H3 execution ledger, configure run-local evidence and disable the persistent usage ledgers before launch:

```powershell
$env:WORKER_EXECUTION_LEDGER='C:\Projects\mission\docs\programmes\HARNESS-EVOLUTION-01\h4-fixtures\live-local\runs\user-executions.jsonl'
$env:WORKER_PORT='7318'
$env:WORKER_USAGE_LEDGER='off'
$env:WORKER_USAGE_CALLS_LEDGER='off'
$env:WORKER_EVIDENCE_LEDGER='off'
bun src/cli/cli.ts serve
```

## List strategy definitions

With Worker serving locally:

```powershell
(Invoke-RestMethod http://127.0.0.1:7318/v1/strategies).strategies | Format-Table key,id,version,digest,maximum_model_invocations
```

## Select and run a strategy

Save a request as `h4-request.json`; for example:

```json
{
  "schema": "worker.work-request.v1",
  "task_id": "my-public-task-01",
  "objective": "Compute 19 + 23. Return exactly one JSON object with an integer field named answer and no other fields.",
  "execution": {
    "backend": "model",
    "model": "h4_qwen_local",
    "policy": "h4.local",
    "strategy_id": "corrective.v1"
  },
  "parameters": {
    "data_policy": "local_only",
    "timeout_ms": 60000,
    "max_output_tokens": 128,
    "output_schema": {
      "type": "object",
      "properties": { "answer": { "type": "integer" } },
      "required": ["answer"],
      "additionalProperties": false
    }
  }
}
```

Run the request through the existing CLI:

```powershell
bun src/cli/cli.ts run --file .\h4-request.json
```

To select A or B, change `strategy_id` to `direct.v1` or `structured.v1`. Direct does not run internal validation. B and C require `output_schema`. The route must be in the explicit policy; a paid route is rejected. A separate local review route is available as `h4_review_mistral_local` under `h4.local.review`.

## Inspect execution evidence and evaluate

The CLI result includes:

- `strategy_execution.strategy`: effective key, version and digest.
- `strategy_execution.state_history`: state transitions.
- `strategy_execution.invocations`: child runtime IDs, route/model identity, latency, usage and output digest.
- `strategy_execution.validation`, `.correction`, and `.resources`: validation decision, correction reason, aggregate use and termination.
- `model_execution`: existing runtime attempt details.

When the execution ledger is configured, the matching H3 summary is available from the existing local-only `GET /v1/executions` endpoint (default Worker port `7317`; the isolated process above uses `7318`). Run the independent evaluator on a file containing the raw model output:

```powershell
python C:\Projects\mission\docs\programmes\HARNESS-EVOLUTION-01\h4-fixtures\live-local\evaluate.py .\model-output.json
```

Retrieve one H3 record by the `request_id` returned in the Work result:

```powershell
Invoke-RestMethod http://127.0.0.1:7318/v1/executions/wrq_0123456789abcdef0123456789abcdef
```

Compare the archived A/B/C records from this H4 run:

```powershell
$runs='C:\Projects\mission\docs\programmes\HARNESS-EVOLUTION-01\h4-fixtures\live-local\runs'
'direct','structured','corrective' | ForEach-Object {
  $r=Get-Content "$runs\$_-result.json" -Raw | ConvertFrom-Json
  [pscustomobject]@{strategy=$r.strategy_execution.strategy.key;state=$r.strategy_execution.state;calls=$r.strategy_execution.resources.invocation_count;tokens=$r.strategy_execution.resources.observed_output_tokens;termination=$r.strategy_execution.resources.termination_reason;request_id=$r.request_id}
} | Format-Table -AutoSize
```

These commands and fields are implemented in Worker. Avoid operational usage-ledger writes in isolated experiments by setting `WORKER_USAGE_LEDGER=off`, `WORKER_USAGE_CALLS_LEDGER=off`, and `WORKER_EVIDENCE_LEDGER=off`; point `WORKER_EXECUTION_LEDGER` to a run-local file when retaining H3 summaries.
