"""WORK-OUTCOME-01 W2: episode reconstruction query surface.

Read-only GETs plus one bounded POST that runs deterministic reconstruction.
No model calls, no Activity UI changes, no completion judgements.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-episodes", tags=["work-episodes"])


def _service(request: Request):
    service = getattr(request.app.state, "episode_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Episode service is not available")
    return service


@router.post("/runs")
def ep_start_run(request: Request, payload: dict | None = None) -> dict:
    """Run one bounded deterministic reconstruction pass (sync, bounded)."""
    body = payload or {}
    try:
        project_contains = body.get("project_contains")
        if project_contains is not None:
            project_contains = str(project_contains)[:200] or None
        limit_sessions = max(1, min(int(body.get("limit_sessions", 500)), 5000))
        limit_signals = max(1, min(int(body.get("limit_signals", 20000)), 100000))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid run parameters")
    from mission_control.work_observation.policies import require_scope_allowed

    require_scope_allowed(request, project_contains, "reconstruct")
    return _service(request).run_reconstruction(
        project_contains=project_contains, limit_sessions=limit_sessions,
        limit_signals=limit_signals)


@router.get("/runs")
def ep_list_runs(request: Request,
                 limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return {"runs": _service(request).list_runs(limit=limit)}


@router.get("/runs/{run_id}")
def ep_get_run(request: Request, run_id: str) -> dict:
    if len(run_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown run")
    run = _service(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("")
def ep_list(request: Request,
            project_key: str | None = Query(default=None, max_length=200),
            kind: str | None = Query(default=None, max_length=32),
            status: str | None = Query(default=None, max_length=32),
            limit: int = Query(default=100, ge=1, le=200),
            offset: int = Query(default=0, ge=0)) -> dict:
    for value, name in ((kind, "kind"), (status, "status")):
        if value is not None and len(value) > 32:
            raise HTTPException(status_code=422, detail=f"Invalid {name}")
    return {"episodes": _service(request).list_episodes(
        project_key=project_key, kind=kind, status=status,
        limit=limit, offset=offset)}


@router.get("/unresolved")
def ep_unresolved(request: Request,
                  project_key: str = Query(default="all", max_length=200)) -> dict:
    return {"buckets": _service(request).list_unresolved(project_key)}


@router.get("/associations")
def ep_associations(request: Request,
                    episode_id: str | None = Query(default=None, max_length=160),
                    assoc_type: str | None = Query(default=None, max_length=32),
                    valid: int = Query(default=1, ge=0, le=1),
                    limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"associations": _service(request).query_associations(
        episode_id=episode_id, assoc_type=assoc_type, valid=valid, limit=limit)}


@router.get("/coverage")
def ep_coverage(request: Request,
                project_key: str | None = Query(default=None, max_length=200)) -> dict:
    return _service(request).coverage(project_key)


@router.get("/{episode_id}")
def ep_get(request: Request, episode_id: str) -> dict:
    if len(episode_id) > 160:
        raise HTTPException(status_code=422, detail="Unknown episode")
    episode = _service(request).get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode
