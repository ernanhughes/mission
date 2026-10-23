"""Managed process inspection and stopping."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session, process_read
from mission_control.core.errors import NotFound
from mission_control.models import ProcessInstance
from mission_control.schemas import LogRead, ProcessRead

router = APIRouter(prefix="/api/processes", tags=["processes"])


@router.get("", response_model=list[ProcessRead])
def list_processes(
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
    application_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ProcessRead]:
    manager = request.app.state.process_manager
    manager.reconcile_live(session, application_id)
    query = select(ProcessInstance).order_by(ProcessInstance.started_at.desc()).limit(limit)
    if application_id:
        query = query.where(ProcessInstance.application_id == application_id)
    return [process_read(session, record) for record in session.scalars(query).all()]


@router.get("/{process_id}", response_model=ProcessRead)
def get_process(
    process_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProcessRead:
    request.app.state.process_manager.reconcile_live(session)
    record = session.get(ProcessInstance, process_id)
    if record is None:
        raise NotFound("Process not found")
    return process_read(session, record)


@router.get("/{process_id}/logs", response_model=LogRead)
def get_process_logs(
    process_id: str,
    lines: int = Query(default=200, ge=1, le=2000),
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> LogRead:
    if session.get(ProcessInstance, process_id) is None:
        raise NotFound("Process not found")
    return LogRead(**request.app.state.process_manager.read_log(process_id, lines))


@router.post("/{process_id}/stop", response_model=ProcessRead)
async def stop_process(
    process_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProcessRead:
    record = await request.app.state.process_manager.stop(process_id)
    return process_read(session, record)
