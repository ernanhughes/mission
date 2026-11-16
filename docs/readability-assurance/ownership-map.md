# Ownership map — READABILITY-ASSURANCE-01

**Status:** Stage 0 draft, pending owner decisions
**Date:** 2026-11-16
**Rule:** the owner named here is the only writer of that data. Everyone else
reads, projects or references it. A new store is allowed only when no existing
owner can represent the lifecycle.

## 1. Capability ownership

| Capability | Sole owner | Public/consumable surface | Must not duplicate |
|---|---|---|---|
| Canonical manuscript bytes | Book repository (Git) | Files + SHA-256 | No service may rewrite source outside Workbench Apply. |
| Source units, spans, hashes | Writer `manuscript_ir` | Runtime facade | No second parser for passage identity. |
| Mechanical readability | Writer `editing` | `runtime.editing` facade; CLI `writer editing`; store `.writer/editing` | No second sentence/paragraph scorer. |
| Technical intent / chapter obligations | Writer `compiler`, `argument`, `chapter_contract` | Runtime facades | No second semantic ledger. |
| Metadata-blind prose observation | Writer `mri` | Runtime facade | No second observation pass. |
| Earned knowledge state | Writer `knowledge_state` | Runtime facade | Not direct proof of reader learning. |
| Frozen explanation requirements | Writer `artifact/self_repair` (`exp-contract-v1`) | Contracts + gates A–E; Writer web/CLI | No second contract, no second gate set. |
| Candidate repair | Writer `artifact/self_repair` + existing chapter-improvement/quality propose paths | Bounded region -> candidate | No second patch engine. |
| Portable quality findings | Writer `quality` (WRITER-QUALITY-01…07) | CLI `writer quality`; DTOs; **runtime facade not registered** | No second portable-finding contract. |
| Finding evaluation campaigns | Writer `quality/campaign.py` | CLI `writer quality campaign` | Do not clone into reader assurance. |
| Candidate repair campaigns | Writer `artifact/book_campaign` | CLI `writer book-campaign`; `.writer/book-campaigns` | Do not add a fourth scheduler. |
| Advisory multi-dimension AI scoring | `ai.scoring` | `ai.scoring` Python API; `manuscript_cli`, `tech_cli` | Do not create `ai.assessment`. |
| Runtime-participant evaluation fabric | Writer `evaluation_fabric` | CQRS service, evidence packets, council synthesis | Not human-reader evidence. |
| Read-only reader-legibility review | Writer `reader_legibility` CLI/core analyzer | CLI reports; not a runtime domain | Do not present as comprehension proof. |
| Sustained readability D1/D2/D4/D5 | Writer `reader_legibility` (proposed extension) | Per-chapter companion report | Do not add as Editing dimensions or a universal score. |
| Sustained readability D3/D6 | Writer `editorial` (cross-chapter) | `writer-sustained-readability-v1` composition | Do not infer reader learning from sequence proxies. |
| Protected-fact guard D7 | Writer `artifact/self_repair` Gate B | Contract + gate result | No second fact gate; `fact_guard.py` is an adapter/fixture. |
| Technical defect ledger | Inference book repo | `editorial/defect-remediation-ledger.md`, tests, frozen results | Writer/Mission never edit it. |
| Technical-defect projection | Writer `editorial` (proposed read-only bridge) | Categorical status + test/rerun refs | No second issue tracker or defect DB. |
| Book-level editorial diagnosis | Writer `editorial` | `runtime.editorial` | Read-only, diagnose-only. |
| Author editorial decision | Workbench `EditorialDecisions` | Append-only decision log; JSONL/file store | Mission never writes it. |
| Candidate Apply / Undo | Workbench `chapter_apply` + proposal routes | `/proposals/{pid}/accept`, `/undo`; journal; Git | Sole mutation path. |
| Human reader study | Writer `quality.reader_study` (accepted owner; not implemented) | Study IDs, consent-bound observations, aggregates | No new `reader_assurance` domain; no AI testimony as human evidence. |
| Mission control-plane display | Mission `writer` read model | `/api/writer/*`, `/writer` page | No rescoring, no manuscript parsing. |
| Mission quality observations | Mission `quality` | `/api/quality/*`; QualityEvaluation/Campaign/Review | Competing lane today; disposition required. |
| Mission technical claims | Mission `technical` | `/api/technical/*`; TechnicalClaim/Evidence/Verification | Manuscript-claim verification, **not** code-defect storage. |
| Cross-book priority / queue | Mission `writer.queue` | `/writer` "Cross-book review queue" | Presentation only, not a score. |

## 2. Store map

| Store | Path | Owner | Notes |
|---|---|---|---|
| Editing reports | `C:\Projects\writer\.writer\editing` | Writer Editing | Default is CWD-relative; `WRITER_EDITING_STORE` overrides. Not per-book. |
| Self-repair contracts/runs | `C:\books\<book>\.writer\self-repair\` | Writer self_repair | Inference has 13 contracts, 1 run; Chapter 10 contract is stale on the editorial branch. |
| Book campaigns | `C:\books\<book>\.writer\book-campaigns\` | Writer book_campaign | 11 Inference campaigns. |
| Technical defect ledger | `C:\books\inference\editorial\defect-remediation-ledger.md` + `tests/test_known_defects.py` + `research/chNN/results.json` | Inference book repo | Canonical; Writer projects read-only. |
| Technical-defect projection | Writer `editorial` store (proposed) | Writer editorial | Categorical status and refs; no second defect DB. |
| Sustained-readability report | Writer `reader_legibility` store (proposed) | Writer reader_legibility | Companion report; no Editing schema mutation. |
| Human reader study | Writer `quality` store (proposed) | Writer quality | Consent-bound; not implemented. |
| Quality campaign state | Writer execution provenance | Writer quality | No separate DB; per-chapter step records. |
| Mission quality | Mission DB (`quality_evaluations`, `quality_campaigns`, `quality_reviews`) | Mission | Append-only evaluation history. |
| Mission integration records | Mission DB (`IntegrationRecord`) | Mission | Writer Editing snapshots. |
| Workbench decisions | Workbench `.workbench` / configured path | Workbench | Author decisions, candidate verdicts. |
| Workbench apply journal | Workbench `.workbench` | Workbench | Apply receipts and Undo. |
| AI scoring bundles | Caller-selected; `persist_bundle` | `ai.scoring` consumer | No canonical Writer manuscript store. |

## 3. Overlap that must be resolved

1. **Readability/quality semantics.** Writer Editing (mechanical), Writer
   `quality` (portable findings), `ai.scoring.manuscript` (LLM 1–5), and
   `reader_legibility` (CLI review) all comment on prose. They are not
   interchangeable; the UI must name which one produced a claim.
2. **Campaigns.** Three durable mechanisms exist. The distinction by work unit
   is proposed, not implemented:
   - `book_campaign` -> contract-bound candidate repair.
   - `quality.campaign` -> portable finding evaluation.
   - Mission `QualityCampaign` -> control-plane record; must not schedule
     independently.
3. **Candidate verification.** `self_repair` gates A–E and
   `quality.verify_candidate` (5 per-check statuses) overlap. They may serve
   different candidate types; this is not documented. Decide before adding
   another verifier.
4. **Human evidence.** `reader` is a TTS/playback queue; `readthrough` is a
   human-led manuscript workflow; `evaluation_fabric` participants are runtime
   evaluators; `mediated_read` is AI-conditioned representation. None is a
   controlled human comprehension study.
5. **Review surfaces.** Mission `/writer` (Editing + decision queue),
   Mission ProjectPage quality tabs, Workbench editing/self-repair/
   chapter-improvement. A new Reader Assurance panel must attach to one of
   these, not become a fifth surface.

## 4. Proposed boundary (pending approval)

- `editing` -> mechanical signals only.
- `quality` -> portable findings and finding campaigns; register a facade if
  cross-system consumption needs one.
- `self_repair` -> contracts + A–E for candidate repair; remains the only
  contract.
- `evaluation_fabric` -> runtime evaluator orchestration; may host paired model
  probes, not human studies.
- `reader_study` (if approved) -> human consent, assignment, frozen questions,
  outcomes, aggregation and calibration. It references contracts and questions;
  it does not own them.
- Workbench -> author decisions and sole Apply/Undo.
- Mission -> display and orchestration through approved actions.

## 5. Hand-offs

| Producer | Consumer | Artifact |
|---|---|---|
| Writer Editing | Mission, Workbench | `writer-editing-report-v1` + finding ids + locators |
| Writer self_repair | Workbench, Mission | `exp-contract-v1` + gate results |
| Writer quality | Mission, Workbench | portable findings + review outcomes |
| Writer book_campaign | Mission, Workbench | campaign/run/chapter status |
| Workbench | Mission | append-only author decisions + apply receipts |
| `ai.scoring` | Mission (today) | `ManuscriptEvaluation` + execution record |
| Reader study (future) | Workbench, Mission | study id, status, aggregate outcomes, limitations |

No hand-off may copy a score into another owner's store and call it the same
measure.
