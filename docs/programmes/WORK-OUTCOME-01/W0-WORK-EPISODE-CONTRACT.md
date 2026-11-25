# W0-WORK-EPISODE-CONTRACT — Durable domain object

Names provisional; reconcile with `Task/ExperimentWorkflow/quality_*/research_chat_*`
before W1 migration. No tables created in W0.

## 1. Definition

A **Work Episode** is a coherent piece of work undertaken to achieve an identifiable
objective. It may span multiple OpenCode sessions, users, models, repos, commits,
uncommitted states, review cycles, and non-code outcomes. A conversation is not a task;
a commit is not completion.

## 2. Entities

- `WorkEpisode(id, programme_id, objective, status, created_at, updated_at, stale_reason)`
  `id`: stable ULID with dedupe key `sha1(programme|objective|repo_set|base)`; never reused.
- `Objective(what was wanted; source quote + locator, not paraphrase-only)`
- `Requirement(episode_id, seq, text, kind {functional, test, integration, deployment, research, doc},
  mandatory bool, state {requested, reported, observed, tested, verified, integrated, demonstrated, complete, incomplete, blocked, unknown, na},
  provenance {observed, claimed, inferred, verified})`
- `Observation(episode_id, kind, source_digest, excerpt_redacted, locator, observed_at)`
  Kinds: message excerpt, tool call, file change, test output, review finding, human note.
  Locator: `(opencode_session, msg_seq, part_ordinal)` / `(repo_id, sha, path, hunk)` / `(review_id)`.
  Never store full conversation bodies; excerpts ≤800 chars + fingerprint.
- `SourceReference(kind {opencode_session, opencode_message, git_commit, git_review, file_state, test_run, workbench_decision, human_note}, ref, digest)`
- `EpisodeAssociation(episode_id, source_ref, relation {addresses, implements, tests, reviews, blocks, follows_up}, confidence {explicit, strong, moderate, weak}, evidence, inferred_by, decided_at)`
  Ambiguous stays ambiguous: `confidence=weak` + `unresolved=true` until confirmed.
- `ExecutionAction(episode_id, session_id, tool_name, summary_redacted, digest, ts)` — observed facts, not claims.
- `CommitAssociation(episode_id, repo_id, sha, signal, confidence, evidence)` — many-to-many; see correlation design.
- `Evidence(episode_id, requirement_id?, kind {commit_diff, test_report, review, observation, demo, doc},
  digest, source_ref, redaction_count, truncated bool, captured_at)`
- `Outcome(episode_id, summary, state {not_started, in_progress, partial, implemented, verified, integrated, complete, blocked, unknown}, decided_at, decided_by {rule, evaluator_id/rubric_version})`
- `Evaluation(episode_id, requirement_id?, dimensions JSON, verdict, evaluator {rule, model, human}, rubric_version, source_digest, cost/tokens/latency, created_at, supersedes?)`
  Append-only; new row supersedes, never overwrites (precedent: `quality_evaluations`, `git_reviews`).
- `Finding(episode_id, severity {blocker, major, minor, note}, text, evidence_ref, state {open, confirmed, dismissed, resolved})`
- `Obligation(episode_id, requirement_id?, text, kind {mandatory, recommended}, state {open, in_progress, resolved, waived, obsolete}, provenance, resolved_by_ref?)` — see lifecycle doc.
- `FollowUp(obligation_id, action {re_run_tests, add_coverage, merge, deploy, demo, doc, new_episode}, status, created_episode_id?)`
  Evaluator never executes follow-ups; execution reuses ActionSpec/confirmation machinery.

## 3. Observed vs claimed vs inferred vs verified

- **Observed:** rows in `opencode.db` (`mode=ro`), `git_commits` diffs, test artifacts, review rows.
- **Claimed:** assistant text asserting done/passed/merged ("implementation complete") — stored as `Observation(kind=claim)` with locator, never as `Outcome.complete`.
- **Inferred:** `EpisodeAssociation(confidence<explicit)` with signal list + scorer version.
- **Verified:** independent check (re-executed test, re-read diff, second-model review, human accept) with its own digest + identity.

Completion rule: `Outcome.complete` iff every `mandatory Requirement.state ∈ {complete, na}` with `verified` or `demonstrated` evidence as the requirement kind demands. `reported` alone never completes.

## 4. Identity, versioning, provenance, lifecycle

- Identity: `episode_id` ULID; dedupe key prevents duplicates on re-scan.
- Versioning: requirements/evaluations/outcomes append-only with `supersedes`; reads resolve latest + `stale` when `source_digest` changed (same pattern as `review_stale/snapshot_fingerprint`).
- Provenance: every row carries `source_digest + source_ref + inferred_by + confidence`. Weak links stay labelled.
- Lifecycle: `not_started → in_progress → partial/implemented → verified → integrated → complete`, with `blocked/unknown` side states. Non-code episodes (research/doc) use subset (no `integrated` unless deployment required).
- Retention: no auto-delete (matches current no-janitor policy); explicit W6 policy required.
- Security: excerpts redacted via `redact_secrets`; absolute paths stay server-side; evaluator treats sources as untrusted (no instruction execution); no auto-mutation.
