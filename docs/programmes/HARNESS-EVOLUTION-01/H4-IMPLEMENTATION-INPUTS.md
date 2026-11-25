# H4 implementation inputs — not an authorization

## Smallest useful next increment

H4 should add a versioned strategy manifest interpreted by existing Worker request/policy/ModelExecutor seams. Keep it declarative: strategy ID/version, task fixture reference and digest, requested route/policy, wall-clock budget, output-token request, attempt limit, tool/side-effect policy, and evaluator reference. Do not introduce a general policy DSL, automatic strategy selection, or promotion logic.

The first controlled comparison can be **Direct** versus **Verified**. Both use the same fixture, route, temperature, timeout, token request, and attempt count. Verified may parse/check its own response and perform at most one bounded repair; it must not receive the expected answer. The frozen external evaluator remains outside the candidate strategy.

## Entry prerequisites

1. Decide how to handle actual model quality failures. The H3Q Qwen 0.5B run returned invalid Markdown-wrapped JSON and incorrect dependency facts; Mission W6A also bars that model from judgements. Select and verify a suitable task-solving route before running a comparison.
2. Preserve honest resource claims. Record requested and effective caps separately; keep provider-side enforcement, billing and remote termination `UNKNOWN` unless the provider returns evidence.
3. Keep one request-wide deadline across retries/fallbacks and retain the new abort regression coverage.
4. Keep Mission's Work Outcome episode/outcome ownership. Link Worker request and attempt IDs to existing episode/evidence references; do not add a parallel harness episode table or write into operational Mission state in H4 without a separate gate.
5. Freeze train/selection tasks separately from held-out acceptance tasks. Do not use the same fixtures to design and judge a strategy.
6. Reuse Praxis effectiveness records and independent `retain` / `reject` / `insufficient_evidence` review. No automatic promotion.

## Existing extension points

Worker already has `WorkRequest`, `ExecutorRegistry`, `ModelExecutor`, `ModelRuntime`, route policies and the opt-in execution summary/ledger. Mission Work Outcome already models objectives, requirements, claims, observations, evaluations and episode linkage. Praxis owns cross-domain effectiveness and experiment reporting; Writer/ECK remains the Writer-domain capability. H4 should connect these by references and provenance rather than copying their state.

H4, comparative experiments, operational integration, migrations, deployment, book changes and promotion remain unstarted pending explicit authorization.

