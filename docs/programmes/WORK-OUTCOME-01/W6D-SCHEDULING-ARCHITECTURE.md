# W6D-SCHEDULING-ARCHITECTURE — Why no new scheduler

Decision: reuse the existing `MaintenanceService` pattern (settings gate
+ asyncio loop + run ledger) rather than introducing cron/APScheduler/
Celery. Concretely for W6: NO timer loop was started anywhere. The
governed pass exists as directly invocable `run_pass` (manual Controls
buttons + recorded scripts); the scheduling *design* is a disabled
setting (`wo_auto_enabled`, default off) plus documented intervals.

Proposed intervals (not activated): deterministic observation 15 min,
semantic queue hourly (only if a governed free route is up and budget
remains), daily reconciliation summary. Suggested, not fixed; operator
conventions win. Rationale: different cadence/budget/locking from the
publication loop, so a shared timer would couple unrelated work; a
separate loop on the identical pattern is extension, not competition —
and it stays off until W6E acceptance.

Overlapping runs: single-flight (one pass per process; enabled-flag
check + run-row status). Retry: outages recorded blocked/failed with
error text, never retried blindly. Manual invocation always available
independent of any timer or model availability (deterministic path
never needs a model).
