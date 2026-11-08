"""Next research export and contextual local chat API."""

from __future__ import annotations

from fastapi import APIRouter, Request

from mission_control.schemas import (
    ResearchChatMessageCreate,
    ResearchChatSessionCreate,
    ResearchChatSessionRead,
    ResearchChatSessionSummary,
    ResearchContextRead,
    ResearchModelCatalogue,
)

router = APIRouter(prefix="/api/research", tags=["research"])


def _service(request: Request):
    return request.app.state.research_chat


@router.get("/models", response_model=ResearchModelCatalogue)
async def research_models(request: Request) -> ResearchModelCatalogue:
    return await _service(request).models()


@router.get(
    "/opportunities/{record_id}/export",
    response_model=ResearchContextRead,
)
def export_opportunity(record_id: str, request: Request) -> ResearchContextRead:
    return _service(request).export(record_id)


@router.get(
    "/opportunities/{record_id}/sessions",
    response_model=list[ResearchChatSessionSummary],
)
def list_opportunity_sessions(
    record_id: str, request: Request
) -> list[ResearchChatSessionSummary]:
    return _service(request).list_sessions(record_id)


@router.post(
    "/opportunities/{record_id}/sessions",
    response_model=ResearchChatSessionRead,
)
async def create_opportunity_session(
    record_id: str,
    payload: ResearchChatSessionCreate,
    request: Request,
) -> ResearchChatSessionRead:
    return await _service(request).create_session(
        record_id, payload.model_id, payload.model_route
    )


@router.get("/sessions/{session_id}", response_model=ResearchChatSessionRead)
def read_session(session_id: str, request: Request) -> ResearchChatSessionRead:
    return _service(request).get_session(session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ResearchChatSessionRead,
)
async def send_message(
    session_id: str,
    payload: ResearchChatMessageCreate,
    request: Request,
) -> ResearchChatSessionRead:
    return await _service(request).send_message(
        session_id, payload.content, payload.request_key
    )


@router.post(
    "/sessions/{session_id}/refresh-context",
    response_model=ResearchChatSessionRead,
)
def refresh_session_context(
    session_id: str, request: Request
) -> ResearchChatSessionRead:
    return _service(request).refresh_context(session_id)
