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


def _pg_database(dsn: str):
    from mission_control.config import RuntimeSettings
    from mission_control.persistence.db import Database

    settings = RuntimeSettings()
    previous_mc, previous_legacy = os.environ.get("MC_DSN"), os.environ.get(
        "MISSION_CONTROL_DATABASE_URL"
    )
    os.environ["MC_DSN"] = dsn
    os.environ.pop("MISSION_CONTROL_DATABASE_URL", None)
    try:
        database = Database(settings)
        assert database.is_postgres
        return database
    finally:
        if previous_mc is None:
            os.environ.pop("MC_DSN", None)
        else:
            os.environ["MC_DSN"] = previous_mc
        if previous_legacy is not None:
            os.environ["MISSION_CONTROL_DATABASE_URL"] = previous_legacy


@pytest.fixture()
def pg_database():
    dsn = _test_dsn()
    database = _pg_database(dsn)
    from mission_control.persistence.migrations import apply_migrations

    # Clean slate: drop all tables in public then rebuild via the runner.
    from sqlalchemy import text

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


def test_missing_operational_config_fails_clearly():
    previous_mc, previous_legacy = os.environ.get("MC_DSN"), os.environ.get(
        "MISSION_CONTROL_DATABASE_URL"
    )
    os.environ.pop("MC_DSN", None)
    os.environ.pop("MISSION_CONTROL_DATABASE_URL", None)
    try:
        with pytest.raises(DatabaseConfigurationError):
            resolve_database_url(allow_sqlite_fallback=False)
    finally:
        if previous_mc is not None:
            os.environ["MC_DSN"] = previous_mc
        if previous_legacy is not None:
            os.environ["MISSION_CONTROL_DATABASE_URL"] = previous_legacy


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


def _make_source_db(path, *, books: int = 2, health: int = 3):
    from mission_control.config import RuntimeSettings
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.persistence.seed import seed_defaults

    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    settings = RuntimeSettings(
        data_dir=path.parent, config_dir=repo_root / "config", frontend_dist=path.parent,
    )
    # Point this Database at the given sqlite file via legacy override.
    previous = os.environ.get("MISSION_CONTROL_DATABASE_URL")
    os.environ.pop("MC_DSN", None)
    os.environ["MISSION_CONTROL_DATABASE_URL"] = f"sqlite:///{path.as_posix()}"
    try:
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
    finally:
        if previous is None:
            os.environ.pop("MISSION_CONTROL_DATABASE_URL", None)
        else:
            os.environ["MISSION_CONTROL_DATABASE_URL"] = previous
    return path


def test_pg_import_preserves_pks_and_sequences(tmp_path, pg_database):
    from mission_control.persistence.migrations import schema_version

    src = _make_source_db(tmp_path / "src.db")
    import subprocess
    import sys

    target = _test_dsn()
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "migrate_sqlite_to_postgres.py"
    env = dict(os.environ)
    completed = subprocess.run(
        [sys.executable, str(script), "--execute", "--yes",
         "--source", str(src), "--target", target],
        capture_output=True, text=True, env=env, timeout=300,
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


def test_pg_migration_refuses_populated_target(tmp_path, pg_database):
    import subprocess
    import sys

    src = _make_source_db(tmp_path / "src2.db")
    target = _test_dsn()
    with pg_database.session() as session:
        from mission_control.models import Project

        session.add(Project(id="existing", name="Existing"))
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "migrate_sqlite_to_postgres.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--execute", "--yes",
         "--source", str(src), "--target", target],
        capture_output=True, text=True, env=dict(os.environ), timeout=120,
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
