# W4-PERSISTENCE-REPORT — Additive 044, ledger as evaluation cache

Migration `044` dual-file (`.sql`/SQLite + `.pg.sql`/operational delta),
version 44, same runner semantics as 041–043 (fresh PG: ORM baseline + mark;
existing PG: pg delta only; pattern validated for 041–043 on simulated
pre-existing schemas). `IF NOT EXISTS`, no ALTERs, no destructive statements.
New tables: `wo_requirement_assessments` (+index), `wo_claim_verifications`
(`UNIQUE(claim_id, method, evaluator)`), `wo_episode_assessments`,
`wo_findings` (+index), `wo_eval_runs`.

The shared `wo_extraction_runs` ledger doubles as the evaluation budget
ledger (schema `w4-eval-v1` rows carry cost/tokens/latency; cap and cache
checks read it). Growth is linear in verdicts; evidence bodies are never
stored — only refs, digests and redacted excerpts (≤2000 chars rationale,
≤500 chars titles).

Operational `mc` untouched (scratch pilots only); 044 applies automatically
on next authorized backend start alongside 041–043. Full-backend regression:
164-test focused/neighbour set green in-process; full suite re-running on the
stable tree (prior run: 970 passed / 1 failed on the migration-version
assertion due to a mid-run test edit race — the same file passes standalone
and in every focused combination; rerun will confirm).
