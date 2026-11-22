# MC-WEBSITES-CULTIVATION-01 — Websites Workstream: Review Report

**For:** reviewer / manager AI. **Scope:** everything in this project related to
*Websites* (Task 2 of MC-WEBSITES-CULTIVATION-01). Cultivation HUD removal and
blog/award work are mentioned only where they interact.
**Status:** implemented, tested, merged to `main` (`158b982`), follow-up path
fix `4878d04`. All pushed to `origin/main`.

## 1. What was built

Mission Control had Books, Fiction Books and Projects as first-class workspace
sections. **Websites** is now a fourth, backed by `C:\websites` (override:
`MISSION_CONTROL_WEBSITES_ROOT`).

### Backend — discovery (read-only, no DB writes, no migration)

`backend/mission_control/discovery/websites.py` (new, ~200 lines)
- `detect_websites(roots)` → `(websites, diagnostics)`. Each immediate
  subdirectory of the root is one workspace. A **missing root is an explicit
  diagnostic**, never an invented list. Empty root → empty list, no error.
- Identity: `site_id = "website-" + slug(dirname)`, display name = humanized
  dirname plus Hugo `<title>` when present and distinct.
- **Hugo classification is evidence-based, never assumed:** `hugo.toml /
  hugo.yaml / hugo.yml / hugo.json / config.toml / config.yaml / config.yml /
  config.json`, else a `config/` dir with config files, else
  `content/ + layouts/` together. Anything else → `static` / non-Hugo with the
  reason recorded in `evidence`.
- `content_section` = first match of `post|posts|blog|articles` under
  `content/` (Hugo only).
- `website_read()` builds the display record: availability (`is_dir`),
  `launch_supported = is_hugo and available and hugo-on-PATH`, plus live
  server status when joined.

### Backend — managed Hugo previews (new, deliberately narrow)

`backend/mission_control/websites/service.py` (new, ~270 lines)
- `WebsitesState`: in-memory `{site_id → Popen, port, url, process_id}`,
  guarded by a threading lock, dead entries reaped on read.
- `resolve_site(root, site_id)`: re-runs discovery and matches the id, so
  **only currently-discovered website ids can launch** — no arbitrary paths.
- `launch_hugo(site)`: refuses non-Hugo (409) and missing dirs; resolves the
  `hugo` executable via PATH (409 with install guidance if absent); **reuses a
  running server instead of duplicating**; otherwise spawns
  `hugo server --bind 127.0.0.1 --port <free>` with `cwd=<site root>`,
  `shell=False`, allowlisted env, no `-D`/`--buildDrafts` (drafts never
  rendered). Port scan starts at **1313**, skips taken/open ports (up to 200
  tries). Waits up to 20 s for the loopback port, kills and 422s on timeout.
  **Never launches during discovery** — only via explicit POST.
- `stop_hugo(site_id)`: terminates the managed tree; 409 when nothing runs.
- Reuses `build_environment`, `port_is_open`, `WINDOWS_FLAGS` from the existing
  `processes.manager` instead of reimplementing them. Does **not** reuse
  `ProcessManager` itself: Websites have their own identity and must not
  duplicate Application/Project registry entries (explicit requirement).

### Backend — API, config, wiring

- `backend/mission_control/api/websites.py` (new): `GET /api/websites`,
  `GET /api/websites/diagnostics`, `GET /api/websites/{site_id}`,
  `POST /api/websites/{site_id}/launch`, `POST .../stop`,
  `POST .../open-path` (opens the folder with the configured editor).
- `schemas.py`: `WebsiteRead`, `WebsiteLaunchRead`.
- `config.py`: `websites_root` (`MISSION_CONTROL_WEBSITES_ROOT`, default
  `C:\websites`).
- `main.py`: router mounted; `app.state.websites = WebsitesState()` in
  lifespan.

### Frontend

- `components/Layout.tsx`: **Websites** nav item (Globe icon) in Workspace,
  right after Projects.
- `app/App.tsx`: `/websites` route.
- `pages/WebsitesPage.tsx` (new): collection view in the Books idiom —
  selector list (name + Hugo/Static + Available/Running), detail panel (path,
  evidence, Hugo config, content section, preview URL), **Launch Hugo /
  Rejoin / Stop / Open folder** actions, preview link, discovery-diagnostics
  section, "how it works" note. Explicitly no scoring, reviews, or publishing.
- `types/api.ts`: `Website`, `WebsiteLaunch` types.

## 2. Live verification (this machine, 2026-11-22)

Discovered 4 sites: `programmer.ie` (Hugo), `aibussin.com` (Hugo),
`zeromodel.org` (Hugo), `programmer.ie.notebooks` (static — correctly refused
launch with 409). All three Hugo sites launched via the real API on distinct
ports (1314/1316/1317; 1313/1315 were already occupied here, allocator skipped
them), served HTTP, and stopped cleanly. Hugo found on PATH.

## 3. Tests

- New `backend/tests/test_mc_websites_cultivation.py` (19 tests): 4-directory
  discovery, Hugo vs static classification, missing/empty root diagnostics,
  launch + reuse + distinct ports + stop (fake Popen binding real loopback
  sockets), non-Hugo/unknown-id/missing-binary errors.
- Frontend `WebsitesLayout.test.tsx` (HUD absent, nav retained, list/empty/
  launch flows) and existing suites: backend targeted files **88/88**,
  frontend **90/90**, `tsc -b` clean, `vite build` clean, `ruff` clean.

## 4. Known limitations (for the reviewer to weigh)

1. **Servers are in-memory only.** A backend restart orphans running Hugo
   processes (they keep serving; the fresh registry doesn't know them).
   Re-launch is collision-safe (port check) but the old servers become
   unmanaged. `ProcessManager` reattaches on startup; Websites does not.
2. **Duplicate-launch race.** `launch_hugo` checks-then-registers without
   holding one lock across the whole sequence; two simultaneous POSTs for the
   same site could start two servers (the second register would overwrite the
   first's entry, orphaning it). Sync endpoints run in the threadpool, so this
   is reachable. Suggest a per-site lock or atomic register-if-absent.
3. **Readiness wait blocks a worker** up to 20 s per launch (sync endpoint).
   Acceptable, but note under concurrency.
4. **Stop has no PID-identity check** (unlike `ProcessManager`, which validates
   `create_time`). Same-process Popen handle makes this low-risk, but a stale
   entry reaping path should be reviewed.
5. **Heuristic classification:** a non-Hugo dir containing `content/ +
   layouts/` is treated as Hugo. Evidence string discloses the basis; launch
   would then fail fast with Hugo's own error, surfaced as 422.
6. **Slug collisions** (two dirs normalising to one `site_id`) are not
   deduplicated — near-impossible on case-insensitive Windows FS, but unhandled.
7. **Frontend status freshness:** list is fetched on mount and reloaded after
   actions; no polling, so externally-started/stopped servers show stale state
   until reload.
8. `open-path` endpoint has **no backend test**; launch tests use a fake Popen
   (no real-Hugo test in CI).

## 5. Suggested review focus

1. `websites/service.py` `launch_hugo` — race in §4.2, error mapping
   (409 vs 422 choices), port-scan bounds, `_terminate` fallback (`kill`
   after 5 s; no `create_time` guard — compare `processes/manager.py`
   `_terminate_tree`).
2. `resolve_site` path-confinement claim — confirm no route accepts a raw
   path (all take `site_id`; `normalize_absolute_path` rejects `..`/devices).
3. `discovery/websites.py` — classification false-positive/negative cases;
   `_read_hugo_title` failure modes (swallowed → `None`, fine?).
4. `api/websites.py` — `open-path` uses editor settings; confirm failure
   modes match the Applications equivalent.
5. Frontend `WebsitesPage.tsx` — action error toasts, disabled states during
   `busy`, preview URL handling (`target="_blank" rel="noreferrer"` present?).
6. Test gaps in §4.8; consider a startup-reconciliation or orphan-adoption
   story for §4.1.
7. Confirm no Website/Application/Project registry duplication (a hard
   requirement): Websites create no `Application`, `Project`, or
   `Repository` rows — verify by code inspection of the three new backend
   files (they import none of the registry models).

## 6. File list

New: `discovery/websites.py`, `websites/__init__.py`, `websites/service.py`,
`api/websites.py`, `pages/WebsitesPage.tsx`, `tests/test_mc_websites_cultivation.py`,
`test/WebsitesLayout.test.tsx`.
Modified: `config.py`, `main.py`, `schemas.py`, `App.tsx`, `Layout.tsx`,
`types/api.ts` (all Websites hunks only; no unrelated changes).
