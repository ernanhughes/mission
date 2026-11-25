# PUBLICATION Architecture

PUB-00 grounding. Every claim below was checked against live source on 2026-11-24;
file paths are given so later stages can re-verify. Assumed-stable IDs: PUB-00…PUB-11
(ROADMAP.md).

## 1. Layering and dependency direction

```text
AI (ai.scoring advisory rubric, providers via Worker runtime.models)
  → Writer (detection, diagnosis, evidence, candidates, verification, provenance)
    → Workbench/Worker (author decisions, governed Apply/Undo, job execution)
      → Manuscript transformation (book repo bytes change only here)
        → Mission Control (read model, orchestration surface, release gates)
          → Publication (Hugo/BookKit/EPUB/PDF pipelines, deployment evidence)
```

Dependency rules (inherited from `docs/readability-assurance/ownership-map.md` and
its ADRs, which this programme adopts rather than relitigates):

1. Canonical manuscript bytes live in the book Git repo. Nothing rewrites source
   outside an explicit governed Apply path.
2. Writer owns all manuscript analysis (parsing, scoring, findings, provenance).
   Mission and Workbench consume Writer evidence **by reference** (report id +
   source fingerprint); they never re-parse, re-score, or copy a score into
   another store under the same name.
3. Workbench `chapter_apply` (journaled atomic one-file apply, Git commit, Undo)
   is currently the **sole manuscript mutation path** (Workbench
   `src/workbench/chapter_apply.py`, routes `/proposals/{pid}/accept`, `/undo`).
4. Mission is display plus orchestration through approved actions only
   (ADR-007 proposed; no arbitrary shell).
5. No composite book score anywhere. No green state from a model's self-score
   (ADR-010 proposed: every observation carries one primary evidence label;
   revising-model output is `CONFLICTED_MODEL_JUDGEMENT`).

## 2. Ownership

| Concern | Owner | Consumed via |
|---|---|---|
| Mechanical readability | Writer `editing` | `runtime.editing`, CLI `writer editing`, `writer-editing-report-v1` |
| Structural legibility (placeholders, workflow leakage, reproduction gaps, repeated qualification, density) | Writer `reader_legibility` (writer-core analyzer + CLI; not a runtime domain) + PUB-02 `publication_cruft` (CR01–CR12 classifier + `cruft` CLI, deterministic) | CLI `reader-legibility review/reports/show`, `cruft review` |
| Portable findings, campaigns, (future) human studies | Writer `quality` (WRITER-QUALITY-01…07; **runtime facade not registered**) | CLI `writer quality`; public surface is a PUB-01/02 prerequisite |
| Frozen explanation contracts, gates A–E | Writer `artifact/self_repair` (internal package, not a runtime domain) | Writer web/CLI, `exp-contract-v1` |
| Contract-bound repair campaigns | Writer `artifact/book_campaign` (internal package) | CLI `writer book-campaign`, `.writer/book-campaigns` |
| Book-level diagnosis, specialist orchestration, capability gaps | Writer `editorial` (`runtime.editorial`, diagnose-only, read-only) | Facade `diagnose_book/diagnose_chapter` |
| Source spans, semantic roles, downstream verification | Writer `manuscript_ir` | Facade `compile_chapter(_file)`, `verify_candidate_downstream`, snapshots |
| Concept integrity, argument/evidence connectivity, transitions | Writer `argument` | Chapter/cross-chapter diagnostics, drift reports |
| Claim↔evidence verification | Writer `evidence` | `verify_claim(_text)`, `verify_chapter`, record diffing |
| Text segmentation, repair windows | Writer `text_structure` | `split_text/split_chapter`, `build_repair_window` |
| Prose linting | Writer `vale` (external Vale binary) + `artifact` detectors | `check_project`, `analyze_text/analyze_book_tics` |
| Author-specific judgement, calibration evidence | Writer `taste`, `sentence_evolution`, `author_evidence`, `sentence_arena`, `decision_lineage`, `readthrough`, `statistics` | Advisory; read-only; see CAPABILITIES.md |
| Candidate generation/comparison/selection, QC gate | Writer `review` (COTMOE), `sentence_repair`/`improve`, `refine`, `qc`, `revision` paths (`revise`, `sentence_lab`, `sentence_studio`, `writethrough`) | Facades; QC is the post-apply gate |
| Staged manuscript mutations | Writer `vfs` (git backend only) | `create_branch/snapshot/change_set`, `apply_change_set`, `diff` |
| Cross-runtime participation planning/binding | Writer `workflow_graph`, `execution` (neutral provenance) | Facades |
| Author decisions, Apply/Undo, proposals | Workbench | Decision log, `/proposals/{pid}/accept`, `/undo` |
| Job execution, model routing | Worker (`POST /v1/work`, replaceable executors; owns no memory/verification/provenance) + Writer `runtime.models` | Worker API; Workbench/Writer adapters |
| Publication read model, orchestration, release assurance | Mission (`mission_control/publication/`, `/api/publication`, `BookPublishingPage`, `/writer` queue) | REST; Writer evidence by reference |
| Manuscript truth, results, ledger, preregistration, book tests | Book repo (Jev: `content/books/jev`, `results/`, `evidence/ledger.md`, `planning/`, `scripts/apply_edits.py`) | Files + SHA-256; Mission fingerprinting |
| Rendering/publication artifacts | Hugo + layouts + EPUB/PDF tooling (Jev: `hugo.toml`, `layouts/`, `publication/`) | Build outputs + deployment evidence |
| Production-path editorial automation | Writer `publication_automation` (writer-core analysis + `transform automate` CLI; injected dispatch via D-PUB-08 seam, no writer_runtime import) | `transform automate`, record `dispatch_ledger` (`writer.automation.ledger.v1`) |
| Package-scale candidate proposals | Workbench `publication_proposals` (Proposal data + span-bound stale/source checks; accept/undo never invoked) | `proposal.json` records, `check_proposal_fresh` |

Unresolved ownership (explicitly not decided in PUB-00):

- **U1. Editing plan/apply home.** `editing` reserves `plan`/`apply` (unimplemented);
  `vfs.apply_change_set` and Workbench `chapter_apply` both mutate. ADR-005
  (proposed) stages large regions without weakening Apply. PUB-06 must pick one
  mutation substrate and one staged-change-set design; until then no bulk apply.
- **U2. `runtime.quality` registration.** CLI-only blocks Mission/Workbench
  in-process consumption (STAGE0 blocker, still open). PUB-01 decided
  CLI-only-with-unblock-plan (D-PUB-07): the working seam is
  `writer quality evaluate` via `MISSION_CONTROL_WRITER_QUALITY_RUNNER`;
  facade design → PUB-02, surface + bridge → PUB-07, migration → PUB-09.
- **U3. Campaign consolidation.** `book_campaign` vs `quality/campaign.py` vs
  Mission `QualityCampaign` record — one scheduler per work unit (decision D3 open).
- **U4. Mission quality-lane migration.** `manuscript-prose-v1` → Writer quality
  read model (ADR-003 accepted, implementation open).
- **U5. Worker/Work/Next roles.** Worker executes; Work is a commercial-opportunity
  engine (not manuscript); Next has no manuscript role observed. No new
  responsibilities assigned.

## 3. Cross-repo contracts (existing — extend, do not fork)

- `writer-editing-report-v1` (versioned, fingerprinted, stale-checked) → Mission,
  Workbench.
- `exp-contract-v1` + gates A–E → Workbench, Mission.
- Portable `portable-v1` findings → Mission, Workbench (surface pending U2).
- `Current Text / Recommended Change` block format (`C:\books\jev\scripts\apply_edits.py`,
  exact + block-safe replacement) → align with VFS change-sets and Workbench
  proposals in PUB-06 rather than inventing a third edit grammar.
- Manuscript identity: Mission `project_id` canonical; Writer registry key validated;
  assessments bind `(project_id, manuscript_fingerprint)` (MC-PUBLISH-02).
- Freshness: any assessment binds an exact revision; changed source ⇒ STALE;
  `unknown` freshness is reported, never treated as success.

## 4. What PUBLICATION must not build

New manuscript parser, new sentence/paragraph scorer, new quality composite, new
`reader_assurance`-style domain, new campaign scheduler, new contract schema, new
model gateway, new AI assessment primitive, second defect tracker, or a Mission
rescoring lane. Each was proposed before and rejected with recorded rationale
(DECISIONS.md). PUB-01's first job is reconciling the stale capability catalog
(see CAPABILITIES.md §8) so later stages stop designing against it.
