"""Database engine and session construction.

Operational database is PostgreSQL, configured exclusively through ``MC_DSN``
(see :mod:`mission_control.config`). SQLite remains available only for
explicitly isolated unit tests (temporary directories) and for the one-shot
legacy migration utility, which opens the old file read-only. There is no
silent SQLite fallback in normal operation.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from mission_control.config import (
    RuntimeSettings,
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
        settings.ensure_directories()
        url = normalize_database_url(settings.database_url)
        self.database_url = url
        self.backend = "postgresql" if is_postgres_url(url) else "sqlite"
        if self.backend == "postgresql":
            # Modest pool for a local application: health monitor, API
            # workers and background jobs share a handful of connections.
            # pool_pre_ping drops stale connections after PG restarts.
            self.engine: Engine = create_engine(
                url,
                future=True,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=30,
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
