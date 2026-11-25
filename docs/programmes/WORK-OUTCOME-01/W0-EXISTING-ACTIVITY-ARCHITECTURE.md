# W0-EXISTING-ACTIVITY-ARCHITECTURE — Mission Control Activity today

Source: read-only inspection 2026-11-24. See also `docs/MC-ACTIVITY-01.md`, `docs/MC-ACTIVITY-02.md`.

## 1. Module map (verified)

Backend `backend/mission_control/`:

- `activity/service.py` (88 lines) — `record_activity`, provenance taxonomy, generic `activity_events` log.
- `activity_git/service.py` (1785 lines) — `GitActivityService`: discovery, incremental index + resumable backfill, timeline/summary/daily queries, prompt builders, secret redaction, review orchestration, context inventory/proposals.
- `git/history.py` (361 lines) — read-only Git plumbing only (`rev-parse/for-each-ref/log/show/diff`, `shell=False`, `GIT_TERMINAL_PROMPT=0`, hooks suppressed).
- `api/git_activity.py` (321 lines, `prefix=/api/git-activity`) — roots/scan/repos/timeline/summary/commit/diff/prompt/range/reviews/daily/context routes. Invariant: opening endpoints never starts a model call.
- `models.py` (1795 lines) — `ActivityEvent`, `WorkCheckpoint`, `Task`, `DiscoveryRoot`, `GitRepository`, `GitCommit (repo_id,sha)`, `GitReview`, `GitReviewFeedback`, plus `Project/Repository/ProjectRepository`, `IntegrationExecution`, `ExperimentWorkflow/WorkflowEvent`, technical/quality families.
- `schemas.py` (3245 lines) — `ActivityRead`, `Git*Read`, `GitReviewCreate` (incl. daily fields), `GitDaily*`.
- `persistence/db.py` (145 lines) — PostgreSQL operational via `MC_DSN`; SQLite only for isolated tests/legacy migration. `persistence/migrations.py` (175 lines) — SQLite `NNN_*.sql` once; PG baseline from ORM `create_all` + `*.pg.sql` deltas; `schema_migrations` tracked.
- Migration `007_activity_git.sql` (108 lines) — extends `discovery_roots` + creates `git_repositories/git_commits/git_reviews/git_review_feedback`.

Frontend:

- `frontend/src/pages/ActivityPage.tsx` (1824 lines) — `tab = commits|events`. Commits: presets today/yesterday/7d/30d/custom/all, filters (repo/root/category/author/review/search), summary strip, day-grouped timeline, commit-detail/diff/prompt/review/range/repo/daily modals. Events: `GET /api/activity` + notes.
- `frontend/src/types/api.ts` (2970 lines) — `ActivityEvent`, `GitActivityRoot/Repo/Commit/Timeline/Summary/Review/ScanStatus`, `GitDaily*`.
- `frontend/src/features/project/ActivityTab.tsx` (124 lines) — project-scoped activity.

## 2. How discovery works

- **Curated projects vs observed repos:** `projects/service.py:116 refresh_repositories`, `discovery/scanner.py:87 scan_roots` (bounded BFS, reparse-point skip, stops at repo root) → `repositories` table with `dirty` from `core/git_observe.py:55`.
- **Git index (factual):** `_discover_root` walks `DiscoveryRoot`s (`git_enabled`), `resolve_identity` per `.git` (`repo_uid=sha1(common_dir)[:24]`), `_sync_one_repo` upserts `GitRepository`, skips if `refs_snapshot` unchanged + backfill complete, else `log_recent(30d)` + bodies/stats/branches; `_backfill_page` pages `log --before=<cursor> --max-count 500` until done. `ThreadPoolExecutor(concurrency=8)`, write-lock serialised. Honesty signals: `partial/backfill_pending`, never claims zero when incomplete.
- **Reviews (assessment):** `request_review/request_daily_review` create `GitReview(queued)` deduped by `prompt_hash`, storing `prompt/prompt_hash/diff_hash/context_fingerprint/evidence_coverage`; `execute_review` calls `research.inference` (local/Pi route), parses `Accept|Accept with warnings|Request changes|Inconclusive` + findings. Feedback in `GitReviewFeedback`.
- **Test evidence:** NOT in `git_*`. Separate families: `quality_software/evidence.py` bounded manifest, `quality_software/service.py`, `technical_claims/evidence/verifications`, `quality_evaluations/campaigns`, `integration_executions/workflow_events`. No FK to `git_commits`.
- **Workbench records:** no `workbench_*` execution table. Only `workbench_url` fields, `workbench-server` launch def, read of `.workbench/editorial-decisions.jsonl`. Indexer **excludes** `.workbench`.

## 3. Task / programme identifiers

- `Task (project_id FK, no commit link)`, `Project`, `Repository/ProjectRepository`, `WorkCheckpoint(project_id)`, `ExperimentWorkflow(project_id|repository_path|baseline_commit|result_commit)`, `IntegrationExecution(application_id|action_id|artifact_ref)`, `WorkflowEvent(workflow_id|sequence)`.
- **No** `programme_id/work_episode_id/task_id` on `git_commits/git_reviews`. `evidence_coverage` carries only daily scope + fingerprints. No Task→GitReview join.

## 4. Edge-case representation (verified gaps)

- **Uncommitted:** not indexed. No `status/stash` reader; working tree read only for `AGENTS.md/DESCRIPTION.md` fallback (labelled `working-tree`). `dirty` only in legacy `repositories`.
- **Squash:** invisible — flat `parents/is_merge/is_root`, no `patch-id/Change-Id` link.
- **Rebase/amend/force-push:** detected via `refs_snapshot` change; rewritten SHAs are new rows; old linger `reachable=False` (no GC, no reflog, no old→new map).
- **Cherry-pick:** independent rows; no trailer parsing; no dedupe.
- **Merges:** `is_merge`, first-parent diffs; `branches_for` tip-only so old branch membership incomplete.
- **Cross-repo:** none. All range/daily prompts single-`repo_id`; `snapshot_fingerprint=sha1(sorted shas)` per repo/day only; timeline pagination not snapshot-stable; no multi-repo episode.

## 5. Reusable vs gaps

Reusable: `git_*` schema + ORM + migrations; `git/history.py` helpers; incremental index + backfill + `partial` honesty; `timeline/summary/daily_projects` + `review_stale/snapshot_fingerprint`; prompt builders + `redact_secrets` + `prompt_hash` dedupe; review lifecycle + `requested/observed_model/route/profile/verdict/findings/usage_info` + feedback; `DiscoveryRoot(category|git_enabled)`; context inventory; full `/api/git-activity/*` surface; `ActivityEvent` log; adjacent `tasks/workflows/executions/technical/quality` stores.

Gaps for Work Episodes: no episode entity; no task/programme/workflow IDs on commits/reviews; no uncommitted/stash capture; no rebase/squash/cherry-pick resolution; no cross-repo aggregation; tip-only branches + first-parent merges undercount; test/workbench evidence unlinked; `.workbench` excluded by default.
