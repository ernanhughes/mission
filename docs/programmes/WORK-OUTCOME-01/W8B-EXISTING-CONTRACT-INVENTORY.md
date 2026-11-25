# W8B-EXISTING-CONTRACT-INVENTORY — Reuse, not duplication

Surveyed read-only 2026-11-25 (mission, worker, workbench, sidecar, ai,
praxis, writer, cocoder, aitest; `C:\Projects\pi` does not exist).
Every identity below already exists; W8C reuses them. No new bus,
registry, or executor is introduced.

## Work / execution identity (existing)

- Mission `WoEpisode.id` (`ep:task:…`) — reconstructed work identity;
  `parent_id` for sub-work. Owner: Mission Control.
- Mission `WoProposal.id` (`wp:…`) + `scope_hash` + `WoProposalEvent`
  (actor, from→to) — corrective commission + digest-bound approval.
  Owner: Mission Control.
- Worker `WORK_REQUEST_SCHEMA=worker.work-request.v1` — `request_id`
  (`wrq_<sha32>`), caller-supplied `task_id`/`episode_id`, `operation_id`,
  `stage_id` (`worker.ts:263`, `request.ts:3-22`, `core/worker.ts:40`).
  Worker ACCEPTS external episode ids (execution-summary
  `episode_link: caller_supplied_unverified`). Propagation point.
- Worker `WORK_RESULT_SCHEMA=worker.work-result.v1` — `request_id`,
  `work_id`, `run_id`, `acceptance_id`, `execution{backend,model?}`,
  `provenance{…}`. Execution receipts + `ExecutionSummary`
  (`execution-summary.v1`: requested vs OBSERVED model).
- Workbench `run_id` (`ci-<hex16>`), `invocation_id`, artifact
  `{artifact_id,sha256}`, `admission_id` (`adm-<sha16>`), journal/outbox
  envelope `(seq,id,type,run_id,payload,occurred_at)`. No "commission"
  term — runs are the unit.
- Sidecar: Pi/Senpi `session_id` events (`session.observed`,
  `message/tool/turn.completed`, results with findings/coverage/
  freshness). Gap: NO OpenCode session linkage — sidecar cannot see
  OpenCode work. W8 must not pretend otherwise.
- AITest: `aitest.event.v1` (`event_id` idempotent), receipts
  (`execution_id`, counters, `created_at`), tests (`relpath…last_outcome`),
  issues. Revision proxy = `source_snapshot_id` + versions (no raw SHA;
  git facts live in `git_commits`).

## Evidence / authorization (existing)

- ai experiments: frozen `ExperimentPlanDTO` (plan_fingerprint sha256),
  `AuthorizationRequestDTO` (planner cannot self-authorize),
  `EvaluationDTO` (independent verdict), `ResearchFeedbackDTO`.
- Mission: `GitReview` (verdict/findings/evidence_coverage),
  `IntegrationExecution` (approval gate + receipt), `WoEvidenceLink`,
  `WoRequirementConfirmation`, `WoFinding` closure evidence.
- cocoder: `MessageEnvelope` (`correlation_id`, `causation_id`) — the
  cross-system correlation pattern to copy.
- praxis: `manifest_digest`, effectiveness records (advisory only).
- ECK (writer): `ExecutionPolicy` gates, strategy profiles, lesson
  aggregation, skill learning loop — a learning consumer, not a
  duplicate evaluator.

## The reuse decision (binding)

The Work Envelope carries Mission Control's episode/objective/
requirement/authorization identities INTO worker `task_id/episode_id`
fields, workbench `run_id` metadata, and AITest linkage rows — never
minting parallel work ids. Correlation uses the cocoder
correlation/causation pattern. New storage is limited to the envelope
row itself + link columns on the existing execution-link table.
