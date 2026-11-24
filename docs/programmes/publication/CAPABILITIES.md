# PUBLICATION Capability Inventory

Verified 2026-11-24 against live source. Notation: ✅ verified working by this
stage (import, CLI/doc, or live run); 📄 verified by reading source/docs/tests
(not executed here); ⚠️ verified with limitations; ❌ confirmed missing.
"Callable" means an entry point observed in source, not a catalog role.
Catalog references are to
`C:\Projects\writer\packages\writer-runtime\writer_runtime\capabilities\catalog.py`
(165 runtimes, `build_catalog()` import-verified this stage).

**Material catalog finding:** the catalog does NOT contain `editing`, `quality`,
`reader_legibility`, `self_repair`, `book_campaign`, `evaluation_fabric`,
`refinement` or `mediated_read`, although `editing` is bootstrap-registered
(`bootstrap.py`) and the others ship tested code. The catalog's "exactly one
manifest per registered runtime" invariant is therefore already broken. Every
later stage must verify against source + entry points, never the catalog alone.
Catalog reconciliation is a PUB-01 prerequisite (§8).

**PUB-01 outcome (2026-11-24):** `editing` and `mediated_read` manifests added
(`catalog.py`, catalog 165→167); both are registered runtimes with facades,
CLI and tests. Remaining gap is documented-open, not green: 1 missing manifest
(`metadata_generation`, unrelated owner), 46 orphaned manifests (code present,
never registered — recorded separately, none PUBLICATION-blocking),
1 adapter problem (`analysis_state` claims EVALUATE without adapter). See §8.

## 1. Reusable immediately (verified)

| Capability | Responsibility | Callable entry points | Determinism / mutation | Evidence / provenance | Limits |
|---|---|---|---|---|---|
| Writer `editing` ✅ | Mechanical readability diagnosis over registered manuscripts | `runtime.editing`: `audit_book`, `audit_all`, `summary`, `list_reports`, `get_report`, `report_status`, `compare`; CLI `writer editing audit\|summary\|reports\|show\|status\|compare`; web `POST /api/editing/audit` | Deterministic, no model; **read-only** (`plan`/`apply` reserved, unimplemented) | `writer-editing-report-v1`, finding ids `edfinding:…`, source SHA-256, stale detection, canonical fingerprint | Readability only (6 subdims: paragraph/sentence load, fragmentation, rhythm, lexical accessibility, section structure); thresholds uncalibrated across genres; no composite |
| Writer `reader_legibility` ✅ | Structural legibility: evidence intrusion, reproduction gaps, workflow leakage, technical density, repeated qualifications, placeholders | `ReaderLegibilityAnalyzer.analyze(...)` (`writer_core/analysis/reader_legibility.py`); CLI `reader-legibility review/reports/show` | Deterministic structural; optional `--include-llm`; no manuscript writes | Finding id, severity, confidence, evidence role, quote + locations, source fingerprint | CLI/core analyzer, not a runtime domain; no registered facade; D1/D2/D4 detection pending (ADR-009); extended by `publication_cruft` (PUB-02, next row) |
| Writer `publication_cruft` ✅ (PUB-02) | CR01–CR12 cruft classification extending legibility/artifact/evidence/argument | `PublicationCruftClassifier.classify(...)` (`writer-core/analysis/publication_cruft.py`); CLI `cruft review` | Deterministic only (zero model dispatches); typed-task payloads prepared for CR07/08/11, never dispatched; read-only | Finding id (`cruft:…`), span, evidence role + MEASURED_TEXT label, severity/confidence (uncalibrated), provenance, preserved + needs-evidence lists | Analyzer + CLI, not a runtime domain (no manifest, per D-PUB-09/10); profile `cruft-v0.1` uncalibrated; CR11 same-block-mixed-text limit documented |
| Writer `manuscript_ir` 📄 | Dense provenance-preserving IR: sentences, paragraphs, semantic roles, procedure contracts, spans, snapshots, downstream verification | Facade: `compile_chapter`, `compile_chapter_file`, `compile_dense`, `analyze_semantics`, `classify_sentence`, `analyze/verify_candidate_downstream(invalidation)`, `persist_snapshot`, `latest_snapshot`, calibration + correction APIs | Deterministic; **no mutation** (VERIFY is a role only, no adapter) | Evidence + provenance; evaluation dims incl. role/contract/coverage/verification status | Semantic-role taxonomy bounded; sentence split/merge not implemented |
| Writer `text_structure` 📄 | Canonical segmentation + narrative context; shared source of truth | Facade: `split_text`, `split_chapter`, `build_narrative_context`, `build_repair_window` | Deterministic; read-only | Source-unit identity for all downstream locators | Must be the only passage-identity parser (ownership map) |
| Writer `argument` 📄 | Technical-chapter contracts, concept lifecycle, cross-chapter diagnostics | `create_argument_domain`; `run_chapter_diagnostics`, `run_cross_chapter_diagnostics`, `analyze_transition_chains`, drift/defect reports | Deterministic extraction (lexical); no model-backed semantics yet; diagnostics only | Contract coverage, concept integrity, argument support, evidence connectivity, transitions | Drift detection is a lifecycle placeholder (`drift='none'`) |
| Writer `evidence` 📄 | Warranted-search evidence engine over file/project sources | Facade: `extract_claims`, `verify_claim`, `verify_claim_text`, `verify_chapter`, `measure_narrative_energy`, `lint_narrative_support`, record diffing | Async, file/project-oriented; verification pipeline real but **no adapter** | Evidence records | Adapter gap blocks capability-plane use; narrative-energy APIs are fiction-oriented |
| Writer `artifact` 📄 | Deterministic AI-smell/cruft-structural detector, before/after compare | Facade: `analyze_text/analyze_file`, `analyze_book_tics`, `detect_book_findings`, `calculate_structural_metrics`, `rank_damage`, `build_repair_plan`, `repair_file/repair_path`, batch export | Deterministic; repair paths exist | `evidence_available`; pilot adapter (OBSERVE/EVALUATE/COMPARE/VERIFY) | Heuristic detectors; repair needs QC gating |
| Writer `vale` 📄 | Managed Vale prose-lint integration + findings normalization | Facade: `init/build/check_project`, `status` | Deterministic; needs installed Vale binary; writes managed config + reports, never manuscript | Alert counts, readiness, rule set version | Rule-set/version drift; no EVALUATE/VERIFY adapter |
| Writer `findings` 📄 | Chapter-level findings index preserving `source_domain` provenance | Facade: `get_sentence_findings`, `build/load_chapter_findings`, `build_project_report` | Deterministic aggregation | Evidence; provenance-preserving | Aggregator only; owns no detection |
| Writer `editorial` 📄 | Persistent book-level diagnosis loop: specialist evidence, local-first AI reasoning, contribution assessment, capability-gap reporting | Facade: `diagnose_book`, `diagnose_chapter`, `synthesize_book_evidence`, `get_run/get_episode`, `export_experience` | Deterministic core; optional local (Ollama) synthesis; **diagnose-only, read-only** | Evidence; MRI-compatible state | V1.2 only; no native MRI/metadata/QC/artifact semantics; utility unmeasured until grounded outcomes |
| Writer `mri` 📄 | Metadata-blind diagnostic scan + quoted-evidence verification + alignment | RETRIEVE/REPRESENT/STRUCTURE facade claims only (no adapter) | Deterministic; Chapter Lens only; never edits or adjudicates | Observed purpose, alignment, beat coverage, evidence verification | Book/Scene/Sentence lenses unimplemented |
| Writer `taste` 📄 | Author-specific judgement from decision/evolution evidence; benchmarked refinements | Facade: `collect_evidence`, `build/get/list_profiles`, `inspect_chapter`, `report_chapter`, `run_refinements`, `benchmark_*`, counterexamples | Mixed deterministic + optional LLM; **advisory, read-only** | Calibration reports (SUPPORTED/MIXED/CONTRADICTORY/INSUFFICIENT_DATA) | No hierarchy resolution, no auto-promotion, no adapter |
| Writer `vfs` 📄 | Git-backed staged manuscript changes | Facade: `create_workspace/branch/snapshot/change_set`, `diff`, `apply_change_set`, `compare_change_sets`, `checkout_branch`, `discard_branch` | Git backend only; **mutates via apply** | Snapshots, patches, change-sets | Relationship to Workbench Apply unresolved (U1) |
| Writer `review` / `improve` / `refine` / `sentence_repair` / `qc` 📄 | Candidate generation, COTMOE judging, chapter strengthening, paragraph/chapter refinement, before/after QC gate | `review_chapter`, `cotmoe_improve_chapter`, `improve_chapter`, `refine survey/inspect/plan/generate/audit/verify`, `evaluate_document/candidate_qc`, `improvement.improve_chapter/improve_book/strengthen_chapter` (+ campaign/dossier/approval APIs) | Mixed deterministic + model; `improvement` orchestrates only; QC gates apply | Meaning/voice/purpose/compression/artifact dims; decision lineage; training evidence | Generation/eval live behind facades but most lack capability adapters; `refine` claims no mutation; campaign/approval surface is broad — use smallest path |
| Writer `readthrough` / `editor` 📄 | Human-led readthrough (scores, annotations, stale detection, repair prompts) + manuscript approval workflow | `get_book_map`, `save_assessment`, `add_annotation`, `request/apply/undo_*_repair`, `finish_chapter`; editor `approve_section`, annotations, `approval_report` | Deterministic workflow; generates prompts not candidates; **never mutates** | Human verdicts; staleness by source hash | No GENERATE/APPLY adapters; human-effort intensive by design |
| Writer `sentence_evolution` / `author_evidence` / `decision_lineage` / `execution` / `workflow_graph` / `statistics` / `usage` / `sentence` 📄 | Lineage, acceptability evidence, durable decisions, neutral provenance, participation planning, statistical evidence layer, lexical observability, sentence heuristics | Facades verified present (statistics: top-level `writer_runtime.statistics` package, not `domains/`) | Largely deterministic; statistics advisory-only, never mutates | Provenance + evidence across all; statistics model-gated by governance | Many lack adapters (no callable capability claims); sentence facade is diagnostic-bus oriented; statistics needs `decision_lineage`-resolved outcomes |
| Workbench Apply 📄 | Sole manuscript mutation: journaled atomic one-file apply + Git commit + Undo; proposals accept; self-repair/chapter-improvement wired | `/proposals/{pid}/accept`, `/undo`, `chapter_apply.py`; editing/self-repair/chapter-improvement routes | Mutating, journaled, undoable | Apply receipts, decision log, Git history | Large-region staging undesigned (ADR-005 proposed); quality bridge unwired (read-only mapping exists) |
| Mission publication 📄 | Release assurance over stored evidence: assessments, fingerprinting, identity, calibration, followups, policy gates | `mission_control/publication/` (`service`, `pipeline`, `identity`, `evidence`, `fingerprint`, `calibration`, `followups`, `publishing`, `policy.get_gate/derive_readiness`); `/api/publication`; `BookPublishingPage`; `/writer` queue | Deterministic; no model calls, no writes, no deploy | Dossier dir, manuscript fingerprints, versioned policy | Release-assurance slice only — not the full §11 Publication section (PUB-09 scope) |
| Jev authoring rig 📄 | Prereg discipline, claim ledger, runner/result convention, governed edit grammar | `RUN.md`, `AGENTS.md` ("never invent a result"), `planning/`, `evidence/ledger.md` (112 KB), `results/*.jsonl` (per-case rows), `examples/*/run_*.py + selftest.py`, `scripts/apply_edits.py` (Current Text / Recommended Change) | Deterministic runners; human-governed | Commit + prompt hash + seed per row; ledger claim types | Author-side; align, don't fork |

## 2. Requires extension (real base, named gap)

| Gap | Base to extend | Why not new |
|---|---|---|
| CR01–CR12 cruft classifier ✅ delivered PUB-02 (deterministic v0.1, `publication_cruft` analyzer + `cruft` CLI; thresholds uncalibrated, model seam prepared-not-dispatched) | `reader_legibility` (workflow leakage, placeholders, reproduction gaps) + `artifact` detectors + `evidence` (claim↔result check) + `argument` (contradiction/drift) | Signals exist; classification + calibration missing → classifier built; held-out suite + promotion gate live in PUB-08 |
| Cognitive-complexity detector | `editing` (new dimension block, versioned profile) + `manuscript_ir` roles + `statistics` features | Mechanical layer proven; thresholds need calibration, not invention |
| Claim↔repo reconciliation | `evidence.verify_claim/verify_chapter` + `manuscript_ir` snapshots + book-side ledger/result conventions | Verification pipeline exists; book-specific binding (prereg/runner/ledger schema) missing |
| Pedagogical/representation analysis | `argument` (concept/prerequisite maps) + `editorial` + `mri` + `taste` benchmarks | No recommender exists; build on diagnosis, not beside it |
| Public quality surface | `quality` domain → register `runtime.quality` facade (findings, campaign status, reader_study) | Domain tested (WRITER-QUALITY-01…07); only exposure missing |
| Staged large-region edits | `vfs` change-sets + Workbench Apply | Both exist; merge/authorization design missing (U1) |
| `Current Text/Recommended Change` interop | `apply_edits.py` grammar ↔ VFS/proposals | Author workflow proven; machine interop missing |

## 3. Genuinely missing (no reusable base found)

- Calibrated cruft/complexity thresholds and dev/held-out eval suites (design in
  PUB-02/04; must not invent scores before evaluation).
- Visual-opportunity recommender (table/figure/diagram selection); rendering support
  (Hugo/EPUB) exists, selection logic does not.
- Independent-validation protocolCred (separate-model re-verification with
  `CONFLICTED_MODEL_JUDGEMENT` handling) — pieces exist (`qc`, `verify`,
  `council`, `evaluation_fabric`), no publication-grade composition.
- Portfolio-scale publication orchestration in Mission (PUB-09/11 scope).

## 4. Entry-point index (PUB-01 must consult before proposing anything)

Writer CLI: `writer editing`, `writer quality`, `writer book-campaign`,
`reader-legibility review`; Writer web `/api/editing/*`, self-repair routes;
Workbench `/proposals/{pid}/accept`, `/undo`, editing/self-repair/
chapter-improvement routes; Mission `/api/publication/*`, `/api/writer/*`,
`/api/quality/*` (legacy), `/api/technical/*`; book-side `apply_edits.py --edits
<file> --apply --chapter <ch> [--diff]`.

## 5. Verification performed (per stage; inherited claims are not re-claimed)

### PUB-00 (2026-11-24; tail truncated — see note)

- `build_catalog()` imports and builds: **165 runtimes** (system python +
  writer-runtime/writer-core on PYTHONPATH; Writer `.venv` lacks deps —
  full-suite pytest blocked on missing `writer_ai`, recorded not worked around).
- `editing` parser+scorer executed on Jev Ch1: 12 sections; `paragraph_load`
  [NOTE PUB-01: the file ends mid-sentence here — PUB-00's remaining detail was
  lost to a truncated write and is NOT reconstructed. Replacement evidence for
  the same properties is re-established live in "PUB-01" below and in §8.]

### PUB-01 (2026-11-24)

- `build_catalog()` → **167 runtimes** (`editing`, `mediated_read` added).
  Scoped validation `validate_catalog_against_registry(catalog,
  set(runtime.names()), adapters=runtime.capabilities._adapters)` (live
  adapter map — the validator defaults to an empty map, which reports 17
  unrelated adapter problems and is NOT the scoped result): missing
  `['metadata_generation']` only; 46 orphaned (all unrelated owners);
  adapter problems `['analysis_state: EVALUATE without adapter']` only.
  PUBLICATION-scoped agreement achieved; remainder documented-open (§8).
- `runtime.editing` materialized via `build_runtime()` + `require('editing')`:
  `EditingDomainFacade`, 34 books listed, `EditingSummaryDTO` returned.
- `runtime.mediated_read` materialized via `require('mediated_read')`:
  `MediatedReadFacade`, `list_runs()` → `[]`, `builtin_readers()` returns
  the reader-profile mapping. (Requires Writer CWD for `config/models.yaml`.)
- Focused suites (`C:\Projects\writer\venv\Scripts\python -m pytest`,
  CWD `C:\Projects\writer`): `tests/runtime/editing` +
  `tests/runtime/quality` → 86 passed, 1 failed
  (`test_direct_rejects_invented_citations` — pre-existing, see §8);
  `tests/runtime/mediated_read` + `tests/runtime/evaluation_fabric` +
  `tests/runtime/test_capability_resolution.py` → 114 passed;
  catalog-consuming CLI suites (`test_runtime_capabilities_cli`,
  `test_ai_participation_cli`, `test_improve_explain_participants_cli`,
  `test_no_hardcoded_knowledge`) → 30 passed.
- Working Writer test invocation: `C:\Projects\writer\venv\Scripts\python`
  (3.11.4, has `writer_ai`/`writer_runtime`/`writer_core` installed).
  `.venv` (3.13.3) is bare and cannot run the suite; system python has only
  `ai`. PUB-00's "blocked on missing `writer_ai`" is corrected: use `venv`.
- Jev `results/ch01.jsonl` re-characterized read-only: 27 rows = 20
  `provider="predicate"` rows (zero tokens, empty model, `agrees_with_predicate`)
  + 7 aggregate rows. Establishes the *file* holds predicate-only rows; does
  NOT establish experiments were never completed elsewhere (carried to PUB-03
  as unresolved correspondence — see STATE.md §4.6).

### PUB-02 (2026-11-24)

- CR01–CR12 classifier implemented deterministic-first, no model dispatches:
  `packages/writer-core/writer_core/analysis/publication_cruft.py`
  (`PublicationCruftClassifier`, `DETECTOR_VERSION=publication-cruft-v0.1`,
  `CRUFT_PROFILE=cruft-v0.1`, `calibrated=False`); CLI `writer cruft review`
  (`writer_cli/commands/cruft.py` + `main.py` registration). Library+CLI
  surface like `reader_legibility` — deliberately NOT a registered runtime, so
  no catalog manifest is warranted (consistent with D-PUB-09); catalog stays
  167, scoped validation unchanged.
- Reuse honoured, nothing forked: block spans + `EvidenceRole` imported from
  `reader_legibility` (tables/code fences excluded from prose-tone counts);
  evidence-bound CRs take an explicit `EvidenceIndex` and report
  NEEDS_EVIDENCE without one (missing evidence never success); CR11
  cue-then-silence discipline follows `argument.disagreement`.
- Hard rules enforced in code: preservation gate (NOT_OBSERVED honesty,
  did-not-run, Limitations sections, amendments, open questions) exempt from
  CR03/04/05/07/08/09 per block (CR04 still flags scaffolding while the
  correction fact stays preserved); every finding carries span + evidence
  role + `MEASURED_TEXT` label + severity/confidence (detector-internal,
  uncalibrated) + provenance (fingerprint, evidence revision, detector +
  profile versions); `prepare_typed_task` exposes the D-PUB-08 seam
  (Writer-owned prompt + `CruftAdjudicationResponse` contract) for the three
  model-candidate CRs (CR07/CR08/CR11) — prepared and contract-tested, zero
  dispatches in PUB-02.
- Calibration suite: `tests/core/test_publication_cruft.py` (27 unit tests)
  + `tests/core/test_publication_cruft_calibration.py` over
  `tests/core/fixtures/publication_cruft_calibration.jsonl` (29 dev + 10
  held-out entries; real Jev Ch1/Ch2 excerpts + labelled synthetic controls;
  false-positive traps: code-fence/table exclusion, Ch1 NOT_OBSERVED honesty
  as must-preserve, stopword/URL-artefact CR11 traps). Thresholds frozen
  a priori; held-out evaluated once, never tuned. Result: 67/67 pass
  (incl. the new CR11 URL/mixed-block traps found during Ch1 demonstration).
- Live demonstration (read-only): Jev Ch1 with chapter inventory 1–36 bound
  → 1 finding (CR04 LOW consolidation suggestion on the CAPSTONE-02B
  correction note, fact preserved), 11 preserved (incl. NOT_OBSERVED table,
  did-not-run, Limitations), 7 needs-evidence (unbound result rows/repo
  manifest/artifacts — reported, not passed), 0 model candidates. Jev Ch2
  → 0 findings, 6 preserved, 7 needs-evidence. Fingerprint `435974701050…`.
- Regression (same invocation/CWD as PUB-01): editing+quality 86+1 (sole
  failure still `test_direct_rejects_invented_citations`, unchanged);
  mediated_read+evaluation_fabric+capability_resolution 114 passed;
  catalog CLI suites 30 passed
  (`test_runtime_capabilities_cli` + `test_ai_participation_cli` +
  `test_improve_explain_participants_cli` 27, `test_knowledge_state_cli` 3 —
  PUB-01's `test_no_hardcoded_knowledge` name does not exist; 30 total
  confirmed). `tests/core/test_reader_legibility.py`: 15 passed + 2 failed
  (`test_evaluator_reports_not_built_without_fabricating`,
  `test_evaluator_does_not_convert_failure_to_pass` —
  `AttributeError: EnvironmentIdentityStatus.BLOCKED` in the untouched
  reproduction_readiness evaluator path; PUB-01 never ran this file, so
  unbaselined; recorded here as pre-existing, unrelated to PUB-02).

### PUB-02 fix batch (2026-11-24; Codex CONDITIONAL blockers + hygiene)

- CR01 binding rule: status claim with result rows present but no
  backticked arm → NEEDS_EVIDENCE (claim-to-row binding required; never
  silent pass). Regression test: unrelated rows + unquoted arm →
  NEEDS_EVIDENCE.
- CR05 bound-evidence comparison: extracts the claim's own
  version/hardware facts (`_extract_env_claims`, numeric
  `_versions_agree` with operator support) and compares against bound
  `environment_facts`; uncomparable claims → NEEDS_EVIDENCE. Tests:
  matching facts pass silently (old pattern-token comparison false-fired
  here), mismatched version is a finding, unbound package is
  indeterminate.
- Adjudication contract: `AdjudicationVerdict` enum
  (keep_finding/preserve/unclear), non-empty rationale/quote_used,
  `quote_supported_by(passage)` passage check; contract-tested, zero
  dispatches stay zero. Unused `get_runtime` import removed from the
  cruft CLI. CR09 dedupes by block before the minimum-blocks threshold.
  CR07/CR08 `confirmed_stale` fixture entries relabelled
  `candidate_positive` (screen vs ground truth separated; harness
  asserts model_candidate on them).
- Suites now 35 unit + 40 calibration = 75 passed. Live: Jev Ch1
  revision-only index → 1/11/9; with inventory 1-36 → 1/11/7 identical
  to baseline (delta is the 2 unbound-inventory CR06 entries, not the
  CR01/CR05 fixes). Catalog still 167; Jev tree unmodified.

### PUB-02 fix batch 2 (2026-11-24; Codex delta re-review BLOCKED points)

- CR01 binding rule tightened: claim arm binds against the row `arm`
  field only (whole-row substring check removed); missing/unmatched arm →
  NEEDS_EVIDENCE, never a stale finding or silent pass.
- CR05 hardware: exact affirmative match required
  (`_affirmative_hardware` polarity: negation/unknown → indeterminate
  NEEDS_EVIDENCE); version numerics unchanged.
- Adjudication: `ensure_verdict_quote_supported` + dispatch-seam check --
  off-passage `quote_used` fails as `INVALID_TYPED_OUTPUT` (reported, never
  repaired/redispatched); zero dispatches stay zero.
- Suites now 42 unit + 40 calibration = 82 passed; live Jev Ch1 1/11/9 and
  1/11/7 (fingerprint `435974701050…`, baseline-identical).

### PUB-02 fix batch 3 (2026-11-24; Codex single remaining demand: CR05 exclusivity)

- Hardware mismatch contradicts only with exclusivity evidence (plain
  `environment_facts` dict carries no exclusivity guarantee): explicit
  sole-hardware scope (`_exclusive_hardware`: only/exclusively/exclusive/
  solely/single/sole in the affirmed value, e.g. `{"hardware": "H100 only"}`)
  or known-incompatible families (`_hardware_contradicts`: TPU vs
  NVIDIA-GPU stack GPU/CUDA/A100/H100/V100; CPU exempt as co-present;
  same-family overlap never excludes). Default → NEEDS_EVIDENCE
  (indeterminate). Version numerics and negation/unknown handling
  unchanged.
- Suites now 46 unit + 40 calibration = 86 passed; live Jev Ch1 1/11/9 and
  1/11/7 (fingerprint `435974701050…`, baseline-identical).

## 6. CR01–CR12 cruft taxonomy with one-line decision rules (PUB-01)

Adopted as calibration/design input for PUB-02, not as established measures.
Every rule inherits the programme-wide constraints: no finding without a source
span + evidence role (§2 detector bases); genuine uncertainty, negative
results and methodological amendments are preserved (D-PUB-05); missing
evidence is reported, never success (ACCEPTANCE.md §2).

| ID | Name | One-line decision rule | Primary detector base |
|---|---|---|---|
| CR01 | Stale experiment status | Finding iff the manuscript describes an experiment whose authoritative evidence (ledger/results/rerun) is superseded or absent — bind the exact claim span to the exact evidence revision; mismatch or missing evidence is a finding, never silence. | `evidence.verify_claim`/`verify_chapter` + `manuscript_ir` snapshots + book ledger/results schema |
| CR02 | Superseded implementation descriptions | Finding iff prose describes code/runners that no longer exist or have changed at the current repo revision — repair by updating the prose, never by rewriting history. | `evidence` (claim↔repo) + book-side runner/ledger conventions |
| CR03 | Internal development commentary | Author-facing process notes (TODO-style, "we will") that do not serve the reader → move to planning/ledger, or delete only if they carry no limitation value; anything recording a limitation is preserved. | `reader_legibility` (workflow leakage) + `artifact` detectors |
| CR04 | Internal correction history | "We previously claimed X, now Y" scaffolding → consolidate into the current claim plus one traceable amendment note; the fact that a correction occurred is never erased. | `reader_legibility` + `decision_lineage` |
| CR05 | Obsolete environment constraints | Version/hardware limits no longer true → finding iff the claim is falsifiable against current environment evidence; update with a new measurement and keep the original as a frozen record. | `evidence` + book test/rerun artifacts |
| CR06 | Stale promises of future work | "In chapter N we will show" with no materialized or re-pointed target → finding; fix by fulfilling, re-pointing, or downgrading to an explicit open question — never by silent deletion. | `evidence` (claim↔result) + `argument` (cross-chapter diagnostics) |
| CR07 | Unnecessary research-process narration | How-the-work-was-done detail that does not help the reader use the result → condense to a provenance pointer (ledger/run id); the full record stays in the repo, not the prose. | `reader_legibility` (evidence intrusion, density) |
| CR08 | Excessive defensive writing | Hedging pile-up that obscures the warranted claim → tighten to the claim plus one limitation statement; genuine uncertainty is preserved, never edited out. | `reader_legibility` (repeated qualifications) + `editing` |
| CR09 | Redundant evidence disclaimers | Repeated "limited evidence" notes → keep exactly one per claim where the claim is made; the evidence table is a formal record, not a defect by itself. | `reader_legibility` (repeated qualifications); cf. V2 negative-control 7 |
| CR10 | Internal project-management references | Tickets, branch names, owner names in prose → replace with content; traceability lives in the ledger/decision log, not the manuscript. | `reader_legibility` (workflow leakage, placeholders) |
| CR11 | Contradictory research states | Two passages assert incompatible statuses/results → critical finding, blocked on resolution per the Jev decision table (completed+contradictory→block); never averaged or merged. | `argument.disagreement` + `evidence` verification |
| CR12 | Stale tables/figures/supporting artifacts | Figure/table contradicting its source file or revision → finding iff sha/revision mismatch; re-render from source or mark STALE; a missing source is reported, never treated as success. | `evidence` + `manuscript_ir` snapshots + book results/figures schema |

## 7. AI primitives inventory (PUB-01; reuse verdicts for PUB-02/03/04)

"Implementation" is verified source, not catalog text. "Tests" cites observed
suites (targeted runs in §5 cover editing/quality/mediated_read only; the rest
is existence-verified, not executed here). Publication taxonomies, severity and
editorial judgment stay in Writer or the owning domain — no new generic AI
abstraction is created in PUB-01 (amendment B holds: no demonstrated consumer
requires one).

| Primitive | Implementation | Callable interface | Tests | Observed consumers | Limitations | Reuse verdict |
|---|---|---|---|---|---|---|
| Bounded classification | `writer_ai` `DomainClassificationService` / `ScorableClassifier` (embedding-centroid, cosine; YAML seeds) | `classify(text, top_k, min_score, context)` | `tests/ai/services/test_domain_classification_service.py` | book-evolution routing (`ai.books` reads `.writer` evidence) | Embedding-similarity only; no calibration; `ai.books` already breaches the book-agnostic boundary | Reuse for PUB-02 CR-classifier features only if deterministic signals prove insufficient; do not build on until then |
| Multi-label classification | `ai.scoring` dimension registry + `ScoringService` (independent dims, e.g. `manuscript-prose-v1` clarity/argument/precision/economy/voice/structure 1–5, mean overall) | `ScoringService.score(...)` → `ScoreBundle` with provenance | `C:\Projects\ai\tests\scoring` (~27 modules per Stage0) | Mission `/api/quality` via `manuscript_cli` (legacy advisory lane, ADR-003) | Mean-overall is a composite; uncalibrated for publication use; lane is legacy pending migration | Keep as legacy advisory only; PUB-02/04 must not train or threshold on it (D-PUB-04) |
| Structured model judgments | `ai.scoring` `LLMJudgeScorer` (`_JudgeVerdict`); Writer `quality` `ReviewResponse`/`JudgeResponse` (Pydantic); `run_typed_task` schema seam | Typed prompts → validated Pydantic contracts; schema passed to Worker, validated by Writer (Pydantic) | `tests/runtime/quality` (87 incl. 1 pre-existing failure, §8) | quality `direct`/`bounded_judge` strategies | Verdict shape is enforced by Writer; verdict *truth* is not — revising-model output is `CONFLICTED_MODEL_JUDGEMENT` | Reuse the seam + Pydantic-contract pattern in PUB-02/04; never accept a revising model's verdict as independent |
| Semantic equivalence | `ai.scoring` embedding-pair scorers; quality `check_quotation_consistency` / `check_numbers_present`; `writer_ai` `TripleConsistencyEvaluator` (preservation rates) | Quotation/numbers checks inside quality `verify_evidence`; triple preservation metrics | quality suite; `tests/ai/test_labeled_text.py` (parsing only) | quality verification, self-repair preservation | No dedicated NLI/entailment primitive found in `verify`/`eval`; similarity ≠ equivalence | Gap noted but NOT blocking: PUB-02/03 proceed on exact-excerpt + snapshot-hash checks; revisit only with a demonstrated consumer |
| Contradiction detection | `argument.disagreement`: deterministic cue-based `semantic_stance` (supports/contradicts/unclear) + `assess_semantic_disagreements` linking CONTRADICTS assessments to semantic nodes; silence beats fabrication | `assess_semantic_disagreements(*, chapter_id, assessments, observed_nodes, ...)` | `tests/runtime/test_argument_*.py` (observed, not executed here) | `argument` cross-chapter diagnostics | Heuristic v1 cue lists; semantic-channel nodes only | Reuse as CR11 base in PUB-02/03; model-backed semantics stays a candidate input, never the decider |
| Claim extraction | `evidence` facade: `extract_claims`, `verify_claim_text`, `verify_claim`, `verify_chapter`; quality `build_context` | Facade methods (async, file/project-oriented) | quality suite; evidence tests not executed here | quality engine, (planned) PUB-03 reconciliation | Evidence facade has no capability adapter (capability-plane gap, recorded) | Direct reuse in PUB-03 claim↔evidence binding; adapter gap is a PUB-07 concern, not a PUB-03 blocker |
| Evidence-grounded verification | evidence pipeline + quality `deterministic`/`direct`/`bounded_judge` + self_repair gates A–E + `qc.evaluate_candidate_qc` | `QualityEngine.evaluate(...)`, gate verdicts, `portable-v1` DTOs | quality suite; `tests/runtime/qc*`, self-repair routes per baseline-health | quality campaigns, self-repair, Workbench chapter-improvement | Overlapping verifiers (self-repair A–E vs `quality.verify_candidate`) with undocumented division (ownership-map §overlap-3) | Reuse the quality-strategy pattern for PUB-02/04; verifier-division decision needed before PUB-06 (recorded, not solved here) |
| Abstention / uncertainty | quality DTO `ABSTAIN`; `ai.scoring` `requirements_v2.conjectural_status`, `technical_benchmark` abstained-rows, `real_artifacts` ABSTAIN outcome | Status enums, not a service | quality suite | quality evaluation, benchmark harnesses | No uniform abstention protocol across primitives | Adopt ABSTAIN + unknown-freshness as the PUB-02/03/04 convention (ACCEPTANCE.md §2); no new abstraction |
| Pairwise comparison | `sentence_arena` (facade delegates to engine; preference/comparison services); `qc` training-pair derivation (`ai.scoring` `pairs.py`: `pair_rewards`, `training_eligible`) | Arena facade (delegating), `rows_from_bundle`, eligibility reports | `tests/runtime/test_sentence_arena_runtime.py` (observed) | sentence training-data pipelines | Arena-as-judge for publication quality not validated; pairs are training-oriented | No PUB-02/03/04 consumer yet; available for PUB-05 comprehension probes / PUB-08 calibration if needed |
| Confidence representation | Nowhere calibrated: `reader_legibility` high/medium/low (detector-internal); editing scores uncalibrated; `ai.scoring` fusion/normalization 0..1 (weighted, not calibrated); `statistics` calibration + shadow evaluation (governed) | Scores + `confidence_semantics` strings in manifests | editing/quality suites | Manifests, reports | Any cross-system use of these numbers as probabilities is invalid | Reuse `statistics` calibration/shadow-eval in PUB-04/08; forbid calibrated-confidence claims before held-out eval (D-PUB-04) |
| Model-independent evaluation | `statistics` (top-level package; model use governed, advisory-only), `decision_lineage`, `author_evidence`, `sentence_evolution` | Facades; statistics needs `decision_lineage`-resolved outcomes | editing-adjacent suites; statistics tests not executed here | Lineage/provenance across domains | Many facades lack capability adapters; statistics needs resolved outcomes to be meaningful | Foundational for PUB-08 independent validation; deterministic-first ordering mandatory (D-PUB-04) |
| Deterministic+model hybrid | quality engine strategies (`deterministic` = zero Worker calls; `direct`; `bounded_judge` = shadow, policy stays NEEDS_REVIEW) + `models.typed_task.run_typed_task` (one Worker call per typed task; no domain-level retry/repair of invalid typed output — infrastructure POST retry may occur below the seam; validation reported never repaired, usage passed through) | `QualityEngine.evaluate(strategy=...)`, `TypedTaskResult` (succeeded only if Worker ran AND contract validated) | quality suite; `tests/runtime/test_model_task_policies.py` (Stage0) | quality, contract drafting (8 calls, $0.076499, route `default_deepseek_go`) | Hybrid value proven only for finding-triage; publication-grade composition still missing (CAPABILITIES §3) | Canonical pattern for PUB-02/04 model use; Worker routing contract in DECISIONS.md D-PUB-08 — no new gateway |

## 8. PUB-01 registry reconciliation (executed 2026-11-24)

Live check: `build_runtime()` → `runtime.names()` (122 registered) vs
`build_catalog()` (167 manifests) via
`validate_catalog_against_registry(catalog, set(runtime.names()),
adapters=runtime.capabilities._adapters)`. (Bare call without the live
adapter map reports 17 adapter problems across unrelated domains and is
not the scoped result.)

| Apparently missing | Verdict (architecture describes; catalog must not dictate) | Disposition |
|---|---|---|
| `editing` | Independent runtime domain (registered; `create_editing_domain`, facade, CLI, tests) | **Manifest added** — PUBLICATION-critical |
| `mediated_read` | Independent runtime domain (registered; `create_mediated_read_domain`, facade+engine+store+ORM, 7 CLI commands, 114-test suite incl. evaluation_fabric) | **Manifest added** — priority High (reader-comprehension eval) |
| `quality` | Existing implementation lacking registration AND lacking any facade/factory (`create_quality_domain` absent repo-wide); engine + campaign + CLI (7 commands) + tests exist | **Deliberately not registered in PUB-01** — CLI-only with unblock plan; decision D-PUB-07, U2 stays open |
| `reader_legibility` | Reusable library function + CLI surface (`writer-core` analyzer + `reader_legibility` CLI); never a runtime domain | **No manifest** (manifests describe registered runtimes only); thin-facade need recorded as blocker V2-#4 |
| `self_repair` | Service owned by existing domain `artifact` (`contract_service`, gates A–E, `repair_worker`) | **No manifest**; ownership already in ARCHITECTURE.md §2 |
| `book_campaign` | Service owned by existing domain `artifact` (`book_coordinator`, campaign store, CLI `writer book-campaign`) | **No manifest**; consolidation decision D3/U3 open |
| `evaluation_fabric` | Orchestration service, not a runtime domain (`services/evaluation_fabric`: CQRS service + ZeroMQ/runtime-bus transport, built on the `eval` domain store via `build_evaluation_fabric`) | **No manifest**; may host paired model probes, never human studies |
| `refinement` | Existing implementation lacking registration, factory, CLI and callers (stub-defaulted skeptical loop over `writer_ai`; zero repo-wide consumers; not the registered `refine` human-review domain) | **Investigated, not registered** — advertising a default-no-op loop as a runtime would be dishonest; PUB-02 may evaluate the pattern with real injected callables |

Outcome: `validate_registry()` scoped result — missing `['metadata_generation']`
only (model-routing metadata, unrelated owner — recorded below, not fixed here);
46 orphaned manifests (code present, never registered: `agent_mode`,
`agent_terminal`, `agentic_code_lab`, `blender`, `car`, `codex_manager`,
`corpus_lineage`, `council`, `define`, `delta_memory`, `discovery`,
`eck_correction`, `eck_experiment`, `editorial_memory`, `enl`, `episode`,
`err`, `gems`, `goal`, `ingest`, `knowledge_graph`, `lineage_forecasting`,
`liver`, `morning`, `narrative`, `narrative_integrity`, `narrative_profiler`,
`novel_formatter`, `overnight`, `performance`, `preference`, `program_graph`,
`replay`, `scene`, `scene_graph`, `skills`, `speech`, `st_learning`,
`symbolic`, `sync`, `synth`, `thinking`, `timeline`, `voice_analysis`,
`world`, `writing`); adapter problem `analysis_state: EVALUATE without adapter`
only. Full green is **documented-open** with owner (Writer owning team backlog).
PUBLICATION impact: none of the 47+1 items blocks PUB-01/PUB-02 gates; one is
forward-relevant — `council` is named by PUB-08 (`qc` + `verify` + `council` /
`evaluation_fabric`), and its registration (or a principled alternative owner)
is a PUB-08 prerequisite, recorded here rather than solved here.

Pre-existing failure (not caused by PUB-01; `catalog.py` is not imported by the
failing path): `tests/runtime/quality/test_vertical_slice.py::test_direct_rejects_invented_citations`
asserts an `EVIDENCE_UNVERIFIED` entry in `result.errors` when `direct`
evaluation rejects invented citations. Post-Stage0 quality changes (`WQ-07
evidence verification`, `add distillation`) predate PUB-01. Owner: Writer
quality domain; PUB-02 must re-baseline before asserting quality regressions.
...[truncated 2087 chars]