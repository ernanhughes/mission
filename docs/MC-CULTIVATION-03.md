# MC-CULTIVATION-03 — Project Progress Adapter, Lifecycle and Repository Mastery

## 1. Architecture and reuse report

No new scanner, registry, gateway, or inference. Cultivation reads Activity's
index and the Projects registry; it writes only its own tables.

- **Identity model** — Activity `git_repositories.repo_uid` (worktree-stable,
  move-stable) is the deduplication key; `repo_states.repo_id` points at the
  current Activity row and transparently migrates when Activity reissues an id.
  One uid → one Cultivation item (`repo-<uid>`), renames update the title with
  a `renamed` event instead of a new achievement.
- **New tables (migration 010)** — `cultivation_repo_states` (qualification,
  lifecycle, classification, rationale, evidence, decided_by, accessibility,
  last observed head/count), `cultivation_applications` + `cultivation_app_repos`
  (many-to-many both directions; one released app counts once).
- **Source kind `activity_projects`** — a `cultivation_sources` row scoped by
  explicit `included_roots` (default: all software-category DiscoveryRoots;
  `C:\books` excluded unless explicitly listed). Sync is on-demand only.
- **Service** — `sync_activity_projects` plus repo/application CRUD in
  `cultivation/service.py`; batch aggregates (no per-row git, no filesystem
  walk); write-lock-free sequential session use consistent with the existing
  codebase. The Activity R1 gate (§9) is enforced in code: the adapter touches
  only `git_repositories`, `git_commits` aggregates addressed by full SHA,
  DiscoveryRoots and Projects tables — never `file_diff`, `build_prompt`,
  or short-SHA prefix lookup.
- **Frontend** — skill detail view with repo inventory (filters, pagination,
  bulk qualify), application manager with release evidence, source panel with
  scope editor + sync, disagreement/stale callouts; HUD unchanged apart from
  live data.

## 2. Stable identity and deduplication design

- Worktrees sharing `--git-common-dir` collapse to one repo via `repo_uid`.
- Overlapping roots cannot duplicate: discovery is a single pass over
  Activity rows keyed by uid.
- Moves: row id change under a stable uid migrates judgement + history with a
  `reidentified` event; renames update the item title with a `renamed` event.
- Nested repos and submodules are independent rows (their own `.git`); two
  directories with the same name but different uids never merge.
- Inaccessible or removed repositories: `accessible=false` + `source_removed`
  event; qualifications, memberships and reviews history are preserved.
- Display names are never used as identity keys.

## 3–5. Project source adapter, skills, qualification states

`POST /api/cultivation/sources/{id}/sync` reads Activity's index (no git
processes), classifies each in-scope repo (`discovered | eligible | pending`,
configurable `min_commits`, default 2; never `qualified` automatically),
records per-item `first_evidence_ts` from the oldest indexed commit, links
Projects via `ProjectRepository` paths, and emits one `synced` event only when
the fingerprint changes (idempotent resyncs are silent apart from the sync
timestamp). Software Development skill + Meaningful Repositories (1,000) /
qualified-count Perfect Repositories (100) / Applications associations are
seeded idempotently; unassigned goals keep working.

Qualification ladder: `discovered` (observed) → `eligible` (meets heuristic)
→ `pending` (needs owner review) → `qualified` (explicit owner decision with
mandatory rationale) | `excluded` (rationale required) | `archived` |
`unavailable`. Only `qualified` + membership in the goal counts.

## 6–8. Lifecycle, applications, perfect repos

Application lifecycle: idea → planned → in_development → functional →
testing → released / maintained → archived, stored on the application (not on
shared goal stages). Release requires typed evidence (`versioned_release |
deployment | published | completion_decision | owner_confirmed |
project_record`) with reference or owner note plus a completion date
(backdatable for correct cycle attribution); unrelease withdraws the count
with history kept. Perfect Repositories is a two-step gate (qualified-in-goal
then recorded quality evidence); the count is zero until both exist, and the
UI states this explicitly. No scoring engine, no auto-awards.

## 9. R1 B1/B2 qualification gate

- **B1** (redaction labels leak secret bytes): affects only the review-prompt
  export path. The adapter never builds or transmits review prompts; the one
  surface that returns redaction metadata is untouched by this commission.
- **B2** (short-SHA prefix may resolve the wrong commit): the adapter never
  resolves commits by prefix and never renders diffs; cycle attribution uses
  full-SHA memberships and event timestamps only.
- Relevant boundary still open: revise B1/B2 separately. This commission
  adds no new exposure to either path (verified by import-level test).

## 10. Live inventory and reconciliation report (production-DB copy)

Source: read-only copy of `data/mission_control.db`, full Activity scan on
the copy (85 repos, 11,139 commits, 0 errors, ~50–60 s), then sync.

| Question | Answer |
|---|---|
| Repos in Activity index | 85 (uid- and path-unique: 85/85) |
| In software scope (`C:\Projects`) | 39 → 38 eligible, 1 pending, **0 auto-counted** |
| Books-root repos | 34, excluded from software scope |
| Remaining 12 | `C:\book-projects` root (out of scope by design) |
| With project links | 1 (linkage is genuinely sparse — shown, not hidden) |
| Active in last 7 days | 18 |
| Genuine release evidence | 0 (no applications registered yet — honest zero) |
| Meeting meaningful criteria | 0 qualified (correct: nothing auto-qualified) |
| Duplicates | none (uid + path unique) |
| HUD agreement | HUD shows 0/1000 with the seeded «awaiting inventory» baseline; skill detail shows the 39 discovered explicitly |

Previous 74-repo observation differs because the production index has since
grown to 85 and uses explicit roots rather than estimates — both numbers are
observations, not targets.

## 11. Performance

- First scan (copy): ~50–64 s background; page renders from the index.
- Sync of 85 repos: ~200–250 ms (two batched aggregate queries, no git).
- Repo inventory query (100 rows with evidence): ~50 ms warm.
- Timeline/summary unchanged (3–5 ms warm, per MC-ACTIVITY-02).
- No per-row git subprocesses; incremental fingerprint skips event spam.

## 12. Tests and build results

- Backend: **143 passed** (19 new `test_cultivation_03.py`: worktree/nested/
  moved/dup/inaccessible/partial-index handling, no-second-scanner import
  test, discovered-vs-qualified separation, rationale-gated qualification,
  multi-repo single-count apps, one-repo multi-app, release-evidence
  enforcement, unrelease accounting, perfect-repo evidence gate, bulk qualify
  + filters, manual-hold preservation, stale-source retention, force-push
  unreachability with review preservation, cycle window attribution incl.
  `started_in_window`, rollover lifetime preservation, no-model/no-mutation
  assertions, seed skill/source, restart persistence).
- Frontend: **47 passed** (skill inventory with GET-only check, qualify flow
  with mandatory rationale, disagreement notice; blue-theme bar-state tests).
- `tsc` clean, `ruff` clean, production build succeeds.
- A latent framework quirk was found and isolated during testing: batched
  parent+child inserts in one flush can misorder under the installed
  SQLAlchemy (verified minimal repro); the codebase already flushes parents
  first everywhere, and the new tests follow that convention.
- No model calls anywhere in the new stack (test-asserted); no repository
  mutation (git tables byte-identical before/after sync, asserted).

## 13. Limitations and next steps

- Skill consolidation archives superseded 02 scaffolding skills only when
  untouched and empty; user-customised skills are never moved or archived.
- `total_commits`-style staleness (counters refresh on next sync) is accepted;
  counts shown are labelled from live rows, not cached rollups.
- Repo file list UI pagination is server-side (limit 500); the frontend pages
  at 100.
- Future: Books/Writer adapter (04), Notion cycles (05), quality evaluation
  (06) — the `started_in_window` + evidence fields are the hooks they need.
- Architectural debt (pre-existing, untouched): B1/B2 remain open; SQLite
  UOW parent/child single-flush ordering quirk documented above — worked
  around by convention, not fixed (out of scope).

## 14. Working tree status — no commit, no push, no merge

All work is uncommitted in the working tree per instructions, alongside the
pre-existing unrelated modifications (left untouched) and the uncommitted
MC-CULTIVATION-02 work this builds on. New files: migration `010_*`,
`test_cultivation_03.py`, this report. Modified: `models.py`, `schemas.py`,
`cultivation/service.py`, `api/cultivation.py`, `seed.py`,
`test_migrations_and_seed.py`, `CultivationPage.tsx`, `SoftwareSkill.tsx`,
`types/api.ts`, `styles.css` (blue additions only), `api/client.ts` (`put`
helper), `CultivationPage.test.tsx`. No Activity Git-indexing file was
modified; no production repository was written to (verified by file
timestamps and read-only copy methodology).
