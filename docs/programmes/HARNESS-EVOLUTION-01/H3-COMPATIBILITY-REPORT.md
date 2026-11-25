# H3 Compatibility Report

Worker changes are additive: task/episode request identifiers are optional, execution ledger capture is opt-in, and existing request/result shapes remain unchanged unless the feature is enabled. Ledger endpoints are exposed only when a ledger is configured and the API is bound to loopback. Digest and summary formats are explicitly versioned.

Evidence: Worker TypeScript check passed; `git diff --check` passed in Worker and Mission. No Bun executable was available, so `tests/execution-ledger.test.ts` was not run. The short evaluator tests pass. Compatibility with every downstream Worker package is therefore not fully test-proven; no broader suite was run.
