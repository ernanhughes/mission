"""Persistence for normalised integration resources, decisions and inbox."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.adapters.base import ResourceSeed
from mission_control.models import (
    Application,
    Decision,
    IntegrationDecision,
    IntegrationRecord,
    Project,
    Repository,
    Task,
    WorkCheckpoint,
)
from mission_control.persistence.db import now_iso
from mission_control.schemas import (
    InboxItemRead,
    IntegrationDecisionRead,
    IntegrationRecordRead,
    SearchResultRead,
)

DECISION_OPTIONS: dict[str, list[str]] = {
    "next": ["shortlist", "accept", "defer", "reject", "investigate"],
    "work": ["shortlist", "defer", "reject", "investigate"],
    "cocoder": ["investigate", "acknowledge", "defer"],
}

_INTEGRATION_ROUTES = {"next": "next", "work": "work", "cocoder": "cocoder"}


def _age_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed).total_seconds()
    except ValueError:
        return None


def resource_id(application_id: str, resource_type: str, external_id: str) -> str:
    digest = hashlib.sha1(
        f"{application_id}\x1f{resource_type}\x1f{external_id}".encode("utf-8")
    ).hexdigest()[:20]
    return f"res-{digest}"


def _search_text(resource: ResourceSeed) -> str:
    try:
        payload = json.dumps(resource.data, ensure_ascii=False)
    except (TypeError, ValueError):
        payload = ""
    return " ".join(
        [resource.title, resource.summary, resource.state, resource.resource_type, payload]
    )[:30_000]


def upsert_resources(session: Session, application_id: str, resources: list[ResourceSeed]) -> int:
    # Mark the previous refresh as historical but retain it for review/search.
    for existing in session.scalars(
        select(IntegrationRecord).where(IntegrationRecord.application_id == application_id)
    ).all():
        existing.current = False
    count = 0
    for resource in resources:
        rid = resource_id(application_id, resource.resource_type, resource.external_id)
        record = session.get(IntegrationRecord, rid)
        if record is None:
            record = IntegrationRecord(
                id=rid,
                application_id=application_id,
                resource_type=resource.resource_type,
                external_id=resource.external_id,
                project_id=None,
                created_at=now_iso(),
            )
            session.add(record)
        record.title = resource.title[:1000]
        record.summary = resource.summary
        record.state = resource.state[:200]
        record.source_version = resource.source_version
        record.source_timestamp = resource.source_timestamp
        record.observed_at = now_iso()
        record.stale_after_seconds = max(30, resource.stale_after_seconds)
        record.evidence = resource.evidence[:30]
        record.data = resource.data
        record.search_text = _search_text(resource)
        record.current = True
        record.updated_at = now_iso()
        count += 1
    session.flush()
    return count


def latest_decision(
    session: Session, application_id: str, resource_type: str, external_id: str
) -> IntegrationDecision | None:
    return session.scalar(
        select(IntegrationDecision)
        .where(
            IntegrationDecision.application_id == application_id,
            IntegrationDecision.resource_type == resource_type,
            IntegrationDecision.external_id == external_id,
        )
        .order_by(desc(IntegrationDecision.decided_at))
        .limit(1)
    )


def decision_read(decision: IntegrationDecision) -> IntegrationDecisionRead:
    return IntegrationDecisionRead(
        id=decision.id,
        application_id=decision.application_id,
        resource_type=decision.resource_type,
        external_id=decision.external_id,
        decision=decision.decision,
        reason=decision.reason,
        sync_state=decision.sync_state,
        source_decision_id=decision.source_decision_id,
        decided_at=decision.decided_at,
        created_at=decision.created_at,
    )


def resource_read(
    session: Session, record: IntegrationRecord, *, include_data: bool = True
) -> IntegrationRecordRead:
    application = session.get(Application, record.application_id)
    project = session.get(Project, record.project_id) if record.project_id else None
    decision = latest_decision(
        session, record.application_id, record.resource_type, record.external_id
    )
    age = _age_seconds(record.observed_at)
    stale = age is None or age > record.stale_after_seconds
    data = record.data if include_data else _preview_data(record.data)
    return IntegrationRecordRead(
        id=record.id,
        application_id=record.application_id,
        application_name=application.name if application else None,
        resource_type=record.resource_type,
        external_id=record.external_id,
        title=record.title,
        summary=record.summary,
        state=record.state,
        project_id=record.project_id,
        project_name=project.name if project else None,
        source_version=record.source_version,
        source_timestamp=record.source_timestamp,
        observed_at=record.observed_at,
        stale_after_seconds=record.stale_after_seconds,
        stale=stale,
        current=record.current,
        evidence=record.evidence,
        data=data,
        local_decision=decision_read(decision) if decision else None,
        decision_options=DECISION_OPTIONS.get(record.application_id, []),
    )


def _preview_data(data: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "severity",
        "confidence",
        "qualification",
        "qualification_state",
        "queue_type",
        "track",
        "buyer",
        "location",
        "remote",
        "scores",
        "source_mode",
        "repository_path",
        "base",
        "head",
        "finding_count",
        "changed_file_count",
    )
    return {key: data[key] for key in keys if key in data}


def list_resources(
    session: Session,
    *,
    application_id: str | None = None,
    resource_type: str | None = None,
    project_id: str | None = None,
    query: str | None = None,
    current: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[IntegrationRecordRead]:
    statement = select(IntegrationRecord).order_by(
        desc(IntegrationRecord.current),
        desc(IntegrationRecord.source_timestamp),
        desc(IntegrationRecord.observed_at),
    )
    if application_id:
        statement = statement.where(IntegrationRecord.application_id == application_id)
    if resource_type:
        statement = statement.where(IntegrationRecord.resource_type == resource_type)
    if project_id:
        statement = statement.where(IntegrationRecord.project_id == project_id)
    if current:
        statement = statement.where(IntegrationRecord.current.is_(True))
    if query:
        needle = f"%{query.casefold()}%"
        statement = statement.where(IntegrationRecord.search_text.ilike(needle))
    rows = session.scalars(statement.limit(max(1, min(limit, 500))).offset(max(offset, 0))).all()
    return [resource_read(session, row, include_data=False) for row in rows]


def associate_project(
    session: Session, record: IntegrationRecord, project_id: str | None
) -> IntegrationRecordRead:
    if project_id and session.get(Project, project_id) is None:
        raise ValueError("Project does not exist")
    record.project_id = project_id
    record.updated_at = now_iso()
    session.flush()
    return resource_read(session, record)


def record_decision(
    session: Session,
    record: IntegrationRecord,
    decision_value: str,
    reason: str,
) -> IntegrationDecision:
    options = DECISION_OPTIONS.get(record.application_id, [])
    if decision_value not in options:
        raise ValueError(
            f"Decision '{decision_value}' is not supported for {record.application_id}"
        )
    application = session.get(Application, record.application_id)
    existing = latest_decision(
        session, record.application_id, record.resource_type, record.external_id
    )
    decision = IntegrationDecision(
        id=f"idec-{uuid.uuid4().hex[:16]}",
        application_id=record.application_id,
        resource_type=record.resource_type,
        external_id=record.external_id,
        decision=decision_value,
        reason=reason,
        sync_state="local_only",
        source_decision_id=existing.id if existing else None,
        decided_at=now_iso(),
        created_at=now_iso(),
    )
    session.add(decision)
    source_status = {
        "reject": "rejected",
        "defer": "deferred",
        "accept": "accepted",
        "shortlist": "accepted",
        "investigate": "accepted",
        "acknowledge": "accepted",
    }.get(decision_value, "revised")
    session.add(
        Decision(
            id=f"dec-{uuid.uuid4().hex[:16]}",
            project_id=record.project_id,
            title=f"{application.name if application else record.application_id}: {decision_value} — {record.title[:220]}",
            rationale=reason or f"Local Mission Control decision for {record.external_id}.",
            status=source_status,
            source="user",
            decided_at=decision.decided_at,
            created_at=now_iso(),
        )
    )
    record_activity(
        session,
        event_type="recommendation_reviewed",
        title=f"{application.name if application else record.application_id}: {decision_value}",
        detail=(
            f"{record.title[:500]}. Stored locally; the source application was not modified."
        ),
        project_id=record.project_id,
        application_id=record.application_id,
        source="mission-control",
        source_id=record.external_id,
        evidence_ref=record.evidence[0] if record.evidence else None,
        provenance="user",
        metadata={
            "decision": decision_value,
            "resource_type": record.resource_type,
            "sync_state": "local_only",
        },
    )
    session.flush()
    return decision


def decision_history(
    session: Session, application_id: str | None = None
) -> list[IntegrationDecisionRead]:
    statement = select(IntegrationDecision).order_by(desc(IntegrationDecision.decided_at)).limit(300)
    if application_id:
        statement = statement.where(IntegrationDecision.application_id == application_id)
    return [decision_read(row) for row in session.scalars(statement).all()]


def counts_by_type(session: Session, application_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in session.scalars(
        select(IntegrationRecord).where(
            IntegrationRecord.application_id == application_id,
            IntegrationRecord.current.is_(True),
        )
    ).all():
        counts[record.resource_type] = counts.get(record.resource_type, 0) + 1
    return counts


def _decision_map(session: Session) -> dict[tuple[str, str, str], IntegrationDecision]:
    decisions: dict[tuple[str, str, str], IntegrationDecision] = {}
    for decision in session.scalars(
        select(IntegrationDecision).order_by(desc(IntegrationDecision.decided_at))
    ).all():
        key = (decision.application_id, decision.resource_type, decision.external_id)
        decisions.setdefault(key, decision)
    return decisions


def inbox_items(
    session: Session,
    *,
    application_id: str | None = None,
    project_id: str | None = None,
    limit: int = 100,
) -> list[InboxItemRead]:
    applications = {
        app.id: app
        for app in session.scalars(select(Application)).all()
    }
    projects = {project.id: project for project in session.scalars(select(Project)).all()}
    decisions = _decision_map(session)
    items: list[InboxItemRead] = []

    def apply_filters(source_application: str, item_project_id: str | None) -> bool:
        if application_id and source_application != application_id:
            return False
        if project_id and item_project_id != project_id:
            return False
        return True

    records = session.scalars(
        select(IntegrationRecord)
        .where(IntegrationRecord.current.is_(True))
        .order_by(desc(IntegrationRecord.source_timestamp))
        .limit(1200)
    ).all()
    per_source: dict[str, int] = {}
    for record in records:
        if record.application_id not in _INTEGRATION_ROUTES:
            continue
        key = (record.application_id, record.resource_type, record.external_id)
        if key in decisions:
            continue
        if not apply_filters(record.application_id, record.project_id):
            continue
        if per_source.get(record.application_id, 0) >= 15:
            continue
        item_type = record.resource_type
        priority = 50
        actions = DECISION_OPTIONS.get(record.application_id, ["open"])
        if record.application_id == "next" and item_type == "next_opportunity":
            if record.state not in {"NEW", "INVESTIGATE"}:
                continue
            queue = str((record.data or {}).get("queue_type") or "")
            priority = 92 if queue == "validated" else 70
            item_type = "next_recommendation" if queue == "validated" else "next_candidate"
        elif record.application_id == "work" and item_type == "work_opportunity":
            qualification = (record.data or {}).get("qualification") or {}
            if not qualification.get("qualified"):
                continue
            priority = 95
            item_type = "work_opportunity"
        elif record.application_id == "cocoder" and item_type == "cocoder_finding":
            severity = str((record.data or {}).get("severity") or "").lower()
            if severity not in {"high", "medium"}:
                continue
            priority = 90 if severity == "high" else 62
            item_type = "cocoder_finding"
        else:
            continue
        app = applications.get(record.application_id)
        project = projects.get(record.project_id) if record.project_id else None
        per_source[record.application_id] = per_source.get(record.application_id, 0) + 1
        items.append(
            InboxItemRead(
                id=f"inbox-{record.id}",
                source_application=record.application_id,
                source_name=app.name if app else record.application_id,
                item_type=item_type,
                title=record.title,
                summary=record.summary[:1200],
                project_id=record.project_id,
                project_name=project.name if project else None,
                priority=priority,
                priority_label=(
                    "High" if priority >= 90 else "Medium" if priority >= 60 else "Normal"
                ),
                evidence=record.evidence[:8],
                observed_at=record.observed_at,
                state=record.state,
                actions=actions,
                target_path=f"/{_INTEGRATION_ROUTES[record.application_id]}?record={record.id}",
                resource_id=record.id,
                decision_state="pending",
            )
        )

    for task in session.scalars(
        select(Task)
        .where(Task.status.in_(["open", "in_progress", "blocked"]))
        .order_by(Task.priority, desc(Task.created_at))
        .limit(30)
    ).all():
        if not apply_filters("mission-control", task.project_id):
            continue
        project = projects.get(task.project_id) if task.project_id else None
        items.append(
            InboxItemRead(
                id=f"inbox-task-{task.id}",
                source_application="mission-control",
                source_name="Mission Control",
                item_type="task",
                title=task.title,
                summary=task.description or f"Task status: {task.status}",
                project_id=task.project_id,
                project_name=project.name if project else None,
                priority=80,
                priority_label="Medium",
                evidence=[],
                observed_at=task.updated_at,
                state=task.status,
                actions=["open"],
                target_path=f"/projects/{task.project_id}" if task.project_id else "/activity",
                resource_id=None,
                decision_state=task.status,
            )
        )
    return sorted(items, key=lambda item: (item.priority, item.observed_at), reverse=True)[:limit]


def search_all(session: Session, query: str, limit: int = 50) -> list[SearchResultRead]:
    needle = f"%{query.casefold()}%"
    results: list[SearchResultRead] = []
    app_names = {app.id: app.name for app in session.scalars(select(Application)).all()}
    for record in session.scalars(
        select(IntegrationRecord)
        .where(
            IntegrationRecord.current.is_(True),
            IntegrationRecord.search_text.ilike(needle),
        )
        .order_by(desc(IntegrationRecord.source_timestamp))
        .limit(limit)
    ).all():
        app_name = app_names.get(record.application_id, record.application_id)
        results.append(
            SearchResultRead(
                id=record.id,
                source=app_name,
                source_id=record.external_id,
                title=record.title,
                subtitle=record.summary[:300],
                project_id=record.project_id,
                target_path=f"/{_INTEGRATION_ROUTES.get(record.application_id, 'inbox')}?record={record.id}",
                observed_at=record.source_timestamp or record.observed_at,
            )
        )
    for project in session.scalars(
        select(Project)
        .where(or_(Project.name.ilike(needle), Project.description.ilike(needle)))
        .limit(10)
    ).all():
        results.append(
            SearchResultRead(
                id=project.id,
                source="Mission Control",
                source_id=project.id,
                title=project.name,
                subtitle=project.description[:300],
                project_id=project.id,
                target_path=f"/projects/{project.id}",
                observed_at=project.updated_at,
            )
        )
    for repository in session.scalars(
        select(Repository)
        .where(or_(Repository.name.ilike(needle), Repository.path.ilike(needle)))
        .limit(10)
    ).all():
        results.append(
            SearchResultRead(
                id=repository.id,
                source="Repository",
                source_id=repository.id,
                title=repository.name,
                subtitle=repository.path,
                project_id=None,
                target_path="/applications",
                observed_at=repository.last_observed_at,
            )
        )
    for task in session.scalars(
        select(Task).where(Task.title.ilike(needle)).limit(10)
    ).all():
        results.append(
            SearchResultRead(
                id=task.id,
                source="Task",
                source_id=task.id,
                title=task.title,
                subtitle=task.description[:300],
                project_id=task.project_id,
                target_path=f"/projects/{task.project_id}" if task.project_id else "/activity",
                observed_at=task.updated_at,
            )
        )
    for checkpoint in session.scalars(
        select(WorkCheckpoint).where(WorkCheckpoint.summary.ilike(needle)).limit(10)
    ).all():
        results.append(
            SearchResultRead(
                id=checkpoint.id,
                source="Checkpoint",
                source_id=checkpoint.id,
                title=checkpoint.summary[:200],
                subtitle=checkpoint.next_action,
                project_id=checkpoint.project_id,
                target_path=f"/projects/{checkpoint.project_id}",
                observed_at=checkpoint.created_at,
            )
        )
    for decision in session.scalars(
        select(Decision).where(Decision.title.ilike(needle)).limit(10)
    ).all():
        results.append(
            SearchResultRead(
                id=decision.id,
                source="Decision",
                source_id=decision.id,
                title=decision.title,
                subtitle=decision.rationale[:300],
                project_id=decision.project_id,
                target_path=f"/projects/{decision.project_id}" if decision.project_id else "/activity",
                observed_at=decision.decided_at,
            )
        )
    seen: set[str] = set()
    unique: list[SearchResultRead] = []
    for result in results:
        if result.id in seen:
            continue
        seen.add(result.id)
        unique.append(result)
    return unique[:limit]
