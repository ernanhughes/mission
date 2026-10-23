"""Shared API dependencies and response builders."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

from mission_control.models import Application, ProcessInstance
from mission_control.schemas import ProcessRead


def get_session(request: Request) -> Iterator[Session]:
    database = request.app.state.database
    with database.session() as session:
        yield session


def process_read(session: Session, record: ProcessInstance) -> ProcessRead:
    application = session.get(Application, record.application_id)
    log_path = Path(record.log_path) if record.log_path else None
    return ProcessRead(
        id=record.id,
        application_id=record.application_id,
        application_name=application.name if application else None,
        launch_definition_id=record.launch_definition_id,
        pid=record.pid,
        status=record.status,
        started_at=record.started_at,
        ended_at=record.ended_at,
        exit_code=record.exit_code,
        log_available=bool(log_path and log_path.exists()),
        working_directory=record.working_directory,
        command_preview=record.command_preview,
        owned=record.owned,
        reattached=record.reattached,
        error=record.error,
    )
