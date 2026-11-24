# MC-BOOK-PIPELINE-01 — M3 Report: First Governed Execution Loop

**Status:** M3 bounded pilot complete. One chapter, one deterministic
operation, real Writer execution, verified end to end. No manuscript edits,
no commit, no push. M4–M6 not started.

Note: no `M3: First Governed Execution Loop` brief existed in the repo. Per
author direction ("Implement directly"), M3 was scoped from the M1/M2
reports, the research, and the three M3 acceptance conditions. That scope is
recorded in §1 so the brief gap is explicit rather than silently filled.

## 1. M3 scope (as implemented)

Prove for **one chapter** that Mission Control can identify a production
gap, run an eligible analysis under governance, and independently verify the
resulting artifact — while preserving all three conditions:

1. **Writer remains authoritative.** The persisted execution receipt records
   provenance only. Current-ness flips exclusively when the read-only
   projection recomputes digests against the live chapter.
2. **No hidden AI costs or manuscript modifications.** The pilot operation is
   `writer mri chapter` with model usage disabled by construction
   (`--observer deterministic --quality-model none --semantic-model none
   --beat-mode deterministic`), run against an isolated temp fixture. No
   real manuscript was read for writing, none written.
3. **No new orchestration framework.** Execution rides the existing
   `integration_executions` lifecycle (approval gate, duplicate-active
   guard, bounded `run_tool`, persisted receipt, polling endpoints) plus one
   narrowly-scoped Writer adapter action.

Frontend intentionally untouched: the M2 UI already states execution arrives
with M3, and Run affordances need eligibility/cost UX that belongs to M4.

## 2. Files changed

| File | Change |
|---|---|
| `backend/mission_control/adapters/writer.py` | NEW action `mri_observe_chapter`: pinned deterministic argv, path/suffix/existence validation, strict receipt parsing (`mc.mri_observe_chapter.v1`), artifact-on-disk check, informational digest recomputation. |
| `backend/mission_control/publication/pipeline.py` | M1 reader refinement: a `skipped` stage (explicitly disabled judge) is neutral, not failure; at least one pass/ok still required for `passed`. Fully-`skipped` reports stay `pending`. |
| `backend/tests/test_pipeline_m3.py` | NEW. 12 tests: validation, argv pinning, receipt parsing (success / warnings-preserved / every rejection), fake-CLI execution, lifecycle (approval gate, duplicate guard, receipt persistence, polling), receipt≠current separation, skipped-neutral mapping. |
| `docs/MC-BOOK-PIPELINE-01-M3-REPORT.md` | This file. |

## 3. Why this operation

`writer mri chapter <path>` was selected after reading Writer's CLI, engine,
and services (not from a Workbench tab):

- **Explicit paths, no registry.** Unlike `editing audit` (requires a Writer
  registry project key), the chapter command takes chapter/metadata/output
  paths directly, so an isolated fixture needs no Writer config changes.
- **Deterministic by construction, verified in code.** Observer
  `DETERMINISTIC` skips provider section observation and chapter reduction
  (`engine.py:1731,1765`); `--quality-model none` returns before any judge
  call (`:2098`); `--semantic-model none` returns immediately (`:2177`);
  `--beat-mode deterministic` skips LLM verification and embedding evidence
  (`alignment.py:376-420`). Any future spend-enabling flag would have to be
  added to the pinned argv — a code change, never a parameter.
- **Stored artifact matches the M1 reader contract.** The chapter JSON
  report carries top-level `snapshot_hash` + `provenance.stage_status`,
  exactly what `read_mri_cell` compares. No new projection code needed.
- **Honest compute disclosure (found during the pilot).** The deterministic
  path uses the **local** embedding runtime (`hnet`/`mxbai-embed-large`,
  `embed_runtime_used: true` in provenance) for beat evidence ranking, and
  opens a models session for accounting (`models domain ready` in stderr,
  zero calls). No provider/model API calls: `observer_model: null`,
  `quality_model: "none"`, `semantic_model: null` in the stored provenance.
  Local embedding is disclosed in the receipt, not hidden: "no hidden AI
  costs" means no API spend and no model-driven content, not zero CPU.

## 4. Verified pilot (live, bounded, 2026-11-23)

Fixture: temp copies of memory ch01 manuscript + metadata, temp Writer
registry, temp Mission DB; real `writer.exe` (10.7 s run).

| Step | Observed |
|---|---|
| Pre-state projection | MRI `0/1 current`, missing, 1 applicable chapter |
| Dispatch | `POST …/execute` confirm=True → 200 queued; confirm=False → 409; second start while running → 409 |
| Execution | queued → running → **succeeded**, polled via fresh GETs; approval timestamp recorded; `artifact_ref` under the fixture output dir |
| Receipt | `succeeded_with_warnings`, `clean: false`, warnings `['chapter_reducer_fallback', 'deterministic_section_observer', 'reference_section']` preserved verbatim; provenance pins observer/quality/semantic + local-embed disclosure |
| Stored artifacts | Exactly 2 files: `01-chapter.mri.{json,md}` in the fixture output dir and nowhere else |
| Post-state projection | MRI `1/1 current`, result `pending` (warnings need review), `digest_match: true` — flipped by digest comparison alone |
| Isolation | Fixture inputs byte-identical; `git status` in Writer clean before/after; memory book untouched |
| Invalidation | One-word fixture edit → `0/1 current`, `stale`, verdict preserved |

The loop is therefore: **gap observed → governed run → receipt persisted →
projection verifies → invalidation still works.** At no point did the receipt
imply current-ness (proven by the pre/post projections and the hermetic
receipt≠current tests).

## 5. Test results

- `test_pipeline_m3.py`: **12/12** (validation, argv pinning incl. banned
  spend flags, receipt parsing incl. warnings-preserved and all rejections,
  fake-CLI execution, lifecycle approval/duplicate/receipt/polling,
  receipt≠current separation, skipped-neutral mapping).
- Regression: M1 (24), publishing, workbench, registry, identity,
  integration API, adapters — **102 passed** total with M3.
- `ruff check` / `ruff format` clean on all touched files (one F541 in
  untouched campaign code predates M3 and was left alone).

## 6. Limitations and open questions for M4

1. **Deterministic runs read `pending`, not `passed`.** The engine records
   `observer: warning` whenever deterministic fallbacks engage (always,
   without a provider). This is honest — the analysis completed but used
   fallbacks — and the M2 UI already renders pending distinctly. If M4 wants
   deterministic runs to read `passed`, that is a deliberate vocabulary
   decision for the author, not a code fix.
2. **`beat_mode` is not echoed in technical provenance** (Writer drops the
   key; the receipt records `null`). The spend guarantee rests on the pinned
   argv + code verification, not on the stored field. Any M4 audit of
   historical runs must re-derive mode from the receipt's argv record —
   consider logging argv into the execution result (currently only in the
   adapter code, not persisted per run).
3. **No cancellation primitive** for a running CLI action (inherited M1
   constraint): the duplicate guard prevents doubles, but a hung Writer run
   must time out (300 s clamp) rather than be cancelled. M4 fan-out needs a
   cooperative cancel flag before parallel dispatch.
4. **Single-file scope only.** The action validates one chapter + one
   optional metadata file. Whole-book runs, chunking, resume cursors, and
   per-chapter isolation are M4 work — explicitly not started.
5. **No UI affordance yet.** The M2 matrix correctly shows no Run buttons.
   M4 should add eligible-work previews (chapter lists + bounded cost
   estimates from readiness payloads) before enabling execution from the UI.

## 7. M4 recommendations

- Persist the exact argv in each execution result (closes limitation 2).
- Add cooperative cancellation to `integration_executions` first; only then
  build the sequential chapter loop with resume cursor (Writer
  `book_campaign` is the template, per the research).
- Reuse the M3 receipt shape per chapter (`mc.mri_observe_chapter.v1`
  generalizes to a per-stage receipt envelope); aggregate into the
  `pipeline_runs` + stage-state design already sketched in the research.
- Keep the transport as CLI (verified, bounded, no new client) until a
  second stage genuinely needs HTTP; the loopback decision stays open.
- First M4 pilot: whole-book deterministic MRI for `memory` (18 stale
  chapters), sequential, one execution per chapter, matrix as the scoreboard.

**M3 acceptance: the one-chapter governed loop is proven.** Awaiting author
review before any M4 work.
