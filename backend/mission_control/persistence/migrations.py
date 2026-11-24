"""Migration runner for SQLite (legacy) and PostgreSQL (operational).

SQLite: ordered SQL files applied exactly once, recorded in
``schema_migrations`` — unchanged historical behaviour.

PostgreSQL: the numbered SQL files are SQLite-dialect (AUTOINCREMENT, typeless
JSON columns). They are preserved as the legacy archive. The authoritative
PostgreSQL schema is the SQLAlchemy ORM metadata (``mission_control.models``,
which mirrors the migrations), created once as a baseline bound to the
highest legacy migration version. Subsequent PostgreSQL upgrades are new
numbered ``NNN_*.pg.sql`` files executed with the same version tracking.
``schema_migrations`` semantics are identical on both backends.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Connection, text

from mission_control.persistence.db import Database, now_iso

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _migration_files() -> list[Path]:
    return sorted(
        (p for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql") if not p.name.endswith(".pg.sql")),
        key=lambda p: p.name,
    )


def _pg_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.pg.sql"), key=lambda p: p.name)


def max_migration_version() -> int:
    versions: list[int] = []
    for path in list(_migration_files()) + list(_pg_migration_files()):
        try:
            versions.append(int(path.name.split("_", 1)[0]))
        except ValueError:
            continue
    return max(versions) if versions else 0


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
    if getattr(database, "is_postgres", False):
        return _apply_postgres_migrations(database)
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


def _apply_postgres_migrations(database: Database) -> list[int]:
    """Create the PostgreSQL baseline from ORM metadata, then apply *.pg.sql deltas."""
    # Imported here to avoid a hard import cycle at module load
    # (models imports persistence.db; migrations is imported by main).
    from mission_control.models import Base as _ORMBase

    import mission_control.praxis_proposals.models as _praxis_models  # noqa: F401

    applied_now: list[int] = []
    with database.engine.begin() as connection:
        applied = _applied_versions(connection)
        legacy_files = _migration_files()
        if not applied and legacy_files:
            # Fresh PostgreSQL install: authoritative schema comes from the ORM
            # metadata, which mirrors the full SQLite migration history.
            # Baseline is bound to the highest legacy version so
            # schema_version() stays comparable across backends.
            logger.info(
                "Creating PostgreSQL schema from ORM metadata (baseline for %d migrations)",
                len(legacy_files),
            )
            _ORMBase.metadata.create_all(bind=connection)
            # create_all above already created schema_migrations if the ORM
            # ever declares it; ensure tracking table exists regardless.
            _applied_versions(connection)
            for path in legacy_files:
                version = int(path.name.split("_", 1)[0])
                if version in applied:
                    continue
                connection.execute(
                    text(
                        "INSERT INTO schema_migrations (version, name, applied_at) "
                        "VALUES (:version, :name, :applied_at)"
                    ),
                    {"version": version, "name": path.name, "applied_at": now_iso()},
                )
                applied.add(version)
                applied_now.append(version)
            # Continue below: apply any pending *.pg.sql deltas (e.g. 040+)
            # in the same run so a fresh install converges fully.
        # Existing PG database: apply only explicit PostgreSQL deltas.
        for path in _pg_migration_files():
            version = int(path.name.split("_", 1)[0])
            if version in applied:
                continue
            logger.info("Applying PostgreSQL migration %s", path.name)
            for statement in _split_sql(path.read_text(encoding="utf-8")):
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
