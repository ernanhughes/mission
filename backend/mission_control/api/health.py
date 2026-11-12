"""Local health endpoint and system lifecycle actions."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
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
    settings = request.app.state.settings
    ai_enabled = False
    try:
        with database.session() as session:
            setting = session.get(Setting, "ai")
            if setting and isinstance(setting.value, dict):
                ai_enabled = bool(
                    setting.value.get("enabled")
                    and setting.value.get("consent")
                    and setting.value.get("base_url")
                    and setting.value.get("model")
                )
    except Exception:
        pass
    try:
        version = get_schema_version(database)
    except Exception:
        version = 0
    return HealthRead(
        status="ok" if db_state == "ok" else "degraded",
        version=__version__,
        database=db_state,
        schema_version=version,
        ai_enabled=ai_enabled,
        monitor_enabled=settings.start_monitor,
    )


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
