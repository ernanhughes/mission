"""WORK-OUTCOME-01 W7: corrective proposal API.

Read-only GETs plus explicit POSTs. Creating, editing, or approving a
proposal never executes anything: transitions to queued/running/report
only record handoff states. Paid inference is never invoked here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-corrective", tags=["work-corrective"])


def _service(request: Request):
    service = getattr(request.app.state, "proposal_service", None)
    if service is None:
        raise HTTPException(status_code=503,
                            detail="Proposal service is not available")
    return service


@router.post("/proposals")
def create_proposal(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    try:
        finding_ids = body.get("finding_ids") or []
        if not isinstance(finding_ids, list):
            raise ValueError("finding_ids must be a list")
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid proposal body")
    out = _service(request).create_proposal(
        episode_id=str(body.get("episode_id") or ""),
        finding_ids=[str(f) for f in finding_ids],
        action_category=str(body.get("action_category") or ""),
        objective=str(body.get("objective") or ""),
        scope=str(body.get("scope") or ""),
        exclusions=str(body.get("exclusions") or ""),
        acceptance_criteria=str(body.get("acceptance_criteria") or ""),
        required_verification=str(body.get("required_verification") or ""),
        suggested_route=str(body.get("suggested_route") or "manual"),
        cost_constraints=str(body.get("cost_constraints") or ""),
        risk=str(body.get("risk") or "unknown"),
        group_id=(str(body.get("group_id") or "") or None))
    if out.get("status") == "rejected":
        raise HTTPException(status_code=422, detail=out.get("error"))
    return out


@router.get("/proposals")
def list_proposals(request: Request,
                   episode_id: str | None = Query(default=None,
                                                 max_length=160),
                   status: str | None = Query(default=None,
                                              max_length=32)) -> dict:
    return {"proposals": _service(request).list_proposals(
        episode_id=episode_id, status=status)}


@router.get("/proposals/{proposal_id}")
def get_proposal(request: Request, proposal_id: str) -> dict:
    if len(proposal_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown proposal")
    got = _service(request).get_proposal(proposal_id)
    if got is None:
        raise HTTPException(status_code=404, detail="No such proposal")
    return {"proposal": got}


@router.get("/proposals/{proposal_id}/commission")
def get_commission(request: Request, proposal_id: str) -> dict:
    if len(proposal_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown proposal")
    return _service(request).assemble_commission(proposal_id)


@router.post("/proposals/{proposal_id}/scope")
def edit_scope(request: Request, proposal_id: str,
               payload: dict | None = None) -> dict:
    if len(proposal_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown proposal")
    body = payload or {}
    out = _service(request).edit_scope(
        proposal_id,
        scope=(None if "scope" not in body else str(body.get("scope") or "")),
        exclusions=(None if "exclusions" not in body
                    else str(body.get("exclusions") or "")),
        acceptance_criteria=(None if "acceptance_criteria" not in body
                             else str(body.get("acceptance_criteria") or "")),
        objective=(None if "objective" not in body
                   else str(body.get("objective") or "")))
    if out.get("status") in ("rejected", "unknown_proposal"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.post("/proposals/{proposal_id}/transition")
def transition(request: Request, proposal_id: str,
               payload: dict | None = None) -> dict:
    if len(proposal_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown proposal")
    body = payload or {}
    out = _service(request).transition(
        proposal_id, str(body.get("to_status") or ""),
        actor=str(body.get("actor") or ""),
        reason=str(body.get("reason") or ""),
        confirm=bool(body.get("confirm", False)))
    if out.get("status") in ("rejected", "unknown_proposal"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.post("/proposals/{proposal_id}/handoff")
def record_handoff(request: Request, proposal_id: str,
                   payload: dict | None = None) -> dict:
    if len(proposal_id) > 64:
        raise HTTPException(status_code=422, detail="Unknown proposal")
    body = payload or {}
    out = _service(request).record_handoff(
        proposal_id, str(body.get("route") or "manual"),
        external_ref=str(body.get("external_ref") or ""),
        model=str(body.get("model") or ""),
        actor=str(body.get("actor") or ""),
        confirm=bool(body.get("confirm", False)))
    if out.get("status") in ("rejected", "unknown_proposal"):
        raise HTTPException(status_code=422,
                            detail=out.get("error", out.get("status")))
    return out


@router.get("/routes")
def describe_routes(request: Request) -> dict:
    return _service(request).describe_routes()
