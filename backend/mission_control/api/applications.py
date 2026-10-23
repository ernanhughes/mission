"""Application registry, launch and repository actions."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.api.deps import get_session, process_read
from mission_control.core.editor import open_path_with_editor
from mission_control.core.errors import (
    CapabilityUnavailable,
    Conflict,
    MissionControlError,
    NotFound,
    ValidationProblem,
)
from mission_control.models import Application, LaunchDefinition, ProcessInstance, Setting
from mission_control.registry.service import (
    build_application_read,
    create_application,
    reorder_applications,
    update_application,
)
from mission_control.schemas import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    HealthCheckResponse,
    LaunchRequest,
    LogRead,
    OkResponse,
    OpenUrlResponse,
    ProcessRead,
    ReorderRequest,
    StartupActivationEntry,
    StartupActivationRead,
)

router = APIRouter(prefix="/api", tags=["applications"])


@router.get("/applications", response_model=list[ApplicationRead])
def list_applications(
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
    search: str | None = None,
    category: str | None = None,
    enabled_only: bool = False,
    include_archived: bool = False,
) -> list[ApplicationRead]:
    manager = request.app.state.process_manager
    query = select(Application).order_by(Application.display_order, Application.name)
    if enabled_only:
        query = query.where(Application.enabled.is_(True), Application.archived.is_(False))
    if not include_archived:
        query = query.where(Application.archived.is_(False))
    if category:
        query = query.where(Application.category == category)
    applications = session.scalars(query).all()
    if search:
        needle = search.casefold()
        applications = [
            app
            for app in applications
            if needle in app.name.casefold()
            or needle in app.description.casefold()
            or any(needle in str(tag).casefold() for tag in app.tags)
        ]
    return [build_application_read(session, app, manager) for app in applications]


@router.post("/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def add_application(
    payload: ApplicationCreate,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ApplicationRead:
    app = create_application(session, payload)
    session.flush()
    return build_application_read(session, app, request.app.state.process_manager)


@router.get("/applications/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ApplicationRead:
    app = session.get(Application, application_id)
    if app is None:
        raise NotFound("Application not found")
    return build_application_read(session, app, request.app.state.process_manager)


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
def patch_application(
    application_id: str,
    payload: ApplicationUpdate,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ApplicationRead:
    app = update_application(session, application_id, payload)
    session.flush()
    return build_application_read(session, app, request.app.state.process_manager)


@router.post("/applications/reorder", response_model=OkResponse)
def reorder_applications_route(
    payload: ReorderRequest, session: Session = Depends(get_session)
) -> OkResponse:
    reorder_applications(session, payload.ids)
    return OkResponse()


@router.post("/applications/{application_id}/launch", response_model=ProcessRead, status_code=201)
async def launch_application(
    application_id: str,
    payload: LaunchRequest,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProcessRead:
    record = await request.app.state.process_manager.launch(
        application_id, launch_id=payload.launch_id, confirm=payload.confirm
    )
    return process_read(session, record)


@router.post("/applications/{application_id}/stop", response_model=ProcessRead)
async def stop_application(
    application_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProcessRead:
    record = await request.app.state.process_manager.stop_application(application_id)
    return process_read(session, record)


@router.post("/applications/{application_id}/restart", response_model=ProcessRead)
async def restart_application(
    application_id: str,
    payload: LaunchRequest,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> ProcessRead:
    record = await request.app.state.process_manager.restart(
        application_id, launch_id=payload.launch_id, confirm=payload.confirm
    )
    return process_read(session, record)


@router.post("/applications/{application_id}/open-repository", response_model=OkResponse)
def open_repository(
    application_id: str,
    session: Session = Depends(get_session),
) -> OkResponse:
    app = session.get(Application, application_id)
    if app is None:
        raise NotFound("Application not found")
    if not app.repository_path or not Path(app.repository_path).is_dir():
        raise CapabilityUnavailable(
            "No existing primary repository path is configured",
            detail="Edit the application and set a valid repository path.",
        )
    command = open_path_with_editor(session, app.repository_path)
    record_activity(
        session,
        event_type="repository_opened",
        title=f"Opened {app.name} repository",
        detail=str(app.repository_path),
        application_id=app.id,
        source="mission-control",
        provenance="verified_observation",
    )
    return OkResponse(detail=f"Opened {app.repository_path} with {command}")


@router.post("/applications/{application_id}/open-documentation", response_model=OkResponse)
def open_documentation(
    application_id: str,
    session: Session = Depends(get_session),
) -> OkResponse:
    app = session.get(Application, application_id)
    if app is None:
        raise NotFound("Application not found")
    documentation_path = next(
        (path for path in app.documentation_paths if Path(path).exists()), None
    )
    if not documentation_path:
        raise CapabilityUnavailable(
            "No existing documentation path is configured",
            detail="Add a documentation file or directory to the application registry.",
        )
    command = open_path_with_editor(session, documentation_path)
    record_activity(
        session,
        event_type="repository_opened",
        title=f"Opened {app.name} documentation",
        detail=documentation_path,
        application_id=app.id,
        source="mission-control",
        provenance="verified_observation",
    )
    return OkResponse(detail=f"Opened {documentation_path} with {command}")


@router.post("/applications/{application_id}/open-url", response_model=OpenUrlResponse)
def open_url(
    application_id: str,
    session: Session = Depends(get_session),
) -> OpenUrlResponse:
    app = session.get(Application, application_id)
    if app is None:
        raise NotFound("Application not found")
    definitions = session.scalars(
        select(LaunchDefinition)
        .where(LaunchDefinition.application_id == application_id)
        .order_by(LaunchDefinition.is_primary.desc(), LaunchDefinition.name)
    ).all()
    url = next((item.browser_url for item in definitions if item.browser_url), None)
    if not url:
        raise CapabilityUnavailable(
            "No browser URL is configured for this application",
            detail="Add a browser URL to a launch definition.",
        )
    setting = session.get(Setting, "browser")
    browser_config = setting.value if setting and isinstance(setting.value, dict) else {}
    opened_externally = False
    if browser_config.get("open_mode") == "external":
        try:
            opened_externally = bool(webbrowser.open(url, new=2))
        except Exception as exc:  # pragma: no cover - desktop integration
            raise CapabilityUnavailable(
                "The system browser could not be opened",
                detail=exc.__class__.__name__,
            ) from exc
        if not opened_externally:
            raise CapabilityUnavailable("The system browser did not accept the URL")
    record_activity(
        session,
        event_type="repository_opened",
        title=f"Opened {app.name} web interface",
        detail=url,
        application_id=app.id,
        source="mission-control",
        provenance="user",
    )
    return OpenUrlResponse(
        url=url, application_id=app.id, opened_externally=opened_externally
    )


@router.post("/applications/{application_id}/check-health", response_model=HealthCheckResponse)
async def check_health(
    application_id: str,
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> HealthCheckResponse:
    observation = await request.app.state.process_manager.check_health(application_id)
    return HealthCheckResponse(
        id=observation.id,
        application_id=observation.application_id,
        state=observation.state,
        detail=observation.detail,
        source=observation.source,
        observed_at=observation.observed_at,
        stale_after_seconds=observation.stale_after_seconds,
    )


@router.get("/applications/{application_id}/logs", response_model=LogRead)
def application_logs(
    application_id: str,
    lines: int = Query(default=200, ge=1, le=2000),
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> LogRead:
    record = session.scalar(
        select(ProcessInstance)
        .where(ProcessInstance.application_id == application_id)
        .order_by(ProcessInstance.started_at.desc())
        .limit(1)
    )
    if record is None:
        raise NotFound("No process records exist for this application")
    data = request.app.state.process_manager.read_log(record.id, lines)
    return LogRead(**data)


@router.post("/startup/activate", response_model=StartupActivationRead)
async def activate_startup_profile(
    session: Session = Depends(get_session),
    request: Request = None,  # type: ignore[assignment]
) -> StartupActivationRead:
    setting = session.get(Setting, "startup")
    config = setting.value if setting and isinstance(setting.value, dict) else {}
    if not config.get("profile_enabled"):
        raise Conflict("Startup profile is not enabled")
    application_ids = list(config.get("profile_applications") or [])
    if not application_ids:
        raise ValidationProblem("Startup profile has no applications")
    activated: list[StartupActivationEntry] = []
    skipped: list[StartupActivationEntry] = []
    for app_id in application_ids[:10]:
        app = session.get(Application, app_id)
        if app is None:
            skipped.append(StartupActivationEntry(application_id=app_id, status="missing", detail="Application not found"))
            continue
        try:
            record = await request.app.state.process_manager.launch(app_id, confirm=True)
            activated.append(
                StartupActivationEntry(
                    application_id=app_id, status=record.status, process_id=record.id
                )
            )
        except MissionControlError as exc:
            skipped.append(
                StartupActivationEntry(
                    application_id=app_id, status="skipped", detail=exc.message
                )
            )
    return StartupActivationRead(activated=activated, skipped=skipped)
