# W4-COST-AND-COVERAGE — 24/30 calls, $0.00, honest denominators

| Item | Count |
| ---- | ----- |
| Capability benchmark (3 models × 3 tasks) | 9 calls, $0 |
| Warm retry (mistral extract) | 1 call, $0 |
| Superseded pilot runs (pipeline shaping) | 8 calls, $0 |
| Final pilot: extraction (4 episodes) | 4 calls, $0 |
| Final pilot: semantic evaluation (2 episodes) | 2 calls, $0 |
| **W4 total** | **24/30 calls, $0.00 / $2.00** |

Cache: per (input digest, schema, prompt, extractor) — repeat evaluations
of unchanged episodes cost zero (verified `cached` path in tests).
Dedup: 50 distinct claim statements evaluated once per (claim, scope,
revision); finding dedupe by (episode, requirement, kind).

Coverage (deterministic, same denominators as W3): 147 sessions / 6,390
messages observed; 30 episodes; 26 task objectives; 51 deterministic claims
verified; 2 semantic-evaluated episodes; 2 findings raised (+1 missing set).
No exclusions: unresolved/no-requirement episodes are reported as `unknown`,
not dropped. Latency: mistral ~60s/call bounds throughput — the 30-call cap
is a wall-clock cap as much as a cost cap; bulk rollout needs batching or a
faster tier (W9).
