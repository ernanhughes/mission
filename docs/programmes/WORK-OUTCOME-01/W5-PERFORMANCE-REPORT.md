# W5-PERFORMANCE-REPORT — Bounded reads, no page-load inference

- Overview: 1 bounded call (`limit ≤ 200`, default 100) + 1 findings call;
  no N+1 (the overview read-model exists precisely to avoid per-episode
  fetches). Detail modal: 4 bounded calls on open only (episode, evaluation,
  requirements, claims), each `limit ≤ 200`, lazy (never prefetched).
- No model execution on render or navigation (test asserts zero POSTs
  across tab switches; the UI has no POST path at all except none — all
  W5 calls are GET).
- Measured against scratch `w4_pilot3` (31 episodes): overview payload
  ~15 kB, renders in one paint; full-page screenshots show no layout shift
  beyond the async loading blocks.
- No production-scale claims: the pilot DB is tiny by design. W9 rollout
  must re-measure with pagination active (`limit`/`offset` already
  supported) before asserting portfolio-wide performance.
