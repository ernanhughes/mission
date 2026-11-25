# PUBLICATION Decisions

Material decisions with rationale. Proposed-but-unaccepted items stay marked;
silence is not policy.

## Accepted (this programme unless noted)

- **D-PUB-01 — Build on READABILITY-ASSURANCE-01, don't relitigate.**
  Ownership map, ADR-001…004/006 (accepted) and the Stage-0 reconciliation are
  adopted as the starting boundary. Rationale: verified against implementation
  2026-11-16; PUBLICATION's novelty is cruft/reconciliation/pedagogy/
  transformation/orchestration, not re-deciding mechanical readability.
- **D-PUB-02 — Writer owns diagnosis; Workbench owns mutation; Mission displays.**
  Rationale: proven stores and paths exist in each; any consolidation needs a
  stage-gated proposal, not drift.
- **D-PUB-03 — Catalog is advisory until reconciled.**
  `build_catalog()` verified at 165 runtimes, but 8 directly relevant domains are
  absent from it. Rationale: observed gap; designing from the catalog alone
  already misled once (STAGE0 C1 pattern).
- **D-PUB-04 — Deterministic signals before model judgement; calibration before
  thresholds.** Rationale: `editing` and `reader_legibility` prove deterministic
  value; uncalibrated model scores caused the exact blindness this programme
  exists to fix.
- **D-PUB-05 — Jev Ch1 honesty is the house standard, not a defect.**
  Explicit NOT_OBSERVED + untested-prediction framing preserved through
  enhancement. Rationale: evidence reconciliation (27 predicate-only rows)
  confirms the manuscript; deleting such candour would destroy the ledger's
  value.
- **D-PUB-06 — Docs live here; implementation docs stay in owning repos.**
  `docs/programmes/publication/` holds 7 canonical files only (README,
  ARCHITECTURE, CAPABILITIES, ROADMAP, STATE, ACCEPTANCE, DECISIONS). No
  `programmes/` convention existed (tracks use per-track folders; milestones use
  `docs/milestones/`). Rationale: brief §17 + consolidation rule.

## Inherited as proposed (not re-decided here; owners pending)

- ADR-005 staged Apply; ADR-007 Mission surface extension; ADR-008 ledger
  projection; ADR-009 companion report; ADR-010 evidence labels/gates; D3
  campaign consolidation; U1–U5 ownership gaps (ARCHITECTURE.md §2).

## PUB-01 decisions (executed 2026-11-24)

- **D-PUB-07 — `runtime.quality` stays CLI-only in PUB-01; registration is
  deferred with an unblock plan (U2 stays open).** Rationale: the domain ships
  a real engine (`deterministic`/`direct`/`bounded_judge`), campaign service,
  `portable-v1` DTOs, a 7-command CLI and tests — but has no facade, no
  `create_quality_domain` factory, and no capability adapter anywhere in the
  repo. Registering a runtime around a nonexistent facade would advertise a
  surface that does not exist. The current cross-system seam already works:
  Mission `api/quality.py` shells to `python -m writer_cli.main quality
  evaluate …` (transport `writer-cli`, exit-code contract, JSON envelope) when
  `MISSION_CONTROL_WRITER_QUALITY_RUNNER` is set. Unblock plan: PUB-02 designs
  the facade (findings, campaign status, `reader_study`); PUB-07 builds the
  in-process/HTTP surface and wires the Workbench bridge read-only first;
  PUB-09 migrates the Mission lane (ADR-003). U2/U3/U4 remain open with owners
  (Writer quality + Mission), not silently closed.
- **D-PUB-08 — Model routing reuses Writer `runtime.models` via Worker; no new
  gateway.** Rationale: `runtime.models` is the sole model-execution owner
  (`execution_owner=worker`, verified live 2026-11-24); domains call one
  bounded operation through `models.typed_task.run_typed_task` (one Worker
  call, no domain-level retry/repair of invalid typed output (infrastructure POST retry may occur below the seam), JSON schema passed to Worker and validated by Writer via Pydantic, failures
  reported never repaired, usage/cost passed through); Worker serves
  `POST /v1/work` (`src/server/server.ts`) with `opencode`/`opencode-work`/
  `model` executors. Contract: Writer owns prompts + Pydantic contracts;
  Worker owns providers, transport, retry, cost; the seam owns nothing
  domain-specific. Evidence: 8 contract-draft calls / $0.076499 via route
  `default_deepseek_go` (baseline-health §4.2). PUB-02/04 model use goes
  through this seam or stays deterministic; no paid experimental runs in PUB-01.
- **D-PUB-09 — Registry reconciliation describes the architecture; it does not
  dictate one.** `editing` + `mediated_read` manifests added (both registered
  runtimes); `quality` deliberately unregistered (D-PUB-07); `reader_legibility`
  stays a library+CLI surface; `self_repair`/`book_campaign` stay services of
  `artifact`; `evaluation_fabric` stays an orchestration service;
  `refinement` investigated and not registered (stub-defaulted, zero callers —
  distinct from the registered `refine` human-review domain). Remaining
  catalog↔registry gaps (`metadata_generation`, 46 orphans, `analysis_state`
  adapter) are recorded as Writer-owned backlog in CAPABILITIES.md §8, not
  fixed here: unrelated refactoring is out of PUB-01 scope.

## PUB-02 decisions (executed 2026-11-24)

- **D-PUB-10 — Cruft classifier lives in writer-core analysis + CLI; not a
  runtime domain; model seam prepared, never dispatched.** Rationale: the
  CR01–CR12 classifier composes `reader_legibility` (spans, roles),
  `artifact` (debris shapes), `evidence` (claim↔result bindings) and
  `argument` (contradiction discipline) without owning any of them, exactly
  like `reader_legibility` itself — registering a runtime around a
  stateless deterministic function would advertise a surface that does not
  need to exist (same reasoning as D-PUB-07/09: no manifest warranted, no
  catalog change). Model-backed judgement is confined to three marked
  candidates (CR07 reader-usefulness, CR08 obscures-vs-caution, CR11
  contradiction-vs-contrast) via `prepare_typed_task` payloads dispatched
  ONLY through `models.typed_task.run_typed_task` (D-PUB-08); PUB-02
  performs zero dispatches because deterministic signals sufficed for the
  calibration pairs. Thresholds (`cruft-v0.1`) are versioned and explicitly
  uncalibrated; held-out discipline (evaluate once, never tune) is enforced
  by the calibration suite.

## PUB-03 decisions (recorded 2026-11-24 before implementation; Muse design)

- **D-PUB-11 — Reconciliation lives in writer-core analysis + CLI; not a
  runtime domain; zero model dispatches.** Same reasoning as D-PUB-10: the
  reconciler composes `reader_legibility` spans, `publication_cruft`
  `EvidenceIndex`/NEEDS_EVIDENCE, `argument.disagreement` cue discipline
  and book-side evidence without owning any of them.
- **D-PUB-12 — Reuse verdicts (inspected callable interfaces, not
  descriptions).** Reused: `reader_legibility` spans + `EvidenceRole`;
  PUB-02 `EvidenceIndex` (optional-field extension only) and the
  NEEDS_EVIDENCE pattern; `argument.disagreement` cue-then-silence
  principle (conceptual alignment only — PUB-03 imports nothing from
  that module; fix batch 2026-11-24);
  evidence `SupportLabel`/`FreshnessStatus`/ABSTAIN conventions (mapping
  documented). NOT reused: evidence lexical extractor/verifier,
  `quality.evaluate`, `manuscript_ir`, `findings`, `repo`, `editing`,
  no new `ai` primitive; Mission Control has no per-chapter experiment
  inventory, so book-side ledger/results/prereg is authoritative.
- **D-PUB-13 — New `ReconciliationState` enum (8 states).** Evidence
  `SupportLabel` is span-verification; reconciliation state is
  claim-to-authoritative-repo-evidence correspondence — a distinct
  concern. State, cruft severity and lifecycle position stay separate.
- **D-PUB-14 — Preservation is conditional on current evidence, never
  permanent immunity.** `evaluate_preservation()` re-checks preserved
  passages against the current inventory; new authoritative completion
  evidence makes an honesty statement correction-eligible, never
  silently un-preserved and never immune.
- **D-PUB-15 — Evidence authority ranking (policy, in code).** Validated
  execution record > raw complete row > partial row > author report as
  lead > absent. Later is not authoritative without an explicit
  supersede record; larger is not replacement; passing test is not
  hypothesis established.
- **D-PUB-16 — Bounded, reproducible Jev inventory.** Explicit roots
  only; no unrestricted recursive ingestion; every entry carries
  identity, kind, repo, revision, path, digest, experiment, conditions,
  execution metadata, schema class, parse/validation status, limits.
- **D-PUB-17 — Jev demo chapters: 01 + 02 + 36.** Ch1 mandatory (7
  PUB-02 NEEDS_EVIDENCE). Ch2: supported + partial. Ch36: superseding
  impls + mock rows. Ch8/Ch28 are discovery sources only. Coverage
  reported as partial, never full.
- **D-PUB-18 — PUB-02 integration is consumptive, not mutative.**
  `reconcile resolve` consumes cruft-report JSON plus an inventory
  revision; PUB-02 contracts change only by optional fields.

- **D-PUB-19 — The Jev adapter executes the repo's own no-model
  selftests as read-only evidence inspection.** Counting executed checks
  by running `examples/<ch>*/selftest*.py` (bounded 120 s, output parsed
  for `ok` lines, tree verified clean afterwards) is inspection in the
  same class as running `writer cruft review`: the selftests' own
  docstrings state they need no model and no network, and they recompute
  the figures the prose quotes. Static call-site counts (52 sites vs 53
  executions in Ch1) are recorded for contrast but never used as a
  verdict basis — static analysis of check counts is not the runtime
  count, and "correcting" 53 to 52 off static analysis would fabricate a
  contradiction against a true claim. Execution failure returns None
  (explicit, never a silent zero). No other repo code is executed; no
  Mission execution path is created.
- **D-PUB-20 — Binding precision: numbers and containers never bind by
  themselves.** A matching number is not proof (values bind rows only
  with experiment/arm/path/chapter linkage; dates/hashes/prose blobs can
  never manufacture agreement — exact JSON numerics only, time units
  normalised). Citing a container (ledger.md, prereg file) never binds
  its rows (chapter/experiment linkage only). Backticked language
  literals (`None`), split names (`test`) and file paths never bind as
  arm names. File-holding counts ("6001 rows in results/ch07.jsonl")
  check the inventoried file count, never per-row scalars. Each rule was
  added only after the live Jev run produced the corresponding false
  bind/contradiction, which was then fixed and pinned by a regression
  test.

## PUB-03 fix batch (executed 2026-11-24; Muse implementation, addresses
the Codex BLOCKED 5 points + the DeepSeek carry-forward, pending Codex +
DeepSeek delta re-review)

- **D-PUB-21 — Chapter-scope rule for arm-identified binding.** A claim
  is by default a statement about its own chapter's evidence: when no
  experiment is named, a named arm binds completion rows only within the
  claim's chapter (a Ch2 row never supersedes a Ch1 claim on arm
  identity alone). Cross-chapter completion needs either (a) an explicit
  cross-chapter reference in the claim (another chapter's results file
  cited, or a "chapter N"/"Ch N" mention naming another chapter) or
  (b) a globally unique experiment identity (the row's experiment
  occurs under at most one chapter in the inventory). Explicit
  experiment or artifact identity always binds globally. Stated in code
  (`evidence_reconciliation._in_scope` + `_completion_rows` docstrings)
  and pinned by 7 regression tests (adjudication + preservation, incl.
  positive controls for same-chapter, explicit-reference and
  unique-experiment binding).
- **D-PUB-22 — Selftest execution hardening (amends D-PUB-19).**
  Execution stays read-only inspection, now bounded by construction:
  (1) a validated explicit script set — the example directory is listed
  (no dynamic glob) and every candidate must match the selftest name
  shape, resolve inside the book tree, be a regular file within the size
  bound, else it is skipped with an explicit note; (2) a total
  inventory deadline (300 s) in addition to the per-script 120 s cap —
  scripts past the budget are skipped explicitly and bind nothing;
  (3) a post-run clean-tree verification (`git status --porcelain`
  tracked paths before/after) recorded in the inventory notes — any new
  modification is reported, never silent. Permissions remain the
  invoking user's, so the check — not a sandbox — is the boundary, and
  the notes are the evidence. Ch1/Ch2/Ch7 executed counts (53/27/87)
  stay green.

## PUB-03 fix batch 2 (executed 2026-11-24; Muse implementation, applies
the Codex delta re-review's 2 residuals post-acceptance — see STATE §9;
no new review cycle required)

- **D-PUB-23 — No inventory-time execution of repo scripts (supersedes
  D-PUB-19, retires D-PUB-22).** Validated-set and time-budget bounds do
  not make execution read-only (caller permissions, untracked writes, no
  containment), so the inventory stops executing selftests entirely:
  runtime counts are reported as an explicitly unavailable named state
  (`execution.runtime="unavailable"` + pure-parsing `static_sites` count
  + `runtime_unavailable` validation note + inventory note), never
  silently omitted, never success. The reconciler short-circuits genuine
  selftest-count claims (names a selftest script and states its check
  count) to UNRESOLVED with an explicit D-PUB-23 rationale — never
  supported off static call-site counts, never contradicted off rows that
  cannot speak to the unexecuted count — and unavailable markers explain
  no numbers (`_explained_numbers` skips them). Static call-site counts
  (Ch1/Ch2/Ch7: 52/17/73, pure parsing) are kept and bind nothing.
  Rationale: removing the execution path removes the whole class of
  sandbox/containment objections; a sandboxed re-execution that would
  restore verified runtime counts is deferred as future work, and no new
  execution mechanism (no opt-in flag, no runner) is created here.
- README count fix (no new decision number): `C:\Projects\writer\README.md`
  top-level command count 48 → 50, exactly as specified. NOTE (final
  state, tree in flux, recorded not fixed): the owning team landed a new
  `complex` command mid-session (documented) and hand-edited INDEX.md
  (49 rows incl. reconcile + cruft + complex, stale 48 total vs a
  57-command live tree). Coverage: 1 passed / 3 failed — missing docs are
  the 5 batch-era gaps only; reconcile + cruft rows and README dirs
  (batch outputs) remain present. `docs/cli` is the owning team's active
  work area — left alone after two in-session generator runs demonstrably
  collided with their concurrent edits.
- Reuse honesty (no new decision number): the
  `argument.disagreement` lineage is now stated as conceptual, not a
  code dependency, in the module docstring, in
  `EvidenceReconciler._find_conflict`'s docstring, and in D-PUB-12
  above. No fake reuse: PUB-03 imports nothing from that module.
- CLI `reconcile resolve` envelope validation: the unwrapped `result`
  shape is validated inside read-error handling
  (`_unwrap_cruft_report`) — a null/missing/misshapen result is a clean
  exit-1 rejection (JSON envelope `ok:false` under `--json`), never a
  traceback-out. Pinned by 2 regression tests.
- CLI docs: `docs/cli/reconcile/README.md` + `docs/cli/cruft/README.md`
  added; `INDEX.md` +1 row each (total 48→50). The 5 remaining missing
  docs (`book-campaign`, `quality`, `reader-legibility`,
  `strategy-evolution`, `validate-site-links`) are pre-existing
  owning-team backlog — recorded, not fixed here.
- `ReconciliationState` docstring completed: SupportLabel members
  without a counterpart (`not_supported`, `needs_multiple_spans`,
  `out_of_scope`), no direct `conflicted` counterpart, and
  `Binding.check_stale` returns change triggers, never a
  `FreshnessStatus` value (freshness computed on demand, never
  serialized).

## PUB-04 decisions (recorded 2026-11-24 before implementation; Muse design)

- **D-PUB-24 — Complexity screening lives in writer-core analysis + CLI;
  not a runtime domain; zero model dispatches.** Same reasoning as
  D-PUB-10/11: the CX01–CX15 screen composes `reader_legibility` spans,
  editing heuristics and PUB-02 preservation discipline without owning
  any of them. `writer complex review|scan|compare` is the surface;
  no catalog manifest warranted (catalog stays 167). Correction to the
  concurrent-session note above: the final in-stage state is INDEX 51
  rows (complex + cruft + reconcile rows present), `docs/cli/complex/
  README.md` hand-written by this stage, and the five stray
  generator-created doc dirs removed — `docs/cli` otherwise untouched.
- **D-PUB-25 — Reuse verdicts (inspected callable interfaces, not
  descriptions).** Reused: `reader_legibility` spans + `EvidenceRole`;
  editing sentence/word heuristics (mirrored locally — writer-core
  takes no `writer_runtime` import); PUB-02 honest-record sections,
  preservation ordering and NEEDS-style reporting (here NEEDS_CONTEXT
  for terminology without a registry); `argument` cue-then-silence
  discipline (conceptual only, nothing imported). NOT reused as
  deciders: `manuscript_ir` roles/semantics, `statistics` features,
  `compiler`/`knowledge_state` registries, `taste`/`editorial`/
  `editorial_intelligence` judgments — Level B screens use local
  proxies explicitly marked approximate; grounding them is PUB-08 work.
- **D-PUB-26 — No composite, no universal score; max-severity lens.**
  Findings carry severity + kind but the report never aggregates them
  into a score (ARCHITECTURE.md rule 5). `compare` reports count deltas
  AND max severity precisely so a staccato rewrite (fewer findings, new
  high-severity CX10) cannot "win" on count alone. The mandatory
  regression pins rewrite ordering (staccato ≥ clearer, clearer <
  original), never a number.
- **D-PUB-27 — CX15 is candidate-only; restructuring is PUB-05.**
  Enumeration-in-prose screens fire LOW candidates with an explicit
  PUB-05 limitation; no direction in PUB-04 mandates a representation
  change. Repeated-pattern detection (a PUB-04 hypothesis signal) is
  NOT implemented — recorded gap for PUB-08, not silent coverage.
- **D-PUB-28 — Frozen-profile calibration discipline.** Threshold
  values were set a priori and never retuned; pre-freeze work was
  structural precision (HTML/list/definition/methods handling, CX07
  use-before-definition logic, term normalization) plus fixture-text
  shaping. Held-out evaluated once; the single miss stays a strict
  xfail pinning case (held-cx15, 39 vs 40 words), never tuned away.

## PUB-04 fix-batch decisions (recorded 2026-11-24 during the fix batch;
Muse implementation)

- **D-PUB-29 — Span contract: char spans locate quoted evidence.**
  Sentence detectors span the quoted sentence occurrence, CX07 spans
  the term's first-use occurrence, block detectors span the measured
  block(s); CX07 line anchors bracket the use→define gap. Zero-width
  spans are never emitted as located findings (unlocatable → explicit
  needs-context locator miss). Contract lives in the module docstring
  and `docs/cli/complex/README.md`, pinned by regression tests.
- **D-PUB-30 — Severity-preserving dedupe; related links after dedupe.**
  Dedup key stays (cx_id, start_line); the maximum severity survives
  (ties keep the first), so the CX04 HIGH roll-up and the longer CX10
  run are reachable. Related linkage is rebuilt post-dedupe so every
  related id resolves. Live deltas must be shown field-by-field (this
  batch: Ch1 identical, book identical, dangling 312→0).
- **D-PUB-31 — Reader-context inputs resolve, never decorate.**
  `concept_index`/`glossary_terms` establish vocabulary (registry hit =
  quiet, no finding and no need); absence stays explicit via
  `context_limits`. The alternative (removing them from the signature)
  was rejected: resolution is honest, decoration would be pretence.
- **D-PUB-32 — Narrowed structure exclusions.** Figure-structure HTML
  (structural-tag allowlist) vs inline-HTML-wrapped prose; wrapped
  continuations belong to their list (list-structured) vs genuinely
  mixed blocks (column-0 prose + bullets) which stay assessable, with
  list lines stripped wherever a sentence quote is at stake (CX10/CX11
  already did; CX14 added). Definition/methods exemptions unchanged.
- **D-PUB-33 — Volatile metadata and scoped views.**
  `summary.generated_at` is wall-clock metadata excluded from replay
  identity (`REPLAY_VOLATILE_KEYS` + `replay_identity()`); `review
  --cx` rescopes through `rescope()` (filter + pruned related +
  recomputed summary, never mixed filtered/unfiltered numbers);
  `compare` text mode shows `max_severity` because its own note says
  to compare it first.
- **D-PUB-34 — Strict behavioural pins; documented traps.**
  held-cx15 stays an xfail but a strict one (unexpected pass fails
  loudly). F4/F5/F6/F8/F9 are recorded as known traps with a PUB-08
  owner in the complex README and CAPABILITIES — no code, no silence.

## PUB-04 fix batch 2 (recorded 2026-11-24 during the Codex delta
re-review fix; Muse implementation)

- **D-PUB-35 — CX10 run spans anchor forward from the run's own
  start.** Each run sentence is located from the end of the previous
  one (`_locate_span(..., start=...)`), so a later higher-severity run
  whose final sentence also occurs earlier in the block quotes its own
  occurrence (start<end always). Rationale: locating every run end from
  the block start inverts the span when the final sentence repeats
  (reproduced char_start>char_end pre-fix). The span contract (module
  docstring + complex README) now states the forward anchor.
- **D-PUB-36 — Mixed-block prose probes exclude wrapped list
  continuations.** `_prose_lines()` drops list-item lines AND the
  indented continuations belonging to them (the `_is_list_block`
  gluing rule); CX10/CX11/CX14 probe it, and CX11 quotes the probe --
  never list lines or continuations -- whenever the block carries list
  lines (D-PUB-32's prose-only requirement extended from CX14 to
  CX10/CX11). Rationale: stripping markers while keeping continuations
  let mixed prose/list blocks yield findings quoted from continuations.
- Doc one-liners (no new decision numbers): held-cx15 rationale 38→39
  words (1-word margin vs the 40-word floor; count verified by running
  `word_count` on the fixture text); `--cx` rescoped summaries
  documented as keeping `preserved_count`/`needs_context_count`/
  `concept_events` chapter-scoped (complex README + `rescope()`
  docstring — filtering narrows findings only, never the chapter-wide
  lists).
- Untouched by instruction (recorded, never edited): writer `INDEX.md`
  / `README.md` command counts remain owning-team flux (DeepSeek R1
  stays backlog).

## PUB-04 fix batch 3 (recorded 2026-11-24 during the Codex delta
re-review; coordinator-executed, no new files)

- **D-PUB-37 — Run findings require a located occurrence; unlocatable
  runs are declined.** `_strict_locate()` returns `None` instead of a
  fallback whole-block span, and the CX10 run branch skips runs with
  any unlocatable sentence. Rationale: the fallback accepted a block
  span as a run endpoint when line filtering removed the probe's
  context, so the quote was not a contiguous source occurrence
  (Codex BLOCKED point 1).
- **D-PUB-38 — Probes are contiguous prose segments; list boundaries
  break them.** New `_prose_segments()` (membership identical to
  `_prose_lines`, which now delegates to it); CX10 runs, CX11 and the
  CX14 opening probe each measure one segment, so prose is never
  joined across a removed list item (Codex BLOCKED point 2). CX11
  quotes its own segment text (verbatim contiguous); CX14 probes the
  opening segment. Same-block dedupe (D-PUB-30, max severity per
  `(cx_id, start_line)`) is unchanged: two same-block runs still
  collapse to one, now with a side-local quote and correct run_length.
  Extension (verification round): the consecutive-one-sentence CX10b
  run iterates ALL blocks and breaks the sequence on any structural
  (non-assessable, non-blank) block -- previously it iterated assessed
  blocks only and joined runs across tables/code/figures/headings.
  Blank gaps do not break a run. Pins: cross-table no-join +
  blank-gap positive control.
- Verification: complexity 63 unit + 43 calibration (42 passed + 1 strict
  xfailed) green; full fast gate 467 passed + 1 xfailed / 0 failed;
  ruff clean; live Ch1 38 findings identical set (free of cross-structural
  joins), book scan 36 chapters / 1073 findings / 0 dangling /
  0 bad spans (-10 vs batch-2 baseline: removed cross-structural joins;
  Ch1 untouched), fingerprint-stable; Jev clean; $0. Pins:
  cross-boundary no-join (run_length 3/MEDIUM, not 6/HIGH),
  segment-local CX10/CX11 spans, opening-segment CX14 scoping,
  `_strict_locate` unit pins, cross-table seq-break + blank-gap control. Post-verification: CX10b structural-break
  fix (-10 book-wide cross-structural joins; book 1083→1073, Ch1
  identical) with 2 pins.

## PUB-05 decisions (recorded 2026-11-24 before implementation; Muse design)

- **D-PUB-39 — Pedagogical planning lives in writer-core analysis + CLI;
  not a runtime domain; zero model dispatches.** Same reasoning as
  D-PUB-10/11/24: `publication_pedagogy.py` composes `reader_legibility`
  spans/roles, PUB-02 cruft reports + preservation, PUB-03 reconciliation
  states, PUB-04 complexity findings and book-side declared intent
  (Jev `metadata/*.yaml`) without owning any of them. `writer pedag`
  CLI surface (`plan|validate`); no catalog manifest (catalog stays 167).
  Model-backed adjudication is confined to prepared-never-dispatched
  `prepare_typed_task` payloads via the D-PUB-08 seam
  (`PedagogicalAdjudicationResponse` contract); PUB-05 performs zero
  dispatches because deterministic triggers sufficed for the structural
  plan layer.
- **D-PUB-40 — Reuse verdicts (inspected callable interfaces, not
  descriptions).** Reused: `reader_legibility` `split_into_blocks` +
  `Block` + `EvidenceRole` (spans, roles, prose/structure masking);
  PUB-02 `PublicationCruftReport` shape (findings + `preserved` +
  `needs_evidence`, fingerprint binding) consumed from JSON, never
  re-detected; PUB-03 `ReconciliationState` (UNRESOLVED/SUPERSEDED/
  PARTIAL/SUPPORTED) consumed from JSON, freshness via
  `(project_id, manuscript_fingerprint)` binding; PUB-04 complexity
  report shape (findings + preserved + needs-context + concept events);
  `argument.extractor.extract_observed_structure` (deterministic nodes,
  concept mentions — conceptual reuse of node kinds, imported in the
  Jev demonstration path only, engine stays dependency-light);
  `manuscript_ir.compile_chapter_file` paragraph/sentence units +
  content hashes as the span-identity reference (demonstration path;
  engine works from finding spans + block text); Jev `metadata/*.yaml`
  `purpose`/`claims{documented,observed,proposed}`/`limitations`/
  preregistration as declared intent (read-only sidecar, explicit
  uncertainty when absent — never invented intent); hugo.toml
  `math/mermaid` flags + `<figure class="jev-figure">` + EPUB pipeline
  as observed render capabilities (mermaid render path unverified →
  proposals carry a pipeline-support caveat). NOT reused as deciders:
  `knowledge_state` m2/m4/m7 (need event ingestion + milestone
  observations; no book has that pipeline — coherence-only chapter
  measurements cannot ground per-passage plans); `metadata` Writer
  contracts (Writer-side shape ≠ book YAML shape; mapping is a PUB-07
  bridge concern); `editorial` diagnosis (problem lists, not
  transformation ops; consumes PUB-05 plans later, not input);
  `refine`/`revise`/`improvement` plan operations (human-review or
  fiction-oriented or mutating orchestration — vocabulary aligned,
  substrate undecided per U1, PUB-06 owns); `mediated_read`/
  `evaluation_fabric` (PUB-08 comprehension probes; fixtures here never
  claim comprehension); `taste` (advisory alignment, needs profile);
  `statistics` feature extraction (governance-gated; PUB-05 uses local
  count proxies marked approximate); `qc`/`validation` (PUB-06 gates;
  the plan validator follows the same span/evidence discipline, it does
  not call fiction-tuned validators); no new `ai` primitive (typed-task
  seam pattern + ABSTAIN per CAPABILITIES §7 suffice).
- **D-PUB-41 — PD01–PD16 taxonomy with per-item support status; no
  manufactured coverage.** All 16 are defined with decision rules, but
  only the deterministic/structural subset fires in PUB-05 (late
  definition PD04 via CX07; overload PD07 via finding clusters;
  repeated-explanation PD12 via repeated-qualification clusters;
  research-interrupts PD14 via CR07 + CX14 co-location; representation
  PD15 via CX15 candidates + comparison-shape probes). The rest
  (PD01 motivation, PD03 ordering, PD05 definition-writing, PD06
  relations, PD08 buried argument, PD09 synthesis, PD10 excess detail,
  PD11 worked example, PD13 transitions, PD16 purpose-vs-experience)
  are STRUCTURAL (visible in the plan as investigated-and-abstained or
  reader-context-blocked) or ADJUDICATED (prepared payload, never
  dispatched). The planner emits ABSTAIN with reasons rather than
  guessing; KEEP and NO_CHANGE are first-class outcomes.
- **D-PUB-42 — Preservation contract (before planning, in code).**
  Must-survive = PUB-02 honest-record preservation + PUB-04 honest-record
  exemptions + declared-intent claim tiers (`documented`/`observed` =
  established; `proposed`/`hypothesis_notes` = explicitly NOT
  established — plans must never present them as established) +
  metadata `limitations[]` + preregistration hypothesis (frozen record)
  + PUB-03 non-established states (UNRESOLVED/SUPERSEDED/PARTIAL claims
  stay visible; reconciliation proposals are the only sanctioned
  correction path). Essential knowledge may move presentation
  (prose↔table↔diagram↔example) but every operation carries
  preservation obligations naming what stays byte-true (quantities,
  code behaviour, math, evidence refs, NOT_OBSERVED tables, genuine
  limitations). Unresolved evidence claims are NEVER
  strengthened/removed/presented-as-established during planning —
  enforced by the plan validator (unresolved-input → evidence-blocked
  status, never execution-ready).
- **D-PUB-43 — Plan contract (PUB-06/Workbench/Mission-consumable, no
  prose parsing).** Identity/provenance (plan id, project/chapter,
  fingerprint, inventory rev, input finding ids, planner + profile
  versions, model identity `none`, coverage assessed/unassessed,
  reader-context availability); objectives (purpose, essential
  knowledge, prerequisites, target understanding, preservation);
  operations (id, type from the controlled vocabulary, target
  span/section, finding refs, destination, rationale, benefit, evidence
  needed, preservation obligations, deps, validation, open questions,
  approval needs); status lattice
  (candidate/adjudication-ready/execution-ready/evidence-blocked/
  context-blocked/conflicted/no-change) with the hard rule that no
  operation with unresolved material prerequisites is ever
  execution-ready. Freshness: plans bind inputs and go stale on any
  input change (`check_stale`). Operation vocabulary is illustrative
  and aligned with `revise`/`refine`/`improvement` where expressive,
  but independent until U1 settles the mutation substrate (PUB-06).
  Plans describe transformations, never final prose.
- **D-PUB-44 — Grouping and prioritization without invented scores.**
  Findings group by span → paragraph → section → concept/explanation/
  argument/evidence/objective with identity preservation (every input
  finding id appears in exactly one group or the explicitly-unplanned
  list — nothing silently dropped). One coherent transformation per
  group. Priority is ordinal (materiality × impact × risk × certainty ×
  deps × scope, each low/medium/high with a one-line rationale), never
  a calibrated number (D-PUB-04 holds).
- **D-PUB-45 — Representation selection is fit + purpose + pipeline,
  never quotas.** Every visual/structural proposal records knowledge
  communicated, source spans, why current fails, why selected fits,
  what stays in prose, replace/supplement/reorganize, source data,
  provenance, placement, caption, accessibility description, format
  constraints. Candidates: prose/prose+example/bullets/numbered/table/
  state-diagram/Mermaid-SVG/equation+prose/chart/worked-example/
  comparison-callout/relocated-section/evidence-reference. Pipeline
  support is an observed-capability input (default conservative:
  prose/list/table/code/equation-text supported; mermaid/figure/SVG
  need explicit flags). KEEP_PROSE and NO_CHANGE are supported
  outcomes; no diagram quotas, no table-everything.
- **D-PUB-46 — Frozen-profile calibration discipline (as PUB-02/04).**
  `pedagogy-v0.1` UNCALIBRATED; 16 counterfactual cases (spec §15 list)
  as dev/held-out fixture entries over genuine Jev passages + labelled
  synthetics; held-out evaluated once, never tuned; fixtures pin
  planner behaviour and never claim reader comprehension (PUB-08 owns
  that with human data).

- **D-PUB-47 — Materiality-scoped evidence blocking (refines D-PUB-43).**
  Only proposals whose correctness depends on missing or unsettled
  evidence are blocked by it: re-presenting/mutating ops (table, list,
  diagram, reorder, update, remove, relocate, rewrite, worked example)
  are blocked by overlapping missing-evidence needs and overlapping
  unresolved/partial/superseded claims; consolidation is additionally
  blocked by overlapping unresolved/partial claims (it may drop unsettled
  framing); split/synthesis/connect/prerequisite-location moves preserve
  text and framing and are never blocked by needs or unresolved/partial
  states (the INVESTIGATE op tracks those, preservation obligations travel
  with the op); genuine conflict (contradicted/conflicted) blocks
  everything except read-only outcomes; CX07 terminology needs block
  nothing by themselves (the term's own INVESTIGATE op is inherently
  evidence-gated). Rationale: the first implementation blocked whole
  groups on any overlapping need and buried the structural signal (Ch9:
  55 blocked, staccato consolidation invisible); blocking must follow
  materiality, not proximity.

- **D-PUB-48 — Planner-side numeric-literal guard (not a PUB-04
  change).** CX07 needs whose marked "term" is a pure measurement/numeric
  literal (`n=3080`, `0.9878`, `proposed:` — Ch9 carries 40 such needs)
  never open term-investigations: a literal can never be a glossary term,
  so the planner declines and the group falls through to NO_CHANGE. The
  PUB-04 findings stand untouched (no profile change, no re-detection);
  the guard is pinned by a unit test. Rationale: without it the Ch9 plan
  is 40 noise investigations; with it the structural signal (staccato
  consolidation) is visible. Genuine-term misses, if any, are a PUB-08
  calibration question.

## PUB-05 fix batch (executed 2026-11-24; Muse implementation, addresses the
Codex CONDITIONAL 4 residuals + the DeepSeek record-number correction;
verified by coordinator 2026-11-24)

- **D-PUB-49 — Validator authority: exact anchors, attached obligations,
  refs over mutable fields.** The bounds-only `span_out_of_range` check
  could not catch a KEEP retargeted to a *different in-range* span, so
  every operation target now carries an `anchor_sha256` content anchor
  (built at plan time, recomputed by the validator;
  `span_anchor_mismatch` on skew). Preservation coverage is enforced on
  the operations' *attached* `preservation_obligations` lists (overlap +
  attachment, including non-located claim-tier items on every op) rather
  than on op-span overlap alone, so stripping obligations fails as
  `preservation_gap` even when spans still overlap. The
  `execution_ready_with_open_evidence` verdict is derived from
  `need_refs`/`reconcile_refs`/`blocking` -- never the mutable
  `evidence_needed` field alone -- and a new `evidence_needs_mismatch`
  code fires when `evidence_needed` skews from the refs/blockers it was
  built from. Freshness (`check_stale`) binds reconcile *states* (a
  SUPPORTED->UNRESOLVED flip with identical claim ids stales the plan),
  declared-intent *contents*, reader-context *values* and effective
  render-cap *values*, not just finding IDs + inventory rev. The
  validator now carries 17 violation codes (the 14 actually present plus
  the 2 new ones plus `span_anchor_missing`); the CAPABILITIES "12" was
  a recording error, the code set itself is kept, not renamed.
- **D-PUB-50 — CX13 REORDER stays explicitly investigation-only; the
  label-token guard stays a planner-side heuristic.** REORDER proposals
  are never primaries and now carry `investigation_only: True` with
  forced `candidate` status, so PUB-06 cannot consume a candidate
  investigation as a second transformation (adjudication may still
  promote one via a recorded `adjudicated_by`; the mutating-op
  execution-ready rule is unchanged). Recorded choice: investigation-only
  rather than a PUB-06 consumption gate, because the status lattice
  already expresses it and the validator already enforces it. The
  D-PUB-48 numeric-literal guard is kept planner-side with its scope
  documented (heuristic, not a detector change; genuine-term misses are
  a PUB-08 calibration question).
- **D-PUB-51 — Correction path: linked proposal or no UPDATE; grouping
  retains payload; investigations stay read-only under conflict.**
  `UPDATE_FROM_VERIFIED_EVIDENCE` is emitted only when the superseded
  verdict carries a linked PUB-03 correction proposal *with non-empty
  linked evidence* (`applicable_evidence` or `evidence_refs` entries;
  a freshness binding alone is NOT support); otherwise the claim gets
  an evidence-gated INVESTIGATE_EVIDENCE
  (`reconcile:superseded-without-correction`), never an UPDATE.
  Grouping retains `correction` + `evidence_refs` +
  `provenance` through to the proposal (the old shape dropped them, so
  the gate could not see them), and the UPDATE op carries the payload.
  The D-PUB-47 read-only exemption is honoured: conflicted/contradicted
  evidence no longer blocks non-mutating INVESTIGATE_EVIDENCE (it still
  blocks every mutating op). Same decision covers the freshness
  extension (states + intent + context + caps digests in plan inputs).

## PUB-05 fix batch 2 (executed 2026-11-24; coordinator-executed,
addresses the Codex delta re-review's 2 deeper residuals)

- **D-PUB-52 — Anchor presence enforced; UPDATE needs linked evidence,
  not just a binding.** A span-carrying operation with NO
  `anchor_sha256` fails validation outright (`span_anchor_missing`;
  absent anchors are never grandfathered, because a recomputed hash
  is indistinguishable from a stripped one -- the hash is
  tamper-evidence, trust roots in fingerprint-bound regeneration).
  A superseded claim with correction text + freshness binding but zero
  linked evidence refs now routes to evidence-gated INVESTIGATE,
  never an adjudication-ready UPDATE.

## PUB-06 decisions (recorded 2026-11-24 during implementation; Muse design)

- **D-PUB-53 — U1 settled: Workbench Apply produces, VFS stages, the
  surgical grammar fixes small things, QC gates everything.** Production
  mutation substrate is Workbench `chapter_apply` (journaled atomic
  one-file apply + Git commit + Undo) — the sole production mutation
  path, unchanged. VFS change-sets (branch/snapshot/change-set/diff/
  apply) are the *staging* shape for candidates under review; an
  approved staged change-set flows to Workbench Apply through the
  PUB-07 bridge (not built here). `Current Text / Recommended Change`
  fenced blocks (`apply_edits.py`: exact-unique inline, conservative
  block-safe, overlap rejection, backups) are the surgical grammar;
  engine `emit_surgical_edits` renders it with exact-unique prechecks
  and long fences, pinned by fixture round-trip tests against the real
  script. QC gating is `qc.evaluate_candidate_qc` +
  `manuscript_ir.verify_candidate_downstream` before any application
  decision; `request_application` additionally requires a human
  approval record + fresh fingerprint and still returns `fixture_only`.
  No bulk apply before this staged design — this stage IS the design,
  proven on disposable fixtures with fingerprint proof (ACCEPTANCE
  PUB-06 gate). Rationale: each substrate already exists and is owned;
  PUB-06 supplies the missing composition (plan→packages→candidate→
  staged change-set→gated apply), not a third mutator.
- **D-PUB-54 — Boundary violations split blocking vs isolating;
  verification is ordered-subsequence with an anti-gaming verdict.**
  (a) Stale fingerprint/evidence/anchors, unknown op types, validator
  rejection and same-span mutating conflicts block the *plan*
  (malformed/stale/conflicted/ungrounded = rejected). Investigation-only
  REORDER and evidence-held mutating ops isolate the *single op* while
  unrelated improvements proceed (D-PUB-47 materiality at the boundary).
  (b) Byte-true verification compares non-empty source lines as an
  ordered subsequence: SPLIT re-paragraphing passes, rewording/removal
  fails, empty spans are vacuous, duplicates deduped once. (c) Any
  preservation failure fails the candidate even when finding counts
  fall — deleting material to clear findings is FAILED by construction,
  and better-scores-with-unsupported-conclusion is rejected the same
  way. Rationale: the verdict must rest on preservation, never on
  detector deltas, or the stage optimises the wrong thing.
- **D-PUB-55 — Bounded adjudication is recorded editorial judgment;
  editorial generation is CONFLICTED for review.** The 6
  context-blocked CONNECTs resolve from in-manuscript context with
  per-op rationale + context_used (no audience modelling invented);
  the CAPSTONE-02B CONSOLIDATE declines under byte-true preservation
  (correction already integrated in the main text, note minimal).
  Candidate prose is authored by the implementing model inside compiled
  work packages and recorded with its identity in the transformation
  record; that identity can never supply INDEPENDENT_REVIEW
  (`CONFLICTED_MODEL_JUDGEMENT`, ADR-010). Independent review arrives
  via separate-model/human prompts (review-pack), disagreements
  preserved. Zero Worker dispatches keep the model surface auditable
  ($0; editorial vs verification spend both $0).

## PUB-06 fix batch (executed 2026-11-24; Muse implementation, addresses
Codex BLOCKED a–f + 2 editorial and Claude BLOCKED-narrow P1/P2/P4/P5/P8
must-fix + P3/P6/P7/P9/P10 should-fix; pending Codex/DeepSeek/Claude delta
re-review)

- **D-PUB-56 — Application gate binds QC/downstream itself; freshness
  unconditional; VFS staging design-only.** `request_application` no
  longer accepts a caller verdict alone: QC and downstream gates must
  each carry `candidate_fingerprint` + provenance (`detector`,
  `checked_at`), checked here (mismatch/unbound → blocked).
  `live_fingerprint` is required (no fingerprint-optional bypass).
  VFS change-sets are an explicit design-only `StagedChangeSet`
  (`design_only=True`, `production_path=None`, hard `fixture_only`
  gate) — no silent design-as-implemented. Production remains Workbench
  `chapter_apply` via the PUB-07 bridge.
- **D-PUB-57 — Boundary revalidation hardened.** `inventory_digest`
  bound when present and required when mutating ops reference evidence;
  `evidence_rev` mandatory for referenced claims (only true
  `None`/`"unbound"` bypass blocked; the programme `"jev@live"`
  placeholder matches when live equals bound); live `reconcile_states`
  required (no silent pass); supplied live ids/digests rehydrate and
  authenticate plan inputs (detects consistently-edited references);
  preservation obligations authenticated internally plus live-source
  check when supplied (extends D-PUB-52); adjudication promotion needs
  `rationale` + `context_used` + `adjudicated_by` + `at` with
  `plan_id`/`source_fingerprint` freshness (bare accept/modify
  insufficient); dependency cycles block (`DEPENDENCY_CYCLE`).
  CLI `transform check|package` wire live states/digest/adjudications
  through (`--evidence-rev`, `--inventory-digest`,
  `--reconcile-states`, `--adjudications`) and refuse silent runs.
- **D-PUB-58 — Work-package compilation gated and ordered.** `compile_
  work_packages` invokes (or honours a caller-supplied) boundary
  validation; `chapter_text` authenticates every span anchor;
  execution follows dependency order (`_topological_order`, cycles
  isolated); package `blocked` derives from gates (never `False` by
  default); blocked ops promote only on fresh context-bound
  adjudication. Operation vocabulary aligned by explicit map
  (`_OP_ALIASES`): PUB-05 `REWRITE_FOR_CLARITY` ↔ transform
  `REWRITE_PASSAGE`, `RELOCATE_SUPPORTING_DETAIL` ↔ `RELOCATE_SECTION`,
  `ADD_WORKED_EXAMPLE` → `ADD_SYNTHESIS`, `CONVERT_TO_LIST` →
  `CONVERT_TO_TABLE` handling, plus `PROPOSE_DIAGRAM`,
  `REMOVE_CONFIRMED_CRUFT`, `INTRODUCE_PREREQUISITE`,
  `ADD_EXPLANATORY_BRIDGE` accepted directly.
- **D-PUB-59 — Preservation verifier proves placement and covers new
  prose.** Byte-true requires full-line ordered-subsequence (not
  substring-anywhere); no-change spans require contiguous exact-line
  runs; unresolved-evidence obligations enforced independently of
  supplied `byte_true` lists; added sentences get a claim-tier honesty
  check (`_check_new_sentence_honesty`: model-backed + establishment
  language without an unrun qualifier fails; full semantics remain
  PUB-08 human review). Anti-gaming verdict semantics kept
  (deletion → fail) while the stripped-obligation bypass is closed.
- **D-PUB-60 — Surgical exactness matches the real applier.** Exact
  inline requires ≥24 chars, unique occurrence and clean word
  boundaries (mirrors `apply_edits.py` `_MIN_INLINE_CHARS` +
  `_inline_boundaries_are_clean`); shorter Current Text must match a
  full block uniquely or be refused (block-or-refuse). `apply_to_fixture`
  enforces the same. Real-applier regression pins short-substring
  refusal (disposable fixture, `--diff/--apply --no-backup`; 0.978-style
  fuzzy short text refused, never spliced).
- **D-PUB-61 — Record hash-chain guaranteed by the builder.** Package
  hashes bound (`package_hash` per package + `packages_digest`);
  verification before/after fingerprints retained;
  `verification-after == recorded candidate_fingerprint` asserted (else
  `ValueError`); before must equal the plan source fingerprint. The
  builder guarantees the chain, not just reports it.
- **D-PUB-62 — Editorial honesty (Claude + Codex).** P1 roadmap removes
  "cost something"/"measured" for unrun arms; P2 restores unknown model
  shape and drops "exactly where the book begins"; P4 caption/alt/SVG
  per-lane (predicate True/abstain, stub nothing; 25 chars = serialized
  example payload; lane 3 holds two arms, four unobserved arms total);
  P5 SVG qualifier ("naive index, augmented Python grammar") + title/desc
  four-lane match; P8 figure order (1.2 after 1.1); should-fix P3/P6/P7/
  P9/P10 applied; Codex Tam sense ("what format restrictions do to task
  performance") and per-lane 25-char distinction applied. `before-after.md`
  disputed claims corrected to concur (P4 honesty + verdict).
- **D-PUB-63 — Reproducibility and hygiene.** The 46-op plan JSON
  (`pub06/ch01/plan-ch1.json`) + bound adjudications
  (`adjudications-ch1.json` with `adjudicated_by`/`at`/`plan_id`/
  `source_fingerprint`) + live states/digest + boundary/packages gate
  files ship in `pub06/ch01/` (DeepSeek note 1). Review-pack doc nits
  fixed (transformation 35→60 suites; complexity 38→35, not 38→32/33;
  neighbours 258+1). `mission/.writer/writer.db` (13 MB, writer CLI/test
  state) is git-ignored (`.gitignore` `.writer/`), never committed;
  Jev ignore untouched by coordination rule; Temp evidence cleaned after
  runs; editorial generation spend recorded separately
  (muse-spark-1.3, opencode-session, unmetered-session, $0; zero Worker
  dispatches on the engine path).

## PUB-06 close-out (executed 2026-11-24; coordinator-executed, addresses
the Codex delta confirm's 4 fail-closed residuals + Claude R1/R2/R4/R5)

- **D-PUB-64 — Gates fail closed on absence, not just mismatch.**
  Provenance requires BOTH detector and checked_at (either missing
  fails); `request_application` rejects a missing candidate
  fingerprint instead of falling back to live; compile refuses the
  whole plan on a non-executable boundary (0 packages, violations
  surfaced, CLI exits non-zero) instead of letting per-op verdicts
  override it; adjudication promotion and boundary mismatch checks
  require plan_id + source_fingerprint (unbound = rejected, not
  unchecked); the record builder requires before/after fingerprints
  (omission raises instead of skipping the chain assertions). Pins
  for each; pre-existing stale-adjudication test re-pinned to a bound
  record (unbound now correctly reports UNBOUND before staleness can
  be assessed).

## PUB-06 fix batch 2 (executed 2026-11-24; Muse implementation, addresses
the Codex delta-confirm REJECT's 3 trust-root blockers; pending Codex delta
re-confirm + DeepSeek delta re-verify)

- **D-PUB-65 — Compile authenticates caller-supplied boundaries; the
  recomputed boundary governs.** `compile_work_packages` always
  revalidates internally against the plan + chapter bytes + the live
  inputs threaded through its signature (evidence-rev, inventory
  digest, reconcile states, input ids/digests, adjudications,
  book/chapter labels). A caller-supplied boundary is advisory, never
  authoritative: the effective boundary is the fail-closed conjunction
  (executable only when BOTH agree; violations union; per-op verdicts
  take the worse rank). A `binding_digest` (whole-plan digest +
  chapter fingerprint + every live input + adjudication identities)
  authenticates the exact inputs a boundary was computed from; mismatch
  appends an isolating `supplied_boundary_mismatch` note. Rationale:
  authenticating the inputs rather than the verdict closes the forged-
  executable-boundary class (stale plan, same-span conflict) without
  trusting any caller bytes. CLI `check|package` thread identical live
  inputs to both revalidate and compile, so the honest pipeline
  authenticates cleanly.
- **D-PUB-66 — Live states must cover referenced claims (no empty-map
  bypass).** Claim-shaped mutating-op refs (bare `eclaim:<id>` form, or
  any ref present in the bound/live states maps; planner-internal
  `evidence-gated`/`cruft-need`/`reconcile:` markers excluded) must
  EACH be present in the live states map: an empty or incomplete map
  with referenced claims blocks (`stale_input_digest`), no compile.
  Dict-form bound freshness reaches parity with list-form (bound claim
  ids absent from live states stale the plan). `_restrict_unresolved`
  is fail-closed on missing coverage instead of returning on an empty
  map. Rationale: presence is a precondition for the overlap
  assessment; without it `states={}` silently passes held ops as
  `boundary_ok`.
- **D-PUB-67 — Required preservation obligations are rehydrated from
  live trusted sources at the boundary.** The boundary re-runs the
  cruft + complexity classifiers on the live chapter bytes
  (deterministic: same bytes + same code reproduce exactly the
  preserved sets the plan was compiled from) and requires: (a) every
  live preserved span overlapped by a compilable mutating-op span is
  covered by a plan obligation, and (b) every claim-shaped mutating-op
  ref whose live state is unsettled is carried as a plan obligation
  `claim_id`. Either gap blocks (`preservation_auth_failed`): stripping
  an obligation from the plan AND its ops is refused. Chosen over
  plan-digest binding because the digest only moves trust to wherever
  the expected value is stored, while live recomputation re-derives the
  requirement from sources the attacker cannot edit. Materiality scope
  (D-PUB-47): only spans a compiled op can alter and only claims
  compiled ops reference are checked; intent-tier obligations stay
  planner-side (documented limitation -- non-located
  meaning-preservation, enforced at verify against the candidate).
  Verify keeps trusting the boundary-approved plan (safe only behind
  `check`/`package`; the record chain asserts before == plan source
  fingerprint so a substituted plan cannot ride an old record).

- **D-PUB-68 — Record chain binds plan content, not plan id.**
  `chain.plan_digest` was `sha256(plan_id)` -- an id-string hash a
  substituted plan keeps. It now digests the whole plan object (same
  `_digest_obj` the boundary `binding_digest` already uses for its
  plan field), so any post-hoc op mutation changes the chain digest.
  Pin: same `plan_id`/`source_fingerprint` with one added op yields a
  different `chain.plan_digest`. Recorded after DeepSeek's batch-2
  verification flagged the overclaim in D-PUB-67's "cannot ride"
  sentence.
- **D-PUB-75 — Chain digests canonicalize volatile run metadata.**
  `generated_at`/`verified_at`/`recorded_at` are stripped before
  hashing (`_canonical_plan`), so identical content always yields the
  identical digest while any content mutation changes it. Without
  this, every regeneration looks like tampering (false drift) and no
  record is reproducible. Pin: same content + different timestamp
  → identical digest. Added during coordinator close-out after the
  record rebuild exposed the timestamp-sensitivity.
- **R1 doc-record correction (DeepSeek batch-2 re-verify).** Recorded
  live numbers are superseded by the final tree: book scan 38→39
  (CX02 8→9, CX05 2→4, CX13 1→2, CX11 5→4; CX10 1→1 -- the "new HIGH"
  was a cross-table false positive removed by the PUB-04
  structural-break fix, verified gone); neighbours 260 passed +
  1 xfailed (was "258+1"; +2 are the cross-table/blank-gap pins);
  transformation suite 74→76 with the chain-content + chain-stability
  pins. Handover prompts refreshed to 606 lines / `f6c1cb…` / 76+2
  CLI tests / 39.
- **R4 handoff refresh.** Review-pack prompts now carry current
  fingerprints, counts, and a note that `before-after.md` WAS
  rewritten (00:03 rebuild) -- correcting the prior "untouched" claim;
  STATE "0 violations" corrected to 2 isolating (op:039 held,
  op:042 investigation-only consumed).
- **R5 blind spots (documented, PUB-08 owned).** Derived artifacts are
  not auto-regenerated after detector changes -- re-verify step is
  mandatory (09:xx rebuild proved the point); the record does not bind
  detector code version; no independent editorial pass on current
  bytes existed at DeepSeek's run (Claude delta review now covers the
  fixed regions; full-chapter re-read remains author-side).

## PUB-06 conditional acceptance gate (author direction 2026-11-24;
recorded by coordinator, pending Codex delta verdict)

- **D-PUB-69 — PUB-06 conditionally complete; close on Codex ACCEPT or
  CONDITIONAL-minor only.** Apply narrowly scoped corrections, verify,
  record ACCEPTED (7/12). On Codex substantive
  contract/evidence-integrity/preservation/safety defect: resolve
  first, no acceptance. No new broad review cycles either way.
- **D-PUB-70 — Semantic preservation carried through PUB-07 as an
  explicit limitation, not a waiver.** Six levels distinguished:
  (1) lexical -- implemented; (2) structural -- partial; (3)
  quantitative -- bounded; (4) semantic -- PUB-08; (5) epistemic --
  initial implementation; (6) pedagogical recovery -- PUB-08.
  21/21 preservation = checks passed, never proof of complete meaning
  preservation. D-PUB decisions and ACCEPTANCE.md must keep this
  distinction.
- **D-PUB-71 — PUB-07 safety boundary: candidate autonomy now,
  publication autonomy later.** PUB-07 may implement: production
  Worker dispatch, automated candidate generation, independent model
  review, bounded correction loops, candidate provenance/records,
  governed VFS staging, Workbench proposal/acceptance integration,
  fixture-based application, explicit approvals, recovery/failure
  handling. PUB-07 must NOT authorize unsupervised authoritative
  manuscript mutation or automatic publication approval on current
  preservation checks alone.
- **D-PUB-72 — PUB-07 must close the dispatch gap with a real
  production-path demonstration.** At least one editorial
  transformation through actual model routing + Worker execution,
  with invocation provenance, model identity, provider, usage/cost,
  response validation, candidate fingerprint, review outcome and
  correction-loop behaviour recorded. Manual candidates, mock
  providers, prepared-but-undispatched seams and fixture tests do not
  satisfy this. No duplicate gateway or mutation path.
- **D-PUB-73 — 950/1000 stays an aspiration, not a gate; detectors
  are instruments, not the objective.** The Claude 575→695 delta is a
  successful transformation demonstration, not publication readiness.
  Report the measured 38→39 complexity delta accurately; never
  optimize for detector-count reduction. Retain author-side
  obligations: self-test count discrepancy, predicate rerun,
  full-text sourcing, stub-row decision, dependent
  implementation/figure-placement items.
- **D-PUB-74 — PUB-08 semantic verification is mandatory, not
  exploratory.** Compose (before inventing): Manuscript IR +
  compiler, argument, knowledge-state, evidence, QC, mediated read,
  evaluation fabric, Praxis semantic-loss. Required directions:
  (a) forward preservation (lost/weakened/distorted/disconnected
  knowledge); (b) backward grounding (unsupported claims, new
  conclusions, altered certainty, invented relations, ungrounded
  additions); (c) authorized knowledge changes recognised as
  corrections, not loss (PUB-03 reconciliation as the allow-list);
  (d) pedagogical recovery via independent reader probes
  (model-reader vs human-reader distinguished; negative controls
  that pass lexical checks while failing semantic/epistemic
  integrity included).

## PUB-07 decisions (recorded 2026-11-25 during implementation; Muse design)

- **D-PUB-76 — One dispatch per package; generation deepseek-go, review
  haiku-go (independent family).** The package is the coherence unit, so
  a single editorial call carries all of its executable op directions
  (SPLIT + SYNTHESIS together, not per-op fragments). Generation rides
  the cheapest capable route (`default_deepseek_go`); review rides
  `default_haiku_go` (claude family vs deepseek) so the reviewer is not
  the reviser -- a same-family reviewer would be recorded CONFLICTED,
  never INDEPENDENT_REVIEW (ADR-010). Both ride the existing production
  path (Writer `models.run` -> Worker POST /v1/work -> pi provider);
  no new gateway, no new client, no direct provider calls. Writer owns
  prompts + Pydantic contracts (`EditorialCandidateResponse`,
  `EditorialReviewResponse`); off-passage quotes fail validation and
  are reported, never repaired (D-PUB-08 laws).
- **D-PUB-77 — Record extension is additive, never a new schema.**
  `build_transformation_record` gains optional `dispatch_ledger`
  (schema `writer.automation.ledger.v1`: per-dispatch model/provider/
  route/usage/cost with editorial-vs-verification split, spend totals)
  and `config.model_dispatches` counts invocations (0 on the
  deterministic-only path, preserving the PUB-06 pin). Record schema
  stays `writer.transform.record.v1`; the chain digests are untouched.
  `model_invocations` carries one receipt per dispatch (execution id,
  role, model, usage, cost, prompt hash).
- **D-PUB-78 — Workbench proposals at package granularity with span
  binding.** `workbench.publication_proposals` builds Proposal DATA
  objects (never actions) from candidate JSON + verification +
  ledger. `Proposal._validate` is paragraph-scoped and needs a Tray,
  so it cannot apply to multi-paragraph package candidates; instead
  each proposal carries a span binding (lines + span sha + chapter
  fingerprint) checked by `check_proposal_fresh` against live bytes
  (STALE on any mismatch -- the base-hash discipline at package
  granularity). Proposal creation refuses: empty replacement, failed
  verification, missing provenance. Status stays pending; accept/undo
  are never invoked (pinned by test + source scan). VFS staging stays
  design-only + disposable-fixture apply/undo proof (D-PUB-53/56); no
  live VFS change-set is created in the demo (avoids dragging the
  Writer state DB into the evidence loop; recorded, not hidden).
- **D-PUB-79 — Spend policy actuals (first metered dispatches).**
  Hard stop $10 per stage prompt; observed PUB-07 demo spend $0.00706
  over 4 dispatches / 25,504 tokens (editorial deepseek-go
  $0.00470 + $0.00236; verification haiku-go $0.00 subscription
  allowance). Cheapest-capable-first held (no escalation attempted;
  none needed). Provider-reported usage for the haiku route is
  internally inconsistent (input_tokens 4 vs total 5262) -- recorded
  verbatim in the ledger and flagged, never smoothed; cost unaffected
  ($0). Editorial vs verification split is kept in the ledger
  (`by_role`) so future stages can budget the two separately.
- **D-PUB-80 — A verify-pass + review-objected candidate is presented,
  never polished to green.** The Ch2 demo candidate passes all 15
  deterministic checks yet carries a twice-raised substantive
  objection (possible LLM2Jev overstatement vs ledger PARTIAL status)
  plus a final-round quote-discipline failure (verdict recorded
  invalid, rationale preserved). Re-running the loop until accept
  would optimise for green; the bounded loop instead terminated,
  recorded everything, and presented `pending_author_decision`
  with options. 21/21-style passes remain necessary-but-insufficient
  evidence of meaning (D-PUB-70/74); the review objections are the
  reason PUB-08 exists, not a defect to iterate away unsupervised.

## PUB-07 fix batch (executed 2026-11-25; Muse implementation, addresses
 the Codex BLOCKED 4 + DeepSeek F1-F5 + Claude CONDITIONAL residuals;
 pending Codex + DeepSeek delta re-confirm + Claude delta re-read)

- **D-PUB-81 — Review scope, rebind, spend, provenance, paragraph,
  canonical-form repairs (one batch, no new review cycle beyond the
  specified deltas).** (a) Review scoping (Codex 1 + DeepSeek F1):
  the review excerpt is the candidate's REPLACEMENT region (assembly
  lineage range `start + len(replacement) - 1`), never the original
  span end -- a shorter replacement no longer drags trailing source
  lines (in PUB-07 run 1: 8 lines incl. the LLM2Jev paragraph) into the
  review window. (b) Rebind before final review (Codex 2 + DeepSeek
  F2): after any correction, candidate bytes AND lineage are rebound
  from the correction's own assembly (stale indexes discarded), and
  validation consumes exactly the excerpt bytes shown to the reviewer.
  (c) Spend guard (Codex 3): enforced BEFORE dispatch (spent +
  projected next cost vs remaining budget; `halted_spend_guard` with
  zero new dispatch); `--spend-cap` above the default is accepted only
  via the explicit flag and recorded as an override in the ledger +
  record. (d) Dispatch provenance join (Codex 4): every editorial
  ledger row binds `replacement_sha256`; the record chain binds
  `ledger_digest`; the Workbench builder refuses ledgers that do not
  bind the presented replacement, `check_proposal_fresh` covers the
  replacement hash, and the proposal carries the record-chain
  reference (plan + candidate fingerprint + ledger digest). (e) Claude
  items via bounded re-run (never hand-edited): assembly realises
  paragraph breaks (blank-line separated entries, so the CX10b split
  exists in the bytes); the prompt forbids characterising glosses
  ("not rhetorical", resemblance/equivalence) and section/size
  citations beyond the passage; the run-1 LLM2Jev objection is closed
  against the new on-disk bytes (it was raised against leaked source
  bytes, see the superseded-run archive); the rationale record cites
  ledger 2.13 correctly (abstract + S1 + S3.3 PARTIAL; S4 NOT read).
  (f) Narrative correction (DeepSeek F4): the re-run's program +
  approval records supersede the run-1 objection narrative with
  pointers to the preserved run-1 archive; numbers are refreshed to
  the verified set with explicit supersede notes, never silent
  rewrites. (g) Canonical forms (DeepSeek F5): after-fingerprint is
  LF + single trailing newline (`candidate.md` persisted in that
  form, so raw file bytes join); replacement spans are LF-joined with
  no trailing newline; intent paths are slash-normalised before
  digesting; the ledger digest strips per-row `latency_ms`.
- Amendment to **D-PUB-68** (recorded here, original above untouched):
  the chain now also binds `ledger_digest` (D-PUB-81 Fix D) -- the
  "cannot ride an old chain" guarantee extends to the dispatched
  provenance, not just the plan content.
- Amendment to **D-PUB-79** (recorded here, original above untouched):
  spend policy is enforced pre-dispatch with projection (D-PUB-81 Fix
  C); the $10 figure stays the default cap, and any raise is an
  explicitly recorded override.
- Amendment to **D-PUB-69** (recorded here, original above untouched):
  this fix batch follows the same narrow-correction rule -- scoped
  code + pins + ONE bounded package re-run + specified delta reviews;
  no broad re-review cycle, no PUB-08 start until the deltas close.

## Explicitly rejected (appended PUB-03: parallel evidence architecture)

- New `reader_assurance`-style domain, new manuscript parser/scorer/composite,
  new campaign scheduler, new contract schema, new model gateway, `ai.assessment`
  primitive, Mission rescoring lane, diagram quotas, score-before-evaluation.
  Each has a recorded owner decision or a PUB-00 verification behind it.
