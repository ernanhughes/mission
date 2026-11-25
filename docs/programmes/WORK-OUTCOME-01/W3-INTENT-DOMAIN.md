# W3-INTENT-DOMAIN — Minimum semantic entities

Reconciles the W0 contract's provisional names to the W3 tables
(`043_work_intent`). Requirement/outcome *evaluation* stays W4; this stage
records what was intended, claimed, and what evidence might bear on it.

## Implemented (`wo_objectives`, `wo_requirements`, `wo_claims`,
`wo_evidence_links`, `wo_triage_results`, `wo_extraction_runs`)

- `WoObjective(episode_id, text, authority, status, version, supersedes,
  source_digest, extractor)`: one row per extracted objective statement.
  `authority ∈ {user_direct, accepted_proposal, inferred}`; multiple
  objectives per episode allowed; refined objectives supersede (never edit).
  `UNKNOWN` when intent cannot be established — never an invented objective.
- `WoRequirement(episode_id, objective_id?, text, authority, mandatory, kind,
  state, version, supersedes, source_digest, extractor)`: atomic, W4-testable.
  `authority` per W3-REQUIREMENT-AUTHORITY (10 classes);
  `kind ∈ {functional, constraint, gate}` (restrictions and acceptance gates
  are requirements, §11); `state ∈ {proposed, accepted, deferred, superseded,
  ambiguous}` — reconstruction state, not satisfaction.
- `WoClaim(episode_id, claimant, text, scope, source_ref, qualified,
  evidence_available)`: material participant assertions with their
  qualifications preserved. A claim row is never evidence of its own truth.
- `WoEvidenceLink(requirement_id?, claim_id?, evidence_kind, evidence_ref,
  source_digest, method, confidence)`: candidate bindings W4 will judge.
  `evidence_kind` reuses existing contracts (git_commit, test_report,
  code_review, migration_record, workbench_manifest, …). Stale-revision links
  carry the revision in `evidence_ref` and are never silently current.
- `WoTriageResult(session_id, classification, method, reason,
  queued_for_model, run_id)`: deterministic or model verdicts; `UNIQUE
  (session_id, run_id)` for idempotent reruns.
- `WoExtractionRun(…, schema/prompt/extractor versions, input_digest, status,
  error, cost/tokens/latency)`: ledger + idempotence cache
  (`UNIQUE(input_digest, schema, prompt, extractor)`) + budget source.

## Naming reconciliation

W0 `Evidence` → `WoEvidenceLink`; `Finding/Obligation/FollowUp` →
deferred to W4/W7 (W3 binds candidates only); `Observation/SourceReference/
EpisodeAssociation` → W1/W2 rows reused by reference, not duplicated.
`Constraint/AcceptanceCriterion/Decision/Exclusion/Deferral` →
`WoRequirement` rows with `kind`/`authority`/`state` (single table, no
taxonomy sprawl). `ObjectiveVersion/RequirementVersion` → versioned rows with
`supersedes`. `SemanticExtraction` → `WoExtractionRun` + produced rows.
