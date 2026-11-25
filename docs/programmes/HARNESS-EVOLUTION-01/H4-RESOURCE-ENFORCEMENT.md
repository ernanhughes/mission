# H4 resource enforcement

| Resource | Worker control | Evidence / limitation |
|---|---|---|
| Invocation count | Fixed strategy maximum (1, 1, or 2); one provider attempt per route; explicit one-route policy | Count and child IDs recorded per strategy and in H3 summary |
| Strategy wall time | One deadline shared by all calls; request timeout capped at 60,000 ms | Worker abort signal enforced locally; remote inference termination remains unknown |
| Output tokens | Caller budget capped at 2,048 per whole strategy; remaining observed output usage is passed to correction; correction is skipped if usage is missing/exhausted | OpenCode chat adapter forwards `max_tokens`; effective/remote cap is not independently acknowledged and summary marks it `UNKNOWN` |
| Monetary ceiling | Paid/subscription routes are rejected; H4 compare uses local Ollama free route | Estimated cost $0; billed amount remains null. No paid route was called |
| Fallback/retry | Explicit model route and one-attempt policy; no strategy-level fallback | No hidden route substitution; provider/runtime events record selected route and observed model |
| Task/evaluator separation | Only public task and structural schema reach strategy; evaluator runs afterward | No semantic answer constraint is admitted into the schema; corrective prompt contains only structural errors |

The live comparison requested 128 output tokens per strategy, below the authorized 2,048 maximum, and a 60-second deadline, below 120 seconds. Observed output was 15 tokens for A, 15 for B, and 30 across C's two calls. Local route cost estimate was $0; billed cost and remote cancellation are not observed. The output-token ceiling is a request plus aggregate accounting guard, not a provider-certified hard cap.

The failed local Mistral source-review request used a separate 60-second Worker deadline and 2,048 requested output tokens. It timed out with `request_admitted` and `inference_executed` unknown; it did not produce a review.
