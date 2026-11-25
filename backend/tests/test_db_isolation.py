"""Hard safeguards against tests touching operational databases (MC-POSTGRES-02).

These tests run in the normal suite with NO PostgreSQL server and NO MC_TEST_DSN.
They prove that misconfigured test code fails fast — before any engine use or
write — instead of reaching production data.

Background (MC-POSTGRES-01): a test lifespan once created an app with the
default data directory and wrote a blog-sync observation into the live
SQLite database. With PostgreSQL authoritative, the equivalent accident
would target the operational ``mc`` database. Three independent layers
prevent it:

1. ``conftest._isolate_operational_database`` strips MC_DSN (and the legacy
   override) for every test — no implicit inheritance.
2. ``Database`` refuses non-isolated targets while ``PYTEST_CURRENT_TEST``
   is set — PostgreSQL other than exactly MC_TEST_DSN, or the production
   repository SQLite file.
3. Destructive PG fixtures validate the actual connected database identity
   (see test_postgres_integration.pg_database).
"""

from __future__ import annotations

import os

import pytest

from mission_control.config import DatabaseConfigurationError, RuntimeSettings


def test_operational_dsn_stripped_by_default():
    # Layer 1: no test inherits MC_DSN implicitly.
    assert "MC_DSN" not in os.environ
    assert "MISSION_CONTROL_DATABASE_URL" not in os.environ


def test_production_sqlite_file_refused():
    # The exact MC-POSTGRES-01 accident: default settings resolve to the
    # live repository SQLite file. Must raise before any engine use.
    from mission_control.persistence.db import Database

    settings = RuntimeSettings()
    assert settings.database_url.startswith("sqlite")
    assert "mission_control.db" in settings.database_url
    with pytest.raises(DatabaseConfigurationError, match="production SQLite"):
        Database(settings)


def test_non_test_postgres_refused(monkeypatch: pytest.MonkeyPatch):
    # A test that (mis)configures a production-like DSN must fail before any
    # connection is attempted — no network traffic, no writes.
    from mission_control.persistence.db import Database

    monkeypatch.setenv("MC_DSN", "postgresql://mc:mc@localhost:5432/mc")
    monkeypatch.delenv("MC_TEST_DSN", raising=False)
    with pytest.raises(DatabaseConfigurationError, match="non-test PostgreSQL"):
        Database(RuntimeSettings())


def test_explicit_test_dsn_passes_guard_without_connecting(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
):
    # The guard allows exactly MC_TEST_DSN. Engine creation is lazy, so this
    # proves acceptance without needing a live server.
    from mission_control.persistence.db import Database

    monkeypatch.setenv("MC_DSN", "postgresql://mc:mc@localhost:5432/mc_test")
    monkeypatch.setenv("MC_TEST_DSN", "postgresql://mc:mc@localhost:5432/mc_test")
    database = Database(RuntimeSettings(), target="test:mc_test")
    assert database.is_postgres


def test_tmp_sqlite_allowed(tmp_path):
    # Isolated tmp databases (the conftest `runtime` pattern) keep working.
    from mission_control.persistence.db import Database

    settings = RuntimeSettings(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        frontend_dist=tmp_path / "dist",
    )
    database = Database(settings)
    assert not database.is_postgres
    database.dispose()
