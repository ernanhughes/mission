# W7-AFFECTED-EVALUATION-RECONCILIATION — W6 fixes traced to rows

## Fix 1: bare-SHA auto-links (evaluate.py `_auto_link`)

Defect: mechanical `git_commit` links stored bare SHAs; resolver compares
against full `uid:sha` target_refs → every mechanical link unresolvable →
silent `insufficient_evidence`. Fixed in W6 (full-ref mapping + regression
test); verified operationally.

Affected set (exhaustive — auto-link only fires when requirement text
carries a hex string AND the episode has commit assocs; only W6A-created
requirements qualify):
- 2 link rows (2026-11-24T22:08:22, method deterministic): bare
  `f2aeea0…`, `22299e8…` on requirement c578e9ec — superseded, preserved.
- 2 repaired rows (22:10:01): full `git-78e0…:sha` refs — resolving.
- 13 requirement assessments (22:07:27–22:08:22) reading
  insufficient/not_satisfied on unresolvable links — superseded by the
  22:10:01 + 22:10:36 rounds (satisfied_*), all 27 rows preserved.
- Claim verifications NOT affected (50× `reported_only` for 05):
  `verify_claim_deterministic` matches by substring, which worked on bare
  SHAs — only requirement-evidence resolution was broken.

Repaired associations: 2 full-ref links now resolve; newly corroborated
claims: 0 (claim layer was never broken — no false repair claimed).
Remaining unsupported claims: unchanged (still lack SHAs/push/test
records — the fix repairs the mechanism, not the missing evidence).

## Fix 2: recon cross-scope collision (episodes.py `_persist`)

Defect: upsert scoped by project_key; same ids under another scope
string → bulk-INSERT PK collision. Operational impact: NONE — the W5A
backfill used one consistent scope; the failure manifested only on
scratch w6e with a mismatched scope probe. Fixed (global id check +
regression test); replayed scratch passes idempotent (pass1/pass2
identical effect, 7–8s).

Targeted invalidation used: none required operationally (no corrupt
rows exist); the guard prevents future occurrences. No ecosystem rescan
performed or needed.
