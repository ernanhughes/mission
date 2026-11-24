# PUBLICATION Acceptance Criteria

## 1. Programme-wide completion rules

The programme is complete only when manuscript transformation is demonstrated and
a book is published through the governed workflow — not when
detectors/APIs/workflows/UIs exist. A book (Jev first) may be marked ready **only
if all hold**:

1. No experiment is incorrectly described (status, conditions, results match
   authoritative evidence).
2. No claim conflicts with authoritative evidence; no important result lost;
   no figure/table stale against its source.
3. No genuine limitation, negative result, methodological amendment or unresolved
   question erased in the name of cleanliness.
4. No technical meaning altered without justification and independent
   re-verification.
5. All required validations passed (research + technical + editorial + rendering
   + artifact), each bound to the exact manuscript revision it checked.
6. Explicit author release approval recorded against the manuscript digest.

Critical defects override any aggregate score. A model-generated score (~950/1000
target) is necessary but never sufficient evidence of readiness.

## 2. Finding and assessment lifecycle (binding on all stages)

`Unassessed → Detected → Confirmed → Proposed correction → Corrected →
Independently verified → Accepted | Blocked | Waived (with rationale)`.
Assessments bind to exact source + evidence revisions and go STALE on change.
Missing evidence is reported as missing, never as success. Unknown stays a named
pending/blocked state, never a silent pass.

### 2.1 Evidence labels, binding and freshness (adopted PUB-01, binding on all later stages)

- Every observation carries exactly one primary evidence label:
  `MEASURED_TEXT`, `MODEL_JUDGEMENT`, `INDEPENDENT_REVIEW`,
  `HUMAN_READER_OBSERVATION`, `CODE_TEST` or `BENCHMARK_RERUN`.
- A model that revised (or will revise) a passage cannot supply its
  `INDEPENDENT_REVIEW`: record `CONFLICTED_MODEL_JUDGEMENT` and keep it
  visible. No green state is ever derived from a model's self-score, and no
  composite book score exists anywhere.
- Every assessment binds `(project_id, manuscript_fingerprint)` (Mission
  `project_id` canonical; Writer registry key validated at save) plus the
  exact evidence revision it was checked against (ledger/result/contract hash).
- STALE triggers (any one invalidates the assessment; re-verification
  required): manuscript bytes changed under the bound fingerprint; evidence
  revision changed; the bound contract/report status changed; the source
  branch moved. `unknown` freshness is reported, never treated as success.
- Lifecycle positions are terminal only with their evidence attached:
  `Corrected` requires the correction diff + new fingerprint; `Independently
  verified` requires a different-model or human verdict with disclosed
  identity; `Waived` requires a rationale naming what is accepted as residual.

## 3. Per-milestone evidence requirements

- **PUB-00:** objectives documented; architecture grounded in live implementation
  (paths cited); relevant Writer capabilities inspected with callable-vs-role
  separation; reuse/gaps recorded; cruft + complexity taxonomies established;
  Jev case study inspected against evidence; stable IDs + dependencies; ownership
  resolved or explicitly open (U1–U5); acceptance defined; next stage specified;
  temp artifacts removed; unrelated working-tree changes untouched. (§12 held —
  see STATE.md verdict.)
- **PUB-01:** PUBLICATION-scoped catalog↔runtime agreement demonstrated (scoped
  `validate_registry` with the live adapter map: only unrelated-owner gaps
  remain — `metadata_generation` missing, 46 unrelated orphans,
  `analysis_state` adapter — recorded as Writer-owned backlog with rationale,
  which satisfies the "green or delisting with rationale" rule for this
  stage's scope; full-registry green explicitly not required here);
  quality-surface decision recorded; provenance/label conventions adopted;
  no manuscript writes.
- **PUB-02/04:** detector + versioned thresholds/profiles; calibration suite with
  dev/held-out split over real passages; false-positive traps documented;
  deterministic-first rationale where models used.
- **PUB-03:** reconciliation reports binding claims to evidence rows for ≥3
  chapters including one stale/missing case; stale-evidence finding type live.
- **PUB-05:** representation recommendations with accuracy + pipeline-support
  justification; comprehension probes on samples with labelled judges.
- **PUB-06:** disposable-fixture apply/undo end-to-end with fingerprint proof;
  staged-change-set design approved before any bulk apply; QC gate results kept.
- **PUB-07:** bridge + proposal wiring tests; provenance on Worker outputs.
- **PUB-08:** held-out calibration results; conflicted-judgement handling
  demonstrated; no reader claims without human data.
- **PUB-09:** every displayed claim traces to an owning-system evidence id +
  source fingerprint; no Mission rescoring or mutation paths.
- **PUB-10:** Jev transformation diff (before/after with preservation proof),
  all §1 rules evidenced, release approval + deployment verification.
- **PUB-11:** second-book replication with independent validation.

## 4. Review and handover rules

Every implementation stage ends with: scope-done vs verified-done split,
incomplete items, risks, changed repos, and the exact next action with its owning
agent type (defaults: Muse design/docs, DeepSeek testing/regression, Codex
architecture/integration review, Claude editorial/pedagogy — inexpensive
deterministic checks before model inference; consequential calls escalated, never
equated with confidence). Model allocation and cost policy: README.md §6
(preferred models + 10 execution rules) is inherited by every stage prompt.
Disagreements preserved in writing. Cleanup per the
lifecycle before handover.
