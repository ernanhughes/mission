# MC-CULTIVATION-APPS-01 — GitHub Repository Inventory and Application Progress

## 1. What was built

Mission Control → Cultivation → Software Development now shows a live,
GitHub-backed inventory instead of an unexplained empty state:

- **Applications section** (GitHub inventory · Cultivation): compact summary
  (`discovered | applications identified | completed | published | goal
  progress`) plus a searchable, paginated repository inventory with
  classification, language, visibility, lifecycle, last activity and GitHub
  link. Filters: qualification, classification, lifecycle, visibility,
  search, plus bulk qualify.
- **Explicit Refresh GitHub** action and `POST /api/cultivation/sources/{id}/sync`
  for the seeded `src-github-repos` source. No automatic sync, no startup
  sync: the operator refreshes deliberately.
- **Owner judgement preserved**: classification/lifecycle/qualification edits
  persist across syncs; only `decided_by == 'undecided'` rows receive inferred
  updates, and inference never qualifies anything for counting.
- **Books stay visible, never auto-count**: book-classified repos are part of
  the inventory; only explicit qualification toward a goal (or a released
  application with evidence) moves an achievement counter.

## 2. Reuse (no competing registries)

- `cultivation_repo_states` carries owner judgement for both Activity rows
  (`<activity-id>`) and GitHub rows (`gh-<node-id>`); existing
  `list_repo_states`/`classify_repo`/`bulk_set_qualification` and the
  `CultivationRepoStateRead` API serve both.
- `CultivationItem` (`repo-github:<node-id>`) + `CultivationMembership`
  counting is unchanged: books, experiments and libraries count only when
  explicitly qualified toward a goal.
- `CultivationApplication` + release evidence is the only path to a completed
  application; `link_app_repo` now also accepts `gh-` rows.
- New table `cultivation_github_repos` (migration `032`) is the read-only
  observation cache, keyed by stable GitHub node id (renames keep identity
  with a `renamed` event; vanished repos become `missing`, never deleted).
- New constants are additive: `SOURCE_KINDS += github_repos`,
  classifications `dataset`/`tutorial`, lifecycles
  `unreviewed/concept/prototype/development/working/completed/published/abandoned`.
  Old values and existing goals/pins/archives are untouched.

## 3. Fetch paths (read-only)

- `gh` CLI (`gh repo list`, operator login reused) — default, no token.
- REST `GET /user/repos` with pagination (`per_page=100` until short page),
  using a token from the env var named by `config.token_env`
  (default `GITHUB_TOKEN`). The token value is never stored or returned.
- Failures (`auth_error`, `rate_limited`, `unavailable`) mark the source row
  and keep the last inventory; a single failed sync never deletes rows.

## 4. Live reconciliation (12 Nov 2026, read-only, scratch DB)

Seeded `src-github-repos` synced via `gh` CLI on a scratch copy:

- **306 repositories observed: 183 public, 123 private** (1 archived, 36 forks).
- Inferred: application 155, book 23, experiment 36, tutorial 33,
  unclassified 31, research 8, website 5, infrastructure 6, library 4,
  dataset 5. All start `discovered`/`unreviewed`; 31 uncertain stay
  `unclassified` for review.
- Spot checks: `writer`/`mission`/`bookbuilder` → application;
  `language`/`inference`/`math`/`next-books` → book;
  `zeromodel`/`distillation` → research; `programmer.ie` → website.
- Goals after sync: applications 0/100, repositories 0/1000,
  perfect_repositories 0/100 — inventory is not achievement.

## 5. Tests

- Backend: `backend/tests/test_cultivation_github.py` (18 tests) — 250-row
  import, private/visibility filters, rename identity, failure preservation,
  owner-override survival, book/application counting separation, release
  counting, lifecycle transitions, workspace matching, missing tracking,
  heuristics, auth-error endpoint behaviour, token-env hygiene, REST
  pagination, seed validation, plus one live read-only `gh` check.
- Full backend suite: 254 passed + 18 new; one pre-existing
  `test_quality_campaign` failure also fails on the clean tree (environment
  model reference), unrelated.
- Frontend: 73 passed (incl. new GitHub inventory render + Refresh test);
  `tsc` clean; production build succeeds (also fixed 9 pre-existing
  `WriterPage` null-safety errors that broke `npm run build` on the clean tree).

## 6. Limits / next steps

- Single-label classification; multi-label (book + application) is future work.
- Commit counts for GitHub rows are not indexed (Activity adapter remains the
  local-commit source); `pushed_at` is shown instead.
- No polling schedule: refresh is explicit. A periodic refresh can reuse the
  existing adapter refresh path later.
