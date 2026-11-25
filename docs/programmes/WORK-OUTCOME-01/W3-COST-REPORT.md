# W3-COST-REPORT — $0.00 spent of $1.00; 19 of 20 calls

| Item | Calls | Tokens in/out | USD |
| ---- | ----- | ------------- | --- |
| Synthetic probes (fence/strictness calibration) | 2 | 439 / 1,097 | 0.00 |
| Model triage (10 queued sessions) | 10 | ~3,400 / ~1,500 | 0.00 |
| Model requirement extraction (7 episodes) | 7 | ~2,700 / ~1,100 | 0.00 |
| **Total** | **19 / 20** | **≈6,100 / ≈3,700** | **0.00 / 1.00** |

Enforcement: in-service caps (`max_model_calls=20`, `budget_usd=1.0`);
cache-first (repeat inputs cost zero — verified `cached` path in tests);
per-run ledger (`wo_extraction_runs`: extractor, input digest, schema/prompt
versions, tokens, latency, errors). Deterministic pipeline cost is
compute-only (measured wall times in pilot reports). No paid provider was
touched; no API keys used. Remaining headroom (1 call) intentionally unspent
— reserved for a confirmation run only with authorization.
