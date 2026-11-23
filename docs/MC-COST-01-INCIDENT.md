# MC-COST-01 — 22 November 2026 Go Allowance Exhaustion

Primary window: **22 Nov 2026 18:00 UTC → 23 Nov 2026 01:00 UTC**
(`1795370400000`–`1795395600000` ms).
Focus session: `ses_dfab0da59ffeWhe4sDDssnI1YM`
(“Book production pipeline research”, `C:/Projects/mission`).

All observations are from read-only `mode=ro` queries. Earlier reported totals
are treated as unverified until reconciled here.

## 1. Timeline (UTC, per-minute assistant calls)

- 18:00–20:30: steady 5–30 calls/min, mostly Meta cost >0 plus Go cost 0.
  Praxis evidence-replay tasks dominate early (16–32 calls/min, cost 0 each).
- 20:45–21:35: mixed Go volume (10–23 calls/min, cost 0) plus free-model
  `no-route` failures (`nemotron-3.5-lightning-free`, `space-bunny-free`).
- 22:10–22:24 **burst**: 42–63 calls/min, **all cost 0**.
  Target session starts 22:10:02.976, ends 22:41:00.035.
  Four parallel `explore` subagents spawn at 22:10:40
  (`ses_dfab047a...`, `ses_dfab047a5...`, `ses_dfab0479...`, `ses_dfab0479d...`).
  Cache_read grows monotonically per call (1,920 → 370,033) within the parent,
  consistent with a stable OpenCode session reusing context.
- 22:14–22:19: interleaved Meta cost (0.004–0.018/min) from unrelated
  sessions (Inspect, ALIVE, Mission dashboard work).
- **22:22:16–22:22:19**: first `provider.go-limit` idle failures hit all four
  children plus the parent:
  `OpenCode Go monthly usage limit reached (monthly, resets in 10d 20h),
   workspace wrk_01M1KD6TSKK4XF2PD900MN1130, limitName monthly`.
  Synthetic subagent-error messages mirror the same seconds.
- 22:24:29: one more parent `go-limit` failure.
- 22:29:33: parent resumes on `meta/muse-spark-1.3-contributor`
  (seq 1507, in 346,050, cost 0.0393822) — the only large-cost call in the
  target session. Three smaller Meta calls follow (22:33:06–22:33:12,
  total ~0.005). Target session total: **0.044254302** (4 Meta calls;
  105 Go calls cost 0).
- 22:37–23:04: Inspect/Mission children continue on Meta
  (22:49 peak: 104 calls/min, cost 0.132), then taper.

## 2. Top contributors (window, local records)

By request count: Praxis `ses_e099...` (813 Go, 0.0), ALIVE `ses_dfc18c38...`
(646, 0.815), Inspect `ses_e0109...` (372, 0.543), Mission `ses_dfc4c24e...`
(324, 0.316), Mission dashboard `ses_dfa8cbf3...` (188, 0.135).

By dollar cost: Mission `C:/Projects/mission` 14 sessions cost 2.55,
Inspect 12 sessions cost 1.22, ALIVE 2 sessions cost 0.919,
Praxis 3 sessions cost 0.834.

By Go volume (cost 0, allowance-relevant): Praxis-00 alone sent ~945k input
and 385M cache_read with zero local cost; target parent+children sent ~2.2M
input and ~135M cache_read with zero local cost for the Go portion.

## 3. What caused the final burst?

The 22:22 exhaustion was **not** caused by the target session alone.
It was the coincidence of:

1. All-day Go accumulation (Praxis evidence tasks, Inspect reviews, ALIVE
   research, Mission pipelines) — 1,675 Go calls in-window, 3.5M input,
   523M cache_read, all cost 0 locally.
2. A high-concurrency Go burst (parent + 4 subagents, ~50 calls/min for
   12 minutes) with large contexts (300–430k input per child session).
3. A monthly — not 5-hour or weekly — limit (`limitName: monthly`,
   `resets in 10d 20h`), so the burst was the tripwire, not the whole load.

Correlation vs causation: the 22:10 burst immediately precedes the 22:22
rejections (strong temporal correlation, shared workspace/limitName).
Proven cause of the *monthly* exhaustion is cumulative Go token volume;
the burst is proven to have triggered the observed rejections, not proven to
be the majority of monthly use (provider meter required for that).

## 4. Uncertainty

- No local `allowance` column exists, so per-session allowance attribution is
  **estimated from volume**, not authoritative.
- Sessions outside the 18:00–01:00 window also drew from the same monthly
  allowance (a prior `go-limit` event occurred 4 Nov 2026).
- Direct non-OpenCode API calls would not appear here; they remain
  *unattributed* until provider logs are compared.
- Dollar totals ($2.36 Meta + $0 Go in-window) must not be read as allowance
  percent.
