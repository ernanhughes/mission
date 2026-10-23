"""Database engine and session construction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from mission_control.config import RuntimeSettings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utcnow().isoformat()


class Database:
    """A database bound to one runtime configuration.

    Keeping the engine on an instance (rather than a module global) lets the
    test suite create isolated databases in temporary directories.
    """

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        settings.ensure_directories()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            future=True,
            pool_pre_ping=True,
        )
        if settings.database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

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


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db(session: Session) -> Session:  # pragma: no cover - type helper
    return session
