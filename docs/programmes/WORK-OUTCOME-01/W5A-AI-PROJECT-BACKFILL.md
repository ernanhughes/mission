# W5A-AI-PROJECT-BACKFILL — What was populated, honestly counted

Scope: `C:\Projects\ai` only. Live source DB (147 sessions at pilot time,
151 observed at backfill — the source grows; both numbers recorded, neither
adjusted to match).

| Stage | Result |
| ----- | ------ |
| Observe (W1) | 151 sessions, 7,067 messages, 6,681 new signals |
| Reconstruct (W2) | 31 episodes, 291 associations, 126 unresolved |
| Triage (W3) | 90 trivial / 26 insufficient / 23 substantive / 10 queued |
| Deterministic extraction | 26 objectives, 1,267 claims, 0 requirements (abstained) |
| Semantic extraction (6 episodes) | 0 usable requirements (paraphrase filter held) |
| Deterministic evaluation (all 30) | 126 episode assessments, 1,267 claim verifications |
| Findings | 278 (61 verification_gap + 217 unsupported_claim) |

Denominators preserved: every count above is reported against the observed
147/151-session base. No backfill of any other project. No fabricated rows:
every `wo_*` row traces to a live source observation or a deterministic rule
application (semantic rows carry evaluator identity + cost).
