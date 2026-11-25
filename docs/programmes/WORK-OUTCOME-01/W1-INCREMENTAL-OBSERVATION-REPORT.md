# W1-INCREMENTAL-OBSERVATION-REPORT — Watermarks, replay, recovery

Cursors (PG `wo_checkpoints`, per source `opencode`): `session_updated`
(time_updated,id), `message_created` (time_created,id). Each run reads from
`hwm − 5-min overlap`; checkpoints advance to the max observed **only on
`completed` runs**. Signal ids `sha1(source_ref|type|value_digest)` make
redelivery idempotent (verified: repeat run → `signals_new: 0`).

Accounted cases (each a passing test): timestamp ties (stable id order),
late arrivals inside the overlap window, in-place session updates (no dup
signals), interrupted/`locked` runs (checkpoints untouched, run row
`locked`/`failed` — never left `running`), checkpoint recovery across
processes (PG-durable), source replacement (fingerprint refresh on
`wo_observation_sources`), out-of-order delivery (id-ordered fetch),
partial ingestion (`truncated: True` + resume continues, nothing skipped:
fetch is ASC + limit so hwm is the limit boundary), restart replay,
project-scoped resume keys (SQL-side filter keeps `(time,id)` order within
the filtered set). Precision on the "pair" wording: the tiebreak id is stored
and compared but is not a SQL resume predicate — the 5-min overlap rewind is
the correctness mechanism for ties and late arrivals; stable ids make the
resulting redelivery idempotent. No pagination loop on truncated scans
(self-heals via overlap rewind; worth a comment, no behavior change).

Live proof (scratch PG `w1_pilot`, live OpenCode DB): run1 (ai-scoped,
100 sessions/2,000 msgs) → 2,808 signals (2,161 new), `truncated: True`;
replay run → resume + 237 genuinely new (prior run was truncated) / 0 on
exact repeat in tests; checkpoints `(session_updated, message_created)`
persisted; wall 1.7 s; `model_calls: 0`, `model_cost: 0`.
