# MC-POSTGRES-01 — Source inventory (G01)

Source database: `C:\Projects\mission\data\mission_control.db` (SQLite, WAL mode,
`PRAGMA foreign_keys=ON`, busy timeout 30 s).

- Source tables: **90** (89 application tables + `schema_migrations`; excludes
  internal `sqlite_sequence`).
- Source records: **146465** across all tables (final pre-cutover snapshot
  `data/backups/mission_control-pre-pg-migration-FINAL-20261124T090600Z.db`).
- Migration tracking: `schema_migrations` version **39** (`001_initial` …
  `039_website_post_writer_observations`).
- Pre-existing integrity: `PRAGMA integrity_check` = ok,
  `PRAGMA foreign_key_check` = no violations.

## Tables (rows in final snapshot)

| Table | Rows | Owning subsystem |
| ----- | ---- | ---------------- |
| activity_events | 1108 | continuity/registry |
| adapter_statuses | 9 | integrations/workbench |
| applications | 11 | registry |
| artifact_load_observations | 3 | quality/artifact-load |
| books | 41 | books/publishing |
| briefings | 1 | briefing |
| cultivation_app_repos | 0 | cultivation |
| cultivation_applications | 0 | cultivation |
| cultivation_cycle_goals | 8 | cultivation |
| cultivation_cycles | 2 | cultivation |
| cultivation_events | 623 | cultivation |
| cultivation_evidence | 0 | cultivation |
| cultivation_github_repos | 306 | cultivation/github |
| cultivation_goals | 15 | cultivation |
| cultivation_items | 471 | cultivation |
| cultivation_measurements | 149 | cultivation |
| cultivation_memberships | 165 | cultivation |
| cultivation_repo_states | 306 | cultivation |
| cultivation_skills | 15 | cultivation |
| cultivation_sources | 5 | cultivation |
| decisions | 19 | projects |
| discovery_roots | 4 | discovery |
| experiment_workflows | 18 | execution/governance |
| git_commits | 12779 | activity/git |
| git_repositories | 110 | activity/git |
| git_review_feedback | 0 | activity/git |
| git_reviews | 0 | activity/git |
| health_observations | 125273 | processes/health |
| integration_decisions | 12 | integrations |
| integration_executions | 36 | integrations |
| integration_records | 950 | integrations/workbench |
| language_observations | 5 | execution/governance |
| launch_definitions | 11 | processes |
| library_syntheses | 1 | scripts |
| outcomes | 4 | registry |
| praxis_proposals | 16 | praxis |
| process_instances | 109 | processes |
| project_identity_decisions | 39 | projects/identity |
| project_relationships | 4 | projects |
| project_repositories | 90 | projects |
| projects | 81 | projects/books |
| publication_approvals | 0 | publication |
| publication_assessments | 2 | publication |
| publication_calibration_reviews | 202 | publication |
| publication_followups | 0 | publication |
| publication_gate_results | 16 | publication |
| publication_issues | 3 | publication |
| publication_preflights | 2 | publication |
| quality_campaigns | 10 | quality |
| quality_evaluations | 103 | quality |
| quality_reviews | 2 | quality/writer |
| recommendations | 4 | projects |
| repositories | 166 | discovery/registry |
| research_chat_messages | 0 | research |
| research_chat_sessions | 0 | research |
| script_batch_items | 0 | scripts |
| script_batches | 0 | scripts |
| script_candidates | 2 | scripts |
| script_events | 131 | scripts |
| script_links | 12 | scripts |
| script_migrations | 1 | scripts |
| script_records | 67 | scripts |
| script_reviews | 0 | scripts |
| script_tags | 0 | scripts |
| settings | 17 | system/preferences |
| software_charters | 0 | software quality |
| software_eval_reviews | 0 | software quality |
| software_evaluations | 0 | software quality |
| software_finding_reviews | 0 | software quality |
| software_findings | 0 | software quality |
| software_prompts | 0 | software quality |
| tasks | 0 | projects |
| technical_claim_links | 0 | quality/technical |
| technical_claims | 1251 | quality/technical |
| technical_evidence | 33 | quality/technical |
| technical_evidence_requirements | 475 | quality/technical |
| technical_extraction_coverage | 197 | quality/technical |
| technical_extraction_runs | 74 | quality/technical |
| technical_gaps | 471 | quality/technical |
| technical_objective_claims | 9 | quality/technical |
| technical_objectives | 3 | quality/technical |
| technical_regions | 86 | quality/technical |
| technical_requirement_links | 43 | quality/technical |
| technical_verifications | 61 | quality/technical |
| website_post_evaluations | 2 | websites |
| website_post_reviews | 0 | websites |
| website_post_writer_observations | 0 | websites |
| work_checkpoints | 1 | continuity |
| workflow_events | 181 | execution/governance |
| schema_migrations | 39 | migration history |

Empty tables were migrated as empty schemas (no silent omission). No
application-owned table exists outside this list. External databases
(OpenCode `opencode.db`, Next `next.db`, worker stores) are read-only
neighbors and were explicitly NOT migrated.
