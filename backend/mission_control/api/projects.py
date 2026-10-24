"""Projects, books, checkpoints, tasks, decisions and activity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import NotFound
from mission_control.models import ActivityEvent, Outcome, Project
from mission_control.projects.service import (
    add_note,
    create_book,
    create_checkpoint,
    create_decision,
    create_project,
    create_task,
    current_focus,
    get_book_read,
    get_decision_read,
    get_recommendation_read,
    get_task_read,
    list_activity,
    list_books,
    list_checkpoints,
    list_decisions,
    list_projects,
    list_recommendations,
    list_tasks,
    project_detail,
    project_read,
    reorder_books,
    reorder_projects,
    review_recommendation,
    set_project_focus,
    update_book,
    update_project,
    update_task,
)
from mission_control.schemas import (
    ActivityNoteCreate,
    ActivityRead,
    BookCreate,
    BookRead,
    BookUpdate,
    CheckpointCreate,
    CheckpointRead,
    DecisionCreate,
    DecisionRead,
    IntegrationRecordRead,
    OkResponse,
    OutcomeRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    ProjectUpdate,
    RecommendationRead,
    ReorderRequest,
    ResumeRead,
    ReviewUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects", response_model=list[ProjectRead])
def get_projects(
    session: Session = Depends(get_session),
    search: str | None = None,
    kind: str | None = None,
    pinned: bool | None = None,
    include_archived: bool = False,
) -> list[ProjectRead]:
    projects = list_projects(session, include_archived=include_archived)
    if kind:
        projects = [project for project in projects if project.kind == kind]
    if pinned is not None:
        projects = [project for project in projects if project.pinned == pinned]
    if search:
        needle = search.casefold()
        projects = [
            project
            for project in projects
            if needle in project.name.casefold() or needle in project.description.casefold()
        ]
    return projects


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def add_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectRead:
    project = create_project(session, payload)
    session.flush()
    return project_read(session, project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProjectDetail:
    from mission_control.adapters.service import AdapterService

    return project_detail(
        session,
        project_id,
        AdapterService(request.app.state.database, request.app.state.settings),
    )


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def patch_project(
    project_id: str, payload: ProjectUpdate, session: Session = Depends(get_session)
) -> ProjectRead:
    project = update_project(session, project_id, payload)
    session.flush()
    return project_read(session, project)


@router.post("/projects/reorder", response_model=OkResponse)
def reorder_projects_route(
    payload: ReorderRequest, session: Session = Depends(get_session)
) -> OkResponse:
    reorder_projects(session, payload.ids)
    return OkResponse()


@router.post("/projects/{project_id}/focus", response_model=ProjectRead)
def focus_project(project_id: str, session: Session = Depends(get_session)) -> ProjectRead:
    project = set_project_focus(session, project_id)
    session.flush()
    return project_read(session, project)


@router.post("/projects/{project_id}/open-repository", response_model=OkResponse)
def open_project_repository(
    project_id: str, session: Session = Depends(get_session)
) -> OkResponse:
    from mission_control.activity.service import record_activity
    from mission_control.core.editor import open_path_with_editor
    from mission_control.models import ProjectRepository, Repository

    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    repository = session.scalar(
        select(Repository)
        .join(ProjectRepository, ProjectRepository.repository_id == Repository.id)
        .where(ProjectRepository.project_id == project_id)
        .order_by(Repository.name)
    )
    if repository is None:
        raise NotFound("This project has no associated repository")
    command = open_path_with_editor(session, repository.path)
    record_activity(
        session,
        event_type="repository_opened",
        title=f"Opened {project.name} repository",
        detail=repository.path,
        project_id=project_id,
        source="mission-control",
        provenance="verified_observation",
    )
    return OkResponse(detail=f"Opened {repository.path} with {command}")


@router.get(
    "/projects/{project_id}/integration-context",
    response_model=list[IntegrationRecordRead],
)
def project_integration_context(
    project_id: str, session: Session = Depends(get_session)
) -> list[IntegrationRecordRead]:
    from mission_control.integrations.store import list_resources

    if session.get(Project, project_id) is None:
        raise NotFound("Project not found")
    return list_resources(session, project_id=project_id, limit=100)


@router.get("/resume", response_model=ResumeRead)
def resume(session: Session = Depends(get_session)) -> ResumeRead:
    project = current_focus(session)
    checkpoint = None
    if project:
        checkpoint = list_checkpoints(session, project_id=project.id, limit=1)
    recent_ids: list[str] = []
    recent: list[dict[str, object]] = []
    for event in session.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.type.in_(["workspace_focus", "checkpoint"]))
        .order_by(desc(ActivityEvent.occurred_at))
        .limit(30)
    ).all():
        if event.project_id and event.project_id not in recent_ids:
            recent_ids.append(event.project_id)
            recent_project = session.get(Project, event.project_id)
            if recent_project:
                recent.append(
                    {
                        "id": recent_project.id,
                        "name": recent_project.name,
                        "last_event_at": event.occurred_at,
                    }
                )
        if len(recent) >= 5:
            break
    return ResumeRead(
        project=project_read(session, project) if project else None,
        checkpoint=checkpoint[0] if checkpoint else None,
        recent_projects=recent,
    )


# --------------------------------------------------------------------- books
@router.get("/books", response_model=list[BookRead])
def get_books(session: Session = Depends(get_session)) -> list[BookRead]:
    return list_books(session)


@router.post("/books", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def add_book(payload: BookCreate, session: Session = Depends(get_session)) -> BookRead:
    book = create_book(session, payload)
    session.flush()
    return get_book_read(session, book.id)


@router.get("/books/{book_id}", response_model=BookRead)
def get_book_route(book_id: str, session: Session = Depends(get_session)) -> BookRead:
    return get_book_read(session, book_id)


@router.patch("/books/{book_id}", response_model=BookRead)
def patch_book(
    book_id: str, payload: BookUpdate, session: Session = Depends(get_session)
) -> BookRead:
    update_book(session, book_id, payload)
    session.flush()
    return get_book_read(session, book_id)


@router.post("/books/reorder", response_model=OkResponse)
def reorder_books_route(
    payload: ReorderRequest, session: Session = Depends(get_session)
) -> OkResponse:
    reorder_books(session, payload.ids)
    return OkResponse()


# --------------------------------------------------------------- checkpoints
@router.get("/checkpoints", response_model=list[CheckpointRead])
def get_checkpoints(
    session: Session = Depends(get_session),
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CheckpointRead]:
    return list_checkpoints(session, project_id=project_id, limit=limit)


@router.post("/checkpoints", response_model=CheckpointRead, status_code=status.HTTP_201_CREATED)
def add_checkpoint(
    payload: CheckpointCreate, session: Session = Depends(get_session)
) -> CheckpointRead:
    create_checkpoint(session, payload)
    session.flush()
    return list_checkpoints(session, project_id=payload.project_id, limit=1)[0]


# --------------------------------------------------------------------- tasks
@router.get("/tasks", response_model=list[TaskRead])
def get_tasks(
    session: Session = Depends(get_session),
    project_id: str | None = None,
    task_status: str | None = Query(default=None, alias="status"),
) -> list[TaskRead]:
    return list_tasks(session, project_id=project_id, status=task_status)


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def add_task(payload: TaskCreate, session: Session = Depends(get_session)) -> TaskRead:
    task = create_task(session, payload)
    session.flush()
    return get_task_read(session, task.id)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def patch_task(
    task_id: str, payload: TaskUpdate, session: Session = Depends(get_session)
) -> TaskRead:
    task = update_task(session, task_id, payload)
    session.flush()
    return get_task_read(session, task.id)


# ----------------------------------------------------------------- decisions
@router.get("/decisions", response_model=list[DecisionRead])
def get_decisions(
    session: Session = Depends(get_session), project_id: str | None = None
) -> list[DecisionRead]:
    return list_decisions(session, project_id=project_id)


@router.post("/decisions", response_model=DecisionRead, status_code=status.HTTP_201_CREATED)
def add_decision(
    payload: DecisionCreate, session: Session = Depends(get_session)
) -> DecisionRead:
    decision = create_decision(session, payload)
    session.flush()
    return get_decision_read(session, decision.id)


# ----------------------------------------------------------- recommendations
@router.get("/recommendations", response_model=list[RecommendationRead])
def get_recommendations(
    session: Session = Depends(get_session),
    project_id: str | None = None,
    state: str | None = None,
) -> list[RecommendationRead]:
    return list_recommendations(session, project_id=project_id, state=state)


@router.patch("/recommendations/{recommendation_id}", response_model=RecommendationRead)
def review_recommendation_route(
    recommendation_id: str,
    payload: ReviewUpdate,
    session: Session = Depends(get_session),
) -> RecommendationRead:
    rec = review_recommendation(session, recommendation_id, payload)
    session.flush()
    return get_recommendation_read(session, rec.id)


# ------------------------------------------------------------------ activity
@router.get("/activity", response_model=list[ActivityRead])
def get_activity(
    session: Session = Depends(get_session),
    project_id: str | None = None,
    event_type: str | None = Query(default=None, alias="type"),
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ActivityRead]:
    return list_activity(
        session,
        project_id=project_id,
        event_type=event_type,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@router.post("/activity/notes", response_model=ActivityRead, status_code=201)
def add_activity_note(
    payload: ActivityNoteCreate, session: Session = Depends(get_session)
) -> ActivityRead:
    event = add_note(
        session,
        project_id=payload.project_id,
        title=payload.title,
        detail=payload.detail,
        evidence_ref=payload.evidence_ref,
    )
    session.flush()
    return event


# ------------------------------------------------------------------ outcomes
@router.get("/outcomes", response_model=list[OutcomeRead])
def get_outcomes(session: Session = Depends(get_session)) -> list[OutcomeRead]:
    outcomes = session.scalars(select(Outcome).order_by(Outcome.name)).all()
    return [
        OutcomeRead(
            id=item.id,
            name=item.name,
            description=item.description,
            status=item.status,
            url=item.url,
            notes=item.notes,
        )
        for item in outcomes
    ]
