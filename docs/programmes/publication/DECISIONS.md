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
  NEEDS_EVIDENCE pattern; `argument.disagreement` cue-then-silence;
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

## Explicitly rejected (appended PUB-03: parallel evidence architecture)

- New `reader_assurance`-style domain, new manuscript parser/scorer/composite,
  new campaign scheduler, new contract schema, new model gateway, `ai.assessment`
  primitive, Mission rescoring lane, diagram quotas, score-before-evaluation.
  Each has a recorded owner decision or a PUB-00 verification behind it.
