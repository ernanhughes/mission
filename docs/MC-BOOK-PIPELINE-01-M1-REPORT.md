# MC-BOOK-PIPELINE-01 — M1 Report: Read-Only Pipeline Projection

**Status:** M1 implementation complete. No execution, no writes, no commit, no push.
**Scope:** versioned stage registry, read-only chapter/state projection, aggregation, tests, pilot.
M2–M6 explicitly not started.

## 1. Files changed

| File | Change |
|---|---|
| `backend/mission_control/publication/pipeline.py` | NEW (~700 lines). Registry v1, chapter discovery, four digest-bound readers, aggregation, `get_book_pipeline` / `get_stage_detail` / `list_stages`. Read-only: only `read_text`/`read_bytes`/`stat`/`iterdir`/glob, JSON/YAML loads, one bounded fingerprint pass. No writes anywhere. |
| `backend/mission_control/api/pipeline.py` | NEW. Three GET endpoints under `/api/pipeline`. |
| `backend/mission_control/main.py` | +2 lines: import + `include_router` for the pipeline router. |
| `backend/mission_control/writer_registry/adapter.py` | Additive only: `WriterBookDefinition.exclude_prefixes` field + parsing. No behavior change (`_count_chapters` untouched; all existing registry tests pass). |
| `backend/tests/test_pipeline_m1.py` | NEW. 19 hermetic tests covering every acceptance row. |
| `docs/MC-BOOK-PIPELINE-01-M1-REPORT.md` | This file. |

Pre-existing worktree modifications (`.writer/writer.db`, worker/inspect/praxis files from other workstreams) were not touched.

## 2. Registry design (`pipeline-stages-v1`)

Seven stages in fixed presentation order; availability is explicit per stage:

| # | Stage | Availability | Reader in M1 |
|---|---|---|---|
| 10 | `metadata` | implemented | declaration existence + YAML validity; freshness always unknown (no source binding evaluated) |
| 20 | `mri` | implemented | stored `snapshot_hash` vs recomputed chapter text |
| 30 | `patterns` | planned | none — no stored artifacts; requires M3 execution + persistence |
| 40 | `strengthening` | planned | none — model spend, gated to M5 |
| 50 | `editing` | implemented | stored `source_fingerprint` vs recomputed raw bytes |
| 60 | `validation` | implemented | stored `source_digest` vs recomputed `writer_source_digest` |
| 70 | `graph` | unavailable | none — provider wiring unverified per book (M6) |

Per-stage record: stable ID, name, description, owner, scope, applicability rule,
freshness method, prerequisites, order, availability + reason, M2 UI actions.
Unregistered readers are impossible by construction: an `implemented` stage
without a reader reports `unavailable` rather than inventing results
(defensive branch, covered by design though not reachable with v1 data).

Chapter discovery mirrors Writer's own CLI rules: registry glob pattern,
`exclude_prefixes` (newly parsed into the definition), and Writer's
`_NON_CHAPTER_STEMS` (`_index`/`index` are never chapters). For `memory` this
yields 21 applicable chapters (22 `*.md` files minus `_index.md`); the
publishing `chapter_count` of 22 is a raw glob and intentionally unchanged.

## 3. API contracts

- `GET /api/pipeline/stages` → `{registry_version, stages[]}`. No book I/O.
- `GET /api/pipeline/books/{project_id}` → book context (title, registry
  source, chapter dir/pattern, profile, validation flags, manuscript-v1
  fingerprint + non-interchangeability note), `chapters[]`, `summaries{}`
  (per-stage counts + coverage), `matrix{}` (compact per-cell
  `{chapter_id, result, freshness, has_evidence, applicable, artifact_ref}`).
- `GET /api/pipeline/books/{project_id}/stages/{stage_id}` → definition,
  summary, and full per-chapter cells (digests, match flags, provenance,
  diagnostics, detail).
- Unknown book or stage → 404 with an explicit reason (never an empty 200).
  Planned/unavailable stages return full cell lists with `result:
  unavailable` + reason, so M2 can render them without special cases.

Response size note: `matrix` cells are compact; only the stage-detail
endpoint returns full evidence. Editing summary parsing is the heaviest read
(~11 MB store, parsed once per request and shared across chapters).

## 4. Evidence and freshness semantics

- Vocabulary reused verbatim: `passed/failed/pending/unavailable/unknown` ×
  `current/stale/unknown`. Staleness never rewrites the stored verdict
  (e.g. stale MRI keeps its `passed`/`failed`).
- Four digest contracts, never interchanged; each cell records its
  `digest_algorithm`: MRI `snapshot:sha256-utf8-text` (exact Writer
  `read_text` semantics), editing `source_fingerprint:sha256-raw-bytes`,
  validation `writer_source_digest` (`sha256:` prefix, frontmatter-stripped),
  book-level `manuscript-v1` (CRLF→LF manifest, context only).
- Acceptance mapping (all covered by tests): matching digest → current;
  mismatched → stale (verdict preserved); absent → missing (`unknown/
  unknown`, no evidence); present without verifiable binding → `unknown`
  freshness; completed-with-findings → `passed` + findings in detail
  (explicitly not a health grade); stage not enabled → `not_applicable` /
  `unavailable`; new chapter → missing; missing source dir → explicit error,
  zero chapters, no fabricated current.
- Aggregation partition: `current + stale + missing + unknown == applicable`
  (asserted in tests). `passed/failed/pending` are orthogonal result tallies.
  `coverage = current/applicable`; `fully_current` requires every applicable
  chapter current. A book is never "green" on partial evidence.

## 5. Verified pilot output (`memory`, read-only, 2026-11-22)

Chapters: 21 applicable (`_index.md` excluded as a non-chapter stem).

| Stage | current | stale | missing | unknown | coverage |
|---|---|---|---|---|---|
| metadata | 0 | 0 | 1 | 20 | 0/21 current |
| mri | 0 | 18 | 3 | 0 | 0/21 current |
| editing | 21 | 0 | 0 | 0 | 21/21 current |
| validation | 0 | 0 | 21 | 0 | 0/21 current |
| patterns/strengthening/graph | — | — | — | — | unavailable/planned |

Pilot chapters 01/02/18:
- MRI: all three **stale** (reports 2026-09-22 predate the live manuscript;
  mismatch reproduced exactly). 01 additionally carries a stored
  `observer_error: OpenCode HTTP 403` despite `pass` stage statuses, so its
  result is `failed` — a real anomaly in the stored artifact, surfaced rather
  than smoothed over.
- Editing: all three **current** (2026-11-20 audit matches live bytes;
  statuses ok/ok/watch — completed analyses with signals, reported `passed`).
- Validation: **missing** — `memory` has no `.writer/validation/` output.
  Honest, not a failure of the projection.
- Metadata: declarations present and valid; freshness `unknown` by design.

Invalidation proof used isolated `/tmp` copies only (one-word flip →
snapshot mismatch → stale). No manuscript, Writer artifact, publication, or
approval state was modified; the projection itself performed zero writes
(asserted by the read-only test over fixture bytes).

Cross-check: `digital-life` (another book) has 80 stored validation chapter
reports, so the validation reader has a live positive population beyond the
tmp fixtures; `memory` exercises the missing path.

## 6. Test results

- `tests/test_pipeline_m1.py`: **19/19 pass** (registry shape, discovery,
  per-stage current/stale/missing/invalid/unbound rows, partition arithmetic,
  not-applicable books, unknown book, unavailable source, new-chapter
  dilution, digest non-interchangeability, write-nothing, reread stability,
  5 API tests incl. 404s).
- Regression: `test_publishing_summary`, `test_mc_publishing_workbench`,
  `test_writer_registry`, `test_identity` — all pass (54 total with M1).
- `ruff check` clean; `ruff format` applied.

## 7. Limitations and unresolved issues

1. **M1 verifies the source-text binding only.** Stored metadata canonical
   hashes and prompt/alignment/model versions are recorded on every MRI
   cell but not recomputed; a chapter whose text matches but whose upstream
   contract changed still reads `current`. Stated on each cell; needs M3/M4
   version-aware refresh.
2. **Editing store resolution is candidate-based** (env override →
   per-book store → walk-up from the registry file to the Writer checkout
   store). Every checked path is reported on the cell. If Writer changes its
   cwd convention, cells degrade to explicit missing, never to guesses.
3. **No caching.** The editing summary (~11 MB) is parsed once per request.
   Fine for M1/pilot; M2 should add a short-TTL cache or ETag on `mtime_ns`.
4. **Book-level `chapter_count` (22) vs pipeline applicable (21)** differ by
   documented scope (raw glob vs chapter rules). Both are shown; no silent
   reconciliation.
5. `integration_executions` durability (survives browser close, not proven
   across server restart) is carried as the M3 constraint per the brief.

## 8. M2 frontend integration proposal (no code in M1)

- Books page: new "Production" tab reusing `BooksCollectionPage` selection;
  matrix component generalized from `WriterPage` book-table + `QualityMap`
  sorting; cells link to `GET .../stages/{stage}` detail; counts rendered as
  text (`19/21 current`), never color-only; filters reuse the
  `PublishingWorkbench` attention pattern (stale/missing/blocked/review).
- Book view: chapters × stages grid from the `matrix` payload; click opens a
  `Modal`/`.resource-detail-panel` with the full cell (provenance, artifact
  ref with copy button, digest comparison, diagnostics, `available_actions`
  as disabled-until-M3 buttons with reasons, `Open in Writer` deep link).
- Polling: `useApi(..., {pollMs})` on the summary endpoint only; no sockets.
- No new source of truth: M2 renders M1 payloads verbatim; refresh actions
  stay disabled with `DisabledReasons` until M3.

**M1 acceptance: all seven gates hold** (traceable cells, authoritative
digests, applicable-denominator summaries, preserved unknowns, zero
modifications, proven invalidation, M2-ready API). Awaiting author review
before M2.
