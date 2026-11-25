# PUBLICATION Roadmap

Stable IDs. Sequence reflects verified dependencies; rationale recorded per stage.
A stage is complete only under ACCEPTANCE.md evidence rules — never for
"doc/implementation exists".

## PUB-00 — Foundation, discovery, documentation ✅ (this stage, under review)

Research + documentation only. Done: objectives, architecture from live
implementation, Writer catalog read (165 runtimes; 8 relevant domains absent —
reconciliation deferred to PUB-01), cruft + complexity taxonomies adopted for
calibration, Jev Ch1 case study against `results/ch01.jsonl`, stable IDs,
ownership resolved-or-explicitly-open (U1–U5), acceptance criteria, docs in
`docs/programmes/publication/`. No implementation, no manuscript changes.

## PUB-01 — AI foundations and reusable primitives

- Reconcile capability catalog with runtime reality (`editing`, `quality`,
  `reader_legibility`, `self_repair`, `book_campaign`, `evaluation_fabric`,
  `refinement`, `mediated_read` manifests or delisting; run
  `validate_registry()` green) so later stages stop designing against stale data.
- Register or explicitly keep CLI-only the `quality` public surface (unblocks U2).
- Settle model-routing reuse (Writer `runtime.models` via Worker) — no new infra.
- Define provenance + evidence-label conventions (`CONFLICTED_MODEL_JUDGEMENT`,
  finding lifecycle Unassessed→…→Accepted/Blocked/Waived) for all later stages.
- **Depends on:** PUB-00. **Gates:** catalog↔runtime agreement; quality surface
  decision; no manuscript writes.

## PUB-02 — Writer cruft detection and classification

- Extend `reader_legibility` + `artifact` + `evidence` + `argument` toward the
  CR01–CR12 taxonomy (Stale experiment status … Stale tables/figures; see
  STATE.md for the Jev-observed subset). Deterministic first; model only where a
  deterministic signal is proven insufficient.
- Hard rules: genuine uncertainty, negative results and methodological amendments
  are preserved; obsolete-state vs genuine-uncertainty distinguished; no finding
  without source span + evidence role.
- **Depends on:** PUB-01 (surface + provenance conventions). **Gates:** calibration
  suite with confirmed-stale vs genuine-unresolved pairs (dev/held-out split).

## PUB-03 — Repository↔evidence reconciliation

- Bind manuscript claims to authoritative repo evidence (prereg, runners, result
  rows, ledgers, figures) per book; Jev first (`evidence/ledger.md`,
  `results/*.jsonl`, `examples/*/run_*.py`).
- Stale-result and evidence-missing states are first-class findings; missing
  evidence is never reported as success; completed-but-misdescribed experiments
  are critical defects.
- The wider-Jev-programme correspondence question is unresolved (STATE.md
  §4.6): the author reports the programme completed beyond what the book's
  `results/` holds. Treat as claim requiring reconciliation — never as verified
  or disproved. Distinguish: original artifacts vs subsequent artifacts vs
  capstones vs equivalent-differently-scoped vs validated replacements vs
  unresolved correspondence. Decision table (binding in PUB-03):
  pending claim + completed match found → update manuscript; pending +
  equivalent later artifact → investigate transfer; pending + partial match →
  preserve limitation; pending + no match → unresolved (visible, not a defect
  of honesty); completed evidence + contradictory manuscript → block.
- **Depends on:** PUB-02 (finding lifecycle), book-side schema cooperation.
  **Gates:** Ch1-style reconciliation report for ≥3 Jev chapters incl. one
  genuinely-stale case.

## PUB-04 — Writer cognitive-complexity detection

- New `editing` dimension block (versioned profile, no composite) + `manuscript_ir`
  roles + `statistics` features for: long/clausal sentences, parenthetical load,
  contrast pile-up, claim/concept density, undefined terms, unstructured dense
  prose, staccato fragmentation, missing bridges, poor ordering, visualizable
  prose. Treat the AI Statement→Exception→…→Return pattern and its staccato
  opposite as hypotheses, not rules.
- **Depends on:** PUB-01 (editing extension point). **Gates:** calibration on real
  passages (excellent vs degraded), thresholds versioned, false-positive traps
  documented (tables/code inflating naive counts — use `editing`'s parser).

## PUB-05 — Pedagogical analysis and representation selection

- Concept/prerequisite maps (`argument`), diagnosis (`editorial`, `mri`), style
  bounds (`taste`) → recommendations among prose/table/bullets/steps/diagram/
  equation/worked-example. Accuracy + pipeline-support (Hugo/EPUB) constraints;
  no diagram quotas.
- **Depends on:** PUB-04. **Gates:** before/after comprehension probes on samples
  (human or held-out model judges labelled per ADR-010; never self-scores).

## PUB-06 — Governed editing and manuscript transformation

- Settle U1: one mutation substrate (`vfs` change-sets vs Workbench Apply),
  staged large-region design (ADR-005), `Current Text/Recommended Change`
  interop, QC-before/after gating, Undo guarantees.
- Chapter-improvement orchestration (`improvement`/`refine`/`review`/sentence
  paths) under author approval; structural rewrites separated from surgical
  corrections.
- **Depends on:** PUB-02…05 (things worth applying), U1 decision. **Gates:**
  disposable-fixture end-to-end apply/undo with fingerprint proof; no bulk apply
  before staged design lands.

## PUB-07 — Workbench and Worker workflow integration + production automation

- Wire quality/findings bridge read-only first (existing unwired mapper), then
  proposals → Apply with stale/source checks; Worker-executed long jobs with
  provenance; no arbitrary execution from Mission.
- Expanded scope (D-PUB-71/72): close the prepared-never-dispatched gap with
  at least one real editorial transformation through the actual production
  model-routing + Worker execution path (invocation provenance, model
  identity, provider, usage/cost, response validation, candidate
  fingerprint, review outcome, correction-loop behaviour recorded).
  Automated candidate generation, independent model review, bounded
  correction loops, governed VFS staging, Workbench proposal/acceptance
  integration, fixture-based application, explicit approvals, recovery.
  Safety boundary: NO unsupervised authoritative mutation and NO
  automatic publication approval on current checks (candidate-generation
  autonomy and publication-acceptance autonomy are separate).
- **Depends on:** PUB-06 (accepted). **Gates:** wired bridge tests;
  provenance on every Worker-produced candidate; one real dispatched
  transformation demonstrated end-to-end; no duplicate gateway or
  mutation path.

## PUB-08 — Independent validation and calibration

- Publication-grade validation composition (`qc` + `verify` + `council` /
  `evaluation_fabric` with conflicted-judgement handling), dev/held-out
  calibration suites for cruft + complexity, reader-comprehension outcome
  measures (human study only via `quality.reader_study` + consent review).
  Accepted calibration debt queued here: CX10b whitespace-normalised
  quotes, display-`$$` mathematics, coherent-short-prose CX10-medium FPs,
  indented/tilde code fences, synthetic-heavy held-out suites (broaden
  real-manuscript held-out), cue-based new-sentence honesty (negation-
  insensitive establishment cues; full semantics).
- **Mandatory semantic verification (D-PUB-74):** compose Manuscript IR +
  compiler, argument, knowledge-state, evidence, QC, mediated read,
  evaluation fabric (+ Praxis semantic-loss) before inventing anything.
  Required: (a) forward preservation (lost/weakened/distorted/
  disconnected knowledge); (b) backward grounding (unsupported claims,
  new conclusions, altered certainty, invented relations, ungrounded
  additions); (c) authorized knowledge changes recognised as
  corrections via PUB-03 reconciliation (never misclassified as loss);
  (d) pedagogical recovery via independent reader probes
  (model-reader vs human-reader distinguished; negative controls that
  pass lexical checks while failing semantic/epistemic integrity
  included).
- **Mandatory defect attribution (D-PUB-84, author requirement):**
  every candidate defect is attributed to source vs transformation
  (inherited / introduced / strengthened-or-weakened / preserved
  unresolved / authorized evidence-backed correction / resolved), and
  every reviewer quotation is checked for existence in the cited
  version (out-of-scope citation → attribution investigation; text in
  neither version → invalid review evidence). Seven negative controls
  are mandatory, including the redundant/defensive-synthesis class
  (run-1 line 138) that passes lexical preservation. An inherited
  defect may block release without invalidating an unrelated
  improvement.
- **Depends on:** PUB-02, PUB-04 findings to validate. **Gates:** no thresholds
  promoted without held-out evidence; no reader claims without human data.

## PUB-09 — Mission Control Publication section

- Extend existing surfaces (no new top-level page by assumption — ADR-007):
  `/writer` queue + project quality tabs + `BookPublishingPage`, backed by
  `/api/publication`, consuming Writer/Workbench evidence by reference:
  overview, inspection, editing loop (propose/correct/review/accept/revise),
  release gates (mandatory checks, identity/digest, approvals, deployment
  verification).
- **Depends on:** PUB-01 (quality surface), PUB-07 (workflow state), U3/U4.
  **Gates:** all displayed claims traceable to owning-system evidence ids.

## PUB-10 — Jev end-to-end enhancement and publication

- Full workflow on the Book of Jev: inspect → reconcile → eliminate cruft →
  reduce complexity → reconstruct progression → improve representation →
  strong-model enhancement → independent validation → surgical corrections →
  artifact validation → author release approval → publish.
- **Depends on:** PUB-02…09 all operational. **Gates:** ACCEPTANCE.md
  programme-completion rules (transformation demonstrated, defects fixed,
  artifacts verified — score ~950/1000 is necessary but never sufficient).

## PUB-11 — Reuse across the wider portfolio

- Generalize from Jev: registry-driven books, per-genre calibration, portfolio
  queue in Mission. **Depends on:** PUB-10 proof. **Gates:** second-book
  replication with independent validation before claiming generality.

## Deferred / explicitly not scheduled

Experiment reruns with paid models, DB migrations, publication deployment,
broad refactors — recorded in STATE.md, never smuggled into stage scope.
