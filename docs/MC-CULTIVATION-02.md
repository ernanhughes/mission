# MC-CULTIVATION-02 — Blue HUD, Skills, Live Blog Progress and 100-Day Cycles

## 1. Architecture and reuse summary

No new application, database, or gateway. MC-CULTIVATION-01 contracts are
extended, not replaced:

- **Migration 009** (`009_cultivation_skills_sources_cycles.sql`) — additive
  only: `cultivation_skills`, `cultivation_sources`, `cultivation_cycles`,
  `cultivation_cycle_goals`, plus nullable `cultivation_goals.skill_id`.
  Existing goals, milestones and history are untouched; unassigned goals read
  as "Unassigned".
- **Services** — `cultivation/service.py` gains skills, sources, cycles and a
  live-observation override in `goal_progress`; `cultivation/sources.py` is a
  new read-only Hugo scanner (stdlib TOML + PyYAML + stdlib JSON, no new deps).
  No Activity Git-index semantics modified (no files under `activity_git/`,
  `git/` or the Activity page were touched).
- **Frontend** — blue theme tokens scoped to `.cultivation-*` classes; the
  HUD and Cultivation page were extended in place; no new router beyond the
  existing `/cultivation` route.
- **Seed** — 13 skills, skill assignments (only where `skill_id` is NULL),
  one `hugo_blog` source row (path configured, never scanned at seed),
  Cycle 5 snapshot (day 50 reported, no start date invented).

## 2. Blue-and-white HUD implementation

`CultivationHud` and the Cultivation page use the supplied tokens
(`--cultivation-background` … `--cultivation-warning`): navy glass panels,
cyan outlines with angular clipped corners, luminous turquoise bars, green
achieved states, white numerals. Bar states are data-driven
(`empty|active|achieved|over|unknown`) with `role="progressbar"` and text
labels alongside colour; over-target clamps at 100 % width while showing the
true count (`137 / 100`); unknown uses a hatched inactive bar plus an explicit
"unknown" label, never zero. Compact HUD shows the cycle line, primary goal
and a second indicator; expansion shows pinned skills (4 goals each max),
rank, recent completions. `prefers-reduced-motion` disables glow transitions;
all controls are native buttons/inputs; the theme holds in both app themes
since Cultivation sets its own colours.

## 3. Skill management interface

Skills are CRUD entities (icon, category, description, pin/order, archive)
with goal assignment per goal. The full view groups goals under collapsible
skills plus an Unassigned group, with text search, category filter and
active/achieved filter; only expanded groups render their goals. The HUD
expansion lists pinned skills; compact stays goal-focused per spec.

## 4–5. Live Blog Posts source

Source row `programmer.ie posts` → `C:\Projects\programmer.ie\content\post`
(hugo_blog). Sync is explicit (button, synchronous request, no page-load
scan, no scheduler, no model calls). Manual refresh re-renders from the
index; unavailable directory → `stale`, last observation kept, never zeroed.

## 6. Actual counted blog inventory (live, 2026-11-10)

Against the real directory (163 `.md` files, no subdirectories/bundles
present): **132 published, 27 drafts, 4 unknown, 0 excluded, 0 errors.**
Cross-checked independently: 4 files without front matter, 2 YAML files with
unquoted dates (parser fixed to accept `date` objects), 1 `draft = true`
match is body text not front matter, 1 future-dated scheduled post. The
manual hold test proves a user-edited item is not overwritten on resync.

## 7. Source synchronization evidence

Per sync stored on the source row: counts, excluded, candidates, first 20
errors, source fingerprint (sha256 over identity+file-hash+state), timestamp
and status (`ok`/`stale`/`never_synced`). The goal shows published/draft/
unknown/excluded, last sync, stale flag, and a reconciliation notice when the
observed count disagrees with the user-attested baseline. Milestone history
is preserved regardless of direction.

## 8. Persistent 100-day cycle support

`cultivation_cycles` + `cultivation_cycle_goals`. Cycle 5 seeded exactly as
reported (day 50 snapshot + note, no start date, no auto-advance). Setting a
start date enables Europe/Dublin day calculation; rollover is explicit
(complete + open next with focus copied; re-rollover rejected with 409);
cycle progress counts completions via event/occurrence dates inside the
window only — without a start date there is no window and no manufactured
attribution. Survives restart (tested).

## 9. Scalable full-Skills view

Search + category + state filters, collapsible skill groups with per-goal
progress bars, counts always computed index-side. Hundreds of goals render
only within expanded groups.

## 10. Tests and verification report

- **Backend: 124 passed** (10 new in `test_cultivation_02.py`: skills CRUD/
  pin/reorder/archive, skill assignment + filtered listing, Hugo counts with
  leaf-bundle/`_index`/attachment/draft/future/invalid/missing-date/YAML-date
  fixtures, no-duplicate-posts, incremental/no-op resync, deletion reconcile
  with history event, manual-hold preservation, stale-preserves-observation,
  historical-milestone preservation + disagreement flag, cycle snapshot/
  start-date/rollover/409, restart persistence, seed catalogue + cycle 5,
  no-model-imports; plus updated catalogue/migration tests).
- **Frontend: 44 passed** (5 new: skills grouping + filter, skill pin/create,
  cycle snapshot label, over-target clamp, unknown state; existing GET-only/
  no-inference HUD tests extended to the new endpoints).
- `tsc` clean, `ruff` clean, production build succeeds.
- Live verification against the real blog directory (temp DB): counts above,
  manual-hold respected, HUD cycle + pinned skills render.
- No model calls anywhere in the Cultivation stack (source-grepped in tests).

## 11. Known limitations and future integration boundaries

- Scanner covers the observed conventions (standalone + leaf bundles, TOML/
  YAML/JSON front matter, draft/future/expired handling); deeply nested or
  multilingual setups revalidate on first sync via the unknown bucket.
- Goal total under a live source equals the observed count; manual baseline
  stays as history with a disagreement flag when they differ.
- Removed source files move memberships back to the first stage with a
  `source_removed` event (history preserved, not deleted).
- Projects/Books/Notion adapters are **not** implemented: project links are
  manual (`source_project_id` with read-only name resolution). No commit,
  publication, or perfection is inferred from Activity data.
- No browser-screenshot verification was available in this environment;
  visual verification is via the running app + tests.

## 12. Commit hash and working-tree status

- HEAD: `724dfe0` (MC-CULTIVATION-01). No commit, push, or merge performed
  per instructions.
- New: `api/cultivation.py` (extended), `cultivation/service.py` (extended),
  `cultivation/sources.py`, migration `009`, `test_cultivation_02.py`,
  `CultivationHud.tsx` + `progress.ts`, `CultivationPage.tsx` (rewritten),
  `CultivationPage.test.tsx` (extended), this report.
- Modified: `models.py`, `schemas.py`, `seed.py`, `test_migrations_and_seed.py`,
  `test_cultivation.py` (date-robust recurring test + qualified_by expectation),
  `App.tsx` (unchanged routes — already present), `Layout.tsx` (unchanged —
  HUD already mounted), `api.ts` types, `styles.css` (blue theme), `api/client.ts`
  (`put` helper).
- Pre-existing unrelated modifications were preserved and untouched.
