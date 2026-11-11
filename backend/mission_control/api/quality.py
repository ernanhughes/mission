"""Manuscript-quality evaluation history (MC-QUALITY-02). Read-only by default;
recording an evaluation persists an observation, never a manuscript change."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.quality.service import (
    compare,
    create_campaign,
    eligibility,
    get_campaign,
    get_evaluation,
    list_campaigns,
    list_evaluations,
    record_evaluation,
    resume_campaign,
    run_campaign,
    stop_campaign,
    to_read,
    workspace,
)
from mission_control.schemas import (
    QualityCampaignCreate,
    QualityCampaignRead,
    QualityChapterDiscovery,
    QualityEvaluationCreate,
    QualityEvaluationRead,
    QualityWorkspaceRead,
)

router = APIRouter(prefix="/api/quality", tags=["quality"])


@router.get("/workspace", response_model=QualityWorkspaceRead)
def quality_workspace(
    project_id: str = Query(...), session: Session = Depends(get_session)
) -> QualityWorkspaceRead:
    return workspace(session, project_id)


@router.get("/evaluations", response_model=list[QualityEvaluationRead])
def quality_evaluations(
    project_id: str | None = None,
    chapter_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[QualityEvaluationRead]:
    return [to_read(r) for r in list_evaluations(session, project_id=project_id, chapter_id=chapter_id, limit=limit)]


@router.get("/evaluations/{evaluation_id}", response_model=QualityEvaluationRead)
def quality_evaluation(
    evaluation_id: str, session: Session = Depends(get_session)
) -> QualityEvaluationRead:
    return to_read(get_evaluation(session, evaluation_id))


@router.post("/evaluations", response_model=QualityEvaluationRead, status_code=201)
def create_quality_evaluation(
    payload: QualityEvaluationCreate, session: Session = Depends(get_session)
) -> QualityEvaluationRead:
    record = record_evaluation(session, payload)
    session.flush()
    return to_read(record)


@router.get("/compare")
def compare_evaluations(
    first_id: str = Query(...),
    second_id: str = Query(...),
    session: Session = Depends(get_session),
):
    return compare(session, first_id, second_id)


@router.get("/discovery", response_model=list[QualityChapterDiscovery])
def quality_discovery(
    project_id: str = Query(...),
    model: str | None = None,
    session: Session = Depends(get_session),
) -> list[QualityChapterDiscovery]:
    return eligibility(session, project_id, model=model)


@router.get("/campaigns", response_model=list[QualityCampaignRead])
def quality_campaigns(
    project_id: str | None = None, session: Session = Depends(get_session)
) -> list[QualityCampaignRead]:
    from mission_control.quality.service import _campaign_read

    return [_campaign_read(r) for r in list_campaigns(session, project_id)]


@router.get("/campaigns/{campaign_id}", response_model=QualityCampaignRead)
def quality_campaign(
    campaign_id: str, session: Session = Depends(get_session)
) -> QualityCampaignRead:
    from mission_control.quality.service import _campaign_read

    return _campaign_read(get_campaign(session, campaign_id))


@router.post("/campaigns", response_model=QualityCampaignRead, status_code=201)
def create_quality_campaign(
    payload: QualityCampaignCreate, session: Session = Depends(get_session)
) -> QualityCampaignRead:
    from mission_control.quality.service import _campaign_read

    record = create_campaign(session, payload)
    session.flush()
    return _campaign_read(record)


@router.post("/campaigns/{campaign_id}/stop", response_model=QualityCampaignRead)
def stop_quality_campaign(
    campaign_id: str, session: Session = Depends(get_session)
) -> QualityCampaignRead:
    from mission_control.quality.service import _campaign_read

    record = stop_campaign(session, campaign_id)
    session.flush()
    return _campaign_read(record)


@router.post("/campaigns/{campaign_id}/resume", response_model=QualityCampaignRead)
def resume_quality_campaign(
    campaign_id: str, session: Session = Depends(get_session)
) -> QualityCampaignRead:
    from mission_control.quality.service import _campaign_read

    record = resume_campaign(session, campaign_id)
    session.flush()
    return _campaign_read(record)


@router.post("/campaigns/{campaign_id}/run", response_model=QualityCampaignRead)
def run_quality_campaign(
    campaign_id: str,
    background: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
) -> QualityCampaignRead:
    """Start (or continue) campaign execution in a background task.

    Execution shells the canonical AI manuscript CLI; transport, model and
    provenance are recorded per chapter. Only one active campaign per
    project+scope is allowed by create_campaign.
    """
    from fastapi import HTTPException as HTTPException_
    from mission_control.quality.service import _campaign_read

    record = get_campaign(session, campaign_id)
    if record.status not in ("pending",):
        raise HTTPException_(409, f"campaign is {record.status}; resume it instead")
    database = request.app.state.database
    settings = request.app.state.settings
    background.add_task(_run_campaign_task, database, settings, campaign_id)
    return _campaign_read(record)


def _run_campaign_task(database, settings, campaign_id: str) -> None:
    import json
    import subprocess
    import sys

    from mission_control.persistence.db import Database as Database_

    db = database or Database_(settings)

    def evaluate_fn(chapter_id: str) -> dict:
        import os

        with db.session() as session:
            campaign = get_campaign(session, campaign_id)
            book_root = campaign.book_root
            fingerprints = dict(campaign.fingerprints or {})
            route = campaign.model
        source = None
        for root, _dirs, files in os.walk(book_root):
            if chapter_id in files:
                source = os.path.join(root, chapter_id)
                break
        if source is None:
            return {"status": "ERROR", "error": f"chapter file not found: {chapter_id}"}
        python = (getattr(settings, "quality_eval_python", None) or "").strip() if settings else ""
        if not python:
            return {
                "status": "BLOCKED",
                "error": (
                    "no evaluation interpreter configured: set "
                    "MISSION_CONTROL_QUALITY_EVAL_PYTHON to a python with the "
                    "`ai` package installed"
                ),
            }
        cmd = [
            python, "-m", "ai.scoring.manuscript_cli",
            "--chapter", source, "--chapter-id", chapter_id, "--route", route or "",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except Exception as exc:  # noqa: BLE001 - transport failure is data
            return {"status": "BLOCKED", "error": f"evaluator launch failed: {exc}"}
        if proc.returncode not in (0, 2, 3):
            return {"status": "BLOCKED", "error": f"evaluator exited {proc.returncode}: {(proc.stderr or '')[:300]}"}
        try:
            payload_out = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except Exception as exc:  # noqa: BLE001
            return {"status": "ERROR", "error": f"unparsable evaluator output: {exc}"}
        if payload_out.get("status") in ("BLOCKED", "ERROR") and "dimensions" not in payload_out:
            return payload_out
        payload_out["requested_model"] = route
        payload_out.setdefault("source_path", source)
        payload_out.setdefault("chapter_revision", fingerprints.get(chapter_id, ""))
        return payload_out

    run_campaign(db.session, campaign_id, evaluate_fn)
