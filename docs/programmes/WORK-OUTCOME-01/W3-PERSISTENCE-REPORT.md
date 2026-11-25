# W3-PERSISTENCE-REPORT — Additive 043, ledger as budget source

Migration `043` dual-file (`.sql`/`.pg.sql`), version 43, same runner
semantics as 041/042 (fresh PG: ORM baseline + mark; existing PG: pg delta
only; verified pattern). `IF NOT EXISTS`, no ALTERs, no destructive
statements. New tables: `wo_objectives`, `wo_requirements`, `wo_claims`,
`wo_evidence_links`, `wo_triage_results` (`UNIQUE(session_id, run_id)`),
`wo_extraction_runs` (`UNIQUE(input_digest, schema, prompt, extractor)` —
idempotence cache and cost ledger in one row).

Growth (w3_full scratch): triage 147 rows + objectives 26 + claims 1,202 +
evidence candidates carried by reference (W2 rows reused, not duplicated).
Excerpts capped (≤800 chars packet input, ≤500 chars claim text, ≤200 chars
signal values); full message bodies never stored.

Operational `mc` untouched (scratch only); 043 auto-applies on next authorized
backend start. 041/042 pre-existing-PG assertion carries to that same start
(W3 §4 gate).
