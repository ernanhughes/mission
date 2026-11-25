# H3Q resource-control matrix

States use `REQUESTED`, `SUPPORTED`, `ENFORCED`, `OBSERVED`, `UNKNOWN`, or `UNSUPPORTED`; a requested limit is not itself proof of enforcement.

| Resource | H3Q request | Worker / provider behavior | Observed evidence and limit |
|---|---|---|---|
| Wall clock | 2s deterministic scenarios; 60s local inference | Deterministic runner watchdog now covers every scenario. ModelExecutor/ModelRuntime pass abort signals; runtime carries one deadline across retries/routes. | Deterministic runs completed inside bound; local call completed in 28.8s. Local abort proves caller-side stop only; remote termination is `UNKNOWN`. OpenCode CLI has its own fixed timeout outside this route. |
| Output tokens | Local: 2048 | OpenCode chat sends `max_tokens`; Responses sends `max_output_tokens`. Provider-side honoring is not receipt-verified. Pi path has no per-request cap. | 134 output tokens observed on the one valid local endpoint call; cap enforcement remains `UNKNOWN`. |
| Total tokens | Observe if provider reports | Worker records normalized provider usage. | Local call: 119 input, 134 output, 253 total. Prior 404 attempts had no usage. Missing usage stays unknown. |
| Model calls / attempts | Local manifest: 1; fallback policy has one route and one attempt | In-memory H3Q policy selects one explicit local route, `attempts_per_route: 1`; model-only executor invokes no agent tools. | Three authorized local requests total: two used the malformed URL and got 404; one reached Qwen and returned output. The two 404s did not demonstrate inference. |
| Tools / side effects | 0 tools; fixture read only | ModelExecutor returns provider text; no tool registry or file writer is passed. Runner writes only run-local evidence and fixture workspace. | No external side effect observed. OpenCode agent mode can invoke tools and is outside the local model lane. |
| Monetary cost | $0 | Local Ollama loopback route is configured free; no paid provider route or fallback exists. | Estimated cost $0; billed status remains `unknown` because there is no invoice/receipt. Remote free routes are not used. |
| Process / remote termination | Caller timeout and explicit cancellation | Abort signal is passed to fetch/provider and route loop; Pi abort kills its local process tree. | Local inference returned within 60s. Whether any remote service continues compute after local abort is `UNKNOWN`; no remote lane was invoked. |
| Model identity | Observe resolved and returned model | Requested route and provider-reported model are recorded separately. | Request route `h3q_local_qwen25_05b`; provider-reported `qwen2.5:0.5b`, identity status `OBSERVED`. |

