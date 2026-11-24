# MC-PROJECT-TABS-01 — Tabbed Project Workspace Report

**Date:** 2026-11-23
**Project:** Mission Control (`C:\Projects\mission`)
**Reference project:** Math (`http://127.0.0.1:8790/projects/math`)
**Status:** Implemented, tested, no commit/push/deploy per instructions.

## 1. Summary

Replaced the single enormous vertically-stacked project detail page with a persistent header + 8-tab workspace:

**Overview | Book | Quality | Technical | Calibration | Publishing | Work | Activity**

- One persistent compact header, one tab bar, one active workspace mounted at a time.
- URL-addressable tabs (`?tab=quality` etc.), Back/Forward compatible, refresh preserves tab, unknown tab falls back to Overview.
- Badges for Quality (missing+stale), Calibration (awaiting), Work (pending recs + open tasks).
- WAI-ARIA tab pattern, arrow-key/Home/End navigation, visible focus.
- Calibration queue rebuilt as compact searchable queue + detail pane with Prev/Next, draft persistence via `localStorage`, deep link `?tab=calibration&packet=CASE_ID`.
- Quality tab rebuilt with subviews (Summary/Chapters/Signals/Campaigns), shared chapter selector (`?qchapter=`), search (`qview`, `qchapter` in URL).
- Technical chapters deep-link via `?tchapter=` / `?cchapter=`.
- No backend changes. No scoring/policy/model changes. No automatic manuscript edits.

## 2. Before / After Section Map

All existing capabilities preserved, only moved. No deletion.

| Existing section (before) | Proposed tab | Change |
|---|---|---|
| Project identity + status + milestone/next/last | Persistent header + Overview/Project summary | Retain and compact; description truncated to 180 chars |
| Living Book + reading progress + Continue reading | Book (LivingBookCard + Reading + inventory) + Overview/Continue working (link) | Move; Reading Room not duplicated |
| Checkpoints (latest + history + composer) | Work/Continuity + Overview/Continue working (summary + link) | Move full forms to Work; Overview shows summary only |
| Recommendations (pending + reviewed) | Work/Actions and decisions + Overview/Attention (count + link) | Move; accept/defer/reject preserved |
| Cross-application context | Work/Connected capabilities | Move |
| Experiment evidence (workflows + observations) | Work/Continuity | Move |
| Manuscript quality (summary + means) | Quality/Summary | Move |
| Book Quality Map | Quality/Chapters | Move + add search/filter + shared chapter selector + subview |
| Artifact Load | Quality/Signals | Move + filter by shared selector |
| Writer evaluations | Quality/Signals | Move + filter; never merged with prose |
| Evaluation campaign + past campaigns | Quality/Campaigns | Move; start/stop/resume preserved |
| Priority review + Writer QC signals | Quality/Summary | Move; “Open in Chapters” navigates via `qchapter` |
| Chapter evaluations (scorecards + history + workbench) | Quality/Chapters (filtered) | Move + filter; provenance preserved |
| Technical Confidence | Technical | Move |
| Technical campaign | Technical | Move; controls preserved |
| Chapter technical assessment | Technical | Move + deep link `tchapter` |
| Evidence Completeness | Technical | Move + deep link `cchapter`; UNKNOWN stays UNKNOWN |
| Chapter objectives + Evidence gaps | Technical (with Completeness) | Move |
| Publication Readiness + Release gates + Blockers + Author approval + dossier | Publishing | Move; refresh + assessment + approval preserved |
| Requirement calibration summary | Calibration (summary) + Publishing (advisory count) | Move; advisory-only preserved |
| Publishing (evidence, fingerprint, gate, blockers, refresh) | Publishing | Move; refresh is read-only evidence reread |
| Calibration review queue (expanded forms) | Calibration (compact queue + detail pane) | Move **and improve queue presentation** (see §4) |
| Inspect | Work/Connected capabilities | Move; read-only, never executes |
| Tasks (open + done + add) | Work/Actions + Overview/Attention (count) | Move |
| Decisions (list + add) | Work/Actions | Move |
| Activity (full timeline) | Activity (full) + Overview/Recent preview (5) | Move; full history with search/type/provenance/pagination; newest first |
| Outcomes | Work/Project information + Book/Book outcomes | Move |
| Book panel (side) | Book | Move |
| Repositories | Work/Connected | Move |
| Supporting tools | Work/Connected | Move; launch preserved |
| Adapters | Work/Connected | Move; refresh preserved |
| Notes | Work/Project information + Book/Manuscript notes | Move |
| Workspace metadata | Work/Project information | Move |

Software (non-book) projects continue to use the existing `SoftwareWorkspace` tabbed view unchanged.

## 3. Component Changes

**Created:**

- `frontend/src/features/project/projectTabs.tsx` — `PROJECT_TABS`, `normalizeProjectTab`, `useProjectTab`, `tabHref`.
- `frontend/src/features/project/shared.tsx` — `CheckpointForm`, `TaskRow`, `RecommendationRow`, `AdapterCard` (moved from `ProjectPage.tsx` to break cycles; drafts persist `sessionStorage` for checkpoint).
- `frontend/src/features/project/ProjectTabBar.tsx` — accessible tab bar with badges, Arrow/Home/End.
- `frontend/src/features/project/OverviewTab.tsx` — summary, continue working, book progress, attention, recent preview, quick nav.
- `frontend/src/features/project/BookTab.tsx` — Living Book, reading, chapter inventory, outcomes, notes.
- `frontend/src/features/project/WorkTab.tsx` — Actions/Continuity/Connected/Info subviews; checkpoint, recs, tasks, decisions, context, experiment, inspect, repos, tools, adapters, notes, metadata.
- `frontend/src/features/project/ActivityTab.tsx` — full history with search/type/provenance + pagination, newest first.
- `frontend/src/test/ProjectTabs.test.tsx` — navigation, badges, keyboard, packet deep link + draft persistence.

**Modified:**

- `frontend/src/pages/ProjectPage.tsx` — major refactor:
  - Removed shared primitives (now imported).
  - Added compact header + sticky tab bar + badges (discovery/techOverview/campaigns/calRuns lightweight, always mounted).
  - Conditional rendering: only active tab mounted.
  - `QualityPanel` upgraded with `qview`/`qchapter`/`qsearch`, subviews, shared selector, filtered maps/artifacts/writer/chapters.
  - `TechnicalPanel` (`tchapter`) + `CompletenessPanel` (`cchapter`) URL-synced.
  - `CalibrationPanel` replaced with queue + `CalibrationDetailForm` (search, arm/chapter/template/state filters, `packet`/`arm`/`calChapter`/`calState` in URL, `localStorage` drafts, Prev/Next, shared-sample notice).
  - `ReadinessPanel` + `PublishingPanel` grouped under Publishing (unchanged logic).
  - Software branch preserved.
- `frontend/src/features/software/SoftwareWorkspace.tsx` — import shared from new location.
- `frontend/src/styles.css` — appended `.project-header-compact`, `.project-tabbar`, `.project-tab`, `.project-tab-badge`, `.cal-queue-layout`, `.cal-detail`, responsive rules.
- `frontend/src/test/ProjectPage.test.tsx` — updated for tabs (work subviews, quality subviews, technical/publishing/calibration deep links).
- `frontend/src/test/WriterEvaluations.test.tsx` — render `?tab=quality&qview=signals`.
- `frontend/src/test/InspectPage.test.tsx` — render `?tab=work` + click Connected.

**Removed:** none (old `CalibrationReviewCard` remains unused; see limitations).

## 4. Calibration Queue Improvement

Before: up to 10 fully-expanded `CalibrationReviewCard` forms stacked, `Show more` appended more expanded forms; 140 packets would dominate the page.

After (`CalibrationPanel`):

- Top: summary with explicit provenance — “Shared frozen sample CAL04A02 (book-inference, 140 packets) shown in this project for review continuity. Packets are **not project-owned**.”
- Runs, sample (`new_distinct`, `new_model_calls`), stats (human/AI/deterministic, agreement NOT_MEASURED until dual reviews).
- Queue: search (`case, chapter, claim`), Arm/Chapter/Template/State filters, compact rows (`case · template`, `chapter · applicability · satisfaction · reviewed/awaiting`, claim snippet), `role=listbox/option`, `aria-selected`, active highlight.
- Detail: claim, excerpt (400 chars), surrounding context expandable, requirement, system verdict, gaps, prior reviews (`HUMAN`/`AI-ASSISTED`/`AWAITING` via `provenanceOf`), R1–R10 inputs, reviewer, summary, Submit/Save draft/Defer/Abstain. Same POST payload/validation as before.
- Prev/Next + `1 of N`; `packet` in URL (`?tab=calibration&packet=...`) for deep links + refresh preservation.
- Drafts: `localStorage` key `mc.cal.draft.{projectId}.{requirementId}`, restored on mount, cleared on completed submit, “Unsaved draft restored” notice. Switching packets/tabs does not lose input.

## 5. Data Isolation Finding (Section 10)

**Calibration is global, not project-owned.**

- Endpoint `GET /api/publication/calibration/packets` (`backend/mission_control/api/publication.py:353`) takes only `arm` + `limit`, no `project_id`; loads `backend/mission_control/publication/data/packets.json`.
- That file contains 140 packets, all `book_id=book-inference`, chapters `43-chapter.md` (49), `01-chapter.md` (49), `39-chapter.md` (42). No Math chapters.
- Math page therefore shows Inference material because the UI presents a shared frozen sample as if project-scoped. This is a presentation scoping defect, not a data corruption (no calibration data was modified).
- Fix applied in UI only: Calibration summary now explicitly labels the sample as shared/frozen and not project-owned; filters show chapter IDs as observed. No silent reclassification, no invented agreement, no reconciled counts.
- **Recommended backend follow-up (out of scope, not implemented):** either scope packets by project (`?project_id=` + `book_id` filter + empty state for projects without sample) or rename endpoint/UI to “Global calibration sample” with project filter explicitly disabled. Evidence: `packets.json` counts above + endpoint source.

**38 vs 39 discrepancy preserved:**

- Quality discovery (38 chapters current/missing) vs publishing `chapter_count` (39 observed files) are different denominators from different systems. UI shows both as observed (“38 in quality view”, “39 observed files”) without reconciling. No invented unified count.

## 6. Test Evidence

**Frontend type checking + build:**

- `npm run build` (`tsc -b && vite build`): PASS (3559 modules, no TS errors).
- Commands run in `C:\Projects\mission\frontend`.

**Frontend tests (`npm test -- --run`):**

- Before refactor: 6 ProjectPage tests expecting single-page layout.
- After: **29 files, 154 tests, all PASS** (2026-11-23 run, ~12s).
  - `ProjectPage.test.tsx`: 9 tests (3 new tab-navigation + 6 updated functionality).
  - `ProjectTabs.test.tsx` (new): 6 tests — default Overview, 8 tabs + only-active-visible, URL/deep-link + unknown fallback, tab badges, arrow-key nav, packet deep link + draft persistence across tabs + Prev/Next.
  - `WriterEvaluations.test.tsx`: 2 tests updated to `?tab=quality&qview=signals`.
  - `InspectPage.test.tsx`: Inspect test updated to `?tab=work` + Connected.
  - All other 25 files unchanged, still PASS.

**Backend:**

- No backend changes (frontend-only refactor).
- Relevant suites: `python -m pytest backend/tests/test_calibration.py backend/tests/test_publication.py backend/tests/test_quality.py backend/tests/test_technical.py -q`: **51 passed**.
- Full suite (`backend/tests`, ignoring integration): **140 passed, 1 failed** — failure is `test_cultivation_blog.py::test_blog_scanner_supports_markdown_bundles_duplicates` asserting `this_week == 1` (got 0), a date-sensitive fixture unrelated to this UI change (no backend files touched). Calibration subset (8 passed) confirms no regression.

**Manual UX checks (code-level, no browser tooling available in this env):**

- Math acceptance flow verified via test mocks + component structure: Overview shows summary/continue/book-progress/attention/recent/quick-nav without tables; Quality/Chapters shows map + scorecards; Technical shows confidence + completeness; Calibration shows queue + detail + Prev/Next; Publishing shows gates/issues/approval; Work shows recs/tasks/decisions/context/inspect/repos/tools/adapters/notes; Activity shows full history; refresh preserves via URL; Back/Forward works via `setSearchParams` push (tab switches push, selections replace).

## 7. UX Verification (Math Scenario)

- Open `/projects/math` → compact header (Math, description truncated, Active, Pin/Unpin, Focus, Repository, milestone/next/updated), 8 tabs, Overview selected, no quality table/packet list.
- Click Quality → Summary (coverage, comparable basis, priority). Click Chapters → map (search + chapter filter) + scorecards + workbench handoff. Click Signals → artifact load + Writer (native scales, “never merged”). Click Campaigns → start/stop/resume.
- Click Technical → confidence (claims by status/method, unresolved warning) + campaign + chapter assessment (`tchapter`) + completeness (`cchapter`) with gaps/objectives.
- Click Calibration → shared-sample notice + stats + compact queue; select packet → evidence, R1–R10, Save draft (persists), Submit (verdict `R1:… R2:…`), Prev/Next.
- Click Publishing → readiness (snapshot, freshness, blockers/unknowns), gates, issues (Accept Finding etc.), approval + dossier links, publishing evidence + Refresh (read-only).
- Click Work → Actions (recs accept/defer/reject, tasks, decisions), Continuity (checkpoint save + history, experiment), Connected (context, Inspect, repos, tools, adapters), Info (outcomes, notes, metadata).
- Click Activity → full history, search/type/provenance, Show more, newest first.
- Refresh on Activity stays on Activity (`tab` in URL). Back/Forward changes tab (push navigation). Unknown `?tab=x` falls back to Overview.

Non-book projects still render `SoftwareWorkspace` (unchanged) — same interface accommodates Writer-heavy books (Math), ordinary software, research, and sparse projects via accurate empty/unknown states, not invented zeros.

## 8. Known Limitations / Follow-ups

1. **Dead code:** old `CalibrationReviewCard` remains in `ProjectPage.tsx` unused (new `CalibrationDetailForm` replaces it). Remove in cleanup to reduce bundle.
2. **Cache on tab switch:** inactive tabs unmount; returning refetches via `useApi`. Lightweight badge hooks stay mounted, campaign status stays authoritative from backend, drafts/selections survive via URL + `localStorage`, but heavy tables do not preserve scroll. Acceptable per spec; could add in-memory cache later.
3. **Quality subviews default:** `qview` defaults to Overview; direct links to Chapters/Signals/Campaigns require `?qview=`. Tests cover this; docs should mention.
4. **Technical tab has two chapter selectors** (assessment `tchapter` + completeness `cchapter`) — intentional (different backends), but could share a single selector later.
5. **Publishing tab stacks Readiness + Publishing evidence** — both small; no subviews added. Could add Readiness/Evidence subviews if it grows.
6. **No performance measurements:** avoided mounting all tabs + paginated queues should improve load, but no before/after timings taken (per instructions, no invented numbers).
7. **Backend scoping fix not implemented** (see §5) — UI labels the shared sample; proper `project_id` scoping or endpoint rename left for backend follow-up.
8. **No visual browser verification** in this environment — verified via component tests + build + CSS review (sticky tab bar, horizontal scroll, responsive grids). Recommend manual check at desktop + 360px widths.

## 9. Files

- Report: `docs/MC-PROJECT-TABS-01-REPORT.md` (this file)
- Implementation: see §3. No commit/push/deploy performed.
