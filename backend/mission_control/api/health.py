"""Local health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

from mission_control import __version__
from mission_control.models import Setting
from mission_control.persistence.migrations import schema_version as get_schema_version
from mission_control.schemas import HealthRead

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
