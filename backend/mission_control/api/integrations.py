"""Unified application integration API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import ValidationProblem
from mission_control.integrations.service import IntegrationService
from mission_control.integrations.store import (
    associate_project,
    decision_history,
    decision_read,
    inbox_items,
    list_resources,
    record_decision,
    resource_read,
    search_all,
)
from mission_control.models import IntegrationRecord
from mission_control.schemas import (
    InboxItemRead,
    IntegrationConfigUpdate,
    IntegrationDecisionCreate,
    IntegrationDecisionRead,
    IntegrationExecutionCreate,
    IntegrationExecutionRead,
    IntegrationRead,
    IntegrationRecordRead,
    IntegrationResourcePatch,
    SearchResultRead,
)

router = APIRouter(prefix="/api", tags=["integrations"])


def _integration_service(request: Request) -> IntegrationService:
    return request.app.state.integration_service


@router.get("/integrations", response_model=list[IntegrationRead])
def list_integrations(request: Request) -> list[IntegrationRead]:
    return _integration_service(request).list_integrations()


@router.get("/integrations/executions", response_model=list[IntegrationExecutionRead])
def list_executions(
    request: Request,
    application_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[IntegrationExecutionRead]:
    return _integration_service(request).list_executions(application_id, limit)


@router.get("/integrations/executions/{execution_id}", response_model=IntegrationExecutionRead)
def get_execution(execution_id: str, request: Request) -> IntegrationExecutionRead:
    return _integration_service(request).get_execution(execution_id)


@router.get("/integrations/{application_id}", response_model=IntegrationRead)
def get_integration(application_id: str, request: Request) -> IntegrationRead:
    return _integration_service(request).read_integration(application_id)


@router.patch("/integrations/{application_id}", response_model=IntegrationRead)
def configure_integration(
    application_id: str, payload: IntegrationConfigUpdate, request: Request
) -> IntegrationRead:
    return _integration_service(request).update_config(
        application_id, payload.adapter_config, payload.adapter_enabled
    )


@router.post("/integrations/{application_id}/test", response_model=IntegrationRead)
async def test_integration(application_id: str, request: Request) -> IntegrationRead:
    return await _integration_service(request).test_connection(application_id)


@router.post("/integrations/{application_id}/refresh", response_model=IntegrationRead)
async def refresh_integration(application_id: str, request: Request) -> IntegrationRead:
    return await _integration_service(request).refresh(application_id)


@router.get("/integrations/{application_id}/resources", response_model=list[IntegrationRecordRead])
def get_resources(
    application_id: str,
    session: Session = Depends(get_session),
    resource_type: str | None = None,
    project_id: str | None = None,
    q: str | None = None,
    current: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[IntegrationRecordRead]:
    return list_resources(
        session,
        application_id=application_id,
        resource_type=resource_type,
        project_id=project_id,
        query=q,
        current=current,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/integrations/{application_id}/resources/{record_id}",
    response_model=IntegrationRecordRead,
)
def get_resource(application_id: str, record_id: str, session: Session = Depends(get_session)) -> IntegrationRecordRead:
    record = session.get(IntegrationRecord, record_id)
    if record is None or record.application_id != application_id:
        raise ValidationProblem("Integration resource not found")
    return resource_read(session, record)


@router.patch(
    "/integrations/{application_id}/resources/{record_id}",
    response_model=IntegrationRecordRead,
)
def patch_resource(
    application_id: str,
    record_id: str,
    payload: IntegrationResourcePatch,
    session: Session = Depends(get_session),
) -> IntegrationRecordRead:
    record = session.get(IntegrationRecord, record_id)
    if record is None or record.application_id != application_id:
        raise ValidationProblem("Integration resource not found")
    try:
        return associate_project(session, record, payload.project_id)
    except ValueError as exc:
        raise ValidationProblem(str(exc)) from exc


@router.post(
    "/integrations/{application_id}/resources/{record_id}/decision",
    response_model=IntegrationDecisionRead,
)
def decide_resource(
    application_id: str,
    record_id: str,
    payload: IntegrationDecisionCreate,
    session: Session = Depends(get_session),
) -> IntegrationDecisionRead:
    record = session.get(IntegrationRecord, record_id)
    if record is None or record.application_id != application_id:
        raise ValidationProblem("Integration resource not found")
    try:
        decision = record_decision(session, record, payload.decision, payload.reason)
    except ValueError as exc:
        raise ValidationProblem(str(exc)) from exc
    session.flush()
    return decision_read(decision)


@router.get(
    "/integrations/{application_id}/decisions",
    response_model=list[IntegrationDecisionRead],
)
def get_decisions(application_id: str, session: Session = Depends(get_session)) -> list[IntegrationDecisionRead]:
    return decision_history(session, application_id)


@router.post(
    "/integrations/{application_id}/actions/{action_id}/execute",
    response_model=IntegrationExecutionRead,
)
async def execute_action(
    application_id: str,
    action_id: str,
    payload: IntegrationExecutionCreate,
    request: Request,
) -> IntegrationExecutionRead:
    return await _integration_service(request).start_action(
        application_id, action_id, payload.parameters, confirm=payload.confirm
    )


@router.get("/inbox", response_model=list[InboxItemRead])
def inbox(
    session: Session = Depends(get_session),
    application_id: str | None = None,
    project_id: str | None = None,
    priority: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
) -> list[InboxItemRead]:
    items = inbox_items(
        session, application_id=application_id, project_id=project_id, limit=limit
    )
    if priority == "high":
        items = [item for item in items if item.priority >= 90]
    elif priority == "medium":
        items = [item for item in items if 60 <= item.priority < 90]
    elif priority == "normal":
        items = [item for item in items if item.priority < 60]
    return items


@router.get("/search", response_model=list[SearchResultRead])
def search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[SearchResultRead]:
    return search_all(session, q, limit)
