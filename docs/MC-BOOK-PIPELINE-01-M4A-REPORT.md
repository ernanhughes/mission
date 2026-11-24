# MC-BOOK-PIPELINE-01 — M4A Report: Automatic Deterministic Maintenance

**Status:** M4A isolated pilot complete. Deterministic MRI runs automatically
when eligible; everything else stays governed. No commits, pushes,
deployments, manuscript modifications, or real-book executions. M4 (cross-book
orchestration), M5, M6 not started.

A note on provenance: no `M3: First Governed Execution Loop` brief existed in
the repo when M3 was authorized; M3 was implemented from the M1/M2 reports
plus the author's three conditions, recorded in the M3 report. This report
continues that chain: the M4A brief arrived with the M3 acceptance message
and is implemented verbatim below, scoped to the isolated pilot.

## 1. What was built

| Area | Change |
|---|---|
| Execution policy | `execution_class` on every registry stage (`automatic` only for `mri`; governed/unavailable elsewhere with reasons), `MAINTENANCE_POLICY_VERSION = pipeline-auto-v1` in `publication/maintenance.py`, standing authorization recorded in the settings table (`pipeline_auto_enabled`, default **off**; per-book `pipeline_auto_paused_books`). No schema migration. |
| Invalidation | `auto_fingerprint` over source digest + metadata digest + profile + flags version + policy version. Never timestamps, never the M2 parse cache. A policy bump requeues everything with stale fingerprints (the version-aware trigger for engine upgrades). |
| Background execution | `MaintenanceService`: sequential (one dispatch per pass max), duplicate suppression via live execution rows, 60 s cadence with debounce (digest stable across 2 passes), cooldown + 3-strikes block on consecutive identical-input failures, per-run receipts. Wired into app lifespan; loop only starts with `start_monitor` (off in tests). Survives browser closure (server-side); restart reconciles from DB + filesystem (no crash-recovery claims beyond that). |
| Pilot stage | Deterministic MRI only (`mri_observe_chapter_auto`, `approval_required=False`, identical pinned argv + strict receipt parsing as the governed M3 action). Metadata/patterns/validation/graph inspected and explicitly **not** enabled (no verifiable stored-outcome contract yet). Local embeddings already covered inside the deterministic run. |
| Result semantics | `expected_deterministic_mode` flag on MRI cells: expected fallbacks (`chapter_reducer_fallback`, `deterministic_section_observer`, `reference_section`) are presented as expected deterministic mode, not warnings; anything else surfaces as attention. Pending judgement intact — never upgraded to `passed` by a receipt. |
| UI | Maintenance strip (status, policy, pause-all/resume, dry-run "Check for work" with eligible list, active runs, recent failures), per-book pause, `auto` tags on automatic columns, governed-stage notes, Retry button on stale/missing/failed automatic cells (server resolves all paths), expected-mode explainer in the evidence panel. Refresh remains a recovery control. |
| API (all read-only except explicit controls) | `GET /maintenance`, `POST /maintenance/enabled`, `POST /maintenance/pause`, `POST /maintenance/reconcile` (optional `dry_run`), `POST /maintenance/retry` (server-side path resolution, 422 for non-automatic stages). |

## 2. Verified pilot (isolated fixtures, real Writer)

Fixture book (3 chapters: missing report, stale pre-seeded report, current
pre-seeded report), temp registry, temp DB — then enabled auto-maintenance:

- Pass 1: debounce holds everything (`waiting`), zero dispatches.
- Pass 2–3: exactly one dispatch per eligible chapter (10 s real Writer runs
  each); 03-chapter untouched (current, no provenance refresh needed).
- Result: `3/3 current` (01/02 `pending` with expected-mode fallbacks,
  03 `passed`); every execution a full receipt with deterministic provenance.
- Fixture inputs byte-identical; Writer repo `git status` clean; memory book
  untouched; only the 2 expected report pairs written under the fixture.
- Invalidation: one-word fixture edit → stale → next passes requeue exactly
  once → current again.
- Failure discipline (hermetic, fake CLI): 3 consecutive identical-input
  failures → `blocked` with reason, no further dispatch; aged failures retry
  with backoff; changed inputs reset the counter.
- Interruption: new scheduler instance mid-run sees the active execution and
  waits (no duplicate); changed-during-execution requeues once, then settles.
- Unchanged source: repeated passes dispatch nothing.

## 3. Measured cost and resource use

- Catalogue dry-run: cold **9.45 s** (one-time parse per content version),
  warm **0.59 s**; HTTP warm: overview 0.65 s, matrix 0.25 s, stage 0.22 s.
- Deterministic chapter run (24 KB technical chapter): ~10 s wall time,
  zero provider calls (provenance: `observer_model: null`,
  `quality_model: "none"`, `semantic_model: null`); local embedding compute
  only (`embed_runtime_used: true`, hnet/mxbai local model) — disclosed in
  every receipt, never a hidden charge.
- Single-flight execution (max one dispatch per pass) bounds CPU to one
  Writer run at a time; the mtime+size-keyed parse cache keeps passes cheap
  and invalidates exactly on content change (tested).

## 4. Test results

- Backend `test_pipeline_m4a.py`: **13/13** (policy switches, fingerprints,
  full decision matrix, backoff/blocked/reset, service loop, interruption,
  changed-during-execution, pause/retry/status endpoints).
- Regression: M1 (24), M3 (11), publishing, workbench, registry, identity,
  integration, adapters — **115 passed** total with M4A.
- Frontend: **27 files / 139 tests pass** (strip states/toggles/dry-run,
  auto tags, pause, retry + queued note, governed note, expected-mode and
  unexpected-warning rendering, preserved M2 behavior). `tsc` clean.
- `ruff check` / `ruff format` clean on all touched files.

## 5. Screenshots (`docs/images/mc-book-pipeline-01-m4a/`)

- `01-maintenance-check.png` — paused strip, policy version, dry-run
  eligible list (564 units catalogue-wide on missing/stale evidence, first
  two passes debounce then converge).
- `02-matrix-auto-tags.png` — MRI column carries the `auto` tag.
- `03-mri-retry.png` — stale memory chapter with Retry control and the
  recovery-control framing (nothing was executed for the screenshot).

## 6. Known limitations (carried, not hidden)

1. The loop only starts with `start_monitor`; dispatch additionally requires
   the explicit enabled flag. Both default off — correct for now, revisit at
   catalogue enablement.
2. Debounce means first observation never dispatches; the dry-run UI labels
   waiting state explicitly.
3. No cancellation of a running CLI action (inherited M1 constraint); the
   300 s runner bound plus duplicate guard are the current protections.
4. Restart recovery = reconciliation from receipts + projection (tested at
   decision level); no journaled run-state claims.
5. `beat_mode` is not echoed in Writer technical provenance; the spend
   guarantee rests on the pinned argv + code verification, and the M4A
   report recommends persisting argv per execution (still open).

## 7. Proposed next steps (for author review — none executed)

1. **Bounded memory-book pilot** (proposed, not run): enable
   `pipeline_auto_enabled` with all other books paused; expect 18 stale MRI
   chapters to refresh one per pass (~3 min total), then `21/21 current`
   with `pending` judgement preserved. Abort criteria: any failure beyond
   the tested backoff path, any write outside `.writer/mri/memory`, any
   manuscript byte change.
2. **Catalogue enablement** only after (1): unpause books incrementally;
   watch the failure/blocked lists in the strip for a full loop interval.
3. **M4 proper** (still not authorized): cross-book queue with per-target
   leases, cooperative cancel, argv persisted per receipt, then governed
   stages only with their own verified receipt contracts.

**M4A success criterion holds:** an eligible chapter change causes Mission
Control to automatically refresh its deterministic analysis, record Writer
evidence, and update production status — with no author initiation, no
duplicate work, bounded failure behavior, and honest separation of execution,
freshness, expenditure, judgement, and attention. Awaiting review before any
memory-book pilot.
