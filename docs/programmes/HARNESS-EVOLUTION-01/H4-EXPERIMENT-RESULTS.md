# H4 live experiment results

The frozen task `HE-H4-LIVE-001` asked for the sum of 19 and 23 with a public JSON shape. All strategies used Worker route `h4_qwen_local`, observed model `qwen2.5:0.5b`, policy `h4.local`, temperature 0, a 60-second deadline, and a 128-token aggregate output budget. All three returned the correct numeric answer inside Markdown fences, so the independent raw-JSON evaluator returned FAIL.

| Strategy | Invocations | Output tokens | Worker termination | Task evaluator |
|---|---:|---:|---|---|
| A `direct.v1` | 1 | 15 | completed | FAIL: fenced output is not valid raw JSON |
| B `structured.v1` | 1 | 15 | failed | FAIL: fenced output rejected structurally |
| C `corrective.v1` | 2 | 30 | failed | FAIL: one correction; corrected output still fenced |

There were four live model invocations, no paid calls, no tools, and no task side effects. Combined observed usage was 480 input and 60 output tokens. No comparative effectiveness conclusion follows from one fixture.

The historical summaries predate the stronger output-digest binding. The current verifier requires result output and every successful retained raw child output to match their stored digests. The old H4 summaries have `output_digest=null`; consequently all three historical bundles are now `INCONCLUSIVE` as evidence bundles, even though their saved task evaluator says FAIL. Preserve them as historical raw results and do not describe direct as VERIFIED. The subsequent H4Q qualification at a fresh checkpoint is documented separately. No H4 live rerun was made.
