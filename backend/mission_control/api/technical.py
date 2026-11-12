"""Technical-confidence API (MC-QUALITY-03B). Assessment only; manuscripts are never modified."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.quality.service import (
    _campaign_read,
    create_campaign,
    get_campaign,
    record_review,
    to_review_read,
)
from mission_control.schemas import (
    QualityCampaignCreate,
    QualityCampaignRead,
    QualityReviewCreate,
    QualityReviewRead,
    TechnicalChapterAssessment,
    TechnicalClaimCreate,
    TechnicalClaimLinkCreate,
    TechnicalClaimRead,
    TechnicalEvidenceCreate,
    TechnicalEvidenceRead,
    TechnicalGapCreate,
    TechnicalGapRead,
    TechnicalObjectiveClaimCreate,
    TechnicalObjectiveCreate,
    TechnicalObjectiveRead,
    TechnicalRequirementCreate,
    TechnicalRequirementLinkCreate,
    TechnicalVerificationCreate,
    TechnicalVerificationRead,
)
from mission_control.technical import service as tech

router = APIRouter(prefix="/api/technical", tags=["technical"])


@router.post("/claims", response_model=TechnicalClaimRead, status_code=201)
def create_technical_claim(
    payload: TechnicalClaimCreate, session: Session = Depends(get_session)
) -> TechnicalClaimRead:
    record = tech.record_claim(session, payload)
    session.flush()
    return tech.to_claim_read(record)


@router.post("/claims/bulk", response_model=list[TechnicalClaimRead])
def create_technical_claims(
    payload: list[TechnicalClaimCreate], session: Session = Depends(get_session)
) -> list[TechnicalClaimRead]:
    records = [tech.record_claim(session, item) for item in payload]
    session.flush()
    return [tech.to_claim_read(r) for r in records]


@router.get("/claims", response_model=list[TechnicalClaimRead])
def list_technical_claims(
    project_id: str | None = None,
    chapter_id: str | None = None,
    claim_type: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    session: Session = Depends(get_session),
) -> list[TechnicalClaimRead]:
    return [
        tech.to_claim_read(r)
        for r in tech.list_claims(
            session, project_id=project_id, chapter_id=chapter_id,
            claim_type=claim_type, limit=limit,
        )
    ]


@router.get("/claims/{claim_id}", response_model=TechnicalClaimRead)
def get_technical_claim(
    claim_id: str, session: Session = Depends(get_session)
) -> TechnicalClaimRead:
    return tech.to_claim_read(tech.get_claim(session, claim_id))


@router.post("/evidence", response_model=TechnicalEvidenceRead, status_code=201)
def create_technical_evidence(
    payload: TechnicalEvidenceCreate, session: Session = Depends(get_session)
) -> TechnicalEvidenceRead:
    record = tech.record_evidence(session, payload)
    session.flush()
    return tech.to_evidence_read(record)


@router.get("/claims/{claim_id}/evidence", response_model=list[TechnicalEvidenceRead])
def claim_evidence(claim_id: str, session: Session = Depends(get_session)):
    return [tech.to_evidence_read(r) for r in tech.list_evidence(session, claim_id)]


@router.post("/verifications", response_model=TechnicalVerificationRead, status_code=201)
def create_technical_verification(
    payload: TechnicalVerificationCreate, session: Session = Depends(get_session)
) -> TechnicalVerificationRead:
    record = tech.record_verification(session, payload)
    session.flush()
    return tech.to_verification_read(record)


@router.get("/claims/{claim_id}/verifications", response_model=list[TechnicalVerificationRead])
def claim_verifications(claim_id: str, session: Session = Depends(get_session)):
    return [tech.to_verification_read(r) for r in tech.list_verifications(session, claim_id)]


@router.get("/chapters/{chapter_id}", response_model=TechnicalChapterAssessment)
def technical_chapter(
    chapter_id: str,
    project_id: str = Query(...),
    session: Session = Depends(get_session),
) -> TechnicalChapterAssessment:
    return tech.chapter_assessment(session, project_id, chapter_id)


@router.get("/overview")
def technical_overview(
    project_id: str = Query(...), session: Session = Depends(get_session)
):
    return tech.book_overview(session, project_id)


@router.get("/claims/{claim_id}/candidates")
def technical_candidates(
    claim_id: str, session: Session = Depends(get_session)
):
    return tech.cross_chapter_candidates(session, claim_id)


@router.post("/reviews", response_model=QualityReviewRead, status_code=201)
def create_technical_review(
    payload: QualityReviewCreate, session: Session = Depends(get_session)
) -> QualityReviewRead:
    """Author decision on a technical finding. finding_id is a claim or
    verification id; evaluation_id may be omitted with an explicit
    source_digest (prose evaluations are never required for tech review)."""
    record = record_review(session, payload)
    session.flush()
    # Commit before responding: same read-after-write guarantee as the
    # quality create endpoints (teardown runs after the response is sent).
    session.commit()
    return to_review_read(record, payload.source_digest or "")


@router.post("/campaigns", response_model=QualityCampaignRead, status_code=201)
def create_technical_campaign(
    payload: QualityCampaignCreate, session: Session = Depends(get_session)
) -> QualityCampaignRead:
    from mission_control.quality.service import _campaign_read as _read

    payload.assessment_type = "technical"
    record = create_campaign(session, payload)
    session.flush()
    return _read(record)


@router.get("/campaigns", response_model=list[QualityCampaignRead])
def list_technical_campaigns(
    project_id: str | None = None, session: Session = Depends(get_session)
):
    from mission_control.quality import service as quality_service

    return [
        quality_service._campaign_read(r)
        for r in quality_service.list_campaigns(session, project_id)
        if (r.assessment_type or "prose") == "technical"
    ]


@router.get("/campaigns/{campaign_id}")
def get_technical_campaign(
    campaign_id: str, session: Session = Depends(get_session)
):
    from mission_control.quality import service as quality_service
    from mission_control.quality.service import get_campaign as _get

    record = _get(session, campaign_id)
    if (record.assessment_type or "prose") != "technical":
        raise HTTPException(400, "not a technical campaign")
    return quality_service._campaign_read(record)


@router.post("/campaigns/{campaign_id}/stop")
def stop_technical_campaign(
    campaign_id: str, session: Session = Depends(get_session)
):
    from mission_control.quality import service as quality_service
    from mission_control.quality.service import get_campaign as _get

    record = _get(session, campaign_id)
    if (record.assessment_type or "prose") != "technical":
        raise HTTPException(400, "not a technical campaign")
    stopped = quality_service.stop_campaign(session, campaign_id)
    session.flush()
    return quality_service._campaign_read(stopped)


@router.post("/campaigns/{campaign_id}/resume")
def resume_technical_campaign(
    campaign_id: str, session: Session = Depends(get_session)
):
    from mission_control.quality import service as quality_service
    from mission_control.quality.service import get_campaign as _get

    record = _get(session, campaign_id)
    if (record.assessment_type or "prose") != "technical":
        raise HTTPException(400, "not a technical campaign")
    resumed = quality_service.resume_campaign(session, campaign_id)
    session.flush()
    return quality_service._campaign_read(resumed)


@router.post("/campaigns/{campaign_id}/run")
def run_technical_campaign(
    campaign_id: str,
    background: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
):
    from mission_control.quality.service import _campaign_read as _read

    record = get_campaign(session, campaign_id)
    if getattr(record, "assessment_type", "prose") != "technical":
        raise HTTPException(400, "not a technical campaign")
    if record.status != "pending":
        raise HTTPException(409, f"campaign is {record.status}; resume it instead")
    database = request.app.state.database
    settings = request.app.state.settings
    background.add_task(_run_technical_campaign_task, database, settings, campaign_id)
    return _read(record)


def _run_technical_campaign_task(database, settings, campaign_id: str) -> None:
    import json
    import os
    import subprocess
    import sys

    from mission_control.technical.service import run_technical_campaign

    def evaluate_fn(chapter_id: str) -> dict:
        with database.session() as session:
            from mission_control.quality.service import get_campaign

            campaign = get_campaign(session, campaign_id)
            book_root = campaign.book_root
            route = campaign.model
        source = None
        for root, _dirs, files in os.walk(book_root):
            if chapter_id in files:
                source = os.path.join(root, chapter_id)
                break
        if source is None:
            return {"status": "ERROR", "error": f"chapter file not found: {chapter_id}"}
        python = (getattr(settings, "quality_eval_python", None) or "").strip()
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
            python, "-m", "ai.scoring.tech_cli", "extract",
            "--chapter", source, "--chapter-id", chapter_id, "--route", route or "",
            "--requested-limit", "40",
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=900,
                cwd=os.path.dirname(os.path.dirname(sys.executable)),
            )
        except Exception as exc:  # noqa: BLE001
            return {"status": "BLOCKED", "error": f"evaluator launch failed: {exc}"}
        if proc.returncode not in (0, 2, 3):
            return {"status": "BLOCKED",
                    "error": f"evaluator exited {proc.returncode}: {(proc.stderr or '')[:300]}"}
        try:
            out = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except Exception as exc:  # noqa: BLE001
            return {"status": "ERROR", "error": f"unparsable evaluator output: {exc}"}
        if out.get("status") in ("BLOCKED", "ERROR") and "claims" not in out:
            return out
        from mission_control.technical import service as _tech

        decision = _tech.classify_cli_output(out)
        if decision["action"] in ("fail", "quarantine"):
            # Quarantined output: tokens are metered, nothing is persisted
            # as complete extraction. The chapter stays eligible for retry.
            with database.session() as run_session:
                from mission_control.schemas import TechnicalExtractionRunCreate
                _tech.record_extraction_run(run_session, TechnicalExtractionRunCreate(
                    campaign_id=campaign_id, strategy="whole_continuation",
                    chapter_id=chapter_id, region_ids=[],
                    requested_limit=int(out.get("requested_limit", 40)),
                    returned_count=int(out.get("returned_count", 0)),
                    accepted_count=0, status=decision["run_status"],
                    input_tokens=int(out.get("input_tokens", 0) or 0),
                    output_tokens=int(out.get("output_tokens", 0) or 0),
                    model_id=out.get("model_id"),
                    prompt_version=str(out.get("prompt_version", "1") or "1"),
                    source_revision=str(out.get("chapter_revision", "")),
                    error=decision["error"],
                    transport=str(out.get("transport", "") or "")))
                run_session.commit()
            return {"status": "ERROR", "error": decision["error"]}
        out["requested_model"] = route
        out["actual_model"] = out.get("model_id")
        out["source_path"] = source
        with database.session() as run_session:
            from mission_control.schemas import TechnicalExtractionRunCreate
            _tech.record_extraction_run(run_session, TechnicalExtractionRunCreate(
                campaign_id=campaign_id, strategy="whole_continuation",
                chapter_id=chapter_id, region_ids=[],
                requested_limit=int(out.get("requested_limit", 40)),
                returned_count=int(out.get("returned_count", 0)),
                accepted_count=int(out.get("accepted_count", len(out.get("claims", [])))),
                status=decision["run_status"],
                input_tokens=int(out.get("input_tokens", 0) or 0),
                output_tokens=int(out.get("output_tokens", 0) or 0),
                model_id=out.get("model_id"),
                prompt_version=str(out.get("prompt_version", "1") or "1"),
                source_revision=str(out.get("chapter_revision", "")),
                transport=str(out.get("transport", "") or "")))
            run_session.commit()
        return out

    run_technical_campaign(database.session, campaign_id, evaluate_fn)


# ---------------------------------------------------------- 03C completeness

@router.post("/regions/sync")
def sync_technical_regions(
    project_id: str = Query(...),
    book_id: str = "",
    chapter_id: str = Query(...),
    source_path: str = Query(...),
    source_hash: str = Query(...),
    payload: list = Body(default_factory=list),
    session: Session = Depends(get_session),
):
    """Store a deterministic region inventory for one chapter.

    Units are computed by the caller (Workbench plan_sections) and passed
    in; the server never parses manuscripts for structure. Each unit:
    {title, char_span:[lo,hi], byte_span:[lo,hi], id, editable, bounded}.
    """
    records = tech.sync_regions(
        session, project_id=project_id, book_id=book_id, chapter_id=chapter_id,
        source_path=source_path, source_hash=source_hash, units=payload or [],
    )
    session.flush()
    return [{"id": r.id, "title": r.title, "chars": [r.char_start, r.char_end],
             "unit_hash": r.unit_hash, "source_kind": r.source_kind} for r in records]


@router.get("/regions")
def list_technical_regions(
    project_id: str | None = None,
    chapter_id: str | None = None,
    session: Session = Depends(get_session),
):
    return [
        {"id": r.id, "chapter_id": r.chapter_id, "title": r.title,
         "source_hash": r.source_hash, "char_start": r.char_start,
         "char_end": r.char_end, "unit_hash": r.unit_hash,
         "source_kind": r.source_kind, "created_at": r.created_at}
        for r in tech.list_regions(session, project_id=project_id, chapter_id=chapter_id)
    ]


@router.post("/coverage", status_code=201)
def record_technical_coverage(body: dict, session: Session = Depends(get_session)):
    record = tech.record_coverage(session, **{k: v for k, v in body.items() if k != "region_id"},
                                  region_id=body["region_id"])
    session.flush()
    return {"id": record.id, "status": record.status, "region_id": record.region_id,
            "limit_reached": record.limit_reached, "returned_count": record.returned_count}


@router.post("/requirements", response_model=dict, status_code=201)
def create_technical_requirement(
    payload: TechnicalRequirementCreate, session: Session = Depends(get_session)
):
    record = tech.record_requirement(session, payload)
    session.flush()
    return {"id": record.id, "claim_id": record.claim_id,
            "requirement_key": record.requirement_key,
            "applicability": record.applicability, "satisfaction": record.satisfaction}


@router.get("/claims/{claim_id}/requirements")
def claim_requirements(claim_id: str, session: Session = Depends(get_session)):
    return [
        {"id": r.id, "requirement_key": r.requirement_key, "label": r.label,
         "requirement_type": r.requirement_type, "acceptance_rule": r.acceptance_rule,
         "rationale": r.rationale, "applicability": r.applicability,
         "satisfaction": r.satisfaction, "satisfaction_detail": r.satisfaction_detail,
         "waived_reason": r.waived_reason}
        for r in tech.list_requirements(session, claim_id)
    ]


@router.post("/requirements/{requirement_id}/status")
def set_requirement_status(
    requirement_id: str, body: dict, session: Session = Depends(get_session)
):
    record = tech.set_requirement_status(
        session, requirement_id,
        satisfaction=str(body.get("satisfaction", "NOT_ASSESSED")),
        detail=str(body.get("detail", "")),
        waived_reason=str(body.get("waived_reason", "")),
    )
    session.flush()
    return {"id": record.id, "satisfaction": record.satisfaction}


@router.post("/requirement-links", status_code=201)
def link_requirement_evidence(
    payload: TechnicalRequirementLinkCreate, session: Session = Depends(get_session)
):
    record = tech.link_requirement_evidence(session, payload)
    session.flush()
    return {"id": record.id, "relation": record.relation}


@router.post("/claim-links", status_code=201)
def link_technical_claims(
    payload: TechnicalClaimLinkCreate, session: Session = Depends(get_session)
):
    record = tech.link_claims(session, payload)
    session.flush()
    return {"id": record.id, "relation": record.relation}


@router.post("/gaps", status_code=201)
def create_technical_gap(
    payload: TechnicalGapCreate, session: Session = Depends(get_session)
):
    record = tech.record_gap(session, payload)
    session.flush()
    return {"id": record.id, "gap_type": record.gap_type, "status": record.status}


@router.get("/gaps")
def list_technical_gaps(
    project_id: str | None = None,
    chapter_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    return [
        {"id": r.id, "chapter_id": r.chapter_id, "claim_id": r.claim_id,
         "requirement_id": r.requirement_id, "gap_type": r.gap_type,
         "title": r.title, "detail": r.detail, "searched_scope": r.searched_scope,
         "status": r.status, "priority_rationale": r.priority_rationale,
         "created_at": r.created_at}
        for r in tech.list_gaps(session, project_id=project_id, chapter_id=chapter_id, status=status)
    ]


@router.post("/gaps/{gap_id}/status")
def set_gap_status(gap_id: str, body: dict, session: Session = Depends(get_session)):
    record = tech.set_gap_status(session, gap_id, str(body.get("status", "OPEN")))
    session.flush()
    return {"id": record.id, "status": record.status}


@router.post("/objectives", status_code=201)
def create_technical_objective(
    payload: TechnicalObjectiveCreate, session: Session = Depends(get_session)
):
    record = tech.record_objective(session, payload)
    session.flush()
    return {"id": record.id, "statement": record.statement,
            "source": record.source, "status": record.status,
            "chapter_id": record.chapter_id, "created_at": record.created_at}


@router.get("/objectives")
def list_technical_objectives(
    project_id: str | None = None,
    chapter_id: str | None = None,
    session: Session = Depends(get_session),
):
    return [
        {"id": r.id, "chapter_id": r.chapter_id, "statement": r.statement,
         "source": r.source, "status": r.status, "created_at": r.created_at}
        for r in tech.list_objectives(session, project_id=project_id, chapter_id=chapter_id)
    ]


@router.post("/objectives/link", status_code=201)
def link_objective_claim(
    payload: TechnicalObjectiveClaimCreate, session: Session = Depends(get_session)
):
    record = tech.link_objective_claim(session, payload)
    session.flush()
    return {"objective_id": record.objective_id, "claim_id": record.claim_id, "role": record.role}


@router.get("/completeness/{chapter_id}")
def technical_completeness(
    chapter_id: str,
    project_id: str = Query(...),
    book_root: str | None = None,
    session: Session = Depends(get_session),
):
    return tech.chapter_completeness(session, project_id, chapter_id, book_root)
