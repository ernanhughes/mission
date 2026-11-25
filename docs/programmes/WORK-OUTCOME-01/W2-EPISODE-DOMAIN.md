# W2-EPISODE-DOMAIN — Minimum viable episode model

Reconciles W0-WORK-EPISODE-CONTRACT names to the W2 implementation. Only the
reconstruction subset is implemented; requirement/outcome/evaluation/finding/
obligation/follow-up entities remain W3+.

## Implemented (`wo_episodes`, `wo_episode_associations`, `wo_recon_runs`)

- `WoEpisode(id, project_key, title, kind, status, parent_id, first/last_seen_ms,
  source_digest, version)`. `id` is stable and human-debuggable:
  `ep:task:<SLUG>` (task/stage/programme by identifier),
  `ep:chain:<root-session>` (parent-linked session groups),
  `ep:cluster:<digest>` (file/SHA-seeded groups),
  `ep:unresolved:<project>` (single abstention bucket per project scope).
  `kind ∈ {programme, stage, task, chain, cluster, unresolved}`.
  `status ∈ {candidate, established, superseded}` — reconstruction status only,
  never outcome completion (no `complete` value exists at this stage).
  `parent_id` is plain text with service-side cycle rejection (no FK ordering
  hazard). Titles are mechanical (identifier, chain root, bucket label) —
  objectives are never invented.
- `WoEpisodeAssociation(id, episode_id, assoc_type, target_ref, method,
  confidence, reason, signals, recon_version, valid)`. `assoc_type` ∈
  {session, commit, repository, review_of, signal}. `method` ∈
  {explicit, derived, candidate, rejected}. `confidence` ∈
  {explicit, strong, moderate, weak} — heuristic labels, never probabilities.
  `UNIQUE(episode_id, assoc_type, target_ref, method)` makes replay idempotent;
  `valid=0` retires superseded links without deleting history. Rejected
  markers without an episode home live in run stats, not rows.
- `WoReconRun(id, status, scope, episodes_found, associations_made,
  unresolved_observations, error)` — append-only run ledger.

## Deliberately deferred to W3+

Objective text, Requirement rows, Evidence/Outcome/Evaluation/Finding/
Obligation/FollowUp entities, completion semantics. The domain is shaped so
all three later perspectives (execution, outcome, completion quality) can
attach to episode + association rows without restructuring.
