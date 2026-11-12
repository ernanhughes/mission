"""Cultivation goals, items, milestones and ranks (MC-CULTIVATION-01).

The unit of progress is a meaningful completed artefact or measurement, never
an invented score. Counts recompute from stored rows; user estimates are
labelled with their provenance and never silently converted into evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.models import (
    Application,
    Book,
    CultivationApplication,
    CultivationAppRepo,
    CultivationCycle,
    CultivationCycleGoal,
    CultivationEvent,
    CultivationEvidence,
    CultivationGitHubRepo,
    CultivationGoal,
    CultivationItem,
    CultivationMeasurement,
    CultivationMembership,
    CultivationRepoState,
    CultivationSkill,
    CultivationSource,
    DiscoveryRoot,
    GitCommit,
    GitRepository,
    Project,
    ProjectRepository,
    Repository,
    Setting,
)
from mission_control.persistence.db import now_iso

MEASUREMENT_TYPES = {"count", "threshold_up", "threshold_down", "recurring", "qualified_count"}
RECURRING_MODES = {"daily", "period"}
GOAL_STATES = {"active", "paused", "achieved", "archived"}
PRIVACY_LEVELS = {"standard", "private"}
PROVENANCE_VALUES = {"human", "ai_assisted", "ai_workflow", "unclassified"}
BASELINE_PROVENANCE = {"none", "estimate", "user_assertion", "verified"}
EVIDENCE_STATUS = {"none", "claimed", "verified"}
SKILL_STATES = {"active", "archived"}
SOURCE_KINDS = {"hugo_blog", "activity_projects", "numbered_files", "script_registry", "github_repos"}
CYCLE_STATES = {"active", "completed", "archived"}
REPO_QUALIFICATIONS = {"discovered", "eligible", "pending", "qualified", "excluded", "archived", "unavailable"}
REPO_CLASSIFICATIONS = {"application", "library", "infrastructure", "research", "website",
                        "book", "experiment", "other", "unclassified", "dataset", "tutorial"}
LIFECYCLE_STAGES = {"idea", "planned", "in_development", "functional", "testing",
                    "released", "maintained", "archived",
                    "unreviewed", "concept", "prototype", "development",
                    "working", "completed", "published", "abandoned"}
RELEASE_EVIDENCE_KINDS = {"versioned_release", "deployment", "published", "completion_decision",
                          "owner_confirmed", "project_record"}
DUBLIN_TZ = "Europe/Dublin"

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
    if "recurring_mode" in payload or not partial:
        recurring_mode = str(payload.get("recurring_mode", "daily") or "daily")
        if recurring_mode not in RECURRING_MODES:
            raise ValidationProblem(f"Unknown recurring_mode: {recurring_mode}")
        cleaned["recurring_mode"] = recurring_mode
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
    live = _live_observation(session, goal)
    if live is not None:
        return live
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
        mode = (goal.recurring_mode or "daily").strip().lower() or "daily"
        if mode == "period":
            # Total output inside the window versus the target (e.g. at least
            # one new post per 7-day window). Each measurement counts once.
            # The window is anchored to the Europe/Dublin calendar date so
            # weekly discipline survives DST transitions.
            from zoneinfo import ZoneInfo as _ZoneInfo

            try:
                _dublin = _ZoneInfo(DUBLIN_TZ)
            except Exception:
                _dublin = timezone.utc
            _today = datetime.now(_dublin).date()
            from datetime import timedelta as _td

            cutoff = (_today - _td(days=window - 1)).isoformat()
            total = sum(float(row.value) for row in rows if (row.observed_at or "")[:10] >= cutoff)
            return {"current": total, "target": goal.target_value, "unit": goal.unit,
                    "percent": min(100.0, total / goal.target_value * 100.0) if goal.target_value > 0 else None,
                    "unknown_reason": None, "achieved": total >= goal.target_value,
                    "estimate_label": None, "item_count": 0, "pipeline": pipeline,
                    "milestones_reached": [], "next_milestone": None}
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
               privacy: str | None = None, skill_id: str | None = None) -> list[CultivationGoal]:
    query = select(CultivationGoal).order_by(CultivationGoal.priority, CultivationGoal.name)
    if not include_archived:
        query = query.where(CultivationGoal.state != "archived")
    if privacy in PRIVACY_LEVELS:
        query = query.where(CultivationGoal.privacy == privacy)
    if skill_id:
        query = query.where(CultivationGoal.skill_id == skill_id)
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
    skill_id = payload.get("skill_id")
    if skill_id is not None:
        if session.get(CultivationSkill, skill_id) is None:
            raise NotFound("Skill not found")
        goal.skill_id = skill_id
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
    if "skill_id" in payload:
        skill_id = payload["skill_id"]
        if skill_id is not None:
            if session.get(CultivationSkill, skill_id) is None:
                raise NotFound("Skill not found")
        if goal.skill_id != skill_id:
            changes.append("skill_id")
            goal.skill_id = skill_id
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
              completed_at: str | None = None, by_sync: bool = False) -> CultivationMembership:
    membership = session.get(CultivationMembership, (item_id, goal_id))
    if membership is None:
        raise NotFound("Item is not tracked in this goal")
    if stage not in _stage_ids(session):
        raise ValidationProblem(f"Unknown stage: {stage}")
    goal = get_goal(session, goal_id)
    previous = membership.stage
    managed = isinstance(membership.quality_evidence, dict) and bool(membership.quality_evidence.get("managed_by"))
    if previous == stage and completed_at is None:
        session.flush()
        return membership
    if not by_sync and managed:
        # An explicit human move of a source-managed item holds: the next
        # sync will not silently overwrite it.
        membership.quality_evidence = {**membership.quality_evidence, "manual_hold": True}
        note = (note + " " if note else "") + "(Manual hold: source sync will no longer move this item.)"
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
    if qualified:
        # Human-recorded qualification survives source reconciliation.
        membership.quality_evidence = {**dict(membership.quality_evidence or {}), "qualified_by": "user"}
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
def _live_observation(session: Session, goal: CultivationGoal) -> dict[str, Any] | None:
    """Observed counts from an attached live source.

    The observation never rewrites the user-attested baseline: when the two
    disagree the milestone stays achieved (explicit state) while the progress
    honestly reports the observed value with a reconciliation note.
    """
    if goal.evidence_source not in ("hugo_blog", "numbered_files", "script_registry"):
        return None
    source = session.scalars(select(CultivationSource).where(
        CultivationSource.goal_id == goal.id, CultivationSource.kind == goal.evidence_source,
        CultivationSource.last_sync_at.is_not(None)).order_by(
        desc(CultivationSource.last_sync_at)).limit(1)).first()
    if source is None or not isinstance(source.observed, dict):
        return None
    observed = source.observed
    current = float(observed.get("published", 0))
    milestones = sorted(set(float(value) for value in (goal.milestones or [])))
    reached = [value for value in milestones if current >= value]
    upcoming = [value for value in milestones if value > current]
    stale = source.last_status == "stale"
    label = f"{current:g} / {goal.target_value:g} {goal.unit} observed {(source.last_sync_at or '')[:10]}"
    if stale:
        label += " (stale — source unavailable, last known kept)"
    if goal.evidence_source == "script_registry" and isinstance(observed.get("discovered"), int):
        label += f" · {int(observed['discovered'])} discovered"
    disagreement = None
    if goal.baseline_value is not None:
        label += f" · user-attested milestone {goal.baseline_value:g} preserved"
    if goal.baseline_value is not None and current < goal.baseline_value:
        kind = "estimate" if goal.baseline_provenance == "estimate" else "user-attested prior achievements"
        disagreement = (f"Source observes {current:g} but {goal.baseline_value:g} {kind} are recorded. "
                        "Milestone history is preserved; reconciliation required.")
    pipeline: dict[str, int] = {"published": int(observed.get("published", 0)),
                       "draft": int(observed.get("drafts", 0)),
                       "unknown": int(observed.get("unknown", 0))}
    if isinstance(observed.get("scheduled"), int):
        pipeline["scheduled"] = int(observed["scheduled"])
    if isinstance(observed.get("tech_published"), int):
        pipeline["technology"] = int(observed["tech_published"])
    if isinstance(observed.get("finance_published"), int):
        pipeline["finance"] = int(observed["finance_published"])
    if goal.evidence_source == "script_registry":
        for key in ("discovered", "completed", "ready", "needs_review", "archived", "missing"):
            if isinstance(observed.get(key), int):
                pipeline[key] = int(observed[key])
    return {"current": current, "target": goal.target_value, "unit": goal.unit,
            "percent": min(100.0, current / goal.target_value * 100.0) if goal.target_value > 0 else None,
            "unknown_reason": None, "achieved": current >= goal.target_value,
            "estimate_label": label, "item_count": int(observed.get("published", 0)),
            "pipeline": pipeline,
            "milestones_reached": reached, "next_milestone": upcoming[0] if upcoming else None,
            "live_observed": current, "live_sync_at": source.last_sync_at, "live_stale": stale,
            "disagreement": disagreement}


def goal_read(session: Session, goal: CultivationGoal) -> dict[str, Any]:
    skill_name = None
    if goal.skill_id:
        skill = session.get(CultivationSkill, goal.skill_id)
        skill_name = skill.name if skill else None
    return {
        "id": goal.id, "name": goal.name, "description": goal.description,
        "category": goal.category, "unit": goal.unit, "target_value": goal.target_value,
        "measurement_type": goal.measurement_type, "baseline_value": goal.baseline_value,
        "baseline_note": goal.baseline_note, "baseline_provenance": goal.baseline_provenance,
        "qualifying_stage": goal.qualifying_stage, "window_days": goal.window_days,
        "recurring_mode": goal.recurring_mode or "daily",
        "priority": goal.priority, "state": goal.state, "pinned": bool(goal.pinned),
        "pin_order": goal.pin_order, "privacy": goal.privacy,
        "completion_criteria": goal.completion_criteria, "milestones": list(goal.milestones or []),
        "dependencies": list(goal.dependencies or []), "evidence_source": goal.evidence_source,
        "skill_id": goal.skill_id, "skill_name": skill_name,
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


def active_cycle(session: Session) -> CultivationCycle | None:
    return session.scalars(select(CultivationCycle).where(
        CultivationCycle.state == "active").order_by(desc(CultivationCycle.number)).limit(1)).first()


# ------------------------------------------------- projects adapter (03)
#
# R1 B1/B2 qualification gate (read before extending): B1 affects review
# redaction labels; B2 affects short-SHA commit resolution. Neither touches
# repository identity, discovery, or indexed commit metadata. This adapter
# therefore uses ONLY the verified subset — git_repositories rows,
# git_commits aggregates addressed by full SHA, discovery_roots config —
# and never calls file_diff, build_prompt, or short-SHA prefix resolution.

REPO_ITEM_PREFIX = "repo-"
APP_ITEM_PREFIX = "app-"


def _repo_item_id(repo_uid: str) -> str:
    return REPO_ITEM_PREFIX + repo_uid


def _app_item_id(app_id: str) -> str:
    return APP_ITEM_PREFIX + app_id


def _scope_roots(session: Session, source) -> list[str]:
    config = source.config if isinstance(source.config, dict) else {}
    included = config.get("included_roots")
    if included:
        return [str(path) for path in included]
    rows = session.scalars(select(DiscoveryRoot).where(DiscoveryRoot.enabled.is_(True))).all()
    return [row.path for row in rows if (row.category or "software") == "software"]


def _root_category(session: Session, root_path: str) -> str:
    root = session.get(DiscoveryRoot, root_path)
    return (root.category if root and root.category else "software")


def _project_map(session: Session) -> dict[str, list[str]]:
    """Repository path (normcase) -> project ids, via ProjectRepository links."""
    import os as _os

    rows = session.execute(select(Repository.path, ProjectRepository.project_id).join(
        ProjectRepository, ProjectRepository.repository_id == Repository.id)).all()
    mapping: dict[str, list[str]] = {}
    for path, project_id in rows:
        mapping.setdefault(_os.path.normcase(path), []).append(project_id)
    return mapping


def _commit_aggregates(session: Session) -> dict[str, dict[str, int]]:
    rows = session.execute(select(GitCommit.repo_id, func.count(GitCommit.sha),
                                 func.min(GitCommit.committer_ts),
                                 func.max(GitCommit.committer_ts)).group_by(GitCommit.repo_id)).all()
    return {repo_id: {"count": int(count), "first_ts": int(first or 0), "last_ts": int(last or 0)}
            for repo_id, count, first, last in rows}


def _auto_qualification(accessible: bool, commit_count: int, config: dict[str, Any]) -> tuple[str, str]:
    """Conservative default: nothing is ever auto-qualified. Owner confirms."""
    if not accessible:
        return "discovered", "Repository is currently inaccessible; kept as discovered, not counted."
    min_commits = int(config.get("min_commits", 2))
    if commit_count < min_commits:
        return "pending", (f"Only {commit_count} commit(s) indexed (minimum {min_commits}); "
                           "needs owner review before it can count.")
    return "eligible", (f"{commit_count} commits indexed; eligible but requires "
                        "explicit owner confirmation to count.")


def _first_configured_stage(session: Session) -> str:
    stages = get_config(session)["stages"]
    return str(stages[0]["id"]) if stages else "idea"


def _resolve_git_row(session: Session, state: CultivationRepoState):
    """Authoritative row by id, falling back to any row sharing the stable
    uid (handles moves where Activity issued a new row id)."""
    repo = session.get(GitRepository, state.repo_id)
    if repo is None and state.repo_uid:
        repo = session.scalars(select(GitRepository).where(
            GitRepository.repo_uid == state.repo_uid).limit(1)).first()
    return repo


def sync_activity_projects(session: Session, source_id: str) -> dict[str, Any]:
    """Read-only sync from Activity's index. Never writes git tables, never
    spawns git, never touches the filesystem beyond configured roots (and then
    only reads already-indexed rows — no traversal here at all)."""
    import hashlib as _hashlib
    import os as _os

    source = get_source(session, source_id)
    if source.kind != "activity_projects":
        raise ValidationProblem("Only activity_projects sources sync this way")
    config = source.config if isinstance(source.config, dict) else {}
    roots = _scope_roots(session, source)

    def _in_scope(repo_path: str) -> str | None:
        from mission_control.core.paths import is_within, normalize_absolute_path
        try:
            candidate = normalize_absolute_path(repo_path, field="repository path")
        except ValidationProblem:
            return None
        for root in roots:
            try:
                if _os.path.normcase(candidate) == _os.path.normcase(root) or is_within(Path(candidate), Path(root)):
                    return root
            except OSError:
                continue
        return None

    git_rows = session.scalars(select(GitRepository)).all()
    project_map = _project_map(session)
    aggregates = _commit_aggregates(session)

    uid_groups: dict[str, list] = {}
    for row in git_rows:
        root = _in_scope(row.path)
        if root is None:
            continue
        uid_groups.setdefault(row.repo_uid or f"noid:{row.id}", []).append((root, row))

    digest = _hashlib.sha256()
    for uid in sorted(uid_groups):
        rows = sorted(uid_groups[uid], key=lambda pair: pair[1].path)
        _root, primary = rows[0]
        agg = aggregates.get(primary.id, {"count": 0, "first_ts": 0, "last_ts": 0})
        digest.update(uid.encode("utf-8"))
        digest.update(str(primary.head_sha or "").encode("utf-8"))
        digest.update(str(agg["count"]).encode("utf-8"))
    fingerprint = digest.hexdigest()[:24]

    seen_repo_ids: set[str] = set()
    new_items = 0
    for uid in sorted(uid_groups):
        rows = sorted(uid_groups[uid], key=lambda pair: pair[1].path)
        root, primary = rows[0]
        seen_repo_ids.add(primary.id)
        agg = aggregates.get(primary.id, {"count": 0, "first_ts": 0, "last_ts": 0})
        from datetime import datetime as _dt, timezone as _tz
        first_iso = (_dt.fromtimestamp(agg["first_ts"], tz=_tz.utc).isoformat()
                     if agg["first_ts"] else None)

        item_id = _repo_item_id(uid)
        item = session.get(CultivationItem, item_id)
        if item is None:
            item = CultivationItem(
                id=item_id, title=primary.name or Path(primary.path).name, item_type="repository",
                notes=f"Observed by source '{source.name}'.", provenance="unclassified",
                source_application="activity_projects", source_ref=f"{source.id}:{primary.path}",
                created_at=now_iso(), updated_at=now_iso())
            session.add(item)
            session.flush()
            new_items += 1
        else:
            if primary.name and item.title != primary.name:
                old_title = item.title
                item.title = primary.name
                _record_event(session, goal_id=None, item_id=item_id, event_type="renamed",
                              from_value=old_title, to_value=primary.name,
                              note="Repository renamed or moved; stable identity kept, no new achievement.")
            item.source_ref = f"{source.id}:{primary.path}"
            item.updated_at = now_iso()

        state = session.get(CultivationRepoState, primary.id)
        if state is None:
            # Same uid under a new Activity row id (root removed without
            # history, then rediscovered): migrate the judgement across.
            migrated = session.scalars(select(CultivationRepoState).where(
                CultivationRepoState.repo_uid == uid).limit(1)).first()
            if migrated is not None and migrated.repo_id != primary.id:
                session.delete(migrated)
                session.flush()
                _record_event(session, goal_id=None, item_id=item_id, event_type="reidentified",
                              from_value=migrated.repo_id, to_value=primary.id,
                              note="Activity row identity changed; owner judgement carried across.")
            category = _root_category(session, root)
            state = CultivationRepoState(
                repo_id=primary.id, repo_uid=uid,
                classification="book" if category == "books" else "unclassified",
                accessible=bool(primary.accessible), last_seen_at=now_iso(),
                last_head=primary.head_sha, last_commit_count=agg["count"],
                created_at=now_iso(), updated_at=now_iso())
            session.add(state)
            session.flush()
        prev_head, prev_count = state.last_head, state.last_commit_count
        state.accessible = bool(primary.accessible)
        state.last_seen_at = now_iso()
        state.last_head = primary.head_sha
        state.last_commit_count = agg["count"]
        state.updated_at = now_iso()

        if state.decided_by == "undecided":
            qualification, rationale = _auto_qualification(bool(primary.accessible), agg["count"], config)
            if state.qualification != qualification or not state.rationale:
                state.qualification = qualification
                state.rationale = rationale
                state.updated_at = now_iso()
            projects = sorted({pid for _, row in rows for pid in project_map.get(_os.path.normcase(row.path), [])})
            if projects:
                evidence = dict(state.evidence or {})
                evidence["project_ids"] = projects
                state.evidence = evidence
        else:
            # Archived work receiving new commits is an observation, never an
            # automatic state change.
            if (state.lifecycle_stage == "archived" or state.qualification == "archived") and (
                    prev_head != primary.head_sha or prev_count != agg["count"]):
                _record_event(session, goal_id=None, item_id=item_id, event_type="activity_observed",
                              note=(f"New commits observed on an archived repository "
                                    f"({prev_count} -> {agg['count']}); state unchanged by design."))
        # First-evidence timestamp for honest cycle attribution (scan time is
        # NOT the creation date).
        for membership in session.scalars(select(CultivationMembership).where(
                CultivationMembership.item_id == item_id)).all():
            evidence = dict(membership.quality_evidence or {})
            if first_iso and evidence.get("first_evidence_ts") != first_iso:
                evidence["first_evidence_ts"] = first_iso
                membership.quality_evidence = evidence
                membership.updated_at = now_iso()

    # Repositories that vanished from the Activity index keep their history.
    for state in session.scalars(select(CultivationRepoState)).all():
        if state.repo_id in seen_repo_ids:
            continue
        # Still present under another Activity row id (uid match after a move)?
        moved = session.scalars(select(GitRepository).where(
            GitRepository.repo_uid == state.repo_uid).limit(1)).first()
        if moved is not None:
            continue
        if state.accessible:
            state.accessible = False
            state.updated_at = now_iso()
            item_id = _repo_item_id(state.repo_uid or state.repo_id)
            _record_event(session, goal_id=None, item_id=item_id if session.get(CultivationItem, item_id) else None,
                          event_type="source_removed",
                          note=(f"Repository no longer in the Activity index ({state.repo_id}); "
                                "qualifications and history preserved, counted state unchanged."))

    by_qualification: dict[str, int] = {}
    by_lifecycle: dict[str, int] = {}
    projects_linked = 0
    for state in session.scalars(select(CultivationRepoState)).all():
        by_qualification[state.qualification] = by_qualification.get(state.qualification, 0) + 1
        if state.lifecycle_stage:
            by_lifecycle[state.lifecycle_stage] = by_lifecycle.get(state.lifecycle_stage, 0) + 1
        if isinstance(state.evidence, dict) and state.evidence.get("project_ids"):
            projects_linked += 1
    observed = {"repos_total": len(seen_repo_ids), "by_qualification": by_qualification,
                "by_lifecycle": by_lifecycle, "projects_linked": projects_linked,
                "roots": roots, "fingerprint": fingerprint,
                "note": "Owner confirmation required before anything counts."}
    changed = fingerprint != (source.fingerprint or "")
    source.observed = observed
    source.fingerprint = fingerprint
    source.last_sync_at = now_iso()
    source.last_status = "ok"
    source.last_error = None
    source.updated_at = now_iso()
    session.flush()
    if changed and source.goal_id and session.get(CultivationGoal, source.goal_id):
        _record_event(session, goal_id=source.goal_id, event_type="synced",
                      to_value=str(len(seen_repo_ids)),
                      note=(f"Source '{source.name}': {len(seen_repo_ids)} repositories observed "
                            f"({by_qualification})."))
    return {"source_id": source.id, "status": "ok", "observed": observed,
            "stale": False, "goal_id": source.goal_id, "new_items": new_items,
            "fingerprint_changed": changed}


# ------------------------------------------------- GitHub inventory (04)
#
# Read-only GitHub synchronisation. GitHub owns remote facts (cached in
# cultivation_github_repos); Mission Control owns classifications, lifecycle
# assessments, annotations and goals. A failed sync never deletes cached
# rows: the source row records the failure and the last observation is kept.

def _github_local_matches(session: Session, repo_name: str) -> list[dict[str, str]]:
    """Match a GitHub repo name against local workspaces (advisory only)."""
    import os as _os

    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    lowered = repo_name.lower()
    for repo in session.scalars(select(Repository)).all():
        if _os.path.basename(repo.path or "").lower() == lowered and repo.path not in seen:
            seen.add(repo.path)
            matches.append({"kind": "repository", "path": repo.path})
    for git_repo in session.scalars(select(GitRepository)).all():
        if _os.path.basename(git_repo.path or "").lower() == lowered and git_repo.path not in seen:
            seen.add(git_repo.path)
            matches.append({"kind": "activity_index", "path": git_repo.path})
    for app in session.scalars(select(Application)).all():
        candidate = app.repository_path or ""
        if candidate and _os.path.basename(candidate).lower() == lowered and candidate not in seen:
            seen.add(candidate)
            matches.append({"kind": "application", "path": candidate})
    return matches[:5]


def _github_evidence(repo: dict[str, Any],
                     matches: list[dict[str, str]]) -> dict[str, Any]:
    return {"github": {
        "node_id": repo.get("node_id"), "full_name": repo.get("full_name"),
        "url": repo.get("url"), "description": repo.get("description"),
        "visibility": repo.get("visibility"), "private": bool(repo.get("is_private")),
        "fork": bool(repo.get("is_fork")), "archived": bool(repo.get("is_archived")),
        "language": repo.get("language"), "languages": list(repo.get("languages") or []),
        "topics": list(repo.get("topics") or []),
        "default_branch": repo.get("default_branch"),
        "pushed_at": repo.get("pushed_at"), "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at")},
        "local_matches": matches}


def sync_github_repos(session: Session, source_id: str,
                       fetcher: Any | None = None) -> dict[str, Any]:
    """Sync the GitHub inventory snapshot (read-only toward GitHub).

    ``fetcher`` is an injectable zero-argument callable returning normalized
    repository dicts (see ``cultivation.github.normalize_repo``); tests pass a
    fake, production resolves one from the source config.
    """
    from mission_control.cultivation import github as _github

    source = get_source(session, source_id)
    if source.kind != "github_repos":
        raise ValidationProblem("Only github_repos sources sync this way")
    if fetcher is None:
        config = source.config if isinstance(source.config, dict) else {}
        fetcher = _github.resolve_fetcher(config)
    try:
        repos = fetcher()
    except _github.GitHubError as exc:
        source.last_status = exc.status
        source.last_error = str(exc)[:2000]
        source.updated_at = now_iso()
        session.flush()
        return {"source_id": source.id, "status": exc.status,
                "observed": dict(source.observed or {}), "stale": True,
                "error": source.last_error, "goal_id": source.goal_id}
    if not isinstance(repos, list):
        raise ValidationProblem("GitHub fetcher must return a list of repositories")

    valid = [repo for repo in repos
             if isinstance(repo, dict) and str(repo.get("node_id") or "").strip()]
    seen: set[str] = set()
    new_items = 0
    for repo in valid:
        node_id = str(repo.get("node_id"))
        seen.add(node_id)
        row = session.get(CultivationGitHubRepo, node_id)
        if row is None:
            row = CultivationGitHubRepo(
                node_id=node_id, numeric_id=repo.get("numeric_id"),
                owner=str(repo.get("owner") or ""), name=str(repo.get("name") or ""),
                full_name=str(repo.get("full_name") or ""),
                url=str(repo.get("url") or ""),
                description=str(repo.get("description") or ""),
                visibility=str(repo.get("visibility") or "PUBLIC").upper(),
                is_private=bool(repo.get("is_private")),
                is_fork=bool(repo.get("is_fork")),
                is_archived=bool(repo.get("is_archived")),
                language=repo.get("language"),
                languages=list(repo.get("languages") or []),
                topics=list(repo.get("topics") or []),
                default_branch=repo.get("default_branch"),
                pushed_at=repo.get("pushed_at"),
                created_at_github=repo.get("created_at"),
                updated_at_github=repo.get("updated_at"),
                missing=False, observed_at=now_iso(), updated_at=now_iso())
            session.add(row)
            session.flush()
        else:
            row.numeric_id = repo.get("numeric_id")
            row.owner = str(repo.get("owner") or "")
            row.name = str(repo.get("name") or "")
            row.full_name = str(repo.get("full_name") or "")
            row.url = str(repo.get("url") or "")
            row.description = str(repo.get("description") or "")
            row.visibility = str(repo.get("visibility") or "PUBLIC").upper()
            row.is_private = bool(repo.get("is_private"))
            row.is_fork = bool(repo.get("is_fork"))
            row.is_archived = bool(repo.get("is_archived"))
            row.language = repo.get("language")
            row.languages = list(repo.get("languages") or [])
            row.topics = list(repo.get("topics") or [])
            row.default_branch = repo.get("default_branch")
            row.pushed_at = repo.get("pushed_at")
            row.created_at_github = repo.get("created_at")
            row.updated_at_github = repo.get("updated_at")
            row.missing = False
            row.observed_at = now_iso()
            row.updated_at = now_iso()

        from mission_control.cultivation import github as _gh_mod

        uid = _gh_mod.gh_repo_uid(node_id)
        state_id = _gh_mod.gh_repo_id(node_id)
        item_id = _repo_item_id(uid)
        item = session.get(CultivationItem, item_id)
        title = str(repo.get("name") or repo.get("full_name") or node_id)
        if item is None:
            item = CultivationItem(
                id=item_id, title=title[:300], item_type="repository",
                notes=f"Observed by GitHub source '{source.name}'.",
                provenance="unclassified", source_application="github_repos",
                source_ref=f"{source.id}:{repo.get('full_name')}",
                created_at=now_iso(), updated_at=now_iso())
            session.add(item)
            session.flush()
            new_items += 1
        else:
            if title and item.title != title:
                old_title = item.title
                item.title = title[:300]
                _record_event(session, goal_id=None, item_id=item_id, event_type="renamed",
                              from_value=old_title, to_value=item.title,
                              note="GitHub repository renamed; stable identity kept, no new achievement.")
            item.source_ref = f"{source.id}:{repo.get('full_name')}"
            item.updated_at = now_iso()

        matches = _github_local_matches(session, str(repo.get("name") or ""))
        classification, rationale = _github.infer_classification(repo)
        lifecycle, lifecycle_note = _github.infer_lifecycle(repo)
        state = session.get(CultivationRepoState, state_id)
        if state is None:
            if repo.get("is_archived"):
                qualification = "archived"
                qualification_note = "GitHub marks this repository archived; observed, never counted."
            else:
                qualification = "discovered"
                qualification_note = rationale
            state = CultivationRepoState(
                repo_id=state_id, repo_uid=uid,
                qualification=qualification,
                lifecycle_stage=lifecycle,
                classification=classification,
                rationale=rationale if not repo.get("is_archived") else qualification_note,
                evidence=_github_evidence(repo, matches),
                decided_by="undecided",
                accessible=True, last_seen_at=now_iso(),
                last_head=None, last_commit_count=0,
                created_at=now_iso(), updated_at=now_iso())
            session.add(state)
            session.flush()
        else:
            state.accessible = True
            state.last_seen_at = now_iso()
            state.updated_at = now_iso()
            evidence = dict(state.evidence or {})
            evidence["github"] = _github_evidence(repo, matches)["github"]
            evidence["local_matches"] = matches
            state.evidence = evidence
            if state.decided_by == "undecided":
                # Inferred fields may move while the owner has not decided.
                # Qualification never becomes "qualified" here.
                if repo.get("is_archived"):
                    state.qualification = "archived"
                    state.lifecycle_stage = "archived"
                    state.rationale = ("GitHub marks this repository archived; "
                                       "observed, never counted.")
                else:
                    if state.qualification == "archived" and not repo.get("is_archived"):
                        state.qualification = "discovered"
                        state.rationale = rationale
                    if state.classification in (None, "", "unclassified"):
                        state.classification = classification
                        state.rationale = rationale
                    if state.lifecycle_stage in (None, "", "archived"):
                        state.lifecycle_stage = lifecycle
                state.updated_at = now_iso()

        # First-evidence timestamp for honest cycle attribution (GitHub's own
        # creation date, never the scan time).
        created_stamp = repo.get("created_at")
        if created_stamp:
            for membership in session.scalars(select(CultivationMembership).where(
                    CultivationMembership.item_id == item_id)).all():
                evidence = dict(membership.quality_evidence or {})
                if evidence.get("first_evidence_ts") != created_stamp:
                    evidence["first_evidence_ts"] = created_stamp
                    membership.quality_evidence = evidence
                    membership.updated_at = now_iso()

    # Repositories that vanished from GitHub keep their history (missing, not
    # deleted). A single failed sync never reaches here, so a missing flag
    # always reflects a successful observation.
    for row in session.scalars(select(CultivationGitHubRepo)).all():
        if row.node_id in seen:
            continue
        row.missing = True
        row.updated_at = now_iso()
        from mission_control.cultivation import github as _gh_mod2

        state = session.get(CultivationRepoState, _gh_mod2.gh_repo_id(row.node_id))
        if state is not None and state.accessible:
            state.accessible = False
            state.updated_at = now_iso()
            item_id = _repo_item_id(_gh_mod2.gh_repo_uid(row.node_id))
            _record_event(session, goal_id=None,
                          item_id=item_id if session.get(CultivationItem, item_id) else None,
                          event_type="source_removed",
                          note=(f"GitHub repository {row.full_name or row.node_id} no longer listed; "
                                "qualifications and history preserved, counted state unchanged."))

    by_qualification: dict[str, int] = {}
    by_classification: dict[str, int] = {}
    by_lifecycle: dict[str, int] = {}
    public_count = 0
    private_count = 0
    archived_count = 0
    fork_count = 0
    missing_count = 0
    gh_states = session.scalars(select(CultivationRepoState).where(
        CultivationRepoState.repo_id.like("gh-%"))).all()
    for state in gh_states:
        by_qualification[state.qualification] = by_qualification.get(state.qualification, 0) + 1
        by_classification[state.classification] = by_classification.get(state.classification, 0) + 1
        if state.lifecycle_stage:
            by_lifecycle[state.lifecycle_stage] = by_lifecycle.get(state.lifecycle_stage, 0) + 1
    for row in session.scalars(select(CultivationGitHubRepo)).all():
        if row.missing:
            missing_count += 1
            continue
        if row.is_private:
            private_count += 1
        else:
            public_count += 1
        if row.is_archived:
            archived_count += 1
        if row.is_fork:
            fork_count += 1
    observed = {"repos_total": len(seen), "public": public_count, "private": private_count,
                "archived": archived_count, "forks": fork_count, "missing": missing_count,
                "by_qualification": by_qualification,
                "by_classification": by_classification,
                "by_lifecycle": by_lifecycle,
                "fingerprint": _github.fingerprint(valid),
                "note": "GitHub inventory: owner confirmation required before anything counts."}
    changed = observed["fingerprint"] != (source.fingerprint or "")
    source.observed = observed
    source.fingerprint = observed["fingerprint"]
    source.last_sync_at = now_iso()
    source.last_status = "ok"
    source.last_error = None
    source.updated_at = now_iso()
    session.flush()
    if changed and source.goal_id and session.get(CultivationGoal, source.goal_id):
        _record_event(session, goal_id=source.goal_id, event_type="synced",
                      to_value=str(len(seen)),
                      note=(f"Source '{source.name}': {len(seen)} GitHub repositories observed "
                            f"({public_count} public, {private_count} private, "
                            f"{archived_count} archived)."))
    return {"source_id": source.id, "status": "ok", "observed": observed,
            "stale": False, "goal_id": source.goal_id, "new_items": new_items,
            "fingerprint_changed": changed}


def github_summary(session: Session) -> dict[str, Any]:
    """Compact Applications-section summary (inventory vs achievement)."""
    from sqlalchemy import func as _func

    states = session.scalars(select(CultivationRepoState).where(
        CultivationRepoState.repo_id.like("gh-%"))).all()
    discovered = len(states)
    applications_identified = sum(1 for state in states if state.classification == "application")
    books_identified = sum(1 for state in states if state.classification == "book")
    private_count = session.scalar(select(_func.count()).select_from(CultivationGitHubRepo).where(
        CultivationGitHubRepo.missing.is_(False),
        CultivationGitHubRepo.is_private.is_(True))) or 0
    shipped = session.scalar(select(_func.count()).select_from(CultivationApplication).where(
        CultivationApplication.lifecycle_stage.in_(["released", "maintained"]))) or 0
    progress: dict[str, Any] = {}
    for goal_id in ("applications", "repositories", "perfect_repositories"):
        goal = session.get(CultivationGoal, goal_id)
        if goal is not None:
            computed = goal_progress(session, goal)
            progress[goal_id] = {"current": computed["current"], "target": goal.target_value,
                                 "unit": goal.unit, "percent": computed["percent"],
                                 "unknown_reason": computed["unknown_reason"],
                                 "estimate_label": computed.get("estimate_label")}
    completed = 0
    goal = session.get(CultivationGoal, "applications")
    if goal is not None:
        completed = len(_qualified_memberships(session, goal))
    return {"discovered": discovered,
            "private": int(private_count),
            "applications_identified": applications_identified,
            "books_identified": books_identified,
            "completed_applications": int(completed),
            "published_applications": int(shipped),
            "goals": progress}


def _github_repo_read(session: Session, state: CultivationRepoState) -> dict[str, Any]:
    """Display record joining owner judgement with the GitHub snapshot."""
    from mission_control.cultivation import github as _gh_mod

    node_id = state.repo_uid[len(_gh_mod.GH_UID_PREFIX):] if state.repo_uid.startswith(
        _gh_mod.GH_UID_PREFIX) else state.repo_id[len(_gh_mod.GH_REPO_PREFIX):]
    snapshot = session.get(CultivationGitHubRepo, node_id)
    projects: list[dict[str, str]] = []
    if snapshot is not None:
        import os as _os

        project_map = _project_map(session)
        for match in _github_local_matches(session, snapshot.name):
            if match.get("kind") != "repository":
                continue
            for project_id in project_map.get(_os.path.normcase(match.get("path", "")), []):
                project = session.get(Project, project_id)
                if project is not None and all(entry["id"] != project.id for entry in projects):
                    projects.append({"id": project.id, "name": project.name})
    return {
        "repo_id": state.repo_id, "repo_uid": state.repo_uid,
        "name": snapshot.name if snapshot and snapshot.name else state.repo_id,
        "path": None,
        "root_path": "github",
        "branch": snapshot.default_branch if snapshot else None,
        "head_sha": None,
        "accessible": (not snapshot.missing) if snapshot else state.accessible,
        "indexed": False,
        "total_commits": 0,
        "first_commit_ts": None, "last_commit_ts": None,
        "backfill_complete": False,
        "last_indexed_at": snapshot.observed_at if snapshot else None,
        "has_agents": False,
        "has_description": bool(snapshot.description) if snapshot else False,
        "context_status": "missing",
        "projects": projects,
        "qualification": state.qualification, "lifecycle_stage": state.lifecycle_stage,
        "classification": state.classification, "rationale": state.rationale,
        "evidence": dict(state.evidence or {}), "decided_by": state.decided_by,
        "decided_at": state.decided_at, "last_seen_at": state.last_seen_at,
        "created_at": state.created_at, "updated_at": state.updated_at,
        "origin": "github",
        "url": snapshot.url if snapshot else None,
        "description": snapshot.description if snapshot else None,
        "visibility": snapshot.visibility if snapshot else None,
        "language": snapshot.language if snapshot else None,
        "private": bool(snapshot.is_private) if snapshot else False,
        "fork": bool(snapshot.is_fork) if snapshot else False,
        "pushed_at": snapshot.pushed_at if snapshot else None,
        "missing": bool(snapshot.missing) if snapshot else False,
    }


def repo_read(session: Session, state: CultivationRepoState) -> dict[str, Any]:
    """Display record joining owner judgement with live Activity evidence."""
    if state.repo_id.startswith("gh-"):
        return _github_repo_read(session, state)
    repo = _resolve_git_row(session, state)
    projects: list[dict[str, str]] = []
    if repo is not None:
        import os as _os

        for project_id in _project_map(session).get(_os.path.normcase(repo.path), []):
            project = session.get(Project, project_id)
            if project is not None:
                projects.append({"id": project.id, "name": project.name})
    agg_count = agg_first = agg_last = None
    if repo is not None:
        row = session.execute(select(func.count(GitCommit.sha),
                                     func.min(GitCommit.committer_ts),
                                     func.max(GitCommit.committer_ts)).where(
            GitCommit.repo_id == repo.id)).first()
        if row is not None:
            agg_count, agg_first, agg_last = int(row[0]), int(row[1] or 0), int(row[2] or 0)
    return {
        "repo_id": state.repo_id, "repo_uid": state.repo_uid,
        "name": repo.name if repo else state.repo_id,
        "path": repo.path if repo else None,
        "root_path": repo.root_path if repo else None,
        "branch": repo.branch if repo else None,
        "head_sha": repo.head_sha if repo else None,
        "accessible": bool(repo.accessible) if repo else False,
        "indexed": repo is not None,
        "total_commits": agg_count if agg_count is not None else state.last_commit_count,
        "first_commit_ts": agg_first, "last_commit_ts": agg_last,
        "backfill_complete": bool(repo.backfill_complete) if repo else False,
        "last_indexed_at": repo.last_indexed_at if repo else None,
        "has_agents": bool(repo.has_agents) if repo else False,
        "has_description": bool(repo.has_description) if repo else False,
        "context_status": repo.context_status if repo else "missing",
        "projects": projects,
        "qualification": state.qualification, "lifecycle_stage": state.lifecycle_stage,
        "classification": state.classification, "rationale": state.rationale,
        "evidence": dict(state.evidence or {}), "decided_by": state.decided_by,
        "decided_at": state.decided_at, "last_seen_at": state.last_seen_at,
        "created_at": state.created_at, "updated_at": state.updated_at,
        "origin": "activity",
        "url": None,
        "description": None,
        "visibility": None,
        "language": None,
        "private": False,
        "fork": False,
        "pushed_at": None,
        "missing": False,
    }


def list_repo_states(session: Session, *, qualification: str | None = None,
                     classification: str | None = None, lifecycle: str | None = None,
                     root: str | None = None, search: str | None = None,
                     include_unavailable: bool = True,
                     origin: str | None = None, visibility: str | None = None,
                     limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    query = select(CultivationRepoState).order_by(CultivationRepoState.updated_at.desc())
    if origin:
        if origin not in {"activity", "github"}:
            raise ValidationProblem(f"Unknown origin: {origin}")
        if origin == "github":
            query = query.where(CultivationRepoState.repo_id.like("gh-%"))
        else:
            query = query.where(~CultivationRepoState.repo_id.like("gh-%"))
    if visibility:
        normalized = str(visibility).upper()
        if normalized not in {"PUBLIC", "PRIVATE"}:
            raise ValidationProblem(f"Unknown visibility: {visibility}")
        query = query.join(
            CultivationGitHubRepo,
            CultivationGitHubRepo.node_id == func.substr(CultivationRepoState.repo_id, 4),
        ).where(CultivationGitHubRepo.visibility == normalized)
    if qualification:
        if qualification not in REPO_QUALIFICATIONS:
            raise ValidationProblem(f"Unknown qualification: {qualification}")
        query = query.where(CultivationRepoState.qualification == qualification)
    if classification:
        if classification not in REPO_CLASSIFICATIONS:
            raise ValidationProblem(f"Unknown classification: {classification}")
        query = query.where(CultivationRepoState.classification == classification)
    if lifecycle:
        if lifecycle != "unset" and lifecycle not in LIFECYCLE_STAGES:
            raise ValidationProblem(f"Unknown lifecycle stage: {lifecycle}")
        if lifecycle == "unset":
            query = query.where(CultivationRepoState.lifecycle_stage.is_(None))
        else:
            query = query.where(CultivationRepoState.lifecycle_stage == lifecycle)
    if not include_unavailable:
        query = query.where(CultivationRepoState.accessible.is_(True))
    if search:
        needle = f"%{search}%"
        query = query.join(CultivationItem, CultivationItem.id == ("repo-" + CultivationRepoState.repo_uid)).where(
            CultivationItem.title.ilike(needle))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.limit(min(max(limit, 1), 500)).offset(max(offset, 0))).all()
    items = []
    for state in rows:
        record = repo_read(session, state)
        if root and (record["root_path"] or "") != root:
            continue
        items.append(record)
    if items:
        horizon = int(datetime.now(timezone.utc).timestamp()) - 7 * 86400
        repo_ids = [item["repo_id"] for item in items]
        recent = dict(session.execute(select(GitCommit.repo_id, func.count(GitCommit.sha)).where(
            GitCommit.repo_id.in_(repo_ids), GitCommit.committer_ts >= horizon).group_by(
            GitCommit.repo_id)).all())
        from mission_control.models import GitReview as _GitReview
        reviewed = dict(session.execute(select(_GitReview.repo_id, func.count(_GitReview.id)).where(
            _GitReview.repo_id.in_(repo_ids), _GitReview.status == "completed").group_by(
            _GitReview.repo_id)).all())
        for item in items:
            item["recent_commits"] = int(recent.get(item["repo_id"], 0))
            item["review_count"] = int(reviewed.get(item["repo_id"], 0))
    return items, int(total or 0)


def classify_repo(session: Session, repo_id: str, *, classification: str | None = None,
                  lifecycle_stage: str | None = None, qualification: str | None = None,
                  rationale: str = "", evidence: dict[str, Any] | None = None,
                  goal_id: str | None = None, completed_at: str | None = None) -> CultivationRepoState:
    """Owner judgement over a repository. Never applied automatically by sync."""
    state = session.get(CultivationRepoState, repo_id)
    if state is None:
        raise NotFound("Repository is not tracked yet — sync its source first")
    if classification is not None and classification not in REPO_CLASSIFICATIONS:
        raise ValidationProblem(f"Unknown classification: {classification}")
    if lifecycle_stage is not None and lifecycle_stage not in LIFECYCLE_STAGES:
        raise ValidationProblem(f"Unknown lifecycle stage: {lifecycle_stage}")
    if qualification is not None and qualification not in REPO_QUALIFICATIONS:
        raise ValidationProblem(f"Unknown qualification: {qualification}")
    if qualification in {"qualified", "excluded"} and not rationale.strip():
        raise ValidationProblem("Qualifying or excluding a repository requires a rationale")
    changed: list[str] = []
    if classification is not None and state.classification != classification:
        state.classification = classification
        changed.append("classified")
    if lifecycle_stage is not None and state.lifecycle_stage != lifecycle_stage:
        previous = state.lifecycle_stage
        state.lifecycle_stage = lifecycle_stage
        changed.append("lifecycle_stage")
        _record_event(session, goal_id=None, event_type="lifecycle_changed",
                      from_value=previous, to_value=lifecycle_stage,
                      note=rationale or f"Repository lifecycle set to '{lifecycle_stage}'.")
    if qualification is not None and state.qualification != qualification:
        state.qualification = qualification
        changed.append("qualification")
        _record_event(session, goal_id=None, event_type="qualified" if qualification == "qualified" else "unqualified",
                      to_value=qualification, note=rationale)
    if evidence:
        merged = dict(state.evidence or {})
        merged.update(evidence)
        state.evidence = merged
        changed.append("evidence")
    if changed:
        state.decided_by = "owner"
        state.decided_at = now_iso()
    state.updated_at = now_iso()
    session.flush()
    if "qualification" in changed and goal_id and session.get(CultivationGoal, goal_id):
        _sync_repo_membership(session, state, goal_id, completed_at=completed_at)
    return state


def _sync_repo_membership(session: Session, state: CultivationRepoState, goal_id: str,
                          *, completed_at: str | None = None) -> None:
    """A qualified repository counts in the goal; anything else leaves the count."""
    goal = get_goal(session, goal_id)
    item_id = _repo_item_id(state.repo_uid or state.repo_id)
    membership = session.get(CultivationMembership, (item_id, goal_id))
    if state.qualification == "qualified":
        if membership is None:
            membership = CultivationMembership(
                item_id=item_id, goal_id=goal_id, stage=goal.qualifying_stage,
                evidence_status="claimed",
                quality_evidence={"qualified_by": "owner"},
                completed_at=completed_at or now_iso(),
                created_at=now_iso(), updated_at=now_iso())
            session.add(membership)
            session.flush()
            _record_event(session, goal_id=goal_id, item_id=item_id, event_type="completed",
                          to_value=goal.qualifying_stage,
                          note="Repository qualified; counts toward the goal.")
        elif membership.stage != goal.qualifying_stage:
            set_stage(session, item_id, goal_id, stage=goal.qualifying_stage,
                      completed_at=completed_at, note="Repository qualified; counts toward the goal.")
        progress = goal_progress(session, goal)
        _check_milestones(session, goal, progress["current"])
    elif membership is not None and membership.stage == goal.qualifying_stage:
        set_stage(session, item_id, goal_id, stage=_first_configured_stage(session),
                  note="Repository left the qualified state; no longer counted, history kept.")
        progress = goal_progress(session, goal)
        _check_milestones(session, goal, progress["current"])


def bulk_set_qualification(session: Session, repo_ids: list[str], *,
                           qualification: str, rationale: str,
                           goal_id: str | None = None) -> dict[str, int]:
    """Explicit owner bulk action; every repository recorded individually."""
    if qualification not in REPO_QUALIFICATIONS:
        raise ValidationProblem(f"Unknown qualification: {qualification}")
    if not rationale.strip():
        raise ValidationProblem("Bulk qualification requires a rationale")
    done = 0
    for repo_id in list(repo_ids or [])[:500]:
        state = session.get(CultivationRepoState, repo_id)
        if state is None:
            continue
        classify_repo(session, repo_id, qualification=qualification,
                      rationale=rationale, goal_id=goal_id)
        done += 1
    return {"updated": done}


# ------------------------------------------------------------ applications
def list_applications(session: Session, *, lifecycle: str | None = None,
                      search: str | None = None) -> list[CultivationApplication]:
    if lifecycle is not None and lifecycle not in LIFECYCLE_STAGES:
        raise ValidationProblem(f"Unknown lifecycle stage: {lifecycle}")
    query = select(CultivationApplication).order_by(CultivationApplication.name)
    if lifecycle:
        query = query.where(CultivationApplication.lifecycle_stage == lifecycle)
    if search:
        query = query.where(CultivationApplication.name.ilike(f"%{search}%"))
    return list(session.scalars(query.limit(500)).all())


def get_application(session: Session, app_id: str) -> CultivationApplication:
    app = session.get(CultivationApplication, app_id)
    if app is None:
        raise NotFound("Application not found")
    return app


def create_application(session: Session, payload: dict[str, Any]) -> CultivationApplication:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValidationProblem("Application name must not be empty")
    app_id = str(payload.get("id") or _new_id("capp"))
    if session.get(CultivationApplication, app_id) is not None:
        raise Conflict("Application id already exists")
    lifecycle = str(payload.get("lifecycle_stage", "idea"))
    if lifecycle not in LIFECYCLE_STAGES:
        raise ValidationProblem(f"Unknown lifecycle stage: {lifecycle}")
    if lifecycle in {"released", "maintained"}:
        raise ValidationProblem("New applications start unreleased — use the release action with evidence")
    app = CultivationApplication(
        id=app_id, name=name[:200], description=str(payload.get("description", ""))[:4000],
        lifecycle_stage=lifecycle, release_evidence={},
        notes=str(payload.get("notes", ""))[:4000],
        created_at=now_iso(), updated_at=now_iso())
    session.add(app)
    session.flush()
    for repo_id in list(payload.get("repo_ids", []) or [])[:50]:
        link_app_repo(session, app_id, repo_id)
    _record_event(session, goal_id=None, event_type="application_created",
                  note=f"Application '{name}' registered at stage '{lifecycle}'.")
    return app


def update_application(session: Session, app_id: str, payload: dict[str, Any]) -> CultivationApplication:
    app = get_application(session, app_id)
    for field in ("name", "description", "notes"):
        if field in payload and payload[field] is not None:
            setattr(app, field, str(payload[field])[:4000 if field != "name" else 200])
    if "lifecycle_stage" in payload and payload["lifecycle_stage"] is not None:
        stage = str(payload["lifecycle_stage"])
        if stage not in LIFECYCLE_STAGES:
            raise ValidationProblem(f"Unknown lifecycle stage: {stage}")
        if stage in {"released", "maintained"} and not app.release_evidence:
            raise ValidationProblem("Releasing requires release evidence — use the release action")
        if app.lifecycle_stage != stage:
            previous = app.lifecycle_stage
            app.lifecycle_stage = stage
            _record_event(session, goal_id=None, event_type="lifecycle_changed",
                          from_value=previous, to_value=stage,
                          note=f"Application '{app.name}' moved to '{stage}'.")
            if stage not in {"released", "maintained"}:
                _sync_app_membership(session, app, None)
    app.updated_at = now_iso()
    session.flush()
    return app


def link_app_repo(session: Session, app_id: str, repo_id: str) -> None:
    from mission_control.cultivation import github as _gh_mod

    get_application(session, app_id)
    if repo_id.startswith(_gh_mod.GH_REPO_PREFIX):
        node_id = repo_id[len(_gh_mod.GH_REPO_PREFIX):]
        if session.get(CultivationGitHubRepo, node_id) is None:
            raise NotFound("Repository is not in the GitHub inventory — sync its source first")
    elif session.get(GitRepository, repo_id) is None:
        raise NotFound("Repository is not in the Activity index")
    if session.get(CultivationAppRepo, (app_id, repo_id)) is None:
        session.add(CultivationAppRepo(app_id=app_id, repo_id=repo_id, created_at=now_iso()))
        session.flush()
        _record_event(session, goal_id=None, event_type="application_linked",
                      note=f"Repository {repo_id[:12]}… linked to '{session.get(CultivationApplication, app_id).name}'.")


def unlink_app_repo(session: Session, app_id: str, repo_id: str) -> None:
    link = session.get(CultivationAppRepo, (app_id, repo_id))
    if link is None:
        raise NotFound("Repository is not linked to this application")
    session.delete(link)
    session.flush()
    _record_event(session, goal_id=None, event_type="application_unlinked",
                  note="Repository unlinked; link history preserved.")


def _validate_release_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    kind = str(evidence.get("kind", ""))
    if kind not in RELEASE_EVIDENCE_KINDS:
        raise ValidationProblem("Release evidence kind must be one of: " + ", ".join(sorted(RELEASE_EVIDENCE_KINDS)))
    if not str(evidence.get("reference", "") or "").strip() and not str(evidence.get("note", "") or "").strip():
        raise ValidationProblem("Release evidence needs a reference or an owner note")
    completed_at = evidence.get("completed_at")
    if completed_at:
        try:
            datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
        except ValueError:
            raise ValidationProblem("completed_at must be an ISO-8601 timestamp") from None
    return {"kind": kind, "reference": str(evidence.get("reference", ""))[:2000],
            "date": str(evidence.get("date", "") or "")[:40],
            "authority": str(evidence.get("authority", "owner"))[:120],
            "note": str(evidence.get("note", ""))[:4000],
            "completed_at": str(completed_at or "")[:40] or None}


def release_application(session: Session, app_id: str, *, lifecycle: str,
                        evidence: dict[str, Any], completed_at: str | None = None,
                        goal_id: str | None = None, note: str = "") -> CultivationApplication:
    if lifecycle not in {"released", "maintained"}:
        raise ValidationProblem("Release requires the released or maintained stage")
    app = get_application(session, app_id)
    checked = _validate_release_evidence(dict(evidence or {}))
    stamp = completed_at or checked.get("completed_at") or now_iso()
    try:
        datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        raise ValidationProblem("completed_at must be an ISO-8601 timestamp") from None
    previous = app.lifecycle_stage
    app.lifecycle_stage = lifecycle
    app.release_evidence = checked
    app.completed_at = stamp
    app.updated_at = now_iso()
    session.flush()
    _record_event(session, goal_id=None, event_type="lifecycle_changed",
                  from_value=previous, to_value=lifecycle,
                  note=(note or f"Application '{app.name}' {lifecycle} "
                        f"({checked['kind']}: {checked['reference'] or checked['note']})."))
    _sync_app_membership(session, app, goal_id or "applications", completed_at=stamp)
    return app


def unrelease_application(session: Session, app_id: str, *, note: str = "") -> CultivationApplication:
    app = get_application(session, app_id)
    if app.lifecycle_stage in {"released", "maintained"}:
        app.lifecycle_stage = "functional"
        app.updated_at = now_iso()
        session.flush()
        _record_event(session, goal_id=None, event_type="reopened",
                      note=note or "Release withdrawn; application no longer counts as shipped.")
        _sync_app_membership(session, app, None)
    return app


def _sync_app_membership(session: Session, app: CultivationApplication, goal_id: str | None,
                         *, completed_at: str | None = None) -> None:
    """One released application counts once, however many repositories it owns."""
    item_id = _app_item_id(app.id)
    item = session.get(CultivationItem, item_id)
    if item is None:
        item = CultivationItem(
            id=item_id, title=app.name, item_type="application", provenance="unclassified",
            source_application="cultivation", source_ref=f"application:{app.id}",
            notes=app.description, created_at=now_iso(), updated_at=now_iso())
        session.add(item)
        session.flush()
    else:
        item.title = app.name
        item.updated_at = now_iso()
    if goal_id is None:
        # Goal unknown (e.g. after unrelease): move every qualifying
        # membership out, keeping history, instead of leaving a stale count.
        for membership in list(session.scalars(select(CultivationMembership).where(
                CultivationMembership.item_id == item_id)).all()):
            goal = session.get(CultivationGoal, membership.goal_id)
            if goal is not None and membership.stage == goal.qualifying_stage:
                set_stage(session, item_id, goal.id, stage=_first_configured_stage(session),
                          note="Application no longer shipped; removed from the count with history kept.")
                progress = goal_progress(session, goal)
                _check_milestones(session, goal, progress["current"])
        return
    goal = session.get(CultivationGoal, goal_id)
    assert goal is not None
    membership = session.get(CultivationMembership, (item_id, goal_id))
    if app.lifecycle_stage in {"released", "maintained"}:
        if membership is None:
            membership = CultivationMembership(
                item_id=item_id, goal_id=goal_id, stage=goal.qualifying_stage,
                evidence_status="claimed",
                quality_evidence={"release": dict(app.release_evidence or {})},
                completed_at=completed_at or app.completed_at or now_iso(),
                created_at=now_iso(), updated_at=now_iso())
            session.add(membership)
            session.flush()
            _record_event(session, goal_id=goal_id, item_id=item_id, event_type="completed",
                          to_value=goal.qualifying_stage,
                          note=f"Application '{app.name}' shipped; counts once.")
        elif membership.stage != goal.qualifying_stage:
            set_stage(session, item_id, goal_id, stage=goal.qualifying_stage,
                      completed_at=completed_at or app.completed_at, note="Application shipped.")
        progress = goal_progress(session, goal)
        _check_milestones(session, goal, progress["current"])
    elif membership is not None and membership.stage == goal.qualifying_stage:
        set_stage(session, item_id, goal_id, stage=_first_configured_stage(session),
                  note="Application no longer shipped; removed from the count with history kept.")
        progress = goal_progress(session, goal)
        _check_milestones(session, goal, progress["current"])


def app_read(session: Session, app: CultivationApplication) -> dict[str, Any]:
    repos = []
    for link in session.scalars(select(CultivationAppRepo).where(
            CultivationAppRepo.app_id == app.id)).all():
        state = session.get(CultivationRepoState, link.repo_id)
        git_repo = session.get(GitRepository, link.repo_id)
        if git_repo is not None:
            repos.append({
                "repo_id": link.repo_id,
                "name": git_repo.name,
                "path": git_repo.path,
                "qualification": state.qualification if state else "untracked",
                "accessible": bool(git_repo.accessible),
            })
            continue
        github_row = None
        if link.repo_id.startswith("gh-"):
            github_row = session.get(CultivationGitHubRepo, link.repo_id[len("gh-"):])
        repos.append({
            "repo_id": link.repo_id,
            "name": github_row.full_name if github_row and github_row.full_name else (
                github_row.name if github_row else (state.repo_uid if state else link.repo_id)),
            "path": None,
            "qualification": state.qualification if state else "untracked",
            "accessible": state.accessible if state else False,
        })
    memberships = []
    item = session.get(CultivationItem, _app_item_id(app.id))
    if item is not None:
        for membership in session.scalars(select(CultivationMembership).where(
                CultivationMembership.item_id == item.id)).all():
            goal = session.get(CultivationGoal, membership.goal_id)
            memberships.append({
                "goal_id": membership.goal_id, "goal_name": goal.name if goal else None,
                "stage": membership.stage, "completed_at": membership.completed_at,
                "qualified": bool(membership.qualified),
                "evidence_status": membership.evidence_status,
            })
    return {"id": app.id, "name": app.name, "description": app.description,
            "lifecycle_stage": app.lifecycle_stage, "release_evidence": dict(app.release_evidence or {}),
            "completed_at": app.completed_at, "notes": app.notes,
            "created_at": app.created_at, "updated_at": app.updated_at,
            "repos": repos, "memberships": memberships}


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
    cycle = active_cycle(session)
    pinned_skills = [skill_read(session, skill) for skill in session.scalars(select(CultivationSkill).where(
        CultivationSkill.pinned.is_(True), CultivationSkill.state != "archived").order_by(
        CultivationSkill.pin_order, CultivationSkill.name)).all()]
    return {
        "primary": _hud_goal(primary) if primary else None,
        "pinned": [_hud_goal(goal) for goal in pinned],
        "rank": ranks["current"],
        "recent_completions": [event_read(session, event) for event in recent],
        "generated_at": now_iso(),
        "cycle": cycle_read(session, cycle) if cycle else None,
        "pinned_skills": pinned_skills,
    }


# ------------------------------------------------------------------ skills
def list_skills(session: Session, *, include_archived: bool = False) -> list[CultivationSkill]:
    query = select(CultivationSkill).order_by(CultivationSkill.pin_order, CultivationSkill.name)
    if not include_archived:
        query = query.where(CultivationSkill.state != "archived")
    return list(session.scalars(query).all())


def get_skill(session: Session, skill_id: str) -> CultivationSkill:
    skill = session.get(CultivationSkill, skill_id)
    if skill is None:
        raise NotFound("Skill not found")
    return skill


def create_skill(session: Session, payload: dict[str, Any]) -> CultivationSkill:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValidationProblem("Skill name must not be empty")
    skill_id = str(payload.get("id") or _new_id("skl"))
    if session.get(CultivationSkill, skill_id) is not None:
        raise Conflict("Skill id already exists")
    state = str(payload.get("state", "active"))
    if state not in SKILL_STATES:
        raise ValidationProblem(f"Unknown state: {state}")
    skill = CultivationSkill(
        id=skill_id, name=name[:120], icon=str(payload.get("icon", "sprout"))[:40],
        category=str(payload.get("category", "general"))[:60],
        description=str(payload.get("description", ""))[:2000],
        pinned=bool(payload.get("pinned", False)), pin_order=int(payload.get("pin_order", 100)),
        state=state, created_at=now_iso(), updated_at=now_iso())
    session.add(skill)
    session.flush()
    _record_event(session, goal_id=None, event_type="skill_created", note=f"Skill '{name}' created.")
    return skill


def update_skill(session: Session, skill_id: str, payload: dict[str, Any]) -> CultivationSkill:
    skill = get_skill(session, skill_id)
    for field in ("name", "icon", "category", "description"):
        if field in payload and payload[field] is not None:
            setattr(skill, field, str(payload[field])[:2000 if field == "description" else 120])
    if "state" in payload and payload["state"] is not None:
        if str(payload["state"]) not in SKILL_STATES:
            raise ValidationProblem("Unknown state")
        skill.state = str(payload["state"])
    for field in ("pinned", "pin_order"):
        if field in payload and payload[field] is not None:
            setattr(skill, field, bool(payload[field]) if field == "pinned" else int(payload[field]))
    skill.updated_at = now_iso()
    session.flush()
    return skill


def reorder_skill_pins(session: Session, ordered_ids: list[str]) -> None:
    for position, skill_id in enumerate(ordered_ids[:200]):
        skill = session.get(CultivationSkill, skill_id)
        if skill is None:
            raise NotFound(f"Skill not found: {skill_id}")
        skill.pin_order = position
        skill.updated_at = now_iso()
    session.flush()


def skill_goals(session: Session, skill_id: str) -> list[CultivationGoal]:
    get_skill(session, skill_id)
    return list(session.scalars(select(CultivationGoal).where(
        CultivationGoal.skill_id == skill_id).order_by(
        CultivationGoal.priority, CultivationGoal.name)).all())


def skill_read(session: Session, skill: CultivationSkill) -> dict[str, Any]:
    goals = skill_goals(session, skill.id)
    achieved = sum(1 for goal in goals if goal.state == "achieved")
    completions = 0
    for goal in goals:
        completions += session.scalar(select(func.count()).select_from(CultivationMembership).where(
            CultivationMembership.goal_id == goal.id,
            CultivationMembership.completed_at.is_not(None))) or 0
    members = []
    for goal in goals:
        progress = goal_progress(session, goal)
        members.append({"id": goal.id, "name": goal.name, "unit": goal.unit,
                        "state": goal.state, "progress": progress})
    return {"id": skill.id, "name": skill.name, "icon": skill.icon,
            "category": skill.category, "description": skill.description,
            "pinned": bool(skill.pinned), "pin_order": skill.pin_order,
            "state": skill.state, "created_at": skill.created_at,
            "updated_at": skill.updated_at,
            "goals_total": len(goals), "goals_achieved": achieved,
            "item_completions": int(completions), "goals": members}


# ----------------------------------------------------------------- sources
def list_sources(session: Session) -> list[CultivationSource]:
    return list(session.scalars(select(CultivationSource).order_by(CultivationSource.name)).all())


def get_source(session: Session, source_id: str) -> CultivationSource:
    source = session.get(CultivationSource, source_id)
    if source is None:
        raise NotFound("Source not found")
    return source


def create_source(session: Session, payload: dict[str, Any]) -> CultivationSource:
    from mission_control.core.paths import require_existing_directory
    kind = str(payload.get("kind", "hugo_blog"))
    if kind not in SOURCE_KINDS:
        raise ValidationProblem(
            "Unsupported source kind: {kind}. Only hugo_blog, activity_projects, numbered_files, "
            "script_registry and github_repos are implemented.".format(kind=kind))
    raw_path = str(payload.get("path", "") or "")
    if kind in ("activity_projects", "script_registry", "github_repos"):
        # The registry lives in the database and reads the configured scripts
        # root; an explicit path is optional and only documents intent.
        path = require_existing_directory(raw_path, field="source path") if raw_path else ""
    else:
        path = require_existing_directory(raw_path, field="source path")
    skill_id = payload.get("skill_id")
    if skill_id is not None and session.get(CultivationSkill, skill_id) is None:
        raise NotFound("Skill not found")
    goal_id = payload.get("goal_id")
    if goal_id is not None and session.get(CultivationGoal, goal_id) is None:
        raise NotFound("Goal not found")
    source_id = str(payload.get("id") or _new_id("src"))
    if session.get(CultivationSource, source_id) is not None:
        raise Conflict("Source id already exists")
    source = CultivationSource(
        id=source_id, name=str(payload.get("name", "Source")).strip()[:120] or "Source",
        kind=kind, skill_id=skill_id, goal_id=goal_id, path=path,
        config=dict(payload.get("config", {}) or {}),
        last_status="never_synced", created_at=now_iso(), updated_at=now_iso())
    session.add(source)
    session.flush()
    return source


def update_source(session: Session, source_id: str, payload: dict[str, Any]) -> CultivationSource:
    from mission_control.core.paths import require_existing_directory
    source = get_source(session, source_id)
    if "name" in payload and payload["name"] is not None:
        source.name = str(payload["name"]).strip()[:120] or source.name
    if "path" in payload and payload["path"] is not None:
        raw = str(payload["path"] or "")
        if source.kind in ("activity_projects", "script_registry", "github_repos") and not raw:
            source.path = ""
        else:
            source.path = require_existing_directory(raw or str(source.path), field="source path")
    for field in ("skill_id", "goal_id"):
        if field in payload:
            value = payload[field]
            if value is not None:
                model = CultivationSkill if field == "skill_id" else CultivationGoal
                if session.get(model, value) is None:
                    raise NotFound(f"{'Skill' if field == 'skill_id' else 'Goal'} not found")
            setattr(source, field, value)
    if "config" in payload and payload["config"] is not None:
        if not isinstance(payload["config"], dict):
            raise ValidationProblem("config must be a mapping")
        source.config = dict(payload["config"])
    source.updated_at = now_iso()
    session.flush()
    return source


def _observed_item_id(prefix: str, source_id: str, identity: str) -> str:
    import hashlib as _hashlib
    return prefix + _hashlib.sha1(f"{source_id}:{identity}".encode("utf-8")).hexdigest()[:16]


def _hugo_item_id(source_id: str, identity: str) -> str:
    return _observed_item_id("hugo-", source_id, identity)


def _script_item_id(source_id: str, identity: str) -> str:
    return _observed_item_id("script-", source_id, identity)


def sync_source(session: Session, source_id: str) -> dict[str, Any]:
    """Dispatch to the kind-specific synchronizer.

    All synchronizers are read-only toward their evidence: the Hugo scanner
    and the numbered-file scanner read files; the Activity adapter reads
    indexed rows only. The script registry reads the configured scripts root
    through the registry reconciler and never invents completions.
    """
    source = get_source(session, source_id)
    # Controlled retirement: the legacy numbered-file scripts source becomes
    # the registry-backed source on first sync. History is preserved; the old
    # file-counts-as-completed logic can no longer run for script goals.
    if source.id == "src-scripts" and source.kind == "numbered_files":
        ensure_script_source_retired(session)
        source = get_source(session, source_id)
    if source.kind == "hugo_blog":
        return _sync_hugo_blog(session, source)
    if source.kind == "numbered_files":
        return _sync_numbered_files(session, source)
    if source.kind == "script_registry":
        return _sync_script_registry(session, source)
    if source.kind == "activity_projects":
        return sync_activity_projects(session, source_id)
    if source.kind == "github_repos":
        return sync_github_repos(session, source_id)
    raise ValidationProblem(f"Unsupported source kind: {source.kind}")


def ensure_script_source_retired(session: Session) -> bool:
    """Migrate the seeded scripts source to the registry-backed kind.

    Returns True when a migration happened. Never deletes the source row,
    never invents completions, never touches the filesystem.
    """
    source = session.get(CultivationSource, "src-scripts")
    if source is None or source.kind == "script_registry":
        return False
    if source.kind != "numbered_files":
        return False
    source.kind = "script_registry"
    config = dict(source.config or {})
    config.pop("period_goal_id", None)
    source.config = config
    source.updated_at = now_iso()
    session.flush()
    _record_event(session, goal_id=source.goal_id, event_type="source_retired",
                  note="Legacy numbered-file interpretation retired; the script registry is now authoritative. File existence no longer counts as completion.")
    return True


def _feed_period_goal(session: Session, source: CultivationSource, post: Any) -> None:
    """Record one output unit for a linked weekly-rhythm goal.

    A numbered-file source may name a recurring ``period`` goal in its config
    (``period_goal_id``). Each newly observed script records a single
    measurement dated at the script's own date, so the weekly goal counts
    output inside its window. Only new items feed; resyncs dedupe on the
    sync source + note and never double-count. Removals do not retract
    history: the measurement stays as observed fact.
    """
    config = source.config if isinstance(source.config, dict) else {}
    period_goal_id = config.get("period_goal_id")
    if not period_goal_id or post.state != "published":
        return
    goal = session.get(CultivationGoal, str(period_goal_id))
    if goal is None:
        return
    if goal.measurement_type != "recurring" or (goal.recurring_mode or "daily") != "period":
        return
    note = f"New script observed: {post.relpath}."
    marker = f"sync:{source.id}"
    existing = session.scalars(select(CultivationMeasurement).where(
        CultivationMeasurement.goal_id == goal.id,
        CultivationMeasurement.source == marker,
        CultivationMeasurement.note == note)).first()
    if existing is not None:
        return
    record_measurement(session, goal.id, value=1.0,
                       observed_at=post.date.isoformat() if post.date else now_iso(),
                       note=note, source=marker)


def _store_scan_observation(session: Session, source: CultivationSource, scan: Any) -> dict[str, Any]:
    """Persist a file-scan observation on the source (shared sync helper)."""
    observed = {"published": scan.published, "drafts": scan.drafts, "unknown": scan.unknown,
                "excluded": scan.excluded, "candidates": scan.candidates,
                "errors": scan.errors[:20], "fingerprint": scan.fingerprint}
    # Hugo blogs carry enriched cultivation dimensions (scheduled, tech/finance,
    # Dublin weekly windows, latest posts). Merge them when available without
    # breaking the legacy keys used by existing tests.
    try:
        from mission_control.cultivation.sources import blog_observation as _blog_obs

        if source.kind == "hugo_blog" and hasattr(scan, "posts"):
            enriched = _blog_obs(scan)
            for key, value in enriched.items():
                if key not in observed:
                    observed[key] = value
    except Exception:
        pass
    source.observed = observed
    source.fingerprint = scan.fingerprint
    source.last_sync_at = now_iso()
    source.last_status = "ok"
    source.last_error = "; ".join(error["error"] for error in scan.errors[:3]) or None
    source.updated_at = now_iso()
    session.flush()
    return observed


def _mark_source_stale(session: Session, source: CultivationSource) -> dict[str, Any]:
    """Keep the last observation when the source directory is unavailable."""
    source.last_status = "stale"
    source.last_error = "Source directory unavailable; kept the last observation."
    source.updated_at = now_iso()
    session.flush()
    return {"source_id": source.id, "status": "stale", "observed": dict(source.observed or {}),
            "error": source.last_error, "stale": True}


def _attach_live_source(session: Session, source: CultivationSource, goal: CultivationGoal,
                        evidence_kind: str) -> None:
    """Point a goal at its live source, preserving the baseline as history."""
    if goal.evidence_source != evidence_kind:
        goal.evidence_source = evidence_kind
        goal.updated_at = now_iso()
        _record_event(session, goal_id=goal.id, event_type="goal_updated",
                      note=f"Live source '{source.name}' attached: progress now follows observed counts; "
                           "the user-attested baseline is preserved as history.")


def _reconcile_observed_items(
    session: Session,
    source: CultivationSource,
    goal: CultivationGoal,
    scan: Any,
    *,
    item_type: str,
    source_application: str,
    item_id_fn: Any,
    completed_label: str,
) -> dict[str, Any]:
    """Reconcile file-scan observations into items, memberships and events.

    Shared by the Hugo blog and numbered-file synchronizers: the scan is the
    observed truth, manual holds and human qualifications survive, history is
    preserved as events, and a linked weekly-rhythm goal is fed one unit per
    newly observed item.
    """
    observed = dict(source.observed or {})
    stages = get_config(session)["stages"]
    stage_ids = [str(stage["id"]) for stage in stages]
    first_stage = stage_ids[0] if stage_ids else "idea"
    draft_stage = "development" if "development" in stage_ids else first_stage
    qualifying = goal.qualifying_stage if goal.qualifying_stage in stage_ids else None
    seen: set[str] = set()
    for post in scan.posts:
        item_id = item_id_fn(source.id, post.identity)
        seen.add(item_id)
        item = session.get(CultivationItem, item_id)
        if item is None:
            item = CultivationItem(
                id=item_id, title=post.title or post.identity, item_type=item_type,
                notes=f"Observed in {source.name}.", provenance="unclassified",
                source_application=source_application,
                source_ref=f"{source.id}:{post.relpath}",
                created_at=now_iso(), updated_at=now_iso())
            session.add(item)
            session.flush()
        else:
            item.title = post.title or item.title
            item.source_ref = f"{source.id}:{post.relpath}"
            item.updated_at = now_iso()
        target = qualifying if post.state == "published" and qualifying else (
            draft_stage if post.state == "draft" else first_stage)
        membership = session.get(CultivationMembership, (item_id, goal.id))
        first_seen = post.date.isoformat() if post.date else None
        if membership is None:
            membership = CultivationMembership(
                item_id=item_id, goal_id=goal.id, stage=target,
                evidence_status="claimed" if post.state == "published" else "none",
                quality_evidence={"managed_by": source.id, "fingerprint": post.fingerprint,
                                  "mtime_ns": post.mtime_ns, "relpath": post.relpath,
                                  "first_evidence_ts": first_seen},
                completed_at=post.date.isoformat() if post.state == "published" and post.date else (
                    now_iso() if post.state == "published" else None),
                created_at=now_iso(), updated_at=now_iso())
            session.add(membership)
            session.flush()
            _record_event(session, goal_id=goal.id, item_id=item_id, event_type="item_added",
                          to_value=target, note=f"Observed '{item.title}' in {source.name} ({post.reason}).")
            if post.state == "published":
                _record_event(session, goal_id=goal.id, item_id=item_id, event_type="completed",
                              to_value=target, note=f"{completed_label}: {post.relpath}.")
                _feed_period_goal(session, source, post)
            continue
        membership.quality_evidence = {**dict(membership.quality_evidence or {}),
                                       "fingerprint": post.fingerprint,
                                       "mtime_ns": post.mtime_ns, "relpath": post.relpath,
                                       "managed_by": source.id,
                                       "first_evidence_ts": first_seen or membership.quality_evidence.get("first_evidence_ts")}
        membership.updated_at = now_iso()
        if membership.quality_evidence.get("manual_hold"):
            continue
        if membership.stage != target:
            set_stage(session, item_id, goal.id, stage=target, by_sync=True,
                      completed_at=post.date.isoformat() if post.state == "published" and post.date else None,
                      note=f"Observed by source '{source.name}': {post.reason}.")
        elif post.state == "published" and not membership.completed_at and post.date:
            membership.completed_at = post.date.isoformat()
    # Reconcile removals: files no longer observed leave the qualifying set,
    # with history preserved as events. Human qualifications are kept.
    for membership in session.scalars(select(CultivationMembership).where(
            CultivationMembership.goal_id == goal.id)).all():
        item = session.get(CultivationItem, membership.item_id)
        if item is None or item.source_application != source_application:
            continue
        ref = str(item.source_ref or "")
        if not ref.startswith(f"{source.id}:") or membership.item_id in seen:
            continue
        set_stage(session, membership.item_id, goal.id, stage=first_stage, by_sync=True,
                  note=f"Observed by source '{source.name}': file no longer present; moved out of '{membership.stage}'.")
        refreshed = session.get(CultivationMembership, (membership.item_id, goal.id))
        if refreshed is not None and refreshed.qualified and refreshed.quality_evidence.get("qualified_by") != "user":
            refreshed.qualified = False
            refreshed.qualified_at = None
            refreshed.updated_at = now_iso()
            _record_event(session, goal_id=goal.id, item_id=membership.item_id, event_type="unqualified",
                          note="Source item removed; automatic qualification cleared (human qualifications are kept).")
        _record_event(session, goal_id=goal.id, item_id=membership.item_id, event_type="source_removed",
                      note=f"File {ref.split(':', 1)[1] if ':' in ref else ref} no longer observed in {source.name}.")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    _record_event(session, goal_id=goal.id, event_type="synced",
                  to_value=str(observed["published"]),
                  note=(f"Source '{source.name}': {observed['published']} published, "
                        f"{observed['drafts']} drafts, {observed['unknown']} unknown of "
                        f"{observed['candidates']} files."))
    return {"source_id": source.id, "status": "ok", "observed": observed,
            "stale": False, "goal_id": goal.id, "current": progress["current"]}


def _sync_hugo_blog(session: Session, source: CultivationSource) -> dict[str, Any]:
    from pathlib import Path as _Path

    from mission_control.cultivation.sources import scan_hugo_blog
    if not source.path or not _Path(source.path).is_dir():
        return _mark_source_stale(session, source)
    scan = scan_hugo_blog(source.path)
    observed = _store_scan_observation(session, source, scan)

    goal = session.get(CultivationGoal, source.goal_id) if source.goal_id else None
    if goal is None:
        return {"source_id": source.id, "status": "ok", "observed": observed,
                "stale": False, "goal_id": None}
    _attach_live_source(session, source, goal, "hugo_blog")
    return _reconcile_observed_items(
        session, source, goal, scan, item_type="blog_post",
        source_application="hugo_blog", item_id_fn=_hugo_item_id,
        completed_label="Published post observed")


def _sync_numbered_files(session: Session, source: CultivationSource) -> dict[str, Any]:
    """Sync a numbered-script directory (e.g. self-hypnosis ``ScriptNNN.md`` files).

    Every matching file is one published item; everything else is excluded.
    Read-only toward the scanned tree; a linked weekly-rhythm goal named in
    the source config (``period_goal_id``) is fed one unit per new script.
    NOTE: script goals must use the ``script_registry`` kind instead; this
    legacy path is kept only for non-script numbered collections.
    """
    from pathlib import Path as _Path

    from mission_control.cultivation.sources import scan_numbered_files
    if not source.path or not _Path(source.path).is_dir():
        return _mark_source_stale(session, source)
    scan = scan_numbered_files(source.path)
    observed = _store_scan_observation(session, source, scan)

    goal = session.get(CultivationGoal, source.goal_id) if source.goal_id else None
    if goal is None:
        return {"source_id": source.id, "status": "ok", "observed": observed,
                "stale": False, "goal_id": None}
    _attach_live_source(session, source, goal, "numbered_files")
    return _reconcile_observed_items(
        session, source, goal, scan, item_type="script",
        source_application="numbered_files", item_id_fn=_script_item_id,
        completed_label="New script observed")


def _sync_script_registry(session: Session, source: CultivationSource) -> dict[str, Any]:
    """Registry-backed script sync: completion comes from explicit records.

    Reconciles the configured scripts root into stable records, then reports
    completed vs discovered. Never treats file existence as completion and
    never feeds the weekly goal from file dates; weekly units are recorded
    when a script is explicitly marked completed.
    """
    from mission_control.scripts import service as _scripts

    try:
        result = _scripts.sync_scripts(session)
    except ValidationProblem as exc:
        source.last_status = "stale"
        source.last_error = exc.message
        source.updated_at = now_iso()
        session.flush()
        return {"source_id": source.id, "status": "stale",
                "observed": dict(source.observed or {}), "stale": True,
                "error": exc.message, "goal_id": source.goal_id}
    if result.get("status") in ("stale", "unavailable"):
        source.last_status = "stale"
        source.last_error = result.get("error") or "Script directory unavailable; kept the last observation."
        source.updated_at = now_iso()
        session.flush()
        return {"source_id": source.id, "status": "stale",
                "observed": dict(source.observed or {}), "stale": True,
                "error": source.last_error, "goal_id": source.goal_id}
    counts = result.get("counts", {}) or {}
    completed = int(counts.get("completed", 0))
    total = int(counts.get("total", 0))
    present = int(counts.get("present", total))
    ready = int(counts.get("ready", 0))
    needs_review = int(counts.get("needs_review", 0))
    archived = int(counts.get("archived", 0))
    missing = int(counts.get("missing", 0))
    drafts = max(0, present - completed)
    observed = {"published": completed, "drafts": drafts, "unknown": missing,
                "excluded": int(result.get("observed", {}).get("excluded", 0)),
                "candidates": int(result.get("observed", {}).get("candidates", total)),
                "discovered": total, "completed": completed, "ready": ready,
                "needs_review": needs_review, "archived": archived, "missing": missing,
                "library_key": result.get("library_key", ""),
                "fingerprint": result.get("fingerprint", "")}
    source.observed = observed
    source.fingerprint = str(result.get("fingerprint", "") or "")
    source.last_sync_at = now_iso()
    source.last_status = "ok"
    source.last_error = None
    source.updated_at = now_iso()
    session.flush()
    goal = session.get(CultivationGoal, source.goal_id) if source.goal_id else None
    if goal is None:
        return {"source_id": source.id, "status": "ok", "observed": observed,
                "stale": False, "goal_id": None}
    _attach_live_source(session, source, goal, "script_registry")
    progress = goal_progress(session, goal)
    _check_milestones(session, goal, progress["current"])
    _record_event(session, goal_id=goal.id, event_type="synced",
                  to_value=str(completed),
                  note=(f"Source '{source.name}': {completed} completed, "
                        f"{total} discovered ({ready} ready, {needs_review} need review, "
                        f"{missing} missing, {archived} archived)."))
    return {"source_id": source.id, "status": "ok", "observed": observed,
            "stale": False, "goal_id": goal.id, "current": progress["current"]}


# ------------------------------------------------------------------ cycles
_ROMAN = [(100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(value: int) -> str:
    result = ""
    remaining = max(1, int(value))
    for amount, numeral in _ROMAN:
        while remaining >= amount:
            result += numeral
            remaining -= amount
    return result


def _parse_cycle_date(value: str | None, *, field: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    text = str(value).strip()[:10]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValidationProblem(f"{field} must be a YYYY-MM-DD date") from None
    return text


def list_cycles(session: Session) -> list[CultivationCycle]:
    return list(session.scalars(select(CultivationCycle).order_by(CultivationCycle.number)).all())


def get_cycle(session: Session, cycle_id: str) -> CultivationCycle:
    cycle = session.get(CultivationCycle, cycle_id)
    if cycle is None:
        raise NotFound("Cycle not found")
    return cycle


def create_cycle(session: Session, payload: dict[str, Any]) -> CultivationCycle:
    number = payload.get("number")
    if number is None:
        highest = session.scalar(select(func.max(CultivationCycle.number))) or 0
        number = int(highest) + 1
    number = int(number)
    if number < 1:
        raise ValidationProblem("Cycle number must be positive")
    if session.scalar(select(CultivationCycle).where(CultivationCycle.number == number)) is not None:
        raise Conflict(f"Cycle {number} already exists")
    state = str(payload.get("state", "active"))
    if state not in CYCLE_STATES:
        raise ValidationProblem(f"Unknown state: {state}")
    cycle = CultivationCycle(
        id=_new_id("cyc"), number=number, name=str(payload.get("name", f"Cycle {to_roman(number)}"))[:120],
        length_days=int(payload.get("length_days", 100)),
        start_date=_parse_cycle_date(payload.get("start_date"), field="start_date"),
        snapshot_day=payload.get("snapshot_day"), snapshot_note=str(payload.get("snapshot_note", ""))[:2000],
        state=state, notes=str(payload.get("notes", ""))[:4000],
        created_at=now_iso(), updated_at=now_iso())
    if cycle.length_days < 1 or cycle.length_days > 3650:
        raise ValidationProblem("length_days must be between 1 and 3650")
    session.add(cycle)
    session.flush()
    focus = list(payload.get("focus_goal_ids", []) or [])[:50]
    if focus:
        set_cycle_focus(session, cycle.id, focus)
    _record_event(session, goal_id=None, event_type="cycle_created",
                  note=f"Cycle {number} '{cycle.name}' created.")
    return cycle


def update_cycle(session: Session, cycle_id: str, payload: dict[str, Any]) -> CultivationCycle:
    cycle = get_cycle(session, cycle_id)
    if "name" in payload and payload["name"] is not None:
        cycle.name = str(payload["name"])[:120]
    if "length_days" in payload and payload["length_days"] is not None:
        length = int(payload["length_days"])
        if length < 1 or length > 3650:
            raise ValidationProblem("length_days must be between 1 and 3650")
        cycle.length_days = length
    if "start_date" in payload:
        cycle.start_date = _parse_cycle_date(payload["start_date"], field="start_date")
    if "snapshot_day" in payload:
        snapshot = payload["snapshot_day"]
        cycle.snapshot_day = None if snapshot is None else int(snapshot)
    if "snapshot_note" in payload and payload["snapshot_note"] is not None:
        cycle.snapshot_note = str(payload["snapshot_note"])[:2000]
    if "notes" in payload and payload["notes"] is not None:
        cycle.notes = str(payload["notes"])[:4000]
    if "state" in payload and payload["state"] is not None:
        if str(payload["state"]) not in CYCLE_STATES:
            raise ValidationProblem("Unknown state")
        cycle.state = str(payload["state"])
    cycle.updated_at = now_iso()
    session.flush()
    return cycle


def set_cycle_focus(session: Session, cycle_id: str, goal_ids: list[str]) -> None:
    cycle = get_cycle(session, cycle_id)
    for goal_id in goal_ids[:50]:
        if session.get(CultivationGoal, goal_id) is None:
            raise NotFound(f"Goal not found: {goal_id}")
    existing = {row.goal_id for row in session.scalars(
        select(CultivationCycleGoal).where(CultivationCycleGoal.cycle_id == cycle_id)).all()}
    wanted = set(goal_ids[:50])
    for goal_id in sorted(wanted - existing):
        session.add(CultivationCycleGoal(cycle_id=cycle_id, goal_id=goal_id))
    for goal_id in sorted(existing - wanted):
        link = session.get(CultivationCycleGoal, (cycle_id, goal_id))
        if link is not None:
            session.delete(link)
    cycle.updated_at = now_iso()
    session.flush()
    _record_event(session, goal_id=None, event_type="cycle_focus",
                  note=f"Cycle {cycle.number} focus goals: {', '.join(sorted(wanted)) or 'none'}.")


def rollover_cycle(session: Session, cycle_id: str) -> CultivationCycle:
    """Explicitly complete a cycle and open the next one. Nothing automatic."""
    cycle = get_cycle(session, cycle_id)
    if cycle.state != "active":
        raise Conflict("Only an active cycle can be rolled over")
    cycle.state = "completed"
    cycle.updated_at = now_iso()
    session.flush()
    _record_event(session, goal_id=None, event_type="cycle_completed",
                  note=f"Cycle {cycle.number} completed.")
    focus = [row.goal_id for row in session.scalars(
        select(CultivationCycleGoal).where(CultivationCycleGoal.cycle_id == cycle_id)).all()]
    nxt = create_cycle(session, {"number": cycle.number + 1, "length_days": cycle.length_days,
                                 "focus_goal_ids": focus,
                                 "snapshot_note": f"Opened by rollover from cycle {cycle.number}."})
    return nxt


def cycle_day(session: Session, cycle: CultivationCycle) -> dict[str, Any]:
    from zoneinfo import ZoneInfo
    if cycle.start_date:
        start = datetime.strptime(cycle.start_date, "%Y-%m-%d").date()
        today = datetime.now(ZoneInfo(DUBLIN_TZ)).date()
        day = (today - start).days + 1
        return {"day": day, "mode": "calculated", "length_days": cycle.length_days,
                "past_length": day > cycle.length_days,
                "label": f"Cycle {to_roman(cycle.number)} — Day {day} / {cycle.length_days}"}
    if cycle.snapshot_day is not None:
        return {"day": int(cycle.snapshot_day), "mode": "snapshot",
                "length_days": cycle.length_days, "past_length": False,
                "label": (f"Cycle {to_roman(cycle.number)} — Day {cycle.snapshot_day} / "
                          f"{cycle.length_days} (reported; start date not set)")}
    return {"day": None, "mode": "unknown", "length_days": cycle.length_days,
            "past_length": False,
            "label": f"Cycle {to_roman(cycle.number)} — day unknown (no start date or snapshot)"}


def cycle_focus_goals(session: Session, cycle_id: str) -> list[CultivationGoal]:
    get_cycle(session, cycle_id)
    return list(session.scalars(select(CultivationGoal).join(
        CultivationCycleGoal, CultivationCycleGoal.goal_id == CultivationGoal.id).where(
        CultivationCycleGoal.cycle_id == cycle_id).order_by(CultivationGoal.name)).all())


def cycle_progress(session: Session, cycle: CultivationCycle) -> dict[str, Any]:
    """Completions attributed by event/publication dates, never scan timestamps.

    Without a start date there is no window to attribute to: totals are shown,
    windowed counts stay null rather than manufactured.
    """
    window: dict[str, str] | None = None
    if cycle.start_date:
        from zoneinfo import ZoneInfo
        start = datetime.strptime(cycle.start_date, "%Y-%m-%d").date()
        end = start + timedelta(days=cycle.length_days)
        today = datetime.now(ZoneInfo(DUBLIN_TZ)).date()
        window = {"from": start.isoformat(), "to": min(end, today).isoformat()}
    focus = []
    for goal in cycle_focus_goals(session, cycle.id):
        current = goal_progress(session, goal)["current"]
        completions: int | None = None
        started: int | None = None
        if window is not None:
            rows = session.scalars(select(CultivationEvent).where(
                CultivationEvent.goal_id == goal.id,
                CultivationEvent.event_type == "completed")).all()
            completions = 0
            for event in rows:
                stamp = (event.occurred_at or event.created_at or "")[:10]
                if window["from"] <= stamp <= window["to"]:
                    completions += 1
            # "Established" uses first-evidence dates, never scan timestamps:
            # an old repository discovered today must not count as new.
            started = 0
            for membership, item in session.execute(
                    select(CultivationMembership, CultivationItem).join(
                        CultivationItem, CultivationItem.id == CultivationMembership.item_id).where(
                        CultivationMembership.goal_id == goal.id)).all():
                evidence = dict(membership.quality_evidence or {})
                first_seen = str(evidence.get("first_evidence_ts") or membership.created_at or "")[:10]
                if window["from"] <= first_seen <= window["to"]:
                    started += 1
        focus.append({"goal_id": goal.id, "goal_name": goal.name,
                      "completions_in_window": completions, "started_in_window": started,
                      "current": current})
    return {"window": window, "focus": focus}


def cycle_read(session: Session, cycle: CultivationCycle) -> dict[str, Any]:
    return {"id": cycle.id, "number": cycle.number, "name": cycle.name,
            "length_days": cycle.length_days, "start_date": cycle.start_date,
            "snapshot_day": cycle.snapshot_day, "snapshot_note": cycle.snapshot_note,
            "state": cycle.state, "notes": cycle.notes,
            "created_at": cycle.created_at, "updated_at": cycle.updated_at,
            "day": cycle_day(session, cycle),
            "focus_goal_ids": [goal.id for goal in cycle_focus_goals(session, cycle.id)],
            "progress": cycle_progress(session, cycle)}
