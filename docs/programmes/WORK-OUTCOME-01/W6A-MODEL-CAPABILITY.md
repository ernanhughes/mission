# W6A-MODEL-CAPABILITY — mistral-small re-benchmark (2026-11-24)

Loopback `mistral-small:latest`, $0, temperature 0, bounded packets.
2 packets × up to 2 attempts (first substantive call cold-timed-out at
180s; warm retry 112s; probe 131s cold / 27s warm).

## Results

| Packet | Requirements | Objectives | Latency | Judgement |
| ------ | ------------ | ---------- | ------- | --------- |
| Substantive (user ask + claims + files) | 1, authority `derived`, session cited correctly | text mirrors user ask, `explicit_user` + session source | 112s warm | PASS: sourced, schema-valid, no echo |
| Probe (tool invocation only) | 0 proposed | "Achieve PROBE-2", `explicit_user`, episode-ref only | 27–131s | SPLIT: requirement abstention correct; objective authority over-claimed |

## Calibration gap found and fixed

The probe objective claimed `explicit_user` for an episode-title echo
with no session message — the same failure class as qwen's W4 leak,
narrower. Fix (landed + tested): the model-output validator now rejects
`explicit_user` objectives without a session-kind source
(`test_explicit_user_objective_requires_session_source`). Constraints
tightened, never loosened.

## Standing decision (§6)

- Adequate for *assisted* extraction with validation: sourcing,
  vacuity-free output, abstention on requirements, injection refusal
  (W4) all hold. Latency (~60–130s/call) still bounds unattended use to
  a handful of episodes — consistent with the ≤30-call budget.
- NOT adequate for unattended verdicts: qwen2.5:0.5b remains barred
  from judgements; `derived`-authority requirements are assessable by
  the deterministic engine (reported, never verified) — recorded as a
  W6 follow-up calibration question, behavior unchanged.
- Unattended semantic evaluation stays BLOCKED by default (auto flag
  off, paid budget $0); human-reviewed recovery is the supported path
  until an operator enables the governed queue.
