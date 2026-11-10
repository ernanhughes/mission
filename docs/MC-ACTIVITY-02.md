# MC-ACTIVITY-02 — Daily Project AI Review

## 1. Architecture / reuse summary

Daily project review is a thin extension of MC-ACTIVITY-01, not a second system.

**Reused, not rebuilt:**

- `activity_git/service.py` — `GitActivityService` owns the new daily scope (`daily_projects`, `daily_scope_commits`, `build_daily_prompt`, `request_daily_review`). Existing `file_diff` (first-parent), `redact_secrets`, `_read_current_context` / `context_file_at`, `request_review` / `execute_review`, and `git_reviews` persistence are reused. No new scanner, registry, or inference gateway.
- `git/history.py` — read-only Git plumbing only. Daily diffs reuse `file_diff`; no fetch/pull/checkout paths were added.
- `research/inference.py` — `discover_local_models` + `complete_local_chat` remain the sole execution path. Daily execution reuses `execute_review` with mode-specific system prompts. Loopback enforcement and fail-closed behavior are unchanged.
- `api/git_activity.py` — new `/daily/*` routes follow the existing FastAPI conventions and `_review_read` shape.
- `models.py` — no migration. Daily reviews persist as `git_reviews` rows with `review_type="daily"`; the day scope (`daily_date`, `timezone`, `daily_mode`, `snapshot_fingerprint`, `commit_shas`, coverage) lives in `evidence_coverage` JSON. Owner feedback stays in `git_review_feedback`.
- Frontend idioms — `useApi` + `apiPath`, `Section/Stat/Tag/Modal`, `copyText`, existing Activity visual language. The per-commit timeline and range prompt are untouched.

## 2. Files changed and why

| File | Change |
| --- | --- |
| `backend/mission_control/activity_git/service.py` | Day helpers (`_validate_day/timezone/mode`, `_day_bounds_exclusive`, `_snapshot_fingerprint`), `daily_projects`, `daily_scope_commits`, `build_daily_prompt` (full-manifest, budgeted diffs, explain/review objectives), `request_daily_review`, `request_review` daily passthrough, `execute_review` mode-aware system prompts + Summary verdict for explain. |
| `backend/mission_control/schemas.py` | `GitReviewCreate` gains optional `daily_date/timezone/mode`; new `GitDailyPromptRequest`, `GitDailyReviewRequest`, `GitDailyProjectRead`, `GitDailyProjectsRead`. |
| `backend/mission_control/api/git_activity.py` | `GET /daily/projects`, `POST /daily/prompt`, `POST /daily/reviews`, `GET /daily/reviews`; `POST /reviews` forwards daily fields. |
| `frontend/src/types/api.ts` | `GitDailyProject(s)`, `GitDailyPrompt` types. |
| `frontend/src/pages/ActivityPage.tsx` | `DailyProjectPanel` (date + All-active/project chips + selected stats + Explain/Review/Create-prompt), `DailyPromptModal` (POST-only, no model call, copy/save, size/coverage), `DailyReviewModal` (mode/model/profile, explicit submit, polling, previous daily reviews). |
| `backend/tests/test_git_daily.py` | 11 focused tests (see §9). |
| `frontend/src/test/DailyReview.test.tsx` | Panel tabs, selection gating, empty-day state. |

## 3. Backend API contract

- `GET /api/git-activity/daily/projects?date=YYYY-MM-DD&timezone=Europe/Dublin` → `{date, timezone, start_ts, end_ts, total_commits, total_repos, partial, backfill_pending, projects[]}`. Each project: `repo_id/repo_name`, day bounds, `commit_count`, `insertions/deletions`, `files_changed` (summed touches; `files_changed_distinct: null`, `files_changed_estimated: true` — per-file names are not indexed), `first_ts/last_ts`, `backfill_complete/index_complete`, `coverage_warning`, `snapshot_fingerprint`, full `commit_shas` (chronological), `review_status/review_id/mode/verdict/completed_at/stale/count`.
- `POST /api/git-activity/daily/prompt` `{repo_id, date, timezone, mode: explain|review, profile: code|prose}` → `{markdown, prompt_hash, diff_hash, context_fingerprint, size_chars, truncated, redactions, redaction_count, coverage, commit_shas, snapshot_fingerprint, date/timezone/mode/profile/start_ts/end_ts}`. Never starts a model call. Same package direct execution uses.
- `POST /api/git-activity/daily/reviews` same + `{model}` → `GitReviewRead` (`review_type: daily`, queued → background `execute_review`).
- `GET /api/git-activity/daily/reviews?repo_id&date&timezone` → prior daily reviews for reopening.
- `POST /api/git-activity/reviews` also accepts `daily_date/timezone/mode` as a narrow adapter to the same pipeline.

Validation: `400/422` on bad date (`YYYY-MM-DD`), unknown timezone (`ZoneInfo`), bad mode, unknown repo, or empty day (`No indexed commits for this project on the selected day`).

## 4. Daily scope and completeness

- Identity: `(repo_id, date, timezone)`. Bounds are calendar midnights in the requested timezone: start-inclusive / end-exclusive. Example: `2026-11-10 Europe/Dublin` → `[00:00, next 00:00)`. DST-safe (2026-03-29 = 23 h, 2026-10-25 = 25 h; verified by test).
- Membership: `GitCommit.committer_ts >= start AND < end`, ordered `committer_ts ASC, sha ASC`. Server-side, no `LIMIT`; the 100-row timeline pagination is never used for scope.
- Manifest: exact SHA list is returned, embedded in the prompt, and stored in `evidence_coverage.commit_shas`. `snapshot_fingerprint = sha256(sorted(shas))[:24]`. A later commit changes the snapshot; `daily_projects.review_stale` flips and the UI warns instead of misrepresenting the old review as current.
- Branches/merges: union of `branches`, `multi_branch` flag, `has_merges` flag. Multi-branch days carry an explicit `do NOT assume one linear cumulative diff` note; merges use documented first-parent diffs. Reachability is preserved per commit but never filters scope.
- Index completeness: `backfill_complete` per repo surfaces as `coverage_warning` + `partial`. A partial review is labelled PARTIAL.

## 5. Prompt generation and large-day handling

- Sections: A. Objective (mode-specific) + Scope/provenance (repo, date/tz/bounds, counts, branches, snapshot, manifest, fingerprints, limitations); B. Project context (historical `AGENTS.md/DESCRIPTION.md` at the latest commit, else labelled working-tree fallback); C. Chronological history; D. Per-commit first-parent diffs; E. Mode instructions + output contract; F. Coverage.
- Budgeting: `total = min(prompt_max_chars, 95_000)` (hard cap keeps the package inside the `prompt[:100_000]` inference slice). Diff budget = `total − 15_000`; per-commit cap = `clamp(diff_budget // n, 2_000, 15_000)`. Commits beyond the budget keep metadata + ≤800-char preview and are listed in `excluded_shas`/`coverage.truncated`. The manifest always lists every SHA; truncation only affects diff bytes and is labelled PARTIAL. Final guard re-truncates only trailing text, never the manifest.
- Secrets: `redact_secrets` before export and before model submission; redaction count surfaced; absolute filesystem paths never appear in markdown (project identified by name + root label).

## 6. Explanation / review execution

- Explain: workstream summary — what was attempted, major changes, how commits connect, functionality added/altered, key decisions, complete vs unfinished, what to know before tomorrow. Verdict stored as `Summary`.
- Review: correctness, cross-commit regressions, architecture/contract consistency, security, missing tests, complexity/duplication, incomplete work, interactions (e.g. A introduces service, B alters contract, C changes caller), priority corrections. Verdict via existing `Accept / Accept with warnings / Request changes / Inconclusive` parser.
- Execution: explicit user submit only; queued → running → completed/failed with polling; result (`summary`, `findings`, `verdict`, `observed_model`, `usage_info`) persists on the same `git_reviews` row; restart-safe (row re-readable); missing model/endpoint fails closed with `error`, never fabricated output.

## 7. Persistent evidence and stale handling

`git_reviews.review_type = "daily"`, `commit_shas = manifest`, `prompt/prompt_hash/diff_hash/context_fingerprint`, `evidence_coverage = {kind: daily-project, daily_date, timezone, daily_mode, snapshot_fingerprint, commit_count, branches, multi_branch, truncated, excluded_shas, …}`. `GET /daily/projects` compares the stored snapshot to the live manifest for `review_stale`. `GET /daily/reviews` reopens exact prior results.

## 8. UI evidence

`Activity → Commits` now shows `Daily Project Review — <pretty day>` above the timeline: date input (defaults to Dublin today) + Today, `All active (n)` + per-project chips (`Name (count)`), selected-project stats (commits, files, review status/stale, snapshot, coverage warning), and `Explain with AI / Review with AI / Create prompt`. Prompt modal previews/copies/saves the exact package with size/coverage/fingerprint; review modal runs the model and lists previous daily reviews. Screenshots were not captured in this headless run; the `DailyReview.test.tsx` render test is the checked-in UI evidence.

## 9. Test results

- Backend: `20 passed` (`test_git_activity.py` 9 + `test_git_daily.py` 11). Daily tests cover: (1) two-repo day tabs/counts, (2) 150-commit manifest, (3) >50-commit prompt inclusion + no review creation, (4) Dublin DST bounds, (5) same-name repos stay separate by ID, (6) timeline-pagination independence, (7) multi-branch warning, (8) snapshot stale, (9) explain/review distinct, (10) prompt makes no model call, (11) fail-closed + stubbed-model persistence + daily listing, (12) missing-model error, (13) secret redaction + no absolute paths, (14) tiny-budget partial coverage, (15) per-commit flow intact (via existing suite), (16) no repo mutation.
- Frontend: `14 files, 54 tests passed` (incl. 2 new daily tests); `tsc -b` + `vite build` succeed (pre-existing chunk-size warning only).
- Lint: `ruff check` clean on touched backend files (one pre-existing `scripts/workbench_browser_test.py` F401 is unrelated).
- Full backend suite was started in background; the two activity suites + migrations/seed are green. Any background full-suite result will be reported separately.

## 10. Git status and uncommitted changes

Modify-only, no commit/push/merge per instructions. Changed: `backend/mission_control/activity_git/service.py`, `backend/mission_control/api/git_activity.py`, `backend/mission_control/schemas.py`, `frontend/src/pages/ActivityPage.tsx`, `frontend/src/types/api.ts`; new: `backend/tests/test_git_daily.py`, `frontend/src/test/DailyReview.test.tsx`, `docs/MC-ACTIVITY-02.md`. No monitored repositories were modified (read-only `git -C … log/show/diff` paths only; verified by mutation test).
