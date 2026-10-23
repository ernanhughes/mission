"""Application registry CRUD and capability-aware presentation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.core.paths import resolve_executable
from mission_control.models import (
    Application,
    Book,
    HealthObservation,
    LaunchDefinition,
    Outcome,
    ProcessInstance,
    Project,
    Setting,
)
from mission_control.persistence.db import now_iso
from mission_control.processes.manager import ProcessManager
from mission_control.schemas import (
    ActionState,
    ApplicationActions,
    ApplicationCreate,
    ApplicationRead,
    ApplicationStatus,
    ApplicationUpdate,
    ControlPolicy,
    LaunchDefinitionInput,
    LaunchDefinitionRead,
)

SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = SLUG.sub("-", value.strip().lower()).strip("-")
    return slug[:64] or f"app-{uuid.uuid4().hex[:6]}"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_seconds(value: str | None) -> float | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def editor_state(session: Session) -> tuple[bool, str | None]:
    setting = session.get(Setting, "editor")
    value = setting.value if setting and isinstance(setting.value, dict) else {}
    command = str(value.get("command") or "").strip()
    if not command:
        return False, "Configure an editor command in Settings to open repositories."
    resolved = resolve_executable(command)
    if not resolved:
        return False, f"Configured editor was not found: {command}"
    if Path(resolved).suffix.casefold() in {".bat", ".cmd", ".ps1"}:
        return False, "The configured editor resolves to a shell script. Set the native executable (for example Code.exe)."
    return True, None


def primary_definition(session: Session, application_id: str) -> LaunchDefinition | None:
    definitions = session.scalars(
        select(LaunchDefinition)
        .where(LaunchDefinition.application_id == application_id)
        .order_by(desc(LaunchDefinition.enabled), desc(LaunchDefinition.is_primary), LaunchDefinition.name)
    ).all()
    enabled = [item for item in definitions if item.enabled]
    if enabled:
        return next((item for item in enabled if item.is_primary), enabled[0])
    return definitions[0] if definitions else None


def _definition_status(session: Session, application: Application) -> tuple[ApplicationStatus, bool]:
    """Return computed status and whether an enabled launch exists."""
    manager_active = session.scalar(
        select(ProcessInstance)
        .where(
            ProcessInstance.application_id == application.id,
            ProcessInstance.status == "running",
        )
        .order_by(desc(ProcessInstance.started_at))
    )
    enabled_definitions = session.scalars(
        select(LaunchDefinition).where(
            LaunchDefinition.application_id == application.id,
            LaunchDefinition.enabled.is_(True),
        )
    ).all()
    health = session.scalar(
        select(HealthObservation)
        .where(HealthObservation.application_id == application.id)
        .order_by(desc(HealthObservation.observed_at))
    )
    # Health history from a disabled definition must not be presented as the
    # current application's state. Only an enabled health-capable definition
    # can make a probe meaningful.
    if not any(item.health_type != "none" for item in enabled_definitions):
        health = None
    latest_process = session.scalar(
        select(ProcessInstance)
        .where(ProcessInstance.application_id == application.id)
        .order_by(desc(ProcessInstance.started_at))
    )
    stale = False
    if health and _age_seconds(health.observed_at) is not None:
        stale = (_age_seconds(health.observed_at) or 0) > health.stale_after_seconds
    if manager_active:
        detail = f"PID {manager_active.pid} is owned by Mission Control."
        if health and not stale and health.state not in {"healthy", "process_only"}:
            detail += f" Latest health probe: {health.state} ({health.detail})."
        return (
            ApplicationStatus(
                state="running",
                label="Running",
                detail=detail,
                ownership="managed",
                observed_at=manager_active.started_at,
                stale=False,
                health_state=health.state if health and not stale else None,
                process_id=manager_active.id,
            ),
            bool(enabled_definitions),
        )
    if health and not stale and health.state == "healthy":
        return (
            ApplicationStatus(
                state="running",
                label="Running (external)",
                detail=(
                    f"{health.detail}. A responding endpoint does not prove that this configured "
                    "application owns the listener. Mission Control does not own it and will not stop it."
                ),
                ownership="external",
                observed_at=health.observed_at,
                stale=False,
                health_state=health.state,
            ),
            bool(enabled_definitions),
        )
    if health and stale:
        return (
            ApplicationStatus(
                state="stale",
                label="Status is stale",
                detail=f"Last observed state was {health.state}: {health.detail}",
                ownership="unknown",
                observed_at=health.observed_at,
                stale=True,
                health_state=health.state,
            ),
            bool(enabled_definitions),
        )
    failed_recently = (
        application.last_launch_failure_at
        and (
            not application.last_launch_success_at
            or application.last_launch_failure_at >= application.last_launch_success_at
        )
    )
    if failed_recently and latest_process and latest_process.status in {"failed", "lost"}:
        return (
            ApplicationStatus(
                state="launch_failed",
                label="Last launch failed",
                detail=application.last_failure_detail or latest_process.error or "The process failed.",
                ownership="none",
                observed_at=application.last_launch_failure_at,
                stale=False,
            ),
            bool(enabled_definitions),
        )
    definition = primary_definition(session, application.id)
    misconfigured_reason = None
    if definition and definition.enabled:
        if definition.launch_type in {"command", "server"}:
            if not definition.executable:
                misconfigured_reason = "Enabled launch definition has no executable."
            elif not resolve_executable(definition.executable):
                misconfigured_reason = f"Executable not found: {definition.executable}"
            working = (
                definition.working_directory
                or application.working_directory
                or application.repository_path
            )
            if not working or not Path(working).is_dir():
                misconfigured_reason = misconfigured_reason or "Working directory is missing or invalid."
        if definition.health_type == "http" and not definition.health_url:
            misconfigured_reason = misconfigured_reason or "HTTP health check has no URL."
    if misconfigured_reason:
        return (
            ApplicationStatus(
                state="misconfigured",
                label="Misconfigured",
                detail=misconfigured_reason,
                ownership="none",
                stale=False,
            ),
            bool(enabled_definitions),
        )
    if health:
        state = health.state
        if state == "unhealthy":
            return (
                ApplicationStatus(
                    state="unavailable",
                    label="Unavailable",
                    detail=health.detail,
                    ownership="none",
                    observed_at=health.observed_at,
                    health_state=state,
                ),
                bool(enabled_definitions),
            )
        if state in {"unavailable", "misconfigured"}:
            return (
                ApplicationStatus(
                    state="unavailable" if state == "unavailable" else "misconfigured",
                    label="Unavailable" if state == "unavailable" else "Misconfigured",
                    detail=health.detail,
                    ownership="none",
                    observed_at=health.observed_at,
                    health_state=state,
                ),
                bool(enabled_definitions),
            )
    has_health = any(item.enabled and item.health_type != "none" for item in enabled_definitions)
    if has_health and not health:
        return (
            ApplicationStatus(
                state="not_checked",
                label="Not checked",
                detail="No health observation has been recorded yet.",
                ownership="none",
                stale=True,
            ),
            bool(enabled_definitions),
        )
    if not enabled_definitions:
        return (
            ApplicationStatus(
                state="unavailable",
                label="No launch configured",
                detail="The repository and documentation can be opened; no verified launch action is enabled.",
                ownership="none",
            ),
            False,
        )
    return (
        ApplicationStatus(
            state="stopped",
            label="Stopped",
            detail="A launch action is configured but no managed process is running.",
            ownership="none",
            observed_at=latest_process.ended_at if latest_process else None,
        ),
        True,
    )


def build_application_read(
    session: Session, application: Application, manager: ProcessManager | None = None
) -> ApplicationRead:
    all_definitions = session.scalars(
        select(LaunchDefinition)
        .where(LaunchDefinition.application_id == application.id)
        .order_by(desc(LaunchDefinition.is_primary), LaunchDefinition.name)
    ).all()
    enabled_definitions = [item for item in all_definitions if item.enabled]
    launchable = any(item.launch_type in {"command", "server"} for item in enabled_definitions)
    status = _definition_status(session, application)[0]
    active = None
    if manager is not None:
        manager.reconcile_live(session, application.id)
        active = session.scalar(
            select(ProcessInstance)
            .where(
                ProcessInstance.application_id == application.id,
                ProcessInstance.status == "running",
            )
            .order_by(desc(ProcessInstance.started_at))
        )
        if active:
            status = status.model_copy(
                update={
                    "state": "running",
                    "label": "Running",
                    "ownership": "managed",
                    "process_id": active.id,
                    "detail": f"PID {active.pid} is owned by Mission Control.",
                }
            )
    repository_ok = bool(application.repository_path and Path(application.repository_path).is_dir())
    documentation_path = next(
        (path for path in application.documentation_paths if Path(path).exists()), None
    )
    editor_ok, editor_reason = editor_state(session)
    browser_url = None
    for definition in enabled_definitions:
        if definition.launch_type == "url" and definition.browser_url:
            browser_url = definition.browser_url
            break
        if definition.browser_url:
            browser_url = definition.browser_url
            break
    health_enabled = any(item.enabled and item.health_type != "none" for item in enabled_definitions)
    latest_process = session.scalar(
        select(ProcessInstance)
        .where(ProcessInstance.application_id == application.id)
        .order_by(desc(ProcessInstance.started_at))
    )
    launch_reason = None
    if not application.enabled or application.archived:
        launch_reason = "Application is disabled or archived."
    elif not application.control_policy.get("allow_launch", True):
        launch_reason = "Launching is disabled by the control policy."
    elif not launchable:
        launch_reason = (
            "No enabled command/server launch definition. Configure one to make launch available."
        )
    elif active:
        launch_reason = "A managed process is already running."
    launch_enabled = launch_reason is None
    stop_reason = None if active else "No Mission Control-owned process is running."
    open_repo_reason = None
    if not repository_ok:
        open_repo_reason = "No existing primary repository path is configured."
    elif not editor_ok:
        open_repo_reason = editor_reason
    actions = ApplicationActions(
        launch=ActionState(enabled=launch_enabled, reason=launch_reason),
        stop=ActionState(enabled=bool(active), reason=stop_reason),
        restart=ActionState(
            enabled=launchable and application.enabled and not application.archived,
            reason=launch_reason if not launchable else None,
        ),
        open_repository=ActionState(enabled=open_repo_reason is None, reason=open_repo_reason),
        open_documentation=ActionState(
            enabled=bool(documentation_path) and editor_ok,
            reason=(
                "No existing documentation path is configured."
                if not documentation_path
                else editor_reason
            ),
        ),
        open_url=ActionState(
            enabled=bool(browser_url),
            reason=None if browser_url else "No browser URL is configured for this application.",
        ),
        logs=ActionState(
            enabled=bool(latest_process and latest_process.log_path and Path(latest_process.log_path).exists()),
            reason=None
            if latest_process and latest_process.log_path and Path(latest_process.log_path).exists()
            else "No process log is available yet.",
        ),
        check_health=ActionState(
            enabled=health_enabled,
            reason=None if health_enabled else "No enabled health check is configured.",
        ),
    )
    return ApplicationRead(
        id=application.id,
        name=application.name,
        description=application.description,
        category=application.category,  # type: ignore[arg-type]
        icon=application.icon,
        tags=application.tags,
        enabled=application.enabled,
        archived=application.archived,
        pinned=application.pinned,
        display_order=application.display_order,
        repository_path=application.repository_path,
        additional_paths=application.additional_paths,
        working_directory=application.working_directory,
        documentation_paths=application.documentation_paths,
        output_paths=application.output_paths,
        integration_adapter=application.integration_adapter,
        adapter_enabled=application.adapter_enabled,
        adapter_config=application.adapter_config,
        related_projects=application.related_projects,
        related_books=application.related_books,
        outcomes=application.outcomes,
        dependencies=application.dependencies,
        control_policy=ControlPolicy(**(application.control_policy or {})),
        source=application.source,
        notes=application.notes,
        launch_definitions=[
            LaunchDefinitionRead(
                id=item.id,
                application_id=item.application_id,
                name=item.name,
                launch_type=item.launch_type,  # type: ignore[arg-type]
                executable=item.executable,
                arguments=item.arguments,
                working_directory=item.working_directory,
                env_names=item.env_names,
                browser_url=item.browser_url,
                health_type=item.health_type,  # type: ignore[arg-type]
                health_url=item.health_url,
                expected_port=item.expected_port,
                is_primary=item.is_primary,
                enabled=item.enabled,
                verified=item.verified,
                verification_note=item.verification_note,
                shutdown_behavior=item.shutdown_behavior,
            )
            for item in all_definitions
        ],
        status=status,
        actions=actions,
        last_launch_success_at=application.last_launch_success_at,
        last_launch_failure_at=application.last_launch_failure_at,
        last_failure_detail=application.last_failure_detail,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def _validate_relationships(session: Session, payload: ApplicationCreate | ApplicationUpdate) -> None:
    for project_id in payload.related_projects or []:
        if session.get(Project, project_id) is None:
            raise ValidationProblem(f"Related project does not exist: {project_id}")
    for book_id in payload.related_books or []:
        if session.get(Book, book_id) is None:
            raise ValidationProblem(f"Related book does not exist: {book_id}")
    for outcome_id in payload.outcomes or []:
        if session.get(Outcome, outcome_id) is None:
            raise ValidationProblem(f"Outcome does not exist: {outcome_id}")


def _add_launch_definitions(
    session: Session, application_id: str, definitions: list[LaunchDefinitionInput]
) -> None:
    seen: set[str] = set()
    primary_assigned = False
    for definition in definitions:
        launch_id = definition.id or f"{application_id}-launch-{uuid.uuid4().hex[:8]}"
        if launch_id in seen:
            raise ValidationProblem(f"Duplicate launch definition id: {launch_id}")
        seen.add(launch_id)
        is_primary = definition.is_primary and not primary_assigned
        primary_assigned = primary_assigned or is_primary
        session.add(
            LaunchDefinition(
                id=launch_id,
                application_id=application_id,
                name=definition.name,
                launch_type=definition.launch_type,
                executable=definition.executable,
                arguments=definition.arguments,
                working_directory=definition.working_directory,
                env_names=definition.env_names,
                browser_url=definition.browser_url,
                health_type=definition.health_type,
                health_url=definition.health_url,
                expected_port=definition.expected_port,
                is_primary=is_primary,
                enabled=definition.enabled,
                verified=definition.verified,
                verification_note=definition.verification_note,
                shutdown_behavior=definition.shutdown_behavior,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
        )
    if definitions and not primary_assigned:
        first_id = definitions[0].id or None
        if first_id:
            existing = session.get(LaunchDefinition, first_id)
            if existing:
                existing.is_primary = True


def create_application(session: Session, payload: ApplicationCreate) -> Application:
    _validate_relationships(session, payload)
    app_id = payload.id or slugify(payload.name)
    if session.get(Application, app_id) is not None:
        raise Conflict(f"Application already exists: {app_id}")
    app = Application(
        id=app_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        icon=payload.icon,
        tags=payload.tags,
        enabled=payload.enabled,
        archived=False,
        pinned=payload.pinned,
        display_order=payload.display_order,
        repository_path=payload.repository_path,
        additional_paths=payload.additional_paths,
        working_directory=payload.working_directory,
        documentation_paths=payload.documentation_paths,
        output_paths=payload.output_paths,
        integration_adapter=payload.integration_adapter,
        adapter_enabled=payload.adapter_enabled,
        adapter_config=payload.adapter_config,
        related_projects=payload.related_projects,
        related_books=payload.related_books,
        outcomes=payload.outcomes,
        dependencies=payload.dependencies,
        control_policy=payload.control_policy.model_dump(),
        source="user",
        notes=payload.notes,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    session.add(app)
    _add_launch_definitions(session, app_id, payload.launch_definitions)
    record_activity(
        session,
        event_type="system",
        title=f"Registered application: {payload.name}",
        detail="Created through the application registry.",
        application_id=app_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return app


def update_application(session: Session, app_id: str, payload: ApplicationUpdate) -> Application:
    app = session.get(Application, app_id)
    if app is None:
        raise NotFound("Application not found")
    _validate_relationships(session, payload)
    updates = payload.model_dump(exclude_unset=True, exclude={"launch_definitions"})
    if "control_policy" in updates and updates["control_policy"] is not None:
        updates["control_policy"] = payload.control_policy.model_dump() if payload.control_policy else {}
    for key, value in updates.items():
        if key == "archived" and value is None:
            continue
        setattr(app, key, value)
    app.source = "user"
    app.updated_at = now_iso()
    if payload.launch_definitions is not None:
        for definition in session.scalars(
            select(LaunchDefinition).where(LaunchDefinition.application_id == app_id)
        ).all():
            session.delete(definition)
        session.flush()
        _add_launch_definitions(session, app_id, payload.launch_definitions)
    record_activity(
        session,
        event_type="system",
        title=f"Updated application: {app.name}",
        detail="Configuration changed through the application registry.",
        application_id=app_id,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return app


def reorder_applications(session: Session, ordered_ids: list[str]) -> None:
    for index, app_id in enumerate(ordered_ids):
        app = session.get(Application, app_id)
        if app:
            app.display_order = (index + 1) * 10
            app.updated_at = now_iso()
    record_activity(
        session,
        event_type="system",
        title="Application display order updated",
        detail="The user changed the application ordering.",
        source="mission-control",
        provenance="user",
    )
