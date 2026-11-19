"""Mission Control's Living Book API.

The browser talks only to Mission. Mission maps the project to an approved ALIVE book,
adds bounded quality evidence, and proxies a small fixed ALIVE surface.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import ValidationProblem
from mission_control.living_book import improvement, service
from mission_control.living_book.client import LivingBookError, LivingBookUnavailable
from mission_control.living_book.service import LivingBookProblem

router = APIRouter(prefix="/api/living-book", tags=["living-book"])


class ConnectPreviewRequest(BaseModel):
    root: str = Field(min_length=1, max_length=512)


class ConnectRequest(ConnectPreviewRequest):
    approve: bool = False
    label: str | None = Field(default=None, max_length=120)


class ReadingRequest(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=256)
    progress: float = Field(default=0, ge=0, le=1)
    anchor: str = Field(default="", max_length=240)


class AnnotationRequest(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=256)
    quote: str = Field(min_length=1, max_length=4000)
    note: str = Field(default="", max_length=4000)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=64000)
    chapter_id: str | None = Field(default=None, max_length=256)
    scope: Literal["chapter", "book"] = "chapter"
    selection: str | None = Field(default=None, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=36)
    idempotency_key: str = Field(min_length=1, max_length=60)


class NoteRequest(BaseModel):
    regenerate: bool = False


class ImprovementLaunchRequest(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=256)
    focus: Literal["economy"] = "economy"
    intent_sha256: str = Field(min_length=64, max_length=64)
    plan_sha256: str = Field(min_length=64, max_length=64)
    criteria: str = Field(min_length=1, max_length=600)
    model: str | None = Field(default=None, max_length=80)
    use_experience: bool = False
    confirmed: bool = False
    idempotency_key: str = Field(min_length=1, max_length=60)


class ImprovementDecisionRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    proposal_sha256: str = Field(min_length=64, max_length=64)
    comment: str = Field(default="", max_length=1000)
    acknowledge_earlier_version: bool = False
    idempotency_key: str = Field(min_length=1, max_length=60)


async def _run(work):
    try:
        return await work
    except LivingBookProblem as error:
        raise HTTPException(error.status, str(error)) from None
    except LivingBookUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except LivingBookError as error:
        raise HTTPException(error.status or 502, str(error)) from None
    except ValidationProblem as error:
        raise HTTPException(422, str(error)) from None


@router.get("/projects/{project_id}")
async def status(
    project_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(service.status(session, request.app.state.settings, project_id))


@router.get("/projects/{project_id}/candidates")
async def candidates(
    project_id: str,
    session: Session = Depends(get_session),
):
    return await _run(service.candidates(session, project_id))


@router.post("/projects/{project_id}/connect/preview")
async def connect_preview(
    project_id: str,
    payload: ConnectPreviewRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.connect_preview(session, request.app.state.settings, project_id, payload.root)
    )


@router.post("/projects/{project_id}/connect")
async def connect(
    project_id: str,
    payload: ConnectRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.connect(
            session,
            request.app.state.settings,
            project_id,
            payload.root,
            approve=payload.approve,
            label=payload.label,
        )
    )


@router.get("/projects/{project_id}/book")
async def book(
    project_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(service.book_detail(session, request.app.state.settings, project_id))


@router.get("/projects/{project_id}/chapters/{chapter_id}")
async def chapter(
    project_id: str,
    chapter_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(service.chapter(session, request.app.state.settings, project_id, chapter_id))


@router.put("/projects/{project_id}/reading")
async def reading(
    project_id: str,
    payload: ReadingRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.set_reading(
            session,
            request.app.state.settings,
            project_id,
            payload.model_dump(),
        )
    )


@router.get("/projects/{project_id}/annotations")
async def annotations(
    project_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(service.annotations(session, request.app.state.settings, project_id))


@router.post("/projects/{project_id}/annotations")
async def add_annotation(
    project_id: str,
    payload: AnnotationRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.add_annotation(
            session,
            request.app.state.settings,
            project_id,
            payload.model_dump(),
        )
    )


@router.delete("/projects/{project_id}/annotations/{annotation_id}")
async def remove_annotation(
    project_id: str,
    annotation_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.remove_annotation(session, request.app.state.settings, project_id, annotation_id)
    )


@router.get("/projects/{project_id}/notes/{chapter_id}")
async def read_note(
    project_id: str,
    chapter_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.read_note(session, request.app.state.settings, project_id, chapter_id)
    )


@router.post("/projects/{project_id}/notes/{chapter_id}")
async def build_note(
    project_id: str,
    chapter_id: str,
    payload: NoteRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.note(
            session,
            request.app.state.settings,
            project_id,
            chapter_id,
            regenerate=payload.regenerate,
        )
    )


@router.post("/projects/{project_id}/ask")
async def ask(
    project_id: str,
    payload: AskRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.ask(
            session,
            request.app.state.settings,
            project_id,
            payload.model_dump(),
        )
    )


@router.get("/projects/{project_id}/conversations/{conversation_id}")
async def conversation(
    project_id: str,
    conversation_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.conversation(
            session,
            request.app.state.settings,
            project_id,
            conversation_id,
        )
    )


@router.get("/projects/{project_id}/quality")
async def quality(
    project_id: str,
    request: Request,
    chapter_id: str | None = Query(default=None, max_length=256),
    session: Session = Depends(get_session),
):
    return await _run(service.quality(session, request.app.state.settings, project_id, chapter_id))


@router.get("/projects/{project_id}/improvement/preview")
async def improvement_preview(
    project_id: str,
    request: Request,
    chapter_id: str = Query(..., min_length=1, max_length=256),
    focus: Literal["economy"] = Query(default="economy"),
    use_experience: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    return await _run(
        improvement.preview(
            session,
            request.app.state.settings,
            project_id,
            chapter_id,
            focus=focus,
            use_experience=use_experience,
        )
    )


@router.post("/projects/{project_id}/improvement")
async def start_improvement(
    project_id: str,
    payload: ImprovementLaunchRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        improvement.launch(
            session,
            request.app.state.settings,
            project_id,
            payload.model_dump(),
        )
    )


@router.get("/projects/{project_id}/improvement/{run_id}")
async def improvement_detail(
    project_id: str,
    run_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        improvement.detail(session, request.app.state.settings, project_id, run_id)
    )


@router.post("/projects/{project_id}/improvement/{run_id}/decision")
async def decide_improvement(
    project_id: str,
    run_id: str,
    payload: ImprovementDecisionRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        improvement.decide(
            session,
            request.app.state.settings,
            project_id,
            run_id,
            payload.model_dump(),
        )
    )


@router.post("/projects/{project_id}/refresh")
async def refresh(
    project_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(service.refresh(session, request.app.state.settings, project_id))


@router.post("/projects/{project_id}/sessions/{consent_ref}/revoke")
async def revoke_session(
    project_id: str,
    consent_ref: str,
    request: Request,
    session: Session = Depends(get_session),
):
    return await _run(
        service.revoke_session(session, request.app.state.settings, project_id, consent_ref)
    )


@router.get("/projects/{project_id}/assets")
async def asset(
    project_id: str,
    request: Request,
    path: str = Query(..., min_length=1, max_length=512),
    session: Session = Depends(get_session),
):
    try:
        resolved, media_type = service.asset(session, project_id, path)
    except LivingBookProblem as error:
        raise HTTPException(error.status, str(error)) from None
    return FileResponse(
        resolved,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
