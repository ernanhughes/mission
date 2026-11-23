"""Read-only Worker runtime visibility (MC-INSPECT-04 A).

GET /api/worker/runtime returns cached availability, usage and preflight
without ever triggering a model probe. Worker outages are honest
unavailable states (200 with available:false), never 500, and never
affect Projects/Inspect.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from typing import Any

from mission_control.worker_runtime import DEFAULT_BASE_URL, read_worker_runtime

router = APIRouter(prefix="/api/worker", tags=["worker runtime"])


class WorkerRuntimeRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    available: bool
    base_url: str
    checked_at: str
    connection: dict[str, Any]
    availability: dict[str, Any]
    usage: dict[str, Any]
    preflight: dict[str, Any]
    notes: list[str]


def _base_url(request: Request) -> str:
    try:
        settings = request.app.state.settings
        worker_url = getattr(settings, "worker_base_url", None)
        if worker_url:
            return str(worker_url)
    except Exception:
        pass
    # Fall back to the configured worker application, else loopback default.
    try:
        from mission_control.models import Application
        from mission_control.persistence.db import Database

        db: Database = request.app.state.database
        with db.session() as session:
            app = session.get(Application, "worker")
            if app is not None and isinstance(app.adapter_config, dict):
                configured = app.adapter_config.get("base_url")
                if isinstance(configured, str) and configured.strip():
                    return configured.strip()
    except Exception:
        pass
    return DEFAULT_BASE_URL


@router.get("/runtime", response_model=WorkerRuntimeRead)
def read_runtime(request: Request) -> WorkerRuntimeRead:
    data = read_worker_runtime(_base_url(request))
    return WorkerRuntimeRead(**data)
