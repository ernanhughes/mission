# Scripts in Cultivation — numbered self-hypnosis files as a live goal

Follow-up to MC-CULTIVATION-02/03. Adds `C:\script` to the Cultivation panel
as a live-counted goal plus a weekly-rhythm goal. No AI calls, no model
execution, no changes to Activity Git indexing, no auto-sync.

## 1. What counts

Only numbered files count: any `.md` file whose stem starts with `Script`
+ digits (`Script001.md`, `Script052s.md`, `Script036_not your money.md`,
`sub/Script057a.md`, case-insensitive). Everything else — `Morning001.md`,
themed notes (`OceanOfEnergy`, `perfect belief`, `problems`), `gpt-hypnosis.txt`,
`audio/`, dot-directories (`.git`, `.vscode`) — is excluded, never counted.
Unreadable files land in `unknown`, never silently counted.

Identity is the repo-style relative path; the item date prefers the file's
first git addition commit and falls back to filesystem mtime. Dating reads
the repository only: two read-only git processes per scan (`rev-parse` to
confirm the source path is the repo root, `log --diff-filter=A` for addition
dates), each with a timeout, `shell=False`, and total failure tolerance
(any miss falls back to mtime). The sync never writes to the repository —
a behavioral test asserts HEAD and working tree are unchanged after sync.

Layer rule (enforced in `test_cultivation_03.py`): shelling out is banned in
`cultivation/service.py` and in the Activity adapter (per-function
`inspect` guards); the file scanners in `cultivation/sources.py` may use
read-only git for observation. A blanket file-wide `subprocess` grep was
tried and reverted as too constricting — it would have capped the
observation layer at mtime dating. Item IDs are `script-<sha1(source:relpath)>`,
distinct from the `hugo-` namespace so a file observed by both kinds never
collides. A first-pass parsing bug (NUL-separated date/name chunks dropped
every mapping, silently falling back to mtime) was caught by the new
behavioral test and fixed with line-wise parsing.

## 2. Source kind `numbered_files`

- `cultivation_sources` row (`src-scripts`, path-gated on `C:\script` existing,
  never auto-synced), attached to the count goal; the config names the
  weekly-rhythm goal: `{"period_goal_id": "weekly_script"}`.
- `scan_numbered_files` in `cultivation/sources.py` reuses `BlogPost`/`BlogScan`.
- `sync_source` dispatches the new kind to `_sync_numbered_files`, which shares
  `_reconcile_observed_items` with `_sync_hugo_blog` (extracted verbatim from
  the Hugo path: manual holds respected, human qualifications kept, removals
  move items out of the qualifying set with `source_removed` events, history
  preserved, stale keeps the last observation and never zeroes it).
- `_live_observation` accepts `hugo_blog` and `numbered_files` (kind-filtered
  by the goal's own `evidence_source`); the user-attested baseline stays
  preserved as history with a reconciliation note.

## 3. Weekly rhythm via `recurring_mode`

Migration 011 adds `cultivation_goals.recurring_mode` (`daily` default —
existing per-day threshold semantics unchanged; `period` = total output in
the window vs the target). Validation rejects unknown modes (422).

`weekly_script` is `recurring`/`period`, `window_days` 7, target 1. Each newly
observed script records one measurement (value 1, dated at the file's mtime,
source `sync:<source_id>`, note `New script observed: <relpath>`), deduped on
(sync source, note) so resyncs never double-count and backfilled old scripts
land outside the current window. Removals do not retract history.

## 4. Seeded catalogue (idempotent, never overwrites)

- Skill `scripts` (icon `moon`, pinned, pin_order 20).
- Goal `scripts_published`: count, unit scripts, target 100, qualifying
  stage `published`, milestones 1/10/25/50/75/100, pinned 20.
- Goal `weekly_script`: recurring/period, 7-day window, target 1, pinned 21.
- Source `src-scripts` as above (only when `C:\script` is a directory).
- Existing pin-control test helper extended to unpin the new seeds; no seeded
  counts asserted exactly, so catalogue growth breaks nothing.

## 5. Frontend

`CultivationGoal` type gains `recurring_mode: string` (test fixture updated).
No panel changes needed: skills, goals, sources and sync buttons are generic.

## 6. Verification

- Backend: 164 passed (`tests/`, incl. new `test_cultivation_scripts.py`
  with 9 tests: counts/exclusions, live count + idempotent resync, weekly
  window, removal/hold/stale, period progress + 422 validation, bad-kind
  rejection, seed catalogue, no model imports on sync, git-date preference
  with zero repo mutation); `ruff check` clean.
- Frontend: `tsc --noEmit` clean, CultivationPage suite 13 passed,
  production build succeeds.
- Live on a temp DB against the real `C:\script`: 67 published / 0 unknown /
  71 excluded of 138 candidates; count goal 67/100 live; weekly goal 3/1
  achieved (3 scripts touched in the last 7 days), 67 measurements fed.
