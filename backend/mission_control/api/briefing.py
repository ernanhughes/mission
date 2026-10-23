"""Daily briefing API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.briefing.service import generate_briefing, latest_briefing
from mission_control.schemas import BriefingRead, BriefingRequest

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


@router.get("", response_model=BriefingRead | None)
def get_briefing(session: Session = Depends(get_session)) -> BriefingRead | None:
    return latest_briefing(session)


@router.post("/generate", response_model=BriefingRead)
async def create_briefing(payload: BriefingRequest, request: Request) -> BriefingRead:
    return await generate_briefing(request.app.state.database, use_ai=payload.use_ai)
