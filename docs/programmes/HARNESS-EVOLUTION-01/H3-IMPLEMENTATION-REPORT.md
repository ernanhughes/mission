# H3 Implementation Report

**Historical implementation state:** implemented; post-fix review pending at the time of this report. Final H3Q outcome is recorded below. No H4 work was started.

## Implemented

- Worker gained an opt-in append-only execution summary ledger, versioned request/resolution/configuration identity, request/task/episode/operation correlation, bounded event summaries, content digest privacy controls, and loopback-only read endpoints when the ledger is enabled.
- Ledger reading now rejects records outside the exact allowlisted summary schema, including nested record sections, in addition to rejecting malformed/checksum-invalid/conflicting rows.
- `HE-PKG-001` is a frozen synthetic `package.json` fixture with pinned SHA-256 and a pinned evaluator digest. Runner refuses to dispatch if either digest differs.
- The run uses WorkerService plus Worker’s OpenCodeExecutor adapter with an injected deterministic transport. That transport reads the attempt workspace fixture and constructs the structured findings; it invokes no model, process, network, or tool. A two-second abort signal is applied.
- The isolated Mission link resolves the task-derived episode through `EpisodeService.get_episode` backed by run-local SQLite. It does not touch operational Mission data or establish a production integration.
- The fail-closed evaluator verifies manifest/evaluator/fixture pins, request/task/episode identities, output digest, ledger checksum and summary equality, and the isolated episode resolution before semantic scoring.

## Run result

Latest run: `h3-fixtures/h3-results/run-c5a84fa3-6b1b-4533-9440-a2683feb5018/`. Request `wrq_15e5b137df884580eb1977ac6eb23d2d` returned `AWAITING_ACCEPTANCE`; offline evaluator result `PASS` (4/4 findings), with bundle integrity verified. This is a bounded adapter smoke, not evidence of model or agent quality.

## Known limits

The Worker configuration digest covers the requested fields and the resolved fields explicitly recorded by this Worker change; it is not a claim that every provider, model, sandbox, or adapter setting is captured. Output token enforcement remains `UNKNOWN` for live model runs. The artifact bundle is consistency-checked, not signed or tamper-proof against an actor able to replace all files and the trusted manifest. The Worker summary marks the episode link caller-supplied/unverified; only the separate isolated Mission lookup proves that this fixture episode ID resolves in that database. No negative end-to-end run was archived.

No production database or book manuscript was used. H3Q later made at most three owner-authorized local model requests; see the qualification report for the actual result and limits.

## H3Q qualification update

H3 is accepted for the deterministic offline lane only. The current manifest-pinned baseline passes; N1 rejects the incorrect version; N2 and N3 fail closed without candidate output. The runner now enforces the declared timeout for all scenarios, and the evaluator binds scenario, request identity, configuration schema and terminal reason. Mission episode resolution is idempotent. Fresh independent review accepted this bounded scope.

The corrected local model route executed Qwen2.5:0.5b and returned observed usage, but its Markdown-fenced, incorrect response failed the task evaluator. The live model lane is not accepted. See [H3Q-LIVE-EXECUTION-REPORT.md](H3Q-LIVE-EXECUTION-REPORT.md) and [H3Q-FINAL-ACCEPTANCE.md](H3Q-FINAL-ACCEPTANCE.md). H4 remains pending explicit authorization.
