# W8-COST-AND-PERFORMANCE — Measured, not modelled

- Model invocations attributable to W8: 0. Cumulative provider
  spend W4→W8: $0.00 (local loopback only; benchmark 4 calls earlier).
- Envelope cost: 671 bytes stored; 0 context tokens (never injected);
  registration = 3 indexed inserts; size probe is one row read.
- Lifecycle pass on scratch: 7–8s end to end (observe→recon→queue→
  eval→groups), idempotent on replay.
- Pilot execution: 3 git plumbing calls (<1s each), 0 tokens.
- DB growth: 1 episode + 1 objective + 3 requirements + 1 envelope +
  1 execution link + 3 links + 3 assessments (scratch only).
- Manual intervention: authorization + command runs + verification
  reads (minutes, not hours — vs weeks of retrospective recovery).
- Cache reuse: envelope digest dedupe; evaluation digest cache;
  group upsert idempotence — all exercised, no duplicate rows.
