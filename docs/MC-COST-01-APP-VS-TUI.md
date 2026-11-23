# MC-COST-01 — Application vs TUI Hypothesis: Verdict

Question: **do application-driven AI calls consume significantly more
allowance than equivalent TUI calls through no price difference?**

## Verdict

**Plausible mechanism, not a price difference. Evidence supports an
orchestration/client-integration effect, not a per-token surcharge.**

- No blanket surcharge for application calls is documented. Go docs price
  tokens per 1M identically across clients; `cost`/`allowance` semantics are
  per-request, not per-client.
- Local records cannot show a price gap: identical DeepSeek V4.1 Flash calls
  record `cost 0` whether launched from TUI sessions or subagents. Any residual
  per-request cost gap would need provider `list_cost`/`allowance` logs, which
  are not retained locally.

## What differs (verified in-repo)

1. **Stable session / prompt caching.**
   Go docs: send stable `x-opencode-session` so routing and prompt caching can
   work. Current Pi builds support session info; older installs need updating.
   OpenCode TUI sessions in the DB show growing `cache.read`
   (1,920 → 370,033 across one session) — caching works when the session is
   stable.
   Mission Control's Pi backend (`backend/mission_control/research/pi_backend.py:155-156`)
   and website evaluator (`websites/evaluate.py:256-260`) invoke Pi with
   **`--no-session` on every call** (fresh process per call, no tools/extensions/
   skills/templates/context). ALIVE tests use the same flag. `--no-session`
   forfeits the stable-session optimisation the Go docs recommend; each call
   resends system prompt (up to 8k) + full prompt (up to 100k) with no reuse.
2. **Request multiplication.**
   The incident's Go burst was 1 parent + 4 parallel `explore` subagents
   (~50 calls/min, each child 93–148 calls, 300–430k input). Even at identical
   per-call price, 5× concurrency with large contexts burns allowance 5× faster.
   Mission daily-review, quality-campaign and cultivation loops share this
   fresh-process-per-call shape.
3. **No local evidence of different provider routing for the same model.**
   `providerID` is `opencode-go` for DeepSeek in both TUI and subagent rows;
   `billing_source` is not stored locally, so a silent `go` vs `byok` route
   change cannot be confirmed or ruled out from the DB alone.

## What would prove/disprove a residual client gap

Compare **normalised** requests for the same model (e.g. DeepSeek V4.1 Flash):
same input/output size, same cache-read/write, same long-context bucket —
then test for a remaining cost/allowance delta by client. Today's local rows
lack `allowance`/`billing_source`/`list_cost`, so this test needs provider-side
logs or new instrumentation:

- log `opencode.allowance`, `opencode.list_cost`, `opencode.billing_source`
  per call (response `usage.opencode`), plus the sent session header and Pi
  `--no-session` flag;
- add an optional, loopback-only Go meter panel (provider `v1/usage`) — never
  as an automated spending control in this release.

## Practical implication

Treat this as an **orchestration problem first, integration second**:

- batch and cache (stable sessions, smaller contexts, fewer parallel agents)
  before suspecting pricing;
- fix `--no-session` where conversation continuity is intended, or document why
  isolation is worth the extra allowance;
- keep the Cost dashboard observational: high-volume zero-cost routes are
  flagged (`zero-cost-volume`, `low-cache-reuse`, `parallel-agents`) without
  claiming a surcharge.

No paid experimental calls were made for this verdict.
