# H3Q negative execution evidence

All four current bundles pin the current fixture and evaluator. Mission episode resolution uses `EpisodeService.get_episode` with run-local SQLite. The resolver is idempotent. Evaluations are fixture/task checks, not proof of broad capability.

| Scenario | Request ID | Worker result | Frozen evaluator | Meaning |
|---|---|---|---|---|
| Baseline — `run-a70505b9-56d2-4663-8671-be7f5081c255` | `wrq_8b486ee51cf1e891c4dcc4e3b886c2c2` | `AWAITING_ACCEPTANCE` | `PASS`, 4/4 | Deterministic fixture output matches all expected facts. |
| N1 incorrect fact — `run-07b301fe-3a0f-45f6-a9c6-2f36d2ca9a28` | `wrq_6314ab6c60a7dc40d99ae76439b3ccbd` | `AWAITING_ACCEPTANCE` | `FAIL` | Unsupported version `9.9.9` is rejected. |
| N2 executor failure — `run-351ab02b-bc0a-4891-9934-fae97e5f3662` | `wrq_e40ad4e99a6d0dc061679b5d3449b669` | `FAILED / EXECUTOR_FAILED` | `NOT_EVALUATED` | No candidate text was fabricated or scored. |
| N3 cancellation — `run-2f24611f-6ebb-44a4-9aa2-3b0fbdfc7b98` | `wrq_766547abb4b23f1708529b3588e06141` | `BLOCKED / CANCELLED` | `NOT_EVALUATED` | Abort is recorded; no candidate text was fabricated or scored. |

The evaluator now binds attempt scenario to Worker operation identity, terminal status to termination reason/abort state, and requires the exact Worker configuration digest schema. Tampered scenario and termination tests fail closed. Bundles are hash-consistent, not signed; an actor with write access can replace all inputs consistently.

