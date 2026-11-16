# READABILITY-ASSURANCE-01 — Stage 0 reconciliation

**Status:** DRAFT — local read-only audit complete enough to reconcile the proposal; **Stage 0 gate NOT PASSED**
**Date:** 2026-11-16
**Scope:** `C:\Projects\ai`, `C:\Projects\writer`, `C:\Projects\workbench`, `C:\Projects\mission`
**Pilot book:** `C:\books\inference\content\books\inference` (45 chapters)

This report tests the design document READABILITY-ASSURANCE-01 against the local
working trees. It is not a complete audit of all 168 Writer runtime domains or
all four full test suites. It does cover every subsystem the proposal names,
plus several it does not name and which change the ownership decision.

Where this report and the proposal disagree, the local source and tests are
treated as reality; the proposal is the intent to be amended.

---

## 1. Verdict

The product intent is sound and most of its invariants are already implemented
somewhere in the connected system. The **architecture premise is materially
out of date**:

1. Writer already has a `quality` domain (WRITER-QUALITY-01…07) that owns
   portable findings, three evaluation strategies, durable campaigns and
   improvement requests. It is not in the runtime index and is not registered
   as `runtime.quality`, but it exists and is tested.
2. `ai.scoring` is not a hypothesis. It is a full generic scoring runtime, and
   Mission Control already invokes it through
   `python -m ai.scoring.manuscript_cli` for a six-dimension manuscript rubric.
   The proposal's "not established" finding and its `ai.assessment` decision
   rule are obsolete.
3. Mission Control has no `Review` route. The cross-book review queue is a
   section of the `/writer` page; chapter quality lives on the project page.
   The proposal's "Mission Control Review" is a naming aspiration, not a live
   surface.
4. There are now **three** campaign mechanisms: `artifact/book_campaign`,
   `quality/campaign.py`, and Mission's `QualityCampaign`. The proposal names
   one and adds a reader-assurance lifecycle on top.
5. The proposal's pilot chapters 10, 34 and 44 have **no self-repair
   contracts**. Existing contracts cover chapters 01, 02, 22, 39 and 43; only
   one contract is APPROVED. Inference's Editing report is STALE.

**Recommendation (accepted 2026-11-16):** do **not** create
`reader_assurance`. The controlled **human-reader study** capability is added
to Writer `quality` as a `reader_study` service (ADR-002). Mission's
`manuscript-prose-v1` lane is migrated to Writer quality (ADR-003). The pilot
remains chapters 10, 34 and 44, which requires new contracts because none exist
for those chapters.

**Stage 0 gate:** **DESIGN PASS (conditional); implementation gate open.**
The owner decisions are recorded, but the target surfaces do not exist yet:
`runtime.quality` is unregistered, the Mission quality migration has no Writer
API, the Workbench bridge is unwired, and the pilot contracts must be generated
and approved. This is the audit doing its job, not a judgement on the product.

**2026-11-16 V2/addendum review:** the attached Claude addendum adds a
technical-integrity lane and a D1–D7 sustained-readability lane. Those are
integrated in `V2-ADDENDUM-INTEGRATION.md`. They do not revive
`reader_assurance`: technical defects project through `editorial`, D1/D2/D4/D5
extend `reader_legibility`, D3/D6 extend `editorial`, and D7 remains Gate B.
The human study stays in `quality`. The editorial branch switch also made the
Chapter 10 contract **STALE**; see C15.

---

## 2. Repository baseline

| Repo | Branch | HEAD | Working tree |
|---|---|---|---|
| `C:\Projects\writer` | `main` | `f36d2ada3` | clean |
| `C:\Projects\mission` | `main` | `245b231` | clean |
| `C:\Projects\workbench` | `codex/writer-quality-01` | `0546f87` | clean; 0 ahead / 0 behind `main` |
| `C:\Projects\ai` | `main` | `0274296` | clean |

Canonical book registry: `C:\Projects\writer\config\web\projects.yaml`.
Canonical Inference manuscript:
`C:\books\inference\content\books\inference\01-chapter.md` … `45-chapter.md`
(45 chapter files confirmed).

Writer's editing summary over registered books reports:

- 31 registered active books
- 20 with a manuscript
- 19 audited
- **0 CURRENT**
- 17 NEEDS_REVIEW
- 2 STALE (Inference is one)
- 1 NOT_RUN
- 10 BLOCKED
- 1 NO_MANUSCRIPT
- 0 ERROR

This means the whole-book programme starts from stale or absent evidence, not
from a clean 45-chapter baseline.

---

## 3. Verified ownership map

| Capability | Actual owner and path | Exposure | Verified state |
|---|---|---|---|
| Mechanical readability | `writer_runtime/domains/editing/` | `runtime.editing`; CLI `writer editing` | Registered. Facade: `audit_book`, `audit_all`, `summary`, `list_reports`, `get_report`, `report_status`, `compare`. Six independent subdimensions: `paragraph_load`, `sentence_load`, `fragmentation`, `rhythm`, `lexical_accessibility`, `section_structure`. Report store defaults to `<cwd>/.writer/editing` (Writer repo), overridable by `WRITER_EDITING_STORE`; **not** under the book's `.writer`. |
| Portable quality findings | `writer_runtime/domains/quality/` | CLI `writer quality`; **`runtime.quality` not registered** | WRITER-QUALITY-01…07. Portable-v1 DTOs, strict validation, `deterministic` / `direct` / `bounded_judge`, chapter and whole-book campaigns, `prepare-request`, `propose`, `verify`, `apply-copy`, `reevaluate`. |
| Frozen explanation contracts and gates | `writer_runtime/domains/artifact/self_repair/` | Internal package + Writer web/CLI paths; not a top-level runtime domain | `exp-contract-v1`; gates A–E; 10 stored contracts in Inference; 1 APPROVED, 9 not approved. |
| Book-wide candidate campaigns | `writer_runtime/domains/artifact/book_campaign/` | CLI `writer book-campaign`; internal package | 11 persisted Inference campaigns; 6 COMPLETE, 3 READY, 1 CREATED, 1 CANCELLED. Separate store `.writer/book-campaigns`. |
| Second campaign engine | `writer_runtime/domains/quality/campaign.py` | CLI `writer quality campaign` | Reuses execution provenance, per-chapter checkpoints. States: pending/executing/completed/partial/failed/blocked/skipped/stale. |
| Evaluation fabric | `writer_runtime/services/evaluation_fabric/` | Service/CQRS; not a domain facade | Runtime participants, evidence packets, council synthesis, idempotent commands, ZeroMQ/runtime-bus transport. Participants are runtime evaluators; there is no human-reader study type. |
| Reader-legibility review | `writer_cli/commands/reader_legibility.py` | CLI only; **not a runtime domain** | Read-only review of evidence intrusion, reproduction gaps, workflow leakage, density, repeated qualifications, placeholders. Stored reports. |
| Book-level editorial diagnosis | `writer_runtime/domains/editorial/` | `runtime.editorial` | Registered; diagnose-only, read-only, MRI-compatible state, capability gaps. |
| Advisory multi-dimension scoring | `C:\Projects\ai\src\ai\scoring\` | `ai.scoring`; CLI modules | Generic dynamic dimensions, heuristic/LLM/embedding scorers, fusion, profiles, persistence, training pairs. `manuscript-prose-v1` = clarity, argument, precision, economy, voice, structure (1–5, mean overall). |
| Mission Writer read model | `mission_control/writer/service.py` | `/api/writer/*` | Consumes Writer Editing reports, self-repair, chapter-improvement, campaigns, intel, evolution. Displays findings and Workbench decisions; does not rescore text. |
| Mission quality pipeline | `mission_control/quality/service.py`, `api/quality.py` | `/api/quality/*` | Separate append-only QualityEvaluation/QualityCampaign/QualityReview store. Invokes `ai.scoring.manuscript_cli` (or a Writer quality runner when configured). Six-dimension rubric with `overall`. |
| Workbench editing and repair | `workbench/src/workbench/app.py` | `/api/conversations/{cid}/editing`, `/self-repair`, `/chapter-improvement` | Editing decisions, self-repair A–E review, chapter-improvement opportunities/plan/run/decide. |
| Workbench portable-findings bridge | `workbench/src/workbench/quality_bridge.py` | **No route/UI wiring yet** | Pure mapping of Writer portable findings to editing rows and author decisions. Deliberately read-only; integration deferred. |
| Workbench apply/undo | `workbench/src/workbench/chapter_apply.py`, `app.py` | `/proposals/{pid}/accept`, `/undo` | Journaled atomic one-file apply, Git commit and Undo. This remains the only manuscript mutation path. |

---

## 4. Material corrections to the proposal

| # | Proposal claim | Local evidence | Consequence |
|---|---|---|---|
| C1 | Writer has 167 runtime entries; `quality` not considered | 170 directories: 167 indexed domains + 2 non-domain dirs + the unindexed `quality` domain = **168 domains**. `docs/runtime/INDEX.md` is stale. | Regenerating the index would add `quality`. Do it in a disposable worktree, not as part of a feature branch. |
| C2 | `ai.scoring` / comprehension API not established | Full `ai.scoring` package with ~27 test modules; Mission calls `manuscript_cli` and `tech_cli`. | Delete the `ai.assessment` new-primitive hypothesis. Reuse, relabel or retire the existing lane. |
| C3 | "Do not create a second generic AI scoring framework" | A generic framework already exists; Writer's mechanical Editing and Mission's LLM rubric are separate lanes on top of different semantics. | The risk is not a future duplicate; it is the **current** duplicate. Decide its disposition before adding reader assurance. |
| C4 | New `reader_assurance` lifecycle is unowned | `quality`, `eval`, `evaluation_fabric`, `reader`, `readthrough`, `reader_legibility`, `editorial`, `self_repair` collectively own most of it. | No new domain. Human study -> `quality.reader_study`; D1–D6 -> `reader_legibility`/`editorial`; D7 -> Gate B. |
| C5 | `artifact/book_campaign` is the primary 45-chapter orchestrator | `book_campaign`, `quality/campaign.py`, and Mission `QualityCampaign` all schedule durable multi-chapter work. | Pick one per work unit; do not add a fourth scheduler. |
| C6 | Mission Control has a Review surface | Routes are `/writer` and `/projects/:id`; there is no `/review`. WriterPage contains a "Cross-book review queue"; ProjectPage contains quality tabs. | Extend those, or choose one deliberately. Do not create a top-level page by assumption. |
| C7 | Mission never assigns a competing readability score | `/api/quality` records six-dimension LLM scores and `overall` (mean). It orchestrates rather than locally rescoring, but it is a competing quality lane. | Explicitly label it advisory/legacy or migrate it. Silence is not a policy. |
| C8 | Workbench will consume self-repair/campaign evidence | Self-repair and chapter-improvement are wired; the portable-quality bridge exists but has **no view wiring**. | Workbench integration is a real ticket, not a small display change. |
| C9 | Pilot chapters 10/34/44 are the contract base | At Stage 0 no contract existed for them. Three were later drafted; chapters 34/44 are source-current, but Chapter 10 is now stale after the editorial-branch switch. | Approve 34/44 after review; re-audit and re-contract Chapter 10, or pin a `main` worktree and label it historical. |
| C10 | Editing reports are current | Inference report `edit-20261025T231633334069Z-904c13cd0598` is STALE (last checked 2026-10-25); 0 CURRENT across all books. | Every pilot must re-audit before contract work; old findings must not be attached to new source. |
| C11 | AI is book-agnostic and Writer-independent | `ai.books` is a book-evolution domain that reads `.writer` evidence (`writer_evidence.py`). | The "no book knowledge" rule is already violated inside `ai`; define the boundary before adding anything. |
| C12 | `artifact/self_repair` and `artifact/book_campaign` are runtime domains | They are internal packages with CLI/web entry points; `writer info describe self_repair` and `book_campaign` fail. | Adapters must use supported CLI/web APIs or add a deliberate facade; do not assume `runtime.self_repair`. |
| C13 | Existing contract generation is a reusable approved model path | `scripts/expo03b/opencode_runner.py` calls `ai.inference.providers.opencode` directly because the Writer `runtime.models` Worker path returned BLOCKED (documented EXPO-03B blocker). The Writer web path uses `ArtifactModelsAdapter` over `runtime.models`. Worker health was `WORKER_HTTP_UNREACHABLE` before a local start. | Do not reuse the direct-runner provenance as Worker evidence and do not copy the raw `opencode-go/...` route. Draft through the web/Workbench adapter with `model_name=None` once the policy below is fixed. |
| C14 | Contract drafting inherits the private manuscript policy | `ContractService` calls the runner with `task="artifact.contract"`; `config/models.yaml` had `artifact.repair: private` but no `artifact.contract` entry, so `runtime.models` fell through to the default `training_allowed`. | **FIXED locally 2026-11-16:** added `artifact.contract: private` and `tests/runtime/test_model_task_policies.py` (2 passed). Do not draft contracts until this change is reviewed/committed and the route is preflighted. |
| C15 | The Chapter 10 pilot contract remains usable after the branch switch | The book moved to `editorial/reader-first-reconstruction` (`1403b62`), which rewrites Chapters 01–14. Chapter 10 is now `9f05…`; the contract pins `fd34…`. Chapters 34/44 still match. | Chapter 10 is **STALE**; re-audit and re-contract it or evaluate against a pinned `main` worktree. Do not approve/run the stale contract. This is the design's version-binding invariant working as intended. |

---

## 5. Live Inference state

### 5.1 Editing

- Canonical source: `C:\books\inference\content\books\inference`, 45 chapters.
- Latest stored report: `edit-20261025T231633334069Z-904c13cd0598`.
- Status: `STALE`.
- Findings recorded: 8.
- Highest-risk signal: `READABILITY.PARAGRAPH_DENSITY`, chapter 20, line 149,
  score 56.5.
- Editing reports are stored in `C:\Projects\writer\.writer\editing`, not in
  the book tree. Any consumer that assumes a per-book store will miss them.

### 5.2 Self-repair contracts

| Contract | Chapter | Status | Approved | Questions | Review |
|---|---|---|---|---|---|
| `exp-cb5b2e4d4e68a06c` | 01 | APPROVED | yes | 5 | SUPPORTED |
| `exp-a055aac0811c99e1` | 02 | DRAFT | no | 8 | — |
| `exp-6da1b3937ed60b6a` | 02 | REVIEW_REQUIRED | no | 6 | REVISION_REQUIRED |
| `exp-a31c9bb9a0f9fa1f` | 02 | REVIEW_REQUIRED | no | 7 | REVISION_REQUIRED |
| `exp-c49d72a7d97494a6` | 02 | REVIEW_REQUIRED | no | 6 | REVISION_REQUIRED |
| `exp-eea1e9bd726b11c3` | 02 | REVIEW_REQUIRED | no | 7 | SUPPORTED |
| **`exp-7f9262f8c66377cd`** | **10** | **REVIEW_REQUIRED** | no | **8** | **SUPPORTED (v2), STALE on editorial branch** |
| `exp-0200da458ff2dc8c` | 22 | REVIEW_REQUIRED | no | 8 | REVISION_REQUIRED |
| `exp-16569e7db2711a24` | 22 | REVIEW_REQUIRED | no | 6 | REVISION_REQUIRED |
| **`exp-3d0a9322fcc0771e`** | **34** | **REVIEW_REQUIRED** | no | **7** | **SUPPORTED (v2)** |
| `exp-207ab17179b41d96` | 39 | REVIEW_REQUIRED | no | 7 | SUPPORTED |
| `exp-53975ff66bd117fb` | 43 | REVIEW_REQUIRED | no | 6 | REVISION_REQUIRED |
| **`exp-c732f3709d55f68a`** | **44** | **REVIEW_REQUIRED** | no | **6** | **SUPPORTED** |

Bold rows were drafted on 2026-11-16 for the pilot, through Writer web and the
Worker-routed `runtime.models` adapter. Chapters 10 and 34 were amended to v2
after independent review, and both v2 reviews now return `SUPPORTED`. Actual
usage: 8 calls, 0 failures, $0.076499, route `default_deepseek_go`. No contract
is approved and no candidate was generated.

Implications:

- The contract mechanism is real and produces source-bound, question-rich
  contracts.
- The approval bottleneck is real: 12 of 13 are not approved.
- The pilot contracts for 34 and 44 are source-current and have `SUPPORTED`
  independent reviews; Chapter 10's contract is `SUPPORTED` but **STALE** on the
  editorial branch (pinned `fd34…`, current `9f05…`) and cannot be approved.
- Existing contracts for chapters 01/02/22/39/43 may be stale against current
  source; source hashes must be rechecked before reuse.

### 5.3 Book campaigns

11 persisted campaigns under `C:\books\inference\.writer\book-campaigns\campaigns`:
6 COMPLETE, 3 READY, 1 CREATED, 1 CANCELLED. This proves durable campaign
artifacts exist; it does not prove the 45-chapter programme has run.

### 5.4 AI / Mission quality

- `mission_control/api/quality.py` launches
  `python -m ai.scoring.manuscript_cli` with `--chapter`, `--chapter-id`,
  `--route`.
- The rubric is `manuscript-prose-v1`; dimensions are clarity, argument,
  precision, economy, voice, structure; overall is a mean.
- A Writer quality runner is optional (`MISSION_CONTROL_WRITER_QUALITY_RUNNER`);
  when unset, Writer-commanded strategies are blocked rather than faked.
- This is a second quality lane with real tests and real storage. It is not
  the Writer Editing report and must not be presented as one.

---

## 6. Test baseline (targeted)

| Repo | Command | Result |
|---|---|---|
| Writer | `.venv` unavailable for pytest; `venv\Scripts\python -m pytest tests/runtime/editing tests/runtime/quality -q` | **87 passed** |
| Workbench | `pytest tests/test_quality_bridge.py tests/test_quality_native_handoff.py tests/test_self_repair.py tests/test_chapter_apply.py -q` | **64 passed** |
| Mission | `pytest backend/tests/test_quality.py backend/tests/test_quality_writer.py backend/tests/test_writer_adapter.py -q` | **24 passed, 1 skipped** (runner not configured) |
| AI | `pytest tests/scoring -q` | **passed, exit 0** |

Not run: full suites, browser acceptance, live model calls, Hugo/EPUB/PDF.
No baseline failures were observed in the targeted suites. That is not a claim
that the full suites are green.

---

## 7. Gate S0 assessment

The proposal's own Gate S0 requires: exact owners named; reused vs new
interfaces enumerated; no conflicting source store; four-repo baselines and
blockers recorded; design reconciled with live implementation.

| Criterion | Result | Reason |
|---|---|---|
| Exact owners named | **PASS** | `editing` mechanical; `quality` findings + human study; `self_repair` contracts; `book_campaign` repair campaigns; Workbench decisions/Apply; Mission display. ADR-002/003 accepted. |
| Reused vs new enumerated | **PASS** | New code is limited to `quality.reader_study` and a quality public surface. No new parser, contract, scheduler, gateway or AI primitive. |
| No conflicting source store | **PARTIAL** | The competing Mission quality store is to be migrated, not deleted; existing history remains until mapping is accepted. Campaign boundaries are decided but not implemented. |
| Four-repo baselines/blockers recorded | **PARTIAL** | Targeted tests and Git state recorded; full suites and browser baselines are not. |
| Design reconciled with implementation | **PASS** | This document and the accepted ADRs reconcile the named subsystems. |

**Gate result: DESIGN PASS, CONDITIONAL.** Stage 1 implementation may begin only
on the tickets below; no bulk campaign or Apply is authorized.

| Implementation blocker | Owner | Exit condition |
|---|---|---|
| `runtime.quality` unregistered; no facade | Writer | Public surface for findings, campaign status and `reader_study`; contract tests. |
| Mission quality migration has no Writer API | Writer + Mission | Writer quality HTTP/bus surface; Mission read model mapping; legacy rows labelled. |
| Pilot contracts for 10/34/44 | Writer | Drafted; 34/44 source-current; Chapter 10 stale after branch switch; approval pending. |
| Inference Editing report stale | Writer | Fresh audits for 10/34/44 done; 34/44 current, Chapter 10 stale after branch switch. |
| Workbench quality bridge unwired | Workbench | Read-only view wiring with stale/source checks; tests. |
| Technical defect projection absent | Writer + book repo | Read-only ledger adapter; 5 tested defects, 4 untested; branch frozen. |
| D1–D6 sustained readability absent | Writer | Extend `reader_legibility`/`editorial`; negative-control fixtures; companion report. |
| Chapter 10 contract stale after branch switch | Writer + book repo | Re-audit and re-contract, or pin a `main` worktree and label it historical. |
| Independent review 07–14 missing | Book repo | Either produce it or restrict claims to Chapters 01–06. |
| Campaign consolidation not implemented | Writer + Mission | Documented boundary and no duplicate scheduling path. |

Proceeding to code on anything outside these tickets would violate the
proposal's own stop condition.

---

## 8. Recommended architecture adjustment

### 8.1 Keep

- `runtime.editing` as the sole mechanical readability authority.
- `exp-contract-v1` as the frozen requirements document.
- `artifact/self_repair` gates A–E for candidate-level preservation.
- Workbench as the only author Apply/Undo path.
- Mission as a read-only consumer and orchestration surface.
- No composite book score.

### 8.2 Change

1. **Do not create `reader_assurance` yet.**
   - Register/expose `runtime.quality` first, or explicitly keep it CLI-first.
   - Add a `reader_study` capability only for the genuinely new unit:
     consenting human readers, assignment, frozen questions, outcomes,
     aggregation and calibration.
   - Candidate homes: `quality` (recommended if the lifecycle shares
     findings/campaigns), `eval` (if probes are benchmark-like), or a small
     new domain (only if neither accepts the lifecycle).
2. **Pick one campaign engine per work unit.**
   - `artifact/book_campaign` for contract-bound candidate repair.
   - `quality.campaign` for portable-finding evaluation.
   - Mission `QualityCampaign` as a control-plane record only, not a third
     scheduler. If it already schedules, either make it a thin client or
     retire it.
3. **Resolve the Mission quality lane.**
   - Option A (preferred): keep `manuscript-prose-v1` as an explicitly
     labelled **legacy advisory** lane, never an Apply gate, and show Writer
     Editing separately.
   - Option B: migrate Mission evaluations to Writer quality reports and stop
     shelling out to `ai.scoring.manuscript_cli`.
   - Do not leave it unlabelled beside Writer Editing.
4. **No `ai.assessment` package.**
   - If an AI-layer change is needed, extend `ai.scoring` with the smallest
     missing protocol, or record `NO CHANGE REQUIRED`.
   - `ai.books` already breaches the book-agnostic boundary; do not widen it.
5. **Mission placement.**
   - Extend the existing `/writer` cross-book review queue and the project
     quality tabs.
   - Reuse the existing Workbench deep-link grammar:
     `/#chapter=<name>&menu=edt&drawer=editing&finding=<finding_id>`.
   - Do not add a top-level Review route without an explicit UI decision.
6. **Pilot order.**
   - Prove the end-to-end loop on chapter 01 (approved contract) or 22
     (source-bound contract, 8 questions) first.
   - Then generate and approve contracts for 10, 34 and 44 before claiming the
     proposed pilot.
   - Re-audit Editing first; the current Inference report is stale.

### 8.3 Proposed v1 scope

A defensible v1 is:

> One already-contracted chapter, re-audited; source-current contract; one
> candidate through existing gates; Workbench review and explicit Apply/Undo;
> Mission read-only display; human-reader study marked NOT_RUN.

That proves the vertical workflow without a new domain, new scheduler, new
score or new AI primitive.

---

## 9. Decisions required before Stage 1

| ID | Decision | Status / result |
|---|---|---|
| D1 | Owner for human-reader studies | **DECIDED:** add `reader_study` to Writer `quality`; no new domain. |
| D2 | Mission `manuscript-prose-v1` disposition | **DECIDED:** migrate to Writer quality; keep legacy rows read-only and labelled until mapped. |
| D3 | Campaign consolidation | **OPEN:** proposed `book_campaign` for repair candidates; `quality.campaign` for finding evaluation; Mission records, not schedules. |
| D4 | Pilot cohort | **DECIDED:** chapters 10, 34 and 44 as designed; generate new contracts. |
| D5 | `runtime.quality` registration | **OPEN but implied:** needed as the public surface for `reader_study` and Mission consumption. |
| D6 | Workbench quality bridge | **OPEN:** wire it into the editing view as a separate reviewed increment. |
| D7 | AI-layer ADR | **DECIDED:** no `ai.assessment`; migrate Mission's advisory lane to Writer quality. |

### Stage 0.5 execution order

1. **DONE 2026-11-16 — Re-audit** chapters 10, 34 and 44 with current
   source (deterministic, no model). Fresh reports and source fingerprints are
   recorded in `baseline-health.md`; all three are `PARTIAL` (single-chapter
   scope) with `stale=false`.
2. **Design the `quality` public surface**: findings, campaign status and
   `reader_study`; decide registration vs CLI-only. Add contract tests.
3. **Design the Mission migration**: Writer quality read model, legacy-row
   labelling, no new `ai.scoring.manuscript_cli` evaluations.
4. **DONE 2026-11-16 — Draft and revise contracts** for 10/34/44 through
   Writer web and the Worker-routed `runtime.models` adapter. Initial reviews:
   10 and 34 `REVISION_REQUIRED`, 44 `SUPPORTED`. Chapters 10 and 34 were
   amended to v2 with source-grounded wording fixes; both v2 reviews are now
   `SUPPORTED`. Chapters 34 and 44 remain source-current. Chapter 10 is now
   **STALE** because the book switched to `editorial/reader-first-reconstruction`
   (`9f05…` current vs `fd34…` contract). All three remain `REVIEW_REQUIRED`;
   none approved. Actual usage 8 calls / $0.076499. **Next:** re-audit and
   re-contract Chapter 10, then seek author approval of 34/44.
5. **Wire the Workbench bridge** read-only; no Apply changes.
6. **Only then** run one bounded candidate through gates A–E and the existing
   Workbench Apply/Undo on a disposable fixture.

---

## 10. Evidence index

- Writer Editing facade:
  `packages/writer-runtime/writer_runtime/domains/editing/facade.py`
- Writer Editing store:
  `packages/writer-runtime/writer_runtime/domains/editing/store.py`
- Writer quality domain:
  `packages/writer-runtime/writer_runtime/domains/quality/`
- Writer self-repair:
  `packages/writer-runtime/writer_runtime/domains/artifact/self_repair/`
- Writer book campaign:
  `packages/writer-runtime/writer_runtime/domains/artifact/book_campaign/`
- Writer evaluation fabric:
  `packages/writer-runtime/writer_runtime/services/evaluation_fabric/`
- Writer reader-legibility CLI:
  `packages/writer-cli/writer_cli/commands/reader_legibility.py`
- AI scoring:
  `src/ai/scoring/`
- AI books:
  `src/ai/books/`
- Mission Writer read model:
  `backend/mission_control/writer/service.py`, `queue.py`
- Mission quality:
  `backend/mission_control/quality/service.py`, `api/quality.py`
- Mission routes and UI:
  `frontend/src/app/App.tsx`, `frontend/src/pages/WriterPage.tsx`,
  `frontend/src/pages/ProjectPage.tsx`
- Workbench routes:
  `src/workbench/app.py`
- Workbench quality bridge:
  `src/workbench/quality_bridge.py`
- Project registry: `C:\Projects\writer\config\web\projects.yaml`
- Inference source: `C:\books\inference\content\books\inference`
- V2/addendum integration:
  `docs/readability-assurance/V2-ADDENDUM-INTEGRATION.md`
- Book defect ledger: `editorial/defect-remediation-ledger.md`
- Book known-defect tests: `tests/test_known_defects.py`
- Book fatigue pilot:
  `editorial/reader-fatigue-evaluation.md`,
  `editorial/baseline-proxies.json`, `editorial/after-proxies.json`
- Book independent review:
  `editorial/independent-review-ch01-06.md` (07–14 missing)

---

## 11. Limitations of this audit

- Not every one of the 168 Writer domains was inspected; the audit focused on
  domains named by the proposal plus collisions found by discovery.
- Full test suites, browser acceptance and live model/Hugo builds were not run.
- Mission's runtime database was not migrated or inspected row-by-row.
- Workbench was inspected at one branch (`codex/writer-quality-01`, identical
  to `main` at the recorded HEAD); concurrent work may change it.
- GitHub descriptions in the proposal may describe earlier branches. This
  report describes the local checkouts only.
