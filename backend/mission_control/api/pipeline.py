"""Book production pipeline API (MC-BOOK-PIPELINE-01, M1).

Read-only projection of stored Writer evidence onto books, chapters, and
production stages. No execution, no writes, no invented results.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.publication import pipeline as _pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/stages")
def list_pipeline_stages() -> dict:
    """Versioned stage registry. No book I/O."""
    return _pipeline.list_stages()


@router.get("/overview")
def get_pipeline_overview(
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Cross-book summaries (no matrices). One request, shared store parses."""
    settings = request.app.state.settings if request is not None else None
    return _pipeline.get_pipeline_overview(session, settings)


@router.get("/maintenance")
def get_maintenance_status(
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Read-only automatic-maintenance state: policy, switches, activity."""
    from mission_control.publication import maintenance as _maintenance

    settings = request.app.state.settings if request is not None else None
    database = request.app.state.database if request is not None else None
    if database is None:
        raise HTTPException(status_code=503, detail="Maintenance service is unavailable.")
    return _maintenance.maintenance_status(database, settings)


@router.post("/maintenance/enabled")
def set_maintenance_enabled(
    payload: dict,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Master switch for automatic maintenance. Records standing authorization."""
    from mission_control.publication import maintenance as _maintenance

    enabled = bool(payload.get("enabled", False))
    result = _maintenance.set_auto_enabled(session, enabled)
    session.commit()
    return {"enabled": result, "policy_version": _maintenance.MAINTENANCE_POLICY_VERSION}


@router.post("/maintenance/pause")
def set_maintenance_paused(
    payload: dict,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Pause or resume automatic maintenance for one book."""
    from mission_control.publication import maintenance as _maintenance

    project_id = str(payload.get("project_id") or "").strip()
    if not project_id:
        raise HTTPException(status_code=422, detail="project_id is required.")
    paused = _maintenance.set_book_paused(session, project_id, bool(payload.get("paused", True)))
    session.commit()
    return {"project_id": project_id, "paused_books": paused}


@router.post("/maintenance/reconcile")
async def run_maintenance_reconcile(
    payload: dict | None = None,
    request: Request = None,  # type: ignore[assignment]
) -> dict:
    """Run one reconciliation pass. ``dry_run`` previews without dispatching."""
    service = request.app.state.maintenance_service if request is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="Maintenance service is unavailable.")
    dry_run = bool((payload or {}).get("dry_run", False))
    report = await service.run_once(dry_run=dry_run)
    return report.to_dict()


@router.post("/maintenance/retry")
async def retry_automatic_stage(
    payload: dict,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Recovery control: dispatch one automatic run for a chapter-stage.

    All Writer paths resolve server-side from the registry. Only
    allowlisted automatic stages may run here.
    """
    from mission_control.publication import maintenance as _maintenance

    settings = request.app.state.settings if request is not None else None
    integration_service = request.app.state.integration_service if request is not None else None
    if integration_service is None:
        raise HTTPException(status_code=503, detail="Integration service is unavailable.")
    try:
        dispatch = _maintenance.maintenance_retry(
            session,
            settings,
            integration_service,
            project_id=str(payload.get("project_id") or ""),
            chapter_id=str(payload.get("chapter_id") or ""),
            stage_id=str(payload.get("stage_id") or "mri"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        execution = await integration_service.start_action(
            dispatch["application_id"], dispatch["action_id"], dispatch["parameters"], confirm=True
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "execution_id": execution.id,
        "status": execution.status,
        "application_id": execution.application_id,
        "action_id": execution.action_id,
    }


@router.get("/books/{project_id}")
def get_book_pipeline(
    project_id: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Book pipeline summary: chapters, per-stage summaries, compact matrix."""
    settings = request.app.state.settings if request is not None else None
    try:
        payload = _pipeline.get_book_pipeline(session, settings, project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not payload.get("known"):
        raise HTTPException(status_code=404, detail=str(payload.get("diagnostics")))
    return payload


@router.get("/books/{project_id}/stages/{stage_id}")
def get_book_stage_detail(
    project_id: str,
    stage_id: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Stage-specific evidence detail: full per-chapter cells."""
    settings = request.app.state.settings if request is not None else None
    try:
        payload = _pipeline.get_stage_detail(session, settings, project_id, stage_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown book {project_id!r} or stage {stage_id!r}. Books must "
                "be registered in the Writer registry; stages must come from "
                "GET /api/pipeline/stages."
            ),
        )
    return payload
