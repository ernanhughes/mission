"""Experiment workflow API."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from mission_control.schemas import (
    ExperimentWorkflowRead,
    WorkflowApprove,
    WorkflowCreate,
    WorkflowDecision,
    WorkflowExecute,
)
from mission_control.workflows.service import WorkflowService

router = APIRouter(prefix="/api", tags=["workflows"])


def _service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


@router.get("/workflows", response_model=list[ExperimentWorkflowRead])
def list_workflows(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> list[ExperimentWorkflowRead]:
    return _service(request).list(limit)


@router.post("/workflows", response_model=ExperimentWorkflowRead)
def create_workflow(
    payload: WorkflowCreate, request: Request
) -> ExperimentWorkflowRead:
    return _service(request).create(
        payload.record_id,
        payload.template,
        payload.project_id,
        force_new=payload.force_new,
    )


@router.get("/workflows/{workflow_id}", response_model=ExperimentWorkflowRead)
def get_workflow(workflow_id: str, request: Request) -> ExperimentWorkflowRead:
    return _service(request).get(workflow_id)


@router.post(
    "/workflows/{workflow_id}/approve", response_model=ExperimentWorkflowRead
)
def approve_workflow(
    workflow_id: str, payload: WorkflowApprove, request: Request
) -> ExperimentWorkflowRead:
    return _service(request).approve(
        workflow_id,
        confirm=payload.confirm,
        approved_by=payload.approved_by,
        scope_acknowledged=payload.scope_acknowledged,
    )


@router.post(
    "/workflows/{workflow_id}/execute", response_model=ExperimentWorkflowRead
)
async def execute_workflow(
    workflow_id: str, payload: WorkflowExecute, request: Request
) -> ExperimentWorkflowRead:
    service = _service(request)
    result = await service.execute(workflow_id, confirm=payload.confirm)
    if result.status == "executed":
        result = await service.review(workflow_id)
    return result


@router.post(
    "/workflows/{workflow_id}/review", response_model=ExperimentWorkflowRead
)
async def review_workflow(workflow_id: str, request: Request) -> ExperimentWorkflowRead:
    return await _service(request).review(workflow_id)


@router.post(
    "/workflows/{workflow_id}/decision", response_model=ExperimentWorkflowRead
)
def decide_workflow(
    workflow_id: str, payload: WorkflowDecision, request: Request
) -> ExperimentWorkflowRead:
    return _service(request).decide(
        workflow_id,
        decision=payload.decision,
        reason=payload.reason,
        override_adverse=payload.override_adverse,
    )
