"""WORK-OUTCOME-01 W1: observation service HTTP surface.

Read-only GETs plus one bounded POST that runs a deterministic observation
pass. Never starts a model call. Follows ``api/git_activity.py`` conventions:
opening endpoints performs no inference; explicit validation errors are 422.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-observation", tags=["work-observation"])


def _service(request: Request):
    service = getattr(request.app.state, "work_observation", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Work observation is not available")
    return service


@router.get("/status")
def wo_status(request: Request) -> dict:
    """Source health + store/channel checkpoint state. No model calls."""
    return _service(request).health()


@router.post("/runs")
def wo_start_run(request: Request, payload: dict | None = None) -> dict:
    """Run one bounded deterministic observation pass (sync, bounded)."""
    body = payload or {}
    try:
        since_ms = body.get("since_ms")
        since = int(since_ms) if since_ms is not None else None
        limit_messages = max(1, min(int(body.get("limit_messages", 2000)), 20000))
        limit_sessions = max(1, min(int(body.get("limit_sessions", 500)), 5000))
        project_contains = body.get("project_contains")
        if project_contains is not None:
            project_contains = str(project_contains)[:200]
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid run parameters")
    from mission_control.work_observation.policies import require_scope_allowed

    require_scope_allowed(request, project_contains, "observe")
    return _service(request).run_observation(
        since_ms=since, limit_messages=limit_messages,
        limit_sessions=limit_sessions, project_contains=project_contains)


@router.get("/runs")
def wo_list_runs(request: Request,
                 limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return {"runs": _service(request).list_runs(limit=limit)}


@router.get("/runs/{run_id}")
def wo_get_run(request: Request, run_id: str) -> dict:
    if len(run_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown run")
    run = _service(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/checkpoints")
def wo_checkpoints(request: Request) -> dict:
    return {"checkpoints": _service(request).get_checkpoints()}


@router.get("/signals")
def wo_signals(request: Request,
               signal_type: str | None = Query(default=None, max_length=64),
               source_ref: str | None = Query(default=None, max_length=200),
               limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"signals": _service(request).query_signals(
        signal_type=signal_type, source_ref=source_ref, limit=limit)}


@router.get("/coverage")
def wo_coverage(request: Request) -> dict:
    """Source inventory vs stored progress. Index-only; no model calls."""
    return _service(request).coverage()
