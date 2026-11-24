"""MC-SQLITE-LOCK-01 regression tests.

Covers book-reorder atomicity, health-monitor isolation from SQLite write
contention, and health-state integrity when observation persistence fails.
Contention tests use real SQLite file locking (BEGIN IMMEDIATE from a second
connection) with a short busy timeout so the same code path fails fast; the
production default busy timeout (30s) is unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from helpers import open_client
from mission_control.config import RuntimeSettings
from mission_control.core.errors import Conflict
from mission_control.models import (
    Application,
    HealthObservation,
    LaunchDefinition,
)
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.processes import manager as manager_module
from mission_control.processes.manager import ProcessManager
from mission_control.projects import service as projects_service


@pytest.fixture
def lock_db(runtime: RuntimeSettings) -> Iterator[Database]:
    """A short-timeout Database on an isolated file for contention tests."""
    settings = RuntimeSettings(
        repo_root=runtime.repo_root,
        data_dir=runtime.data_dir / "lockdb",
        config_dir=runtime.config_dir,
        frontend_dist=runtime.frontend_dist,
        book_root=runtime.book_root,
        fiction_book_root=runtime.fiction_book_root,
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
    )
    database = Database(settings, busy_timeout_ms=500)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, settings)
        session.add(Application(id="lock-app", name="Lock App"))
        session.add(
            LaunchDefinition(
                id="lock-app-run",
                application_id="lock-app",
                name="Run",
                launch_type="server",
                health_type="http",
                health_url="http://127.0.0.1:1/health",
                enabled=True,
                is_primary=True,
            )
        )
    yield database
    database.dispose()


@contextmanager
def held_write_lock(db_path: str, hold_seconds: float = 5.0) -> Iterator[None]:
    """Hold a SQLite RESERVED lock from an independent connection."""
    ready = threading.Event()
    release = threading.Event()

    def _hold() -> None:
        conn = sqlite3.connect(str(db_path), timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO health_observations "
                "(application_id, process_instance_id, state, detail, source,"
                " observed_at, stale_after_seconds) VALUES "
                "('lock-app', NULL, 'healthy', 'holder', 'test',"
                " '2026-01-01T00:00:00+00:00', 60)"
            )
            ready.set()
            release.wait(hold_seconds + 5.0)
            conn.execute("ROLLBACK")
        finally:
            conn.close()

    thread = threading.Thread(target=_hold, daemon=True)
    thread.start()
    assert ready.wait(10.0), "lock holder did not take RESERVED"
    try:
        yield
    finally:
        release.set()
        thread.join(timeout=10.0)


def book_ids(client: TestClient) -> list[str]:
    response = client.get("/api/books")
    assert response.status_code == 200, response.text
    return [book["id"] for book in response.json()]


def test_single_book_reorder_persists(client: TestClient) -> None:
    ids = book_ids(client)
    assert len(ids) >= 2
    moved = [ids[1], ids[0], *ids[2:]]
    assert client.post("/api/books/reorder", json={"ids": moved}).status_code == 200
    assert book_ids(client) == moved


def test_reorder_then_reload_is_stable(client: TestClient, runtime: RuntimeSettings) -> None:
    ids = book_ids(client)
    moved = list(reversed(ids))
    assert client.post("/api/books/reorder", json={"ids": moved}).status_code == 200
    with open_client(runtime) as reloaded:
        assert [book["id"] for book in reloaded.get("/api/books").json()] == moved


def test_reorder_ignores_unknown_ids_and_keeps_all_books(client: TestClient) -> None:
    ids = book_ids(client)
    moved = [*reversed(ids), "book-does-not-exist"]
    assert client.post("/api/books/reorder", json={"ids": moved}).status_code == 200
    assert book_ids(client) == list(reversed(ids))


def test_concurrent_reorders_and_health_checks_agree(lock_db: Database) -> None:
    database, settings = lock_db, lock_db.settings
    with database.session() as session:
        from mission_control.models import Book

        ids = [book.id for book in session.scalars(select(Book)).all()]
    assert len(ids) >= 2
    forward, backward = list(ids), list(reversed(ids))
    errors: list[str] = []

    def _storm(order: list[str]) -> None:
        try:
            for _ in range(10):
                with database.session() as session:
                    projects_service.reorder_books(session, order)
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            errors.append(repr(exc))

    async def _health() -> None:
        manager = ProcessManager(database, settings)
        for _ in range(10):
            try:
                await manager.check_health("lock-app", timeout=1.0)
            except Exception as exc:  # noqa: BLE001 - collected, asserted below
                errors.append(repr(exc))

    threads = [
        threading.Thread(target=_storm, args=(forward if i % 2 == 0 else backward,))
        for i in range(4)
    ]
    for thread in threads:
        thread.start()
    asyncio.run(_health())
    for thread in threads:
        thread.join()

    assert errors == []
    with database.session() as session:
        from mission_control.models import Book, Project

        books = session.scalars(select(Book)).all()
        assert sorted(book.id for book in books) == sorted(ids)  # none lost/duplicated
        projects = session.scalars(select(Project)).all()
        priorities = sorted(
            project.priority for project in projects if project.id in {b.project_id for b in books}
        )
        assert priorities == list(range(1, len(books) + 1))
        observations = session.scalars(
            select(HealthObservation).where(HealthObservation.application_id == "lock-app")
        ).all()
        assert len(observations) == 10


def test_health_check_holds_no_connection_across_probe(lock_db: Database) -> None:
    database, settings = lock_db, lock_db.settings
    manager = ProcessManager(database, settings)
    original_probe = manager_module.probe
    seen: dict[str, int] = {}

    async def _spy(definition, *, timeout: float = 2.0):  # type: ignore[no-untyped-def]
        seen["checkedout"] = database.engine.pool.checkedout()
        await asyncio.sleep(0.2)
        return await original_probe(definition, timeout=timeout)

    async def _run() -> None:
        manager_module.probe = _spy
        try:
            await manager.check_health("lock-app", timeout=2.0)
        finally:
            manager_module.probe = original_probe

    asyncio.run(_run())
    assert seen.get("checkedout") == 0


def test_contended_writer_gives_bounded_explained_failure(lock_db: Database) -> None:
    database, settings = lock_db, lock_db.settings
    manager = ProcessManager(database, settings)
    with database.session() as session:
        before = session.scalar(
            select(HealthObservation).where(HealthObservation.application_id == "lock-app")
        )
    assert before is None
    started = time.monotonic()
    with held_write_lock(str(settings.db_path)):
        with pytest.raises(Conflict) as exc_info:
            asyncio.run(manager.check_health("lock-app", timeout=1.0))
    elapsed = time.monotonic() - started
    assert elapsed < 20.0  # busy_timeout (0.5s) + probe, far below production 30s
    assert "busy" in exc_info.value.message.lower()
    assert "unavailable" in (exc_info.value.detail or "").lower()  # probe result preserved
    with database.session() as session:
        # No partial observation row was committed.
        assert (
            session.scalar(
                select(HealthObservation).where(HealthObservation.application_id == "lock-app")
            )
            is None
        )
    # Session cleanup: the pool recovered and later writes succeed.
    recovered = asyncio.run(manager.check_health("lock-app", timeout=1.0))
    assert recovered.state == "unavailable"


def test_failed_observation_insert_does_not_change_health_state(
    lock_db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    database, settings = lock_db, lock_db.settings
    manager = ProcessManager(database, settings)
    with database.session() as session:
        session.add(
            HealthObservation(
                application_id="lock-app",
                process_instance_id=None,
                state="healthy",
                detail="baseline",
                source="test",
                observed_at="2026-01-01T00:00:00+00:00",
                stale_after_seconds=60,
            )
        )
    with caplog.at_level(logging.WARNING, logger="mission_control.processes.manager"):
        with held_write_lock(str(settings.db_path)):
            # The monitor pass survives a persistence failure without raising.
            asyncio.run(manager._monitor_once())
    assert "health_observation_persistence_failed" in caplog.text
    with database.session() as session:
        latest = session.scalar(
            select(HealthObservation)
            .where(HealthObservation.application_id == "lock-app")
            .order_by(HealthObservation.id.desc())
        )
        # The failed insert did not masquerade as a probe outcome.
        assert latest is not None and latest.state == "healthy" and latest.detail == "baseline"
    asyncio.run(manager._monitor_once())  # recovered database accepts writes
