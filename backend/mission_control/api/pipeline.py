"""Book production pipeline API (MC-BOOK-PIPELINE-01, M1).

Read-only projection of stored Writer evidence onto books, chapters, and
production stages. No execution, no writes, no invented results.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.publication import pipeline as _pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/stages")
def list_pipeline_stages() -> dict:
    """Versioned stage registry. No book I/O."""
    return _pipeline.list_stages()


@router.get("/overview")
def get_pipeline_overview(
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Cross-book summaries (no matrices). One request, shared store parses."""
    settings = request.app.state.settings if request is not None else None
    return _pipeline.get_pipeline_overview(session, settings)


@router.get("/books/{project_id}")
def get_book_pipeline(
    project_id: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Book pipeline summary: chapters, per-stage summaries, compact matrix."""
    settings = request.app.state.settings if request is not None else None
    try:
        payload = _pipeline.get_book_pipeline(session, settings, project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not payload.get("known"):
        raise HTTPException(status_code=404, detail=str(payload.get("diagnostics")))
    return payload


@router.get("/books/{project_id}/stages/{stage_id}")
def get_book_stage_detail(
    project_id: str,
    stage_id: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Stage-specific evidence detail: full per-chapter cells."""
    settings = request.app.state.settings if request is not None else None
    try:
        payload = _pipeline.get_stage_detail(session, settings, project_id, stage_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown book {project_id!r} or stage {stage_id!r}. Books must "
                "be registered in the Writer registry; stages must come from "
                "GET /api/pipeline/stages."
            ),
        )
    return payload
