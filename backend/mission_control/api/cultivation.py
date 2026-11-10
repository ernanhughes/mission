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
    CultivationAppCreate,
    CultivationAppRead,
    CultivationAppRelease,
    CultivationAppRepoAdd,
    CultivationAppUnrelease,
    CultivationAppUpdate,
    CultivationConfig,
    CultivationCycleCreate,
    CultivationCycleFocusUpdate,
    CultivationCycleRead,
    CultivationCycleUpdate,
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
    CultivationRepoBulk,
    CultivationRepoClassify,
    CultivationRepoStateRead,
    CultivationSkillCreate,
    CultivationSkillRead,
    CultivationSkillUpdate,
    CultivationSourceCreate,
    CultivationSourceRead,
    CultivationSourceSyncRead,
    CultivationSourceUpdate,
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
              privacy: str | None = None,
              skill_id: str | None = None) -> list[CultivationGoalRead]:
    return [CultivationGoalRead(**service.goal_read(session, goal))
            for goal in service.list_goals(
                session, include_archived=include_archived, privacy=privacy, skill_id=skill_id)]


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


# ------------------------------------------------------------------ skills
@router.get("/skills", response_model=list[CultivationSkillRead])
def get_skills(session: Session = Depends(get_session),
               include_archived: bool = False) -> list[CultivationSkillRead]:
    return [CultivationSkillRead(**service.skill_read(session, skill))
            for skill in service.list_skills(session, include_archived=include_archived)]


@router.post("/skills", response_model=CultivationSkillRead, status_code=201)
def add_skill(payload: CultivationSkillCreate, session: Session = Depends(get_session)) -> CultivationSkillRead:
    skill = service.create_skill(session, payload.model_dump())
    session.flush()
    return CultivationSkillRead(**service.skill_read(session, skill))


@router.get("/skills/{skill_id}", response_model=CultivationSkillRead)
def get_skill(skill_id: str, session: Session = Depends(get_session)) -> CultivationSkillRead:
    return CultivationSkillRead(**service.skill_read(session, service.get_skill(session, skill_id)))


@router.patch("/skills/{skill_id}", response_model=CultivationSkillRead)
def patch_skill(skill_id: str, payload: CultivationSkillUpdate,
                session: Session = Depends(get_session)) -> CultivationSkillRead:
    skill = service.update_skill(session, skill_id, payload.model_dump(exclude_none=True))
    session.flush()
    return CultivationSkillRead(**service.skill_read(session, skill))


@router.post("/skills/reorder", response_model=OkResponse)
def reorder_skills(payload: ReorderRequest, session: Session = Depends(get_session)) -> OkResponse:
    service.reorder_skill_pins(session, payload.ids)
    return OkResponse()


# ----------------------------------------------------------------- sources
@router.get("/sources", response_model=list[CultivationSourceRead])
def get_sources(session: Session = Depends(get_session)) -> list[CultivationSourceRead]:
    return [CultivationSourceRead(**_source_read(row)) for row in service.list_sources(session)]


@router.post("/sources", response_model=CultivationSourceRead, status_code=201)
def add_source(payload: CultivationSourceCreate, session: Session = Depends(get_session)) -> CultivationSourceRead:
    row = service.create_source(session, payload.model_dump())
    session.flush()
    return CultivationSourceRead(**_source_read(row))


@router.get("/sources/{source_id}", response_model=CultivationSourceRead)
def get_source(source_id: str, session: Session = Depends(get_session)) -> CultivationSourceRead:
    return CultivationSourceRead(**_source_read(service.get_source(session, source_id)))


@router.patch("/sources/{source_id}", response_model=CultivationSourceRead)
def patch_source(source_id: str, payload: CultivationSourceUpdate,
                 session: Session = Depends(get_session)) -> CultivationSourceRead:
    row = service.update_source(session, source_id, payload.model_dump(exclude_none=True))
    session.flush()
    return CultivationSourceRead(**_source_read(row))


@router.post("/sources/{source_id}/sync", response_model=CultivationSourceSyncRead)
def sync_source(source_id: str, session: Session = Depends(get_session)) -> CultivationSourceSyncRead:
    result = service.sync_source(session, source_id)
    session.flush()
    return CultivationSourceSyncRead(
        source_id=result["source_id"], status=result["status"],
        observed=result["observed"], stale=result["stale"],
        error=result.get("error"), goal_id=result.get("goal_id"),
        current=result.get("current"), new_items=result.get("new_items", 0),
        fingerprint_changed=result.get("fingerprint_changed", True))


def _source_read(row) -> dict:
    return {"id": row.id, "name": row.name, "kind": row.kind, "skill_id": row.skill_id,
            "goal_id": row.goal_id, "path": row.path, "config": dict(row.config or {}),
            "last_sync_at": row.last_sync_at, "last_status": row.last_status,
            "last_error": row.last_error, "fingerprint": row.fingerprint,
            "observed": dict(row.observed or {}), "created_at": row.created_at,
            "updated_at": row.updated_at}


# ------------------------------------------------------------------ cycles
@router.get("/cycles", response_model=list[CultivationCycleRead])
def get_cycles(session: Session = Depends(get_session)) -> list[CultivationCycleRead]:
    return [CultivationCycleRead(**service.cycle_read(session, cycle))
            for cycle in service.list_cycles(session)]


@router.post("/cycles", response_model=CultivationCycleRead, status_code=201)
def add_cycle(payload: CultivationCycleCreate, session: Session = Depends(get_session)) -> CultivationCycleRead:
    cycle = service.create_cycle(session, {**payload.model_dump(), "focus_goal_ids": payload.focus_goal_ids})
    session.flush()
    return CultivationCycleRead(**service.cycle_read(session, cycle))


@router.get("/cycles/{cycle_id}", response_model=CultivationCycleRead)
def get_cycle(cycle_id: str, session: Session = Depends(get_session)) -> CultivationCycleRead:
    return CultivationCycleRead(**service.cycle_read(session, service.get_cycle(session, cycle_id)))


@router.patch("/cycles/{cycle_id}", response_model=CultivationCycleRead)
def patch_cycle(cycle_id: str, payload: CultivationCycleUpdate,
                session: Session = Depends(get_session)) -> CultivationCycleRead:
    cycle = service.update_cycle(session, cycle_id, payload.model_dump(exclude_none=True))
    session.flush()
    return CultivationCycleRead(**service.cycle_read(session, cycle))


@router.put("/cycles/{cycle_id}/focus", response_model=CultivationCycleRead)
def set_focus(cycle_id: str, payload: CultivationCycleFocusUpdate,
              session: Session = Depends(get_session)) -> CultivationCycleRead:
    service.set_cycle_focus(session, cycle_id, payload.goal_ids)
    session.flush()
    return CultivationCycleRead(**service.cycle_read(session, service.get_cycle(session, cycle_id)))


@router.post("/cycles/{cycle_id}/rollover", response_model=CultivationCycleRead, status_code=201)
def rollover_cycle(cycle_id: str, session: Session = Depends(get_session)) -> CultivationCycleRead:
    nxt = service.rollover_cycle(session, cycle_id)
    session.flush()
    return CultivationCycleRead(**service.cycle_read(session, nxt))


# ------------------------------------------------- repository inventory
@router.get("/repo-states", response_model=dict)
def list_repo_states(session: Session = Depends(get_session),
                     qualification: str | None = None,
                     classification: str | None = None,
                     lifecycle: str | None = None,
                     root: str | None = None,
                     search: str | None = None,
                     include_unavailable: bool = True,
                     limit: int = Query(default=100, ge=1, le=500),
                     offset: int = Query(default=0, ge=0)) -> dict:
    items, total = service.list_repo_states(
        session, qualification=qualification or None, classification=classification or None,
        lifecycle=lifecycle or None, root=root or None, search=search or None,
        include_unavailable=include_unavailable, limit=limit, offset=offset)
    return {"items": [CultivationRepoStateRead(**row) for row in items],
            "total": total, "limit": limit, "offset": offset}


@router.patch("/repo-states/{repo_id}", response_model=CultivationRepoStateRead)
def classify_repo(repo_id: str, payload: CultivationRepoClassify,
                  session: Session = Depends(get_session)) -> CultivationRepoStateRead:
    state = service.classify_repo(
        session, repo_id, classification=payload.classification,
        lifecycle_stage=payload.lifecycle_stage, qualification=payload.qualification,
        rationale=payload.rationale, evidence=payload.evidence,
        goal_id=payload.goal_id, completed_at=payload.completed_at)
    session.flush()
    return CultivationRepoStateRead(**service.repo_read(session, state))


@router.post("/repo-states/bulk", response_model=dict)
def bulk_qualify(payload: CultivationRepoBulk,
                 session: Session = Depends(get_session)) -> dict:
    return service.bulk_set_qualification(
        session, payload.repo_ids, qualification=payload.qualification,
        rationale=payload.rationale, goal_id=payload.goal_id)


# ------------------------------------------------------------ applications
@router.get("/applications", response_model=list[CultivationAppRead])
def list_applications(session: Session = Depends(get_session),
                      lifecycle: str | None = None,
                      search: str | None = None) -> list[CultivationAppRead]:
    return [CultivationAppRead(**service.app_read(session, app))
            for app in service.list_applications(session, lifecycle=lifecycle or None,
                                                 search=search or None)]


@router.post("/applications", response_model=CultivationAppRead, status_code=201)
def add_application(payload: CultivationAppCreate, session: Session = Depends(get_session)) -> CultivationAppRead:
    app = service.create_application(session, payload.model_dump())
    session.flush()
    return CultivationAppRead(**service.app_read(session, app))


@router.get("/applications/{app_id}", response_model=CultivationAppRead)
def get_application(app_id: str, session: Session = Depends(get_session)) -> CultivationAppRead:
    return CultivationAppRead(**service.app_read(session, service.get_application(session, app_id)))


@router.patch("/applications/{app_id}", response_model=CultivationAppRead)
def patch_application(app_id: str, payload: CultivationAppUpdate,
                       session: Session = Depends(get_session)) -> CultivationAppRead:
    app = service.update_application(session, app_id, payload.model_dump(exclude_none=True))
    session.flush()
    return CultivationAppRead(**service.app_read(session, app))


@router.post("/applications/{app_id}/repos", response_model=CultivationAppRead)
def link_repo(app_id: str, payload: CultivationAppRepoAdd,
              session: Session = Depends(get_session)) -> CultivationAppRead:
    service.link_app_repo(session, app_id, payload.repo_id)
    session.flush()
    return CultivationAppRead(**service.app_read(session, service.get_application(session, app_id)))


@router.delete("/applications/{app_id}/repos/{repo_id}", response_model=CultivationAppRead)
def unlink_repo(app_id: str, repo_id: str, session: Session = Depends(get_session)) -> CultivationAppRead:
    service.unlink_app_repo(session, app_id, repo_id)
    session.flush()
    return CultivationAppRead(**service.app_read(session, service.get_application(session, app_id)))


@router.post("/applications/{app_id}/release", response_model=CultivationAppRead)
def release_application(app_id: str, payload: CultivationAppRelease,
                        session: Session = Depends(get_session)) -> CultivationAppRead:
    app = service.release_application(
        session, app_id, lifecycle=payload.lifecycle, evidence=payload.evidence,
        completed_at=payload.completed_at, goal_id=payload.goal_id, note=payload.note)
    session.flush()
    return CultivationAppRead(**service.app_read(session, app))


@router.post("/applications/{app_id}/unrelease", response_model=CultivationAppRead)
def unrelease_application(app_id: str, payload: CultivationAppUnrelease,
                          session: Session = Depends(get_session)) -> CultivationAppRead:
    app = service.unrelease_application(session, app_id, note=payload.note)
    session.flush()
    return CultivationAppRead(**service.app_read(session, app))
