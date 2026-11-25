# W0-PERSISTENCE-AND-SECURITY — Derived episode storage + guardrails

Verified 2026-11-24 by read-only inspection. No migrations run, no DB writes.

## 1. Current persistence

- Operational DB is PostgreSQL via `MC_DSN` only (`config.py:59-99`, `normalize_database_url`, `require_operational_database_url`). Engine `pool_pre_ping, pool 5+5, timeouts` (`persistence/db.py:46-88`). SQLite only for isolated unit tests + one-shot legacy migration utility (read-only).
- Post-cutover: 89 app tables + `schema_migrations`, ~146k records, PG `mc` authoritative; SQLite retained as migration source/recovery asset (`docs/MC-POSTGRES-01-REPORT.md`).
- Convention (`models.py:1-10`): column-level `ForeignKey`, no `relationship()`; parents `flush()` before children (pinned by `test_persistence_conventions`).
- Migrations (`persistence/migrations.py`): SQLite `NNN_*.sql` applied once; PG fresh-install baseline from ORM `create_all` bound to highest legacy version + `*.pg.sql` deltas; `schema_migrations(version,name,applied_at)`. Max seen: `040_script_bigint.pg.sql`.
- Seed (`persistence/seed.py:514-754`): get-or-create only, never overwrites; reads `config/defaults/*.yaml`; seeds roots, settings (`retention`, `ai` defaults), outcomes/projects/books/apps, cultivation catalogue, one `record_activity(dedupe_key=seed-initial-workspace-v1)`.

Key tables: `applications/launch_definitions/process_instances/health_observations` (001); `projects/books/outcomes/work_checkpoints/tasks/recommendations/decisions/activity_events/briefings` (001); `integration_records/decisions/executions` (002); `experiment_workflows/workflow_events/language_observations` (003/004); `research_chat_sessions/messages` (006); `git_repositories/git_commits(PK repo_id,sha)/git_reviews/git_review_feedback` (007); cultivation (008-011); quality manuscript/technical/publication/website/software/script families (012-040); `praxis_proposals` (033).

## 2. Existing evaluation storage (precedent, not to duplicate)

Append-only observation + separate verdict pattern throughout:

- Manuscript prose: `quality_evaluations` (chapter_revision, rubric/version, prompt/actual model, NULL-able overall, dimensions, findings, uncertainty, limitations, previous_evaluation_id, campaign_id) + `quality_campaigns` + `quality_reviews` (author verdicts).
- Technical: `technical_claims/evidence/verifications/regions/extraction_coverage/requirements/links/gaps/objectives`.
- Publication: `assessments/preflights/gate_results/issues/approvals/calibration_reviews`; full preflight report as dossier file, only identity/fingerprints in row.
- Software quality: `software_charters/evaluations/eval_reviews/findings/finding_reviews/prompts`; evidence manifest bounded (`MAX_FILES=500, MAX_EXCERPT=8000, MAX_TOTAL=90k, MAX_PACKAGE=26k`).
- Git reviews: `git_reviews` already stores `prompt/prompt_hash/diff_hash/context_fingerprint/evidence_coverage/usage_info`; `research_chat_sessions/messages` store `context_snapshot/fingerprint/model_route` + sequenced messages.
- **No `episode` table exists** (grep `episode` over `backend/` returns zero). Closest: per-commit/per-day/per-campaign evidence + review + author-verdict triple; `research_chat_sessions`-style `session + sequenced messages` with fingerprints is the natural precedent.

## 3. Proposed derived-episode store (W1/W2, not created in W0)

- New tables only (migration `041_*.pg.sql` + ORM models following conventions): `work_episodes`, `episode_requirements`, `episode_observations/source_references/associations/execution_actions/commit_associations/evidence/outcomes/evaluations/findings/obligations/followups` (names provisional; reconcile with `Task/ExperimentWorkflow/quality_*` before finalising — see contract doc).
- Store fingerprints + digests, never full conversation dumps: `(source_digest, rubric_version, evaluator_identity)` cache key; `prompt_hash/diff_hash/context_fingerprint/snapshot_fingerprint` carried over from git/review pattern.
- Original conversations stay in OpenCode DB (read-only source). Retain only excerpts + locators + redacted evidence needed for audit.
- Idempotent replay: stable IDs (e.g. `episode_id = sha1(programme|objective|repo_set|base_sha)` or ULID with dedupe key), `observed_at/evaluated_at` + `stale` derived at read (same as `review_stale`), never overwrite prior evaluations — new row supersedes.

## 4. Secrets, retention, directories

- Rule (`docs/SECURITY.md`, `config.py:1-6`): keys live in process env, read at request time; only name + presence returned; logs redacted; secret-like keys stripped from API responses.
- Enforcement points: `core/logging.py:12-24 redact_text` + `RedactionFilter`; `processes/manager.py` redacted previews + log rewrite (≤5MB); `activity_git/service.py:74-82,219-228 SECRET_PATTERNS + redact_secrets` on every diff/prompt slice (count recorded); `config.py:23-33 _redact_url` for DSN; `settings/service.py` rejects secret fields, `ai.api_key_env` name-pattern only; `integrations/service.py:70-79 _safe_config`; `briefing/service.py` + `research/inference.py` read key at call time, `trust_env=False`; `quality_software/evidence.py` reuses `redact_secrets`; `api/inspect_proposals.py:54-63 _redact`.
- Residual risks (`docs/SECURITY.md:184-199`): same-user can read DB/logs; `data/` unencrypted; external apps may log before on-read redaction; Next PG credential in env (read-only grants are the defence).
- Retention configured only, **not enforced**: `retention:{activity_days:365, briefing_days:90, log_days:30}` validated but no janitor deletes (grep `purge|prune` finds only unrelated draft-expiry). No auto-delete for new episode tables either — explicit policy required in W6.
- `data/` layout (git-ignored, overridable via `MISSION_CONTROL_DATA_DIR`): `backups/` (snapshots + `mc-pg-pre-cutover-20261124.dump`), `experiments/`, `integrations/{next,worker,cocoder}/`, `logs/` (`RotatingFileHandler 2MB×5`, process `proc-*.log`), `publication_dossiers/`. Log dirs verified `is_within(log_dir)` on read.

## 5. Security constraints for sending history to AI

From `docs/SECURITY.md`, `docs/MC01-ARCHITECTURE.md`, verified call sites:

1. Loopback-only; non-loopback startup refused; origin guard + `X-Mission-Control-Request: 1`.
2. No shell / no browser-supplied executable/cwd/command; stored `launch_id` only.
3. Registered adapter actions with schema-validated params only; CoCoder repo must be registered, refs charset-restricted.
4. No `..`/device/relative paths; Next SQLite `mode=ro`; Next PG read-only transaction + SELECT-only.
5. Children get Windows essentials + named vars only.
6. Keys never stored/returned (name + presence); DSNs by env name; `_safe_config` strips secrets; redaction on logs/prompts/evidence.
7. AI boundary: disabled by default; needs enablement + consent + endpoint/model; cannot execute tools; explicit calls only. Note discrepancy: current seed defaults `ai:{enabled:True, consent:True}` (Pi-first treated as sufficient; loopback required only for local override) — re-confirm before W4 model calls.
8. Briefing AI receives only grounded `BriefingItem`s (rank/title/project/rationale≤1000/provenance/evidence≤5); prompt forbids invention; response JSON ≤3 items; failure retains deterministic briefing with `ai_unavailable`.
9. Research chat local-only: non-loopback `base_url` refused, no silent remote fallback; model must be configured/catalogue-proven; fail-closed.
10. Git-to-model: secret-redacted, per-commit + day budgets (`diff_max 120k`, `prompt_max 60k`, hard cap 95k), partial/omitted commits labelled PARTIAL never silently dropped, absolute paths stay server-side, historical `AGENTS.md/DESCRIPTION.md` preferred with source labels, `redaction_count/coverage/truncated` recorded alongside.
11. No telemetry/outbound except configured health checks + explicit AI/briefing calls. Generated code only in Docker (`--network none`, RO mounts, caps) or not at all. Worker loopback HTTP unauthenticated — constrain what is submitted.

Evaluator must treat source conversations/repo text/tool output as **untrusted data**; embedded instructions are never executed. Evaluator must not mutate repos, create commits, deploy, or execute follow-ups. Follow-up execution reuses existing integration/ActionSpec confirmation machinery.
