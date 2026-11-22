"""Projects, books, checkpoints, tasks, decisions and activity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import NotFound
from mission_control.discovery.books import sync_detected_books, sync_fiction_books
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
    BookDetectionRead,
    BookRead,
    BookUpdate,
    CheckpointCreate,
    CheckpointRead,
    DecisionCreate,
    DecisionRead,
    IdentityApplyRead,
    IdentityApplyRequest,
    IdentityAutoRegisterRequest,
    IdentityPolicyRead,
    IdentityPreviewRead,
    IdentityRollbackRead,
    IdentityRollbackRequest,
    IntegrationRecordRead,
    OkResponse,
    OutcomeRead,
    ProjectCreate,
    ProjectDetail,
    ProjectGitLinkRead,
    ProjectRead,
    ProjectReconciliationRead,
    ProjectUpdate,
    RecommendationRead,
    ReorderRequest,
    ResumeRead,
    ReviewUpdate,
    SoftwareInventoryRead,
    SoftwareProjectRead,
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


@router.get("/projects/reconciliation", response_model=ProjectReconciliationRead)
def get_projects_reconciliation(
    session: Session = Depends(get_session),
    root: str | None = None,
    live: bool = False,
) -> ProjectReconciliationRead:
    """Read-only software-project discovery reconciliation (no writes).

    Compares the inventory under ``root`` (default ``C:\\Projects``) against
    persisted projects, repositories, Git identities and applications.
    Book-legacy projects are listed separately and preserved.
    """
    from mission_control.projects.reconciliation import build_reconciliation

    return ProjectReconciliationRead(**build_reconciliation(session, software_root=root, live=live))


# --------------------------------------- software identity cutover (MC-PROJECTS-QUALITY-01)


@router.get("/projects/identity/preview", response_model=IdentityPreviewRead)
def get_identity_preview(
    session: Session = Depends(get_session),
    root: str | None = None,
) -> IdentityPreviewRead:
    """Read-only cutover preview: eligible, needs-review and skipped. No writes."""
    from mission_control.projects.registration import preview_registration

    return IdentityPreviewRead(**preview_registration(session, root))


@router.get("/projects/identity/policy", response_model=IdentityPolicyRead)
def get_identity_policy(session: Session = Depends(get_session)) -> IdentityPolicyRead:
    from mission_control.projects.registration import get_policy

    return IdentityPolicyRead(**get_policy(session))


@router.post("/projects/identity/apply", response_model=IdentityApplyRead)
def apply_identity_cutover(
    payload: IdentityApplyRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> IdentityApplyRead:
    """Register software project workspaces. Requires explicit confirmation.

    Backs up the SQLite database before writing. Idempotent: repeated calls
    with the same selection skip already-registered repositories.
    """
    from mission_control.projects.registration import apply_registration, backup_database

    settings = request.app.state.settings
    backup = backup_database(settings.db_path, settings.data_dir / "backups")
    result = apply_registration(
        session,
        paths=payload.paths,
        select_all_eligible=payload.all_eligible,
        confirm=payload.confirm,
        approve_policy=payload.approve_policy,
        root=payload.root,
        backup_path=backup,
    )
    # Commit before returning: dependency cleanup runs after the response is
    # sent, so a following request would otherwise not see these rows yet.
    session.commit()
    return IdentityApplyRead(**result)


@router.post("/projects/identity/auto-register", response_model=IdentityApplyRead)
def auto_register_projects(
    payload: IdentityAutoRegisterRequest,
    session: Session = Depends(get_session),
) -> IdentityApplyRead:
    """Register currently-eligible repositories under the approved policy.

    Explicit endpoint only; scans never register implicitly. Requires the
    approved policy and explicit confirmation.
    """
    from mission_control.projects.registration import auto_register

    result = auto_register(session, confirm=payload.confirm, root=payload.root)
    session.commit()
    return IdentityApplyRead(**result)


@router.post("/projects/identity/rollback", response_model=IdentityRollbackRead)
def rollback_identity_cutover(
    payload: IdentityRollbackRequest,
    session: Session = Depends(get_session),
) -> IdentityRollbackRead:
    """Remove pristine auto-registered projects. User records are never deleted."""
    from mission_control.projects.registration import rollback_cutover

    result = rollback_cutover(session, confirm=payload.confirm)
    session.commit()
    return IdentityRollbackRead(**result)


def _inspect_ids_by_path(request: Request, paths: list[str]) -> dict[str, str]:
    """Reverse-map repository paths to Inspect project ids (read-only snapshot)."""
    try:
        from mission_control.inspect_snapshots import (
            get_store,
            normalize_repository_path,
        )

        store = get_store(request.app.state.settings.inspect_dir)
        data, _ = store.view()
    except Exception:
        return {}
    if data is None:
        return {}
    by_path: dict[str, str] = {}
    for project in data.projects:
        if not isinstance(project, dict):
            continue
        key = normalize_repository_path(project.get("path"))
        if key and key not in by_path:
            by_path[key] = str(project.get("id") or "")
    from mission_control.inspect_snapshots import normalize_repository_path as _norm_path

    result: dict[str, str] = {}
    for path in paths:
        key = _norm_path(path)
        if key and key in by_path and by_path[key]:
            result[path] = by_path[key]
    return result


@router.get("/projects/software", response_model=SoftwareInventoryRead)
def get_software_inventory(
    request: Request,
    session: Session = Depends(get_session),
    search: str | None = None,
    classification: str | None = None,
    attention_only: bool = False,
    missing_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SoftwareInventoryRead:
    """Paginated software workspace inventory. Book-legacy projects are excluded."""
    from mission_control.projects.registration import software_inventory

    total, rows = software_inventory(
        session,
        search=search,
        classification=classification,
        attention_only=attention_only,
        missing_only=missing_only,
        limit=limit,
        offset=offset,
    )
    inspect_ids = _inspect_ids_by_path(
        request, [row["path"] for row in rows if row.get("path")]
    )
    return SoftwareInventoryRead(
        total=total, limit=limit, offset=offset,
        items=[
            SoftwareProjectRead(
                **row,
                inspect_project_id=inspect_ids.get(row.get("path") or "") if row.get("path") else None,
            )
            for row in rows
        ],
    )


@router.get("/projects/{project_id}/git-links", response_model=list[ProjectGitLinkRead])
def get_project_git_links(
    project_id: str, session: Session = Depends(get_session)
) -> list[ProjectGitLinkRead]:
    """Git-indexed repositories backing one project, matched by normalized path."""
    from mission_control.projects.registration import project_git_links

    return [ProjectGitLinkRead(**row) for row in project_git_links(session, project_id)]


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProjectDetail:
    from mission_control.adapters.service import AdapterService

    detail = project_detail(
        session,
        project_id,
        AdapterService(request.app.state.database, request.app.state.settings),
    )
    inspect_ids = _inspect_ids_by_path(
        request, [repo.path for repo in detail.repositories]
    )
    for repo in detail.repositories:
        if repo.path in inspect_ids:
            detail.inspect_project_id = inspect_ids[repo.path]
            break
    return detail


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


@router.post("/books/detect", response_model=BookDetectionRead)
def detect_book_workspaces(
    request: Request, session: Session = Depends(get_session)
) -> BookDetectionRead:
    created = sync_detected_books(session, [request.app.state.settings.book_root])
    return BookDetectionRead(created=created, count=len(created))


# ------------------------------------------------- fiction book collection
@router.get("/fiction-books", response_model=list[BookRead])
def get_fiction_books(
    request: Request, session: Session = Depends(get_session)
) -> list[BookRead]:
    """Fiction manuscripts from the configured fiction root (read-only filter).

    The shared Book workspace table holds both collections; membership in the
    fiction collection is determined by manuscript paths under the configured
    fiction root. Technical books are never included here.
    """
    from pathlib import Path as _Path

    from mission_control.core.paths import is_within

    try:
        fiction_root = _Path(request.app.state.settings.fiction_book_root)
    except Exception:
        return []
    result = []
    for book in list_books(session):
        try:
            if any(
                is_within(_Path(path), fiction_root)
                for path in (book.manuscript_paths or [])
            ):
                result.append(book)
        except OSError:
            continue
    return result


@router.post("/fiction-books/detect", response_model=BookDetectionRead)
def detect_fiction_book_workspaces(
    request: Request, session: Session = Depends(get_session)
) -> BookDetectionRead:
    created = sync_fiction_books(session, [request.app.state.settings.fiction_book_root])
    return BookDetectionRead(created=created, count=len(created))


# ------------------------------------------- writer registry integration
@router.get("/books/writer-registry")
def writer_registry_status(
    request: Request, session: Session = Depends(get_session)
) -> dict:
    """Read-only view of Writer's authoritative book registry."""
    from mission_control.discovery.books import detect_books, detect_fiction_books
    from mission_control.writer_registry import (
        load_writer_registry,
        resolve_registry_path,
    )
    from mission_control.writer_registry.sync import classify_discovery

    settings = request.app.state.settings
    snapshot = load_writer_registry(resolve_registry_path(settings))
    books = []
    for project_id in sorted(snapshot.books):
        definition = snapshot.books[project_id]
        books.append(
            {
                "project_id": definition.project_id,
                "title": definition.title,
                "chapter_dir": str(definition.chapter_dir),
                "chapter_pattern": definition.chapter_pattern,
                "manuscript": definition.manuscript,
                "profile": definition.profile,
                "publication_status": definition.publication_status,
                "preview_route": definition.preview_route,
                "available": definition.available,
                "chapter_count": definition.chapter_count,
                "error": definition.error,
            }
        )
    try:
        detected_technical = detect_books([settings.book_root])
    except OSError:
        detected_technical = []
    try:
        detected_fiction = detect_fiction_books([settings.fiction_book_root])
    except OSError:
        detected_fiction = []
    try:
        discovery = classify_discovery(
            detected_technical=detected_technical,
            detected_fiction=detected_fiction,
            snapshot=snapshot,
            session=session,
        )
    except Exception:
        discovery = {
            "registered_available": [],
            "registered_unavailable": [],
            "discovered_unregistered": [],
            "ambiguous_or_conflicting": [],
            "registry_errors": snapshot.errors,
        }
    return {
        "registry": str(snapshot.source_path) if snapshot.source_path else None,
        "mtime_ns": snapshot.mtime_ns,
        "books": books,
        "count": len(books),
        "errors": snapshot.errors,
        "skipped_non_book": snapshot.skipped_non_book,
        "discovery": discovery,
    }


@router.post("/books/writer-sync")
def writer_registry_sync(
    request: Request,
    session: Session = Depends(get_session),
    payload: dict | None = None,
) -> dict:
    """Synchronise Mission books with Writer's registry (repairs chapter dirs).

    Writer owns manuscript location; Mission planning state is preserved.
    """
    from mission_control.writer_registry import (
        load_writer_registry,
        resolve_registry_path,
        sync_writer_books,
    )

    body = payload or {}
    create_missing = bool(body.get("create_missing", True))
    snapshot = load_writer_registry(resolve_registry_path(request.app.state.settings))
    summary = sync_writer_books(session, snapshot, create_missing=create_missing)
    return summary


# ------------------------------------------------- canonical book identity
@router.get("/books/identity-conflicts")
def identity_conflicts(
    request: Request, session: Session = Depends(get_session)
) -> dict:
    """Read-only identity reconciliation report: candidates, conflicts, unavailable."""
    from mission_control.publication.identity import list_identity_conflicts
    from mission_control.writer_registry import load_writer_registry, resolve_registry_path

    snapshot = load_writer_registry(resolve_registry_path(request.app.state.settings))
    writer_ids = set(snapshot.books)
    writer_available = {pid: bool(defn.available) for pid, defn in snapshot.books.items()}
    report = list_identity_conflicts(session, writer_ids, writer_available)
    return {
        "registry": str(snapshot.source_path) if snapshot.source_path else None,
        "errors": snapshot.errors,
        **report,
    }


@router.get("/books/{book_id}/identity")
def book_identity_route(
    book_id: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    """Canonical identity, aliases and locations for one book. Read-only."""
    from sqlalchemy import select as _select

    from mission_control.models import Book as _Book
    from mission_control.publication.identity import get_aliases, identity_status
    from mission_control.writer_registry import (
        book_source_diagnostic,
        load_writer_registry,
        resolve_registry_path,
    )

    row = session.get(_Book, book_id)
    if row is None:
        row = session.scalar(_select(_Book).where(_Book.project_id == book_id))
    project_id = row.project_id if row is not None else book_id
    snapshot = load_writer_registry(resolve_registry_path(request.app.state.settings))
    writer_ids = set(snapshot.books)
    writer_available = {pid: bool(defn.available) for pid, defn in snapshot.books.items()}
    status = identity_status(session, project_id, writer_ids, writer_available)
    diagnostic = book_source_diagnostic(session, project_id, snapshot)
    aliases = [
        entry for entry in get_aliases(session)
        if entry.get("canonical_project_id") == project_id
    ]
    definition = snapshot.books.get(status.get("writer_id") or project_id)
    locations: list[dict[str, str]] = []
    if diagnostic.get("resolved_chapter_dir"):
        locations.append({
            "location_type": "manuscript_root",
            "source_system": "writer" if diagnostic.get("writer_registered") else "mission",
            "location": str(diagnostic["resolved_chapter_dir"]),
            "availability": "available" if diagnostic.get("available") else "unavailable",
        })
    for extra in diagnostic.get("manuscript_paths", [])[1:]:
        locations.append({
            "location_type": "manuscript_root",
            "source_system": "mission",
            "location": str(extra),
            "availability": "unknown",
        })
    return {
        "project_id": project_id,
        "book_id": row.id if row is not None else None,
        "canonical_id": project_id,
        "display_title": diagnostic.get("book_title"),
        "identity_state": status.get("state"),
        "identity_reason": status.get("reason"),
        "writer_project_id": status.get("writer_id"),
        "candidates": status.get("candidates", []),
        "aliases": aliases,
        "locations": locations,
        "lifecycle": diagnostic.get("publication_status"),
    }


@router.post("/books/aliases", status_code=201)
def create_book_alias(
    request: Request, session: Session = Depends(get_session), payload: dict | None = None
) -> dict:
    """Persist an explicit identity alias. Requires explicit author confirmation.

    Body: {canonical_project_id, system, external_id, source_reference?, confirm}.
    Nothing is inferred; conflicts and fabricated Writer ids fail closed.
    """
    from mission_control.publication.identity import save_alias
    from mission_control.writer_registry import load_writer_registry, resolve_registry_path

    body = payload or {}
    if body.get("confirm") is not True:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail="Alias registration requires explicit confirmation (confirm: true).",
        )
    snapshot = load_writer_registry(resolve_registry_path(request.app.state.settings))
    try:
        entry = save_alias(
            session,
            canonical_project_id=str(body.get("canonical_project_id") or ""),
            system=str(body.get("system") or ""),
            external_id=str(body.get("external_id") or ""),
            source_reference=str(body.get("source_reference") or ""),
            known_writer_ids=set(snapshot.books),
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(exc)) from None
    session.flush()
    return entry


@router.delete("/books/aliases")
def remove_book_alias(
    request: Request, session: Session = Depends(get_session), payload: dict | None = None
) -> dict:
    """Remove an explicit identity alias (author action; history is untouched)."""
    from mission_control.publication.identity import delete_alias

    body = payload or {}
    removed = delete_alias(
        session, system=str(body.get("system") or ""), external_id=str(body.get("external_id") or "")
    )
    session.flush()
    return {"removed": removed}


@router.get("/books/{book_id}/source")
def book_source_diagnostic_route(
    book_id: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    """Per-book source diagnostics for the Book workspace UI."""
    from sqlalchemy import select as _select

    from mission_control.models import Book as _Book
    from mission_control.writer_registry import (
        book_source_diagnostic,
        load_writer_registry,
        resolve_registry_path,
    )

    project_id = book_id
    row = session.get(_Book, book_id)
    if row is None:
        row = session.scalar(_select(_Book).where(_Book.project_id == book_id))
    else:
        project_id = row.project_id
    if row is not None:
        project_id = row.project_id
    snapshot = load_writer_registry(resolve_registry_path(request.app.state.settings))
    return book_source_diagnostic(session, project_id, snapshot)


@router.post("/fiction-books/reorder", response_model=OkResponse)
def reorder_fiction_books_route(
    payload: ReorderRequest, session: Session = Depends(get_session)
) -> OkResponse:
    from mission_control.projects.service import reorder_books as _reorder_books

    _reorder_books(session, payload.ids)
    return OkResponse()


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
