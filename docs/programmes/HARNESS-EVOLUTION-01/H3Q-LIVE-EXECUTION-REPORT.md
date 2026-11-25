# H3Q bounded live execution report

## Result

Three local requests were made, the maximum authorized. Two early attempts addressed `/v1/v1/chat/completions` because the runner base URL included `/v1` and the adapter appended `/v1/chat/completions`; they returned HTTP 404 and are not evidence that the model or correct endpoint was unavailable. The runner base URL was corrected, then the final permitted attempt reached the local model.

The final attempt is [run-432b2eb2-092d-4f18-9dd7-e37885acdef2](h3-fixtures/h3-results/run-432b2eb2-092d-4f18-9dd7-e37885acdef2/). Worker recorded request `wrq_d98fc7791a4047a7e85b17cf13680bcd`, observed model `qwen2.5:0.5b`, 119 input tokens, 134 output tokens, 253 total, 28.8s elapsed, estimated cost $0 and billed status unknown. No tool call occurred; request stayed on loopback with a 60s request timeout and 2048-token requested cap.

The model returned Markdown-fenced JSON with an invalid output shape and incorrect dependency findings. The frozen evaluator returned `FAIL` (`Worker output is not valid JSON`). This is a genuine model execution and a failed task result. It does not qualify the model lane as accepted. No fourth attempt was made.

The run artifact is internally hash-consistent under its execution-time manifest/evaluator pins. Its evaluator pin predates the final evaluator changes; running the current evaluator implementation against the archived execution-time manifest gives the same semantic `FAIL`. Do not compare its manifest hash directly to the current deterministic manifest.

## Safe stopping decision

The local lane proved dispatch, response, model identity and usage observation, but failed task correctness. The authorization ceiling is exhausted, so model-quality follow-up requires a separately authorized stage/run. Do not promote this model/configuration to evaluation or judgement tasks. Mission Work Outcome W6A independently records that `qwen2.5:0.5b` is barred from judgements.

