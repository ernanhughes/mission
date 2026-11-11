"""Writer Editing workspace API.

Read routes consume Writer's adapter resources. The audit action is launched
through Mission Control's durable integration-execution lifecycle; the browser
never supplies an executable or command.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from mission_control.adapters.service import AdapterService
from mission_control.schemas import (
    IntegrationExecutionRead,
    WriterAuditRequest,
    WriterWorkspaceRead,
)
from mission_control.writer.service import WriterService

router = APIRouter(prefix="/api/writer", tags=["writer"])


@router.get("/books", response_model=WriterWorkspaceRead)
def list_writer_books(request: Request) -> WriterWorkspaceRead:
    return WriterWorkspaceRead(
        **WriterService(
            request.app.state.database, request.app.state.settings
        ).workspace()
    )


@router.get("/self-repair")
def read_writer_self_repair(request: Request) -> dict[str, Any]:
    """Read-only self-repair process summary. No scores, no writes."""
    from mission_control.writer.self_repair import summarize_self_repair

    return summarize_self_repair(request.app.state.settings.book_root)


@router.post("/refresh", response_model=WriterWorkspaceRead)
async def refresh_writer(request: Request) -> WriterWorkspaceRead:
    await AdapterService(
        request.app.state.database, request.app.state.settings
    ).refresh_application("writer")
    return WriterWorkspaceRead(
        **WriterService(
            request.app.state.database, request.app.state.settings
        ).workspace()
    )


@router.post("/audit", response_model=IntegrationExecutionRead)
async def audit_writer(
    payload: WriterAuditRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer",
        "audit_registered_books",
        {"profile": payload.profile},
        confirm=True,
    )
