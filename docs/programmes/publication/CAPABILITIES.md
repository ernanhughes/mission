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
| Cognitive-complexity detector ✅ delivered PUB-04 (deterministic v0.1, `publication_complexity` CX01–CX15 analyzer + `complex` CLI; profile `complexity-v0.1` uncalibrated, Level C seam prepared-not-dispatched) | `editing` (sentence/word heuristics mirrored — writer-core stays dependency-light, no `writer_runtime` import) + `reader_legibility` spans/roles + `manuscript_ir`/`statistics` (Level B proxies only, not wired) + `argument` cue discipline (conceptual) | Signals exist; workload classification + calibration missing → screen built; held-out suite + promotion gate live in PUB-08 |
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
| Deterministic+model hybrid | quality engine strategies (`deterministic` = zero Worker calls; `direct`; `bounded_judge` = shadow, policy stays NEEDS_REVIEW) + `models.typed_task.run_typed_task` (one Worker call per typed task; no domain-level retry/repair of invalid typed output — infrastructure POST retry may occur below the seam; validation reported never repaired, usage passed through) | `QualityEngine.evaluate(strategy=...)`, `TypedTaskResult` (succeeded only if Worker ran AND contract validated) | quality suite; `tests/runtime/test_model_task_policies.py` (Stage0) | quality, contract drafting (8 calls, $0.076499, route `default_deepseek_go`) | Hybrid value proven only for finding-triage; publication-grade composition still missing (CAPABILITIES §3) | Canonical pattern for PUB-02/04 model use; Worker routing contract in DECISIONS.md D-PUB-08 — no new gateway. PUB-04 reuses the seam prepared-not-dispatched (8 CX candidate payloads, `ComplexityAdjudicationResponse` contract + quote-discipline tests, zero dispatches, $0) |

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

### PUB-03 (2026-11-24; Muse implementation, pending review gate)

- Reconciliation engine `packages/writer-core/writer_core/analysis/evidence_reconciliation.py`
  (`evidence-reconciler-v0.1`, profile `reconcile-v0.1`, `calibrated:false`):
  deterministic 10-category claim extraction, explicit-identifier binding
  (D-PUB-20 precision rules), 8-state adjudication, conditional
  preservation (`evaluate_preservation`), freshness `Binding` + `check_stale`,
  PUB-02 `resolve_needs_evidence` consumer. Zero model dispatches.
- Jev adapter `packages/writer-core/writer_core/analysis/jev_evidence.py`
  (`jev-evidence-v0.1`): explicit roots only (inspected `results/*.jsonl` +
  all capstone files per-row; every results file discovery-indexed;
  `evidence/ledger.md`, inspected `metadata/*.yaml`, `environment.md`,
  `deferred-runs.md`, chapter-referenced examples/src/figures/evidence).
  Tolerant multi-schema JSONL reader (standard/analytic/replay/
  pretty-printed/unsupported-explicit); `to_evidence_index()` projects the
  PUB-02 `EvidenceIndex` shape (provider-as-arm translation documented).
  Selftest runtime counts explicitly unavailable (D-PUB-23, fix batch 2;
  supersedes D-PUB-19/D-PUB-22): no execution; static call-site
  counts (52/17/73) kept as pure parsing and bound to nothing.
- CLI `writer reconcile` (`inventory|chapter|book|resolve`, JSON envelopes
  `writer.reconcile.cli.v1`); registered in `writer_cli/main.py`. No catalog
  change (library+CLI surface per D-PUB-11).
- Tests: 38 unit (`tests/core/test_evidence_reconciliation.py`, incl. CLI
  smoke on a synthetic root) + 38 calibration (23 dev + 15 held-out,
  `evidence_reconciliation_calibration.jsonl`; real Jev excerpts + labelled
  synthetic controls; held-out from uninspected Ch3/Ch8 prose + novel cases).
- Live read-only demo, Jev `c7aaad7` (inventory `jev@7f008df8772f677f`,
  4 chapters inspected, 32 uninspected — coverage partial, never full):
  59 supported / 9 not_applicable / 15 unresolved / 3 superseded / 3 partial,
  0 contradicted/conflicted, 6 correction proposals. Ch1's 7 PUB-02
  NEEDS_EVIDENCE: CR02x4 + CR12x1 + CR06x2 resolve silent with the real
  index; CR01x2 resolve via `reconcile resolve` (L111 SUPPORTED, L493
  unresolved-on-excerpt / partial-in-full-text). Genuinely stale live
  claim demonstrated: Ch7 `run_ch07.py` reference (file never existed;
  SUPERSEDED + update_impl_description, fully traced). Ch1/Ch2 forward
  pointers to Ch7/Ch2 resolve SUPERSEDED (promise materialised;
  incorporate_results). Preservation upheld everywhere (incl. Ch1
  did-not-run + Limitations); no silent passes. Jev tree verified clean
  (`scripts/` pre-existing untracked only).
- Regression (same invocation/CWD as PUB-01): editing+quality +
  publication_cruft (46+40) + reader_legibility = 190 passed, 0 failed
  (the 3 pre-existing failures are gone — owning teams fixed them
  concurrently, §4.3 — not PUB-03); capability short test 1 passed
  (1 long deselected); CLI surface verified (`--help` lists reconcile;
  smoke test green). Mediated/eval 114 deferred (long suite, untouched
  paths — recorded, not run). Catalog-CLI "30" suite names no longer
  exist (owning-team test reorganisation, concurrent activity); short
  capability test passes instead — recorded, not a regression.

### PUB-03 fix batch (2026-11-24; Codex BLOCKED 5 + DeepSeek carry-forward)

- Chapter-scope rule (D-PUB-21): arm-identified rows bind within the
  claim's chapter unless explicitly cross-referenced or the experiment
  identity is globally unique (`_in_scope`, `_completion_rows`,
  `_claim_references_other_chapter`, `_experiment_chapters`).
- Selftest hardening (D-PUB-22): validated explicit set, per-script
  120 s + 300 s total budget, post-run clean-tree check in notes.
- `ReconciliationState` docstring completed; `argument.disagreement`
  lineage stated as conceptual (D-PUB-12); `reconcile resolve`
  envelope validation (`_unwrap_cruft_report`); CLI docs for
  `reconcile` + `cruft` (INDEX 50; 5 remaining missing are pre-existing
  owning-team backlog).
- Tests: 85 reconciliation (76 + 9 new); combined fast neighbours 190;
  capability short 1 + 1 deselected. Live: book 01,02,07,36 →
  59/9/15/3/3 @ `jev@7f008df8772f677f`; selftests 53/27/87; catalog 167.

### PUB-03 fix batch 2 (2026-11-24; Codex 2 residuals, applied
post-acceptance — STATE §9)

- Execution removed (D-PUB-23): no inventory-time script runs;
  runtime counts are an explicit unavailable named state
  (`runtime: unavailable` + static sites + validation/inventory
  notes); `_runtime_unavailable` screen resolves genuine
  selftest-count claims to UNRESOLVED in `_adjudicate_status` and
  `_adjudicate_result` (claim-gated; unavailable markers explain no
  numbers).
- README count 48 → 50, exactly as specified. NOTE: `docs/cli` saw
  active owning-team edits throughout the session (new documented
  `complex` command; INDEX.md hand state: 49 rows incl. reconcile +
  cruft + complex, stale 48 total vs 57-command live tree). Coverage 1
  passed / 3 failed — missing docs are the 5 batch-era gaps only;
  reconcile + cruft rows and README dirs (batch outputs) remain present.
  Owning-team backlog, recorded not fixed.
- Tests: 90 reconciliation (50 unit + 40 calibration; two
  `dev-selftest-*` entries re-pointed at unavailable markers);
  combined fast neighbours 190; capability short 1 + 1 deselected.
  Live: book 01,02,07,36 → 57/17/9/3/3 @ `jev@6c13d2837f138c84`
  (rev changed: entry digests feed the hash, notes do not);
  selftest notes `runtime=unavailable; static_sites=52/17/73`;
  cruft Ch1 1/11/2 (fingerprint unchanged); catalog 167.

### PUB-04 (2026-11-24; Muse implementation, pending review gate)

- CX01–CX15 deterministic screen implemented, zero model dispatches:
  `packages/writer-core/writer_core/analysis/publication_complexity.py`
  (`PublicationComplexityClassifier`, `DETECTOR_VERSION=
  publication-complexity-v0.1`, `COMPLEXITY_PROFILE` profile
  `complexity-v0.1`, `calibrated=False`); CLI `writer complex
  review|scan|compare` (`writer_cli/commands/complex.py` + `main.py`
  registration; `docs/cli/complex/README.md` + INDEX row → 51).
  Library+CLI surface like `reader_legibility` itself — deliberately
  NOT a registered runtime, so no catalog manifest is warranted
  (consistent with D-PUB-09/10/11/24); catalog stays 167, scoped
  validation unchanged.
- Reuse honoured, nothing forked: block spans + `EvidenceRole` imported
  from `reader_legibility` (HTML figure blocks + code fences/tables
  excluded from prose-tone counts); editing sentence/word heuristics
  mirrored locally (no `writer_runtime` import — writer-core stays
  dependency-light); PUB-02 honest-record sections, preservation
  ordering, NEEDS-style reporting (here NEEDS_CONTEXT for terminology
  without a concept registry); methods sections exempt from CX12;
  lists exempt from CX10/CX11/CX05/CX06/CX12/CX14/CX15; definition
  blocks recorded as concept events and exempt from CX06; math spans
  recorded, never clause-parsed. Level B screens (`manuscript_ir`/
  `statistics` proxies) marked explicitly approximate; Level C never
  emitted — 8 adjudication payloads prepared via `prepare_typed_task`
  (CX02/04/06/07/10/11/14/15) for the D-PUB-08 seam, prepared and
  contract-tested, zero dispatched in PUB-04.
- Hard rules in code: preservation gate (honest-record sections +
  genuine-uncertainty markers exempt from tone/load CXs on the same
  block); every finding carries CX id, kind (observation/candidate —
  judgment never occurs), span + evidence role + MEASURED_TEXT label +
  severity/confidence (detector-internal, uncalibrated) + provenance
  (fingerprint, evidence revision, detector + profile versions);
  correction *directions* only (never prose); no composite anywhere —
  summary carries by-CX/by-severity/by-kind counts plus concentration
  composites (labels, not findings); `compare` adds max-severity so a
  staccato rewrite cannot win on count.
- Calibration suite: 41 unit tests
  (`tests/core/test_publication_complexity.py`) + 43 calibration
  (`test_publication_complexity_calibration.py` over
  `fixtures/publication_complexity_calibration.jsonl`: 30 dev + 12
  held entries; real Jev Ch1 excerpts + labelled synthetic controls;
  labels human/synthetic). Profile values frozen a priori and never
  retuned (pre-freeze work was structural precision + fixture-text
  shaping only); held evaluated once. Result: 83 passed + 1 xfailed —
  the xfail is a KNOWN-FN pinning case (held-cx15: 39-word block vs
  the 40-word floor; absolute-word floors are edge-brittle, PUB-08
  should consider density-relative sizing). Mandatory regression:
  staccato rewrite fires CX10-high + CX11 and never ranks below the
  genuinely-clearer rewrite (max-severity lens); clearer rewrite
  strictly reduces the original.
- Live demonstration (read-only, Jev `c7aaad7`): Ch1 → 38 findings
  (CX02×8/CX03×8/CX14×8/CX01×2/CX05×2/CX08×1/CX10×1/CX11×5/CX13×1/
  CX15×1/CX04×1), 10 preserved, 6 needs-context, 9 concept events;
  heaviest concentration L509 (closing question → interrupted-argument
  + qualification-pile-up); Ch7 clause-heavy (CX02×16/CX03×18), Ch35
  long-sentence-heavy (CX01×9), Ch9 staccato-heavy (CX10×9).
  Contrasting chapters confirm the screen discriminates workload
  shapes, not just length: editing scores Ch1 `good` on every
  dimension (88.7–100) with only two review findings while 17
  sentences exceed 35 words yet the real load is clause/qualification/
  interruption stacking — the baseline gap this stage closes.
  Bounded book-wide scan: 36 chapters, 1083 findings, coverage
  explicit (assessed vs code/table/figure/HTML/heading). Before-after
  on the real Ch1 closing block: overloaded 5×medium → staccato
  2 (1×high + 1×medium; count drops, max severity rises — the
  no-composite design stops the cheat) → clearer 0. Fingerprint
  `435974701050…` (unchanged from PUB-02/03: source untouched).
- Regression (same invocation/CWD as PUB-01):
  editing+quality+cruft+cruft-calibration+legibility+complexity(unit+
  calibration) = 273 passed, 0 failed (+1 xfailed, the known CX15
  FN); capability short 1 passed + 1 deselected; mediated/eval 114
  deferred (long suite, untouched paths — recorded, not run). Catalog
  167; Jev tree verified clean (`scripts/` pre-existing untracked
  only); zero model dispatches; $0 verification spend.

### PUB-04 fix batch (2026-11-24; Muse implementation, addresses the Codex
BLOCKED findings-contract defects + DeepSeek F1/F2/F3/F7 must-fix;
pending Codex + DeepSeek delta re-review)

- Codex findings-contract defects, all fixed in code with regression
  pins (`publication_complexity.py`; `complex.py`; both complexity test
  files; `docs/cli/complex/README.md`):
  1. CX07 zero-spans → every finding carries a usable source span per
     the new span contract (module docstring + complex README):
     sentence detectors span the quoted sentence occurrence, CX07 spans
     the premature term's first-use occurrence, block detectors span the
     measured block(s); CX07 line anchors bracket the use→define gap.
     Unlocatable term evidence reports needs-context (`missing:
     locator`), never a zero-span. Pinned by
     `test_premature_term_finding_carries_located_term_span`.
  2. Related-after-dedupe → linkage built AFTER dedupe; book-wide
     dangling related refs 312→0 (Ch1 12→0). Pinned by
     `test_related_links_always_resolve_to_surviving_findings` (incl. a
     same-CX-per-block two-run text, the path the old invariant test
     never exercised).
  3. Severity-preserving dedupe → max severity per (cx_id, start_line),
     ties keep first (D-PUB-30). The CX04 HIGH paragraph roll-up and
     the longer of two CX10 runs are now reachable (both were
     structurally dropped by first-wins). Pinned by
     `test_cx04_paragraph_rollup_survives_dedupe_as_high` and
     `test_same_block_duplicate_cx10_keeps_max_severity`.
  4. Span semantics defined once (contract + README, above) and applied
     uniformly (CX01/02/03/04-sentence/CX14 narrowed to quoted
     evidence; CX10a spans the run occurrence).
  5. `summary.generated_at` marked volatile and excluded from replay
     identity (`REPLAY_VOLATILE_KEYS` + `replay_identity()`; code +
     `test_replay_identity_excludes_volatile_generated_at`).
  6. `review --cx` rescopes (filter + pruned related + recomputed
     scoped summary via `rescope()`; finding_count and
     `summary.total_findings` always agree — the DeepSeek 1-vs-38 split
     is gone, verified live CX02 8/8); `compare` text mode shows
     `max_severity` per side. Pinned by
     `test_cli_review_category_filter_scoped_summary` and
     `test_cli_compare_text_mode_shows_max_severity`.
  7. `concept_index`/`glossary_terms` now RESOLVE CX07 terminology
     (registry hit = established vocabulary: no finding, no need) --
     wired, not removed, documented in `ReaderContext`, module
     docstring and README. The old test pinning NEEDS_CONTEXT-despite-
     index was rewritten to pin resolution, plus a glossary pin.
  8. `_is_html_block` narrowed to structural tags (figure/div/table/
     img/…; inline `<em>/<strong>/<a>/<code>/<span>` stays prose) and
     `_is_list_block` narrowed to list-structured blocks (list items +
     indented wrapped continuations; column-0 prose beside bullets =
     genuinely mixed and stays assessable). CX14 additionally measures
     mixed blocks on prose lines only (never quotes a `1.` fragment).
     Pinned by `test_inline_html_wrapped_prose_is_assessed`,
     `test_mixed_prose_and_list_block_measures_prose`,
     `test_wrapped_list_with_continuations_stays_structure`.
     Definition/methods exemptions untouched; Ch1/Ch7 spot-check below
     shows no whole-section suppression.
  9. Counts: INDEX total 48→51 rows; writer README top-level 50→51.
- DeepSeek F7 → held-cx15 unconditional xfail is now a STRICT
  behavioural pin: the check runs, an expected failure xfails, an
  unexpected pass FAILS loudly (promote the entry, never silently heal).
- Documented, not changed (known traps, PUB-08 owner; complex README +
  here): F4 indented/tilde listings (parser lane, 0 in Jev); F5 `$$`
  display math vs STATE claim; F6 coherent-short CX10-medium FP (needs
  connective/density-aware clearing); F8 calibration 11/12 synthetic
  held-out (broaden before any promotion); F9 editing `_stamp` flake
  (Writer editing owner).
- Suites: complexity 94 passed + 1 strict xfailed (was 83 + 1);
  combined neighbours editing+quality 87 + cruft/cruft-calibration/
  legibility 103 + complexity 95 = 284 passed + 1 xfailed, 0 failed;
  capability 8 passed + 1 deselected (long corpus); mediated/eval 114
  deferred (long, untouched). `ruff check` clean on all four touched
  files (format drift is pre-existing in untouched regions — not
  reformatted). Catalog 167; fingerprint `435974701050…` unchanged.
- Live re-verification (Jev `c7aaad7`, read-only): Ch1 → 38 findings
  with the IDENTICAL finding set as baseline (no dropped, no added;
  by_cx/preserved/needs unchanged 38/10/6; dangling 12→0) — all fix
  effects are strictly additive-correct there. Book scan → 36 chapters,
  1083 findings, zero per-chapter deltas; book-wide dangling 312→0.
  Ch7 still clause-heavy (CX02×16/CX03×18, 52 total). `compare` live:
  overloaded 3×medium → staccato 2 with max_severity high (count drops
  3→2 but severity rises — cheat visible) → clearer 0. Zero model
  dispatches; $0; Jev and writer trees clean of strays (Jev:
  pre-existing `scripts/` only); no commits/pushes, no manuscript
  edits, temp evidence removed at handover.

### PUB-04 fix batch 2 (2026-11-24; Muse implementation, addresses the
Codex delta re-review's 2 precise residuals on the fix-batch tree;
pending Codex + DeepSeek delta re-review)

- CX10 invalid span → run sentences located forward from the run's own
  start (`_locate_span(..., start=...)` + sequential location in the run
  branch): a later HIGH run whose final sentence also occurs earlier in
  the block quotes its own occurrence (pre-fix reproduced inverted
  char_start>char_end; post-fix start<end slicing the later run).
  Pinned by
  `test_later_cx10_run_with_repeated_final_sentence_keeps_valid_span`.
- Wrapped continuations → new `_prose_lines()` helper (list-item lines
  AND their indented wrapped continuations excluded, per the
  `_is_list_block` gluing rule): CX10/CX11/CX14 probe mixed blocks on
  genuine prose only, and CX11 quotes the probe — never list lines or
  continuations — whenever the block carries list lines (D-PUB-36;
  D-PUB-32's prose-only requirement extended from CX14 to CX10/CX11).
  Pinned by `test_mixed_block_continuation_load_is_not_prose` (no
  CX10/CX11 from continuation load),
  `test_mixed_block_genuine_prose_still_assessed_without_list_quote`
  (genuine prose still measured, probe-only quote) and
  `test_mixed_block_cx14_never_quotes_continuation`.
- Docs: module span contract + complex README state the forward run
  anchor and the prose-probe/quote rule; `--cx` rescoped summaries
  documented as keeping `preserved_count`/`needs_context_count`/
  `concept_events` chapter-scoped (README + `rescope()` docstring);
  held-cx15 rationale corrected to 39 words (1-word margin vs the
  40-word floor; count verified by running `word_count` on the fixture
  text, not by hand).
- Suites: complexity 98 passed + 1 strict xfailed (94 + 4 new pins);
  combined neighbours editing+quality 87 + cruft 46 + cruft-calibration
  40 + legibility 17 + evidence 50 + evidence-calibration 40 = 280
  passed; capability 8 passed (7 CLI + 1 short) + 1 deselected (long
  corpus); mediated/eval 114 deferred (long, untouched). `ruff check`
  clean on all touched Python files. Catalog 167.
- Live re-verification (Jev `c7aaad7`, read-only): Ch1 → 38 findings
  with the IDENTICAL by-CX set as baseline (fingerprint
  `435974701050…` unchanged; 10 preserved / 6 needs-context / 9 concept
  events). Book scan → 36 chapters, 1083 findings (total unchanged),
  book-wide dangling 0, zero bad (inverted/zero) spans. Ch7 still
  clause-heavy (CX02×16/CX03×18, 52 total). `review --cx CX02` live →
  8/8 with chapter-scoped counters (preserved 10 / needs 6 / concepts
  9). Zero model dispatches; $0; Jev clean (`scripts/` pre-existing
  only); no commits/pushes, no manuscript/evidence edits, temp cleaned.
- Untouched by instruction (recorded, not edited): writer `INDEX.md` /
  `README.md` command counts (owning-team flux; DeepSeek R1 stays
  backlog).

### PUB-04 fix batch 3 (2026-11-24; coordinator-executed, closes the
Codex delta re-review's 2 deeper edge residuals)

- Run findings require located occurrences: new `_strict_locate()`
  (verbatim forward search returning `None` on miss -- never a fallback
  span); the CX10 run branch declines any run with an unlocatable
  sentence (D-PUB-37). The old `_locate_span` fallback accepted a
  whole-block span as a run endpoint when filtering removed context.
- Probes are contiguous segments: new `_prose_segments()` (membership
  identical to `_prose_lines`, which now delegates to it); CX10 runs,
  CX11 and the CX14 opening probe each measure one segment, so prose
  is never joined across a removed list item (D-PUB-38). CX11 quotes
  its own segment text; CX14 probes the opening segment. Same-block
  dedupe unchanged (max severity per `(cx_id, start_line)`): two
  same-block runs collapse to one with a side-local quote and truthful
  run_length.
- Pins (5 new): cross-boundary no-join (run_length 3/MEDIUM, not the
  joined 6/HIGH), segment-local CX10/CX11 spans, opening-segment CX14
  scoping, `_strict_locate` unit pins (present/absent/offset/empty).
  Post-verification extension: consecutive-one-sentence CX10b run
  breaks on structural blocks (2 pins); whitespace-normalisation
  documented in the span contract.
- Suites: complexity 63 unit + 43 calibration (42 passed + 1 strict
  xfailed); full fast gate 467 passed + 1 xfailed / 0 failed;
  `ruff check` clean. Live (Jev `c7aaad7`): Ch1 38 identical, book
  36/1073 (was 1083; -10 removed cross-structural joins, Ch1
  untouched) with by-CX CX01:45 CX02:175 CX03:405 CX04:12 CX05:14
  CX06:65 CX08:5 CX09:7 CX10:60 CX11:78 CX12:15 CX13:42 CX14:139
  CX15:11, 0 dangling, 0 bad spans, fingerprint-stable; catalog 167;
  Jev clean; $0. Behavioural delta vs batch-2 tree: only the removal
  of non-contiguous cross-structural joins.

### PUB-05 (2026-11-24; Muse implementation, pending review gate)

- Executable editorial transformation planner
  (`packages/writer-core/writer_core/analysis/publication_pedagogy.py`,
  `publication-pedagogy-v0.1`, profile `pedagogy-v0.1` UNCALIBRATED) +
  `writer pedag plan|validate` CLI (`pedag.py` + `main.py` registration +
  `docs/cli/pedag/README.md`). Library+CLI surface, no runtime domain,
  no catalog change (D-PUB-39); zero model dispatches (typed-task seam
  prepared, `PedagogicalAdjudicationResponse` contract + quote-discipline,
  never dispatched — pin `test_zero_dispatches_in_this_module`).
- Reuse honoured, nothing forked: block spans from `reader_legibility`
  (code/table/figure excluded from prose probes); PUB-02 cruft reports
  (findings + preserved + needs_evidence, fingerprint-bound) and PUB-04
  complexity reports consumed from JSON, never re-detected; PUB-03
  reconciliation states consumed from JSON (chapter-scoped runs:
  Ch1 35 claims 22/7/4/2/0 — full-inventory run would resolve 2 more
  SUPERSEDED; chapter scope is the conservative planning input);
  declared intent from Jev `metadata/*.yaml` (purpose/claim-tiers/
  limitations/prereg as explicit sidecar, missing = uncertainty, never
  invented); render caps observed (Jev hugo math+mermaid, jev-figure
  HTML, EPUB pipeline; mermaid render path unverified → conditional
  proposals only). NOT reused as deciders: knowledge_state m2/m4/m7
  (no ingestion pipeline), metadata Writer contracts (shape ≠ book
  YAML), editorial/refine/revise/improvement (consumers, not inputs),
  mediated_read/evaluation_fabric (PUB-08), taste/statistics/qc/
  validation (advisory/governance/PUB-06-gate roles kept separate);
  no new `ai` primitive (D-PUB-40).
- Contracts: PD01–PD16 taxonomy with per-item support
  (deterministic PD04/07/12/14/15; structural PD02/03/09/10/13;
  adjudicated PD01/05/06/08/11/16; nothing wholly unsupported —
  D-PUB-41); preservation-before-planning (honest records + claim
  tiers + limitations + unresolved states; D-PUB-42); plan contract
  (identity/provenance, objectives, operations with span/refs/
  rationale/benefit/obligations/deps/validation/open-questions/
  approval, status lattice, freshness via `check_stale`; validator
  with 17 violation codes (14 from the start -- the "12" was a
  counting error -- plus span_anchor_mismatch,
  evidence_needs_mismatch and span_anchor_missing; D-PUB-43/D-PUB-49);
  ordinal priorities only
  (D-PUB-44); representation selection with pipeline caveats, dims as
  open questions, values never invented (D-PUB-45); materiality-scoped
  blocking (D-PUB-47); numeric-literal + already-structured guards
  (D-PUB-48, planner-side, PUB-02/04 contracts untouched).
- Calibration: 37 unit (`test_publication_pedagogy.py`) + 23
  calibration (10 dev + 12 held incl. 6 fresh once-only held-2 + counts;
  `publication_pedagogy_calibration.jsonl`; labels human/synthetic).
  Held discipline: first held pass exposed 3 implementation bugs +
  harness strictness (fixed without touching profile values, entries
  corrected transparently); fresh held-2 set evaluated once green on
  the frozen tree. Profile values never retuned. Fixtures pin planner
  behaviour; they are not comprehension proof (PUB-08 owns that).
- Live (read-only, Jev `c7aaad7`, fingerprint `435974701050…`):
  Ch1 → 46 ops (12 adjudication-ready incl. CAPSTONE-02B
  CONSOLIDATE, predicate-error SPLIT+SYNTHESIS, Willard-numbers TABLE
  candidate, Tam-block SPLITs; 17 evidence-blocked incl. closing
  TABLE/REORDER over the unresolved Jev-contract claim; 6
  context-blocked CONNECTs; 3 execution-ready KEEPs incl. results
  table + Limitations; 8 NO_CHANGE; 15 gated INVESTIGATEs),
  validates clean. Ch2 (0 cruft, well-written) → 48 ops, KEEP-heavy.
  Ch7 (dense research, CR07) → 53 ops incl. RELOCATE candidate +
  UPDATE_FROM_VERIFIED_EVIDENCE (superseded `run_ch07.py` pointer).
  Ch9 (staccato) → 61 ops, consolidation visible after the D-PUB-48
  guard (40 numeric-literal CX07 needs declined). Bounded book scan:
  36 chapters, 1398 structural ops (426 no_change / 329 KEEP /
  280 adjudication-ready / 251 evidence-blocked / 112
  context-blocked), all 36 plans validate. Structural candidates
  (no reconcile/intent) distinguished from adjudicated plans
  (Ch1/02/07 with reconcile+intent+context-limits).
- Regression (same invocation/CWD as PUB-01): cruft 46+40 +
  evidence 52+38 + legibility 17 + complexity 61+43 + pedagogy 37+23 +
  editing+quality 87 = 444 collected (443 passed, 1 strict xfailed
  held-cx15, PUB-04), 0 failed; capability short 1 passed +
  1 deselected (long corpus); `ruff check` clean on all touched files.
  (Counts are collected totals on this tree; evidence/complexity-
  calibration differ slightly from their stage-report numbers — those
  test files are untracked in writer git, so no diff was possible;
  PUB-05 touched none of them.) Catalog
  167; Jev + writer trees clean of strays (only pre-existing
  untracked `scripts/` + owning-team flux in `docs/cli` and writer
  root, untouched); zero dispatches; $0 verification spend.

### PUB-05 fix batch (2026-11-24; Muse implementation, addresses the Codex
CONDITIONAL residuals + the DeepSeek record-number correction;
pending Codex + DeepSeek delta re-review)

- Validator authority (D-PUB-49, code + pins in
  `test_publication_pedagogy.py`): every operation target carries an
  `anchor_sha256` content anchor -- a KEEP retargeted to a different
  in-range span fails `span_anchor_mismatch` (bounds-only
  `span_out_of_range` still passes, pin asserts both); preservation
  coverage is enforced on attached `preservation_obligations`
  (overlap + attachment, non-located claim-tier items on every op), so
  stripped obligations fail `preservation_gap`; the execution-ready
  verdict reconciles `need_refs`/`reconcile_refs`/`blocking` instead of
  trusting the mutable `evidence_needed` field, and any
  `evidence_needed` skew vs refs/blockers fails
  `evidence_needs_mismatch`. Freshness binds reconcile *states*,
  intent *contents*, reader-context *values* and effective render-cap
  *values* (`reconcile_states_changed` / `intent_changed` /
  `reader_context_changed` / `render_caps_changed`), not just finding
  IDs + inventory rev. Validator codes: 16 (14 actual + 2 new; the
  pre-fix "12" was a counting error, code set kept).
- One-primary honesty (D-PUB-50, pin
  `test_cx13_reorder_is_investigation_only_never_primary`): CX13
  REORDER carries `investigation_only: True`, is never a primary and is
  forced to `candidate` status, so PUB-06 cannot consume it as a second
  transformation. The numeric-literal guard stays a planner-side
  heuristic with documented scope (`_is_numeric_literal` docstring +
  pedag README limits; PUB-02/04 contracts untouched).
- Correction path (D-PUB-51, pins incl. the reproduced case):
  UPDATE_FROM_VERIFIED_EVIDENCE requires a linked PUB-03 correction
  proposal *with* evidence linkage, else evidence-gated
  INVESTIGATE_EVIDENCE (`reconcile:superseded-without-correction`) --
  a superseded result_claim with no correction payload emits no UPDATE.
  Grouping retains `correction` + `evidence_refs` + `provenance`
  (previously dropped); the UPDATE op carries the payload. The
  D-PUB-47 read-only exemption is honoured: conflicted/contradicted
  evidence no longer blocks non-mutating INVESTIGATE_EVIDENCE (pin:
  CX07-term investigation on a conflicted span stays unblocked while
  the same-span mutating op stays blocked).
- Live re-verification (read-only, Jev `c7aaad7`, fingerprint
  `435974701050…`, chapter-scoped reconcile + intent, no reader
  context, default render caps; exact invocations in STATE §3):
  reconcile inputs confirmed chapter-scoped (Ch1 35 claims
  22/7/4/2/0 corr 2 @ `jev@bbbb73b55d7668a8`; Ch2 14 claims 7/4/2/0/1
  corr 1 @ `jev@899c02ad76215729`; Ch7 28 claims 22/4/1/1/0 corr 1 @
  `jev@a6cd2b879ef9ae6a` incl. the superseded `run_ch07.py` pointer
  WITH correction + evidence refs, so the UPDATE stands; Ch9 16
  claims 8/0/7/0/1 corr 1 @ `jev@d3c457a3af1aa23b`). Plans, all four
  validating clean:
  | chapter | record | DeepSeek | actual (this tree) |
  |---|---|---|---|
  | Ch1 (status split adj/evid/ctx/no-change/exec) | 46 (12/17/6/8/3) | 46 (11/17/6/9/3) | 46 (11/17/6/9/3) -- DeepSeek confirmed |
  | Ch2 | 48 | 46 | 46 -- DeepSeek confirmed |
  | Ch7 | 53 | 49 | 49 (incl. UPDATE_FROM_VERIFIED_EVIDENCE) -- DeepSeek confirmed |
  | Ch9 | 61 | 62 | 62 -- DeepSeek confirmed |
  No count differs from both record and DeepSeek; every actual matches
  DeepSeek, so the pre-fix record was hand-tallied wrong in all four
  cases (Ch1 additionally mis-split 12/8 vs 11/9). Bounded book scan:
  36 chapters, 1398 structural ops -- aggregate EXACT, leave as is;
  mix is 426 no_change / 329 execution_ready (KEEP) / 249
  adjudication-ready / 251 evidence-blocked / 112 context-blocked /
  31 candidate (249+31 = the old 280: exactly the 31 investigation-only
  CX13 REORDERs moved out of adjudication-ready by D-PUB-50, the only
  behavioural delta on live corpora). All 36 + 4 chapter plans
  validate, 0 violations.
- CLI docs: `docs/cli/INDEX.md` hand-updated to the live tree (58
  rows: pedag + 6 missing rows; artifact 22, info 13, metadata 25,
  mri 8 corrected; total nodes 789→855). No generator run (the script
  rewrites the owning team's active work area unconditionally; the
  batch-2 collision boundary stands). Coverage now 3 passed / 1
  failed: the single failure is `test_every_registered_command_has_docs`
  with exactly the 5 pre-existing owning-team gaps
  (`book-campaign`, `strategy-evolution`, `quality`,
  `validate-site-links`, `reader-legibility`) -- recorded, NOT fixed
  here. No orphan docs.
- Suites: pedagogy 50 unit (37 + 13 new pins) + 23 calibration = 73
  green; combined neighbours 457 collected (456 passed + 1 strict
  xfailed held-cx15, PUB-04) -- cruft 46+40, evidence 52+38,
  legibility 17, complexity 61+43, pedagogy 50+23, editing+quality 87;
  capability short 1 passed + 1 deselected (long corpus);
  `ruff check` clean on all touched files (`ruff format` drift is
  file-wide pre-existing, not reformatted per stage convention).
  Catalog 167; fingerprint `435974701050…` unchanged; Jev clean
  (pre-existing `scripts/` only); zero dispatches; $0; no commits.
- Held-evaluation limitation (kept candid, no action beyond wording):
  the 12 held entries are synthetic, 6 of them fresh once-only
  (held-2); they pin planner behaviour, never reader comprehension,
  and the profile stays UNCALIBRATED -- 6 synthetic held-2 cases do
  not generalise, and no promotion gate may read them as validation
  (PUB-08 owns that with human data).

### PUB-06 (2026-11-24; Muse implementation + coordinator close-out;
verified in-session, awaiting author verdict)

- Transformation boundary implemented deterministic-first, zero model
  dispatches: `packages/writer-core/writer_core/analysis/publication_transformation.py`
  (`publication-transformation-v0.1`, profile `transform-v0.1`,
  `calibrated=False`, `EVIDENCE_LABEL=MEASURED_TEXT`); CLI `writer
  transform check|package|verify|surgical`
  (`writer_cli/commands/transform.py` + `main.py` registration;
  `docs/cli/transform/README.md` + INDEX row → 59). Library+CLI surface
  like `reader_legibility` itself — deliberately NOT a registered
  runtime, so no catalog manifest is warranted (consistent with
  D-PUB-10/11/24/39); catalog stays 167, scoped validation unchanged.
- Reuse honoured, nothing forked: plan shape + `validate_plan` +
  `check_stale` + anchor semantics reused from `publication_pedagogy`
  (boundary re-runs the PUB-05 validator: validity != execution
  validity); spans/roles from `reader_legibility`; PUB-02 reports +
  preservation, PUB-03 states, PUB-04 reports consumed as JSON;
  `typed_task` seam shape mirrored for prepared-never-dispatched
  adjudication payloads (zero dispatches in PUB-06); `qc` +
  `manuscript_ir` gate roles, VFS/Workbench boundaries referenced, not
  reimplemented (U1 settlement D-PUB-53).
- Hard rules in code: blocking vs isolating violations (stale
  fingerprint/evidence/anchors/unknown-type/validator-reject/conflict
  block the plan; investigation-only + evidence-held isolate single
  ops); REORDER never consumed (D-PUB-50); same-span mutating conflict
  held; mutating-op unresolved overlap held per-claim (D-PUB-47 at the
  boundary); byte-true verification at ordered-line-subsequence level
  (re-paragraphing passes, rewording fails; empty spans vacuous;
  duplicates deduped); anti-gaming verdict (counts-down + preservation
  failure = fail); `request_application` returns `fixture_only` at best
  (approval + QC + freshness required; no production path); surgical
  edits exact-unique + overlap-refused + long fences.
- Tests: 65 unit (`tests/core/test_publication_transformation.py`:
  consumption valid/malformed/stale/conflicting, grouping,
  no-change respect, blocked isolation, preservation incl.
  score-gaming rejection, reword-vs-reparagraph pins, placement proofs,
  unresolved-independent, new-sentence honesty, candidacy, QC/downstream
  binding, freshness unconditional, digest/states required, adjudication
  binding, preservation auth, dependency order/cycles, vocab aliases,
  surgical exactness incl. real-applier short-substring refusal,
  staged design-only, hash-chain, approval enforcement, fixture
  apply/undo, visuals, seam; plus 5 fail-closed pins: either-provenance-
  missing, no-fallback candidate fp, non-executable boundary isolation,
  unbound adjudication, missing record fingerprints) — all green.
- Live demonstration (read-only + derived artifacts only, Jev
  `c7aaad7`): Ch1 plan revalidated executable (44 boundary_ok + 1
  evidence_held + 1 investigation-only REORDER) with live states/digest
  and bound adjudications (17 records upgraded with `adjudicated_by`/
  `at`/`plan_id`/`source_fingerprint`); 7 work packages / 17 isolated /
  12 respected (blocked derived, never False by default); revised Ch1
  candidate (604 lines, fp `bb95457e…`, post-polish R1/R2/R5) verified pass 21/21 (cruft 1→1
  with CR04 retained, 11→12 preserved; complexity 38→35, CX14 8→6 all
  LOW, CX11 5→3, CX05 2→3 honest-text residual, CX10 1→1, max severity
  never rises; new-sentence honesty passes); Figure 1.2 SVG (per-lane
  honesty, naive-index qualifier, four-lane desc) + Willard table
  spec-validated; diff 178 lines; before-after (concurrs with Claude
  P1/P2/P4/P5/P8 + Codex Tam/per-lane) + provenance record with
  hash-chain (`package_hashes`, `packages_digest`, before/after
  retained, after == candidate asserted;
  `writer.transform.record.v1`, model identity CONFLICTED for review).
  Bounded passages P-07 (Ch7 superseded pointer annotated, no inferred
  replacement, dependent L556 held) + P-09 (Ch9 staccato→2 sentences,
  CX10-high+CX11-med → CX03-med residual with rationale).
- Fixture gate (ACCEPTANCE PUB-06): real `apply_edits.py` on disposable
  copies — `--diff` 2/2 inline-exact ratio 1.000, `--apply` fingerprint
  proof (`441a5111…`→`7576d75f…`), pristine-copy undo byte-identical,
  ambiguous Current Text refused (SKIP, no match), short-substring
  (<24 chars) refused block-or-refuse (real-applier SKIP, engine
  refused; 0.978-style fuzzy short text never spliced).
- Regression (same invocation/CWD as PUB-01): transformation 60 +
  cruft/cruft-calibration/complexity/complexity-calibration/pedagogy/
  legibility 259 collected (258 passed + 1 strict xfail held-cx15,
  PUB-04) = 319 collected (318 passed + 1 strict xfail), 0 failed.
  Catalog 167; Jev tree verified clean (pre-existing `scripts/` only);
  authoritative manuscript + evidence unchanged; zero Worker dispatches
  on the engine path; editorial generation spend recorded separately
  (muse-spark-1.3, opencode-session, unmetered-session, $0); no
  commits/pushes.
- Held-evaluation limitation (kept candid): no calibration suite for
  the boundary (pins are behavioural, not threshold); profile
  UNCALIBRATED; comprehension probe specified but not executed
  (model-reader ≠ human proof; PUB-08 owns human calibration);
  new-sentence honesty is a first deterministic layer only.

### PUB-06 fix batch 2 (2026-11-24; Muse implementation, addresses the
Codex delta-confirm REJECT 3 trust-root blockers; pending Codex delta
re-confirm + DeepSeek delta re-verify)

- Boundary authentication (D-PUB-65): `compile_work_packages` always
  revalidates internally against plan + chapter bytes + threaded live
  inputs; caller-supplied boundaries are advisory (fail-closed
  conjunction: executable only when both agree, violations union,
  verdicts worst-rank, `supplied_boundary_mismatch` isolating note on
  `binding_digest` mismatch). CLI `check|package` thread identical
  live inputs through revalidate and compile. New pins:
  forged-executable boundary over a stale plan and over a same-span
  conflict both compile zero packages; a matching supplied boundary
  authenticates cleanly.
- States coverage (D-PUB-66): claim-shaped mutating-op refs must each
  be present in the live states map (empty/incomplete map with
  referenced claims blocks); dict-form bound freshness reaches
  list-form parity; `_restrict_unresolved` fail-closed on missing
  coverage. New pins: `states={}`, incomplete map, dict-bound claim
  absent from live.
- Live preservation rehydration (D-PUB-67): boundary re-runs cruft +
  complexity on the live bytes; live preserved spans overlapped by
  compilable mutating ops must be plan-covered and unsettled
  referenced claims must be obligation-carried, else blocking
  `preservation_auth_failed`. New pins: plan+op span strip and
  plan+op claim strip both refused; honest obligation passes.
  4 pre-existing fixtures re-pinned honest (claim obligations where
  unsettled refs are held/promoted).
- CLI contract pinned by runner (2 tests): stale plan packages exit 1,
  executable plan exits 0.
- Suites: transformation 76 + 2 CLI (base 60 + 5 close-out gates + 9
  fix-batch-2 pins + 1 chain-content pin + 1 chain-stability pin);
  neighbours 260 + 1 strict xfail (held-cx15; 258 + 2 cross-table
  pins) unchanged otherwise; ruff clean.
  Live (Jev `c7aaad7`): cruft 1/11/9 fp `43597470…`, complex 38,
  pedag Ch1 46 (11/17/6/9/3) validates, boundary executable
  (44 boundary_ok + 1 evidence_held + 1 investigation-only, binding
  `ae883922…`), packages 7/17/12 authenticated, verify pass 21/21.
  Catalog 167; Jev clean; zero engine dispatches; $0;
  no commits/pushes.
- Coordinator close-out (D-PUB-64 fail-closed gates + D-PUB-68 record
  chain + R1/R2 prose & SVG fixes, rebuilt record + before-after,
  $0): candidate `f6c1cbf4…` 606 lines; verify 21/21 pass on final
  bytes; chain rebuilt via the builder (after == candidate asserted).
  Final candidate complexity: 38→39 (CX02 8→9, CX05 2→4, CX11 5→4,
  CX13 1→2, CX14 8→6, CX10 1→1 -- the mid-programme CX10 HIGH was a
  cross-table false-positive join, removed by the PUB-04
  structural-break fix and verified gone). Before-after updated to
  the final bytes (supersedes the 38→35 and interim 38→40+HIGH
  numbers); `diff.txt` predates the polish edits (deltas listed
  verbatim). R5 lane-3 alt-text change REVERTED (SVG desc was already
  correct); stub-row dashes reverted (byte-true preservation wins;
  author/PUB-10 to decide).

### PUB-07 (2026-11-25; Muse implementation, pending review gate)

- Production-path editorial automation implemented, zero new gateways:
  `packages/writer-core/writer_core/analysis/publication_automation.py`
  (`publication-automation-v0.1`, profile `automation-v0.1`
  UNCALIBRATED) + `writer transform automate` CLI subcommand (existing
  group, no new runtime/CLI group; catalog stays 167). Wiring: Writer
  owns prompts + `EditorialCandidateResponse` /
  `EditorialReviewResponse` contracts; `run_typed_task` seam (one call,
  no retry/repair) -> Writer `models.run` -> Worker `POST /v1/work`
  (opencode-work executor) -> pi provider (subscription). writer-core
  stays dependency-light (dispatch callable injected; `writer_runtime`
  import pinned absent by test).
- Contracts: one dispatch per package (D-PUB-76); quote discipline
  (off-passage quotes fail, reported never repaired); deterministic
  assembly with per-line origin lineage (source vs dispatch execution
  id); bounded correction loop (editorial <= max+1, review <= 2,
  total <= 5; explicit termination incl. repeat-failure and
  dispatch-failed-twice halts); spend hard cap ($10) fail-closed;
  review on an independent family (deepseek-go generate, haiku-go
  review).
- Record extension (D-PUB-77, additive): optional `dispatch_ledger`
  (`writer.automation.ledger.v1`: per-dispatch model/provider/route/
  usage/cost, editorial-vs-verification split) + `config.
  model_dispatches` count; schema stays `writer.transform.record.v1`,
  chain untouched, PUB-06 zero-dispatch pin still green.
- Workbench bridge (`src/workbench/publication_proposals.py`, D-PUB-78):
  candidate JSON -> pending Proposal data with span binding
  (lines + span sha + chapter fingerprint), `check_proposal_fresh`
  stale checks, QC-gate evidence + dispatch provenance in the
  editorial handoff; refuses empty/failed-unverified/unprovenanced
  proposals; accept/undo never invoked (pinned).
- Tests: 19 automation unit (fakes, zero live calls) + 5 transform CLI
  pins (incl. 3 new automate dry-run/refusal pins) + 10 workbench
  bridge tests; full fast gate 560 passed + 1 strict xfailed
  (held-cx15, PUB-04) / 0 failed; ruff clean.
- Live end-to-end demo (Jev Ch2, `c7aaad7`, KEEP-heavy safety
  rationale): plan revalidated executable (44 boundary_ok + 2 isolating
  REORDERs), packages compiled (10; 8 passage + chapter frame +
  surgical), single bounded package executed
  (`passage:Nine older mechanisms...`, ops 006 SPLIT + 007 SYNTHESIS,
  lines 133-146). 4 dispatches, $0.00706, 25,504 tokens: editorial x2
  (deepseek-go, $0.00470 + $0.00236), review x2 (haiku-go, $0.00
  subscription allowance; provider-reported input_tokens=4 vs total
  5262 flagged verbatim). Candidate 338 lines (346 -> 338, single
  region 133-146 -> 6 lines), verify 15/15 pass, chain-verified
  fingerprint `50e1ef2e…`. Correction loop terminated honestly:
  verify-pass -> review request_changes (LLM2Jev overstatement, twice
  raised) -> single review-driven correction -> re-verify pass ->
  final review request_changes + quote failure (verdict invalid,
  rationale preserved). Presented `pending_author_decision`
  (pub07/ch02/approval-decision.json), NOT auto-approved/applied.
  Fixture gate: real `apply_edits.py` on disposable copy (diff 1/1
  ratio-1.000, apply fp `34E7…`->`8047…`, bytes == candidate,
  pristine-restore byte-identical). Workbench proposal
  `pub07-ch02-p001` pending + fresh. Staged change-set design-only.
  Zero authoritative mutation (Jev `c7aaad7` clean; Worker + Writer
  state untouched outside their own stores).

- PUB-07 fix batch (D-PUB-81, 2026-11-25; code + pins + docs) +
  coordinator close-out (+9 pins): review excerpt scoped to the replacement
  lineage range (Fix A); candidate + lineage rebound after correction
  with excerpt-exact review validation (Fix B); pre-dispatch spend
  guard with projection + explicit override bookkeeping in ledger +
  record config (Fix C); ledger `replacement_sha256` rows + record
  `chain.ledger_digest` + bridge refusal of unbound ledgers +
  replacement-hash freshness + proposal record-chain reference
  (Fix D); paragraph-break assembly + no-gloss/no-section-citation
  prompt discipline (Fix E); LF + slash canonical digest forms shared
  by Writer and Workbench with a pinned cross-compat vector, ledger
  digest stripping per-row `latency_ms` (Fix G); per-round review-state
  binding revalidation failing closed with `halted_stale_binding` on
  mismatch (Fix B hardening, 3 pins) + Ch2-shape paragraph-assembly pin
  (Fix E). Per-file collected on the settled tree: transformation 83 +
  CLI 9 + automation 40 (= 132 combined passed); full delta gate 593
  collected (592 passed + 1 strict xfailed held-cx15) / 0 failed —
  supersedes the 584/583 fix-batch-time count; workbench
  neighbours 35/0; ruff clean. Run-1 artifacts preserved verbatim in
  `pub07/ch02-superseded-run1/` with the stale-window /
  spurious-quote-failure analysis; Fix F annotations land on the
  re-run's records (not by editing history). Bounded re-run EXECUTED
  by the coordinator in a credential-bearing shell (the 08:48 UTC temp-dir
  attempt was Worker-BLOCKED on opencode-go auth, authentication_failed,
  non-retryable, $0): outcome review_accepted, 2 dispatches $0.0039864
  (editorial deepseek-v4.1-flash 8246 tok + review haiku $0/5678 tok,
  13,924 tok total), spend cap $10 enforced pre-dispatch
  (override_explicit false), verify 15/15 pass, candidate `9f36c9ba…`
  (355 lines, 20,239 bytes, LF, chain after==candidate asserted;
  `pub07/ch02-rerun/`; `pub07/ch02/` on disk still holds the run-1
  bytes `50e1ef2e…` 338 lines pending the author's promotion decision).