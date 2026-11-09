# MC-ACTIVITY-01 — Unified Project Activity, Git History and AI Review

## 1. Architecture and reuse report

Mission Control owns the activity index and presentation layer. Git repositories
remain authoritative for their own history. Worker remains the preferred
model-execution boundary; no second inference gateway was created.

**Reused, not rebuilt:**

- `activity/service.py` (`record_activity`, provenance taxonomy, `Database.session()` ownership) — root add/remove/history-retain events are recorded through it.
- `discovery_roots` table + `settings/service.py` root validation (`require_existing_directory`, Windows path normalization) — extended with `display_name`, `category`, `git_enabled`, `last_git_sync_at`, `last_git_error` columns (migration `007_activity_git.sql`) instead of a competing registry.
- `discovery/scanner.py` conventions — reparse-point skipping, exclusion patterns, read-only Git observation (`core/git_observe.py` philosophy; all new Git commands use `shell=False`, `GIT_TERMINAL_PROMPT=0`, `GIT_OPTIONAL_LOCKS=0`, `core.hooksPath=` override).
- `research/inference.py` — `discover_local_models` (model catalogue) and `complete_local_chat` (local-only execution, no remote fallback, loopback enforced). Worker was inspected first: its adapter exposes health/availability only and its `direct` executor path is a code-generation experiment route (`workflows/service.py`), not a conversational review route, so the existing local OpenAI-compatible boundary is the smallest compatible execution path. Review identity (requested vs observed model, route `configured-local-openai`) is preserved per review.
- Frontend idioms — `useApi` + `apiPath`, `PageHeader/Section/Stat/Tag/LoadingBlock/ErrorState/EmptyState/InlineError`, `Modal`, `copyText`, existing Activity visual language (`.activity-feed`, `.activity-marker`, provenance badges). The old notes/events view is preserved under a second tab.

**New, narrowly scoped:**

| File | Responsibility |
| --- | --- |
| `backend/mission_control/git/history.py` | Read-only Git plumbing: identity resolution (worktree-aware `repo_uid` via `--git-common-dir`), NUL-safe-ish delimited `log`, batched bodies/stats, first-parent diffs, fingerprints. |
| `backend/mission_control/activity_git/service.py` | `GitActivityService`: discovery, incremental indexing + resumable backfill, timeline/summary queries, prompt builder, secret redaction, review orchestration, context inventory/proposals. |
| `backend/mission_control/api/git_activity.py` | `/api/git-activity/*`: roots, scan, config, repos, timeline, summary, commit detail/diff/prompt, range prompt, reviews, feedback, context. |
| `backend/mission_control/models.py` + `persistence/migrations/007_activity_git.sql` | `git_repositories`, `git_commits`, `git_reviews`, `git_review_feedback` + `DiscoveryRoot` columns. |
| `backend/mission_control/persistence/db.py` | SQLite WAL + 30 s busy timeout so index writers and UI readers coexist. |
| `frontend/src/pages/ActivityPage.tsx` | Unified timeline UI (see §5). |
| `frontend/src/types/api.ts` | `GitActivityRoot/Repo/Commit/Timeline/Summary/Review/ScanStatus/ReviewModelCatalogue`. |

**Deliberate non-goals honored:** no scoring engine (§15 — only observations stored),
no autonomous review orchestration, no repository mutation (verified by test),
no premium/remote fallback (fail-closed), no second project registry.

## 2. Configuration

Activity roots reuse DiscoveryRoot rows. `GET /api/git-activity/roots` merges the
stored `display_name`/`category` (seeded: `Projects/software`, `Books/books`,
`Book Projects/books`). Add/remove/enable/pause-git-sync from Activity →
Configure. `DELETE ...?retain_history=true` (default) stops monitoring but keeps
indexed history and reviews; `retain_history=false` deletes them explicitly.
Scan settings live in Setting `activity_git`
(`recent_days`, `max_depth`, `max_repos_per_scan`, `diff_max_bytes`,
`backfill_page`, `prompt_max_chars`, `concurrency`); content exclusions combine a
hard-coded generated-dir set (now including `.workbench`, `.roborev`, `.vscode`,
`.idea`, `.tox`, `site-packages`) with the user's `discovery.exclusions` globs.

## 3. Project inventory (live, 2026-11-09)

Read-only smoke scan of the real roots (`scripts/smoke_git_activity.py`, temp DB):

- `C:\Projects` + `C:\books` → **74 repositories**, 0 errors, first scan **44 s**.
- Excluded as generated: ~5,475 `.git` dirs under `C:\Projects\workbench\.workbench`
  (test-run fixtures), plus `node_modules`/`.venv`/etc. via exclusions.
- Context readiness is reported per repo (`ready/partial/missing/stale`);
  e.g. fixture repos show `has_agents`/`has_description` flags in
  `GET /api/git-activity/repos`.

## 4. Activity index

- First scan: bounded recent window (30 d, ≤2000 commits/repo), then one
  historical backfill page (500) per repo per scan — resumable via
  `backfill_before` cursor; restart-safe.
- Incremental refresh: per-repo `for-each-ref` fingerprint; unchanged repos are
  skipped without a log walk. New commits detected by SHA-set difference;
  reachability recomputed only when refs changed (rebase/force-push safe:
  unreachable commits are marked, never deleted; their reviews survive).
- Writes from the worker pool are serialized through a write lock with
  busy-retry; Git subprocess work stays parallel. SQLite lock errors: **0** in
  the live scan (previously 2/500 before the fix).
- Numbers (live): 8,098 commits indexed; Today 62 commits / 6 projects;
  week 585; backfill pending 5 repos → timeline and summary report
  `partial: true` instead of claiming zero activity.

## 5. Activity GUI

`/activity` → **Commits** tab (default): Today/Yesterday/7 d/30 d/Custom presets,
filters (project, root, category, author, branch, review status, text search),
summary strip (commits today, active projects, week, reviewed, index status),
day-grouped newest-first timeline with per-row time/project/subject/SHA/refs/
stats/review badge and **View diff / Copy review prompt / Review with AI**
actions, multi-select range review, commit-detail modal (message, parents,
files, stats, diff, reviews), diff viewer, prompt modal (size/truncation/
redaction state, copy + save `.md`), review modal (local model catalogue,
profile, explicit submit, progress, verdict/findings, owner feedback),
per-project panel (path, root, branch, context readiness, context proposal
workflow, recent commits), root-management modal, scan status banner.
**Notes & events** tab preserves the previous Activity functionality.
Opening Activity starts no model calls (only index queries; the models
catalogue loads on review-modal open).

## 6. Review export

Real artifact: `docs/acceptance/mc-activity-01/review-prompt-example.md`
(generated by `scripts/gen_prompt_example.py`, no model call). Contains review
objective, project context (historical `AGENTS.md`/`DESCRIPTION.md` at the
commit revision, labelled as such), commit metadata, exact first-parent diff,
review instructions and the output contract, plus coverage/limitation notes
(size, truncation, redactions). Fixture secret `API_KEY=…` is redacted
(`[REDACTED-SECRET]`, redaction count shown); automated check asserts the raw
secret never appears. Absolute filesystem paths are not exported (project
identified by name + root label; paths stay server-side).

## 7. AI review integration

`POST /api/git-activity/reviews` → queued → background `execute_review` →
`completed`/`failed` (never invented). Single and range reviews share the path.
Live evidence (Ollama loopback, `mistral-small:latest`, temp DBs):

- `rev-21a936c00f1f4383`: **completed**, verdict **Request changes**,
  observed model `mistral-small:latest`, route `configured-local-openai`,
  7 parsed findings — correctly flagged an unguarded `div` (ZeroDivisionError),
  cited `calc.py:4`, listed missing tests, stated `Tests not executed: None`
  honestly as unexecuted.
- Local-only enforcement: non-loopback endpoints fail closed
  (`test_review_request_requires_model_config` proves a missing endpoint yields
  `failed` + error, never fabricated output). No premium/remote fallback exists.
- Local model latency varies (cold loads, long structured outputs); the review
  lifecycle is asynchronous so the page never blocks. Timeouts are recorded as
  `failed`, distinct from completed reviews.

## 8. Persistent review evidence

`git_reviews` rows are immutable evidence (prompt/diff/context fingerprints,
scope, verdict, findings, usage, timestamps); owner feedback lives in
`git_review_feedback`. Proven by `scripts/prove_restart.py`: a fresh process
re-opened an earlier demo DB and read back the completed review, its
fingerprints, evidence coverage and the exact reviewed commit
(`restart-persistence: OK`).

## 9. Project context management

`GET /api/git-activity/context/{repo}` reports `AGENTS.md`/`DESCRIPTION.md`
presence, nested `AGENTS.md` files and `ready/partial/missing/stale` status
(staleness is a labelled heuristic: untouched description + active repo).
`POST .../propose` drafts `DESCRIPTION.md`/`AGENTS.md` from README, manifests
and recent subjects (deterministic template, no inference); `POST .../apply`
requires `confirm: true` and writes exactly one file inside the repo, recording
an activity event. Tested: proposal never writes without approval; unknown
kinds/empty content/confirmation-less applies are rejected.

## 10. Verification report

- Backend: **95 passed** (`pytest -q`; includes 8 new `test_git_activity.py`
  tests: roots validation, scan→timeline→detail→diff→prompt, incremental
  no-op + new-commit, secret redaction, fail-closed review, no-mutation,
  context inventory/proposal, generated-dir exclusion; plus updated
  `test_migrations_and_seed.py` for migration 7).
- Frontend: **34 passed** (`npm test`), `tsc --noEmit` clean, `npm run build`
  succeeds (pre-existing chunk-size warning only).
- Lint: `ruff check backend scripts` clean.
- Scan performance: fixture repos <1 s/scan; real roots first scan 44 s for
  74 repos/8,098 commits (background, UI usable from the index immediately;
  warm timeline queries are index-only).
- No-mutation: fixture repo `HEAD` + `status --porcelain` identical before/after
  scans (test); live scans use only `rev-parse/for-each-ref/log/show/diff`
  (no fetch/pull/checkout/write paths exist in `git/history.py`).
- Security: no shell construction from user input (fixed argv), SHA validation,
  path containment within enabled roots, secret redaction before copy and
  before model submission, prompt-injection posture (repo text treated as
  evidence; contract forbids new permissions), absolute paths excluded from
  exported prompts, no credentials in artifacts (API keys live only in env).
- Known gaps: discovery truncates past `max_repos_per_scan` (now surfaced via
  `truncated`, default 2000); backfill of very large histories takes several
  scans (progress exposed); review verdict parsing is heuristic and stored
  alongside the raw model text; Worker `direct` executor intentionally not used
  for conversational review (see §1); local-model latency varies — reviews are
  async and never block the timeline.

## Git state

- Branch: `main`, HEAD `a2ba95f` ("Add research export and contextual local chat").
- Working tree contains **pre-existing modifications unrelated to this
  commission** (e.g. `README.md`, `config.py`, `BooksPage.tsx`, `mission.cmd`;
  the tree was dirty before MC-ACTIVITY-01 started). Files changed by this
  commission (new: `backend/mission_control/{git,activity_git}`,
  `api/git_activity.py`, migration `007`, `test_git_activity.py`,
  `docs/MC-ACTIVITY-01.md`, `docs/acceptance/mc-activity-01/`,
  `scripts/{smoke_git_activity,gen_prompt_example,demo_live_review,prove_restart}.py`;
  modified: `main.py`, `models.py`, `schemas.py`, `persistence/db.py`,
  `persistence/seed.py`, `tests/test_migrations_and_seed.py`,
  `ActivityPage.tsx`, `types/api.ts`, `styles.css`).
- Line endings in edited files match the working tree (LF); CRLF warnings are
  repo-wide autocrlf behavior, not introduced here.
- **No commit, push or merge performed** — left for explicit owner
  authorization. No scanned repository was modified (only the Mission Control
  working tree gained new implementation files).
