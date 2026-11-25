"""Mission Control FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from mission_control import __version__
from mission_control.adapters.service import AdapterService
from mission_control.activity_git.service import GitActivityService
from mission_control.api import (
    adapters,
    applications,
    artifact_load as artifact_load_api,
    briefing,
    cost as cost_api,
    cultivation,
    dashboard,
    discovery,
    git_activity,
    health,
    integrations as integrations_api,
    inspect as inspect_api,
    inspect_proposals as inspect_proposals_api,
    inspect_ops as inspect_ops_api,
    living_book as living_book_api,
    pipeline as pipeline_api,
    processes,
    projects,
    praxis_proposals as praxis_proposals_api,
    publication as publication_api,
    quality as quality_api,
    research as research_api,
    scripts as scripts_api,
    settings as settings_api,
    software_quality as software_quality_api,
    technical as technical_api,
    testing as testing_api,
    testing_runs as testing_runs_api,
    website_posts as website_posts_api,
    websites as websites_api,
    worker_runtime as worker_runtime_api,
    workflows as workflows_api,
    writer as writer_api,
    writer_evaluations as writer_evaluations_api,
)
from mission_control.config import RuntimeSettings, is_postgres_url
from mission_control.core.errors import MissionControlError
from mission_control.core.logging import configure_logging
from mission_control.core.paths import is_within
from mission_control.core.security import OriginGuardMiddleware, SecurityHeadersMiddleware
from mission_control.discovery.books import sync_detected_books, sync_fiction_books
from mission_control.discovery.service import DiscoveryService
from mission_control.integrations.service import IntegrationService
from mission_control.praxis_proposals.service import PraxisProposalService
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.processes.manager import ProcessManager
from mission_control.projects.service import refresh_repositories
from mission_control.research.chat_service import ResearchChatService
from mission_control.workflows.service import WorkflowService

logger = logging.getLogger(__name__)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


async def _startup_refresh(app: FastAPI) -> None:
    try:
        count = await asyncio.to_thread(refresh_repositories, app.state.database)
        logger.info("Observed Git metadata for %s repositories", count)
        await app.state.adapter_service.refresh_all(force=False)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Startup observation failed; the dashboard remains available")


async def _startup_blog_sync(app: FastAPI) -> None:
    """Best-effort live blog sync (read-only, idempotent, never fails startup).

    Blog posts behave like the Self-Hypnosis track: the filesystem is
    authoritative, the last valid observation is kept as stale when the source
    is unavailable. This runs on every startup regardless of unrelated
    repository-monitor settings; missing sources are repaired first so the
    weekly panel never reads 0 from a disconnected path.
    """
    try:
        from mission_control.cultivation import service as _cult

        def _sync_blogs() -> int:
            synced = 0
            with app.state.database.session() as session:
                _cult.repair_blog_source(session)
                for source in _cult.list_sources(session):
                    if source.kind != "hugo_blog":
                        continue
                    try:
                        _cult.sync_source(session, source.id)
                        synced += 1
                    except Exception:
                        logger.exception(
                            "Blog source sync failed for %s; kept last observation", source.id
                        )
            return synced

        synced = await asyncio.to_thread(_sync_blogs)
        if synced:
            logger.info("Synced %s blog source(s) on startup", synced)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Startup blog sync failed; kept last observations")


def create_app(runtime: RuntimeSettings | None = None) -> FastAPI:
    settings = runtime or RuntimeSettings()
    if settings.host not in LOOPBACK_HOSTS:
        raise RuntimeError(
            "Mission Control binds to loopback only. Set MISSION_CONTROL_HOST to 127.0.0.1."
        )
    configure_logging(settings)
    settings.ensure_directories()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(settings)
        try:
            database.health_check()
        except Exception as exc:
            logger.error(
                "Operational database unreachable (backend=%s url=%s): %s",
                database.backend,
                settings.redacted_database_url,
                exc,
            )
            raise RuntimeError(
                "Mission Control could not connect to the operational database. "
                "Verify MC_DSN points at the live PostgreSQL instance."
            ) from exc
        if not is_postgres_url(database.database_url) and os.environ.get("PYTEST_CURRENT_TEST") is None:
            # Production guard: never silently run the live service against a
            # local SQLite file once PostgreSQL is authoritative. Tests run
            # with tmp data_dirs under pytest and bypass this guard; the
            # migration utility opens SQLite explicitly as a read-only source.
            allow_sqlite = os.environ.get("MISSION_CONTROL_ALLOW_SQLITE") == "1"
            if not allow_sqlite:
                raise RuntimeError(
                    "MC_DSN is required for Mission Control operation. "
                    "Set MC_DSN to the PostgreSQL connection string; "
                    "SQLite is retained only for migration source and isolated tests."
                )
        try:
            schema_applied = apply_migrations(database)
        except Exception:
            logger.exception(
                "Database migration failed (backend=%s)", database.backend
            )
            raise
        logger.info(
            "Database ready backend=%s schema_applied=%s url=%s",
            database.backend,
            schema_applied,
            settings.redacted_database_url,
        )
        with database.session() as session:
            seed_defaults(session, settings)
        try:
            with database.session() as session:
                try:
                    from mission_control.writer_registry import (
                        resolve_registry_path,
                        sync_writer_books,
                    )

                    _writer_snapshot_path = resolve_registry_path(settings)
                    if _writer_snapshot_path.exists():
                        _writer_summary = sync_writer_books(
                            session, _writer_snapshot_path, create_missing=False
                        )
                        if _writer_summary.get("updated"):
                            logger.info(
                                "Writer registry repair: %s",
                                ", ".join(_writer_summary["updated"][:10]),
                            )
                except Exception:
                    logger.exception(
                        "Writer registry sync failed; existing workspaces remain available"
                    )
                detected = sync_detected_books(session, [settings.book_root])
                if detected:
                    logger.info("Detected %s book workspaces", len(detected))
                try:
                    fiction = sync_fiction_books(session, [settings.fiction_book_root])
                except Exception:
                    logger.exception(
                        "Fiction book detection failed; existing workspaces remain available"
                    )
                else:
                    if fiction:
                        logger.info("Detected %s fiction book workspaces", len(fiction))
        except Exception:
            logger.exception("Book detection failed; existing workspaces remain available")
        process_manager = ProcessManager(database, settings)
        adapter_service = AdapterService(database, settings)
        adapter_service.ensure_statuses()
        discovery_service = DiscoveryService(
            database, book_root=settings.book_root, fiction_book_root=settings.fiction_book_root
        )
        integration_service = IntegrationService(database, settings)
        workflow_service = WorkflowService(database, settings, integration_service)
        praxis_proposal_service = PraxisProposalService(database, integration_service)
        from mission_control.publication.maintenance import (
            MaintenanceService as _MaintenanceService,
        )

        maintenance_service = _MaintenanceService(database, settings, integration_service)
        research_chat = ResearchChatService(database, settings)
        git_activity_service = GitActivityService(database)
        from mission_control.quality_software.service import (
            SoftwareQualityService as _SoftwareQualityService,
        )

        software_quality_service = _SoftwareQualityService(database)
        from mission_control.opencode_cost import OpencodeCostStore as _OpencodeCostStore

        opencode_cost = _OpencodeCostStore(settings.opencode_db_path)
        app.state.database = database
        app.state.settings = settings
        app.state.process_manager = process_manager
        app.state.adapter_service = adapter_service
        app.state.discovery = discovery_service
        app.state.integration_service = integration_service
        app.state.workflow_service = workflow_service
        app.state.praxis_proposal_service = praxis_proposal_service
        app.state.maintenance_service = maintenance_service
        app.state.research_chat = research_chat
        app.state.git_activity = git_activity_service
        app.state.software_quality = software_quality_service
        app.state.opencode_cost = opencode_cost
        from mission_control.websites.service import WebsitesState as _WebsitesState

        app.state.websites = _WebsitesState()
        await process_manager.reconcile_startup()
        try:
            await _startup_blog_sync(app)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Startup blog sync failed; kept last observations")
        refresh_task: asyncio.Task[None] | None = None
        if settings.start_monitor:
            refresh_task = asyncio.create_task(
                _startup_refresh(app), name="mission-control-startup-refresh"
            )
            process_manager.start_monitor()
            # Automatic deterministic maintenance: read-only reconciliation
            # loop. Dispatch additionally requires the pipeline_auto_enabled
            # setting, so the loop is inert until explicitly enabled.
            await maintenance_service.start()
        logger.info(
            "Mission Control %s ready on http://%s:%s", __version__, settings.host, settings.port
        )
        try:
            yield
        finally:
            if refresh_task:
                refresh_task.cancel()
                try:
                    await refresh_task
                except (asyncio.CancelledError, Exception):
                    pass
            try:
                await integration_service.shutdown()
            except Exception:
                logger.exception("Integration action shutdown failed")
            try:
                await maintenance_service.stop()
            except Exception:
                logger.exception("Maintenance shutdown failed")
            await process_manager.shutdown()
            try:
                await discovery_service.shutdown()
            except Exception:
                logger.exception("Discovery shutdown failed")
            try:
                await git_activity_service.shutdown()
            except Exception:
                logger.exception("Git activity shutdown failed")
            database.dispose()

    app = FastAPI(
        title="Mission Control",
        description="Local-first control centre for an applied-AI ecosystem.",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    allowed_origins = tuple(
        {
            *settings.dev_origins,
            f"http://127.0.0.1:{settings.port}",
            f"http://localhost:{settings.port}",
        }
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(OriginGuardMiddleware, allowed_origins=allowed_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Mission-Control-Request"],
    )

    @app.exception_handler(MissionControlError)
    async def mission_control_error_handler(
        _request: Request, exc: MissionControlError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for item in exc.errors():
            details.append(
                {
                    "location": ".".join(str(part) for part in item.get("loc", [])),
                    "message": item.get("msg", "Invalid value"),
                    "type": item.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "detail": details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": message, "detail": None}},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred. Inspect the local Mission Control log.",
                    "detail": None,
                }
            },
        )

    app.include_router(health.router)
    app.include_router(dashboard.router)
    app.include_router(applications.router)
    app.include_router(processes.router)
    app.include_router(projects.router)
    app.include_router(living_book_api.router)
    app.include_router(discovery.router)
    app.include_router(cultivation.router)
    app.include_router(git_activity.router)
    app.include_router(cost_api.router)
    app.include_router(adapters.router)
    app.include_router(integrations_api.router)
    app.include_router(inspect_api.router)
    app.include_router(inspect_proposals_api.router)
    app.include_router(inspect_ops_api.router)
    app.include_router(praxis_proposals_api.router)
    app.include_router(worker_runtime_api.router)
    app.include_router(research_api.router)
    app.include_router(workflows_api.router)
    app.include_router(writer_api.router)
    app.include_router(writer_evaluations_api.router)
    app.include_router(quality_api.router)
    app.include_router(technical_api.router)
    app.include_router(testing_api.router)
    app.include_router(testing_runs_api.router)
    app.include_router(publication_api.router)
    app.include_router(pipeline_api.router)
    app.include_router(artifact_load_api.router)
    app.include_router(briefing.router)
    app.include_router(settings_api.router)
    app.include_router(scripts_api.router)
    app.include_router(websites_api.router)
    app.include_router(website_posts_api.router)
    app.include_router(software_quality_api.router)

    dist = settings.frontend_dist
    if dist.exists() and (dist / "index.html").exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_frontend(full_path: str):
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (dist / full_path).resolve(strict=False)
            if full_path and is_within(candidate, dist) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        def api_root() -> JSONResponse:
            return JSONResponse(
                {
                    "name": "Mission Control",
                    "version": __version__,
                    "message": (
                        "Frontend build not found. Run npm run build in frontend, or use the "
                        "Vite development server."
                    ),
                    "api": "/api/health",
                    "docs": "/docs",
                }
            )

    return app


app = create_app()
