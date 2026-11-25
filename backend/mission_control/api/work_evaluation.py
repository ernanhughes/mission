"""WORK-OUTCOME-01 W4: evaluation read surface + bounded evaluation runs.

Read-only GETs plus one bounded POST. No UI, no auto-execution, no outcome
mutation beyond new assessment rows. Opening a page never triggers inference.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-evaluation", tags=["work-evaluation"])


def _service(request: Request):
    service = getattr(request.app.state, "evaluation_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Evaluation service is not available")
    return service


@router.post("/runs")
def ev_start_run(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    episode_id = str(body.get("episode_id") or "")[:160]
    if not episode_id:
        raise HTTPException(status_code=422, detail="episode_id is required")
    try:
        semantic = bool(body.get("semantic", True))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid run parameters")
    from mission_control.work_observation.policies import require_scope_allowed

    service = _service(request)
    # W9 review F3: manual evaluation is policy-gated too. The scope is
    # the episode's own project, resolved from the stored episode.
    project_key = ""
    try:
        rows = service.overview(limit=200).get("episodes", [])
        project_key = next((r["project_key"] for r in rows
                            if r["id"] == episode_id), "")
    except Exception:
        project_key = ""
    require_scope_allowed(request, project_key, "evaluate_manual")
    if semantic:
        require_scope_allowed(request, project_key,
                              "evaluate_semantic_manual")
    return service.evaluate_episode(episode_id, semantic=semantic)


@router.get("/episodes/{episode_id}")
def ev_episode(request: Request, episode_id: str) -> dict:
    if len(episode_id) > 160:
        raise HTTPException(status_code=422, detail="Unknown episode")
    assessment = _service(request).get_episode_assessment(episode_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="No assessment for episode")
    return {"assessment": assessment,
            "requirements": _service(request).list_req_assessments(episode_id),
            "claims": _service(request).list_claim_verifications(episode_id),
            "findings": _service(request).list_findings(episode_id=episode_id)}


@router.get("/findings")
def ev_findings(request: Request,
                episode_id: str | None = Query(default=None, max_length=160),
                status: str | None = Query(default=None, max_length=32),
                limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"findings": _service(request).list_findings(
        episode_id=episode_id, status=status, limit=limit)}


@router.get("/findings/groups")
def ev_finding_groups(request: Request) -> dict:
    """W6B computed finding groups (presentation layer; members preserved)."""
    return {"groups": _service(request).finding_groups()}


@router.post("/findings/groups/runs")
def ev_persist_groups(request: Request) -> dict:
    """W6B recorded grouping pass (idempotent). Manual trigger only."""
    return _service(request).persist_groups()


@router.post("/findings/reconcile-severity")
def ev_reconcile_severity(request: Request) -> dict:
    """W6B recorded w6b-v1 severity pass (manual trigger only)."""
    return _service(request).reconcile_severity()


@router.post("/findings/reconcile-resolved")
def ev_reconcile_resolved(request: Request, payload: dict | None = None) -> dict:
    """W6D §21: close findings resolved by new evidence (manual trigger,
    human actor + reason required per W9A cross-family review)."""
    body = payload or {}
    out = _service(request).reconcile_resolved(
        actor=str(body.get("actor") or ""),
        reason=str(body.get("reason") or ""))
    if out.get("status") == "rejected":
        raise HTTPException(status_code=422, detail=out.get("error"))
    return out


@router.post("/findings/resolve")
def ev_resolve_finding(request: Request, payload: dict | None = None) -> dict:
    """W7 §15 evidence-bound closure (manual trigger, human actor)."""
    body = payload or {}
    out = _service(request).resolve_finding(
        str(body.get("finding_id") or ""),
        closure_evidence=str(body.get("closure_evidence") or ""),
        actor=str(body.get("actor") or ""))
    if out.get("status") in ("rejected", "unknown_finding"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.post("/findings/reopen")
def ev_reopen_finding(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    out = _service(request).reopen_finding(
        str(body.get("finding_id") or ""),
        reason=str(body.get("reason") or ""),
        actor=str(body.get("actor") or ""))
    if out.get("status") in ("rejected", "unknown_finding"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.get("/eval-state")
def ev_state(request: Request,
             episode_id: str | None = Query(default=None,
                                           max_length=160)) -> dict:
    """W6C freshness + queue state per episode (read-only)."""
    return {"state": _service(request).eval_state(episode_id=episode_id)}


@router.get("/eval-queue")
def ev_queue(request: Request,
             limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"queue": _service(request).eval_queue(limit=limit)}


@router.get("/auto")
def ev_auto_get(request: Request) -> dict:
    """W6D: scheduled-evaluation flag + last run (read-only)."""
    return _service(request).get_auto()


@router.post("/auto")
def ev_auto_set(request: Request, payload: dict | None = None) -> dict:
    """W6D: enable/disable scheduled semantic evaluation. Manual trigger
    only; default off; paid budget stays zero regardless."""
    body = payload or {}
    return _service(request).set_auto(bool(body.get("enabled", False)))


@router.post("/eval-state/mark-stale")
def ev_mark_stale(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    episode_id = str(body.get("episode_id") or "")[:160]
    reason = str(body.get("reason") or "")[:64]
    if not episode_id or not reason:
        raise HTTPException(status_code=422,
                            detail="episode_id and reason are required")
    out = _service(request).mark_stale(episode_id, reason)
    if out.get("status") == "rejected":
        raise HTTPException(status_code=422, detail=out.get("error", "rejected"))
    return out


@router.get("/coverage")
def ev_coverage(request: Request,
                project_key: str | None = Query(default=None,
                                                max_length=200)) -> dict:
    return _service(request).coverage(project_key)


@router.get("/overview")
def ev_overview(request: Request,
                project_key: str | None = Query(default=None, max_length=200),
                limit: int = Query(default=100, ge=1, le=200)) -> dict:
    """Compact overview rows (single bounded read; no evaluation triggered)."""
    return _service(request).overview(project_key=project_key, limit=limit)


@router.get("/cost")
def ev_cost(request: Request) -> dict:
    return _service(request).get_cost()
