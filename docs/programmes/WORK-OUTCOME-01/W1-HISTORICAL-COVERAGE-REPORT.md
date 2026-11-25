# W1-HISTORICAL-COVERAGE-REPORT — Message vs part availability

W1 entry requirement §2. Read-only live investigation 2026-11-24
(`mode=ro`, short-lived connections, aggregates + key names only).

## Finding

The 145,505-vs-13,233 "disparity" is a category error plus a recency cut, not
missing history:

- 145,505 ≈ `session_message` rows (all eras). Live recount: 146,004 and
  growing (~100 rows/min during the session — live system).
- 13,233 ≈ `session_part` rows at an older instant. Live recount: 14,404.
- `session_part` was created by migration `20261029_session_part` with **no
  backfill** and is populated only for sessions active since ~2026-11-23:
  96/2,998 sessions (3.2%), ~5,700/133,000 assistant messages (4.3%).
- Assistant text and tool calls live **complete in `session_message.data.content`**
  for all eras (Oct 2 → Nov 24); parts are a second normalized split
  (`text/reasoning/tool`, ~2.4 parts/message) covering the last ~36 h only.
- User content never uses parts (`user_with_parts = 0`); it lives in
  `session_message.data.text` (avg ~27 kB).
- Orphan parts: 0. `event` table: 0 rows (no server audit log — deletes leave
  no trace). `time_archived` set: 442 sessions. Compaction rows: 121 message
  rows; never promoted to `session_v2.summary_*` (all NULL) or
  `session_v2.time_compacting` (all NULL).
- 24 distinct `session_v2.version` values (2.0.21 → 2.4.1); parsers tolerate
  missing keys (`native` vs `rawFinish`, in-flight rows without cost/tokens).

## Availability matrix (for W2+ consumers)

| Era | `session_message` | `session_part` | Rule |
| --- | ----------------- | -------------- | ---- |
| 2026-10-02 → 2026-11-22 | complete (all types) | 0% | read `data.content`/`data.text`; never require parts |
| 2026-11-23 → now | complete | ~98.6% of recent msgs | parts are a supplement, not the source |
| Deleted sessions | unrecoverable (cascade, no tombstones) | same | mark `source_missing`; never treat absence as "no work" |
| Archived (442) | present, `time_archived` set | as above | normal observation |

## Design consequences (implemented)

- Adapter primary source is `session_message.data`; parts supplement recent
  assistant rows only. Coverage endpoint reports both inventories.
- Parsers are key-tolerant; malformed JSON → `parse_error` with locator, never
  silent drop. A message without parts never implies missing content.
