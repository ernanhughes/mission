# READABILITY-ASSURANCE-01B — V2 / Claude-addendum integration

**Status:** design enhancement, source-informed; implementation NOT RUN
**Date:** 2026-11-16
**Inputs:** `READABILITY-ASSURANCE-CROSS-SYSTEM-DESIGN-v2.md` and
`READABILITY-ASSURANCE-CLAUDE-REVIEW-ADDENDUM.md`
**Local evidence:** `C:\books\inference` on
`editorial/reader-first-reconstruction` at `1403b62`; `main` at `132820e`
**Companion:** `STAGE0-RECONCILIATION.md`, `ADRs.md`, `ownership-map.md`,
`baseline-health.md`

This document reviews the V2/addendum against the committed Stage 0 audit and
the local Inference repository. It preserves the V2 intent, corrects the
premises that local evidence contradicts, and proposes the two-lane ownership
boundary the addendum needs.

---

## 1. Verdict

The addendum is **materially correct and locally supported**. It adds two things
the original design lacked:

1. a **technical-integrity lane** with a real defect ledger, strict regression
   tests, frozen evidence and a `fix:`/`editorial:` commit boundary;
2. a **sustained-readability lane** with D1–D7, negative controls and a
   human-reader protocol that does not treat model judgment as reader evidence.

The V2 main body still carries the Stage 0 defects already recorded:
`ai.scoring` exists and is used by Mission; Writer has an unindexed `quality`
domain; there are multiple campaign mechanisms; Mission has no `/review` route;
and the proposed `reader_assurance` domain is not justified.

**Decision:** keep the V2/addendum goals, but implement them as **two
independent evidence lanes projected through existing owners**, not as a new
scoring platform or a new editor.

| Lane | Canonical evidence | Writer owner | Review surface |
|---|---|---|---|
| Technical integrity | Book repo ledger + code/tests + frozen results | Read-only adapter in Writer `editorial` (recommended) | Workbench `Technical correctness`; Mission technical/integrity lane |
| Sustained readability | Source text + `reader_legibility`/`editorial` findings + human study | `reader_legibility` (per chapter) + `editorial` (cross-chapter); `quality` for human study records | Workbench `Sustained readability`; Mission review lane |
| Preservation | `exp-contract-v1` + Gates A–E | `artifact/self_repair` | Workbench gate view |
| Human outcome | Study protocol + observations | `quality.reader_study` | Workbench/Mission, `NOT_RUN` until observed |

No lane may close another lane's issue. A code fix cannot prove readability; a
readability preference cannot prove correctness; a model score cannot prove
human comprehension.

---

## 2. Local evidence register

### 2.1 Repository state

- Book branch: `editorial/reader-first-reconstruction`, local only, clean,
  `1403b62`; `main` `132820e`; 26 commits ahead of `main`.
- Chapters 01–14 revised. Chapters 15–45 not yet reconstructed.
- Independent review covers chapters 01–06
  (`editorial/independent-review-ch01-06.md`). The checkpoint references a
  chapters 07–14 review, but
  `editorial/independent-review-ch07-14.md` **does not exist**.
- `editorial/baseline-proxies.json` and `editorial/after-proxies.json` exist.
- `editorial/defect-remediation-ledger.md`, `editorial/fatigue_proxies.py`,
  `editorial/fact_guard.py`, and `tests/test_known_defects.py` exist.
- The existing Chapter 10 self-repair contract is **stale** on this branch
  (`fd34…` contract vs `9f05…` source); Chapters 34/44 still match.
- Neither `fatigue_proxies.py` nor `fact_guard.py` has a test module. That is an
  integration risk, not a reason to ignore them.

### 2.2 Test status on this Windows machine

Torch is present: `2.6.0+cu124`.

| Command | Result |
|---|---|
| `pytest tests/test_known_defects.py -q` | **4 passed, 7 xfailed** |
| `pytest tests/test_ch01_inference.py tests/test_ch02_reproducible.py tests/test_ch03_probability.py tests/test_ch05_real_generation.py -q` | **46 passed** |
| `pytest tests/test_ch03_real_distributions.py -q` | **14 passed** |
| `pytest tests/test_ch04_gpt2_from_scratch.py -q` | **8 passed** |

The ledger's "pre-existing failure"
`test_ch03_real_distributions::test_numerics_report_flags_float32_overflow_threshold`
**did not reproduce here**. It must be recorded as environment-dependent, not
as a currently failing Windows test.

The 7 xfails are the open defects, not passes:

- `LEDGER-03` sampling metadata
- `LEDGER-04` triangular/dense FLOP denominator
- `LEDGER-05a` EOS hold-back
- `LEDGER-05b` final flush bypasses `on_text`
- `LEDGER-05c` overlapping stop-string chunk dependence

`LEDGER-09a`, `LEDGER-09b`, `LEDGER-14a`, `LEDGER-14b` and `LEDGER-README`
have ledger entries but **no regression tests yet**. They cannot enter T1 as
"reproduced".

### 2.3 Existing analyzer coverage

Running the current deterministic `reader-legibility` analyzer on the revised
branch:

- Chapter 01: 3 findings, all `reproduction_gap`.
- Chapter 04: 1 finding, all `reproduction_gap`.

It did **not** detect D1 explanation fragmentation, D2 relocatable
qualification, or D4 repeated limitation. That is expected: the analyzer's
current vocabulary is evidence intrusion, reproduction gap, internal workflow
leakage, unnecessary technical density, repeated qualifications and
placeholders. It is the right base for D1/D4/D5, not a finished D1–D6 system.

### 2.4 Review evidence is real but conflicted

The independent review found:

- one **UNSAFE** Chapter 2 claim: "weights unchanged across modes" converted
  from a modal statement into an observation the chapter says was not tested;
- one misleading Chapter 5 opening attributing a 27× gap to seriality when the
  numbers show most of it is the missing KV cache;
- six **WEAKENED** relocations, including "pinned", "Import dominates",
  "settles" and "Quality: No";
- two overclaiming chapter-end bridges.

All reported fixes are now in the branch, but the review is a second model's
judgment, not reader evidence. The initial scores in
`reader-fatigue-evaluation.md` were produced by the revising model and remain
`CONFLICTED_MODEL_JUDGEMENT`.

---

## 3. Corrections to the V2/addendum premises

| # | V2/addendum statement | Local evidence | Consequence |
|---|---|---|---|
| E1 | Writer has 167 runtime entries; map through the current index | 168 domain directories, 167 indexed; `quality` is unindexed; `reader_legibility` is a CLI/core analyzer, not a runtime domain | Regenerate the index in a disposable worktree; do not assume `runtime.reader_legibility` exists. |
| E2 | `ai.scoring` and evaluation fabric are open questions | `ai.scoring` is a full generic scorer; Mission already calls `ai.scoring.manuscript_cli` | No new `ai.assessment`; the migration decision in ADR-003 stands. |
| E3 | Writer Reader Assurance is a proposed runtime | `quality`, `reader_legibility`, `editorial`, `evaluation_fabric`, `eval` and `readthrough` overlap the lifecycle | Do not create `reader_assurance`; extend the closest owner. |
| E4 | Mission Control Review is a page | No `/review` route; `/writer` has the cross-book queue; project pages have technical/quality lanes | Extend `/writer` and project tabs; do not add a page by assumption. |
| E5 | `test_historical_evidence_unchanged` may need extension to Chapter 04 | It already protects `research/ch03`, `ch04`, `ch05` | The protection exists; verify hashes, do not duplicate it. |
| E6 | A pre-existing float32 test failure exists | 14/14 pass on Windows with torch 2.6 | Classify by environment; do not attribute it to a repair. |
| E7 | Chapters 01–05 are the pilot | Branch has 01–14 revised; 01–06 independently reviewed; 07–14 review missing | Freeze the branch; do not use unrevised 15–45 as before/after evidence. |
| E8 | `editorial/fact_guard.py` is reusable after confirming its implementation | Present and simple, but untested and only a chapter-level diff; no unit tests | Wrap it as a fixture/adapter behind Gate B; do not make it a second gate. |
| E9 | `editorial/fatigue_proxies.py` provides diagnostics | It is a proxy script with a caveat-interruption helper; no tests | Use it as `MEASURED_TEXT` input, never as acceptance evidence. |
| E10 | Mission has no technical integrity lane | Mission already has `/api/technical` claims/evidence/verification campaigns (MC-QUALITY-03B) | Reuse the display/verification vocabulary; do **not** conflate manuscript claims with code defects. |

---

## 4. Technical-integrity lane

### 4.1 Ownership

- **Book repository owns the canonical defect ledger, code, tests, rerun
  artefacts and Git history.** Writer never edits them.
- **Writer `editorial` owns a read-only technical-dependency projection**
  (recommended), because it already produces book/chapter diagnosis, evidence,
  capability gaps and provenance. It does not become an issue tracker.
- **Mission** displays the projection and links to exact source/test/run
  records. Its existing `TechnicalClaim`/`TechnicalEvidence` tables remain
  manuscript-claim verification, not code-defect storage.
- **Workbench** shows a `Technical correctness` lane and links to the owning
  code/test; it does not apply code patches through the prose editor.

If a separate runtime surface is later required, add a thin
`runtime.editorial.technical_dependencies`/CLI projection rather than a new
`technical_integrity` domain.

Alternative owner: a read model inside `quality` if defects must be triaged
alongside portable findings. That choice must be recorded before code.
`validation` is not the owner: it checks publication profiles, not code
correctness. The canonical ledger remains in the book repo either way.

### 4.2 `technical-defect-v1` projection

The addendum's DTO is a good start. The local version must carry:

```json
{
  "schema_version": "technical-defect-v1",
  "defect_id": "LEDGER-04",
  "project_id": "inference",
  "chapter_id": "04-chapter.md",
  "category": "measurement_denominator",
  "statement": "cmd_timing divides by a triangular attention FLOP count while attention() executes dense T×T products.",
  "severity": "technical_review_required",
  "status": "REPRODUCED",
  "source": {
    "ledger_path": "editorial/defect-remediation-ledger.md",
    "ledger_sha256": "<full hex>",
    "code_paths": ["examples/ch04/gpt2_from_scratch.py"],
    "source_revision": "<book git commit>",
    "frozen_evidence": ["research/ch04/results.json"],
    "frozen_sha256": "<full hex>"
  },
  "test_refs": ["tests/test_known_defects.py::test_dense_whole_sequence_flops_helper"],
  "test_status": "XFAIL_STRICT",
  "correction_required": true,
  "rerun_refs": [],
  "git_commit_class": "fix",
  "evidence_class": "CODE_TEST",
  "limitations": ["Corrected measured rates require a new rerun; archived times remain valid for the original code."]
}
```

Rules:

- `test_status` is derived by running the named test, not copied from prose.
- `XFAIL_STRICT` means the defect is documented and open, never "passed".
- A repair commit removes the marker; the projection must show the test now
  passes before `FIXED_PENDING_RERUN`.
- `frozen_sha256` is the normalized hash of the original result file; a changed
  hash is a hard integrity failure.
- No generated "defect score"; status is categorical.

### 4.3 Lifecycle and gates

`REPORTED -> REPRODUCED -> REGRESSION_TEST_RECORDED -> FIXED_PENDING_RERUN ->
RERUN_RECORDED -> MANUSCRIPT_RECONCILED -> VERIFIED`

Alternatives: `BLOCKED`, `INCONCLUSIVE`, `WONT_FIX_WITH_RATIONALE`, `STALE`.

| Gate | Criterion | Unknown result |
|---|---|---|
| T1 Reproduction | Test or a recorded reproduction exists; source pin | `REPRODUCTION_PENDING` |
| T2 Repair | `fix:` commit; strict xfail removed; targeted tests pass | `BLOCKED`/`PARTIAL` |
| T3 Corrected evidence | New rerun record with command, environment, date, workload, output hash; original retained | `CORRECTION_PENDING` |
| T4 Manuscript reconciliation | Chapter cites original and correction; formulas match executed code | `MANUSCRIPT_PENDING` |

A code-only fix may skip T3 only with a positive rationale and a test that
establishes the scope. It may never overwrite the original result.

### 4.4 Local defect status

| Defect | Test present | Current status |
|---|---|---|
| LEDGER-03 | yes, strict xfail | reproduced/Documented |
| LEDGER-04 | yes, strict xfail | reproduced/Documented |
| LEDGER-05a | yes, strict xfail | reproduced/Documented |
| LEDGER-05b | yes, strict xfail | reproduced/Documented |
| LEDGER-05c | yes, strict xfail | reproduced/Documented |
| LEDGER-09a | **no** | reported only |
| LEDGER-09b | **no** | reported only |
| LEDGER-14a | **no** | reported only |
| LEDGER-14b | **no** | reported only |
| LEDGER-README | no automated test (author status) | reported only |

The five tested defects are the first technical pilot. The untested four must
not be displayed as reproduced or fixed.

---

## 5. Sustained-readability lane

### 5.1 Ownership

| Diagnostic | Primary owner | Inputs | Output |
|---|---|---|---|
| D1 explanation fragmentation | `reader_legibility` per chapter | sentence roles, spans, concept ledger | `EXPLANATION_FRAGMENTATION` |
| D2 essential vs relocatable qualification | `reader_legibility` + independent model | qualification spans, deletion/move counterfactual | `ESSENTIAL_QUALIFICATION`, `RELOCATABLE_QUALIFICATION` |
| D3 prerequisite burden | `editorial` (cross-chapter) | `NN-concepts.txt`, `knowledge_state`, compiler/manuscript_ir spans | `USED_BEFORE_DEFINED`, `SYMBOL_DRIFT`, `REDUNDANT_REEXPLANATION`, `DISTANT_DEPENDENCY` |
| D4 repeated limitation | `reader_legibility` | limitation statements + evidence table | repeated-proposition finding |
| D5 formal before intuition | `reader_legibility` | notation/equation first use + plain-language purpose | `FORMAL_BEFORE_INTUITION` |
| D6 cumulative fatigue | `editorial` (4-chapter windows) | chapter diagnostics + proxies + sequence state | window report, no blended score |
| D7 protected facts | `artifact/self_repair` Gate B | contract obligations + candidate | hard/semantic gate result |

`editing` remains mechanical only. D1–D6 must not be added to
`writer-editing-report-v1` as hidden extra dimensions; use a companion
`writer-sustained-readability-v1` report that references the editing report and
contract.

### 5.2 Evidence labels

Every observation carries exactly one primary label:

- `MEASURED_TEXT` — deterministic proxy/statistic
- `MODEL_JUDGEMENT` — a model's rubric/classification
- `INDEPENDENT_REVIEW` — a different model/reader with disclosed identity
- `HUMAN_READER_OBSERVATION` — consented human outcome
- `CODE_TEST` — executable test result
- `BENCHMARK_RERUN` — new measured evidence

A model that revised a passage cannot also supply its `INDEPENDENT_REVIEW`.
Record `CONFLICTED_MODEL_JUDGEMENT` and keep it visible.

### 5.3 D1–D7 negative controls

These come from the local pilot and must be fixtures:

1. Original Chapter 01 "chain"/"factorisation" should flag explanation
   fragmentation; revised "loop at the heart of generation" should not.
2. Chapter 02 weights-unchanged sentence must be `WEAKENED/UNSAFE` if a rewrite
   turns a modal statement into an observation. This is the UNSAFE finding the
   independent review caught.
3. Chapter 04 causal-mask condition is essential and must never be classified
   relocatable.
4. Chapter 05 opening must not attribute the 27× gap to seriality when the
   missing KV cache dominates.
5. A sentence that scores 92 on a sentence-artifact detector can still have a
   structural D1 finding; the new lane must not override the old score.
6. Chapter 03 "cannot attend to later tokens" is essential negation, not an
   empty caveat.
7. A repeated limitation in body/limits/evidence table may be consolidated only
   if the full statement survives in a traceable location; the evidence table is
   a formal record, not a defect by itself.
8. A four-chapter window with short sentences can still show a concept jump;
   D3/D6 must detect sequence burden, not average it away.

### 5.4 Rubric

Use the eight independent 1–5 dimensions from the pilot (conceptual entry,
sentence cognitive load, explanation continuity, prerequisite burden,
qualification interruption, examples/visuals, four-chapter fatigue, retention)
as **advisory observations**, with rubric version and evidence snippet. Do not
average them into a publication score. The teaching sequence
`question -> intuition -> trace -> mechanism -> formula -> consequence -> limit`
is a revision strategy, not a mandatory template.

---

## 6. Cross-lane link and staleness

Additive link record:

```text
project_id / book_id / chapter_id / source_sha256
technical_defect_ids[]
editorial_finding_ids[]
candidate_id? / contract_id+hash?
test_run_ids[]
source_evidence[]
human_decision_id?
manuscript_commit?
```

Rules:

- Links are relationships, not identities. An editorial decision cannot close a
  technical defect; a code fix cannot close a readability finding.
- A technical fix that changes chapter evidence invalidates any editorial
  approval pinned to the earlier source; re-audit before Apply.
- Mission shows both lanes and never computes a blended scalar.
- Workbench shows the two lanes side by side; Apply remains the sole mutation
  path.

---

## 7. Release gates

| Gate | Criterion | Unknown |
|---|---|---|
| T1 | Defect reproduced | `REPRODUCTION_PENDING` |
| T2 | Fix commit, xfail removed, tests pass | `BLOCKED`/`PARTIAL` |
| T3 | Rerun recorded, original frozen | `CORRECTION_PENDING` |
| T4 | Chapter reconciled to code/evidence | `MANUSCRIPT_PENDING` |
| E1 | D1–D6 findings source-bound; editing separate | `NOT_EVALUATED` |
| E2 | D7/Gates A–E pass; no loss | `INCONCLUSIVE` blocks auto-approval |
| E3 | Author approval with exact hashes | `AWAITING_AUTHOR` |
| E4 | Human reader study observed | `NOT_RUN`, not improvement |
| R1 | Declared technical + editorial policy satisfied | `RELEASE_BLOCKED` |

Human A/B evidence is required for a claim of improved reader comprehension,
not for every routine wording edit. That policy is the author's to declare.

---

## 8. Revised sequence

1. **RA-B0 — Freeze evidence.** Snapshot branch `1403b62`, `main` `132820e`,
   chapters 01–14, defect ledger, tests, proxies, reviews. Record the missing
   07–14 review as a blocker. Do not push the branch.
2. **RA-B1 — Technical projection.** Add the read-only ledger adapter in
   `editorial` (or a thin existing-owner bridge). Validate ledger/hash/test
   status; no code execution from Writer/Mission.
3. **RA-B2 — Technical repairs.** Start with LEDGER-03/04/05a/b/c as separate
   `fix:` commits, strict xfail removal and targeted tests; then add tests for
   09a/b/14a/b before repairing them. Reruns go to new files.
4. **RA-B3 — D1–D7.** Extend `reader_legibility` for D1/D2/D4/D5; extend
   `editorial` for D3/D6; wire D7 to Gate B. Add the eight negative controls.
5. **RA-B4 — Workbench.** Two lanes, source-bound preview, gate display,
   explicit Apply/Undo. Stale technical rerun invalidates editorial approval.
6. **RA-B5 — Mission.** Two-lane review, deep links, separate statuses,
   restart-safe read model. Reuse existing technical/quality surfaces.
7. **RA-B6 — Human pilot.** Blinded A/B on ch01 loop, ch02 switches, ch04
   attention; freeze questions before exposure; `NOT_RUN` until observed.
8. **RA-B7 — Book scale.** 45-chapter diagnostic campaign with 4-chapter
   windows; technical defects remain separate `fix:` work.

The existing 34/44 contracts remain source-current for preservation. Chapter 10
is **stale** after the branch switch (`fd34…` contract vs `9f05…` source) and
must be re-audited/re-contracted or evaluated in a pinned `main` worktree. The
10/34/44 preservation pilot remains a different pilot from the 01–05
fatigue/defect evidence; do not merge their evidence.

---

## 9. ADR impact

- **ADR-002:** human studies stay in `quality`; D1–D6 do **not** create
  `reader_assurance`. Extend `reader_legibility`/`editorial`.
- **ADR-003:** no `ai.assessment`; Mission quality migration stands.
- **ADR-004:** `exp-contract-v1` remains the only contract; D7 uses Gate B.
- **ADR-008 (new):** technical defect ledger is book-repo-owned; Writer
  projects it read-only; no second issue tracker.
- **ADR-009 (new):** sustained readability is a companion report, not an
  Editing dimension and not a universal score.
- **ADR-010 (new):** evidence labels and conflicted-model rule are mandatory;
  T1–T4/E1–E4/R1 gates are separate.

---

## 10. Blockers

1. `editorial/independent-review-ch07-14.md` is referenced but absent.
2. LEDGER-09a/b and 14a/b have no tests; they cannot be called reproduced.
3. The editorial branch is local only; its provenance must be frozen before
   Workbench/Mission consume it.
4. `reader_legibility` has no registered runtime/API surface for Workbench or
   Mission; a thin facade/route is required if cross-system use is approved.
5. `fact_guard.py` and `fatigue_proxies.py` have no unit tests; wrap them as
   fixtures behind existing owners, not new authorities.
6. Full Windows suite and rendered Hugo/EPUB/PDF verification were not run in
   this review.
