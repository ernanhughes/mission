# W1-OBSERVATION-ARCHITECTURE — Deterministic foundation, no models

```
opencode.db (RO, WAL-consistent)          git repos (RO plumbing)
        │                                          │
        ▼                                          ▼
work_observation/opencode_adapter.py   git/history.resolve_identity
(parse session_message.data primary;    + existing git_repositories/
 parts recent-only supplement;           git_commits index (no new
 bounded, key-tolerant)                  history system)
        │                                          │
        ▼                                          ▼
work_observation/evidence.py ──→ WorkObservationService ──→ PG wo_* tables
(OBSERVED/CLAIMED/INFERRED/              (runs, checkpoints, signals,
 VERIFIED; redact + excerpt ≤800)         sources; idempotent replay;
                                         checkpoints advance on success only)
        │                                          │
        ▼                                          ▼
workbench_allowlist.py (deny-by-default)  /api/work-observation/* (index-only
(LEDGER_FIELDS projection; no raw        reads; one bounded POST; no UI yet)
 prompts/text/creds/paths)
```

## Principles (enforced by tests)

- Read-only source: `mode=ro` per batch, bounded queries, explicit
  `missing/not_a_file/incompatible_schema/locked` envelopes, never silent zero.
- Content rule: `session_message.data` is the source; parts supplement recent
  rows only. Malformed → `parse_error` with locator, never dropped silently.
- Claims ≠ evidence: test/completion assertions are CLAIMED signals;
  VERIFIED is unproducible in W1 (no independent re-execution exists here).
- Watermarks are `(time_ms, id)` pairs plus a 5-min overlap; stable signal ids
  (`sha1(ref|type|digest)`) make redelivery idempotent; checkpoints advance on
  completed runs only (`locked`/failed runs change nothing).
- Project scoping is SQL-side (`fetch_sessions_matching` JOINs project):
  the global scan cannot serve pilots (first-N global rows may miss the pilot).
- Git reuse: identity via `resolve_identity`, facts from the existing
  `git_repositories`/`git_commits` index; unresolvable → recorded error, never
  treated as branch proof.
- Zero model calls anywhere in this package (no research/inference or Worker
  imports); every envelope reports `model_calls: 0`.
