"""The home dashboard, assembled from persisted data."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.adapters.service import AdapterService
from mission_control.api.deps import get_session
from mission_control.briefing.service import latest_briefing
from mission_control.models import (
    ActivityEvent,
    Application,
    Outcome,
    Project,
    Repository,
    Task,
)
from mission_control.persistence.db import now_iso
from mission_control.projects.service import (
    activity_read,
    current_focus,
    list_books,
    list_checkpoints,
    list_recommendations,
    list_tasks,
    project_read,
)
from mission_control.registry.service import build_application_read
from mission_control.schemas import DashboardRead, OutcomeRead

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    session: Session = Depends(get_session), request: Request = None  # type: ignore[assignment]
) -> DashboardRead:
    manager = request.app.state.process_manager
    manager.reconcile_live(session)
    focus = current_focus(session)
    # Resume is the most recent saved checkpoint, independently of the chosen
    # focus. Focus and last work are different concepts.
    checkpoints = list_checkpoints(session, limit=1)
    checkpoint = checkpoints[0] if checkpoints else None
    applications = [
        build_application_read(session, app, manager)
        for app in session.scalars(
            select(Application)
            .where(Application.archived.is_(False))
            .order_by(Application.display_order, Application.name)
        ).all()
    ]
    activity = [
        activity_read(session, item)
        for item in session.scalars(
            select(ActivityEvent).order_by(desc(ActivityEvent.occurred_at)).limit(12)
        ).all()
    ]
    outcomes = [
        OutcomeRead(
            id=item.id,
            name=item.name,
            description=item.description,
            status=item.status,
            url=item.url,
            notes=item.notes,
        )
        for item in session.scalars(select(Outcome).order_by(Outcome.name)).all()
    ]
    open_tasks = list_tasks(session, status="open")
    pending_recommendations = list_recommendations(session, state="pending")
    adapter_service = AdapterService(request.app.state.database, request.app.state.settings)
    adapters = adapter_service.list_adapters()
    books = list_books(session)
    stats = {
        "priority_books": sum(1 for book in books if book.priority is not None),
        "applications": len(applications),
        "running_applications": sum(1 for app in applications if app.status.state == "running"),
        "pending_reviews": len(pending_recommendations),
        "open_tasks": int(
            session.scalar(
                select(func.count())
                .select_from(Task)
                .where(Task.status.in_(["open", "in_progress", "blocked"]))
            )
            or 0
        ),
        "repositories_discovered": int(
            session.scalar(select(func.count()).select_from(Repository)) or 0
        ),
        "adapters_available": sum(1 for adapter in adapters if adapter.available),
        "priority_projects": int(
            session.scalar(
                select(func.count())
                .select_from(Project)
                .where(Project.pinned.is_(True), Project.archived.is_(False))
            )
            or 0
        ),
    }
    return DashboardRead(
        generated_at=now_iso(),
        date=datetime.now().astimezone().date().isoformat(),
        focus=project_read(session, focus) if focus else None,
        checkpoint=checkpoint,
        books=books,
        applications=applications,
        activity=activity,
        outcomes=outcomes,
        tasks=open_tasks[:10],
        recommendations=pending_recommendations[:10],
        adapters=adapters,
        briefing=latest_briefing(session),
        stats=stats,
    )
