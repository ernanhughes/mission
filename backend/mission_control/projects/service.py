"""Project workspaces, books, checkpoints, tasks and decisions."""

from __future__ import annotations

import hashlib
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.adapters.service import AdapterService
from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.core.git_observe import observe_git
from mission_control.core.paths import require_existing_directory
from mission_control.models import (
    ActivityEvent,
    Application,
    Book,
    Decision,
    Outcome,
    Project,
    ProjectRelationship,
    ProjectRepository,
    Recommendation,
    Repository,
    Setting,
    Task,
    WorkCheckpoint,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.persistence.seed import repository_id
from mission_control.registry.service import editor_state
from mission_control.schemas import (
    ActionState,
    ActivityRead,
    BookCreate,
    BookRead,
    BookUpdate,
    CheckpointCreate,
    CheckpointRead,
    DecisionCreate,
    DecisionRead,
    OutcomeRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    ProjectUpdate,
    RecommendationRead,
    RepositoryRead,
    ReviewUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

SLUG = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    return SLUG.sub("-", value.strip().lower()).strip("-")[:64] or f"project-{uuid.uuid4().hex[:6]}"


def _repo_read(repo: Repository, role: str | None = None) -> RepositoryRead:
    return RepositoryRead(
        id=repo.id,
        name=repo.name,
        path=repo.path,
        classification=repo.classification,
        confidence=repo.confidence,
        evidence=repo.evidence,
        role=role,
        source_root=repo.source_root,
        is_git=repo.is_git,
        branch=repo.branch,
        commit_hash=repo.commit_hash,
        last_commit_at=repo.last_commit_at,
        dirty=repo.dirty,
        accessible=repo.accessible,
        candidate=repo.candidate,
        last_observed_at=repo.last_observed_at,
        notes=repo.notes,
    )


def _checkpoint_read(session: Session, checkpoint: WorkCheckpoint) -> CheckpointRead:
    project = session.get(Project, checkpoint.project_id)
    return CheckpointRead(
        id=checkpoint.id,
        project_id=checkpoint.project_id,
        project_name=project.name if project else None,
        summary=checkpoint.summary,
        last_completed=checkpoint.last_completed,
        next_action=checkpoint.next_action,
        blockers=checkpoint.blockers,
        evidence_refs=checkpoint.evidence_refs,
        milestone=checkpoint.milestone,
        source=checkpoint.source,
        created_at=checkpoint.created_at,
    )


def _latest_checkpoint(session: Session, project_id: str) -> WorkCheckpoint | None:
    return session.scalar(
        select(WorkCheckpoint)
        .where(WorkCheckpoint.project_id == project_id)
        .order_by(desc(WorkCheckpoint.created_at))
    )


def repository_action(session: Session, project_id: str) -> ActionState:
    repo = session.scalar(
        select(Repository)
        .join(ProjectRepository, ProjectRepository.repository_id == Repository.id)
        .where(ProjectRepository.project_id == project_id)
        .order_by(Repository.name)
    )
    if repo is None:
        return ActionState(enabled=False, reason="No repository is associated with this project.")
    if not Path(repo.path).is_dir():
        return ActionState(enabled=False, reason="The associated repository path is unavailable.")
    ok, reason = editor_state(session)
    return ActionState(enabled=ok, reason=reason)


def _book_read(session: Session, book: Book, project: Project) -> BookRead:
    checkpoint = _latest_checkpoint(session, book.project_id)
    return BookRead(
        id=book.id,
        project_id=book.project_id,
        project_name=project.name,
        title=book.title,
        status=book.status,  # type: ignore[arg-type]
        current_milestone=book.current_milestone,
        next_action=book.next_action,
        manuscript_paths=book.manuscript_paths,
        implementation_paths=book.implementation_paths,
        published_url=book.published_url,
        local_url=book.local_url,
        quality_review_state=book.quality_review_state,
        last_activity_at=book.last_activity_at,
        priority=project.priority,
        latest_checkpoint=_checkpoint_read(session, checkpoint) if checkpoint else None,
        repository_action=repository_action(session, book.project_id),
    )


def _task_read(session: Session, task: Task) -> TaskRead:
    project = session.get(Project, task.project_id) if task.project_id else None
    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        project_name=project.name if project else None,
        title=task.title,
        description=task.description,
        status=task.status,  # type: ignore[arg-type]
        priority=task.priority,
        source=task.source,
        due_at=task.due_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _decision_read(session: Session, decision: Decision) -> DecisionRead:
    project = session.get(Project, decision.project_id) if decision.project_id else None
    return DecisionRead(
        id=decision.id,
        project_id=decision.project_id,
        project_name=project.name if project else None,
        title=decision.title,
        rationale=decision.rationale,
        status=decision.status,
        source=decision.source,
        decided_at=decision.decided_at,
        created_at=decision.created_at,
    )


def _recommendation_read(session: Session, rec: Recommendation) -> RecommendationRead:
    project = session.get(Project, rec.project_id) if rec.project_id else None
    return RecommendationRead(
        id=rec.id,
        project_id=rec.project_id,
        project_name=project.name if project else None,
        title=rec.title,
        rationale=rec.rationale,
        evidence=rec.evidence,
        source_application=rec.source_application,
        source_ref=rec.source_ref,
        external_id=rec.external_id,
        provenance=rec.provenance,
        review_state=rec.review_state,  # type: ignore[arg-type]
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def activity_read(session: Session, event: ActivityEvent) -> ActivityRead:
    project = session.get(Project, event.project_id) if event.project_id else None
    application = session.get(Application, event.application_id) if event.application_id else None
    return ActivityRead(
        id=event.id,
        type=event.type,
        title=event.title,
        detail=event.detail,
        project_id=event.project_id,
        project_name=project.name if project else None,
        application_id=event.application_id,
        application_name=application.name if application else None,
        process_id=event.process_id,
        source=event.source,
        source_id=event.source_id,
        evidence_ref=event.evidence_ref,
        provenance=event.provenance,
        occurred_at=event.occurred_at,
        observed_at=event.observed_at,
        metadata=event.metadata_json,
    )


def project_read(session: Session, project: Project) -> ProjectRead:
    repo_rows = session.execute(
        select(Repository, ProjectRepository.role)
        .join(ProjectRepository, ProjectRepository.repository_id == Repository.id)
        .where(ProjectRepository.project_id == project.id)
        .order_by(ProjectRepository.role, Repository.name)
    ).all()
    book = session.scalar(select(Book).where(Book.project_id == project.id))
    outcome_rows = session.scalars(
        select(ProjectRelationship).where(
            ProjectRelationship.project_id == project.id,
            ProjectRelationship.target_type == "outcome",
        )
    ).all()
    outcomes = [
        OutcomeRead(
            id=outcome.id,
            name=outcome.name,
            description=outcome.description,
            status=outcome.status,
            url=outcome.url,
            notes=outcome.notes,
        )
        for relation in outcome_rows
        if (outcome := session.get(Outcome, relation.target_id)) is not None
    ]
    applications = [
        {"id": app.id, "name": app.name, "category": app.category}
        for app in session.scalars(select(Application).order_by(Application.display_order)).all()
        if project.id in (app.related_projects or [])
    ]
    checkpoint = _latest_checkpoint(session, project.id)
    open_tasks = int(
        session.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.project_id == project.id, Task.status.in_(["open", "in_progress", "blocked"]))
        )
        or 0
    )
    pending_recs = int(
        session.scalar(
            select(func.count())
            .select_from(Recommendation)
            .where(
                Recommendation.project_id == project.id,
                Recommendation.review_state == "pending",
            )
        )
        or 0
    )
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        kind=project.kind,  # type: ignore[arg-type]
        status=project.status,  # type: ignore[arg-type]
        priority=project.priority,
        pinned=project.pinned,
        archived=project.archived,
        display_order=project.display_order,
        current_milestone=project.current_milestone,
        next_action=project.next_action,
        notes=project.notes,
        last_activity_at=project.last_activity_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
        repositories=[_repo_read(repo, role) for repo, role in repo_rows],
        book=_book_read(session, book, project) if book else None,
        outcomes=outcomes,
        applications=applications,
        latest_checkpoint=_checkpoint_read(session, checkpoint) if checkpoint else None,
        open_task_count=open_tasks,
        pending_recommendation_count=pending_recs,
    )


def project_detail(session: Session, project_id: str, adapter_service: AdapterService) -> ProjectDetail:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    base = project_read(session, project)
    checkpoints = [
        _checkpoint_read(session, item)
        for item in session.scalars(
            select(WorkCheckpoint)
            .where(WorkCheckpoint.project_id == project_id)
            .order_by(desc(WorkCheckpoint.created_at))
            .limit(25)
        ).all()
    ]
    tasks = [
        _task_read(session, item)
        for item in session.scalars(
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.status, Task.priority, desc(Task.created_at))
            .limit(100)
        ).all()
    ]
    decisions = [
        _decision_read(session, item)
        for item in session.scalars(
            select(Decision)
            .where(Decision.project_id == project_id)
            .order_by(desc(Decision.decided_at))
            .limit(50)
        ).all()
    ]
    recommendations = [
        _recommendation_read(session, item)
        for item in session.scalars(
            select(Recommendation)
            .where(Recommendation.project_id == project_id)
            .order_by(desc(Recommendation.created_at))
            .limit(50)
        ).all()
    ]
    activity = [
        activity_read(session, item)
        for item in session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.project_id == project_id)
            .order_by(desc(ActivityEvent.occurred_at))
            .limit(40)
        ).all()
    ]
    return ProjectDetail(
        **base.model_dump(),
        repository_action=repository_action(session, project_id),
        checkpoints=checkpoints,
        tasks=tasks,
        decisions=decisions,
        recommendations=recommendations,
        activity=activity,
        adapters=adapter_service.list_adapters(project_id=project_id),
    )


def list_projects(session: Session, *, include_archived: bool = False) -> list[ProjectRead]:
    query = select(Project).order_by(Project.display_order, Project.priority, Project.name)
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    return [project_read(session, project) for project in session.scalars(query).all()]


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project_id = payload.id or _slugify(payload.name)
    if session.get(Project, project_id) is not None:
        raise Conflict(f"Project already exists: {project_id}")
    repository_path = None
    if payload.repository_path:
        try:
            repository_path = require_existing_directory(payload.repository_path, field="repository_path")
        except ValidationProblem as exc:
            raise ValidationProblem(exc.message) from exc
    max_priority = int(session.scalar(select(func.max(Project.priority))) or 0)
    max_order = int(session.scalar(select(func.max(Project.display_order))) or 0)
    project = Project(
        id=project_id,
        name=payload.name,
        description=payload.description,
        kind=payload.kind,
        status=payload.status,
        priority=max_priority + 1,
        pinned=payload.pinned,
        archived=False,
        display_order=max_order + 10,
        current_milestone=payload.current_milestone,
        next_action=payload.next_action,
        notes=payload.notes,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    session.add(project)
    session.flush()
    if payload.kind == "book":
        session.add(
            Book(
                id=f"book-{project_id}",
                project_id=project_id,
                title=payload.book_title or payload.name,
                status="planned",
                current_milestone=payload.current_milestone,
                next_action=payload.next_action,
                manuscript_paths=[repository_path] if repository_path else [],
                implementation_paths=[],
                quality_review_state="not_reviewed",
                created_at=now_iso(),
                updated_at=now_iso(),
            )
        )
        session.flush()
    if repository_path:
        repo = session.scalar(select(Repository).where(Repository.path == repository_path))
        if repo is None:
            observed = observe_git(repository_path)
            repo = Repository(
                id=repository_id(repository_path),
                path=repository_path,
                name=Path(repository_path).name,
                classification="unknown",
                confidence=0.3,
                evidence=["Added through the project workspace"],
                source_root=str(Path(repository_path).parent),
                is_git=bool(observed.get("is_git")),
                branch=observed.get("branch"),
                commit_hash=observed.get("commit"),
                last_commit_at=observed.get("last_commit_at"),
                dirty=observed.get("dirty"),
                accessible=bool(observed.get("accessible", True)),
                candidate=False,
                first_seen_at=now_iso(),
                last_observed_at=now_iso(),
            )
            session.add(repo)
            session.flush()
        session.add(
            ProjectRepository(project_id=project_id, repository_id=repo.id, role="manuscript")
        )
    record_activity(
        session,
        event_type="system",
        title=f"Created project: {payload.name}",
        detail="Created through the project workspace.",
        project_id=project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return project


def update_project(session: Session, project_id: str, payload: ProjectUpdate) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(project, key, value)
    project.updated_at = now_iso()
    record_activity(
        session,
        event_type="system",
        title=f"Updated project: {project.name}",
        detail="Project settings changed.",
        project_id=project.id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return project


def set_project_focus(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None or project.archived:
        raise NotFound("Active project not found")
    setting = session.get(Setting, "workspace")
    value = dict(setting.value) if setting else {}
    value["current_project_id"] = project_id
    if setting is None:
        session.add(Setting(key="workspace", value=value, updated_at=now_iso()))
    else:
        setting.value = value
        setting.updated_at = now_iso()
    record_activity(
        session,
        event_type="workspace_focus",
        title=f"Focused on {project.name}",
        detail="Current workspace focus changed.",
        project_id=project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return project


def current_focus(session: Session) -> Project | None:
    setting = session.get(Setting, "workspace")
    if setting and isinstance(setting.value, dict) and setting.value.get("current_project_id"):
        project = session.get(Project, setting.value["current_project_id"])
        if project and not project.archived:
            return project
    checkpoint = session.scalar(
        select(WorkCheckpoint).order_by(desc(WorkCheckpoint.created_at)).limit(1)
    )
    if checkpoint:
        project = session.get(Project, checkpoint.project_id)
        if project and not project.archived:
            return project
    return None


def reorder_projects(session: Session, ordered_ids: list[str]) -> None:
    for index, project_id in enumerate(ordered_ids):
        project = session.get(Project, project_id)
        if project:
            project.priority = index + 1
            project.display_order = (index + 1) * 10
            project.updated_at = now_iso()
    record_activity(
        session,
        event_type="system",
        title="Priority order updated",
        detail="The user reordered priority projects.",
        source="mission-control",
        provenance="user",
    )


# --------------------------------------------------------------------- books
def list_books(session: Session) -> list[BookRead]:
    rows = session.execute(
        select(Book, Project)
        .join(Project, Project.id == Book.project_id)
        .where(Project.archived.is_(False))
        .order_by(Project.display_order, Project.priority, Book.title)
    ).all()
    return [_book_read(session, book, project) for book, project in rows]


def get_book(session: Session, book_id: str) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise NotFound("Book not found")
    return book


def get_book_read(session: Session, book_id: str) -> BookRead:
    book = get_book(session, book_id)
    project = session.get(Project, book.project_id)
    if project is None:
        raise NotFound("Book project not found")
    return _book_read(session, book, project)


def create_book(session: Session, payload: BookCreate) -> Book:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise NotFound("Project not found")
    if session.scalar(select(Book).where(Book.project_id == payload.project_id)):
        raise Conflict("This project already has a book workspace")
    book = Book(
        id=f"book-{payload.project_id}-{uuid.uuid4().hex[:6]}",
        project_id=payload.project_id,
        title=payload.title,
        status=payload.status,
        current_milestone=payload.current_milestone,
        next_action=payload.next_action,
        manuscript_paths=payload.manuscript_paths,
        implementation_paths=payload.implementation_paths,
        published_url=payload.published_url,
        local_url=payload.local_url,
        quality_review_state=payload.quality_review_state,
        created_at=now_iso(),
        updated_at=now_iso(),
        last_activity_at=now_iso(),
    )
    session.add(book)
    record_activity(
        session,
        event_type="system",
        title=f"Created book workspace: {payload.title}",
        detail="Book workspace created through Mission Control.",
        project_id=payload.project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return book


def update_book(session: Session, book_id: str, payload: BookUpdate) -> Book:
    book = get_book(session, book_id)
    project = session.get(Project, book.project_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(book, key, value)
    book.updated_at = now_iso()
    book.last_activity_at = now_iso()
    if project:
        if "next_action" in updates:
            project.next_action = book.next_action
        if "current_milestone" in updates:
            project.current_milestone = book.current_milestone
        project.updated_at = now_iso()
    record_activity(
        session,
        event_type="system",
        title=f"Updated book workspace: {book.title}",
        detail="Book status or next action changed.",
        project_id=book.project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return book


def reorder_books(session: Session, ordered_book_ids: list[str]) -> None:
    for index, book_id in enumerate(ordered_book_ids):
        book = session.get(Book, book_id)
        if book:
            project = session.get(Project, book.project_id)
            if project:
                project.priority = index + 1
                project.display_order = (index + 1) * 10
                project.updated_at = now_iso()
    record_activity(
        session,
        event_type="system",
        title="Book priority order updated",
        detail="The user reordered priority books.",
        source="mission-control",
        provenance="user",
    )


# --------------------------------------------------------------- continuity
def create_checkpoint(session: Session, payload: CheckpointCreate) -> WorkCheckpoint:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise NotFound("Project not found")
    checkpoint = WorkCheckpoint(
        id=f"cp-{uuid.uuid4().hex[:16]}",
        project_id=payload.project_id,
        summary=payload.summary,
        last_completed=payload.last_completed,
        next_action=payload.next_action,
        blockers=payload.blockers,
        evidence_refs=payload.evidence_refs,
        milestone=payload.milestone,
        source="user",
        created_at=now_iso(),
    )
    session.add(checkpoint)
    if payload.next_action.strip():
        project.next_action = payload.next_action.strip()
    if payload.milestone.strip():
        project.current_milestone = payload.milestone.strip()
    project.updated_at = now_iso()
    book = session.scalar(select(Book).where(Book.project_id == payload.project_id))
    if book:
        if payload.next_action.strip():
            book.next_action = payload.next_action.strip()
        if payload.milestone.strip():
            book.current_milestone = payload.milestone.strip()
        book.updated_at = now_iso()
        book.last_activity_at = now_iso()
    setting = session.get(Setting, "workspace")
    value = dict(setting.value) if setting and isinstance(setting.value, dict) else {}
    value["current_project_id"] = project.id
    if setting is None:
        session.add(Setting(key="workspace", value=value, updated_at=now_iso()))
    else:
        setting.value = value
        setting.updated_at = now_iso()
    record_activity(
        session,
        event_type="checkpoint",
        title=f"Checkpoint: {project.name}",
        detail=payload.summary,
        project_id=project.id,
        source="mission-control",
        provenance="user",
        evidence_ref=", ".join(payload.evidence_refs[:5]) or None,
    )
    session.flush()
    return checkpoint


def list_checkpoints(
    session: Session, *, project_id: str | None = None, limit: int = 50
) -> list[CheckpointRead]:
    query = select(WorkCheckpoint).order_by(desc(WorkCheckpoint.created_at)).limit(min(limit, 200))
    if project_id:
        query = query.where(WorkCheckpoint.project_id == project_id)
    return [_checkpoint_read(session, item) for item in session.scalars(query).all()]


# ------------------------------------------------------------------- tasks
def create_task(session: Session, payload: TaskCreate) -> Task:
    if payload.project_id and session.get(Project, payload.project_id) is None:
        raise ValidationProblem("Project does not exist")
    task = Task(
        id=f"task-{uuid.uuid4().hex[:16]}",
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        source="user",
        due_at=payload.due_at,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    session.add(task)
    record_activity(
        session,
        event_type="task_created",
        title=f"Task added: {task.title}",
        detail=task.description,
        project_id=task.project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return task


def update_task(session: Session, task_id: str, payload: TaskUpdate) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise NotFound("Task not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(task, key, value)
    task.updated_at = now_iso()
    record_activity(
        session,
        event_type="task_updated",
        title=f"Task updated: {task.title}",
        detail=f"Status: {task.status}",
        project_id=task.project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return task


def list_tasks(
    session: Session, *, project_id: str | None = None, status: str | None = None
) -> list[TaskRead]:
    query = select(Task).order_by(Task.status, Task.priority, desc(Task.created_at)).limit(500)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)
    return [_task_read(session, task) for task in session.scalars(query).all()]


def get_task_read(session: Session, task_id: str) -> TaskRead:
    task = session.get(Task, task_id)
    if task is None:
        raise NotFound("Task not found")
    return _task_read(session, task)


def get_decision_read(session: Session, decision_id: str) -> DecisionRead:
    decision = session.get(Decision, decision_id)
    if decision is None:
        raise NotFound("Decision not found")
    return _decision_read(session, decision)


def get_recommendation_read(session: Session, recommendation_id: str) -> RecommendationRead:
    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise NotFound("Recommendation not found")
    return _recommendation_read(session, recommendation)


# --------------------------------------------------------------- decisions
def create_decision(session: Session, payload: DecisionCreate) -> Decision:
    if payload.project_id and session.get(Project, payload.project_id) is None:
        raise ValidationProblem("Project does not exist")
    decision = Decision(
        id=f"dec-{uuid.uuid4().hex[:16]}",
        project_id=payload.project_id,
        title=payload.title,
        rationale=payload.rationale,
        status=payload.status,
        source="user",
        decided_at=now_iso(),
        created_at=now_iso(),
    )
    session.add(decision)
    record_activity(
        session,
        event_type="user_decision",
        title=f"Decision: {decision.title}",
        detail=decision.rationale,
        project_id=decision.project_id,
        source="mission-control",
        provenance="user",
        metadata={"status": decision.status},
    )
    session.flush()
    return decision


def list_decisions(session: Session, *, project_id: str | None = None) -> list[DecisionRead]:
    query = select(Decision).order_by(desc(Decision.decided_at)).limit(200)
    if project_id:
        query = query.where(Decision.project_id == project_id)
    return [_decision_read(session, item) for item in session.scalars(query).all()]


# ----------------------------------------------------------- recommendations
def list_recommendations(
    session: Session, *, project_id: str | None = None, state: str | None = None
) -> list[RecommendationRead]:
    query = select(Recommendation).order_by(desc(Recommendation.created_at)).limit(300)
    if project_id:
        query = query.where(Recommendation.project_id == project_id)
    if state:
        query = query.where(Recommendation.review_state == state)
    return [_recommendation_read(session, item) for item in session.scalars(query).all()]


def review_recommendation(session: Session, rec_id: str, payload: ReviewUpdate) -> Recommendation:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise NotFound("Recommendation not found")
    rec.review_state = payload.review_state
    rec.updated_at = now_iso()
    decision = Decision(
        id=f"dec-{uuid.uuid4().hex[:16]}",
        project_id=rec.project_id,
        title=f"Recommendation {payload.review_state}: {rec.title[:240]}",
        rationale=payload.note or rec.rationale,
        status=payload.review_state if payload.review_state in {"accepted", "rejected", "deferred"} else "revised",
        source="user",
        decided_at=now_iso(),
        created_at=now_iso(),
    )
    session.add(decision)
    record_activity(
        session,
        event_type="recommendation_reviewed",
        title=f"Recommendation {payload.review_state}: {rec.title[:200]}",
        detail=payload.note or rec.rationale,
        project_id=rec.project_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return rec


# --------------------------------------------------------------- activity
def list_activity(
    session: Session,
    *,
    project_id: str | None = None,
    event_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ActivityRead]:
    query = select(ActivityEvent).order_by(desc(ActivityEvent.occurred_at))
    if project_id:
        query = query.where(ActivityEvent.project_id == project_id)
    if event_type:
        query = query.where(ActivityEvent.type == event_type)
    if since:
        query = query.where(ActivityEvent.occurred_at >= since)
    if until:
        query = query.where(ActivityEvent.occurred_at <= until)
    query = query.limit(min(limit, 200)).offset(max(offset, 0))
    return [activity_read(session, item) for item in session.scalars(query).all()]


def add_note(
    session: Session, *, project_id: str | None, title: str, detail: str, evidence_ref: str | None
) -> ActivityRead:
    if project_id and session.get(Project, project_id) is None:
        raise ValidationProblem("Project does not exist")
    event = record_activity(
        session,
        event_type="user_note",
        title=title,
        detail=detail,
        project_id=project_id,
        source="mission-control",
        provenance="user",
        evidence_ref=evidence_ref,
    )
    session.flush()
    return activity_read(session, event)


# ---------------------------------------------------------- Git observation
def refresh_repositories(database: Database) -> int:
    with database.session() as session:
        project_repo_ids = set(session.scalars(select(ProjectRepository.repository_id)).all())
        app_paths = {
            path
            for path in session.scalars(select(Application.repository_path)).all()
            if path
        }
        repos = [
            repo
            for repo in session.scalars(select(Repository)).all()
            if repo.id in project_repo_ids or repo.path in app_paths
        ]
        targets = [(repo.id, repo.path) for repo in repos]

    def observe(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        repo_id, path = item
        return repo_id, observe_git(path)

    observed_items: list[tuple[str, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(targets)))) as pool:
        observed_items = list(pool.map(observe, targets))

    with database.session() as session:
        fingerprint_parts: list[str] = []
        for repo_id, info in observed_items:
            repo = session.get(Repository, repo_id)
            if repo is None:
                continue
            repo.is_git = bool(info.get("is_git"))
            repo.accessible = bool(info.get("accessible", True))
            repo.branch = info.get("branch")
            repo.commit_hash = info.get("commit")
            repo.last_commit_at = info.get("last_commit_at")
            repo.dirty = info.get("dirty")
            repo.last_observed_at = now_iso()
            if info.get("error"):
                repo.notes = str(info["error"])[:500]
            fingerprint_parts.append(f"{repo.path}:{repo.commit_hash}:{repo.dirty}")
        if observed_items:
            fingerprint = hashlib.sha1("|".join(sorted(fingerprint_parts)).encode()).hexdigest()[:12]
            record_activity(
                session,
                event_type="git_observation",
                title=f"Observed Git state for {len(observed_items)} repositories",
                detail="Read-only status and commit metadata; no repository state was changed.",
                source="mission-control",
                provenance="verified_observation",
                dedupe_key=f"git-observation-{fingerprint}",
                metadata={"repositories": len(observed_items)},
            )
    return len(observed_items)
