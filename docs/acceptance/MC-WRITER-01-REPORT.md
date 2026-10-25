# MC-WRITER-01 — Writer Editing integration acceptance

Date: 2026-10-24

Recommendation: **ADOPT** the Writer Editing runtime and Mission Control adapter
for bounded, read-only readability experiments. **REFINE** before treating the
thresholds as editorial policy, broadening to arbitrary repositories, or adding
manuscript mutation.

## 1. Starting repositories

| Repository | Branch | HEAD | Pre-existing changes |
| --- | --- | --- | --- |
| Writer | `main` | `da0ef153e` | 3 modified: `docs/runtime/INDEX.md`, `.../models/providers/worker.py`, `tests/runtime/models/test_worker_provider.py` |
| Mission Control | `main` | `9a3d45b` | clean |
| Calibration: Language | `main` | `c7e7953` | clean, treated read-only |
| Next | `main` | `491b501` | clean |
| Worker | `main` | `0aecefa` | 33 pre-existing changes preserved |
| CoCoder | `cc-r06-p0-codeai-qualification` | `f4e90d6` | 36 pre-existing changes preserved |
| Work | `main` | `e79e68c` | 1 pre-existing change preserved |

Writer's pre-existing `.cocoder/` directory and the existing untracked content
were preserved. Mission Control has no `.cocoder/`.

## 2. Documentation and architecture discovered

Writer:

- root `AGENTS.md` (Worker-owned model execution; no provider clients in Writer);
- runtime domain index and metadata/MRI/improve (strengthen) contracts;
- CLI command registry and output envelopes;
- project registry (`config/web/projects.yaml`), project loader and manuscript
  resolver;
- source-aware Markdown parser and text-structure/statistics primitives;
- `.writer` report/artifact conventions, schema conventions and domain tests;
- docs-architecture and CLI-docs coverage tests.

Mission Control:

- loopback-only FastAPI/SQLite architecture;
- application contracts and read-only adapter protocol (`mc09.1`);
- integration resources, durable execution lifecycle, origins and approval
  guards;
- existing application views, type contracts and frontend test conventions.

Language calibration read only: `scripts/prose_readability.py`,
`readability-baseline.json`, `readability-final.json`,
`prose-revision-report.md`, `prose-revision-status.md`, Chapter 3 and repository
`AGENTS.md`.

The calibration lesson was retained: paragraph length is not a quality target;
the runtime detects both density and fragmentation/uniform cadence. Flesch does
not establish comprehension.

## 3. Writer files changed

Added:

- `packages/writer-runtime/writer_runtime/domains/editing/{__init__,dto,engine,facade,metrics,parser,profile,scoring,store}.py`
- `.../domains/editing/schemas/writer-editing-report-v1.schema.json`
- `packages/writer-cli/writer_cli/commands/editing.py`
- `tests/runtime/editing/test_editing_runtime.py`
- `docs/runtime/editing/{README,SKILL,STATE,SPEC.instructions,PROMPT}.md`
- `docs/cli/editing/README.md`
- `docs/architecture/writer-editing-runtime.md`
- `docs/architecture/wrt-edit-01-acceptance.md`

Modified:

- `packages/writer-runtime/writer_runtime/bootstrap.py` — register `editing`
- `packages/writer-cli/writer_cli/main.py` — register `writer editing`
- `docs/cli/INDEX.md` - command count/docs
- `docs/runtime/INDEX.md` - editing domain entry (this file already had
  pre-existing modifications)
- `README.md`, `docs/architecture/cli-system.md`, `docs/architecture/overview.md`
  - command count and Editing runtime link

## 4. Mission Control files changed

Added:

- `backend/mission_control/adapters/writer.py` — CLI contract adapter and
  approved audit action
- `backend/mission_control/api/writer.py` — books/refresh/audit routes
- `backend/mission_control/writer/{__init__,service}.py` — read model and queue
- `backend/mission_control/persistence/migrations/005_writer_editing_integration.sql`
- `backend/tests/test_writer_adapter.py`, `test_writer_api.py`
- `frontend/src/pages/WriterPage.tsx`
- `frontend/src/test/WriterPage.test.tsx`
- `docs/MC-WRITER-01-WRITER-INTEGRATION.md`
- `docs/acceptance/mc-writer-01/` evidence and fixtures
- `docs/milestones/MC-WRITER-01.md`

Modified:

- adapter registry/base and integration service — Writer app/action support
- `main.py`, `schemas.py` — Writer API/contracts
- `config/defaults/applications.yaml` — Writer adapter defaults
- migration test — schema version 5
- frontend routes, navigation, command palette, types, styles
- README, security, milestone index

## 5. Final runtime boundary

Writer owns:

```text
manuscript discovery → chapter inventory → prose projection → readability
metrics → independent scores → findings/locators → fingerprints → report
versioning → stale/compare evidence
```

Mission Control owns:

```text
Writer adapter/client → durable audit action → cached evidence → book table →
chapter drill-down → cross-book queue → current/stale/not-run display
```

Mission Control imports no Writer scoring or Markdown code. Books remain source
artifacts. Audit is read-only. No `plan`/`apply`, automatic correction,
publishing, Movies integration or paid model call was added.

## 6. Report contract

- Schema: `writer-editing-report-v1`
- Report version: `1.0.0`
- Static schema:
  `packages/writer-runtime/writer_runtime/domains/editing/schemas/writer-editing-report-v1.schema.json`
- Profile: `technical-nonfiction-v1`, version `1.0.0`
- Store: `C:\Projects\writer\.writer\editing` (git-ignored)
- Summary contract: `writer-editing-summary-v1` in the CLI envelope
  `writer.editing.cli.v1`

The report contains run/tool identity, profile and thresholds, book identity,
source revision/dirty state, scope, source fingerprints, chapter and section
inventory, independent dimension results, findings and locators, limitations,
errors, partial state and a canonical fingerprint.

## 7. Dimensions and formulas

All scores are 0–100 diagnostics. Bands: good ≥80, watch ≥60, review ≥40,
high <40, insufficient evidence `not_applicable`. No composite score.

```text
paragraph_load = 100
  - 55*share(paragraphs > 100 words)
  - 25*share(paragraphs > 140 words)
  - 20*max(0,(p90-90)/90)
  - 10*max(0,(longest-160)/160)

sentence_load = 100
  - 65*share(sentences > 35 words)
  - 20*share(sentences > 50 words)
  - 15*max(0,(p90-30)/30)

fragmentation = 100
  - 70*max(0,short_share-0.45)
  - 40*max(0,one_sentence_share-0.55)
  - 30*max(0,(max_short_run-4)/4)
  - 20*max(0,fragment_like_share-0.25)

rhythm = 100
  - 55*max(0,uniform_paragraph_share-0.55)
  - 25 if narrow_distribution
  - 25*max(0,dominant_sentence_count_share-0.65)

lexical_accessibility = 100
  - 3*max(0,40-FRE)
  - 1*max(0,FRE-65)
  - 4*max(0,FK-16)

section_structure = 100
  - 45*share(sections > 2500 words)
  - 25*share(sections > 4000 words)
  - 20*share(sections < 20 words)
  - heading-density penalty when >=1000 prose words and >=4 sections
  - 10 when one section carries >3000 words
```

Every dimension result in the report includes these weights and thresholds in
its `scoring` block. Findings include `READABILITY.*` codes, severity, locator,
measured evidence, reason, bounded guidance and limitations.

## 8. Tests and exact results

| Check | Result |
| --- | --- |
| Writer focused Editing tests | **17 passed** |
| Writer focused Ruff | passed |
| Writer CLI docs coverage | passed |
| Writer docs-architecture tests | **17 passed, 2 failed (pre-existing)** |
| Writer full suite | **collection blocked (pre-existing IndentationError)** |
| Mission Control backend | **63 passed**, 1 pre-existing warning |
| Mission Control Ruff | passed |
| Mission Control frontend | **29 passed** |
| Production frontend build | passed |
| Browser E2E | **8 steps passed**, 0 console/page errors |
| Writer-to-MC audit action | succeeded (`exec-42b9faeb4b0b49ab`) |
| `git diff --check` | passed (line-ending warnings only) |

Pre-existing Writer failures:

- `metadata_generation` has no runtime docs dir/SKILL, so two docs-architecture
  tests fail. Not caused by and not repaired in this milestone.
- Full-suite collection stops at
  `tests/runtime/domains/test_mri_semantic_adjudication.py:493` with an
  `IndentationError`. The file is unmodified in this working tree.

Evidence files are under `docs/acceptance/mc-writer-01/`.

## 9. Real acceptance identifiers

| Run | Identifier |
| --- | --- |
| Language whole-book report | `edit-20261024T235402252638Z-4c44a9e02cc3` |
| Language canonical fingerprint | `4c44a9e02cc3a83b876836c21f760f67e402ad81b52730d12fea58593cfebdae` |
| Repeated audit | same fingerprint on both runs |
| Language chapter 03 read-only report | `edit-20261024T234647327303Z-1eb6a7762267` |
| Dense fixture | `edit-20261024T234652099917Z-098282e998d2` |
| Fragmented fixture | `edit-20261024T234652276937Z-f900e4907dc2` |
| Uniform-cadence fixture | `edit-20261024T234652460575Z-dbfd96ac3591` |
| Live MC audit execution | `exec-42b9faeb4b0b49ab` |
| Browser stale cycle | `browser-e2e.json` |

The stored Language report was retrieved with `writer editing show` and checked
with `writer editing status`; it returned `writer-editing-report-v1`, 38 chapters
and `NEEDS_REVIEW` with `stale=false`.

The Language manuscript tree hash was identical before and after the audits
(39 Markdown files, SHA-256
`e17a5a301ed412da9061245fb73d955f3ec3c8820f8cc3658cf6829df32ebaeb`). The fixture
fingerprint changed and was restored; MC showed `STALE` then current.

## 10. Registered books and audit coverage

Live registry: 29 active projects.

- **7 with recognised Markdown chapters and current reports**
- **21 blocked** because their configured content roots are absent
- **1 without a manuscript** (`writer`: Python project, no Markdown chapters)
- 0 stale immediately after the audit
- 0 not run

Blocked projects: `agents-from-first-principles`, `applied-ai`, `axiom_zero`,
`becoming_alice`, `browser-ai-from-first-principles`, `coin`, `collapse`,
`context`, `debugging-ai`, `digital-life`, `dspy-from-first-principles`,
`embeddings-from-first-principles`, `goblins`, `hallucination-from-first-principles`,
`latent`, `memory`, `pi`, `projection`, `pytorch-from-first-principles`,
`softwear`, `techno_prophet`.

Most of these point at `C:\Projects\new-books`, which is absent. Mission Control
does not substitute lookalike paths.

## 11. Cross-book results

| Project | Chapters | Status | Worst signal | Para | Sent | Frag | Rhythm | Lexical | Section |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| advanced-agents | 46 | NEEDS_REVIEW | fragmentation 0.0 | 100 | 99.7 | 0 | 41.7 | 77.8 | 0 |
| cellular-automata | 59 | NEEDS_REVIEW | fragmentation 0.0 | 100 | 96.7 | 0 | 43.9 | 84.4 | 55.7 |
| models | 12 | NEEDS_REVIEW | fragmentation 0.0 | 100 | 99.8 | 0 | 42.1 | 100 | 0 |
| programmer_ie (Digital Life content) | 19 | NEEDS_REVIEW | fragmentation 1.2 | 99.3 | 96.4 | 0 | 86.9 | 85.9 | 75.7 |
| freestyle-cognition | 32 | NEEDS_REVIEW | fragmentation 6.8 | 99.5 | 98.6 | 0 | 53.5 | 72.5 | 52.6 |
| agent-architectures | 16 | NEEDS_REVIEW | fragmentation 15.7 | 98.9 | 96.1 | 15.7 | 93.6 | 0 | 69.6 |
| language | 38 | NEEDS_REVIEW | fragmentation 29.3 | 61 | 95.9 | 29.3 | 53.6 | 47.9 | 97.3 |

Synthetic fixtures:

| Fixture | Expected signal | Observed |
| --- | --- | --- |
| Dense (6 × 150-word paragraphs) | density | paragraph load 6.7, sentence 0, density/long-sentence findings |
| Fragmented (12 × "Short line.") | fragmentation | fragmentation 0.0, 100% short/one-sentence, max run 11 |
| Uniform (10 × 60-word paragraphs) | cadence | rhythm 41.5, narrow distribution true, uniform-cadence finding |

### What this does to the hypothesis

- Language shows a **watch-level paragraph-load signal** (worst 61, no chapter
  flagged) and lexical review in 4 chapters, not a high-density failure.
- Embeddings, Context and Debugging AI could not be tested: their configured
  content roots are absent.
- Digital Life (through the `programmer_ie` registry entry) does show
  fragmentation (worst 1.2), but **so do all other accessible technical books**,
  including Language (29.3). Hallucination could not be tested.
- The narrow "Digital Life and Hallucination have the fragmentation problem"
  hypothesis is therefore not supported. Fragmentation is widespread in the
  accessible sample.
- This is calibration evidence, not a verdict on the books. The thresholds are
  not yet genre-normalised and all seven books have at least one high/medium
  finding.

## 12. Mission Control view and startup

- URL: `http://127.0.0.1:8790/writer`
- Navigation: **Engines → Writer**; command palette entry **Writer editing**.
- API: `GET /api/writer/books`, `POST /api/writer/refresh`,
  `POST /api/writer/audit`.
- Audit action: `POST /api/integrations/writer/actions/audit_registered_books/execute`
  with explicit confirmation; execution history is in the existing
  `integration_executions` lifecycle.
- Live service: healthy on `127.0.0.1:8790`; Writer adapter available with 29
  books, 7 audited.
- The acceptance server ran separately on `127.0.0.1:8791` with a synthetic
  registry; it was stopped after the browser run.
- Both documented application start paths were exercised: Writer CLI and the
  Mission Control backend/SPA.

## 13. Unresolved risks

- Readability thresholds are provisional and not calibrated across genres,
  authors, fiction/nonfiction, or publication formats.
- Flesch metrics do not establish comprehension; technical vocabulary and proper
  names distort them.
- All accessible technical books produced fragmentation review signals. This may
  be a real prose pattern or a threshold/paragraph-convention problem; further
  calibration is required before any edit is proposed.
- 21 registered projects are inaccessible on this machine, so the hypothesis
  about Embeddings, Context, Debugging AI, Hallucination and standalone Digital
  Life is untested.
- `section_structure` can show review-level scores for heading/trivial-section
  patterns; it is navigation evidence, not prose quality.
- The audit action is durable but synchronous from the user's perspective. There
  is no streaming progress or cancellation acknowledgement inside Writer.
- The latest report can be selected-chapter-only; Mission Control labels that
  book `PARTIAL` rather than pretending it covered the whole book.
- Writer docs-architecture tests and full-suite collection have pre-existing
  failures unrelated to this milestone.
- No editorial decision, manuscript change, `plan`/`apply`, or publication was
  produced.

## 14. Next recommended milestone

**WRT-EDIT-02 — Calibrate and extend Editing.** Add a second independent
dimension (suggested: clarity or repetition), calibrate thresholds against
accessible books/fixtures, and add asynchronous progress/cancellation to the
audit runner without changing `writer-editing-report-v1`. Keep `plan`/`apply`
behind separate authorisation.

## 15. Final git state

Both repositories remain uncommitted and unpushed, as required.

| Repository | HEAD | Working tree |
| --- | --- | --- |
| Writer | `da0ef153e` | 9 modified (3 pre-existing preserved) + 7 new implementation/doc paths |
| Mission Control | `9a3d45b` | 17 modified + 12 new integration, migration, test, page and acceptance paths |

No push, pull request, paid model call, source-manuscript edit or book repository
write occurred. Report artifacts are in Writer's git-ignored `.writer/editing`
store.
