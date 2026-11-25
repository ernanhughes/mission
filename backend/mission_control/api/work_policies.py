"""WORK-OUTCOME-01 W9E: project policy API (read + explicit human change)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/work-evaluation/policies", tags=["work-policies"])


def _service(request: Request):
    service = getattr(request.app.state, "policy_service", None)
    if service is None:
        raise HTTPException(status_code=503,
                            detail="Policy service is not available")
    return service


@router.get("")
def list_policies(request: Request) -> dict:
    return _service(request).list()


@router.post("")
def set_policy(request: Request, payload: dict | None = None) -> dict:
    body = payload or {}
    try:
        lookback = int(body.get("lookback_days") or 30)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid lookback_days")
    out = _service(request).set(
        str(body.get("project_key") or "")[:200],
        str(body.get("level") or "")[:32],
        lookback_days=lookback,
        actor=str(body.get("actor") or "")[:80])
    if out.get("status") == "rejected":
        raise HTTPException(status_code=422, detail=out.get("error"))
    return out


@router.get("/gate/{capability}")
def gate(request: Request, capability: str,
         project_key: str = Query(..., max_length=200)) -> dict:
    return _service(request).gate(project_key, capability)


@router.get("/project/{project_key:path}")
def get_policy(request: Request, project_key: str) -> dict:
    if len(project_key) > 200:
        raise HTTPException(status_code=422, detail="Unknown project")
    return _service(request).get(project_key)
