# MC-CULTIVATION-01 — Achievement Paths, Goal Tracking and Progress HUD

## 1. Architecture and reuse map

No new database, no new gateway, no inference. Cultivation reuses Mission
Control's existing storage, DTO/service and UI conventions:

- **Persistence** — explicit SQL migrations (`008_cultivation.sql`) + SQLAlchemy
  models + `Database.session()` ownership, same as Activity (007) and all
  prior milestones. Six tables: goals, items, memberships, measurements,
  events, evidence.
- **Service idiom** — stateless functions taking `Session`
  (`cultivation/service.py`), same as `projects/service.py`. Counts recompute
  from stored rows on every read; nothing cached, nothing inferred.
- **API idiom** — FastAPI router with Pydantic `RawModel` inputs / `*Read`
  outputs, `get_session` dependency, `MissionControlError` mapping.
- **Activity integration** — goal creation, stage changes, measurements and
  context updates record `ActivityEvent`s through the existing
  `record_activity` service (provenance `user`). No Activity Git-index
  semantics touched: no file under `activity_git/`, `git/` or the Activity
  page was modified for this commission.
- **Frontend** — `useApi` + `apiPath`, `PageHeader/Section/Stat/Tag`,
  `Modal`, `copyText`-free (nothing to copy), existing tokens/responsive
  patterns. HUD lives in `Layout` (fixed top-right, collapsible); the full
  view is a new `CultivationPage` + `/cultivation` route + `Sprout` nav entry.
- **Ranks/stages config** — stored in the existing `Setting` table
  (`cultivation` key), editable through the API; no config-file editing.

## 2. Goal data model and persistence (migration 008)

- `CultivationGoal` — id, name, description, category, unit, target_value,
  measurement_type (`count|threshold_up|threshold_down|recurring|
  qualified_count`), `baseline_value` + `baseline_note` + `baseline_provenance`
  (`none|estimate|user_assertion|verified`), `qualifying_stage`,
  `window_days` (recurring), priority, state (`active|paused|achieved|
  archived`), pinned/pin_order, privacy (`standard|private`),
  completion_criteria, milestones[], dependencies[], evidence_source.
- `CultivationItem` — stable artefact registry (title, type, notes, tags,
  provenance `human|ai_assisted|ai_workflow|unclassified`, optional
  `source_application|source_project_id|source_ref` with project-existence
  validation, read-only project/book name resolution).
- `CultivationMembership` — item↔goal with stage, evidence_status,
  quality_evidence JSON, qualified flag + timestamps, completed_at
  (backdatable). PK `(item_id, goal_id)` makes double-counting the same book
  in one goal impossible (409).
- `CultivationMeasurement` — dated numeric observations for metric goals.
- `CultivationEvent` — append-only history (created/updated/stage_changed/
  completed/reopened/correction/measurement/milestone/qualified/unqualified/
  item_added/goal_created/goal_updated). Corrections and reversals add events;
  nothing is deleted (no item/goal delete endpoint in v1 — archive instead).
- `CultivationEvidence` — verification references; verified evidence upgrades
  membership `evidence_status` (`none → claimed → verified`).

Progress rules: count/qualified_count = baseline(prior achievements) +
tracked qualified memberships, labelled (`≈31 (30 estimate + 1 tracked)`);
threshold_up = max measurement; threshold_down requires a baseline or reports
`unknown` (never a fake percent); recurring = days-met in window_days;
unknown stays unknown with a reason string. Achieved is derived; the
`achieved/archived` **state** remains an explicit user action.

## 3. Configurable goal management interface

Cultivation page: goal list with progress bars and state/privacy/achieved
badges; goal detail with stage pipeline, add-item, per-stage advance buttons,
backdatable completion, qualification recording (qualified_count goals),
measurement entry (metric goals), milestone list, full event history, evidence
list, pause/mark-achieved/archive/reactivate, pin reorder, new-goal modal.
Stages editable as JSON through the Configuration section (validated
server-side); ranks display with attainment state.

## 4. Compact Cultivation HUD

Fixed top-right element in `Layout`: pinned primary goal (lowest pin_order
active pinned), count + progress bar + rank concept; click expands pinned
goals (deep-links to goal detail), recent completions, link to full view.
Collapsible, keyboard-accessible button, dark/light via existing tokens,
bottom-docked on small screens, no popups/animations. Only GETs; verified by
test that HUD mount issues no POST and touches no inference path.

## 5/8. Expanded view, detail, history

Covered by the Cultivation page (§3): pinned-goal expansion, per-goal items/
stages/measurements/milestones/history, cultivation ranks with requirements
and attainment.

## 6. Initial editable goal definitions

Seeded catalogue (12, never overwritten once user-edited): Published Books
(100, pinned primary, baseline **30 estimate** labelled "awaiting inventory
verification"), Fiction/Technical Books (100), Blog Posts (100, baseline 100
**user_assertion** with explicit "exact date not recorded", state achieved),
Movies/Songs/Papers/Applications (100), Repositories (1000, custom
milestones), Perfect Repositories (qualified_count + revisable standard incl.
renewal caveat), Body Weight (threshold_down 150 lb, private, **no baseline
→ honestly unknown**), Press-ups (threshold_up 100/day, private).

## 7. Manual item lifecycle

Idea → In development → Editing → Ready → Published (configurable; per-goal
qualifying stage; default published). Transitions timestamped with notes and
optional evidence refs; entering the qualifying stage stamps completion
(backdatable); leaving it reopens with history intact. Multi-goal membership
(one book → Published + Fiction) with per-goal stages.

## 9. Progress history

Append-only events + dated measurements give achievements over time, last
30/90-day completions (HUD recent list + goal event history), milestone dates
(by milestone events), per-goal progress. No velocity projection (insufficient
dated evidence by design); no streaks.

## 10. Tests and verification report

- **Backend: 114 passed** (`pytest -q`; includes 18 new `test_cultivation.py`:
  creation/editing, multi-goal, pin/reorder, lifecycle + reversal + backdated
  completion, all five measurement types, unknown-down-without-baseline,
  historical baseline + correction events, multi-membership + 409 dedup +
  distinct editions, qualified_count incl. unqualify, milestones + rank
  qualification, manual vs verified evidence upgrade, archive exclusion,
  privacy filter, restart persistence (close + reopen same data dir),
  seeded catalogue assertions incl. estimate labels and no invented blog date,
  seed-never-overwrites, no-inference-imports source check; plus migration-008
  assertions in the seed/migration test). The tests caught and fixed three
  real bugs: `pinned` ignored by goal update, backdated completion dropped,
  verified evidence not upgrading `claimed`.
- **Frontend: 39 passed** (5 new: estimate rendering, stage advance PATCH,
  goal creation, HUD GET-only + no inference paths). `tsc` clean, build OK.
- **Lint:** `ruff check backend` clean.
- **Live smoke** (temp DB, seeded): 12 goals, `≈30 (30 estimate + 0 tracked)`
  → publish one item → `≈31 (30 estimate + 1 tracked)`, milestones
  [1,10,25], HUD primary `published_books`, Initiate rank attained.
- **No-model-call:** HUD/page mount only GETs (test-asserted); cultivation
  modules contain no inference/httpx references (test-asserted).

## 11. Known integration gaps (future adapters, not built)

Activity/Git (e.g. repo counts), Writer/Bookkit (manuscript/publication
states), Projects/Next/Worker/film tooling: associations are currently manual
(`source_project_id` with read-only name resolution). No automatic discovery
writes into goals; nothing infers publication from commits or perfection from
review verdicts. Model self-reporting is untrusted by design (per R1).
Rank requirements are configurable but simple predicates, not a scoring
engine.

## 12. Working tree (no commit, no push per instructions)

New: `backend/mission_control/cultivation/`, `api/cultivation.py`,
`migrations/008_cultivation.sql`, `backend/tests/test_cultivation.py`,
`frontend/.../CultivationHud.tsx`, `pages/CultivationPage.tsx`,
`test/CultivationPage.test.tsx`, this report. Modified: `main.py` (router),
`models.py`, `schemas.py`, `seed.py` (catalogue), `test_migrations_and_seed.py`,
`App.tsx`, `Layout.tsx` (nav + HUD), `api.ts`, `styles.css`.
Pre-existing unrelated modifications were left untouched.
