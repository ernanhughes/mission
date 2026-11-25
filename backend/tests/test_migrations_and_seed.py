from __future__ import annotations

import yaml
from sqlalchemy import text

from mission_control.config import RuntimeSettings
from mission_control.models import Application
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations, schema_version
from mission_control.persistence.seed import seed_defaults


def test_migrations_are_repeatable_and_create_expected_tables(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    # MC-INSPECT-04: 053 adds inspect_runs; 054 adds AITEST quality evidence.
    # In-flight workstreams contribute 041-052 (work outcome + AITEST tables).
    assert apply_migrations(database) == list(range(1, 40)) + list(range(41, 55))
    assert apply_migrations(database) == []
    assert schema_version(database) == 54
    with database.engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
    for expected in {
        "applications",
        "launch_definitions",
        "projects",
        "books",
        "process_instances",
        "activity_events",
        "work_checkpoints",
        "recommendations",
        "adapter_statuses",
        "discovery_roots",
        "briefings",
        "integration_records",
        "integration_decisions",
        "integration_executions",
        "experiment_workflows",
        "workflow_events",
        "language_observations",
        "research_chat_sessions",
        "research_chat_messages",
        "git_repositories",
        "git_commits",
        "git_reviews",
        "git_review_feedback",
        "cultivation_goals",
        "cultivation_items",
        "cultivation_memberships",
        "cultivation_measurements",
        "cultivation_events",
        "cultivation_evidence",
        "cultivation_skills",
        "cultivation_sources",
        "cultivation_cycles",
        "cultivation_cycle_goals",
        "cultivation_repo_states",
        "cultivation_github_repos",
        "cultivation_applications",
        "cultivation_app_repos",
        "script_records",
        "script_events",
        "script_links",
        "script_migrations",
        "script_reviews",
        "script_batches",
        "script_batch_items",
        "script_tags",
        "library_syntheses",
        "script_candidates",
        "quality_evaluations",
        "quality_campaigns",
        "technical_claims",
        "technical_evidence",
        "technical_verifications",
        "technical_regions",
        "technical_extraction_coverage",
        "technical_evidence_requirements",
        "technical_requirement_links",
        "technical_claim_links",
        "technical_gaps",
        "technical_objectives",
        "technical_objective_claims",
        "publication_assessments",
        "publication_preflights",
        "publication_gate_results",
        "publication_issues",
        "publication_approvals",
        "publication_calibration_reviews",
        "technical_extraction_runs",
        "praxis_proposals",
        "website_post_evaluations",
        "website_post_reviews",
        "website_post_writer_observations",
        "project_identity_decisions",
        "publication_followups",
        "software_charters",
        "software_evaluations",
        "software_eval_reviews",
        "software_findings",
        "software_finding_reviews",
        "software_prompts",
        "wo_observation_sources",
        "wo_observation_runs",
        "wo_checkpoints",
        "wo_signals",
        "wo_episodes",
        "wo_episode_associations",
        "wo_recon_runs",
        "wo_objectives",
        "wo_requirements",
        "wo_claims",
        "wo_evidence_links",
        "wo_triage_results",
        "wo_extraction_runs",
        "wo_requirement_assessments",
        "wo_claim_verifications",
        "wo_episode_assessments",
        "wo_findings",
        "wo_eval_runs",
        "aitest_quality",
        "wo_requirement_sources",
        "wo_finding_groups",
        "wo_finding_group_members",
        "wo_eval_state",
        "wo_proposals",
        "wo_proposal_findings",
        "wo_proposal_events",
        "wo_requirement_confirmations",
        "wo_execution_links",
        "wo_work_envelopes",
        "aitest_projects",
        "aitest_tests",
        "aitest_receipts",
        "aitest_issues",
        "aitest_events_seen",
        "inspect_runs",
    }:
        assert expected in tables
    database.dispose()


def test_seed_does_not_overwrite_user_changes(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    with database.session() as session:
        app = session.get(Application, "next")
        assert app is not None
        app.pinned = False
        app.name = "Next — customised"
        app.notes = "User note"
    with database.session() as session:
        seed_defaults(session, runtime)
    with database.session() as session:
        app = session.get(Application, "next")
        assert app is not None
        assert app.pinned is False
        assert app.name == "Next — customised"
        assert app.notes == "User note"
    database.dispose()


def test_defaults_are_valid_yaml_and_do_not_claim_verified_launches(runtime: RuntimeSettings) -> None:
    applications = yaml.safe_load(
        (runtime.config_dir / "defaults" / "applications.yaml").read_text(encoding="utf-8")
    )["applications"]
    assert {app["id"] for app in applications} >= {"next", "cocoder", "work", "writer", "worker"}
    for app in applications:
        for launch in app.get("launch_definitions", []):
            if launch.get("enabled"):
                assert launch.get("verified") is True, (
                    f"{app['id']} enables an unverified launch definition"
                )
