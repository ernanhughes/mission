# W3-COVERAGE-REPORT — Deterministic triage + extraction (w3_full, $0)

Scope: 147 ai sessions / 6,390 messages / 7,959 signals / 30 episodes /
73 linked commits (same denominators as W2; exclusions: none — every session
was triaged, and exclusions would be reported here, not silently dropped).

| Classification | Sessions | Share | Next step |
| -------------- | -------- | ----- | --------- |
| TRIVIAL_INTERACTION | 90 | 61% | No further action (probe pattern, deterministic) |
| INSUFFICIENT_EVIDENCE | 26 | 18% | Retained as unknown; re-triage on new evidence |
| SUBSTANTIVE_CANDIDATE | 21 | 14% | Covered by W2 episodes; W4 input |
| NEEDS_SEMANTIC | 10 | 7% | Bounded model queue (≤10 calls, within cap) |
| AMBIGUOUS (model-queued) | 0 | 0% | Claim-only sessions all carried file/sha context |

Coverage before triage: 21/147 sessions homed (14%), 94.6% of messages in
signal-bearing sessions. After deterministic triage: 111/147 sessions
explained without any model call (90 trivial + 21 substantive); 26 retained
as known-unknowns; 10 queued for judgement. No session was excluded from any
denominator.

Deterministic extraction: 26/26 task episodes got inferred objectives; 1,202
claims preserved with locators; 0 requirements invented (explicit abstention).
Model-backed requirement drafting is the only remaining gap and is gated on
the governed route (≤10 queued + spares fit the 20-call cap).
