# MC-COST-01 — OpenCode Cost Forensics

Read-only investigation against `C:\Users\ernan\.local\share\opencode\opencode.db`
(1.5 GB, live WAL). Opened strictly `mode=ro` (`sqlite3.connect(f"file:...?mode=ro")`);
no writes, checkpoints, vacuums or migrations performed. Prompt bodies, tool
responses, API keys and secrets were never exported.

## 1. Actual schema (observed 23 Nov 2026)

`sqlite_master` tables:

- `project(id, worktree, vcs, name, ...)` — 573 rows. `worktree` is the
  filesystem root (e.g. `C:/Projects/mission`); `name` is often NULL.
- `project_directory` — 0 rows.
- `session_v2(id, project_id, parent_id, title, directory, model, agent, cost,
  tokens_input/output/reasoning/cache_read/cache_write, time_created/updated, ...)`
  — 2,872 rows. `time_*` are **milliseconds** since epoch (UTC).
  `cost` is REAL (balance charge). `model` is JSON text
  (`{"id":...,"providerID":...,"variant":...}`).
- `session_message(id, session_id, type, seq, time_created, time_updated, data)`
  — 139,324 rows. `time_*` ms. `data` is JSON text; large prompt/tool bodies
  live here, so aggregations must avoid returning bodies.
- `session_part` — 0 rows. `event` — 0 rows.
- `session_inbox` — 73 rows. `job` — 0 rows.
- `kv`, `migration` (62 rows), `account`, `account_state`, etc. present but
  out of scope for cost.

Indexes: `session_v2_project_idx`, `session_v2_parent_idx`,
`session_message_session_seq_idx` (unique), `session_message_time_created_idx`.

Message types observed: `assistant` (127,487), `user`, `system`, `synthetic`,
`idle`, `model-switched`, `agent-switched`, `compaction`, `location-switched`.

## 2. Where cost and usage live

Per-assistant-message JSON (`session_message.type='assistant'`):

```json
{
  "time": {"created": 1795385403051, "firstToken": ..., "completed": ...},
  "agent": "build",
  "model": {"id": "deepseek-v4.1-flash", "providerID": "opencode-go", "variant": "max"},
  "content": [...],
  "finish": "tool-calls",
  "cost": 0,
  "tokens": {"input": 7724, "output": 160, "reasoning": 0,
             "cache": {"read": 1920, "write": 0}}
}
```

- `cost` = **balance charge in USD**. `0` for Go usage within allowance and
  for free models.
- `tokens` = billed tokens for that request; `input` excludes cache reads/writes
  per provider docs; `output` includes reasoning.
- `session_v2.cost` / `tokens_*` are **rollups** that equal the sum of that
  session's assistant-message values (verified: target session
  `ses_dfab0da59ffeWhe4sDDssnI1YM` sum = `0.044254302`, rollup = `0.044254302`).

What is **not** retained locally:

- `opencode.allowance` (Go monthly-limit dollars) — provider response only.
- `opencode.list_cost` (model-price estimate) — provider response only.
- `opencode.billing_source` (`free`/`balance`/`go`/`go-plus`/`byok`) — provider
  response only.

Verified by inspecting full JSON keys for Go and Meta messages: top keys are
`time/agent/model/content/snapshot/finish/cost/tokens` (plus `native` for Meta).
No `opencode.*` allowance fields are persisted. The string `opencode` only
appears in `providerID: opencode-go`.

Consequence: **summing local `cost` tells the balance story, not the Go
allowance story.** Go consumption must be inferred from request volume, input
size and cache behaviour, or read from the provider meter
(`GET https://opencode.ai/inference/go/v1/usage`).

## 3. Key forensic numbers (18:00 UTC 22 Nov → 01:00 UTC 23 Nov)

Window: `1795370400000` → `1795395600000` ms.

- Assistant messages in window: **3,862**.
- By provider (local records):
  - `meta/muse-spark-1.3-contributor`: 2,129 calls, cost **2.359663**,
    in 5,871,236, out 687,512, cache_read 778,690,428.
  - `opencode-go/deepseek-v4.1-flash`: 1,675 calls, **cost 0**,
    in 3,532,015, out 485,379, cache_read 523,609,088.
  - `opencode/nemotron-3.5-super-vl-free`: 58 calls, cost 0.
- Top sessions by count include `ses_e099f6b5...` (Praxis, 813 Go calls,
  cost 0), `ses_dfc18c38...` (ALIVE, 646 calls, cost 0.815),
  `ses_e0109b51...` (Inspect, 372 calls, cost 0.543),
  `ses_dfc4c24e...` (Mission, 324 calls, cost 0.316).
- Research session `ses_dfab0da59ffeWhe4sDDssnI1YM` (Mission book-pipeline):
  109 calls, cost 0.044, in 735k, cache_read 23M; plus 4 parallel child
  subagents (148/127/105/93 calls, each cost 0, combined in ~1.5M,
  cache_read ~112M).
- Failures in window: `idle` 212 total, of which `provider.go-limit` rejections
  at 22:22:16–22:24:29 UTC (5 records) and `provider.no-route` for free models
  (nemotron/space-bunny); `synthetic` subagent Go-limit errors mirror the same
  burst.

## 4. Cost semantics (verified against docs 23 Nov 2026)

- `https://opencode.ai/docs/console/api/inference` § Cost:
  `cost` = balance charge (`0` for Go within limits and free models);
  `opencode.billing_source` ∈ free/balance/go/go-plus/byok;
  `opencode.list_cost` = model-price estimate; `opencode.allowance` = Go-limit
  dollars; `opencode.tokens` billed with `input` excluding cache.
- `https://opencode.ai/docs/console/go/`:
  Go/Go Plus/Teams share one allowance; 5h = 20%, weekly = 50%, monthly resets
  each paid period; switching models draws from the same allowance; current
  Pi builds send session info, older installs need updating; clients must send
  stable `x-opencode-session` for routing/prompt caching.
- Local DB stores only `cost` + `tokens`. Without `allowance`/`billing_source`,
  the dashboard must label dollar figures as **recorded** (authoritative for
  balance, estimated for BYOK) and **unavailable** for allowance, never convert
  dollars → allowance percent without a model-specific rule.

## 5. Gaps

- Provider-side request logs (with `allowance`, `billing_source`, `list_cost`)
  were not available for historical calls; no authoritative allowance
  attribution per session exists locally.
- Direct application → inference API calls (if any) bypass OpenCode sessions and
  leave no local rows; they appear only as *unattributed* provider usage.
- `cache_write` is 0 for all inspected Go messages; write-window semantics
  (`cache_write_5m/1h`) are provider-side only.
