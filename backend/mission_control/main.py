"""Mission Control FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from mission_control import __version__
from mission_control.adapters.service import AdapterService
from mission_control.api import adapters, applications, briefing, dashboard, discovery, health, processes, projects, settings as settings_api
from mission_control.config import RuntimeSettings
from mission_control.core.errors import MissionControlError
from mission_control.core.logging import configure_logging
from mission_control.core.paths import is_within
from mission_control.core.security import OriginGuardMiddleware, SecurityHeadersMiddleware
from mission_control.discovery.service import DiscoveryService
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.processes.manager import ProcessManager
from mission_control.projects.service import refresh_repositories

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
        apply_migrations(database)
        with database.session() as session:
            seed_defaults(session, settings)
        process_manager = ProcessManager(database, settings)
        adapter_service = AdapterService(database)
        adapter_service.ensure_statuses()
        discovery_service = DiscoveryService(database)
        app.state.database = database
        app.state.settings = settings
        app.state.process_manager = process_manager
        app.state.adapter_service = adapter_service
        app.state.discovery = discovery_service
        await process_manager.reconcile_startup()
        refresh_task: asyncio.Task[None] | None = None
        if settings.start_monitor:
            refresh_task = asyncio.create_task(_startup_refresh(app), name="mission-control-startup-refresh")
            process_manager.start_monitor()
        logger.info("Mission Control %s ready on http://%s:%s", __version__, settings.host, settings.port)
        try:
            yield
        finally:
            if refresh_task:
                refresh_task.cancel()
                try:
                    await refresh_task
                except (asyncio.CancelledError, Exception):
                    pass
            await process_manager.shutdown()
            try:
                await discovery_service.shutdown()
            except Exception:
                logger.exception("Discovery shutdown failed")
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
    async def mission_control_error_handler(_request: Request, exc: MissionControlError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
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
    app.include_router(discovery.router)
    app.include_router(adapters.router)
    app.include_router(briefing.router)
    app.include_router(settings_api.router)

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
