"""Persistent, evidence-backed software quality evaluation (MC-PROJECTS-QUALITY-02).

Separate domain from manuscript/technical/website evaluations: own tables, own
ids, own rubric. Reuses the approved AI execution layer and the async review
pattern; never invents scores.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import ValidationProblem
from mission_control.models import SoftwareEvalReview
from mission_control.quality_software import service as _service
from mission_control.schemas import (
    SoftwareCharterCreate,
    SoftwareCharterDraftRead,
    SoftwareCharterRead,
    SoftwareCompareRead,
    SoftwareCultivationReportCreate,
    SoftwareCultivationReportRead,
    SoftwareDimensionRead,
    SoftwareEvaluationCreate,
    SoftwareEvaluationDetailRead,
    SoftwareEvaluationPreviewRead,
    SoftwareEvaluationRead,
    SoftwareEvalReviewCreate,
    SoftwareEvalReviewRead,
    SoftwareFindingRead,
    SoftwareFindingReopen,
    SoftwareFindingResolve,
    SoftwareFindingReviewCreate,
    SoftwarePromptCreate,
    SoftwarePromptRead,
)

router = APIRouter(prefix="/api/software-quality", tags=["software-quality"])


def _quality_service(request: Request) -> _service.SoftwareQualityService:
    service = getattr(request.app.state, "software_quality", None)
    if service is None:
        from mission_control.core.errors import NotFound

        raise NotFound("Software quality service is not available")
    return service


def _eval_read(session: Session, row, inspect_dir: Path | str | None = None) -> SoftwareEvaluationRead:
    from mission_control.quality_software.service import evaluation_freshness

    fresh = evaluation_freshness(session, row, inspect_dir)
    dimensions = {
        key: SoftwareDimensionRead(**value) if isinstance(value, dict) else value
        for key, value in (row.dimensions or {}).items()
    }
    return SoftwareEvaluationRead(
        id=row.id, project_id=row.project_id, charter_id=row.charter_id,
        charter_revision=row.charter_revision, repo_uid=row.repo_uid or "",
        repo_path=row.repo_path or "", head_sha=row.head_sha,
        evidence_fingerprint=row.evidence_fingerprint or "",
        rubric_id=row.rubric_id, rubric_version=row.rubric_version,
        prompt_version=row.prompt_version, requested_model=row.requested_model,
        observed_model=row.observed_model, model_route=row.model_route or "",
        status=row.status, overall=row.overall, max_attainable=row.max_attainable,
        coverage_percent=row.coverage_percent, dimensions=dimensions,
        uncertainty=row.uncertainty or "", limitations=list(row.limitations or []),
        execution=dict(row.execution or {}), error=row.error,
        prompt_hash=row.prompt_hash or "", previous_evaluation_id=row.previous_evaluation_id,
        created_at=row.created_at, completed_at=row.completed_at,
        freshness=fresh["state"], freshness_reasons=fresh["reasons"],
    )


# ----------------------------------------------------------------- charters


@router.get("/charter", response_model=SoftwareCharterRead | None)
def get_charter(session: Session = Depends(get_session), project_id: str = Query(...)) -> SoftwareCharterRead | None:
    current = _service.current_charter(session, project_id)
    return SoftwareCharterRead(**current) if current else None


@router.get("/charters", response_model=list[SoftwareCharterRead])
def get_charters(session: Session = Depends(get_session), project_id: str = Query(...)) -> list[SoftwareCharterRead]:
    return [SoftwareCharterRead(**item) for item in _service.list_charters(session, project_id)]


@router.post("/charters/propose", response_model=SoftwareCharterDraftRead)
def propose_charter(session: Session = Depends(get_session), project_id: str = Query(...)) -> SoftwareCharterDraftRead:
    draft = _service.propose_charter(session, project_id)
    return SoftwareCharterDraftRead(**draft)


@router.post("/charters", response_model=SoftwareCharterRead, status_code=status.HTTP_201_CREATED)
def add_charter(payload: SoftwareCharterCreate, session: Session = Depends(get_session)) -> SoftwareCharterRead:
    row = _service.create_charter(session, payload.project_id, payload.model_dump())
    session.commit()
    return SoftwareCharterRead(**_service._charter_read(row))


@router.post("/charters/{charter_id}/confirm", response_model=SoftwareCharterRead)
def confirm_charter(charter_id: str, session: Session = Depends(get_session)) -> SoftwareCharterRead:
    row = _service.confirm_charter(session, charter_id)
    session.commit()
    return SoftwareCharterRead(**_service._charter_read(row))


# ----------------------------------------------------------------- evidence


@router.get("/evidence")
def collect_evidence(
    request: Request, session: Session = Depends(get_session), project_id: str = Query(...)
) -> dict:
    from mission_control.quality_software.evidence import collect_evidence

    return collect_evidence(session, project_id, inspect_dir=request.app.state.settings.inspect_dir)


# --------------------------------------------------------------- evaluations


@router.post("/evaluations/preview", response_model=SoftwareEvaluationPreviewRead)
def preview_evaluation(
    payload: SoftwareEvaluationCreate, request: Request, session: Session = Depends(get_session)
) -> SoftwareEvaluationPreviewRead:
    """Build the exact execution prompt without creating a row or executing."""
    from mission_control.quality_software import service as _svc

    return SoftwareEvaluationPreviewRead(**_svc.build_preview(
        session, payload.project_id, model=payload.model, charter_id=payload.charter_id,
        inspect_dir=request.app.state.settings.inspect_dir,
    ))


@router.post("/evaluations", response_model=SoftwareEvaluationRead, status_code=status.HTTP_201_CREATED)
async def request_evaluation(
    payload: SoftwareEvaluationCreate, request: Request, session: Session = Depends(get_session)
) -> SoftwareEvaluationRead:
    from mission_control.quality_software.service import request_evaluation

    row = request_evaluation(
        session, payload.project_id, model=payload.model,
        charter_id=payload.charter_id, force=payload.force,
        inspect_dir=request.app.state.settings.inspect_dir,
    )
    evaluation_id = row.id
    read = _eval_read(session, row).model_dump()
    session.commit()
    asyncio.create_task(_quality_service(request).execute_evaluation(evaluation_id))
    return SoftwareEvaluationRead(**read)


@router.get("/evaluations", response_model=list[SoftwareEvaluationRead])
def list_evaluations(
    session: Session = Depends(get_session), project_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SoftwareEvaluationRead]:
    from mission_control.quality_software.service import list_evaluations

    return [_eval_read(session, row) for row in list_evaluations(session, project_id, limit)]


@router.get("/evaluations/{evaluation_id}", response_model=SoftwareEvaluationDetailRead)
def get_evaluation(evaluation_id: str, session: Session = Depends(get_session)) -> SoftwareEvaluationDetailRead:
    from mission_control.quality_software import service as _svc

    row = _svc.get_evaluation(session, evaluation_id)
    reviews = session.scalars(
        select(SoftwareEvalReview)
        .where(SoftwareEvalReview.evaluation_id == evaluation_id)
        .order_by(desc(SoftwareEvalReview.created_at))
    ).all()
    findings = [
        f for f in (_svc.list_findings(session, row.project_id) or [])
        if evaluation_id in (f.get("source_evaluations") or [])
    ]
    return SoftwareEvaluationDetailRead(
        evaluation=_eval_read(session, row),
        reviews=[SoftwareEvalReviewRead(**_review_read(r)) for r in reviews],
        findings=[SoftwareFindingRead(**f) for f in findings],
    )


def _review_read(row) -> dict:
    return {
        "id": row.id, "evaluation_id": row.evaluation_id,
        "reviewer_model": row.reviewer_model or "", "model_route": row.model_route or "",
        "status": row.status, "verdict": row.verdict or "",
        "rationale": row.rationale or "",
        "finding_verdicts": list(row.finding_verdicts or []),
        "usage_info": dict(row.usage_info or {}), "error": row.error,
        "created_at": row.created_at, "completed_at": row.completed_at,
    }


@router.get("/evaluations/{first_id}/compare/{second_id}", response_model=SoftwareCompareRead)
def compare_evaluations(first_id: str, second_id: str, session: Session = Depends(get_session)) -> SoftwareCompareRead:
    from mission_control.quality_software import service as _svc

    first = _svc.get_evaluation(session, first_id)
    second = _svc.get_evaluation(session, second_id)
    if first.project_id != second.project_id:
        raise ValidationProblem("Evaluations belong to different projects")
    result = _svc.compare_evaluations(
        {"rubric_id": first.rubric_id, "rubric_version": first.rubric_version,
         "head_sha": first.head_sha, "charter_revision": first.charter_revision,
         "overall": first.overall, "dimensions": first.dimensions or {}},
        {"rubric_id": second.rubric_id, "rubric_version": second.rubric_version,
         "head_sha": second.head_sha, "charter_revision": second.charter_revision,
         "overall": second.overall, "dimensions": second.dimensions or {}},
    )
    return SoftwareCompareRead(
        compatible=result["compatible"], reason=result["reason"],
        warnings=result["warnings"], delta=result["delta"],
        first=_eval_read(session, first), second=_eval_read(session, second),
    )


# --------------------------------------------------- independent reviews


@router.post("/evaluations/{evaluation_id}/reviews", response_model=SoftwareEvalReviewRead, status_code=status.HTTP_201_CREATED)
async def request_review(
    evaluation_id: str, payload: SoftwareEvalReviewCreate, request: Request,
    session: Session = Depends(get_session),
) -> SoftwareEvalReviewRead:
    service = _quality_service(request)
    review = service.request_eval_review(session, evaluation_id, payload.model)
    review_id = review.id
    read = _review_read(review)
    session.commit()
    asyncio.create_task(service.execute_eval_review(review_id))
    return SoftwareEvalReviewRead(**read)


@router.get("/evaluations/{evaluation_id}/reviews", response_model=list[SoftwareEvalReviewRead])
def list_reviews(evaluation_id: str, session: Session = Depends(get_session)) -> list[SoftwareEvalReviewRead]:
    from sqlalchemy import desc, select

    from mission_control.models import SoftwareEvalReview

    rows = session.scalars(
        select(SoftwareEvalReview)
        .where(SoftwareEvalReview.evaluation_id == evaluation_id)
        .order_by(desc(SoftwareEvalReview.created_at))
    ).all()
    return [SoftwareEvalReviewRead(**_review_read(row)) for row in rows]


# ------------------------------------------------------------------ findings


@router.get("/findings", response_model=list[SoftwareFindingRead])
def list_findings(
    session: Session = Depends(get_session), project_id: str = Query(...),
    status: str | None = None, severity: str | None = None,
) -> list[SoftwareFindingRead]:
    from mission_control.quality_software import service as _svc

    return [SoftwareFindingRead(**item) for item in _svc.list_findings(session, project_id, status=status, severity=severity)]


@router.post("/findings/{finding_id}/reviews", response_model=SoftwareFindingRead)
def review_finding(
    finding_id: str, payload: SoftwareFindingReviewCreate, session: Session = Depends(get_session)
) -> SoftwareFindingRead:
    from mission_control.quality_software import service as _svc

    _svc.review_finding(session, finding_id, decision=payload.decision.upper(), reason=payload.reason, reviewer=payload.reviewer or "owner")
    session.commit()
    row = session.get(_svc.SoftwareFinding, finding_id)
    return SoftwareFindingRead(**_svc._finding_read(session, row))


@router.post("/findings/{finding_id}/start", response_model=SoftwareFindingRead)
def start_finding(finding_id: str, session: Session = Depends(get_session)) -> SoftwareFindingRead:
    from mission_control.quality_software import service as _svc

    row = _svc.start_finding_work(session, finding_id)
    session.commit()
    return SoftwareFindingRead(**_svc._finding_read(session, row))


@router.post("/findings/{finding_id}/resolve", response_model=SoftwareFindingRead)
def resolve_finding(
    finding_id: str, payload: SoftwareFindingResolve, session: Session = Depends(get_session)
) -> SoftwareFindingRead:
    from mission_control.quality_software import service as _svc

    row = _svc.resolve_finding(session, finding_id, payload.resolution_evidence)
    session.commit()
    return SoftwareFindingRead(**_svc._finding_read(session, row))


@router.post("/findings/{finding_id}/confirm-resolution", response_model=SoftwareFindingRead)
def confirm_resolution(finding_id: str, session: Session = Depends(get_session)) -> SoftwareFindingRead:
    from mission_control.quality_software import service as _svc

    row = _svc.confirm_resolution(session, finding_id)
    session.commit()
    return SoftwareFindingRead(**_svc._finding_read(session, row))


@router.post("/findings/{finding_id}/reopen", response_model=SoftwareFindingRead)
def reopen_finding(
    finding_id: str, payload: SoftwareFindingReopen, session: Session = Depends(get_session)
) -> SoftwareFindingRead:
    from mission_control.quality_software import service as _svc

    row = _svc.reopen_finding(session, finding_id, payload.reason)
    session.commit()
    return SoftwareFindingRead(**_svc._finding_read(session, row))


# ------------------------------------------------------------------- prompts


@router.post("/prompts", response_model=SoftwarePromptRead, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: SoftwarePromptCreate, session: Session = Depends(get_session)) -> SoftwarePromptRead:
    from mission_control.quality_software import service as _svc

    text = _svc.build_improvement_prompt(session, payload.project_id, payload.finding_ids, payload.scope)
    row = _svc.save_prompt(
        session, payload.project_id, payload.finding_ids, payload.scope, text,
        provenance={"generated_by": "software-quality", "source": "accepted-findings"},
    )
    session.commit()
    return SoftwarePromptRead(
        id=row.id, project_id=row.project_id, finding_ids=list(row.finding_ids or []),
        scope=row.scope, prompt=row.prompt, provenance=dict(row.provenance or {}),
        created_at=row.created_at,
    )


@router.get("/prompts", response_model=list[SoftwarePromptRead])
def list_prompts(
    session: Session = Depends(get_session), project_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[SoftwarePromptRead]:
    from mission_control.quality_software import service as _svc

    return [
        SoftwarePromptRead(
            id=row.id, project_id=row.project_id, finding_ids=list(row.finding_ids or []),
            scope=row.scope, prompt=row.prompt, provenance=dict(row.provenance or {}),
            created_at=row.created_at,
        )
        for row in _svc.list_prompts(session, project_id, limit)
    ]


# ---------------------------------------------------------------- cultivation


@router.post("/cultivation-report", response_model=SoftwareCultivationReportRead)
def cultivation_report(
    payload: SoftwareCultivationReportCreate, session: Session = Depends(get_session)
) -> SoftwareCultivationReportRead:
    from mission_control.quality_software import service as _svc

    result = _svc.report_progress(
        session, project_id=payload.project_id, goal_id=payload.goal_id,
        item_id=payload.item_id, note=payload.note,
        finding_id=payload.finding_id, evaluation_id=payload.evaluation_id,
    )
    session.commit()
    return SoftwareCultivationReportRead(**result)


@router.get("/models")
async def quality_models(request: Request, session: Session = Depends(get_session)) -> dict:
    from mission_control.research.inference import discover_local_models

    return await discover_local_models(session)
