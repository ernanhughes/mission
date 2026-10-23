"""Small, testable migration runner for the local SQLite database.

Migrations are ordered SQL files applied exactly once and recorded in
``schema_migrations``. The runner is intentionally boring: no hidden schema
generation means every deployment path is the same, and a future migration is
just a new numbered file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Connection, text

from mission_control.persistence.db import Database, now_iso

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"), key=lambda p: p.name)


def _applied_versions(connection: Connection) -> set[int]:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
    )
    rows = connection.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {int(row[0]) for row in rows}


def apply_migrations(database: Database) -> list[int]:
    """Apply all pending migrations and return their versions."""
    applied_now: list[int] = []
    with database.engine.begin() as connection:
        applied = _applied_versions(connection)
        for path in _migration_files():
            try:
                version = int(path.name.split("_", 1)[0])
            except ValueError as exc:  # pragma: no cover - guarded by filename pattern
                raise RuntimeError(f"Invalid migration filename: {path.name}") from exc
            if version in applied:
                continue
            logger.info("Applying database migration %s", path.name)
            sql = path.read_text(encoding="utf-8")
            # SQLite's driver accepts one statement at a time via executescript,
            # which is not exposed by SQLAlchemy's Connection. Split on the
            # semicolon at end-of-statement; migration files contain no triggers.
            for statement in _split_sql(sql):
                connection.execute(text(statement))
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (version, name, applied_at) "
                    "VALUES (:version, :name, :applied_at)"
                ),
                {"version": version, "name": path.name, "applied_at": now_iso()},
            )
            applied_now.append(version)
    return applied_now


def _split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip()
            if statement:
                statements.append(statement[:-1].strip())
            buffer = []
    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def schema_version(database: Database) -> int:
    with database.engine.connect() as connection:
        _applied_versions(connection)
        row = connection.execute(text("SELECT MAX(version) FROM schema_migrations")).fetchone()
    return int(row[0] or 0)
