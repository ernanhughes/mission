"""Cultivation goals, items, milestones, ranks and HUD (MC-CULTIVATION-01).

Read-only by default for the interface: opening any cultivation view starts no
model calls. All progress derives from stored rows and labelled estimates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import ValidationProblem
from mission_control.cultivation import service
from mission_control.schemas import (
    CultivationConfig,
    CultivationEvidenceCreate,
    CultivationEvidenceRead,
    CultivationEventRead,
    CultivationGoalCreate,
    CultivationGoalRead,
    CultivationGoalUpdate,
    CultivationHudRead,
    CultivationItemCreate,
    CultivationItemRead,
    CultivationItemUpdate,
    CultivationMeasurementCreate,
    CultivationMeasurementRead,
    CultivationMembershipRead,
    CultivationQualifyUpdate,
    CultivationRankStatus,
    CultivationStageUpdate,
    OkResponse,
    ReorderRequest,
)

router = APIRouter(prefix="/api/cultivation", tags=["cultivation"])


def _membership_read(row) -> CultivationMembershipRead:
    return CultivationMembershipRead(
        item_id=row.item_id, goal_id=row.goal_id, goal_name=None, stage=row.stage,
        evidence_status=row.evidence_status, quality_evidence=dict(row.quality_evidence or {}),
        qualified=bool(row.qualified), qualified_at=row.qualified_at,
        completed_at=row.completed_at, created_at=row.created_at, updated_at=row.updated_at)


# ------------------------------------------------------------------ goals
@router.get("/goals", response_model=list[CultivationGoalRead])
def get_goals(session: Session = Depends(get_session),
              include_archived: bool = False,
              privacy: str | None = None) -> list[CultivationGoalRead]:
    return [CultivationGoalRead(**service.goal_read(session, goal))
            for goal in service.list_goals(session, include_archived=include_archived, privacy=privacy)]


@router.post("/goals", response_model=CultivationGoalRead, status_code=201)
def add_goal(payload: CultivationGoalCreate, session: Session = Depends(get_session)) -> CultivationGoalRead:
    goal = service.create_goal(session, payload.model_dump())
    session.flush()
    return CultivationGoalRead(**service.goal_read(session, goal))


@router.get("/goals/{goal_id}", response_model=CultivationGoalRead)
def get_goal(goal_id: str, session: Session = Depends(get_session)) -> CultivationGoalRead:
    return CultivationGoalRead(**service.goal_read(session, service.get_goal(session, goal_id)))


@router.patch("/goals/{goal_id}", response_model=CultivationGoalRead)
def patch_goal(goal_id: str, payload: CultivationGoalUpdate,
               session: Session = Depends(get_session)) -> CultivationGoalRead:
    goal = service.update_goal(session, goal_id, payload.model_dump(exclude_none=True))
    session.flush()
    return CultivationGoalRead(**service.goal_read(session, goal))


@router.post("/goals/reorder", response_model=OkResponse)
def reorder_goals(payload: ReorderRequest, session: Session = Depends(get_session)) -> OkResponse:
    service.reorder_pins(session, payload.ids)
    return OkResponse()


@router.get("/goals/{goal_id}/items", response_model=list[CultivationItemRead])
def goal_items(goal_id: str, session: Session = Depends(get_session),
               stage: str | None = None) -> list[CultivationItemRead]:
    service.get_goal(session, goal_id)
    from sqlalchemy import select as _select
    from mission_control.models import CultivationItem as _Item, CultivationMembership as _Membership
    query = _select(_Item).join(_Membership, _Membership.item_id == _Item.id).where(
        _Membership.goal_id == goal_id).order_by(_Item.title)
    if stage:
        query = query.where(_Membership.stage == stage)
    return [CultivationItemRead(**service.item_read(session, item))
            for item in session.scalars(query).all()]


@router.get("/goals/{goal_id}/measurements", response_model=list[CultivationMeasurementRead])
def goal_measurements(goal_id: str, session: Session = Depends(get_session)) -> list[CultivationMeasurementRead]:
    from sqlalchemy import desc as _desc, select as _select
    from mission_control.models import CultivationMeasurement as _Measurement
    service.get_goal(session, goal_id)
    rows = session.scalars(_select(_Measurement).where(
        _Measurement.goal_id == goal_id).order_by(_desc(_Measurement.observed_at)).limit(500)).all()
    return [CultivationMeasurementRead(id=row.id, goal_id=row.goal_id, value=row.value,
                                       observed_at=row.observed_at, note=row.note,
                                       source=row.source, created_at=row.created_at) for row in rows]


@router.post("/goals/{goal_id}/measurements", response_model=CultivationMeasurementRead, status_code=201)
def add_measurement(goal_id: str, payload: CultivationMeasurementCreate,
                    session: Session = Depends(get_session)) -> CultivationMeasurementRead:
    row = service.record_measurement(session, goal_id, value=payload.value,
                                     observed_at=payload.observed_at, note=payload.note,
                                     source=payload.source)
    session.flush()
    return CultivationMeasurementRead(id=row.id, goal_id=row.goal_id, value=row.value,
                                      observed_at=row.observed_at, note=row.note,
                                      source=row.source, created_at=row.created_at)


@router.get("/goals/{goal_id}/evidence", response_model=list[CultivationEvidenceRead])
def goal_evidence(goal_id: str, session: Session = Depends(get_session)) -> list[CultivationEvidenceRead]:
    from sqlalchemy import desc as _desc, select as _select
    from mission_control.models import CultivationEvidence as _Evidence
    service.get_goal(session, goal_id)
    rows = session.scalars(_select(_Evidence).where(
        _Evidence.goal_id == goal_id).order_by(_desc(_Evidence.created_at)).limit(200)).all()
    return [CultivationEvidenceRead(id=row.id, goal_id=row.goal_id, item_id=row.item_id,
                                    kind=row.kind, reference=row.reference, note=row.note,
                                    verified=bool(row.verified), created_at=row.created_at) for row in rows]


@router.post("/goals/{goal_id}/evidence", response_model=CultivationEvidenceRead, status_code=201)
def add_goal_evidence(goal_id: str, payload: CultivationEvidenceCreate,
                      session: Session = Depends(get_session)) -> CultivationEvidenceRead:
    row = service.add_evidence(session, goal_id, item_id=payload.item_id, kind=payload.kind,
                               reference=payload.reference, note=payload.note, verified=payload.verified)
    session.flush()
    return CultivationEvidenceRead(id=row.id, goal_id=row.goal_id, item_id=row.item_id,
                                   kind=row.kind, reference=row.reference, note=row.note,
                                   verified=bool(row.verified), created_at=row.created_at)


@router.get("/goals/{goal_id}/events", response_model=list[CultivationEventRead])
def goal_events(goal_id: str, session: Session = Depends(get_session),
                limit: int = Query(default=100, ge=1, le=500)) -> list[CultivationEventRead]:
    service.get_goal(session, goal_id)
    return [CultivationEventRead(**service.event_read(session, event))
            for event in service.list_events(session, goal_id=goal_id, limit=limit)]


# ------------------------------------------------------------------ items
@router.get("/items", response_model=list[CultivationItemRead])
def get_items(session: Session = Depends(get_session),
              search: str | None = None,
              limit: int = Query(default=200, ge=1, le=500)) -> list[CultivationItemRead]:
    from sqlalchemy import select as _select
    from mission_control.models import CultivationItem as _Item
    query = _select(_Item).order_by(_Item.title).limit(limit)
    if search:
        needle = f"%{search}%"
        query = query.where(_Item.title.ilike(needle))
    return [CultivationItemRead(**service.item_read(session, item))
            for item in session.scalars(query).all()]


@router.post("/items", response_model=CultivationItemRead, status_code=201)
def add_item(payload: CultivationItemCreate, session: Session = Depends(get_session)) -> CultivationItemRead:
    item = service.create_item(session, payload.model_dump())
    session.flush()
    return CultivationItemRead(**service.item_read(session, item))


@router.get("/items/{item_id}", response_model=CultivationItemRead)
def get_item(item_id: str, session: Session = Depends(get_session)) -> CultivationItemRead:
    from mission_control.models import CultivationItem as _Item
    item = session.get(_Item, item_id)
    if item is None:
        from mission_control.core.errors import NotFound as _NotFound
        raise _NotFound("Item not found")
    return CultivationItemRead(**service.item_read(session, item))


@router.patch("/items/{item_id}", response_model=CultivationItemRead)
def patch_item(item_id: str, payload: CultivationItemUpdate,
               session: Session = Depends(get_session)) -> CultivationItemRead:
    item = service.update_item(session, item_id, payload.model_dump(exclude_none=False))
    session.flush()
    return CultivationItemRead(**service.item_read(session, item))


@router.post("/items/{item_id}/goals/{goal_id}", response_model=CultivationMembershipRead, status_code=201)
def attach_item(item_id: str, goal_id: str, session: Session = Depends(get_session)) -> CultivationMembershipRead:
    row = service.add_membership(session, item_id, goal_id)
    if row is None:
        raise ValidationProblem("Could not attach item to goal")
    session.flush()
    return _membership_read(row)


@router.patch("/items/{item_id}/goals/{goal_id}/stage", response_model=CultivationMembershipRead)
def move_stage(item_id: str, goal_id: str, payload: CultivationStageUpdate,
               session: Session = Depends(get_session),
               completed_at: str | None = None) -> CultivationMembershipRead:
    row = service.set_stage(session, item_id, goal_id, stage=payload.stage,
                            note=payload.note, evidence_ref=payload.evidence_ref,
                            completed_at=completed_at)
    session.flush()
    return _membership_read(row)


@router.patch("/items/{item_id}/goals/{goal_id}/qualify", response_model=CultivationMembershipRead)
def qualify_item(item_id: str, goal_id: str, payload: CultivationQualifyUpdate,
                 session: Session = Depends(get_session)) -> CultivationMembershipRead:
    row = service.set_qualified(session, item_id, goal_id, qualified=payload.qualified,
                                quality_evidence=payload.quality_evidence, note=payload.note)
    session.flush()
    return _membership_read(row)


@router.get("/items/{item_id}/events", response_model=list[CultivationEventRead])
def item_events(item_id: str, session: Session = Depends(get_session),
                limit: int = Query(default=100, ge=1, le=500)) -> list[CultivationEventRead]:
    return [CultivationEventRead(**service.event_read(session, event))
            for event in service.list_events(session, item_id=item_id, limit=limit)]


# ------------------------------------------------------- ranks / HUD / config
@router.get("/ranks", response_model=list[CultivationRankStatus])
def get_ranks(session: Session = Depends(get_session)) -> list[CultivationRankStatus]:
    status = service.rank_status(session)
    return [CultivationRankStatus(**rank) for rank in status["ranks"]]


@router.get("/hud", response_model=CultivationHudRead)
def get_hud(session: Session = Depends(get_session)) -> CultivationHudRead:
    return CultivationHudRead(**service.hud_summary(session))


@router.get("/config", response_model=CultivationConfig)
def get_config(session: Session = Depends(get_session)) -> CultivationConfig:
    return CultivationConfig(**service.get_config(session))


@router.patch("/config", response_model=CultivationConfig)
def update_config(payload: dict, session: Session = Depends(get_session)) -> CultivationConfig:
    return CultivationConfig(**service.update_config(
        session, stages=payload.get("stages"), ranks=payload.get("ranks")))
