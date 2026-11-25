# H5 experiment results

## Deterministic lane

Fresh bundle `h5-fixtures/runs/deterministic-20261125-d/` verifies PASS with current source identity, isolated ledgers, and five scripted invocations. Direct: FAIL/VERIFIED, 1 call. Structured: FAIL/VERIFIED, 1 call. Corrective: FAIL/VERIFIED, 2 calls. Adaptive: PASS/VERIFIED after `json-fence.v1`, 1 call. All used identical frozen fenced JSON. This isolates representation handling only.

## Bounded local lane

Fresh bundle `h5-fixtures/runs/live-local-20261125-d/` verifies VERIFIED, storage isolated, two invocations total. Model `mistral:7b-instruct`, route `h5_mistral7b_local`, policy `h5.local`; each run completed once, used 120 observed tokens (112 input, 8 output), and was independently evaluated PASS on the pinned arithmetic fixture. Corrective latency was about 4.45s and adaptive about 0.19s in this pair; this single observation is not comparative latency evidence. Both Worker results remain `AWAITING_ACCEPTANCE`. Adaptive did not normalize or correct: the provider returned parseable JSON. No general strategy-effectiveness or independent model-family review claim is made.

The H5 live invocation ceiling is eight. Runs b and c consumed four invocations; final run d consumed two, for six total. Two remained unused. Earlier a was a preflight runner failure before dispatch. Deterministic scripted calls are not model invocations against that live ceiling. No paid calls were made.

Earlier bundles are preserved as historical evidence and may have stale source/verifier identities. Only the final c/d bundles are used for current H5 acceptance.
