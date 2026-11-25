# W2-W1-OBLIGATION-RECONCILIATION — Evidence for the carried/closed items

## 1. Migration 041 on representative pre-existing PG — CLOSED

Simulated v40 scratch PG `w2_pgval` (script `w2_pgval.py`, outside repo):
fresh ORM baseline → `DROP TABLE wo_*` + `DELETE FROM schema_migrations
WHERE version >= 41` + ORM-inserted `projects` probe row → `apply_migrations`.

Result: `upgrade applied: [41]`, `version: 41`, pre-existing row intact,
`wo_signals` readable, reapplication `[]`. Sequencing note: fresh installs
list `[…, 39, 41, 40]` (legacy `.sql` marked before the `.pg.sql` delta runs)
with identical end state; existing PGs apply only `041_work_observation.pg.sql`.
Existing application queries unaffected (additive, `IF NOT EXISTS`, no ALTERs).
Operational `mc` was NOT modified; 041 applies automatically on next backend start.

## 2. Unmatched SHAs — CLOSED (classified, never forced)

Read-only git evidence (no fetch, no writes):

- `0ada120a5e0a393ca94a127af94c031332c58a78` — **cross-repo reference.**
  Valid commit in `C:\Projects\stephanie` (`security: use environment
  references…`, main, 2026-11-06). Absent from ai history (`cat-file`,
  `rev-list --all`, reflog, fsck-unreachable, packed-refs all negative; ai is
  non-shallow, 75 commits). ai docs cite it 13× as the Stephanie source
  (e.g. `docs/research/RANKER-ARCHITECTURE.md:8`). Rule consequence: W2 R3
  resolves SHAs repo-scoped and emits `cross-repo` candidate associations
  instead of dropping or misattaching them.
- `49d89821` — **invalid as commit.** 64-hex embedding-profile identity
  (`AI-CORE-WEB-01B-RESULTS.md:31`) whose 8-char prefix tripped the SHA
  pattern; repo uses sha1 (64-hex impossible); 0 objects share the prefix in
  ai, mission, worker, workbench, stephanie, writer; fsck-unreachable negative.
  Recorded as `unresolved/invalid-reference`. Rule consequence: abbreviated
  SHAs require unique object existence (`git cat-file -e <prefix>^{commit}`)
  before promotion; ambiguous prefixes abstain.

## 3. Independent review — CARRIED (open obligation, external commission)

Still no governed model route (verified: no Muse/Codex route strings in-repo;
`research` offers only `configured-local-openai` + `pi-default`; Worker down).
W2 proceeds deterministically with zero model calls; W2-INDEPENDENT-REVIEW
contains a self-contained external commission (changed files, diffs, test
evidence, acceptance requirements). Implementer self-check is not presented
as independent verification.

## 4. Full backend regression — CARRIED

76 focused/neighbour tests green; full suite deferred per `AGENTS.md` test
policy (short suites named, `long` deliberately deferred). Required before
any integration touching shared infrastructure.
