# Baseline health — READABILITY-ASSURANCE-01

**Date:** 2026-11-16
**Purpose:** record what is green, what is stale, and what was not run before any
Stage 1 change.

## 1. Repositories

| Repo | Branch | HEAD | Tree |
|---|---|---|---|
| Writer | `main` | `2563b8453` | clean |
| Mission | `main` | `9be0c02` | clean |
| Workbench | `codex/writer-quality-01` | `0546f87` | clean; 0 ahead / 0 behind `main` |
| AI | `main` | `0274296` | clean |
| Inference book | `editorial/reader-first-reconstruction` | `1403b62` | clean; local branch only; `main` is `132820e`; 26 commits ahead |

No stashes, resets, merges or pushes were performed. The Inference book is on a
local editorial reconstruction branch, not `main`; its provenance must be frozen
before any cross-system consumption.

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

The Chapter 34 and 44 audits are source-current on the editorial branch. The
Chapter 10 audit was run against `main` (`fd34…`) and is **STALE** on the current
branch (`9f05…`); do not cite it as current. The earlier book-level Inference
report remains stale and must not be cited as the pilot baseline.

### 3.2 Contract regions

| Chapter | Region | Why this region |
|---|---|---|
| 10 | L106–108 | Logits-parity numbers (`6.1e-5`, `6.7e-4`, `5.3e-4`, `9.2e-5`), 48 positions, and explicit limits on what argmax parity does not prove. |
| 34 | L121–123 | Fresh-prefill/reuse timings (`41 ms` to `2.0 s`, `27–33 ms`), modelled contributions, the ten-call illustrative scenario, and the environmental-confounder warning. |
| 44 | L131–133 | A/A SLO shares (`0.63` vs `0.91`), trial ranges, the `0.0625` sign-flip floor, and the zero-denominator ratio boundary. |

Each region is three source lines, well inside the 60-line pilot limit. Each
contains hard numbers, a scope qualifier and a negative/limitation statement,
so a contract and Gate B can test real preservation rather than prose polish.
Contracts were drafted for these regions on 2026-11-16; Chapter 10 is now stale
after the editorial-branch switch, while 34/44 remain source-current.

## 4. Self-repair baseline

Stored contracts: 10 before this run; 13 after.

- 1 APPROVED: chapter 01, 5 questions, `exp-cb5b2e4d4e68a06c`.
- 1 DRAFT: chapter 02, 8 questions.
- 8 REVIEW_REQUIRED: chapter 02 (4), chapter 22 (2), chapter 39 (1),
  chapter 43 (1).

Before this run, no contract existed for chapters 10, 34 or 44. One run exists:
`C:\books\inference\.writer\self-repair\runs\ch01-first`.

### 4.1 Pilot contracts drafted 2026-11-16

| Chapter | Contract | Version | Status | Questions | Preservation items | Independent review | Freshness |
|---|---|---|---|---|---|---|---|
| 10 | `exp-7f9262f8c66377cd` | 2 | REVIEW_REQUIRED | 8 | 12 | `SUPPORTED` | **STALE** (`fd34…` vs `9f05…`) |
| 34 | `exp-3d0a9322fcc0771e` | 2 | REVIEW_REQUIRED | 7 | 28 | `SUPPORTED` | CURRENT |
| 44 | `exp-c732f3709d55f68a` | 1 | REVIEW_REQUIRED | 6 | 18 | `SUPPORTED` | CURRENT |

Chapter 10's contract was drafted against `main`; the current editorial branch
has a revised Chapter 10, so the contract cannot be approved or run. Chapters 34
and 44 still match their contract source revisions.

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

- Contract drafts for chapters 10/34/44 are policy-safe; the
  `artifact.contract: private` change is committed in `2563b8453`, and the three
  drafts ran successfully through the Worker-routed adapter.
- Chapter 10's contract is still **stale** after the book branch switch; policy
  safety and source freshness are separate checks.
- Do **not** fall back to `scripts/expo03b/opencode_runner.py`; it uses a direct
  OpenCode provider and a raw `opencode-go/deepseek-v4.1-flash` route. That was
  a recorded EXPO-03B workaround, not the approved path.
- `ArtifactModelsAdapter` correctly rejects `provider/model` strings and
  requires a Worker route alias or `model_name=None`. The pilot must use
  `None` (Worker policy routing) unless an approved alias is named.
- No paid inference was attempted during the route check; contract-draft usage
  is recorded in §4.2.

## 6.2 Technical integrity and fatigue baseline (editorial branch)

Book state: `editorial/reader-first-reconstruction` at `1403b62`, 26 commits
ahead of `main` (`132820e`), local only. Chapters 01–14 are revised.

### Technical

`pytest tests/test_known_defects.py -q` on Windows with torch 2.6.0+cu124:

- **4 passed, 7 xfailed**
- the 7 xfails are LEDGER-03, -04, -05a, -05b, -05c (strict), not passes
- LEDGER-09a, -09b, -14a, -14b and LEDGER-README have no regression tests

Additional baseline:

| Command | Result |
|---|---|
| `pytest tests/test_ch01_inference.py tests/test_ch02_reproducible.py tests/test_ch03_probability.py tests/test_ch05_real_generation.py -q` | 46 passed |
| `pytest tests/test_ch03_real_distributions.py -q` | 14 passed |
| `pytest tests/test_ch04_gpt2_from_scratch.py -q` | 8 passed |

The ledger's flagged
`test_ch03_real_distributions::test_numerics_report_flags_float32_overflow_threshold`
**passed here** (14/14); it remains environment-dependent, not a current Windows
failure.

### Fatigue / readability

- `editorial/fatigue_proxies.py` and `editorial/fact_guard.py` exist, but neither
  has a test module.
- `editorial/baseline-proxies.json` and `editorial/after-proxies.json` exist for
  the original/revised comparison.
- `editorial/reader-fatigue-evaluation.md` and
  `editorial/independent-review-ch01-06.md` exist.
- `editorial/independent-review-ch07-14.md` is referenced by `CHECKPOINT.md` but
  **does not exist**.
- Current `reader-legibility` on revised Ch01: 3 findings, all
  `reproduction_gap`; Ch04: 1 finding, `reproduction_gap`. D1/D2/D4 are not yet
  detected.

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
