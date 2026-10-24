"""Adapter execution, persistence, source attribution and deduplication."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.adapters.base import Adapter, AdapterResult, AdapterTarget
from mission_control.adapters.book_adapters import (
    InferenceBookAdapter,
    LanguageBookAdapter,
    MathBookAdapter,
)
from mission_control.adapters.cocoder import CoCoderAdapter
from mission_control.adapters.next import NextAdapter
from mission_control.adapters.work import WorkAdapter
from mission_control.adapters.worker import WorkerAdapter
from mission_control.config import RuntimeSettings
from mission_control.core.errors import NotFound
from mission_control.integrations.store import upsert_resources
from mission_control.models import (
    AdapterStatus,
    Application,
    Book,
    Project,
    ProjectRepository,
    Recommendation,
    Repository,
    Setting,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.schemas import AdapterRead

logger = logging.getLogger(__name__)

_APP_ADAPTERS: dict[str, Adapter] = {
    "next": NextAdapter(),
    "cocoder": CoCoderAdapter(),
    "worker": WorkerAdapter(),
    "work": WorkAdapter(),
}
_PROJECT_ADAPTERS: dict[str, Adapter] = {
    "language": LanguageBookAdapter(),
    "inference": InferenceBookAdapter(),
    "math": MathBookAdapter(),
}

_AUTO_PROJECT_ADAPTERS = {
    "language": "language",
    "inference": "inference",
    "math": "math",
}


def get_app_adapter(name: str) -> Adapter | None:
    return _APP_ADAPTERS.get(name)


def available_app_adapters() -> dict[str, Adapter]:
    return dict(_APP_ADAPTERS)


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


class AdapterService:
    def __init__(self, database: Database, settings: RuntimeSettings | None = None) -> None:
        self.database = database
        self.settings = settings or RuntimeSettings()

    # --------------------------------------------------------------- targets
    def _application_target(self, session: Session, application: Application) -> AdapterTarget:
        paths: list[tuple[str, str]] = []
        if application.repository_path:
            paths.append((application.repository_path, "primary"))
        paths.extend((path, "additional") for path in application.additional_paths)
        return AdapterTarget(
            name=application.name,
            application_id=application.id,
            repository_paths=paths,
            documentation_paths=application.documentation_paths,
            related_project_ids=application.related_projects,
            config=application.adapter_config or {},
            data_dir=str(self.settings.data_dir),
        )

    def _project_target(self, session: Session, project: Project) -> AdapterTarget:
        rows = session.execute(
            select(Repository.path, ProjectRepository.role)
            .join(ProjectRepository, ProjectRepository.repository_id == Repository.id)
            .where(ProjectRepository.project_id == project.id)
        ).all()
        book = session.scalar(select(Book).where(Book.project_id == project.id))
        documentation: list[str] = []
        if book:
            documentation = [*book.manuscript_paths, *book.implementation_paths]
        return AdapterTarget(
            name=project.name,
            project_id=project.id,
            repository_paths=[(str(path), str(role)) for path, role in rows],
            documentation_paths=documentation,
            related_project_ids=[project.id],
        )

    # ------------------------------------------------------------- lifecycle
    def ensure_statuses(self) -> None:
        with self.database.session() as session:
            for application in session.scalars(
                select(Application).where(Application.integration_adapter.is_not(None))
            ).all():
                status_id = f"adapter-app-{application.id}"
                if session.get(AdapterStatus, status_id) is None:
                    adapter_key = application.integration_adapter or ""
                    adapter_impl = _APP_ADAPTERS.get(adapter_key)
                    session.add(
                        AdapterStatus(
                            id=status_id,
                            adapter=adapter_key,
                            application_id=application.id,
                            available=False,
                            capabilities=adapter_impl.capabilities if adapter_impl else [],
                            detail=(
                                "Integration is disabled in the application registry."
                                if not application.adapter_enabled
                                else "Integration has not been refreshed yet."
                            ),
                            last_checked_at=None,
                            stale_after_seconds=600,
                        )
                    )
            for project_id, adapter_name in _AUTO_PROJECT_ADAPTERS.items():
                project = session.get(Project, project_id)
                if project is None:
                    continue
                status_id = f"adapter-project-{project_id}"
                if session.get(AdapterStatus, status_id) is None:
                    session.add(
                        AdapterStatus(
                            id=status_id,
                            adapter=adapter_name,
                            project_id=project_id,
                            available=False,
                            capabilities=_PROJECT_ADAPTERS[adapter_name].capabilities,
                            detail="Adapter has not been refreshed yet.",
                            last_checked_at=None,
                            stale_after_seconds=600,
                        )
                    )

    async def refresh_application(self, application_id: str) -> AdapterRead:
        with self.database.session() as session:
            application = session.get(Application, application_id)
            if application is None:
                raise NotFound("Application not found")
            if not application.integration_adapter:
                raise NotFound("This application has no adapter")
            adapter_name = application.integration_adapter
            if not application.adapter_enabled:
                status = session.get(AdapterStatus, f"adapter-app-{application_id}")
                if status is None:
                    status = AdapterStatus(
                        id=f"adapter-app-{application_id}",
                        adapter=adapter_name,
                        application_id=application_id,
                        available=False,
                        capabilities=[],
                        detail="Integration is disabled in the application registry.",
                        last_checked_at=now_iso(),
                        stale_after_seconds=600,
                    )
                    session.add(status)
                status.available = False
                status.detail = "Integration is disabled in the application registry."
                status.error = None
                status.last_checked_at = now_iso()
                session.flush()
                return self._to_read(session, status)
            target = self._application_target(session, application)
            config = application.adapter_config or {}
            adapter = _APP_ADAPTERS.get(adapter_name)
            previous_available = (
                session.get(AdapterStatus, f"adapter-app-{application_id}").available
                if session.get(AdapterStatus, f"adapter-app-{application_id}")
                else None
            )
            result = await self._execute(adapter_name, adapter, target, config)
            status = self._persist_status(
                session,
                status_id=f"adapter-app-{application_id}",
                adapter_name=adapter_name,
                result=result,
                application_id=application_id,
                project_id=None,
                previous_available=previous_available,
            )
            self._ingest(session, adapter_name, application_id, None, result)
            session.flush()
            return self._to_read(session, status)

    async def refresh_project(self, project_id: str) -> AdapterRead:
        with self.database.session() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise NotFound("Project not found")
            adapter_name = _AUTO_PROJECT_ADAPTERS.get(project_id)
            if not adapter_name:
                raise NotFound("No adapter is registered for this project")
            adapter = _PROJECT_ADAPTERS.get(adapter_name)
            target = self._project_target(session, project)
            status_id = f"adapter-project-{project_id}"
            existing = session.get(AdapterStatus, status_id)
            previous_available = existing.available if existing else None
            result = await self._execute(adapter_name, adapter, target, {})
            status = self._persist_status(
                session,
                status_id=status_id,
                adapter_name=adapter_name,
                result=result,
                application_id=None,
                project_id=project_id,
                previous_available=previous_available,
            )
            self._ingest(session, adapter_name, None, project_id, result)
            session.flush()
            return self._to_read(session, status)

    async def _execute(
        self,
        adapter_name: str,
        adapter: Adapter | None,
        target: AdapterTarget,
        config: dict[str, Any],
    ) -> AdapterResult:
        if adapter is None:
            return AdapterResult(
                available=False,
                detail=f"Adapter '{adapter_name}' is configured but not implemented in this release.",
                error="Unknown adapter",
            )
        try:
            return await asyncio.wait_for(adapter.refresh(target), timeout=30.0)
        except asyncio.TimeoutError:
            return AdapterResult(
                available=False,
                detail="Adapter timed out; other applications remain available.",
                capabilities=adapter.capabilities,
                error="Adapter timed out",
            )
        except Exception as exc:  # adapters must not crash the dashboard
            logger.exception("Adapter %s failed", adapter_name)
            return AdapterResult(
                available=False,
                detail="Adapter failed; no results were imported.",
                capabilities=adapter.capabilities,
                error=str(exc)[:500],
            )

    def _persist_status(
        self,
        session: Session,
        *,
        status_id: str,
        adapter_name: str,
        result: AdapterResult,
        application_id: str | None,
        project_id: str | None,
        previous_available: bool | None,
    ) -> AdapterStatus:
        status = session.get(AdapterStatus, status_id)
        if status is None:
            status = AdapterStatus(id=status_id, adapter=adapter_name)
            session.add(status)
        status.application_id = application_id
        status.project_id = project_id
        status.available = result.available
        status.capabilities = result.capabilities
        status.detail = result.detail
        status.error = result.error
        status.last_checked_at = now_iso()
        status.stale_after_seconds = 600
        if previous_available is None or previous_available != result.available:
            record_activity(
                session,
                event_type="adapter_available" if result.available else "adapter_unavailable",
                title=f"{adapter_name}: {'available' if result.available else 'unavailable'}",
                detail=result.detail,
                application_id=application_id,
                project_id=project_id,
                source=adapter_name,
                provenance="verified_observation",
            )
        session.flush()
        return status

    def _ingest(
        self,
        session: Session,
        adapter_name: str,
        application_id: str | None,
        project_id: str | None,
        result: AdapterResult,
    ) -> int:
        created = 0
        target_key = application_id or project_id or "global"
        if application_id and result.resources:
            upsert_resources(session, application_id, result.resources)
        for observation in result.observations[:25]:
            dedupe = f"obs-{adapter_name}-{target_key}-{observation.external_id}"
            occurrence = observation.occurred_at or now_iso()
            record_activity(
                session,
                event_type="adapter_observation",
                title=observation.title[:300],
                detail=observation.detail[:4000],
                application_id=application_id,
                project_id=project_id,
                source=adapter_name,
                source_id=observation.external_id,
                evidence_ref=observation.evidence_ref,
                provenance=observation.provenance,
                occurred_at=occurrence,
                metadata=observation.metadata,
                dedupe_key=dedupe,
            )
        for seed in result.recommendations[:10]:
            dedupe = f"rec-{adapter_name}-{target_key}-{seed.external_id or hashlib.sha1(seed.title.encode()).hexdigest()[:10]}"
            existing = session.scalar(
                select(Recommendation).where(Recommendation.dedupe_key == dedupe)
            )
            if existing:
                continue
            rec_project = seed.project_id or project_id
            if rec_project and session.get(Project, rec_project) is None:
                rec_project = project_id
            recommendation = Recommendation(
                id=f"rec-{hashlib.sha1(dedupe.encode()).hexdigest()[:16]}",
                project_id=rec_project,
                title=seed.title[:300],
                rationale=seed.rationale,
                evidence=seed.evidence[:10],
                source_application=application_id,
                source_ref=seed.source_ref,
                external_id=seed.external_id,
                provenance=seed.provenance,
                review_state="pending",
                created_at=now_iso(),
                updated_at=now_iso(),
                dedupe_key=dedupe,
            )
            session.add(recommendation)
            record_activity(
                session,
                event_type="recommendation_created",
                title=f"Review suggested: {seed.title[:200]}",
                detail=seed.rationale[:3000],
                project_id=rec_project,
                application_id=application_id,
                source=adapter_name,
                source_id=seed.external_id,
                evidence_ref=seed.source_ref,
                provenance=seed.provenance,
            )
            created += 1
        return created

    # ---------------------------------------------------------------- reading
    def _to_read(self, session: Session, status: AdapterStatus) -> AdapterRead:
        application = session.get(Application, status.application_id) if status.application_id else None
        project = session.get(Project, status.project_id) if status.project_id else None
        age = _age_seconds(status.last_checked_at)
        stale = age is None or age > status.stale_after_seconds
        return AdapterRead(
            id=status.id,
            adapter=status.adapter,
            application_id=status.application_id,
            application_name=application.name if application else None,
            project_id=status.project_id,
            project_name=project.name if project else None,
            available=status.available,
            capabilities=status.capabilities,
            detail=status.detail,
            error=status.error,
            last_checked_at=status.last_checked_at,
            stale_after_seconds=status.stale_after_seconds,
            stale=stale,
        )

    def list_adapters(
        self, *, project_id: str | None = None, application_id: str | None = None
    ) -> list[AdapterRead]:
        self.ensure_statuses()
        with self.database.session() as session:
            query = select(AdapterStatus).order_by(AdapterStatus.adapter)
            if project_id:
                query = query.where(AdapterStatus.project_id == project_id)
            if application_id:
                query = query.where(AdapterStatus.application_id == application_id)
            return [self._to_read(session, status) for status in session.scalars(query).all()]

    async def refresh_all(self, *, force: bool = False) -> int:
        self.ensure_statuses()
        jobs: list[tuple[str, str]] = []
        with self.database.session() as session:
            setting = session.get(Setting, "adapters")
            interval = int(setting.value.get("refresh_interval_minutes", 10) * 60) if setting else 600
            applications = session.scalars(
                select(Application).where(
                    Application.integration_adapter.is_not(None),
                    Application.adapter_enabled.is_(True),
                )
            ).all()
            for application in applications:
                status = session.get(AdapterStatus, f"adapter-app-{application.id}")
                age = _age_seconds(status.last_checked_at) if status else None
                if force or age is None or age >= interval:
                    jobs.append(("app", application.id))
            for project_id in _AUTO_PROJECT_ADAPTERS:
                if session.get(Project, project_id) is None:
                    continue
                status = session.get(AdapterStatus, f"adapter-project-{project_id}")
                age = _age_seconds(status.last_checked_at) if status else None
                if force or age is None or age >= interval:
                    jobs.append(("project", project_id))
        for target_type, target_id in jobs:
            try:
                if target_type == "app":
                    await self.refresh_application(target_id)
                else:
                    await self.refresh_project(target_id)
            except Exception:
                logger.exception("Adapter refresh failed for %s", target_id)
        with self.database.session() as session:
            return int(
                session.query(Recommendation).filter(Recommendation.review_state == "pending").count()
            )
