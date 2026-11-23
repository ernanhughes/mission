# MC-BOOK-PIPELINE-01 — M2 Report: Visual Production Matrix

**Status:** M2 implementation complete. Read-only; no execution, no manuscript
edits, no commit, no push. M3–M6 not started.

## 1. Changed files

| File | Change |
|---|---|
| `backend/mission_control/publication/pipeline.py` | Added `get_pipeline_overview` (cross-book summaries, shared store parses, per-book `elapsed_ms`) + mtime+size-keyed in-memory parsed-document cache (MRI reports, editing store, metadata YAML) with FIFO cap. No contract changes; all M1 tests pass unmodified. |
| `backend/mission_control/api/pipeline.py` | Added `GET /api/pipeline/overview` (after `/stages`, before `/books/{id}` so routing is unambiguous). |
| `backend/tests/test_pipeline_m1.py` | +5 tests: overview shape, overview==per-book summaries, shared-parse-once, cache invalidation on rewrite, `GET /api/pipeline/overview`. |
| `frontend/src/types/api.ts` | Pipeline types mirroring the backend contracts verbatim (stages, summaries, overview, book matrix, evidence cells, stage detail). |
| `frontend/src/features/pipeline/pipelineStatus.ts` | NEW. Pure status mapping (7 tones), coverage text, attention-filter matching, localStorage visibility. Fully unit-tested. |
| `frontend/src/features/pipeline/usePipelineVisibility.ts` | NEW. Shared visibility hook (localStorage `mc.pipeline.hiddenStages`). |
| `frontend/src/features/pipeline/ProductionOverview.tsx` | NEW. Catalogue table: one row per book, one column per configured stage, filters, column configurator, legend + the two explicit semantics notes. One overview request. |
| `frontend/src/features/pipeline/ChapterMatrix.tsx` | NEW. Chapter×stage grid for the selected book; cells are buttons with full aria labels; evidence fetched only on click. |
| `frontend/src/features/pipeline/StageEvidencePanel.tsx` | NEW. Modal with result + freshness badges kept separate, artifact ref, digest comparison, timestamps, diagnostics, stage notes, contextual failed+stale / editing-current notes. Read-only footer (M3 note). |
| `frontend/src/features/pipeline/BooksProduction.tsx` | NEW. Composition: overview + selected-book matrix + panel. |
| `frontend/src/pages/BooksPage.tsx` | Workspace/Production tabs (opt-in `showProduction`; Fiction Books unchanged). Workspace branch byte-for-byte behavior preserved. |
| `frontend/src/styles.css` | `.book-view-tabs`, `.pipe-*` table/badge/cell/filter/legend styles reusing existing theme vars. Two case-inheritance fixes for row-header notes (verified by screenshot). |
| `frontend/src/test/PipelineProduction.test.tsx` | NEW. 15 tests (status mapping, overview, matrix, panel, tab integration, visibility persistence, fiction exclusion). |
| `docs/images/mc-book-pipeline-01-m2/` | 5 screenshots (01-overview, 02-memory-matrix-full + viewport, 03-mri-01-failure, 04-mri-02-stale, 05-metadata-unknown). |

## 2. Screenshots

- `01-overview.png` — 32-book catalogue: unavailable sources with explicit errors, missing/unknown/failed·stale/current/planned columns, filters, column configurator, legend, both explicit semantics notes, computed-time footer.
- `02-memory-matrix-full.png` — full 21-chapter memory matrix: MRI failed·stale on 01, stale 02–18, missing 19–21; editing 21/21 current; validation missing; patterns/strengthening planned; graph unavailable.
- `03-mri-01-failure.png` — chapter 01 MRI detail: result `failed` + freshness `stale` as separate badges, failed+stale explainer, artifact ref, digest mismatch, timestamps, stage version, provenance.
- `04-mri-02-stale.png` — chapter 02 MRI detail (stale, passed verdict preserved).
- `05-metadata-unknown.png` — metadata detail: unknown/unknown with the no-binding explanation, no fabricated verdict.

## 3. UI behavior

- Books → Production tab (workspace default untouched). Overview loads once;
  selecting a book loads its matrix once; cell evidence loads on click.
- Filters (stale/missing/failed/unknown) match books on visible stages only.
  Column visibility persists in localStorage; hiding never alters evidence.
- Planned/unavailable stages render as `planned`/`n/a` text — never `0%`.
- Every cell carries an aria-label (`<Stage> — <chapter>: <status>`); tables
  scroll horizontally with sticky first columns; loading/error/empty states
  reuse existing components. Close returns focus (Modal); Escape closes.
- The two required interface statements are always visible: editing-current
  ≠ edited (legend footer + editing panel note); failed+stale stay separate
  (legend footer + dedicated panel explainer whenever both occur).

## 4. API changes

- NEW `GET /api/pipeline/overview` → `{registry_version, registry_source,
  book_count, elapsed_ms, stages[], books[{project_id, book_title, profile,
  applicable_chapters, discovery_error, chapter_dir, validation_enabled,
  human_approval_required, elapsed_ms, summaries}]}`. No matrices (keeps the
  catalogue request light). Unregistered books are absent by construction
  (registry-driven); discovery errors are rows with `discovery_error`, not
  404s.
- No changes to the three M1 endpoints; their contracts are frozen and the
  frontend renders them verbatim.

## 5. Performance measurements

Concern from the brief was real: naive per-book fetching re-parses the 11 MB
editing store per book, and YAML parsing dominated warm runs (profiled:
~70 ms per metadata declaration × ~460 declarations ≈ 32 s under profiler).

- Fix: each distinct store/artifact file parses **at most once per content
  version**, keyed `(path, mtime_ns, size)`. Any rewrite changes mtime/size
  → cache miss → re-read. Only successful parses are cached; errors re-read.
  Process-local, FIFO-capped (2000 entries); a restart starts cold, never stale.
- Invalidation is proven by test (rewrite stored report → status flips on
  the next read; repeated reads stable).
- 32-book catalogue: **cold 9.45 s → warm 0.59 s** (service-level).
  Live HTTP (warm): overview **0.65 s**, memory matrix **0.25 s**, MRI stage
  detail **0.22 s**. Per-book `elapsed_ms` is returned by the overview so the
  cost stays visible (slowest books: distillation/inference/pi, 2–2.7 s cold
  on first parse; sub-second warm).
- Frontend cost: overview = 1 request; matrix = 1 per selected book;
  detail = 1 per inspected cell. No N+1, no polling, manual refresh only.
- Measured pilot recomputation matches M1 exactly (memory MRI 0/21, editing
  21/21, validation 0/21, metadata 20+1; ch01 failure retained). No hardcoding:
  tests use tmp fixtures; the pilot reads live evidence each run.

## 6. Test results

- Backend: `test_pipeline_m1.py` **24/24** (incl. 5 new overview/cache/API
  tests); regression set publishing/workbench/registry/identity/integration:
  **80 passed** total. `ruff check` clean, formatted.
- Frontend: full suite **26 files / 127 tests pass** (12 new pipeline tests
  + status unit tests + tab integration; existing `BooksPage` workspace tests
  unchanged and green). `tsc --noEmit` clean.
- No manuscript, Writer artifact, publication, approval, or settings writes
  anywhere (M1 read-only test still guards the backend; the frontend issues
  only GETs).

## 7. Known limitations

1. Cold overview (~9 s for 32 books) happens once per backend restart or
   content change; it shows an explicit loading state with a refresh action.
   Further reduction would need streaming or precomputation — deferred until
   real usage proves it necessary.
2. The in-memory parse cache is per-process; multi-worker deployments warm
   independently (correctness unaffected).
3. Fiction Books keeps the workspace only (opt-in prop) — the pipeline
   endpoints already key on `project_id`, so enabling it later is a one-line
   prop change after a fiction-pilot verification.
4. Overview rows reuse workspace-independent registry titles; DB titles are
   best-effort (falls back to registry title, never blocks).
5. `elapsed_ms` measures server compute, not transfer; 11 MB-class stores
   are never sent to the browser (only digests and counts).

## 8. M3 execution integration recommendations

- The overview already identifies the work queue (stale/missing per book and
  stage). M3 should add per-stage **eligible-work previews** (chapter lists
  with cost/budget estimates from existing readiness payloads) before any
  Run button.
- Reuse `integration_executions` (duplicate-active guard, approval gates,
  bounded runner, polling) exactly as M1/M2 reuse evidence contracts; add
  per-(book, chapter, stage) keys and a cooperative cancel flag — do not
  build a new orchestrator.
- Transport decision is still open (M1 addendum §I.1): CLI-only Mission→Writer
  vs loopback HTTP client for `POST /api/artifacts/observe` and
  `POST /api/mri/observe`. The UI is ready either way: disabled-until-M3
  actions become enabled with `DisabledReasons` carrying budget/approval state.
- First M3 action stays as recommended: patterns-observe or deterministic
  MRI-observe on one book, stored as `integration_records`, with the matrix
  cell flipping on the next digest comparison — no UI data-model change needed.

**M2 success criterion holds:** an author can open Books → Production, spot
gaps across the catalogue, drill into memory's 21 chapters, and inspect the
exact artifact and digest behind every status — without running anything.
Awaiting author review before M3.
