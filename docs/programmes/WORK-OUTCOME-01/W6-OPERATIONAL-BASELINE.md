# W6-OPERATIONAL-BASELINE — Live DB re-verification (2026-11-24)

Method: read-only SQL against operational `mc` (schema v46). No writes.

## Verified counts

| Table | Rows | Reported W5A | Delta |
| ----- | ---- | ------------ | ----- |
| wo_observation_runs | 1 | 1 run | match |
| wo_episodes | 31 | 31 | match |
| wo_episode_associations | 291 | 291 | match |
| wo_triage_results | 151 | 151 sessions | match |
| wo_objectives | 27 | 26 | +1 (see below) |
| wo_requirements | 0 | 0 | match |
| wo_claims | 1267 | 1267 | match |
| wo_claim_verifications | 1267 | 1267 | match (all `reported_only`) |
| wo_requirement_assessments | 0 | 0 (implied) | match |
| wo_episode_assessments | 126 | 126 | match |
| wo_findings | 278 | 278 | match |
| wo_eval_runs | 126 | — (not reported) | informational |
| wo_extraction_runs | 36 | 6 semantic + deterministic | consistent |
| wo_checkpoints | 2 | — | informational |

Findings: 217 `unsupported_claim/suspected` (78.1%) + 61
`verification_gap/suspected` (21.9%). Zero resolved, zero confirmed —
all open/suspected. No verified-complete episodes.

## Delta 1: 27 objectives vs 26 reported

AI-CORE-06 carries two objectives: the standard inferred
"Achieve AI-CORE-06" plus one `explicit_user` objective
("Check what's left to finish the implementation.") recovered by semantic
extraction. All other 25 task episodes carry exactly the inferred
identifier-objective. Five non-task episodes (3 chain, 1 cluster,
1 unresolved) carry none. Reported "26" counted inferred only.

## Delta 2: 126 assessments for 30 distinct episodes

`wo_episode_assessments` holds 126 rows over 30 distinct episode_ids
(4–5 per task episode; top: AI-CORE-01/02/03/04/05/06 with 5 each).
The single unassessed episode is `ep:unresolved:Projects_ai`.
`wo_eval_runs` likewise holds 126 rows: each evaluation run appends an
assessment row rather than overwriting. This is legitimate assessment
history (initial deterministic pass + merge-corroboration re-run +
post-clean re-evaluation), not 126 unique episodes. The UI overview
uses the latest assessment per episode (30 assessed + 1 unevaluated = 31).

## Triage mix (live)

`wo_triage_results`: 151 rows. Classification breakout matches W5A
(90 trivial / 26 insufficient / 23 substantive / 10 queued per W5A;
W3 pilot reported 21 substantive — the +2 is episode-growth, both
numbers preserved as-written).

## Claim verdicts

All 1,267 claim verifications are `reported_only`. Zero requirements
means zero requirement assessments. Zero verified-complete follows
mechanically: completion requires verified requirements, of which there
are none. This is the W6A problem statement, confirmed live.
