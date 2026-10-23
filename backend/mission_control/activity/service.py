"""Activity recording with stable provenance and deduplication."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.models import ActivityEvent, Application, Project
from mission_control.persistence.db import now_iso

EVENT_TYPES = {
    "user_note",
    "user_decision",
    "workspace_focus",
    "checkpoint",
    "task_created",
    "task_updated",
    "recommendation_created",
    "recommendation_reviewed",
    "application_launch",
    "application_stopped",
    "application_launch_failed",
    "application_health",
    "repository_opened",
    "git_observation",
    "adapter_refresh",
    "adapter_available",
    "adapter_unavailable",
    "adapter_observation",
    "discovery_scan",
    "briefing_generated",
    "system",
}


def record_activity(
    session: Session,
    *,
    event_type: str,
    title: str,
    detail: str = "",
    project_id: str | None = None,
    application_id: str | None = None,
    process_id: str | None = None,
    source: str = "mission-control",
    source_id: str | None = None,
    evidence_ref: str | None = None,
    provenance: str = "user",
    occurred_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> ActivityEvent:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown activity type: {event_type}")
    if dedupe_key:
        existing = session.scalar(select(ActivityEvent).where(ActivityEvent.dedupe_key == dedupe_key))
        if existing:
            return existing
    timestamp = occurred_at or now_iso()
    event = ActivityEvent(
        id=f"evt-{uuid.uuid4().hex[:16]}",
        type=event_type,
        title=title,
        detail=detail,
        project_id=project_id,
        application_id=application_id,
        process_id=process_id,
        source=source,
        source_id=source_id,
        evidence_ref=evidence_ref,
        provenance=provenance,
        occurred_at=timestamp,
        observed_at=now_iso(),
        metadata_json=metadata or {},
        dedupe_key=dedupe_key,
    )
    session.add(event)
    if project_id:
        project = session.get(Project, project_id)
        if project:
            project.last_activity_at = timestamp
            project.updated_at = now_iso()
    if application_id:
        app = session.get(Application, application_id)
        if app:
            # Application.last_activity_at is intentionally not used: operational
            # health is separate from substantive work.
            pass
    session.flush()
    return event
