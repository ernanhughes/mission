# Baseline health — READABILITY-ASSURANCE-01

**Date:** 2026-11-16
**Purpose:** record what is green, what is stale, and what was not run before any
Stage 1 change.

## 1. Repositories

| Repo | Branch | HEAD | Tree |
|---|---|---|---|
| Writer | `main` | `f36d2ada3` | modified by this work: `config/models.yaml`, `packages/writer-web/writer_web/routes/self_repair.py`, `packages/writer-web/writer_web/services/self_repair_web_service.py`, `tests/web/test_self_repair_routes.py`; new `tests/runtime/test_model_task_policies.py` |
| Mission | `main` | `245b231` | untracked `docs/readability-assurance/` |
| Workbench | `codex/writer-quality-01` | `0546f87` | clean; 0 ahead / 0 behind `main` |
| AI | `main` | `0274296` | clean |
| Inference book | `main` | `f958967` | pre-existing dirty: `15-chapter.md`, `_index.md`, `scripts/apply_edits.py`, `test.md`; concurrent untracked `content/examples/` |

No stashes, resets, merges or pushes were performed. The book's dirty paths
predate this audit and were not touched; the three pilot chapters were read
only, and their SHA-256 values match the audit and contract source revisions.

An untracked `content/examples/` tree (45 chapter example pages) appeared during
the session while separate `programmer.ie` processes were running. It is not
produced by the Writer self-repair path and was left untouched; treat it as
concurrent work, not part of this change set.

## 2. Test runs

| Repo | Command | Output |
|---|---|---|
| Writer | `venv\Scripts\python -m pytest tests/runtime/editing tests/runtime/quality -q` | `87 passed in 1.52s` |
| Writer (web/self-repair, after changes) | `pytest tests/web/test_self_repair_routes.py tests/runtime/artifact/test_self_repair.py tests/runtime/test_model_task_policies.py -q` | `32 passed` |
| Workbench | `.venv\Scripts\python -m pytest tests/test_quality_bridge.py tests/test_quality_native_handoff.py tests/test_self_repair.py tests/test_chapter_apply.py -q` | `64 passed` |
| Mission | `.venv\Scripts\python -m pytest backend/tests/test_quality.py backend/tests/test_quality_writer.py backend/tests/test_writer_adapter.py -q` | `24 passed, 1 skipped` |
| AI | `python -m pytest tests/scoring -q` | passed, exit 0 |

Environment notes:

- Writer `.venv` does not contain pytest; `venv\Scripts\python` does.
- Writer CLI is `venv\Scripts\writer.exe`; `python -m writer_cli` is not
  installed in `.venv`.
- AI is importable from the global Python 3.13 environment.
- Mission skip: `MISSION_CONTROL_WRITER_QUALITY_RUNNER` is not configured, so
  the live Writer-CLI path is skipped rather than faked.

Not run: full repositories, browser acceptance, Hugo/EPUB/PDF, task cancellation,
restart recovery. Live model calls **were** run for the three contract drafts
(6 calls) and are recorded in §4.2; no candidate generation or Apply was run.

## 3. Book baseline

Canonical Inference source:
`C:\books\inference\content\books\inference` — 45 `*-chapter.md` files.

Writer editing summary:

- 31 active books
- 20 with manuscript
- 19 audited
- **0 CURRENT**
- 17 NEEDS_REVIEW
- 2 STALE
- 1 NOT_RUN
- 10 BLOCKED
- 1 NO_MANUSCRIPT
- 0 ERROR

Inference Editing report:

- id `edit-20261025T231633334069Z-904c13cd0598`
- status `STALE`
- 8 findings
- highest risk: `READABILITY.PARAGRAPH_DENSITY`, chapter 20 line 149,
  score 56.5

Consequence: a 45-chapter campaign must first re-audit. It cannot treat the
October report as current evidence.

### 3.1 Fresh pilot audits (2026-11-16, deterministic, no model)

| Chapter | Report id | Chapter status | Report status | Source fingerprint | Findings |
|---|---|---|---|---|---|
| 10 | `edit-20261116T085441634175Z-2a94a55304a1` | `watch` (band `good`) | `PARTIAL`, stale=false | `fd34d339a1c626cacf60f6362dbbaf951752ad6148c23395cbd9c444652ef1b2` | 4 |
| 34 | `edit-20261116T085453023999Z-80e878aeeca1` | `review_required` (band `review`) | `PARTIAL`, stale=false | `92e1385fcc7447a6ec69c4f86d7b5c8bed3ebd197f57c908bf6e43e6fc0eb919` | 4 |
| 44 | `edit-20261116T085453084171Z-706c733769ec` | `watch` (band `watch`) | `PARTIAL`, stale=false | `26c5ba680811b676e1d628c15db919c9839d8d740d2b9b8454363f0845e69c8e` | 4 |

`PARTIAL` is expected for a single-chapter audit of a 45-chapter book; it is
not a failure. The important checks are `stale=false` and the recorded source
fingerprints.

Findings:

- **Ch 10:** `READABILITY.PARAGRAPH_DENSITY` (medium, line 106),
  `READABILITY.HEADING_DENSITY` (low, line 12),
  `READABILITY.TRIVIAL_SECTION` (low, line 265),
  `READABILITY.METRIC_LIMITATION` (info).
- **Ch 34:** `READABILITY.LONG_SENTENCE` (high, line 121),
  `READABILITY.PARAGRAPH_DENSITY` (high, line 26),
  `READABILITY.TRIVIAL_SECTION` (low, line 309),
  `READABILITY.METRIC_LIMITATION` (info).
- **Ch 44:** `READABILITY.LEXICAL_DIFFICULTY` (medium, line 1),
  `READABILITY.LONG_SENTENCE` (medium, line 200),
  `READABILITY.PARAGRAPH_DENSITY` (medium, line 131),
  `READABILITY.METRIC_LIMITATION` (info).

These reports are source-current for the three pilot chapters. The earlier
book-level Inference report remains stale and must not be cited as the pilot
baseline.

### 3.2 Proposed contract regions (not yet drafted)

| Chapter | Region | Why this region |
|---|---|---|
| 10 | L106–108 | Logits-parity numbers (`6.1e-5`, `6.7e-4`, `5.3e-4`, `9.2e-5`), 48 positions, and explicit limits on what argmax parity does not prove. |
| 34 | L121–123 | Fresh-prefill/reuse timings (`41 ms` to `2.0 s`, `27–33 ms`), modelled contributions, the ten-call illustrative scenario, and the environmental-confounder warning. |
| 44 | L131–133 | A/A SLO shares (`0.63` vs `0.91`), trial ranges, the `0.0625` sign-flip floor, and the zero-denominator ratio boundary. |

Each region is three source lines, well inside the 60-line pilot limit. Each
contains hard numbers, a scope qualifier and a negative/limitation statement,
so a contract and Gate B can test real preservation rather than prose polish.
These are proposals; no contract has been drafted.

## 4. Self-repair baseline

Stored contracts: 10 before this run; 13 after.

- 1 APPROVED: chapter 01, 5 questions, `exp-cb5b2e4d4e68a06c`.
- 1 DRAFT: chapter 02, 8 questions.
- 8 REVIEW_REQUIRED: chapter 02 (4), chapter 22 (2), chapter 39 (1),
  chapter 43 (1).

No contract existed for chapters 10, 34 or 44. One run exists:
`C:\books\inference\.writer\self-repair\runs\ch01-first`.

### 4.1 Pilot contracts drafted 2026-11-16

| Chapter | Contract | Version | Status | Questions | Preservation items | Independent review |
|---|---|---|---|---|---|---|
| 10 | `exp-7f9262f8c66377cd` | 2 | REVIEW_REQUIRED | 8 | 12 | `SUPPORTED` |
| 34 | `exp-3d0a9322fcc0771e` | 2 | REVIEW_REQUIRED | 7 | 28 | `SUPPORTED` |
| 44 | `exp-c732f3709d55f68a` | 1 | REVIEW_REQUIRED | 6 | 18 | `SUPPORTED` |

All three are source-current (`source_revision` equals the fresh audit
fingerprints in §3.1). No contract is approved, no candidate was generated and
no manuscript byte changed.

Initial review objections, resolved in the v2 amendments:

- **Ch 10:** the draft called the maximum absolute errors “small” although the
  source only reports the values; it dropped “the effect of” before
  “hot-swapping weights”; and it conflated “48 positions” with “48 argmax
  steps.” The v2 contract removes the unsupported “small,” restores “the effect
  of,” and separates the two counts. The reviewer also raised an optional
  question about whether full sentences should be hard (verbatim) items; that
  remains an author decision, not an automatic change.
- **Ch 34:** the draft turned “was retained but not used to calibrate the final
  time model” into “should not be used,” and “evidence of a large environmental
  confounder” into “is an environmental confounder.” Both were corrected in v2.
- **Ch 44:** `SUPPORTED` on v1; no recommended changes.

v2 reviews for 10 and 34 have **zero non-pass findings**. All three still
require author approval; `SUPPORTED` is eligibility for review, not approval.

### 4.2 Actual model usage for the pilot drafts

- 8 requests / 8 executions / 8 successes / 0 failed attempts
- 33,857 input tokens; 119,034 output tokens
- route: `default_deepseek_go` (Pi, `opencode-go/deepseek-v4.1-flash`)
- estimated paid usage: **$0.076499**
- cap: $0.25
- no direct-provider fallback, no cache hits, no reasoning tokens

Execution ids are recorded in each contract's `history` (`model-exec-…`) and
the full draft/review payloads are saved under
`C:\Users\ernan\AppData\Local\Temp\opencode\ra-contract-ch10.json`,
`…-ch34.json`, `…-ch44.json`, plus the v2 review files
`…-ch10-v2-review.json` and `…-ch34-v2-review.json`.

## 5. Campaign baseline

`C:\books\inference\.writer\book-campaigns\campaigns` contains 11 campaigns:

- 6 COMPLETE
- 3 READY (2 with chapters, 1 PLAN with 0 chapters, 1 PLAN with 1 chapter)
- 1 CREATED (0 chapters)
- 1 CANCELLED

This proves durable artifacts and resumability exist. It does not prove a
45-chapter run occurred.

## 6. Quality / scoring baseline

- Writer `runtime.quality` is **not registered** (`registered: False`,
  no facade). The CLI and internal modules exist.
- `runtime.editing` is registered and exposes the expected facade.
- `runtime.scoring`, `runtime.eval`, `runtime.artifact`, `runtime.review`,
  `runtime.readthrough`, `runtime.mediated_read`, `runtime.reader`,
  `runtime.validation`, `runtime.editorial` are registered.
- `runtime.self_repair` and `runtime.book_campaign` are not runtime domains;
  they are internal packages/CLI surfaces.
- Mission `/api/quality` invokes `ai.scoring.manuscript_cli`; the Writer
  quality runner is optional and currently unset.

## 6.1 Model execution readiness (2026-11-16)

Before a local start, `writer models health --json` reported
`WORKER_HTTP_UNREACHABLE`. After starting `C:\Projects\worker\worker.cmd serve`,
Worker reports `readiness: WORKER_READY` with executors `opencode`,
`opencode-work` and `model`.

For `artifact.repair`, `writer models explain` resolves:

| Order | Route | Provider | Model | Health |
|---|---|---|---|---|
| 1 | `default_deepseek_go` | `pi` | `opencode-go/deepseek-v4.1-flash` | unknown/unverified |
| 2 | `default_haiku_go` | `pi` | `opencode-go/claude-haiku-5-5` | unknown/unverified |
| 3 | `default_luna_go` | `pi` | `opencode-go/gpt-6-luna` | unknown/unverified |

`allow_direct_paid` is `false`; this is subscription/Pi routing, not a
direct-paid path. The routes are declared but not yet verified by a probe.

**Privacy blocker — FIXED locally 2026-11-16:** `ContractService` calls the
runner with `task="artifact.contract"`. `config/models.yaml` defined
`artifact.repair: private` but had no `artifact.contract` entry, so
`runtime.models` fell through to the default `training_allowed`. Added
`artifact.contract: private` plus
`tests/runtime/test_model_task_policies.py` (2 passed). The route still needs a
preflight before the first paid draft.

Consequences:

- Contract drafts for chapters 10/34/44 are now policy-safe in the working
  tree, but the policy change is uncommitted and the Worker routes are still
  `unknown/unverified`.
- Do **not** fall back to `scripts/expo03b/opencode_runner.py`; it uses a direct
  OpenCode provider and a raw `opencode-go/deepseek-v4.1-flash` route. That was
  a recorded EXPO-03B workaround, not the approved path.
- `ArtifactModelsAdapter` correctly rejects `provider/model` strings and
  requires a Worker route alias or `model_name=None`. The pilot must use
  `None` (Worker policy routing) unless an approved alias is named.
- No paid inference was attempted during the route check; contract-draft usage
  is recorded in §4.2.

## 7. Workbench baseline

- Editing routes: `/api/conversations/{cid}/editing`,
  `/editing/decisions`, `/editing/audit`.
- Self-repair routes: `/self-repair`, `/prepare`, `/job`, `/track`, `/refresh`,
  `/approve`, `/run`, `/decide`.
- Chapter-improvement routes: `/chapter-improvement`, `/snapshot`,
  `/opportunities`, `/plan`, `/run`, `/refresh`, `/decide`.
- Apply/Undo: `/proposals/{pid}/accept`, `/proposals/{pid}/undo`.
- Portable-quality bridge: `src/workbench/quality_bridge.py`; pure mapping,
  no route or view wiring yet.

## 8. Mission baseline

- Routes: `/writer` (WriterPage) and `/projects/:id` (ProjectPage); no
  `/review` route.
- `/api/writer/*` exposes editing books, self-repair, improvement, campaigns,
  intel, evolution, refresh, audit.
- Cross-book review queue and Workbench deep links live in WriterPage.
- Deep-link grammar:
  `/#chapter=<name>&menu=edt&drawer=editing&finding=<finding_id>`.
- `/api/quality/*` is a separate quality pipeline with its own DB tables and
  campaigns.

## 9. Known limitations

- The targeted tests are green; full-suite baseline is unmeasured.
- No live model authorization was exercised.
- No browser acceptance was performed in this stage.
- Workbench branch is identical to `main` by commit count but may be changed by
  concurrent work.
- The Writer runtime index is stale (167 rows; 168 domains, `quality` missing).
  Do not regenerate it in place without a disposable worktree.
