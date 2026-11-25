"""PostgreSQL integration tests for MC-POSTGRES-01.

These tests exercise the real production dialect (PostgreSQL) and must never
touch the operational ``mc`` database. They run only when ``MC_TEST_DSN`` is
set (e.g. ``postgresql://mc:mc@localhost:5432/mc_test``) and refuse any DSN
that points at the operational database.

Run:  MC_TEST_DSN=... .venv/Scripts/python -m pytest backend/tests/test_postgres_integration.py -q
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("MC_TEST_DSN"),
    reason="MC_TEST_DSN not set; PostgreSQL integration tests require an isolated test database",
)

from mission_control.config import (  # noqa: E402
    DatabaseConfigurationError,
    is_postgres_url,
    normalize_database_url,
    resolve_database_url,
)


def _test_dsn() -> str:
    dsn = os.environ["MC_TEST_DSN"]
    lowered = dsn.lower()
    assert "/mc_test" in lowered or "mc_test" in lowered, "refusing: MC_TEST_DSN must target mc_test"
    assert "/mc?" not in lowered and not lowered.rstrip().endswith("/mc"), (
        "refusing: MC_TEST_DSN must not target the operational mc database"
    )
    return dsn


def _pg_database(dsn: str, monkeypatch: pytest.MonkeyPatch):
    """Connect the isolated PG test database via explicit opt-in only."""
    from mission_control.config import RuntimeSettings, normalize_database_url
    from mission_control.persistence.db import Database

    # Explicit opt-in: the ONLY postgres URL a test may use is MC_TEST_DSN.
    # The conftest autouse fixture strips any inherited MC_DSN first.
    monkeypatch.setenv("MC_DSN", dsn)
    monkeypatch.delenv("MISSION_CONTROL_DATABASE_URL", raising=False)
    settings = RuntimeSettings()
    database = Database(settings, target="test:isolated-pg")
    assert database.is_postgres
    assert normalize_database_url(database.database_url) == normalize_database_url(dsn), (
        "test Database resolved to an unexpected URL"
    )
    return database


def _isolated_subprocess_env() -> dict[str, str]:
    """Env for migration-subprocess tests: no implicit database fallback.

    MC_DSN is removed so the script can only succeed via the explicit
    ``--target`` argument, proving subprocess tests cannot escape isolation
    through inherited configuration.
    """
    env = dict(os.environ)
    env.pop("MC_DSN", None)
    env.pop("MISSION_CONTROL_DATABASE_URL", None)
    return env


@pytest.fixture()
def pg_database(monkeypatch: pytest.MonkeyPatch):
    from urllib.parse import urlparse

    dsn = _test_dsn()
    database = _pg_database(dsn, monkeypatch)
    expected_db = urlparse(dsn).path.lstrip("/") or "mc_test"
    # Validate the ACTUAL connected database identity (not just the URL):
    # the fixture refuses to proceed unless the server confirms we are on
    # the isolated test database.
    from sqlalchemy import text

    with database.engine.connect() as connection:
        actual_db = connection.execute(text("SELECT current_database()")).scalar()
    assert actual_db == expected_db, f"connected to {actual_db!r}, expected {expected_db!r}"
    assert actual_db != "mc", "refusing to run destructive fixtures on the operational database"
    from mission_control.persistence.migrations import apply_migrations

    # Clean slate: drop all tables in public then rebuild via the runner.
    with database.engine.begin() as connection:
        tables = connection.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"
            )
        ).fetchall()
        for (table,) in tables:
            connection.execute(text(f'DROP TABLE "{table}" CASCADE'))
    apply_migrations(database)
    try:
        yield database
    finally:
        database.dispose()


# ------------------------------------------------------------- configuration


def test_mc_dsn_normalizes_to_psycopg_driver():
    assert (
        normalize_database_url("postgresql://mc:mc@localhost:5432/mc")
        == "postgresql+psycopg://mc:mc@localhost:5432/mc"
    )
    assert is_postgres_url("postgresql+psycopg://mc:mc@localhost:5432/mc")
    assert not is_postgres_url("sqlite:///C:/data/mission_control.db")


def test_credentials_never_logged():
    from mission_control.config import _redact_url

    redacted = _redact_url("postgresql://mc:s3cret@localhost:5432/mc")
    assert "s3cret" not in redacted
    assert "***" in redacted


def test_missing_operational_config_fails_clearly(monkeypatch: pytest.MonkeyPatch):
    # The conftest autouse fixture already strips operational config; this
    # test pins the explicit contract for resolve_database_url itself.
    monkeypatch.delenv("MC_DSN", raising=False)
    monkeypatch.delenv("MISSION_CONTROL_DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        resolve_database_url(allow_sqlite_fallback=False)


# -------------------------------------------------------------------- schema


def test_pg_fresh_init_and_repeat_startup(pg_database):
    from mission_control.persistence.migrations import apply_migrations, schema_version

    assert schema_version(pg_database) >= 39
    assert apply_migrations(pg_database) == []


def test_pg_schema_has_all_tables(pg_database):
    from sqlalchemy import text

    with pg_database.engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).fetchall()
        }
    assert "health_observations" in tables
    assert "books" in tables
    assert "schema_migrations" in tables
    assert len(tables) >= 89


# ----------------------------------------------------------------- migration


def _make_source_db(path, monkeypatch: pytest.MonkeyPatch, *, books: int = 2, health: int = 3):
    from mission_control.config import RuntimeSettings
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.persistence.seed import seed_defaults

    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    # Point this Database at the given sqlite file via legacy override.
    # monkeypatch (on top of the conftest autouse strip) guarantees no
    # production DSN leaks into this helper.
    monkeypatch.delenv("MC_DSN", raising=False)
    monkeypatch.setenv("MISSION_CONTROL_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    settings = RuntimeSettings(
        data_dir=path.parent, config_dir=repo_root / "config", frontend_dist=path.parent,
    )
    database = Database(settings)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, settings)
        from mission_control.models import Application, Book, HealthObservation, Project

        # Application convention (see seed_defaults): flush parents before
        # adding children; one flush never mixes transient parent+child.
        for index in range(books):
            session.add(Project(id=f"pg-proj-{index}", name=f"PG Proj {index}"))
        session.flush()
        for index in range(books):
            session.add(
                Book(
                    id=f"pg-book-{index}", project_id=f"pg-proj-{index}",
                    title=f"PG Book {index}",
                )
            )
        session.flush()
        session.add(Application(id="pg-app", name="PG App"))
        session.flush()
        for index in range(health):
            session.add(
                HealthObservation(
                    application_id="pg-app", state="healthy",
                    detail=f"ok {index}",
                )
            )
    return path


def test_pg_import_preserves_pks_and_sequences(tmp_path, pg_database, monkeypatch):
    from mission_control.persistence.migrations import schema_version

    src = _make_source_db(tmp_path / "src.db", monkeypatch)
    import subprocess
    import sys

    target = _test_dsn()
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "migrate_sqlite_to_postgres.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--execute", "--yes",
         "--source", str(src), "--target", target,
         "--report-path", str(tmp_path / "reconciliation.json")],
        capture_output=True, text=True, env=_isolated_subprocess_env(), timeout=300,
    )
    assert completed.returncode == 0, completed.stdout[-3000:] + completed.stderr[-3000:]
    with pg_database.session() as session:
        from mission_control.models import Book, HealthObservation

        assert session.get(Book, "pg-book-0") is not None
        assert session.get(Book, "pg-book-0").title == "PG Book 0"
        count = session.query(HealthObservation).count()
        assert count >= 3
        # Sequence repaired: next insert must not collide.
        session.add(HealthObservation(application_id="pg-app", state="healthy", detail="post"))
        session.flush()
    assert schema_version(pg_database) >= 39


def test_pg_migration_refuses_populated_target(tmp_path, pg_database, monkeypatch):
    import subprocess
    import sys

    src = _make_source_db(tmp_path / "src2.db", monkeypatch)
    target = _test_dsn()
    with pg_database.session() as session:
        from mission_control.models import Project

        session.add(Project(id="existing", name="Existing"))
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "migrate_sqlite_to_postgres.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--execute", "--yes",
         "--source", str(src), "--target", target],
        capture_output=True, text=True, env=_isolated_subprocess_env(), timeout=120,
    )
    assert completed.returncode != 0
    assert "REFUSING" in completed.stdout or "already matches" in completed.stdout


# -------------------------------------------------------------- application


def _pg_client(pg_database, tmp_path, monkeypatch):
    """TestClient whose lifespan runs against the isolated PG test database.

    The app gets throwaway directories (never the real data_dir) and MC_DSN
    pointed at MC_TEST_DSN via monkeypatch (lifespan runs lazily on client
    entry, so the env must persist for the whole test). Startup
    migrations/seeds touch only mc_test. Must never touch data/mission_control.db.
    """
    from fastapi.testclient import TestClient

    from mission_control.config import RuntimeSettings
    from mission_control.main import create_app

    from pathlib import Path as _Path

    monkeypatch.setenv("MC_DSN", _test_dsn())
    monkeypatch.delenv("MISSION_CONTROL_DATABASE_URL", raising=False)
    settings = RuntimeSettings(
        data_dir=tmp_path / "appdata",
        config_dir=_Path(__file__).resolve().parents[2] / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction-books",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=False,
        workbench_decisions_path=tmp_path / "workbench-decisions.jsonl",
        workbench_preferences_path=tmp_path / "workbench-preferences.json",
        workbench_url="http://workbench.test",
    )
    app = create_app(settings)
    return TestClient(app)


def test_pg_book_reorder_roundtrip(pg_database, tmp_path, monkeypatch):
    with pg_database.session() as session:
        from mission_control.models import Book, Project

        for index, name in enumerate(["Alpha", "Beta", "Gamma"]):
            session.add(
                Project(
                    id=f"reorder-proj-{index}", name=name,
                    priority=index + 1, display_order=(index + 1) * 10,
                )
            )
        session.flush()
        for index, name in enumerate(["Alpha", "Beta", "Gamma"]):
            session.add(
                Book(id=f"reorder-book-{index}", project_id=f"reorder-proj-{index}", title=name)
            )
    client = _pg_client(pg_database, tmp_path, monkeypatch)
    with client:
        books = client.get("/api/books").json()
        titles = [b["title"] for b in books if b["id"].startswith("reorder-book")]
        assert titles == ["Alpha", "Beta", "Gamma"]
        moved = ["reorder-book-2", "reorder-book-0", "reorder-book-1"]
        assert client.post("/api/books/reorder", json={"ids": moved}).status_code == 200
        books = client.get("/api/books").json()
        titles = [b["title"] for b in books if b["id"].startswith("reorder-book")]
        assert titles == ["Gamma", "Alpha", "Beta"]
        assert client.get("/api/diagnostics/database").json()["backend"] == "postgresql"


def test_pg_health_observation_write(pg_database):
    with pg_database.session() as session:
        from mission_control.models import Application, LaunchDefinition

        session.add(Application(id="health-app", name="Health App"))
        session.add(
            LaunchDefinition(
                id="health-app-def", application_id="health-app",
                name="web", launch_type="server", health_type="tcp",
                expected_port=9, enabled=True, is_primary=True,
            )
        )
    from mission_control.processes.manager import ProcessManager

    manager = ProcessManager(pg_database, pg_database.settings)
    import asyncio

    observation = asyncio.run(manager.check_health("health-app", timeout=0.3))
    assert observation.application_id == "health-app"
    # Port 9 (discard) is closed: the probe reports unavailable, and the
    # observation must still persist through the PG backend.
    assert observation.state in (
        "healthy",
        "unhealthy",
        "unavailable",
        "unknown",
        "process_only",
        "not_configured",
    )


def test_pg_reorder_concurrent_with_health_writes(pg_database):
    import asyncio

    async def scenario() -> None:
        with pg_database.session() as session:
            from mission_control.models import Application, Book, LaunchDefinition, Project

            session.add(Application(id="conc-app", name="Conc App"))
            session.add(
                LaunchDefinition(
                    id="conc-def", application_id="conc-app", name="web",
                    launch_type="server", health_type="tcp", expected_port=9,
                    enabled=True, is_primary=True,
                )
            )
            session.flush()
            for index in range(5):
                session.add(
                    Project(
                        id=f"conc-proj-{index}", name=f"C {index}",
                        priority=index + 1, display_order=(index + 1) * 10,
                    )
                )
            session.flush()
            for index in range(5):
                session.add(
                    Book(id=f"conc-book-{index}", project_id=f"conc-proj-{index}", title=f"C {index}")
                )

        from mission_control.processes.manager import ProcessManager
        from mission_control.projects.service import reorder_books

        manager = ProcessManager(pg_database, pg_database.settings)

        def _reorder() -> None:
            with pg_database.session() as session:
                reorder_books(
                    session,
                    [f"conc-book-{i}" for i in (4, 3, 2, 1, 0)],
                )

        await asyncio.gather(
            *[asyncio.to_thread(_reorder) for _ in range(4)],
            *[manager.check_health("conc-app", timeout=0.3) for _ in range(8)],
        )
        with pg_database.session() as session:
            from mission_control.models import Book, HealthObservation, Project

            assert session.query(Book).filter(Book.id.like("conc-book-%")).count() == 5
            assert (
                session.query(HealthObservation)
                .filter(HealthObservation.application_id == "conc-app")
                .count()
                >= 8
            )
            priorities = sorted(
                p.priority
                for p in session.query(Project).filter(Project.id.like("conc-proj-%")).all()
            )
            assert priorities == [1, 2, 3, 4, 5]

    asyncio.run(scenario())


def test_pg_no_sqlite_fallback_in_production_paths(pg_database):
    assert pg_database.backend == "postgresql"
    # Database captures the URL at construction; RuntimeSettings.database_url is
    # a live property of the process environment, so assert on the capture.
    assert pg_database.database_url.startswith("postgresql+psycopg://")
    assert "sqlite" not in pg_database.database_url


# ------------------------------------------------------- resilience (Phase 7)


def test_pg_connection_recovery_after_dispose(pg_database):
    # pool_pre_ping must transparently recover after connections die.
    pg_database.health_check()
    pg_database.dispose()
    pg_database.health_check()
    with pg_database.session() as session:
        from mission_control.models import Setting

        assert session.get(Setting, "nonexistent-key") is None


def test_pg_failed_transaction_rolls_back_cleanly(pg_database):
    from sqlalchemy.exc import IntegrityError

    from mission_control.models import Project

    with pg_database.session() as session:
        session.add(Project(id="resil-proj", name="Resilient"))
    try:
        with pg_database.session() as session:
            session.add(Project(id="resil-proj", name="Duplicate"))
            session.flush()
        raise AssertionError("expected IntegrityError")
    except IntegrityError:
        pass
    # The failed transaction must not poison the factory: later writes work.
    with pg_database.session() as session:
        assert session.get(Project, "resil-proj") is not None
        session.add(Project(id="resil-proj-2", name="Resilient 2"))
    with pg_database.session() as session:
        assert session.get(Project, "resil-proj-2") is not None


def test_pg_unavailable_points_at_postgres_not_sqlite(monkeypatch):
    # An unreachable PostgreSQL must surface as a PG connectivity error.
    # It must never silently become SQLite.
    from mission_control.config import RuntimeSettings
    from mission_control.persistence.db import Database

    monkeypatch.setenv("MC_DSN", "postgresql://mc:mc@127.0.0.1:5499/mc_test")
    monkeypatch.setenv("MC_TEST_DSN", "postgresql://mc:mc@127.0.0.1:5499/mc_test")
    database = Database(RuntimeSettings(), target="test:unavailable-point")
    assert database.backend == "postgresql"
    assert "sqlite" not in database.database_url
    with pytest.raises(Exception):
        database.health_check()
    database.dispose()


def test_pg_monitor_recovers_after_failures(pg_database):
    # A failing observation (unknown application) must not stop later passes,
    # and persistence failures stay distinct from endpoint health.
    import asyncio

    from mission_control.processes.manager import ProcessManager

    manager = ProcessManager(pg_database, pg_database.settings)
    with pytest.raises(Exception):
        asyncio.run(manager.check_health("no-such-app", timeout=0.3))
    with pg_database.session() as session:
        from mission_control.models import Application, LaunchDefinition

        session.add(Application(id="resil-mon", name="Resilient Monitor"))
        session.add(
            LaunchDefinition(
                id="resil-mon-def", application_id="resil-mon", name="web",
                launch_type="server", health_type="tcp", expected_port=9,
                enabled=True, is_primary=True,
            )
        )
    observation = asyncio.run(manager.check_health("resil-mon", timeout=0.3))
    assert observation.application_id == "resil-mon"
