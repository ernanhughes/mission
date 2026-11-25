# W2-PERSISTENCE-REPORT — Additive 042, measured growth

Migration `042` dual-file (`.sql` SQLite/tests + `.pg.sql` operational delta),
version 42, same runner semantics as 041 (fresh PG: ORM baseline + mark;
existing PG: pg delta only; verified pattern in W1). `IF NOT EXISTS`,
no ALTERs, no destructive statements. New tables: `wo_episodes`,
`wo_episode_associations` (+2 indexes), `wo_recon_runs`.

Storage (scratch `w2_pilot2`, 147-session scope): `wo_*` (W1+W2) ≈ 213 kB
total for 2,398 signals + 30 episodes + 280 associations + 5 runs — linear in
rows, raw history never duplicated. Unbounded scopes use the same bounded-run
contract as W1 (`limit_sessions`/`limit_signals`, `truncated` flag).

Operational `mc` untouched (scratch only); 042 auto-applies on next backend
start like 041. PG-delta-against-pre-existing validated for the 041 pattern;
042 follows the identical additive shape (fresh-baseline + SQLite suite green;
a pre-existing-PG re-validation happens automatically at next start and will
be asserted in W3 entry).
