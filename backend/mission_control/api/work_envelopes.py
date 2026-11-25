"""WORK-OUTCOME-01 W8: prospective work envelope API.

Registration binds pre-authorized intent before execution; linkage
records execution evidence after the fact. Neither performs execution,
models, or repository changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-envelopes", tags=["work-envelopes"])


def _service(request: Request):
    service = getattr(request.app.state, "envelope_service", None)
    if service is None:
        raise HTTPException(status_code=503,
                            detail="Envelope service is not available")
    return service


@router.post("")
def register_envelope(request: Request,
                      payload: dict | None = None) -> dict:
    body = payload or {}
    try:
        requirement_ids = body.get("requirement_ids") or []
        repositories = body.get("repositories") or []
        findings = body.get("originating_findings") or []
        if not all(isinstance(x, list) for x in (requirement_ids,
                                                 repositories, findings)):
            raise ValueError("list fields must be lists")
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid envelope body")
    out = _service(request).register_envelope(
        episode_id=str(body.get("episode_id") or ""),
        objective_id=str(body.get("objective_id") or ""),
        requirement_ids=[str(x) for x in requirement_ids],
        repositories=[str(x) for x in repositories],
        scope=str(body.get("scope") or ""),
        acceptance_criteria=str(body.get("acceptance_criteria") or ""),
        acceptance_policy_ref=str(body.get("acceptance_policy_ref")
                                  or "w6b-v1"),
        programme_id=str(body.get("programme_id") or "WORK-OUTCOME-01"),
        stage_id=str(body.get("stage_id") or "W8"),
        parent_work_id=(str(body.get("parent_work_id") or "") or None),
        originating_findings=[str(x) for x in findings],
        authorization_proposal_id=(str(body.get(
            "authorization_proposal_id") or "") or None),
        authorization_note=str(body.get("authorization_note") or ""),
        actor=str(body.get("actor") or ""))
    if out.get("status") in ("rejected", "unknown_episode"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.get("")
def list_envelopes(request: Request,
                   episode_id: str | None = Query(default=None,
                                                  max_length=160),
                   limit: int = Query(default=100, ge=1, le=500)) -> dict:
    return {"envelopes": _service(request).list_envelopes(
        episode_id=episode_id, limit=limit)}


@router.post("/{envelope_id}/executions")
def link_execution(request: Request, envelope_id: str,
                   payload: dict | None = None) -> dict:
    if len(envelope_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown envelope")
    body = payload or {}
    out = _service(request).link_execution(
        envelope_id=envelope_id,
        route=str(body.get("route") or "manual"),
        external_ref=str(body.get("external_ref") or ""),
        model=str(body.get("model") or ""),
        session_id=str(body.get("session_id") or ""),
        commit_sha=str(body.get("commit_sha") or ""),
        test_receipt_ref=str(body.get("test_receipt_ref") or ""),
        review_ref=str(body.get("review_ref") or ""),
        status=str(body.get("status") or "handed_off"),
        proposal_id=str(body.get("proposal_id") or ""))
    if out.get("status") in ("rejected", "unknown_envelope"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.get("/{envelope_id}/size")
def envelope_size(request: Request, envelope_id: str) -> dict:
    if len(envelope_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown envelope")
    out = _service(request).envelope_size_bytes(envelope_id)
    if out.get("status") == "unknown_envelope":
        raise HTTPException(status_code=404, detail="No such envelope")
    return out
