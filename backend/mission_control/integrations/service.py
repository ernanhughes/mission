"""Integration configuration, diagnostics and reviewed action execution."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.adapters.base import ActionContext, ActionSpec
from mission_control.adapters.service import AdapterService, get_app_adapter
from mission_control.config import RuntimeSettings
from mission_control.core.errors import (
    CapabilityUnavailable,
    Conflict,
    NotFound,
    ValidationProblem,
)
from mission_control.core.paths import (
    normalize_absolute_path,
    validate_arguments,
    validate_env_names,
    validate_executable,
)
from mission_control.integrations.store import counts_by_type
from mission_control.models import (
    AdapterStatus,
    Application,
    ExperimentWorkflow,
    IntegrationExecution,
    ProjectRepository,
    Repository,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.schemas import (
    IntegrationActionRead,
    IntegrationExecutionRead,
    IntegrationRead,
)

logger = logging.getLogger(__name__)

INTEGRATION_APPLICATIONS = ("next", "work", "cocoder")
_ALLOWED_CONFIG_KEYS = {
    "next": {"dsn_env", "sqlite_path", "limit"},
    "work": {
        "executable",
        "working_directory",
        "arguments",
        "env_names",
        "timeout_seconds",
        "limit",
    },
    "cocoder": {"executable", "artifact_dir", "artifact_paths", "env_names", "timeout_seconds"},
}
_SECRET_MARKERS = ("secret", "password", "token", "api_key", "apikey")


def _safe_config(config: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in config.items():
        if any(marker in key.casefold() for marker in _SECRET_MARKERS):
            continue
        safe[key] = value
    return safe


def _mode_for(application: Application) -> str:
    if application.id == "next":
        config = application.adapter_config or {}
        dsn_env = str(config.get("dsn_env") or "NEXT_DSN")
        import os

        return "postgres-readonly" if os.environ.get(dsn_env) else "sqlite-snapshot"
    if application.id == "work":
        return "cli-json"
    return "cli-artifact"


def action_read(action: ActionSpec) -> IntegrationActionRead:
    return IntegrationActionRead(
        id=action.id,
        title=action.title,
        description=action.description,
        risk=action.risk,
        capability=action.capability,
        approval_required=action.approval_required,
        side_effect=action.side_effect,
        parameters_schema=action.parameters_schema,
        enabled=action.enabled,
        unavailable_reason=action.unavailable_reason,
    )


def _execution_read(session: Session, execution: IntegrationExecution) -> IntegrationExecutionRead:
    application = session.get(Application, execution.application_id)
    return IntegrationExecutionRead(
        id=execution.id,
        application_id=execution.application_id,
        application_name=application.name if application else None,
        action_id=execution.action_id,
        parameters=execution.parameters,
        status=execution.status,
        risk=execution.risk,
        approval_required=execution.approval_required,
        approved_at=execution.approved_at,
        started_at=execution.started_at,
        ended_at=execution.ended_at,
        exit_code=execution.exit_code,
        output=execution.output,
        error=execution.error,
        result=execution.result,
        artifact_ref=execution.artifact_ref,
        created_at=execution.created_at,
    )


class IntegrationService:
    def __init__(self, database: Database, settings: RuntimeSettings) -> None:
        self.database = database
        self.settings = settings
        self.adapter_service = AdapterService(database, settings)
        self._tasks: set[asyncio.Task[None]] = set()

    def list_integrations(self) -> list[IntegrationRead]:
        self.adapter_service.ensure_statuses()
        with self.database.session() as session:
            applications = session.scalars(
                select(Application)
                .where(Application.id.in_(INTEGRATION_APPLICATIONS))
                .order_by(Application.display_order)
            ).all()
            return [self._read(session, application) for application in applications]

    def read_integration(self, application_id: str) -> IntegrationRead:
        with self.database.session() as session:
            application = session.get(Application, application_id)
            if application is None or application_id not in INTEGRATION_APPLICATIONS:
                raise NotFound("Integration not found")
            return self._read(session, application)

    def _read(self, session: Session, application: Application) -> IntegrationRead:
        adapter = get_app_adapter(application.integration_adapter or "")
        status = session.get(AdapterStatus, f"adapter-app-{application.id}")
        actions = adapter.actions if adapter else []
        available = bool(status and status.available and application.adapter_enabled)
        detail = status.detail if status else "Integration has not been refreshed yet."
        error = status.error if status else None
        if not application.adapter_enabled:
            detail = "Integration is disabled in the application registry."
        return IntegrationRead(
            application_id=application.id,
            name=application.name,
            adapter=application.integration_adapter or "",
            protocol_version=adapter.protocol_version if adapter else "unknown",
            mode=_mode_for(application),
            enabled=application.adapter_enabled,
            available=available,
            detail=detail,
            error=error,
            capabilities=adapter.capabilities if adapter else [],
            actions=[action_read(action) for action in actions],
            last_checked_at=status.last_checked_at if status else None,
            resource_counts=counts_by_type(session, application.id),
            repository_path=application.repository_path,
            config=_safe_config(application.adapter_config or {}),
            repositories=self._repositories(session, application),
        )

    def _repositories(self, session: Session, application: Application) -> list[dict[str, str]]:
        if application.id != "cocoder":
            return []
        repositories: dict[str, dict[str, str]] = {}
        if self.settings.repo_root.is_dir():
            repositories[str(self.settings.repo_root)] = {
                "path": str(self.settings.repo_root),
                "name": "Mission Control",
                "source": "Mission Control",
            }
        for app in session.scalars(select(Application).order_by(Application.name)).all():
            if app.repository_path and Path(app.repository_path).is_dir():
                repositories[app.repository_path] = {
                    "path": app.repository_path,
                    "name": app.name,
                    "source": "Application",
                }
        for path, name in session.execute(
            select(Repository.path, Repository.name)
            .join(ProjectRepository, ProjectRepository.repository_id == Repository.id)
            .order_by(Repository.name)
        ).all():
            if Path(path).is_dir():
                repositories[path] = {"path": path, "name": name, "source": "Project"}
        return sorted(repositories.values(), key=lambda item: item["name"].casefold())

    def update_config(
        self, application_id: str, config: dict[str, Any], enabled: bool | None
    ) -> IntegrationRead:
        if application_id not in INTEGRATION_APPLICATIONS:
            raise NotFound("Integration not found")
        if not isinstance(config, dict):
            raise ValidationProblem("adapter_config must be a JSON object")
        unknown = set(config) - _ALLOWED_CONFIG_KEYS[application_id]
        if unknown:
            raise ValidationProblem(
                f"Unknown integration configuration fields: {', '.join(sorted(unknown))}"
            )
        cleaned = dict(config)
        if "limit" in cleaned:
            try:
                cleaned["limit"] = max(1, min(int(cleaned["limit"]), 500))
            except (TypeError, ValueError) as exc:
                raise ValidationProblem("limit must be an integer") from exc
        if "timeout_seconds" in cleaned:
            try:
                cleaned["timeout_seconds"] = max(5, min(int(cleaned["timeout_seconds"]), 300))
            except (TypeError, ValueError) as exc:
                raise ValidationProblem("timeout_seconds must be an integer") from exc
        if "executable" in cleaned:
            cleaned["executable"] = validate_executable(
                str(cleaned["executable"] or ""), field="integration executable"
            ) or ""
        if "working_directory" in cleaned and cleaned["working_directory"]:
            cleaned["working_directory"] = normalize_absolute_path(
                str(cleaned["working_directory"]), field="integration working directory"
            )
        if "arguments" in cleaned:
            cleaned["arguments"] = validate_arguments(cleaned["arguments"])
        if "env_names" in cleaned:
            cleaned["env_names"] = validate_env_names(cleaned["env_names"])
        if "artifact_dir" in cleaned and cleaned["artifact_dir"]:
            value = str(cleaned["artifact_dir"])
            if value.startswith(("/", "\\")) or ".." in Path(value).parts:
                raise ValidationProblem("artifact_dir must be a relative safe path or absolute path")
            if Path(value).is_absolute():
                cleaned["artifact_dir"] = normalize_absolute_path(
                    value, field="artifact directory"
                )
        if "artifact_paths" in cleaned:
            if not isinstance(cleaned["artifact_paths"], list):
                raise ValidationProblem("artifact_paths must be a list")
            cleaned["artifact_paths"] = [
                normalize_absolute_path(str(path), field="artifact path")
                for path in cleaned["artifact_paths"]
                if str(path).strip()
            ]
        with self.database.session() as session:
            application = session.get(Application, application_id)
            if application is None:
                raise NotFound("Integration not found")
            application.adapter_config = cleaned
            if enabled is not None:
                application.adapter_enabled = enabled
            application.updated_at = now_iso()
            record_activity(
                session,
                event_type="system",
                title=f"Integration configured: {application.name}",
                detail="Integration settings changed; no source repository or database was modified.",
                application_id=application_id,
                source="mission-control",
                provenance="user",
            )
            session.flush()
            return self._read(session, application)

    async def refresh(self, application_id: str) -> IntegrationRead:
        if application_id not in INTEGRATION_APPLICATIONS:
            raise NotFound("Integration not found")
        await self.adapter_service.refresh_application(application_id)
        return self.read_integration(application_id)

    async def test_connection(self, application_id: str) -> IntegrationRead:
        integration = await self.refresh(application_id)
        return integration

    # --------------------------------------------------------------- actions
    def list_executions(
        self, application_id: str | None = None, limit: int = 50
    ) -> list[IntegrationExecutionRead]:
        with self.database.session() as session:
            statement = select(IntegrationExecution).order_by(
                desc(IntegrationExecution.created_at)
            ).limit(max(1, min(limit, 200)))
            if application_id:
                statement = statement.where(
                    IntegrationExecution.application_id == application_id
                )
            return [_execution_read(session, row) for row in session.scalars(statement).all()]

    def get_execution(self, execution_id: str) -> IntegrationExecutionRead:
        with self.database.session() as session:
            execution = session.get(IntegrationExecution, execution_id)
            if execution is None:
                raise NotFound("Integration execution not found")
            return _execution_read(session, execution)

    def _action_context(
        self, session: Session, application: Application
    ) -> ActionContext:
        allowed_paths = {
            path
            for path in session.scalars(select(Application.repository_path)).all()
            if path
        }
        allowed_paths.update(
            path
            for path in session.scalars(
                select(Repository.path).join(
                    ProjectRepository,
                    ProjectRepository.repository_id == Repository.id,
                )
            ).all()
            if path
        )
        allowed_paths.update(
            path
            for path in session.scalars(
                select(ExperimentWorkflow.repository_path)
            ).all()
            if path
        )
        # Mission Control may review its own repository; this is an
        # explicitly known path, not browser-supplied.
        allowed_paths.add(str(self.settings.repo_root))
        return ActionContext(
            application_id=application.id,
            data_dir=self.settings.data_dir,
            allowed_repository_paths=sorted(allowed_paths),
            application_repository_path=application.repository_path,
            config=dict(application.adapter_config or {}),
        )

    async def start_action(
        self,
        application_id: str,
        action_id: str,
        parameters: dict[str, Any],
        *,
        confirm: bool,
    ) -> IntegrationExecutionRead:
        if application_id not in INTEGRATION_APPLICATIONS:
            raise NotFound("Integration not found")
        with self.database.session() as session:
            application = session.get(Application, application_id)
            if application is None:
                raise NotFound("Integration not found")
            if not application.adapter_enabled:
                raise CapabilityUnavailable("Integration is disabled")
            adapter = get_app_adapter(application.integration_adapter or "")
            action = next((item for item in (adapter.actions if adapter else []) if item.id == action_id), None)
            if action is None:
                raise NotFound("Integration action not found")
            if not action.enabled:
                raise CapabilityUnavailable(
                    "This action is not enabled", detail=action.unavailable_reason
                )
            if action.approval_required and not confirm:
                raise Conflict("This action requires explicit confirmation")
            active = session.scalar(
                select(IntegrationExecution).where(
                    IntegrationExecution.application_id == application_id,
                    IntegrationExecution.action_id == action_id,
                    IntegrationExecution.status.in_(["queued", "running"]),
                )
            )
            if active:
                raise Conflict("This integration action is already running")
            _validate_parameters(action.parameters_schema, parameters)
            try:
                adapter.validate_action(action_id, parameters, self._action_context(session, application))
            except ValueError as exc:
                raise ValidationProblem(str(exc)) from exc
            execution = IntegrationExecution(
                id=f"exec-{uuid.uuid4().hex[:16]}",
                application_id=application_id,
                action_id=action_id,
                parameters=parameters,
                status="queued",
                risk=action.risk,
                approval_required=action.approval_required,
                approved_at=now_iso() if confirm else None,
                created_at=now_iso(),
                result={},
            )
            session.add(execution)
            session.flush()
            result = _execution_read(session, execution)
        task = asyncio.create_task(
            self._run_action(execution.id), name=f"integration-action-{execution.id}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return result

    async def _run_action(self, execution_id: str) -> None:
        try:
            with self.database.session() as session:
                execution = session.get(IntegrationExecution, execution_id)
                if execution is None:
                    return
                application = session.get(Application, execution.application_id)
                if application is None:
                    execution.status = "failed"
                    execution.error = "Application was removed"
                    execution.ended_at = now_iso()
                    return
                adapter = get_app_adapter(application.integration_adapter or "")
                action = next(
                    (item for item in (adapter.actions if adapter else []) if item.id == execution.action_id),
                    None,
                )
                if adapter is None or action is None:
                    execution.status = "failed"
                    execution.error = "Adapter or action is no longer available"
                    execution.ended_at = now_iso()
                    return
                execution.status = "running"
                execution.started_at = now_iso()
                session.flush()
                parameters = dict(execution.parameters or {})
                context = self._action_context(session, application)
            action_result = await adapter.execute_action(
                action.id, parameters, context
            )
            with self.database.session() as session:
                execution = session.get(IntegrationExecution, execution_id)
                if execution is None:
                    return
                execution.status = action_result.status
                execution.output = action_result.output[-20_000:]
                execution.error = None if action_result.status == "succeeded" else (
                    action_result.output[-2000:] or "Integration action failed"
                )
                execution.exit_code = action_result.exit_code
                execution.result = action_result.result
                execution.artifact_ref = action_result.artifact_ref
                execution.ended_at = now_iso()
                record_activity(
                    session,
                    event_type="integration_action",
                    title=f"{action.title}: {execution.status}",
                    detail=action_result.output[-2000:] or action.description,
                    application_id=execution.application_id,
                    source="mission-control",
                    provenance="verified_observation",
                    metadata={
                        "action_id": action.id,
                        "execution_id": execution.id,
                        "risk": action.risk,
                        "artifact_ref": action_result.artifact_ref,
                    },
                )
            if action_result.status == "succeeded":
                try:
                    await self.adapter_service.refresh_application(application.id)
                except Exception:
                    logger.exception("Post-action integration refresh failed for %s", application.id)
        except Exception as exc:
            logger.exception("Integration action failed: %s", execution_id)
            with self.database.session() as session:
                execution = session.get(IntegrationExecution, execution_id)
                if execution:
                    execution.status = "failed"
                    execution.error = f"{exc.__class__.__name__}: {str(exc)[:1500]}"
                    execution.ended_at = now_iso()
                    record_activity(
                        session,
                        event_type="integration_action",
                        title=f"Integration action failed: {execution.action_id}",
                        detail=execution.error,
                        application_id=execution.application_id,
                        source="mission-control",
                        provenance="verified_observation",
                        metadata={"execution_id": execution.id, "risk": execution.risk},
                    )

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        with self.database.session() as session:
            for execution in session.scalars(
                select(IntegrationExecution).where(
                    IntegrationExecution.status.in_(["queued", "running"])
                )
            ).all():
                execution.status = "failed"
                execution.error = "Mission Control stopped before the action completed"
                execution.ended_at = now_iso()


def _validate_parameters(schema: dict[str, Any], parameters: dict[str, Any]) -> None:
    if not isinstance(parameters, dict):
        raise ValidationProblem("Action parameters must be an object")
    properties = schema.get("properties") or {}
    required = list(schema.get("required") or [])
    if schema.get("additionalProperties") is False:
        unknown = set(parameters) - set(properties)
        if unknown:
            raise ValidationProblem(
                f"Unknown action parameters: {', '.join(sorted(unknown))}"
            )
    for key in required:
        if key not in parameters:
            raise ValidationProblem(f"Missing required action parameter: {key}")
    for key, value in parameters.items():
        spec = properties.get(key) or {}
        kind = spec.get("type")
        if kind == "string" and not isinstance(value, str):
            raise ValidationProblem(f"Action parameter '{key}' must be a string")
        if kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValidationProblem(f"Action parameter '{key}' must be an integer")
            if "minimum" in spec and value < spec["minimum"]:
                raise ValidationProblem(f"Action parameter '{key}' is below its minimum")
            if "maximum" in spec and value > spec["maximum"]:
                raise ValidationProblem(f"Action parameter '{key}' is above its maximum")
        if kind == "boolean" and not isinstance(value, bool):
            raise ValidationProblem(f"Action parameter '{key}' must be a boolean")
