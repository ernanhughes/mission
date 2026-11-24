"""Local health endpoint and system lifecycle actions."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from mission_control import __version__
from mission_control.models import Setting
from mission_control.persistence.migrations import schema_version as get_schema_version
from mission_control.schemas import HealthRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthRead)
def health(request: Request) -> HealthRead:
    database = request.app.state.database
    try:
        with database.session() as session:
            session.execute(text("SELECT 1"))
        db_state = "ok"
    except Exception:
        db_state = "error"
        logger.exception("Database health check failed")
    settings = request.app.state.settings
    ai_enabled = False
    try:
        with database.session() as session:
            setting = session.get(Setting, "ai")
            if setting and isinstance(setting.value, dict):
                # Pi-first readiness: enabled + consent is sufficient. A
                # loopback endpoint/model is an optional override, not the
                # definition of "AI on" — Pi-only setups report true.
                ai_enabled = bool(
                    setting.value.get("enabled")
                    and setting.value.get("consent")
                )
    except Exception:
        pass
    try:
        version = get_schema_version(database)
    except Exception:
        version = 0
    backend = getattr(database, "backend", "unknown")
    try:
        pool = database.engine.pool
        pool_status = {
            "size": pool.size() if hasattr(pool, "size") else None,
            "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
            "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
        }
    except Exception:
        pool_status = {}
    try:
        with database.engine.connect() as connection:
            if backend == "postgresql":
                pg_version = connection.execute(text("SHOW server_version")).scalar()
            else:
                pg_version = connection.execute(text("select sqlite_version()")).scalar()
    except Exception:
        pg_version = None
    extra: dict[str, object] = {
        "database_backend": backend,
        "database_url_redacted": settings.redacted_database_url,
        "pool": pool_status,
    }
    if pg_version:
        extra["server_version"] = str(pg_version)
    logger.debug(
        "Health check backend=%s schema=%s db=%s", backend, version, db_state
    )
    return HealthRead(
        status="ok" if db_state == "ok" else "degraded",
        version=__version__,
        database=db_state,
        schema_version=version,
        ai_enabled=ai_enabled,
        monitor_enabled=settings.start_monitor,
    )


@router.get("/diagnostics/database")
def database_diagnostics(request: Request) -> dict[str, object]:
    """Narrowly scoped database diagnostics (no credentials, no records)."""
    database = request.app.state.database
    settings = request.app.state.settings
    backend = getattr(database, "backend", "unknown")
    try:
        with database.session() as session:
            session.execute(text("SELECT 1"))
        connectivity: object = "ok"
        last_error: object = None
    except Exception as exc:
        connectivity = "error"
        last_error = f"{exc.__class__.__name__}"
    try:
        version = get_schema_version(database)
    except Exception:
        version = -1
    try:
        pool = database.engine.pool
        pool_status: dict[str, object] = {
            "size": pool.size() if hasattr(pool, "size") else None,
            "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
            "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
        }
    except Exception:
        pool_status = {}
    server_version: object = None
    db_name: object = None
    latency_ms: object = None
    pg_extra: dict[str, object] = {}
    try:
        with database.engine.connect() as connection:
            if backend == "postgresql":
                started = time.perf_counter()
                server_version = connection.execute(text("SHOW server_version")).scalar()
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                db_name = connection.execute(text("SELECT current_database()")).scalar()
                pg_extra = _postgresql_diagnostics(connection)
            else:
                server_version = connection.execute(text("select sqlite_version()")).scalar()
                db_name = "sqlite"
    except Exception as exc:
        last_error = f"{exc.__class__.__name__}"
    return {
        "backend": backend,
        "connectivity": connectivity,
        "database": db_name,
        "server_version": server_version,
        "schema_version": version,
        "pool": pool_status,
        "latency_ms": latency_ms,
        "postgresql": pg_extra,
        "last_verified_backup": _last_verified_backup(),
        "url_redacted": settings.redacted_database_url,
        "last_error_category": last_error,
    }


def _postgresql_diagnostics(connection) -> dict[str, object]:
    """Read-only PostgreSQL operational snapshot (MC-POSTGRES-02 Phase 6).

    Every probe is defensive: any failure yields ``unknown`` for that field
    rather than failing the endpoint. Exposes counts and durations only —
    never query text, PIDs, credentials, or record contents.
    """
    out: dict[str, object] = {}
    try:
        out["size_bytes"] = connection.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar()
    except Exception:
        out["size_bytes"] = "unknown"
    try:
        row = connection.execute(
            text(
                "SELECT "
                "COUNT(*) FILTER (WHERE state = 'active') AS active, "
                "COUNT(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx "
                "FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid()"
            )
        ).fetchone()
        out["active_connections"] = int(row[0])
        out["idle_in_transaction"] = int(row[1])
    except Exception:
        out["active_connections"] = "unknown"
        out["idle_in_transaction"] = "unknown"
    try:
        row = connection.execute(
            text(
                "SELECT COUNT(*), COALESCE(MAX(EXTRACT(EPOCH FROM (now() - xact_start))), 0) "
                "FROM pg_stat_activity WHERE datname = current_database() "
                "AND pid <> pg_backend_pid() AND xact_start IS NOT NULL "
                "AND now() - xact_start > interval '60 seconds'"
            )
        ).fetchone()
        out["long_transactions"] = int(row[0])
        out["longest_transaction_seconds"] = round(float(row[1]), 1)
    except Exception:
        out["long_transactions"] = "unknown"
        out["longest_transaction_seconds"] = "unknown"
    try:
        out["waiting_locks"] = int(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM pg_locks "
                    "WHERE NOT granted AND database = ("
                    "SELECT oid FROM pg_database WHERE datname = current_database())"
                )
            ).scalar()
        )
    except Exception:
        out["waiting_locks"] = "unknown"
    return out


def _last_verified_backup() -> dict[str, object]:
    """Metadata of the last restore-validated backup, if recorded.

    Written by the backup verification workflow (see
    ``docs/migration/MC-POSTGRES-01/08-recovery-runbook.md``); unknown when
    absent. Never contains credentials.
    """
    try:
        from mission_control.config import _repo_root

        candidate = _repo_root() / "data" / "backups" / "last_verified_backup.json"
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return {
                    key: payload.get(key)
                    for key in ("path", "bytes", "sha256", "validated_at", "method")
                }
    except Exception:
        pass
    return {"status": "unknown"}


@router.post("/restart", status_code=202, response_model=dict[str, Any])
def restart_backend(request: Request) -> dict[str, Any]:
    """Restart the Mission Control backend.

    Spawns a replacement backend process bound to the same loopback host and
    port, detached from this one, then exits so the listening port can be handed
    over to the replacement. The frontend polls /api/health and reconnects
    automatically once the new backend answers.
    """
    settings = request.app.state.settings
    command = [
        sys.executable,
        "-m",
        "mission_control",
        "--host",
        settings.host,
        "--port",
        str(settings.port),
    ]
    try:
        creation_flags = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32"
            else 0
        )
        subprocess.Popen(
            command,
            cwd=str(settings.repo_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError:  # pragma: no cover - defensive
        logger.exception("Failed to spawn replacement backend")
        raise HTTPException(status_code=500, detail="Could not spawn replacement backend")

    # Let the 202 response flush before surrendering the port to the replacement.
    def _give_up_port() -> None:
        os._exit(0)

    timer = threading.Timer(1.0, _give_up_port)
    timer.daemon = True
    timer.start()

    return {
        "status": "restarting",
        "message": "Mission Control is restarting; the panel will reconnect automatically.",
    }
