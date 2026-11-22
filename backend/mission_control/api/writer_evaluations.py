"""Writer evaluation envelopes API (LIVING-WORK-BOOKS-01 W2).

Ingests Writer-owned ``writer.evaluation-envelope.v1`` records and serves
them per chapter with derived freshness. This API validates and references;
it never scores, merges, or rewrites evaluations.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mission_control.writer import evaluations as evaluation_store

router = APIRouter(prefix="/api/writer/evaluations", tags=["writer"])


class IngestRequest(BaseModel):
    model_config = {"extra": "forbid"}

    project_id: str | None = None
    ingested_by: str = "operator"
    envelope: dict[str, Any] = Field(...)


class IngestResponse(BaseModel):
    record_id: str
    evaluation_id: str
    created: bool


class ChapterEvaluationsRead(BaseModel):
    project_id: str
    chapter_id: str
    overall: Literal[
        "CURRENT", "STALE", "NOT_RUN", "UNAVAILABLE", "UNVERIFIED"
    ]
    source_hash_compared: str | None = None
    evaluations: list[dict[str, Any]]


@router.post("/ingest", response_model=IngestResponse)
def ingest_evaluation(request: Request, body: IngestRequest) -> IngestResponse:
    try:
        result = evaluation_store.ingest_envelope(
            request.app.state.database,
            body.envelope,
            project_id=body.project_id,
            ingested_by=body.ingested_by,
        )
    except evaluation_store.EnvelopeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return IngestResponse(**result)


@router.get("", response_model=list[dict[str, Any]])
def list_evaluations(
    request: Request,
    project_id: str | None = None,
    provider: str | None = None,
    current_only: bool = True,
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from mission_control.models import IntegrationRecord

    with request.app.state.database.session() as session:
        query = select(IntegrationRecord).where(
            IntegrationRecord.application_id == evaluation_store.APPLICATION_ID,
            IntegrationRecord.resource_type == evaluation_store.RESOURCE_TYPE,
        )
        if current_only:
            query = query.where(IntegrationRecord.current.is_(True))
        rows = session.scalars(query).all()
        items: list[dict[str, Any]] = []
        for row in rows:
            data = row.data if isinstance(row.data, dict) else {}
            producer = data.get("producer", {})
            if project_id and row.project_id and row.project_id != project_id:
                continue
            if provider and (
                not isinstance(producer, dict)
                or producer.get("runtime_name") != provider
            ):
                continue
            items.append(
                {
                    "record_id": row.id,
                    "evaluation_id": row.external_id,
                    "project_id": row.project_id,
                    "current": bool(row.current),
                    "observed_at": row.observed_at,
                    "envelope": data,
                }
            )
        return items


@router.get("/chapter", response_model=ChapterEvaluationsRead)
def read_chapter_evaluations(
    request: Request,
    project_id: str,
    chapter_id: str,
    source_hash: str | None = None,
) -> ChapterEvaluationsRead:
    return ChapterEvaluationsRead(
        **evaluation_store.chapter_evaluations(
            request.app.state.database,
            project_id,
            chapter_id,
            source_hash=source_hash,
        )
    )


@router.get("/{evaluation_id}", response_model=dict[str, Any])
def read_evaluation(
    request: Request, evaluation_id: str
) -> dict[str, Any]:
    from sqlalchemy import select

    from mission_control.models import IntegrationRecord

    with request.app.state.database.session() as session:
        row = session.scalar(
            select(IntegrationRecord).where(
                IntegrationRecord.application_id == evaluation_store.APPLICATION_ID,
                IntegrationRecord.resource_type == evaluation_store.RESOURCE_TYPE,
                IntegrationRecord.external_id == evaluation_id,
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="evaluation not found")
        data = row.data if isinstance(row.data, dict) else {}
        return {
            "record_id": row.id,
            "evaluation_id": row.external_id,
            "project_id": row.project_id,
            "current": bool(row.current),
            "observed_at": row.observed_at,
            "envelope": data,
        }
