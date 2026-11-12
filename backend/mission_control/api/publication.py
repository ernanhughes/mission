"""Publication-readiness API (MC-QUALITY-03D). Assessment only.

No manuscript writes, no deployment, no inferred approval. Gate results are
deterministic given the same snapshot and policy version.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.publication import policy
from mission_control.publication import service as pub
from mission_control.schemas import (
    PublicationApprovalCreate,
    PublicationApprovalRead,
    PublicationAssessmentCreate,
    PublicationAssessmentRead,
    PublicationCalibrationCreate,
    PublicationCalibrationRead,
    PublicationGateRead,
    PublicationIssueRead,
)

router = APIRouter(prefix="/api/publication", tags=["publication"])


def _read(session: Session, record) -> dict:
    return pub.to_read(session, record)


@router.post("/assessments", response_model=PublicationAssessmentRead, status_code=201)
def create_publication_assessment(
    payload: PublicationAssessmentCreate,
    request: Request,
    force: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    settings = request.app.state.settings
    record = pub.create_assessment(
        session, settings, project_id=payload.project_id or "inference",
        book_id=payload.book_id, policy_version=payload.policy_version,
        technical_scope=payload.technical_scope, force=force)
    session.commit()
    session.refresh(record)
    return _read(session, record)


@router.get("/assessments", response_model=list[PublicationAssessmentRead])
def list_publication_assessments(
    project_id: str | None = None,
    session: Session = Depends(get_session),
):
    from mission_control.models import PublicationAssessment

    stmt = select(PublicationAssessment).order_by(desc(PublicationAssessment.created_at)).limit(50)
    if project_id:
        stmt = stmt.where(PublicationAssessment.project_id == project_id)
    return [_read(session, r) for r in session.scalars(stmt).all()]


@router.get("/assessments/{assessment_id}", response_model=PublicationAssessmentRead)
def get_publication_assessment(
    assessment_id: str, session: Session = Depends(get_session)
):
    return _read(session, pub.get_assessment(session, assessment_id))


@router.post("/assessments/{assessment_id}/refresh",
             response_model=PublicationAssessmentRead)
def refresh_publication_assessment(
    assessment_id: str, request: Request, session: Session = Depends(get_session)
):
    settings = request.app.state.settings
    record = pub.refresh_freshness(session, settings, assessment_id)
    session.commit()
    session.refresh(record)
    return _read(session, record)


@router.post("/approvals", response_model=PublicationApprovalRead, status_code=201)
def approve_release_candidate(
    payload: PublicationApprovalCreate, session: Session = Depends(get_session)
):
    record = pub.approve(session, payload)
    session.commit()
    session.refresh(record)
    return {
        "id": record.id, "assessment_id": record.assessment_id,
        "decision": record.decision, "rationale": record.rationale or "",
        "manuscript_fingerprint": record.manuscript_fingerprint,
        "input_manifest_fingerprint": record.input_manifest_fingerprint,
        "policy_version": record.policy_version,
        "accepted_limitation_ids": list(record.accepted_limitation_ids or []),
        "freshness": record.freshness, "reviewer": record.reviewer or "",
        "created_at": record.created_at,
    }


@router.post("/issues/{issue_id}/review", response_model=PublicationIssueRead)
def review_release_issue(
    issue_id: str, body: dict, session: Session = Depends(get_session)
):
    record = pub.review_issue(
        session, issue_id, decision=str(body.get("decision", "")),
        rationale=str(body.get("rationale", "")),
        reviewer=str(body.get("reviewer", "")))
    session.commit()
    session.refresh(record)
    return {
        "id": record.id, "gate_id": record.gate_id, "issue_type": record.issue_type,
        "severity": record.severity, "verification_method": record.verification_method,
        "status": record.status, "waiver_eligibility": record.waiver_eligibility,
        "author_review_status": record.author_review_status,
        "source_refs": list(record.source_refs or []),
        "evidence_refs": list(record.evidence_refs or []),
        "rationale": record.rationale or "", "created_at": record.created_at,
    }


@router.post("/calibration", response_model=PublicationCalibrationRead, status_code=201)
def record_calibration_review(
    payload: PublicationCalibrationCreate, session: Session = Depends(get_session)
):
    record = pub.record_calibration(session, payload)
    session.commit()
    session.refresh(record)
    return {
        "id": record.id, "requirement_id": record.requirement_id,
        "sample_version": record.sample_version, "sample_reason": record.sample_reason or "",
        "claim_accurate": bool(record.claim_accurate),
        "requirement_applicable": record.requirement_applicable,
        "necessary": bool(record.necessary), "strictness_ok": bool(record.strictness_ok),
        "satisfied_by_evidence": record.satisfied_by_evidence,
        "gap_justified": bool(record.gap_justified),
        "priority_proportionate": bool(record.priority_proportionate),
        "would_block": bool(record.would_block),
        "qualification_sufficient": bool(record.qualification_sufficient),
        "duplicate_of": record.duplicate_of or "", "verdict": record.verdict or "",
        "correction": record.correction or "", "reviewer": record.reviewer or "",
        "created_at": record.created_at,
    }


@router.get("/calibration", response_model=list[PublicationCalibrationRead])
def list_calibration_reviews(session: Session = Depends(get_session)):
    from mission_control.models import PublicationCalibrationReview

    rows = session.scalars(
        select(PublicationCalibrationReview)
        .order_by(PublicationCalibrationReview.created_at)).all()
    return [{
        "id": r.id, "requirement_id": r.requirement_id,
        "sample_version": r.sample_version, "sample_reason": r.sample_reason or "",
        "claim_accurate": bool(r.claim_accurate),
        "requirement_applicable": r.requirement_applicable,
        "necessary": bool(r.necessary), "strictness_ok": bool(r.strictness_ok),
        "satisfied_by_evidence": r.satisfied_by_evidence,
        "gap_justified": bool(r.gap_justified),
        "priority_proportionate": bool(r.priority_proportionate),
        "would_block": bool(r.would_block),
        "qualification_sufficient": bool(r.qualification_sufficient),
        "duplicate_of": r.duplicate_of or "", "verdict": r.verdict or "",
        "correction": r.correction or "", "reviewer": r.reviewer or "",
        "created_at": r.created_at} for r in rows]


@router.get("/calibration/summary")
def calibration_summary(session: Session = Depends(get_session)):
    return pub.calibration_summary(session)


@router.get("/calibration/runs")
def calibration_runs(session: Session = Depends(get_session)):
    """Run registry: historical 03D run (DB) + frozen CAL04A02 run (manifest)."""
    from mission_control.publication import calibration as cal
    from mission_control.models import PublicationCalibrationReview

    rows = session.scalars(select(PublicationCalibrationReview)).all()
    by_version: dict[int, list] = {}
    for r in rows:
        by_version.setdefault(r.sample_version, []).append(r)
    sample = json.loads((cal.DATA_DIR / "sample.json").read_text(encoding="utf-8"))
    a_ids = set(sample["sample_A"])
    b_ids = {s["requirement_id"] for s in sample["sample_B"]}
    v2 = [r for r in rows if r.sample_version == 2]
    v2_ids = set(r.requirement_id for r in v2 if r.requirement_id)

    def state_counts(rs):
        states = [cal.review_state(r.verdict or "") for r in rs]
        return {s: states.count(s) for s in ("completed", "draft", "deferred", "abstained", "awaiting")}

    def disagreements(rs):
        from collections import defaultdict
        by_req: dict = defaultdict(list)
        for r in rs:
            if cal.review_state(r.verdict or "") == "completed":
                by_req[r.requirement_id].append(r)
        out = 0
        for req_id, group in by_req.items():
            if len(group) > 1 and (
                    len({g.requirement_applicable for g in group}) > 1
                    or len({bool(g.would_block) for g in group}) > 1):
                out += 1
        return out

    v1 = by_version.get(1, [])
    return [
        {"run_id": "CAL03D-20261111", "contract": "evidence-requirements-v1",
         "sample_version": 1, "kind": "historical",
         "sampled": len(v1), "reviewed": len([r for r in v1 if cal.review_state(r.verdict or "") == "completed"]),
         "states": state_counts(v1), "disagreements": disagreements(v1),
         "provenance": "human:operator"},
        {"run_id": sample["run_id"], "contract": sample["contract"],
         "sample_version": 2, "kind": "probability_plus_diagnostic",
         "seed": sample["seed"], "population": sample.get("population_id"),
         "arm_A_target": len(a_ids), "arm_B_target": len(b_ids),
         "sampled": len([r for r in v2 if (r.requirement_id or "") in (a_ids | b_ids)]),
         "reviewed": len([r for r in v2
                           if (r.requirement_id or "") in (a_ids | b_ids)
                           and cal.review_state(r.verdict or "") == "completed"]),
         "states": state_counts(v2), "disagreements": disagreements(v2),
         "awaiting": len((a_ids | b_ids) - v2_ids),
         "provenance_note": ("Only human: rows count as independent ground truth; "
                             "ai_assisted rows are provisional analysis.")},
    ]


@router.get("/calibration/sample")
def calibration_sample():
    """Frozen CAL04A02 sample manifest (seed, arms, IDs)."""
    from mission_control.publication import calibration as cal

    return json.loads((cal.DATA_DIR / "sample.json").read_text(encoding="utf-8"))


@router.get("/calibration/packets")
def calibration_packets(arm: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    """Frozen review packets (source-grounded, integrity-flagged)."""
    from mission_control.publication import calibration as cal

    packets = json.loads((cal.DATA_DIR / "packets.json").read_text(encoding="utf-8"))["packets"]
    if arm:
        packets = [p for p in packets if p["sampling_arm"] == arm]
    return {"count": len(packets), "packets": packets[:limit]}


@router.get("/calibration/packets/{case_id}")
def calibration_packet(case_id: str):
    """One frozen review packet by calibration_case_id."""
    from mission_control.publication import calibration as cal
    from fastapi import HTTPException as HTTPException_

    packets = json.loads((cal.DATA_DIR / "packets.json").read_text(encoding="utf-8"))["packets"]
    for p in packets:
        if p["calibration_case_id"] == case_id:
            return p
    raise HTTPException_(404, f"unknown calibration case {case_id!r}")


@router.get("/calibration/stats")
def calibration_stats(session: Session = Depends(get_session)):
    """Estimates over completed HUMAN reviews only, plus provisional counts."""
    from mission_control.publication import calibration as cal
    from mission_control.models import PublicationCalibrationReview

    rows = session.scalars(select(PublicationCalibrationReview)).all()
    dicts = [{
        "requirement_applicable": r.requirement_applicable,
        "gap_justified": bool(r.gap_justified),
        "priority_proportionate": bool(r.priority_proportionate),
        "would_block": bool(r.would_block),
        "verdict": r.verdict or "", "reviewer": r.reviewer or "",
        "satisfied_by_evidence": r.satisfied_by_evidence} for r in rows]
    return cal.summarize_human_sample(dicts)


@router.get("/policy")
def release_policy():
    return {"policy_version": policy.POLICY_VERSION,
            "policy_kind": policy.POLICY_KIND, "gates": policy.GATES}


@router.get("/assessments/{assessment_id}/dossier.zip")
def download_dossier(assessment_id: str, request: Request,
                     session: Session = Depends(get_session)):
    settings = request.app.state.settings
    pub.get_assessment(session, assessment_id)
    name, payload = pub.dossier_zip(settings, assessment_id)
    return Response(content=payload, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/assessments/{assessment_id}/dossier.md", response_class=PlainTextResponse)
def dossier_markdown(assessment_id: str, request: Request,
                     session: Session = Depends(get_session)):
    from mission_control.publication.service import dossier_dir

    settings = request.app.state.settings
    pub.get_assessment(session, assessment_id)
    path = dossier_dir(settings.data_dir, assessment_id) / "publication-readiness.md"
    if not path.is_file():
        from fastapi import HTTPException as HTTPException_

        raise HTTPException_(404, "dossier has not been written for this assessment")
    return path.read_text(encoding="utf-8")
