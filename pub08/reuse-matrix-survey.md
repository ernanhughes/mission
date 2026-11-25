# PUB-08 reuse-matrix survey — first pass (subagent report, unreviewed)

**Run identity:** model `Muse Spark` (Meta). **Spend: $0. Zero pipeline dispatches** — no Worker/Workbench/model calls made; all evidence is local file reads + repo-local search only. No writes, no commits, no Jev/PUB-06/PUB-07 modifications. `program.json` / `transformation-record.json` keys were read as interface-shape reference only, not re-verified.

**Starting point honored:** `C:\Projects\writer\packages\writer-runtime\writer_runtime\capabilities\catalog.py` is the backbone. Its classification rule matters for the whole matrix: only the 15 pilot runtimes have real capability adapters (`capabilities/adapters/`); every other domain may only claim non-adapter capabilities. So "callable capability" below means *pilot-adapter-backed*; everything else is at best an *internal library with a facade but no callable-capability claim*.

Status classes used: **CALLABLE** (adapter-backed) / **LIB** (existing internal library, facade exists) / **EXPERIMENTAL** / **DOC-ONLY** / **MISSING**.

## (a) Knowledge representation

| Requirement | Status | Path / evidence |
|---|---|---|
| Manuscript IR | LIB | `writer/.../domains/manuscript_ir/` (`facade.py, compiler.py, semantics.py, incremental.py, calibration.py, candidate_impact.py, downstream_verification.py`); tests `writer/tests/runtime/manuscript_ir/`; docs `writer/docs/runtime/manuscript_ir/` (`STATE.md` etc.). Catalog claims RETRIEVE/REPRESENT/STRUCTURE only; VERIFY is role-only (no adapter). |
| Compiler | LIB | `writer/.../domains/compiler/` (`engine.py` ~137KB, `facade.py, compiled_document.py, dto.py`, `services/`, `persistence/`); tests `tests/runtime/compiler/`; docs `docs/runtime/compiler/`. |
| Argument | LIB (tests not found) | `writer/.../domains/argument/` (`facade.py, engine.py, dto.py, extractor.py, entailment.py, drift.py, graph.py, metadata_parser.py, observation_adapter.py`); docs `docs/runtime/argument/`. No `tests/runtime/argument/` dir found — may live elsewhere; **not confirmed absent**. |
| Knowledge State | LIB | `writer/.../domains/knowledge_state/` (`facade.py`); tests + docs present. Catalog status `partial`. |
| Knowledge Graph | LIB | `writer/.../domains/knowledge_graph/` (`facade.py`); tests + docs present. VERIFY deliberately not claimed. |
| Concept registries | CALLABLE + LIB | Lexicon pilot: `writer/.../domains/lexicon/` (RETRIEVE/REPRESENT via adapter). Workbench companion: `workbench/src/workbench/concepts.py` (model-free `NN-concepts.txt` inventory/validation — reader-facing, not a registry service). |
| Chapter metadata | CALLABLE | Metadata pilot: `writer/.../domains/metadata/`; schema `writer/schemas/technical-chapter-metadata.schema.json` (per PROJECT-INTELLIGENCE `chapter-metadata-validation` entry). DEFINE_OBJECTIVE/RETRIEVE/STRUCTURE via adapter. |
| MRI | LIB (tests not found) | `writer/.../domains/mri/` (`facade.py`); docs `docs/runtime/mri/` (`ARCHITECTURE.md, BOOK_REPAIR.md, …`). Catalog `operational`. No `tests/runtime/mri/` dir found — **not confirmed absent**. |
| Author Evidence | LIB | `writer/.../domains/author_evidence/` (`facade.py`); tests + docs present. No capabilities adapter (RETRIEVE/REPRESENT/STRUCTURE claimed). |
| Decision Lineage | LIB | `writer/.../domains/decision_lineage/` (`facade.py`); tests + docs present; known recorded replay defect (`docs/runtime/decision_lineage/...`). |

## (b) Evidence + semantic preservation

| Requirement | Status | Path / evidence |
|---|---|---|
| Claim extraction | LIB | `writer/.../domains/evidence/claim_extractor.py, span_extractor.py, service.py`; also `domains/evidence_architecture/extraction.py, claims.py` (no facade, campaign-oriented). |
| Claim verification | LIB (×2 repos) | Writer: `domains/evidence/verifier.py, warrant.py, refutation.py, synthesis.py` (+ `tests/runtime/evidence/`). Mission: `mission/backend/mission_control/technical/service.py` (TechnicalClaim/TechnicalEvidence/requirement-link records, read-only vs manuscripts). |
| Evidence reconciliation | LIB | Writer: `domains/analysis_state/service.py + facade.py` (`reconcile_diagnosis(es)`, `benchmark_reconciliations`). MC-side equivalent not checked — **not found, not confirmed absent**. |
| QC / validation | CALLABLE (qc) + LIB (validation) | `domains/qc/` (pilot: VERIFY+EVALUATE adapters, before/after delta report) and `domains/validation/` (real pipeline, no adapter) + tests for both. |
| Semantic-loss detection (Praxis) | LIB in Writer; DOC-ONLY in Praxis | Real implementation is Writer-owned: `domains/artifact/artifact_engine/revision/semantic_loss.py::check_semantic_loss` + `quantity_units.py`, tests `tests/runtime/artifact/test_semantic_loss*.py`. In Praxis: no manuscript semantic implementation found; only `praxis/capability_adapter.py::_WORKFLOW_TEMPLATES` containing `"writer_quantity_units_v1"` (read-only MC hook) + `technical_verification.py` method taxonomy where `semantic` = exploratory model judgment, explicitly *not* independent. Praxis README recounts a quantity-unit defect fixed in an isolated Writer worktree — i.e. Praxis borrows Writer semantics. |
| Quantity/unit normalization | LIB | `.../artifact/.../revision/quantity_units.py::normalize_quantity_unit, quantity_unit_token`; test `test_semantic_loss_quantity_units.py`. |
| Defect attribution (state contracts) | MISSING (equivalents partial) | No named defect-attribution contract found anywhere (grep over `domains/qc` for defect/attribution/blame: zero hits). Closest existing equivalents: artifact findings preserve `source_domain` provenance; `decision_lineage` outcome facts; `editorial_evidence` severity bands (with recorded defect `repo-severity-band-001`). None is a defect-attribution contract. |

## (c) Reader + comparative evaluation

| Requirement | Status | Path / evidence |
|---|---|---|
| Mediated Read | LIB | `domains/mediated_read/` (`facade.py`); 4 test files (`test_mediated_read/information_survival/reader_divergence/human_validation.py`); catalog warns outcomes are model-mediated probes, **human-reader evidence (`quality.reader_study`) does not exist**. |
| Evaluation Fabric | LIB | `writer_runtime/services/evaluation_fabric/` (coordinator, planner, worker, projector, evidence_packet, council, readthrough_materializer…) + `domains/eval/services/evaluation_fabric_bridge.py`; 14 test files `tests/runtime/evaluation_fabric/`; `docs/architecture/evaluation-fabric.md`. |
| Reader Legibility | LIB | `writer-core/writer_core/analysis/reader_legibility.py` + CLI `writer-cli/.../commands/reader_legibility.py` + `tests/core/test_reader_legibility.py` (PROJECT-INTELLIGENCE: implemented/tested-not-demonstrated). |
| Taste | LIB | `domains/taste/` (facade+tests+docs); advisory/read-only by design. |
| Review | CALLABLE | `domains/review/` pilot (COTMOE pipeline; GENERATE/COMPARE/DECIDE via adapter). |
| Editorial | LIB | `domains/editorial/` (diagnose-only orchestrator) + `domains/editor/` (approvals) + `editorial_evidence/` + `editorial_intelligence/` + `editorial_memory/`. |
| Quality / Scoring | CALLABLE + LIBs | Scoring pilot (`domains/scoring/`, EVALUATE/COMPARE adapters). Quality LIB: `domains/quality/` (**no facade**; `__init__.py` mirrors frozen Jev contracts `C:\books\jev\examples\book-quality-lab\contracts\portable-v1` as DTOs; `run_typed_task` seam explicitly "later increment"). Also `ai/src/ai/scoring/` (`manuscript.py, technical.py, evaluation.py…`) and MC `quality/service.py`, `publication/calibration.py`. |
| Sentence Arena / Evolution | LIB + LIB | `domains/sentence_arena/` and `domains/sentence_evolution/` (facades+tests+docs; no GENERATE/EVALUATE adapters claimed). |
| Readthrough | LIB | `domains/readthrough/` (facade+tests+docs); human-led; CAPTURE_FEEDBACK explicitly not claimed. |
| Blind assessment | LIB (nearest) | `domains/revise/` (`construct_blind_trials`, `ReviseBlindTrialDTO`, `DEFAULT_REVIEW_MODE="blind_ab"`, ~28 test files). Paragraph-revision-scoped, V1 never mutates source — reusable blind-trial mechanism, not a general blind-assessment capability. |

## (d) Production execution

| Requirement | Status | Path / evidence |
|---|---|---|
| Workbench | LIB | `workbench/src/workbench/` (`service.py` ~188KB, `app.py, publication.py` (read-only preflight), `quality_bridge.py` (read-only portable-finding→row), `reader.py` (display blocks), `runrecords.py, candidates.py, strengthen.py`, `workflows/`, `knowledge/`, `chapter_improve/`, `capabilities/`). |
| Worker typed-task interfaces | CALLABLE (types) / DOC-ONLY (seam) | Typed + enforced: `worker/src/schema/request.ts` (`worker.work-request.v1`, `normalizeRequest`), `schema/result.ts`, `strategies/catalog.ts` (versioned `direct/structured/corrective/adaptive.v1`), `work/translator.ts` (`translateWorkRequest` → opencode-work declaration), `packages/opencode-work/src/` (`engine.ts, acceptance.ts, capabilities.ts, work.ts…`). But the Writer→Worker **`run_typed_task` seam is DOC-ONLY**: `domains/quality/__init__.py` cites it as "(later increment)". |
| Workflow orchestration | LIBs (plural, overlapping) | Writer `workflow_graph/ + workflow/ + cake/ + improvement/ + moe/` (ORCHESTRATE mostly without adapters); Workbench ALIVE recipes (`workflows/definitions.py, contracts.py, runner.py, runtime.py, worker.py` — bounded, deterministic, single `technical-source-analysis` recipe); MC `workflows/service.py` (~98KB); Worker `strategies/runtime.ts`. No single canonical orchestrator — composition question is real but so is redundancy. |
| PUB-07 automation seam | LIB (shapes recorded, not re-verified) | `ch02-rerun/program.json` keys: `program_schema, detector, package_id, editorial_loop, review_rounds, outcome, spend_policy, ledger, fix_batch_annotations`. `transformation-record.json` keys: `record_schema, detector, profile, plan_id, inputs, config, dispatch_ledger, boundary, work_packages, package_hashes, packages_digest, preservation, model_invocations, revisions, dispositions, assets, reviews, verification, chain, unresolved_obligations, acceptance, recorded_at`. Owning implementation presumably MC `publication/publishing.py + service.py + pipeline.py` (read-only projection w/ digest contracts) — `build_ch02_records.py` deliberately not opened. |

## Frozen paths for the later comparative experiment (recorded, untouched)

- Jev Ch1: `C:\books\jev\content\books\jev\01-chapter.md`; Ch2: `C:\books\jev\content\books\jev\02-chapter.md`. Jev HEAD `c7aaad70…`.
- PUB-06 Ch1 accepted candidate: `C:\Projects\mission\pub06\ch01\01-chapter-candidate.md` (+ `before-after.md, transformation-record.json, verification-report.json, adjudications-ch1.json, packages-ch1.json, plan-ch1.json`).
- PUB-07 Ch2 accepted demonstration candidate: `C:\Projects\mission\pub07\ch02-rerun\candidate.md` (D-PUB-85; run-1 in `pub07/ch02/` + archive `pub07/ch02-superseded-run1/` preserved as history).

## 5 largest genuine gaps (composition-first view)

1. **Calibrated human-comprehension evidence** — explicitly missing by the repos' own admission (`mediated_read` catalog: `quality.reader_study` "does not exist"). Everything reader-side is model-mediated proxy. Any PUB-08 claim about actual reader comprehension needs new evidence collection, not reuse.
2. **Defect-attribution state contract** — no equivalent found in any repo; only adjacent provenance/lineage records. (D-PUB-84 mandates it.)
3. **Composed semantic-preservation contract** — `check_semantic_loss` (Writer) + `TechnicalClaim` records (MC) + digest-bound pipeline projection (MC) + portable-v1 DTOs (Writer quality) exist in three repos with no composed interface; the `run_typed_task` seam that would join them is a documented future.
4. **Blind assessment as a callable capability** — `revise` blind trials and `readthrough`/`mediated_read` judgments exist but none exposes CAPTURE_FEEDBACK/EVALUATE through an adapter; cross-chapter blind comparison for PUB-08 would need adapter work, not new science.
5. **Praxis-owned manuscript semantics** — Praxis has taxonomy + read-only hooks only. The composition-first reading is that PUB-08 should *not* build this in Praxis at all and should cite Writer ownership; a "parallel semantic-verification architecture" in Praxis would violate the author's constraint.

## Coordinator resolutions (2026-11-25, post-survey)

- **Accepted-candidate ambiguity resolved:** `pub07/ch02-rerun/candidate.md` is the D-PUB-85 demonstration candidate; `pub07/ch02/candidate.md` is run-1 history (amended in the frozen-paths table above; the survey's "do not assume" flag is closed).
- **Uncertainties carried forward:** `tests/runtime/{mri,argument}` presence unconfirmed; MC-side evidence-reconciliation coverage unchecked. Both are follow-ups for the design phase, not blockers.
- **Design implication:** gaps 2–4 are composition/adapter work (no new science); gap 1 (human comprehension) and gap 5 (Praxis boundary) are decisions, not builds. The costed experimental design must fit paid inference (Ch1 Arms A/B generation + model-reader probes) inside the $1.00 PUB-08 cap or declare what does not fit.

## Provenance

First-pass survey by background subagent (model Muse Spark / Meta), $0, zero pipeline dispatches, read-only. Recorded verbatim except the frozen-paths amendment and this provenance/resolutions section (coordinator). Not independently re-verified; the design phase must confirm load-bearing paths before building on them.
