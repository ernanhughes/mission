# MC-PROJECTS-QUALITY-01 — Phase 02 Report: Cutover + Project Workspace

Follow-on to `MC-PROJECTS-QUALITY-01-PHASE-01-REPORT.md` (baseline + read-only
reconciliation). This milestone implements the **Phase 1 cutover** (deterministic
automatic registration with owner gates) and the **Phase 2 project workspace**
(software overview + engineering tabs). No quality scoring — that is the next
dedicated milestone (MC-PROJECTS-QUALITY-02).

No commits, pushes or application launches were performed.

## 1. What changed and why

| Problem (from Phase 1) | Fix |
|---|---|
| Classifier labelled Writer/Mission/Workbench as `book` from README keywords | `discovery/classifier.py` now requires a manuscript tree (`content/books`, `book/planning`, `bookbuilder.toml`, `chapters/*.md`) for `book`; README book mentions are recorded as subject matter, never the deliverable. Every classification carries a `reason`. |
| Manual per-repo project creation cannot scale to hundreds of repos | `projects/registration.py`: deterministic auto-registration for unambiguous software repos (Git `repo_uid` or normalized path identity, never basenames); explicit confirmation for bulk apply, policy-gated auto-register, review queue for ambiguous/legacy/missing. |
| Projects page showed only 3 seeded book manuscripts | `/api/projects/software` paginated software inventory (book-legacy excluded, preserved); Projects page defaults to Software with an "All incl. book legacy" scope. |
| Single-scroll book workspace unsuitable for engineering | Software projects render Overview / Activity / Inspect / Quality / Improvements / Context tabs; book projects render exactly as before. |
| No audit trail / rollback for identity decisions | Migration `036`: `repositories.repo_uid`, `projects.origin`, `project_identity_decisions` (unique `path_norm`, idempotent re-runs). Apply backs up SQLite first; rollback removes only pristine projects. |

## 2. Reconciliation counts

### Before cutover (production inventory)
- Discovery scan of `C:\Projects`: **49 candidates, 0 errors** (41 Git, 8 non-Git).
- Persisted projects: **3 book-legacy** (`language`, `inference`, `math`), 0 software.
- Classifier (fixed): Writer→library, Mission→executable_application,
  CoCoder→executable_application, Worker→executable_application,
  Inspect→research_project, Workbench→executable_application,
  genuine manuscripts (`C:\books/*`)→book ≥0.94.

### After cutover (production, 2026-11-22)
- Discovery rescan (`/api/discovery/scan`): `book` 46 → **29**, `executable_application`
  13 → **25**, `research_project` 8 → 10, `library` 10 → 8. The classifier fix
  reclassified Mission, Workbench, CoCoder, Worker and others as software on real data.
- Git activity rescan: **85 → 110 repos**, 10345 → 12779 commits, backfill pending 1.
- Identity preview (`/api/projects/identity/preview`, saved to operator notes):
  **39 eligible, 47 needs_review, 5 skipped, 40 book-legacy preserved**.
  Eligible included all five acceptance targets: writer, mission, cocoder, worker,
  inspect. Needs-review was dominated by missing paths (deleted checkouts held as
  unavailable, never auto-registered) plus genuinely ambiguous items
  (`programmer.ie-main-merge` book, `hugo-bookkit` publishing_site, unknowns).
  One id collision avoided by suffixing (`fine-tuning-git-7c`; established `fine-tuning`
  book id untouched).
- Confirmed apply (`confirm:true, approve_policy:true`): **39 created, 0 skipped**.
  Backup: `data/backups/pre-cutover-20261122T152652Z.db` (online SQLite backup before
  any write). Policy: `auto_register:true` approved for `C:\Projects`.
- Software inventory after: **40 workspaces** (39 new + pre-existing `mc11-experiments`).
  Writer→app `writer` + Inspect `writer`; Mission→app `technical` + Inspect `mission`;
  Inspect→Inspect `inspect`; CoCoder→app `cocoder`; Worker→app `worker`. Writer shows
  `stale:true` (Git backfill pending on its repo) — honest, not hidden.

## 3. Changed files

Backend:
- `backend/mission_control/persistence/migrations/036_software_project_identity.sql` (new)
- `backend/mission_control/models.py` (`Repository.repo_uid`, `Project.origin`, `ProjectIdentityDecision`)
- `backend/mission_control/discovery/classifier.py` (purpose vs subject matter + `reason`)
- `backend/mission_control/discovery/service.py` (persist `repo_uid` from Git index)
- `backend/mission_control/projects/registration.py` (new: preview/apply/auto-register/rollback/software inventory/git links)
- `backend/mission_control/projects/service.py` (`origin` in `ProjectRead`, `repo_uid` in `RepositoryRead`)
- `backend/mission_control/api/projects.py` (identity preview/apply/auto-register/rollback/policy, software inventory, git links, `inspect_project_id`)
- `backend/mission_control/schemas.py` (identity + software + git-link contracts)
- `backend/tests/test_project_identity_cutover.py`, `test_software_classification.py` (new); `test_migrations_and_seed.py` (36 + new table)

Frontend:
- `frontend/src/features/software/SoftwareInventory.tsx`, `ReconcilePanel.tsx`, `SoftwareWorkspace.tsx` (new)
- `frontend/src/pages/ProjectsPage.tsx` (Software default + legacy scope)
- `frontend/src/pages/ProjectPage.tsx` (software tab branch; book view unchanged)
- `frontend/src/features/applications/ApplicationCard.tsx` (workspace link)
- `frontend/src/types/api.ts` (new contracts)
- `frontend/src/test/SoftwareWorkspace.test.tsx` (new)

## 4. Tests and browser evidence

Backend: full suite **667 passed, 1 skipped** (the skip is the pre-existing
`MISSION_CONTROL_WRITER_QUALITY_RUNNER`-gated live CLI test). One mid-run error seen
during the work was proven self-inflicted (a `git stash` executed while the suite was
running mixed pre/post-change tree states) and disappeared on a clean re-run.
New: 8 cutover tests (preview split, confirm-required, idempotent worktree linking,
bulk policy, auto-register gating, rollback preservation, inventory exclusion,
missing-flag) + 5 classifier tests.

Frontend: `tsc` + production build clean; new suite 5/5; book ProjectPage suites unchanged.
Full-suite note: three full `vitest run` passes each showed 1–2 failures in *unrelated,
untouched* files (CultivationPage/WriterPage/ProjectPage-timeout — a different set each
run), while every one of those files passes in isolation and in smaller groups.
Rigorous check: pristine tree full run 97/97; with source changes but without the new
test file 97/97; final full run with everything **102/102**. CultivationPage imports
none of the changed/new modules. Conclusion: worker load flakiness, no regression.

Browser (production, real data, zero console errors throughout): Projects → 40 software
workspaces, 25/page with working pagination. Writer workspace: 6 tabs; Overview shows
Purpose/Repositories (`primary · C:\Projects\writer`, Available, library)/Applications
(Writer, Running-external, authorized Launch)/Checkpoint; Activity shows real commits
(Nov 21/20/19, authors, review status) with backfill badge and working daily-review
controls; Inspect maps to the writer snapshot (Capabilities live); Quality is honestly
Unassessed with rubric preview + copyable evaluation prompt; Improvements aggregates
tasks/recommendations/Inspect opportunities + copyable scoped prompt; Context shows
AGENTS.md present / no DESCRIPTION.md with working propose flow. Mission workspace:
same 6 tabs, Activity live. Language book project: unchanged single-scroll view with
Manuscript quality. Screenshots were not capturable (no visible desktop window in this
environment); DOM + network evidence recorded instead.

## 5. Safeguards honoured

- Identity: `repo_uid` / normalized path; basenames reported only as collisions.
- Book-legacy ids, relationships, launch definitions, Git history, reviews and
  Cultivation state untouched; rollback keeps every project with user records.
- Missing repos surface as unavailable; never deleted, never auto-registered.
- Application launching delegates to the registry; no inferred launch commands.
- Quality tab is honestly unassessed; no placeholder scores, no invented findings.
- AGENTS.md proposals are diffs; applying requires explicit confirmation and writes
  the repository (owner action, never automatic).

## 6. Known limitations / next milestone

**Concurrent workstream note (record corrected during verification):** at 15:02 and
15:24 this session observed uncommitted modifications to `living_book/client.py`,
`living_book/service.py`, `processes/manager.py` and `tests/test_living_book.py`
(which this commission never opened). At 15:28 those changes were committed by their
owner as `192169d` (merged `f51e602`, MC-ALIVE-CONNECT-01) — nothing was lost and no
stash content went missing. Current HEAD is `f51e602`. The full backend suite result
above predates that merge; the directly affected tests were re-run on the merged tree:
**39/39 passed** (`test_living_book` + all cutover/classifier/migration/discovery tests).
My changed-file list is unaffected (disjoint files).

- The live `C:\Projects` scan is depth-1; nested repos rely on the Git activity index.
- Inspect mapping needs a published snapshot; unmapped projects say so honestly.
- Project charter (Phase 3) and the 1,000-point rubric (QUALITY-02) are explicitly
  deferred: Quality tab ships the rubric preview and evidence-package contract only.

Next: **MC-PROJECTS-QUALITY-02 — Software Quality Evaluation** (versioned rubric,
evidence-backed findings, score history, improvement loop).
