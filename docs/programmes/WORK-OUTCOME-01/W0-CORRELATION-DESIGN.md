# W0-CORRELATION-DESIGN — Deterministic-first, many-to-many

## 1. Principle

Timestamps alone never establish belonging. Every inferred link retains signals,
confidence, and scorer version. Abstain when evidence is insufficient.

## 2. Signals (verified availability)

| Signal | Strength | Availability (verified) |
| ------ | -------- | ----------------------- |
| Explicit SHA in message/tool output | Very strong | `session_part(type=tool)` data + `session_message` bodies; parse `[0-9a-f]{40}` + short SHAs; must confirm SHA exists in `git_commits` |
| Recorded git tool execution | Very strong | `session_part(type=tool, name~git)` + `call_id`; needs W1 parser for argv (commit/push/rev-parse) |
| Explicit task/programme ID | Strong | No native field today; search message text + `Task.id/ExperimentWorkflow.id`; future harness should emit `WORK-OUTCOME-01`/episode IDs |
| Repo + branch identity | Strong context | `session_v2.directory/path` + `project.worktree` (NOT NULL) vs `GitRepository.path/repo_uid/branch`; `project.name` often NULL, `project_directory` 0 rows — do not rely on them |
| Exact file paths + change overlap | Moderate–strong | Tool file args vs `commit_stats` paths / `file_diff` names; normalise Windows paths; respect `.workbench` exclusion caveat |
| Test linked to source digest | Strong | Test artifact with recorded `sha/diff_hash/context_fingerprint`; unlinked today — W2 join required |
| Session + commit timestamps | Weak alone | ms-epoch `time_created/updated` vs `committer_ts`; usable only as corroboration inside repo/window |
| Semantic similarity | Supporting only | `ai.*` retrieval/embedding (`RetrievalService`) as last resort; never sole basis |

## 3. Model

Many-to-many: one session → many commits; one commit → many requirements/sessions;
some sessions → zero commits (research/doc). Tables: `EpisodeAssociation` +
`CommitAssociation(episode_id, repo_id, sha, signals[], confidence, scorer_version)`.

Confidence: `explicit` (SHA/tool-ID match + existence check) → `strong` (repo+branch+file overlap + ID)
→ `moderate` (file overlap + window) → `weak` (time/semantic only). `weak` alone ⇒
`unresolved=true`, surfaced for human confirm, never auto-completed.

## 4. Hard cases (verified current behaviour)

- **Uncommitted/stash:** not indexed; no `status/stash` reader. W1: optional worktree snapshot observer (hashes only) or explicit "uncommitted" evidence kind; never claim clean/dirty without reading.
- **Squash:** flat commits, no patch-id link. W2: `git patch-id` on diffs + trailer parse (`cherry picked from`) as supporting signal.
- **Rebase/amend/force-push:** new SHAs, old linger `reachable=False`. W2: `refs_snapshot` drift detector + `old→new` map via patch-id; GC policy for unreachable (mark, never silently delete; reviews survive).
- **Cherry-pick:** independent rows. Trailer + patch-id supporting only.
- **Merges:** first-parent diffs; `branches_for` tip-only. Episode totals need per-file distinct accounting (current `files_changed_distinct=None, estimated=True` insufficient).
- **Cross-repo:** no multi-repo prompt/snapshot today. W2: per-repo manifests + union `snapshot_fingerprint`; range prompts composed per repo under global budget.
- **Deletes:** cascade with no tombstones; `event` table 0 rows. Periodic re-census; vanished IDs marked `source_missing`, not silently dropped.
- **`.workbench`:** excluded from index (`EXCLUDED_DIRS`, seed). Episode runner outputs invisible unless allow-listed per root in W1 config.

## 5. Pipeline (W1/W2)

Deterministic stages (no model): session/message census → repo/activity census →
SHA/task/file-path extraction → repo-identity join → file-overlap join → candidate episodes
(union by shared signals) → confidence scoring → abstain on weak-only.
Hybrid/AI only after: requirement extraction (cheap model), ambiguous tie-break (hybrid),
requirement satisfaction + gaps (AI with evidence), contested/critical (strong model).
Cache: `(source_digest, rubric_version, evaluator_identity)` — never pay twice for same input.

## 6. Future instrumentation (W8)

Propagate explicit IDs instead of inferring: OpenCode session metadata / Workbench invocation /
review commission / commit trailer (`Episode: <id>`, `Task: <id>`) / `ExperimentWorkflow` linkage.
Historical inference gives way to explicit instrumentation; deterministic engine stays as fallback.
