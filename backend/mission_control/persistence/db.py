"""Database engine and session construction.

Operational database is PostgreSQL, configured exclusively through ``MC_DSN``
(see :mod:`mission_control.config`). SQLite remains available only for
explicitly isolated unit tests (temporary directories) and for the one-shot
legacy migration utility, which opens the old file read-only. There is no
silent SQLite fallback in normal operation.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from mission_control.config import (
    DatabaseConfigurationError,
    RuntimeSettings,
    _repo_root,
    is_postgres_url,
    normalize_database_url,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utcnow().isoformat()


class Database:
    """A database bound to one runtime configuration.

    Keeping the engine on an instance (rather than a module global) lets the
    test suite create isolated databases in temporary directories.
    """

    def __init__(self, settings: RuntimeSettings, *, busy_timeout_ms: int = 30_000) -> None:
        self.settings = settings
        self.busy_timeout_ms = max(0, int(busy_timeout_ms))
        url = normalize_database_url(settings.database_url)
        if os.environ.get("PYTEST_CURRENT_TEST"):
            # Hard test-isolation invariant (MC-POSTGRES-02 Phase 2): under
            # pytest, a Database may only target an explicitly isolated
            # database — a tmp SQLite file or exactly MC_TEST_DSN. Anything
            # else (production MC_DSN, the repo data file) is refused before
            # any engine use, so no test can write to operational data even
            # if it constructs production-like settings. Production startup
            # (no PYTEST_CURRENT_TEST) is completely unaffected.
            _enforce_test_database(url)
        settings.ensure_directories()
        self.database_url = url
        self.backend = "postgresql" if is_postgres_url(url) else "sqlite"
        if self.backend == "postgresql":
            # Modest pool for a local application: health monitor, API
            # workers and background jobs share a handful of connections.
            # pool_pre_ping drops stale connections after PG restarts.
            # connect_timeout bounds startup/health checks against a dead
            # server instead of hanging on TCP retransmits.
            self.engine: Engine = create_engine(
                url,
                future=True,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=30,
                connect_args={"connect_timeout": 10},
            )
        else:
            connect_args = {"check_same_thread": False, "timeout": 30.0}
            self.engine: Engine = create_engine(
                url,
                connect_args=connect_args,
                future=True,
                pool_pre_ping=True,
            )
            timeout_ms = self.busy_timeout_ms
            event.listen(self.engine, "connect", lambda c, r: _enable_sqlite_pragmas(c, r, timeout_ms))
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    @property
    def is_postgres(self) -> bool:
        return self.backend == "postgresql"

    def health_check(self) -> None:
        """Raise if the database is unreachable. Used by startup and diagnostics."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def _enforce_test_database(url: str) -> None:
    """Refuse non-isolated database targets while running under pytest.

    Raises :class:`DatabaseConfigurationError` before any engine or
    connection exists, so a misconfigured test fails instead of writing to
    operational data. Independent checks (not naming alone):
    PostgreSQL requires exact equality with the explicitly configured
    ``MC_TEST_DSN``; SQLite refuses the production repository data file.
    """
    if is_postgres_url(url):
        test_dsn = os.environ.get("MC_TEST_DSN", "").strip()
        if test_dsn and normalize_database_url(url) == normalize_database_url(test_dsn):
            return
        raise DatabaseConfigurationError(
            "Refusing to connect a test session to a non-test PostgreSQL "
            "database. Tests must target exactly MC_TEST_DSN."
        )
    if url.startswith("sqlite"):
        path = url[len("sqlite:///"):]
        try:
            resolved = Path(path).expanduser().resolve()
        except Exception:
            raise DatabaseConfigurationError(
                "Refusing to open an unresolvable SQLite path in tests."
            )
        production = (_repo_root() / "data" / "mission_control.db").resolve()
        if resolved == production:
            raise DatabaseConfigurationError(
                "Refusing to open the production SQLite database in tests. "
                "Use an isolated temporary directory."
            )
        return
    raise DatabaseConfigurationError(f"Unsupported test database backend for {url!r}.")


def _enable_sqlite_pragmas(
    dbapi_connection, _connection_record, busy_timeout_ms: int = 30_000
) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # The Git activity index writes from a bounded worker pool while the UI
    # reads concurrently. WAL plus a busy timeout keeps short concurrent
    # writers from failing with SQLITE_BUSY under default rollback journals.
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
    except Exception:  # pragma: no cover - defensive; keep DELETE mode
        pass
    try:
        cursor.execute(f"PRAGMA busy_timeout={max(0, int(busy_timeout_ms))}")
    except Exception:  # pragma: no cover - defensive
        pass
    cursor.close()


def get_db(session: Session) -> Session:  # pragma: no cover - type helper
    return session
