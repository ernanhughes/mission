# W6C-INCREMENTAL-OBSERVATION — Reuse, bounds, demonstration

## Existing infrastructure discovered (§13)

- Observation: `WorkObservationService.run_observation` — bounded pass
  (message/session limits), HWM checkpoints (`session_updated`,
  `message_created`, 5-min overlap), advance-on-success, idempotent
  replays, read-only OpenCode source. No rescan: checkpoints gate.
- Reconciliation: `EpisodeService.run_reconstruction` — stable episode
  ids, supersession retires (valid=0) without deleting history.
- Scheduling: publication `MaintenanceService` — asyncio loop, 60s
  interval, `pipeline_auto_enabled` setting gate, run ledger, inert
  until enabled. **Reused as the pattern; no new scheduler introduced.**
- Gaps closed by W6: per-episode freshness/queue (`wo_eval_state`,
  `staleness.py`) and the governed pass (`continuous.py`,
  `run_pass`) did not exist.

## What was built (no competing scheduler)

`continuous.run_pass`: observe → reconstruct → staleness-mark →
queue-select (≤10/ep, deterministic only unless explicitly allowed) →
evaluate queued → group refresh. Single-flight by construction
(one pass at a time; overlapping-run prevention via the enabled flag +
run rows). Manual invocation is the supported W6 operation; any timer
stays disabled (see W6D-SCHEDULING-ARCHITECTURE).

## Demonstration (scratch DB + tests, NOT operational writes)

- Correct checkpoints / no rescan / idempotence: covered by W1
  checkpoint tests + `run_pass` tests with fake services (queued episode
  evaluated once; outage recorded as blocked, never raised).
- No duplicate episodes/findings: fid dedup unchanged; group upserts
  idempotent (operational re-runs: 0 created, 0 members on replay).
- Targeted staleness: 6 tracked reasons only; unknown reasons rejected;
  a repo-wide commit never invalidates unrelated episodes (only linked
  revisions mark).
- Safe interruption/restart: run rows carry failed status + error;
  refresh clears staleness only on fresh assessment.

Live-source incremental runs against operational rows are deferred to
W6E operator decision (checkpoint mechanics proven; operator data
untouched beyond authorized W6A/W6B passes).
