"""Cultivation goals, items, milestones and ranks (MC-CULTIVATION-01).

The unit of progress is a meaningful completed artefact or measurement, never
an invented score. Counts recompute from stored rows; user estimates are
labelled with their provenance and never silently converted into evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.models import (
    Book,
    CultivationEvent,
    CultivationEvidence,
    CultivationGoal,
    CultivationItem,
    CultivationMeasurement,
    CultivationMembership,
    Project,
    Setting,
)
from mission_control.persistence.db import now_iso

MEASUREMENT_TYPES = {"count", "threshold_up", "threshold_down", "recurring", "qualified_count"}
GOAL_STATES = {"active", "paused", "achieved", "archived"}
PRIVACY_LEVELS = {"standard", "private"}
PROVENANCE_VALUES = {"human", "ai_assisted", "ai_workflow", "unclassified"}
BASELINE_PROVENANCE = {"none", "estimate", "user_assertion", "verified"}
EVIDENCE_STATUS = {"none", "claimed", "verified"}

DEFAULT_STAGES = [
    {"id": "idea", "label": "Idea", "color": "grey"},
    {"id": "development", "label": "In development", "color": "blue"},
    {"id": "editing", "label": "Editing / review", "color": "amber"},
    {"id": "ready", "label": "Ready", "color": "cyan"},
    {"id": "published", "label": "Published / completed", "color": "green"},
]

DEFAULT_RANKS = [
    {"id": "initiate", "name": "Initiate", "concept": "The first real completed work.",
     "requires": {"type": "total_completions", "count": 1}},
    {"id": "qi_refinement", "name": "Qi Refinement", "concept": "Repeated production becomes an established practice.",
     "requires": {"type": "total_completions", "count": 10}},
    {"id": "foundation", "name": "Foundation Establishment", "concept": "A major body of work, such as 100 published books.",
     "requires": {"type": "goals_achieved", "goal_ids": ["published_books"]}},
    {"id": "core_formation", "name": "Core Formation", "concept": "Mastery across multiple creative or technical disciplines.",
     "requires": {"type": "goals_achieved_count", "goal_ids": ["published_books", "movies", "songs", "research_papers", "applications"], "count": 2}},
    {"id": "nascent_soul", "name": "Nascent Soul", "concept": "Sustained, independently demonstrated quality and capability across many disciplines.",
     "requires": {"type": "goals_achieved", "goal_ids": ["published_books", "perfect_repositories"]}},
    {"id": "higher_realms", "name": "Higher realms", "concept": "Reserved for later achievements.",
     "requires": {"type": "total_completions", "count": 1000}},
]

DEFAULT_MILESTONES = [1.0, 10.0, 25.0, 50.0, 75.0, 100.0]


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def get_config(session: Session) -> dict[str, Any]:
    setting = session.get(Setting, "cultivation")
    if setting and isinstance(setting.value, dict):
        stages = setting.value.get("stages") or []
        ranks = setting.value.get("ranks") or []
        return {"stages": stages, "ranks": ranks}
    return {"stages": [dict(stage) for stage in DEFAULT_STAGES],
            "ranks": [dict(rank) for rank in DEFAULT_RANKS]}


def update_config(session: Session, *, stages=None, ranks=None) -> dict[str, Any]:
    config = get_config(session)
    if stages is not None:
        if not isinstance(stages, list) or not stages:
            raise ValidationProblem("stages must be a non-empty list")
        seen: set[str] = set()
        for stage in stages:
            if not isinstance(stage, dict) or not str(stage.get("id") or "").strip():
                raise ValidationProblem("Each stage needs a non-empty id")
            if stage["id"] in seen:
                raise ValidationProblem(f"Duplicate stage id: {stage['id']}")
            seen.add(stage["id"])
        config["stages"] = [{"id": str(item["id"])[:60], "label": str(item.get("label") or item["id"])[:80],
                             "color": str(item.get("color") or "grey")[:20]} for item in stages]
    if ranks is not None:
        if not isinstance(ranks, list) or not ranks:
            raise ValidationProblem("ranks must be a non-empty list")
        for rank in ranks:
            if not isinstance(rank, dict) or not str(rank.get("id") or "").strip() or not str(rank.get("name") or "").strip():
                raise ValidationProblem("Each rank needs an id and a name")
            if not isinstance(rank.get("requires"), dict):
                raise ValidationProblem("Each rank needs a requires mapping")
        config["ranks"] = ranks
    setting = session.get(Setting, "cultivation")
    if setting is None:
        session.add(Setting(key="cultivation", value=config, updated_at=now_iso()))
    else:
        setting.value = config
        setting.updated_at = now_iso()
    session.flush()
    return config


def _stage_ids(session: Session) -> set[str]:
    return {str(stage["id"]) for stage in get_config(session)["stages"]}


def _validate_goal_payload(payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    if not partial or "measurement_type" in payload:
        measurement_type = str(payload.get("measurement_type", "count"))
        if measurement_type not in MEASUREMENT_TYPES:
            raise ValidationProblem(f"Unknown measurement_type: {measurement_type}")
        cleaned["measurement_type"] = measurement_type
    if not partial or "state" in payload:
        state = str(payload.get("state", "active"))
        if state not in GOAL_STATES:
            raise ValidationProblem(f"Unknown state: {state}")
        cleaned["state"] = state
    if not partial or "privacy" in payload:
        privacy = str(payload.get("privacy", "standard"))
        if privacy not in PRIVACY_LEVELS:
            raise ValidationProblem(f"Unknown privacy: {privacy}")
        cleaned["privacy"] = privacy
    if "baseline_provenance" in payload or not partial:
        provenance = str(payload.get("baseline_provenance", "none"))
        if provenance not in BASELINE_PROVENANCE:
            raise ValidationProblem(f"Unknown baseline_provenance: {provenance}")
        cleaned["baseline_provenance"] = provenance
    if "qualifying_stage" in payload or not partial:
        cleaned["qualifying_stage"] = str(payload.get("qualifying_stage", "published"))[:60]
    if "milestones" in payload and payload["milestones"] is not None:
        try:
            cleaned["milestones"] = sorted({float(value) for value in payload["milestones"]})
        except (TypeError, ValueError):
            raise ValidationProblem("milestones must be a list of numbers") from None
    return cleaned


def _record_event(session: Session, *, goal_id: str | None, item_id: str | None = None,
                  event_type: str, from_value: str | None = None, to_value: str | None = None,
                  note: str = "", evidence_ref: str | None = None,
                  occurred_at: str | None = None) -> None:
    session.add(CultivationEvent(
        id=_new_id("gev"), goal_id=goal_id, item_id=item_id, event_type=event_type,
        from_value=from_value, to_value=to_value, note=note[:4000],
        evidence_ref=evidence_ref, occurred_at=occurred_at, created_at=now_iso(),
    ))
    session.flush()


def _check_milestones(session: Session, goal: CultivationGoal, current: float | None) -> None:
    if current is None:
        return
    for milestone in sorted(set(float(value) for value in (goal.milestones or []))):
        if current < milestone:
            continue
        existing = session.scalar(select(CultivationEvent).where(
            CultivationEvent.goal_id == goal.id, CultivationEvent.event_type == "milestone",
            CultivationEvent.to_value == str(milestone)).limit(1))
        if existing is None:
            _record_event(session, goal_id=goal.id, event_type="milestone",
                          to_value=str(milestone), note=f"Reached {milestone:g} of {goal.target_value:g} {goal.unit}.")


def _qualified_memberships(session: Session, goal: CultivationGoal) -> list[CultivationMembership]:
    return list(session.scalars(select(CultivationMembership).where(
        CultivationMembership.goal_id == goal.id,
        CultivationMembership.stage == goal.qualifying_stage)).all())


def _pipeline(session: Session, goal: CultivationGoal) -> dict[str, int]:
    rows = session.execute(select(CultivationMembership.stage, func.count()).where(
        CultivationMembership.goal_id == goal.id).group_by(CultivationMembership.stage)).all()
    return {str(stage): int(count) for stage, count in rows}


def goal_progress(session: Session, goal: CultivationGoal) -> dict[str, Any]:
    """Recompute progress from stored rows. Unknown stays unknown — never estimated."""
    measurement_type = goal.measurement_type
    baseline = goal.baseline_value or 0.0
    has_baseline = goal.baseline_value is not None
    pipeline = _pipeline(session, goal)

    if measurement_type in {"count", "qualified_count"}:
        memberships = _qualified_memberships(session, goal)
        if measurement_type == "qualified_count":
            memberships = [row for row in memberships if row.qualified]
        tracked = len(memberships)
        current = baseline + tracked
        achieved = current >= goal.target_value
        label = None
        if has_baseline and goal.baseline_provenance in {"estimate", "user_assertion"}:
            kind = "estimate" if goal.baseline_provenance == "estimate" else "user-attested prior achievements"
            label = f"≈{current:g} ({baseline:g} {kind} + {tracked} tracked)"
        elif has_baseline:
            label = f"{current:g} ({baseline:g} verified prior + {tracked} tracked)"
        milestones = sorted(set(float(value) for value in (goal.milestones or [])))
        reached = [value for value in milestones if current >= value]
        upcoming = [value for value in milestones if value > current]
        return {"current": current, "target": goal.target_value, "unit": goal.unit,
                "percent": min(100.0, current / goal.target_value * 100.0) if goal.target_value > 0 else None,
                "unknown_reason": None, "achieved": achieved, "estimate_label": label,
                "item_count": tracked, "pipeline": pipeline,
                "milestones_reached": reached, "next_milestone": upcoming[0] if upcoming else None}

    if measurement_type == "threshold_up":
        latest = session.scalars(select(CultivationMeasurement).where(
            CultivationMeasurement.goal_id == goal.id).order_by(desc(CultivationMeasurement.value)).limit(1)).first()
        return _metric_progress(goal, latest.value if latest else None, pipeline)

    if measurement_type == "threshold_down":
        if not has_baseline:
            return _unknown(goal, pipeline, "Needs a starting baseline before progress can be measured.")
        if goal.target_value >= goal.baseline_value:
            return _unknown(goal, pipeline, "Target must be below the baseline for a decreasing goal.")
        latest = session.scalars(select(CultivationMeasurement).where(
            CultivationMeasurement.goal_id == goal.id).order_by(desc(CultivationMeasurement.observed_at)).limit(1)).first()
        if latest is None:
            return _unknown(goal, pipeline, "No measurements recorded yet.")
        span = goal.baseline_value - goal.target_value
        percent = min(100.0, max(0.0, (goal.baseline_value - latest.value) / span * 100.0))
        return {"current": latest.value, "target": goal.target_value, "unit": goal.unit,
                "percent": percent, "unknown_reason": None, "achieved": latest.value <= goal.target_value,
                "estimate_label": None, "item_count": 0, "pipeline": pipeline,
                "milestones_reached": [], "next_milestone": None}

    if measurement_type == "recurring":
        window = goal.window_days or 0
        if window <= 0:
            return _unknown(goal, pipeline, "Needs a measurement window (window_days) before progress can be measured.")
        rows = session.scalars(select(CultivationMeasurement).where(
            CultivationMeasurement.goal_id == goal.id).order_by(desc(CultivationMeasurement.observed_at))).all()
        by_day: dict[str, float] = {}
        for row in rows:
            day = (row.observed_at or "")[:10]
            if day and day not in by_day:
                by_day[day] = max(by_day.get(day, float("-inf")), row.value)
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        met = 0
        for offset in range(window):
            day = (today - _td(days=offset)).isoformat()
            if by_day.get(day, float("-inf")) >= goal.target_value:
                met += 1
        return {"current": float(met), "target": float(window), "unit": "days met",
                "percent": met / window * 100.0, "unknown_reason": None, "achieved": met >= window,
                "estimate_label": None, "item_count": 0, "pipeline": pipeline,
                "milestones_reached": [], "next_milestone": None}

    raise ValidationProblem(f"Unknown measurement_type: {measurement_type}")


def _metric_progress(goal: CultivationGoal, current: float | None, pipeline: dict[str, int]) -> dict[str, Any]:
    if current is None:
        return _unknown(goal, pipeline, "No measurements recorded yet.")
    return {"current": current, "target": goal.target_value, "unit": goal.unit,
            "percent": min(100.0, current / goal.target_value * 100.0) if goal.target_value > 0 else None,
            "unknown_reason": None, "achieved": current >= goal.target_value,
            "estimate_label": None, "item_count": 0, "pipeline": pipeline,
            "milestones_reached": [], "next_milestone": None}


def _unknown(goal: CultivationGoal, pipeline: dict[str, int], reason: str) -> dict[str, Any]:
    return {"current": None, "target": goal.target_value, "unit": goal.unit,
            "percent": None, "unknown_reason": reason, "achieved": False,
            "estimate_label": None, "item_count": 0, "pipeline": pipeline,
            "milestones_reached": [], "next_milestone": None}


def total_completions(session: Session) -> int:
    item_completions = session.scalar(select(func.count()).select_from(CultivationMembership).where(
        CultivationMembership.completed_at.is_not(None))) or 0
    metric_achieved = 0
    for goal in session.scalars(select(CultivationGoal).where(
            CultivationGoal.measurement_type.not_in(["count", "qualified_count"]))).all():
        progress = goal_progress(session, goal)
        if progress["achieved"]:
            metric_achieved += 1
    return int(item_completions) + int(metric_achieved)


def rank_status(session: Session) -> dict[str, Any]:
    config = get_config(session)
    achieved_ids = {row.id for row in session.scalars(
        select(CultivationGoal).where(CultivationGoal.state == "achieved")).all()}
    total = total_completions(session)
    ranks = []
    current = None
    for rank in config["ranks"]:
        requires = rank.get("requires") or {}
        kind = requires.get("type")
        qualified = False
        if kind == "total_completions":
            qualified = total >= int(requires.get("count", 0))
        elif kind == "goals_achieved":
            qualified = all(goal_id in achieved_ids for goal_id in (requires.get("goal_ids") or []))
        elif kind == "goals_achieved_count":
            need = int(requires.get("count", 0))
            qualified = sum(1 for goal_id in (requires.get("goal_ids") or []) if goal_id in achieved_ids) >= need
        elif kind == "any_goals_achieved":
            qualified = len(achieved_ids) >= int(requires.get("count", 0))
        elif kind == "milestone":
            goal = session.get(CultivationGoal, str(requires.get("goal_id") or ""))
            if goal is not None:
                qualified = (goal_progress(session, goal)["current"] or 0) >= float(requires.get("value", 0))
        entry = {"id": rank["id"], "name": rank["name"], "concept": rank.get("concept", ""),
                 "qualified": qualified, "requires": requires}
        ranks.append(entry)
        if qualified:
            current = entry
    return {"ranks": ranks, "current": current}


# ------------------------------------------------------------------ goals
def list_goals(session: Session, *, include_archived: bool = False,
               privacy: str | None = None) -> list[CultivationGoal]:
    query = select(CultivationGoal).order_by(CultivationGoal.priority, CultivationGoal.name)
    if not include_archived:
        query = query.where(CultivationGoal.state != "archived")
    if privacy in PRIVACY_LEVELS:
        query = query.where(CultivationGoal.privacy == privacy)
    return list(session.scalars(query).all())


def get_goal(session: Session, goal_id: str) -> CultivationGoal:
    goal = session.get(CultivationGoal, goal_id)
    if goal is None:
        raise NotFound("Goal not found")
    return goal


def create_goal(session: Session, payload: dict[str, Any]) -> CultivationGoal:
    validated = _validate_goal_payload(payload, partial=False)
    goal_id = str(payload.get("id") or _new_id("goal"))
    if not goal_id or len(goal_id) > 80:
        raise ValidationProblem("Goal id must be 1-80 characters")
    if session.get(CultivationGoal, goal_id) is not None:
        raise Conflict("Goal id already exists")
    milestones = validated.pop("milestones", None)
    if milestones is None:
        target = float(payload.get("target_value", 100))
        milestones = [value for value in DEFAULT_MILESTONES if value <= target] or [target]
        if target not in milestones:
            milestones = sorted(set(milestones + [target]))
    goal = CultivationGoal(
        id=goal_id, name=str(payload.get("name", "")).strip()[:120],
        description=str(payload.get("description", ""))[:4000],
        category=str(payload.get("category", "general"))[:60],
        unit=str(payload.get("unit", "items"))[:60],
        target_value=float(payload.get("target_value", 100)),
        baseline_value=payload.get("baseline_value"),
        baseline_note=str(payload.get("baseline_note", ""))[:2000],
        window_days=payload.get("window_days"),
        priority=int(payload.get("priority", 100)),
        pinned=bool(payload.get("pinned", False)),
        pin_order=int(payload.get("pin_order", 100)),
        dependencies=list(payload.get("dependencies", []) or [])[:50],
        evidence_source=str(payload.get("evidence_source", "manual"))[:60],
        completion_criteria=str(payload.get("completion_criteria", ""))[:2000],
        milestones=milestones,
        created_at=now_iso(), updated_at=now_iso(), **validated,
    )
    if not goal.name:
        raise ValidationProblem("Goal name must not be empty")
    session.add(goal)
    session.flush()
    _record_event(session, goal_id=goal.id, event_type="goal_created", note=f"Goal '{goal.name}' created.")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    return goal


def update_goal(session: Session, goal_id: str, payload: dict[str, Any]) -> CultivationGoal:
    goal = get_goal(session, goal_id)
    validated = _validate_goal_payload(payload, partial=True)
    changes: list[str] = []
    for field in ("name", "description", "category", "unit", "completion_criteria",
                  "evidence_source", "qualifying_stage", "baseline_note"):
        if field in payload and payload[field] is not None:
            value = str(payload[field])
            if getattr(goal, field) != value:
                changes.append(field)
                setattr(goal, field, value[:4000] if field in {"description", "completion_criteria", "baseline_note"} else value[:120])
    for field in ("target_value", "baseline_value", "window_days", "priority", "pin_order"):
        if field in payload and payload[field] is not None:
            if getattr(goal, field) != payload[field]:
                changes.append(field)
                setattr(goal, field, payload[field])
    for field, value in validated.items():
        if field == "milestones":
            continue  # handled below
        if getattr(goal, field) != value:
            changes.append(field)
            setattr(goal, field, value)
    if "pinned" in payload and payload["pinned"] is not None:
        if bool(goal.pinned) != bool(payload["pinned"]):
            changes.append("pinned")
            goal.pinned = bool(payload["pinned"])
    if "milestones" in validated:
        goal.milestones = validated["milestones"]
    if "dependencies" in payload and payload["dependencies"] is not None:
        goal.dependencies = list(payload["dependencies"])[:50]
        changes.append("dependencies")
    goal.updated_at = now_iso()
    session.flush()
    if changes:
        _record_event(session, goal_id=goal.id, event_type="goal_updated",
                      note=f"Updated: {', '.join(sorted(set(changes)))}.")
    if "baseline_value" in changes or "target_value" in changes:
        _record_event(session, goal_id=goal.id, event_type="correction",
                      note=f"Baseline/target adjusted (baseline={goal.baseline_value}, target={goal.target_value}).")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    return goal


def reorder_pins(session: Session, ordered_ids: list[str]) -> None:
    for position, goal_id in enumerate(ordered_ids[:100]):
        goal = session.get(CultivationGoal, goal_id)
        if goal is None:
            raise NotFound(f"Goal not found: {goal_id}")
        goal.pin_order = position
        goal.updated_at = now_iso()
    session.flush()


# ------------------------------------------------------------------ items
def _validate_provenance(value: str) -> str:
    text = str(value or "unclassified")
    if text not in PROVENANCE_VALUES:
        raise ValidationProblem(f"Unknown provenance: {value}")
    return text


def create_item(session: Session, payload: dict[str, Any]) -> CultivationItem:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValidationProblem("Item title must not be empty")
    item_id = str(payload.get("id") or _new_id("item"))
    if session.get(CultivationItem, item_id) is not None:
        raise Conflict("Item id already exists")
    item = CultivationItem(
        id=item_id, title=title[:300], item_type=str(payload.get("item_type", "work"))[:60],
        notes=str(payload.get("notes", ""))[:4000], tags=list(payload.get("tags", []) or [])[:50],
        provenance=_validate_provenance(payload.get("provenance", "unclassified")),
        source_application=payload.get("source_application"),
        source_project_id=payload.get("source_project_id"),
        source_ref=payload.get("source_ref"),
        created_at=now_iso(), updated_at=now_iso(),
    )
    if item.source_project_id and session.get(Project, item.source_project_id) is None:
        raise ValidationProblem("Linked project does not exist")
    session.add(item)
    session.flush()
    stage = str(payload.get("stage", "idea"))
    if stage not in _stage_ids(session):
        raise ValidationProblem(f"Unknown stage: {stage}")
    for goal_id in list(payload.get("goal_ids", []) or [])[:20]:
        add_membership(session, item.id, goal_id, stage=stage)
    _record_event(session, goal_id=None, item_id=item.id, event_type="item_created",
                  note=f"Item '{item.title}' created.")
    return item


def update_item(session: Session, item_id: str, payload: dict[str, Any]) -> CultivationItem:
    item = session.get(CultivationItem, item_id)
    if item is None:
        raise NotFound("Item not found")
    for field in ("title", "item_type", "notes"):
        if field in payload and payload[field] is not None:
            setattr(item, field, str(payload[field])[:4000 if field == "notes" else 300])
    if "tags" in payload and payload["tags"] is not None:
        item.tags = list(payload["tags"])[:50]
    if "provenance" in payload and payload["provenance"] is not None:
        item.provenance = _validate_provenance(payload["provenance"])
    for field in ("source_application", "source_project_id", "source_ref"):
        if field in payload:
            setattr(item, field, payload[field])
    if item.source_project_id and session.get(Project, item.source_project_id) is None:
        raise ValidationProblem("Linked project does not exist")
    item.updated_at = now_iso()
    session.flush()
    return item


def add_membership(session: Session, item_id: str, goal_id: str, *, stage: str = "idea") -> CultivationMembership:
    item = session.get(CultivationItem, item_id)
    if item is None:
        raise NotFound("Item not found")
    goal = get_goal(session, goal_id)
    if stage not in _stage_ids(session):
        raise ValidationProblem(f"Unknown stage: {stage}")
    if session.get(CultivationMembership, (item_id, goal_id)) is not None:
        raise Conflict("Item is already tracked in this goal")
    membership = CultivationMembership(
        item_id=item_id, goal_id=goal_id, stage=stage, created_at=now_iso(), updated_at=now_iso())
    if stage == goal.qualifying_stage:
        membership.completed_at = now_iso()
    session.add(membership)
    session.flush()
    _record_event(session, goal_id=goal_id, item_id=item_id, event_type="item_added",
                  to_value=stage, note=f"'{item.title}' added to '{goal.name}' at stage '{stage}'.")
    if stage == goal.qualifying_stage:
        _record_event(session, goal_id=goal_id, item_id=item_id, event_type="completed",
                      to_value=stage, note=f"'{item.title}' counts toward '{goal.name}'.")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    return membership


def set_stage(session: Session, item_id: str, goal_id: str, *, stage: str,
              note: str = "", evidence_ref: str | None = None,
              completed_at: str | None = None) -> CultivationMembership:
    membership = session.get(CultivationMembership, (item_id, goal_id))
    if membership is None:
        raise NotFound("Item is not tracked in this goal")
    if stage not in _stage_ids(session):
        raise ValidationProblem(f"Unknown stage: {stage}")
    goal = get_goal(session, goal_id)
    previous = membership.stage
    if previous == stage and completed_at is None:
        return membership
    membership.stage = stage
    membership.updated_at = now_iso()
    _record_event(session, goal_id=goal_id, item_id=item_id, event_type="stage_changed",
                  from_value=previous, to_value=stage, note=note, evidence_ref=evidence_ref)
    was_complete = previous == goal.qualifying_stage
    now_complete = stage == goal.qualifying_stage
    if now_complete and not was_complete:
        membership.completed_at = completed_at or now_iso()
        _record_event(session, goal_id=goal_id, item_id=item_id, event_type="completed",
                      to_value=stage, note=note or "Reached the qualifying stage.", evidence_ref=evidence_ref)
    elif now_complete and completed_at:
        membership.completed_at = completed_at
        _record_event(session, goal_id=goal_id, item_id=item_id, event_type="correction",
                      to_value=stage, note=note or "Completion date corrected.")
    elif was_complete and not now_complete:
        membership.completed_at = None
        membership.qualified = False
        membership.qualified_at = None
        _record_event(session, goal_id=goal_id, item_id=item_id, event_type="reopened",
                      from_value=previous, to_value=stage,
                      note=note or "Moved back out of the qualifying stage; no longer counted.")
    session.flush()
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    return membership


def set_qualified(session: Session, item_id: str, goal_id: str, *, qualified: bool,
                  quality_evidence: dict[str, Any] | None = None, note: str = "") -> CultivationMembership:
    membership = session.get(CultivationMembership, (item_id, goal_id))
    if membership is None:
        raise NotFound("Item is not tracked in this goal")
    goal = get_goal(session, goal_id)
    membership.qualified = qualified
    membership.qualified_at = now_iso() if qualified else None
    if quality_evidence:
        membership.quality_evidence = dict(quality_evidence)
    membership.updated_at = now_iso()
    session.flush()
    _record_event(session, goal_id=goal_id, item_id=item_id, event_type="qualified" if qualified else "unqualified",
                  note=note or f"Quality qualification {'recorded' if qualified else 'removed'}.")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    return membership


# ------------------------------------------------------------ measurements
def record_measurement(session: Session, goal_id: str, *, value: float,
                       observed_at: str | None = None, note: str = "",
                       source: str = "manual") -> CultivationMeasurement:
    goal = get_goal(session, goal_id)
    try:
        observed = observed_at or now_iso()
        datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationProblem("observed_at must be an ISO-8601 timestamp") from None
    measurement = CultivationMeasurement(
        id=_new_id("msr"), goal_id=goal_id, value=float(value), observed_at=observed,
        note=str(note)[:2000], source=str(source)[:60], created_at=now_iso())
    session.add(measurement)
    session.flush()
    _record_event(session, goal_id=goal_id, event_type="measurement",
                  to_value=str(float(value)), note=note or f"Recorded {float(value):g} {goal.unit}.")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    return measurement


# -------------------------------------------------------------- evidence
def add_evidence(session: Session, goal_id: str | None, *, item_id: str | None = None,
                 kind: str = "reference", reference: str = "",
                 note: str = "", verified: bool = False) -> CultivationEvidence:
    if goal_id is None and item_id is None:
        raise ValidationProblem("Evidence needs a goal or an item")
    if goal_id is not None and session.get(CultivationGoal, goal_id) is None:
        raise NotFound("Goal not found")
    if item_id is not None and session.get(CultivationItem, item_id) is None:
        raise NotFound("Item not found")
    evidence = CultivationEvidence(
        id=_new_id("gevd"), goal_id=goal_id, item_id=item_id, kind=str(kind)[:60],
        reference=str(reference)[:2000], note=str(note)[:4000],
        verified=bool(verified), created_at=now_iso())
    session.add(evidence)
    session.flush()
    if item_id and goal_id:
        membership = session.get(CultivationMembership, (item_id, goal_id))
        if membership is not None:
            if verified:
                membership.evidence_status = "verified"
            elif membership.evidence_status == "none":
                membership.evidence_status = "claimed"
            membership.updated_at = now_iso()
    return evidence


# ------------------------------------------------------------------ reads
def goal_read(session: Session, goal: CultivationGoal) -> dict[str, Any]:
    return {
        "id": goal.id, "name": goal.name, "description": goal.description,
        "category": goal.category, "unit": goal.unit, "target_value": goal.target_value,
        "measurement_type": goal.measurement_type, "baseline_value": goal.baseline_value,
        "baseline_note": goal.baseline_note, "baseline_provenance": goal.baseline_provenance,
        "qualifying_stage": goal.qualifying_stage, "window_days": goal.window_days,
        "priority": goal.priority, "state": goal.state, "pinned": bool(goal.pinned),
        "pin_order": goal.pin_order, "privacy": goal.privacy,
        "completion_criteria": goal.completion_criteria, "milestones": list(goal.milestones or []),
        "dependencies": list(goal.dependencies or []), "evidence_source": goal.evidence_source,
        "created_at": goal.created_at, "updated_at": goal.updated_at,
        "progress": goal_progress(session, goal),
    }


def item_read(session: Session, item: CultivationItem) -> dict[str, Any]:
    memberships = []
    for membership in session.scalars(select(CultivationMembership).where(
            CultivationMembership.item_id == item.id)).all():
        goal = session.get(CultivationGoal, membership.goal_id)
        memberships.append({
            "item_id": membership.item_id, "goal_id": membership.goal_id,
            "goal_name": goal.name if goal else None, "stage": membership.stage,
            "evidence_status": membership.evidence_status,
            "quality_evidence": dict(membership.quality_evidence or {}),
            "qualified": bool(membership.qualified), "qualified_at": membership.qualified_at,
            "completed_at": membership.completed_at, "created_at": membership.created_at,
            "updated_at": membership.updated_at,
        })
    project_name = None
    if item.source_project_id:
        project = session.get(Project, item.source_project_id)
        if project is None:
            project_name = None
        else:
            project_name = project.name
            book = session.scalar(select(Book).where(Book.project_id == project.id))
            if book is not None:
                project_name = f"{project.name} / {book.title}"
    return {
        "id": item.id, "title": item.title, "item_type": item.item_type, "notes": item.notes,
        "tags": list(item.tags or []), "provenance": item.provenance,
        "source_application": item.source_application, "source_project_id": item.source_project_id,
        "source_project_name": project_name, "source_ref": item.source_ref,
        "created_at": item.created_at, "updated_at": item.updated_at, "memberships": memberships,
    }


def list_events(session: Session, *, goal_id: str | None = None, item_id: str | None = None,
                limit: int = 100) -> list[CultivationEvent]:
    query = select(CultivationEvent).order_by(desc(CultivationEvent.created_at))
    if goal_id:
        query = query.where(CultivationEvent.goal_id == goal_id)
    if item_id:
        query = query.where(CultivationEvent.item_id == item_id)
    return list(session.scalars(query.limit(min(max(limit, 1), 500))).all())


def event_read(session: Session, event: CultivationEvent) -> dict[str, Any]:
    title = None
    if event.item_id:
        item = session.get(CultivationItem, event.item_id)
        title = item.title if item else None
    return {
        "id": event.id, "goal_id": event.goal_id, "item_id": event.item_id,
        "item_title": title, "event_type": event.event_type,
        "from_value": event.from_value, "to_value": event.to_value, "note": event.note,
        "evidence_ref": event.evidence_ref, "occurred_at": event.occurred_at,
        "created_at": event.created_at,
    }


def hud_summary(session: Session) -> dict[str, Any]:
    pinned = [goal for goal in session.scalars(select(CultivationGoal).where(
        CultivationGoal.pinned.is_(True), CultivationGoal.state != "archived").order_by(
        CultivationGoal.pin_order, CultivationGoal.name)).all()]
    active_pinned = [goal for goal in pinned if goal.state == "active"]
    primary = active_pinned[0] if active_pinned else (pinned[0] if pinned else None)

    def _hud_goal(goal: CultivationGoal) -> dict[str, Any]:
        return {"id": goal.id, "name": goal.name, "unit": goal.unit, "state": goal.state,
                "privacy": goal.privacy, "progress": goal_progress(session, goal)}

    recent = session.scalars(select(CultivationEvent).where(
        CultivationEvent.event_type == "completed").order_by(
        desc(CultivationEvent.created_at)).limit(10)).all()
    ranks = rank_status(session)
    return {
        "primary": _hud_goal(primary) if primary else None,
        "pinned": [_hud_goal(goal) for goal in pinned],
        "rank": ranks["current"],
        "recent_completions": [event_read(session, event) for event in recent],
        "generated_at": now_iso(),
    }
