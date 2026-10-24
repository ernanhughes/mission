"""Adapter status and explicit refresh actions."""

from __future__ import annotations

from fastapi import APIRouter, Request

from mission_control.adapters.service import AdapterService
from mission_control.schemas import AdapterRead, AdapterRefreshResponse

router = APIRouter(prefix="/api/adapters", tags=["adapters"])


@router.get("", response_model=list[AdapterRead])
def list_adapters(
    project_id: str | None = None,
    application_id: str | None = None,
    request: Request = None,  # type: ignore[assignment]
) -> list[AdapterRead]:
    service = AdapterService(request.app.state.database, request.app.state.settings)
    return service.list_adapters(project_id=project_id, application_id=application_id)


@router.post("/refresh", response_model=AdapterRefreshResponse)
async def refresh_all(request: Request) -> AdapterRefreshResponse:
    service = AdapterService(request.app.state.database, request.app.state.settings)
    pending = await service.refresh_all(force=True)
    return AdapterRefreshResponse(
        adapters=service.list_adapters(), pending_recommendations=pending
    )


@router.post("/applications/{application_id}/refresh", response_model=AdapterRead)
async def refresh_application(application_id: str, request: Request) -> AdapterRead:
    return await AdapterService(
        request.app.state.database, request.app.state.settings
    ).refresh_application(application_id)


@router.post("/projects/{project_id}/refresh", response_model=AdapterRead)
async def refresh_project(project_id: str, request: Request) -> AdapterRead:
    return await AdapterService(
        request.app.state.database, request.app.state.settings
    ).refresh_project(project_id)
