# H3 Test Evidence

## Earlier H3 implementation loop

- `python -m unittest test_evaluate.py -v` in `h3-fixtures`: 6 tests passed in 0.156 s, covering verified bundle PASS, swapped output rejection, fixture tampering, episode mismatch, wrong findings, and partial findings.
- `node --experimental-transform-types --loader ./worker-ts-loader.mjs ./run-worker-baseline.mjs C:/Projects/worker`: deterministic adapter run completed, `AWAITING_ACCEPTANCE`.
- `resolve-mission-episode.py` against the run directory: actual `EpisodeService.get_episode` resolved the isolated task episode.
- Pinned evaluator against the final run: `PASS`, 4/4 findings, bundle integrity verified.
- `node node_modules/typescript/bin/tsc --noEmit --pretty false` in Worker: passed.
- `bun test tests/execution-ledger.test.ts` in Worker: 8 tests passed, 0 failed. The first cold invocation took 3.33 s and is recorded as long; it ran because it directly covers the changed ledger and is required H3 exit evidence. After schema tightening, a warm rerun took 0.167 s.
- `git diff --check` in Worker and Mission: passed.

## Deferred

- Full Mission, Worker, frontend, integration, long, model, and corpus suites were not run. Other long suites were deliberately deferred under repository policy.

## H3Q acceptance gate (2026-11-24)

- Worker focused command `bun test tests/execution-ledger.test.ts tests/model-executor.test.ts tests/model-runtime.test.ts tests/pi-provider.test.ts`: 42 passed, 0 failed, 175 assertions, 0.454 s test runtime.
- Worker `node node_modules/typescript/bin/tsc --noEmit --pretty false`: passed.
- Mission `python -m pytest test_evaluate.py -q`: 12 passed, 0 failed, 3.34 s. The class is marked `pytest.mark.long` because measured time exceeds 2 s; run only because this suite directly qualifies the changed evaluator at the H3Q gate. It should not be in the routine per-stage smoke loop.
- Four current manifest/evaluator-pinned deterministic executions archived: baseline PASS, N1 FAIL, N2 NOT_EVALUATED, N3 NOT_EVALUATED. A separate local model execution produced a semantically invalid response and evaluator FAIL; see live report.
- Full backend/frontend, integration, and model/capability corpora were deliberately not run under the repository policy.
