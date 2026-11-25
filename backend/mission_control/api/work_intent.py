"""WORK-OUTCOME-01 W3: intent retrieval + bounded extraction runs.

Read-only GETs plus two bounded POSTs (deterministic triage; extraction with
an explicitly enabled backend only). No W4 judgements, no Activity UI changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-intent", tags=["work-intent"])


def _service(request: Request):
    service = getattr(request.app.state, "intent_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Intent service is not available")
    return service


@router.post("/triage/runs")
def intent_triage_run(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    try:
        project_contains = body.get("project_contains")
        if project_contains is not None:
            project_contains = str(project_contains)[:200] or None
        limit = max(1, min(int(body.get("limit_sessions", 500)), 5000))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid triage parameters")
    from mission_control.work_observation.policies import require_scope_allowed

    require_scope_allowed(request, project_contains, "reconstruct")
    return _service(request).triage_scope(project_contains=project_contains,
                                         limit_sessions=limit)


@router.post("/extractions/runs")
def intent_extract_run(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    episode_id = str(body.get("episode_id") or "")[:160]
    if not episode_id:
        raise HTTPException(status_code=422, detail="episode_id is required")
    backend = str(body.get("backend") or "deterministic")[:32]
    if backend == "model":
        return _service(request).extract_episode_model(episode_id)
    if backend == "deterministic":
        return _service(request).extract_episode_deterministic(episode_id)
    raise HTTPException(status_code=422, detail="Unknown backend")


@router.post("/requirements")
def intent_record_requirement(request: Request,
                              payload: dict | None = None) -> dict:
    """W6A human-reviewed requirement recovery. Provenance is mandatory:
    no source_digest + authority_basis, no row. Never called by page loads."""
    body = payload or {}
    return _service(request).record_requirement_manual(
        episode_id=str(body.get("episode_id") or "")[:160],
        text=str(body.get("text") or ""),
        authority=str(body.get("authority") or "")[:32],
        mandatory=bool(body.get("mandatory", True)),
        kind=str(body.get("kind") or "functional")[:32],
        source_kind=str(body.get("source_kind") or "repo_doc")[:32],
        source_path=str(body.get("source_path") or "")[:500],
        source_revision=str(body.get("source_revision") or "")[:80],
        source_digest=str(body.get("source_digest") or "")[:64],
        authority_basis=str(body.get("authority_basis") or "")[:500],
        reviewer=str(body.get("reviewer") or "")[:40])


@router.post("/confirmations")
def intent_record_confirmation(request: Request,
                               payload: dict | None = None) -> dict:
    """W7 human requirement decision (confirm/amend/reject/defer/
    insufficient). Reviewer mandatory; no auto-confirm."""
    body = payload or {}
    out = _service(request).record_confirmation(
        requirement_id=str(body.get("requirement_id") or "")[:64],
        decision=str(body.get("decision") or "")[:32],
        reviewer=str(body.get("reviewer") or "")[:80],
        rationale=str(body.get("rationale") or "")[:500],
        amended_text=str(body.get("amended_text") or ""))
    if out.get("status") in ("rejected", "unknown_requirement"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.get("/confirmations")
def intent_confirmations(
        request: Request,
        requirement_id: str | None = Query(default=None, max_length=64),
        episode_id: str | None = Query(default=None, max_length=160),
        limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"confirmations": _service(request).list_confirmations(
        requirement_id=requirement_id, episode_id=episode_id, limit=limit)}


@router.get("/requirement-sources")
def intent_requirement_sources(
        request: Request,
        episode_id: str | None = Query(default=None, max_length=160),
        limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"sources": _service(request).list_requirement_sources(
        episode_id=episode_id, limit=limit)}


@router.get("/source-candidates")
def intent_source_candidates(
        request: Request,
        episode_id: str = Query(max_length=160)) -> dict:
    """W6A deterministic repo-artifact candidates (read-only, no authority
    assigned, no model calls)."""
    return _service(request).source_candidates(episode_id)


@router.get("/objectives")
def intent_objectives(request: Request,
                      episode_id: str | None = Query(default=None, max_length=160),
                      limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"objectives": _service(request).list_objectives(
        episode_id=episode_id, limit=limit)}


@router.get("/requirements")
def intent_requirements(request: Request,
                        episode_id: str | None = Query(default=None, max_length=160),
                        authority: str | None = Query(default=None, max_length=32),
                        limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"requirements": _service(request).list_requirements(
        episode_id=episode_id, authority=authority, limit=limit)}


@router.get("/claims")
def intent_claims(request: Request,
                  episode_id: str | None = Query(default=None, max_length=160),
                  limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"claims": _service(request).list_claims(
        episode_id=episode_id, limit=limit)}


@router.get("/evidence")
def intent_evidence(request: Request,
                    requirement_id: str | None = Query(default=None, max_length=64),
                    limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"evidence": _service(request).list_evidence(
        requirement_id=requirement_id, limit=limit)}


@router.get("/triage")
def intent_triage(request: Request,
                  classification: str | None = Query(default=None, max_length=40),
                  queued: int | None = Query(default=None, ge=0, le=1),
                  limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return {"triage": _service(request).list_triage(
        classification=classification, queued=queued, limit=limit)}


@router.get("/coverage")
def intent_coverage(request: Request,
                    project_key: str | None = Query(default=None,
                                                   max_length=200)) -> dict:
    return _service(request).coverage(project_key)


@router.get("/cost")
def intent_cost(request: Request) -> dict:
    return _service(request).get_cost()
