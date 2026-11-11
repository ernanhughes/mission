"""Artifact Load history (ARTIFACT-EXPO-01, Stage 08/09).

Read-mostly observation store kept independent from the six-dimension
prose-quality scores. Recording an observation persists a burden measurement,
never a manuscript change and never a quality-score mutation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.artifact_load.service import (
    ASSESSMENT_POLICY_VERSION,
    assessment_state,
    compare_observations,
    get_observation,
    list_observations,
    record_observation,
)
from mission_control.schemas import (
    ArtifactLoadChapterSummary,
    ArtifactLoadCreate,
    ArtifactLoadRead,
    ArtifactLoadWorkspaceRead,
)

router = APIRouter(prefix="/api/artifact-load", tags=["artifact-load"])


def _workbench_link(base: str | None, chapter_id: str) -> str | None:
    if not base:
        return None
    from urllib.parse import quote

    return f"{base.rstrip('/')}/#chapter={quote(chapter_id)}"


def to_read(record) -> ArtifactLoadRead:
    return ArtifactLoadRead(
        id=record.id,
        project_id=record.project_id,
        book_id=record.book_id or "",
        chapter_id=record.chapter_id,
        source_path=record.source_path or "",
        chapter_revision=record.chapter_revision,
        aggregation_version=record.aggregation_version,
        detector_version=record.detector_version,
        status=record.status,
        derived_state=record.status.lower(),
        assessment_state=assessment_state(record),
        assessment_policy=ASSESSMENT_POLICY_VERSION,
        eligible_words=record.eligible_words,
        evaluated_units=record.evaluated_units,
        total_candidates=record.total_candidates,
        confirmed=record.confirmed,
        high=record.high,
        medium=record.medium,
        low=record.low,
        unreviewed=record.unreviewed,
        invalid_evidence=record.invalid_evidence,
        affected_regions=record.affected_regions,
        findings_per_1k=record.findings_per_1k,
        findings_per_100_units=record.findings_per_100_units,
        region_rate=record.region_rate,
        coverage_mechanical=record.coverage_mechanical,
        coverage_semantic=record.coverage_semantic,
        weighted_load=record.weighted_load,
        mechanical_pressure=record.mechanical_pressure,
        baseline_eligible_words=record.baseline_eligible_words,
        revised_eligible_words=record.revised_eligible_words,
        findings=list(record.findings or []),
        regions=list(record.regions or []),
        limitations=list(record.limitations or []),
        execution=dict(record.execution or {}),
        previous_observation_id=record.previous_observation_id,
        supersedes=record.supersedes,
        workbench_url=record.workbench_url,
        workbench_link=_workbench_link(record.workbench_url, record.chapter_id),
        compatible_basis=record.aggregation_version,
        created_at=record.created_at,
    )


def workspace(session: Session, project_id: str) -> ArtifactLoadWorkspaceRead:
    records = list_observations(session, project_id=project_id, limit=2000)
    by_chapter: dict[str, list] = {}
    for record in records:
        by_chapter.setdefault(record.chapter_id, []).append(record)
    chapters: list[ArtifactLoadChapterSummary] = []
    current_count = 0
    for chapter_id in sorted(by_chapter):
        rows = sorted(by_chapter[chapter_id], key=lambda r: r.created_at)
        reads = [to_read(r) for r in rows]
        # Newest CURRENT row on the newest revision is current; older rows
        # on other revisions are stale history, never overwritten.
        current = None
        scored = [r for r in rows if r.status in ("CURRENT", "PARTIAL", "STALE")]
        if scored:
            newest = scored[-1]
            read = to_read(newest)
            if newest.status == "CURRENT":
                read.derived_state = "current"
            else:
                read.derived_state = newest.status.lower()
            current = read
            for item in reads:
                if item.id == read.id:
                    item.derived_state = read.derived_state
                elif item.chapter_revision != read.chapter_revision:
                    item.derived_state = "stale"
                else:
                    item.derived_state = "historical"
            if read.derived_state == "current":
                current_count += 1
        chapters.append(
            ArtifactLoadChapterSummary(chapter_id=chapter_id, observations=reads, current=current)
        )
    # Superseded revisions are stale history: an old row on another revision
    # must not keep reporting its original assessment as current.
    for chapter in chapters:
        if chapter.current is None:
            continue
        for item in chapter.observations:
            if item.chapter_revision != chapter.current.chapter_revision:
                item.assessment_state = "stale"
    return ArtifactLoadWorkspaceRead(
        project_id=project_id,
        chapters_total=len(chapters),
        chapters_observed=len(chapters),
        chapters_current=current_count,
        chapters=chapters,
        limitations=[
            f"{current_count} of {len(chapters)} chapters have a current load observation; coverage is explicit, not extrapolated.",
            "Artifact Load is burden (higher means more confirmed problems). It is independent from prose-quality scores and never merged into them.",
        ],
    )


@router.get("/workspace", response_model=ArtifactLoadWorkspaceRead)
def artifact_load_workspace(
    project_id: str = Query(...), session: Session = Depends(get_session)
) -> ArtifactLoadWorkspaceRead:
    return workspace(session, project_id)


@router.get("/observations", response_model=list[ArtifactLoadRead])
def artifact_load_observations(
    project_id: str | None = None,
    chapter_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[ArtifactLoadRead]:
    return [
        to_read(r)
        for r in list_observations(
            session, project_id=project_id, chapter_id=chapter_id, limit=limit
        )
    ]


@router.get("/observations/{observation_id}", response_model=ArtifactLoadRead)
def artifact_load_observation(
    observation_id: str, session: Session = Depends(get_session)
) -> ArtifactLoadRead:
    return to_read(get_observation(session, observation_id))


@router.post("/observations", response_model=ArtifactLoadRead, status_code=201)
def create_artifact_load_observation(
    payload: ArtifactLoadCreate, session: Session = Depends(get_session)
) -> ArtifactLoadRead:
    record = record_observation(
        session,
        project_id=payload.project_id,
        book_id=payload.book_id,
        chapter_id=payload.chapter_id,
        source_path=payload.source_path,
        chapter_revision=payload.chapter_revision,
        status=payload.status,
        eligible_words=payload.eligible_words,
        evaluated_units=payload.evaluated_units,
        coverage_mechanical=payload.coverage_mechanical,
        coverage_semantic=payload.coverage_semantic,
        findings=list(payload.findings),
        detector_version=payload.detector_version,
        limitations=list(payload.limitations),
        execution=dict(payload.execution),
        previous_observation_id=payload.previous_observation_id,
        supersedes=payload.supersedes,
        workbench_url=payload.workbench_url,
        baseline_eligible_words=payload.baseline_eligible_words,
        revised_eligible_words=payload.revised_eligible_words,
    )
    session.flush()
    return to_read(record)


@router.get("/compare")
def compare_artifact_load(
    first_id: str = Query(...),
    second_id: str = Query(...),
    session: Session = Depends(get_session),
):
    return compare_observations(session, first_id, second_id)
