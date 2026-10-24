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
    assert apply_migrations(database) == [1, 2]
    assert apply_migrations(database) == []
    assert schema_version(database) == 2
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
