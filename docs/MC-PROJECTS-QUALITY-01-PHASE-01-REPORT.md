# MC-PROJECTS-QUALITY-01 — Phase 0+1 Report: Baseline + Discovery Reconciliation

Scope chosen: **Phase 0 (baseline) + Phase 1 (read-only discovery reconciliation)**.
No identity cutover applied. No commits, pushes, launches, or unrelated-repo modifications.

## 1. Baseline inventory (verified against `main` @ `3a0a8b6` + working tree)

### Persisted project records
- `Project` (`models.py`, PK `id`): seeded defaults are `language`, `inference`, `math`
  — all `kind=book`, all with a `Book` row (`Book.project_id` unique FK).
- `config/defaults/projects.yaml` confirms the historical picture: book manuscripts
  (`C:\books\language`, `C:\books\inference`, `C:\books\math`) plus one supporting repo.
- `Project` ↔ `Repository` via `ProjectRepository(project_id, repository_id, role)`.
- `Repository.id` (`repository_id()`) = path-hash — **not stable across relocations**.
- `Application` registry links to projects only via `related_projects: list[str]`;
  launch definitions are curated and verified, never auto-generated.

### Discovery / Git identity (already built, reused — nothing rebuilt)
- `discovery/scanner.py::scan_roots`: bounded, cancellable, symlink/reparse-safe,
  stops at repository roots, read-only Git observation post-pass.
- `discovery/classifier.py::classify`: advisory-only evidence + confidence.
  **Limitation found:** the book-signal fires on README keywords, so genuine software
  repos (mission, writer, workbench, …) classify as `book 0.8`. The cutover must
  override this with repository evidence, never with the label alone.
- `activity_git/service.py` (`GitRepository`): stable technical identity
  `repo_uid = git-sha1(casefold(common_dir))`, worktree-aware; `git/history.py`
  is strictly read-only (`rev-parse/log/rev-list/for-each-ref/show/diff` only).
- `api/git_activity.py`: daily reviews + AGENTS.md context proposals already exist.
- `api/inspect.py` + `inspect_snapshots.py`: read-only consumer snapshot;
  `map_inspect_project` maps `writer`/`mission` by identity, rest by
  `repository_path` equality — never display names.
- `cultivation/service.py`: `cultivation_repo_states` keyed by Activity `repo_uid`;
  owner qualification never written back into Activity tables. High scores never
  auto-qualify anything.

### Migration integrity — drift found and fixed
- Tree contained `035_website_post_evaluations.sql` while
  `test_migrations_and_seed.py` asserted `1..34` / `schema_version == 34`.
  Reproduced: `apply_migrations()` returned `[1..35]` and the test failed.
- Fix (same change set, coordinated as the spec requires): test now asserts
  `list(range(1, 36))` / `schema_version == 35`, and the expected-table set gains
  `website_post_evaluations` + `website_post_reviews` (matching `models.py`).
- Next migration, when needed, will be `036_*` with the count bumped in the same commit.

## 2. Live read-only scan of `C:\Projects` (evidence, no writes)

`scan_roots(['C:/Projects'], max_depth=1, timeout 60s, git_timeout 2s)`:
49 candidates, 0 errors, not truncated, 1.2s elapsed.

| Classification | Count | Notes |
|---|---|---|
| `book` (advisory) | 13 | Mostly README-keyword hits on software repos — see classifier limitation |
| `executable_application` | 13 | cocoder, next, work, inspector-adjacent CLIs |
| `research_project` | 6 | ai, inspect, praxis, smarter, zeromodel(×2) |
| `library` | 4 | clipper-ai, cortex, verity, **writer** |
| `supporting_repository` | 3 | fine-tuning, llm-capture, possibility |
| `background_service` | 2 | clearport, stephanie |
| `unknown` | 4 | plain dirs without markers |
| `generated_artifact` | 3 | review packs, worker-smoke (correctly excludable) |
| `experiment` | 1 | spec-gap-experiment |

41 of 49 are Git checkouts (incl. Writer `git-155ab6e…`, Mission `git-6608048…`,
CoCoder `git-cc8bd00…`, Worker, Inspect). 8 have no `.git` (plain dirs / artifacts).
Full per-repo listing is reproducible via `GET /api/projects/reconciliation?live=true`.

## 3. What was implemented (Phase 1, read-only)

**New:** `backend/mission_control/projects/reconciliation.py`
`build_reconciliation(session, software_root=None, live=False)` — zero writes:
- Default root `C:\Projects` (falls back to first enabled `DiscoveryRoot`).
- Splits projects into `software_projects` vs `book_legacy_projects`
  (`kind == "book"` or has a `Book` row). Book records and FKs untouched.
- `unlinked_candidates`: indexed repos under the root with no `ProjectRepository`
  link and no `Application.repository_path` match, plus optional live-scan finds.
- `missing_paths`: project-linked or Git-indexed paths no longer on disk.
- `basename_collisions`: same directory name at different paths (reported, never used as identity).
- `shared_repo_uids`: one `repo_uid` at several paths (worktrees / nested checkouts).
- `git_backfill_pending` / `repositories_never_observed` staleness counters.
- Explicit `notes`: no auto-creation, no launch definitions, basenames are not identity.

**New endpoint:** `GET /api/projects/reconciliation?root=&live=` →
`ProjectReconciliationRead` (`schemas.py`). Registered **before**
`GET /api/projects/{project_id}` so the literal route wins. Starts no model calls.

**Tests:** `backend/tests/test_projects_reconciliation.py`
1. Report shape + book-legacy set ⊇ `{language, inference, math}` + project count unchanged (read-only).
2. Live scan on a fixture root surfaces the unlinked repo and stays read-only.
3. Deleted linked directory is reported under `missing_paths`.

**Fix:** `backend/tests/test_migrations_and_seed.py` — 34 → 35 as above.

## 4. Verification

- New + migration tests: **6 passed**.
- Regression sweep (`book_detection`, `fiction_books`, `identity`, `inspect`,
  reconciliation, migrations/seed): **45 passed**.
- `ruff check` on touched files: one `F841` in `api/projects.py:438`
  (`book_identity_route`) — verified **pre-existing on clean stash**, left untouched.
- No commits / pushes / launches performed. No files outside `mission` touched.

## 5. Compatibility guarantees kept

- Existing `Project` ids, `Book` rows, `Application` launch definitions and review
  history: untouched (report is pure SELECT + filesystem reads).
- Book projects remain first-class records; they are only *listed separately*,
  never deleted or unlinked.
- Discovery creates no launch definitions; `Application` curation stays manual.

## 6. Known limitations / unverified claims

- Classifier `book` labels on software repos are advisory noise, not fact.
- The live scan is depth-1: nested repositories under a repo root need the Git
  activity scanner (`max_depth=4`), not this report.
- Report staleness follows `last_observed_at` / `backfill_complete`; run
  `/api/discovery/scan` + `/api/git-activity/scan` before treating it as current.
- No frontend surface yet; no quality rubric, charter, or improvement loop yet.

## 7. Proposed next milestone (not started)

Phase 1-cutover: explicit, owner-confirmed mapping `Project ↔ repo_uid (+ path)`,
new `036` migration only if a mapping table is needed, book-legacy filter in the
Projects presentation, then Phase 2 workspace tabs reusing existing endpoints.
Stop condition stands: any risk to production identity or migration integrity
halts the cutover and is recorded here instead of worked around silently.
