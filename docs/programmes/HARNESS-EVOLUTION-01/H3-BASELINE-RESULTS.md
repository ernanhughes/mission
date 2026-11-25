# H3 Baseline Results

Pinned task `HE-PKG-001`; expected four facts: package name, version, and two dependency keys. Latest artifact directory: `h3-fixtures/h3-results/run-c5a84fa3-6b1b-4533-9440-a2683feb5018/`.

| Field | Result |
|---|---|
| Worker request | `wrq_15e5b137df884580eb1977ac6eb23d2d` |
| Worker status | `AWAITING_ACCEPTANCE` |
| Model | `NOT_INVOKED` (deterministic injected transport) |
| Semantic evaluation | `PASS`, 4 expected / 4 observed |
| Bundle integrity | verified against pinned task/evaluator/fixture and Worker ledger |
| Mission link | resolved by `EpisodeService.get_episode` in run-local SQLite fixture |
| Model/token/cost budget | zero model calls; no model tokens or cost |
| Runtime bound | 2-second abort signal |

This is historical H3 implementation evidence. The current qualified baseline is [run-a70505b9-56d2-4663-8671-be7f5081c255](h3-fixtures/h3-results/run-a70505b9-56d2-4663-8671-be7f5081c255/), request `wrq_8b486ee51cf1e891c4dcc4e3b886c2c2`; the current N1-N3 results are in [H3Q-NEGATIVE-EXECUTION-EVIDENCE.md](H3Q-NEGATIVE-EXECUTION-EVIDENCE.md). These are deterministic fixture checks, not a comparative benchmark, efficacy result, production integration, or proof of isolation for live agents.
