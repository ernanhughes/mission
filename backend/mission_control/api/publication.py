"""Publication-readiness API (MC-QUALITY-03D). Assessment only.

No manuscript writes, no deployment, no inferred approval. Gate results are
deterministic given the same snapshot and policy version.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.persistence.db import now_iso
from mission_control.publication import improvements as pubimp
from mission_control.publication import policy
from mission_control.publication import service as pub
from mission_control.schemas import (
    PublicationApprovalCreate,
    PublicationApprovalRead,
    PublicationAssessmentCreate,
    PublicationAssessmentRead,
    PublicationCalibrationCreate,
    PublicationCalibrationRead,
    PublicationFollowupCreate,
    PublicationFollowupRead,
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


@router.get("/publishing")
def get_publishing_summary(
    project_id: str = Query(...),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Read-only publishing evidence summary. Never validates, builds or publishes."""
    from mission_control.publication import publishing as _publishing

    settings = request.app.state.settings if request is not None else None
    return _publishing.get_publishing_summary(session, settings, project_id)


@router.get("/publishing/chapters")
def get_publishing_chapters(
    project_id: str = Query(...),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Per-chapter publication state. Read-only; never validates or builds."""
    from fastapi import HTTPException

    from mission_control.publication import publishing as _publishing

    settings = request.app.state.settings if request is not None else None
    try:
        return _publishing.get_publishing_chapters(session, settings, project_id)
    except _publishing.UnknownProjectError:
        raise HTTPException(status_code=404, detail=f"Unknown project '{project_id}'")


@router.get("/publishing/candidates")
def get_publishing_candidates(project_id: str = Query(...)) -> dict:
    """Retained experimental candidates by reference. Read-only metadata only."""
    from mission_control.publication import publishing as _publishing

    return _publishing.get_publishing_candidates(project_id)


@router.get("/publishing/candidates/{record_id}/body")
def get_publishing_candidate_body(record_id: str) -> dict:
    """Full markdown body of one retained candidate. Read-only, bounded."""
    from fastapi import HTTPException

    from mission_control.publication import publishing as _publishing

    try:
        return _publishing.get_publishing_candidate_body(record_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown candidate record '{record_id}'")


@router.get("/publishing/overview")
def get_publishing_overview(
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Global workbench rows: one compact summary per book. Read-only."""
    from mission_control.publication import publishing as _publishing

    settings = request.app.state.settings if request is not None else None
    return _publishing.get_publishing_overview(session, settings)


@router.post("/publishing/refresh")
def refresh_publishing_evidence(
    project_id: str = Query(...),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Reread stored evidence for one book. Never validates, builds or publishes."""
    from mission_control.publication import publishing as _publishing

    settings = request.app.state.settings if request is not None else None
    return _publishing.get_publishing_summary(session, settings, project_id)


@router.post("/followups", response_model=PublicationFollowupRead, status_code=201)
def create_followup(
    payload: PublicationFollowupCreate,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Promote a blocker to a governed task/decision with provenance."""
    from mission_control.publication import followups as _followups

    result = _followups.create_followup(
        session,
        project_id=str(payload.project_id or ""),
        book_id="",
        evidence_type=str(payload.evidence_type or ""),
        source_reference=str(payload.source_reference or ""),
        fingerprint=str(payload.fingerprint or ""),
        observed_at=str(payload.observed_at or ""),
        target_type=str(payload.target_type or "task"),
        title=str(payload.title or ""),
        rationale=str(payload.rationale or ""),
        reviewer=str(payload.reviewer or ""),
    )
    session.flush()
    return result


@router.get("/followups", response_model=list[PublicationFollowupRead])
def list_followups(
    project_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Follow-ups with provenance; append-only history preserved."""
    from mission_control.publication import followups as _followups

    return _followups.list_followups(session, project_id=project_id, status=status)


@router.post("/followups/{followup_id}/recheck")
def recheck_followup(
    followup_id: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> dict:
    """Re-read fresh evidence and compare fingerprints. Never auto-closes."""
    from mission_control.publication import followups as _followups

    settings = request.app.state.settings if request is not None else None
    result = _followups.recheck_followup(session, settings, followup_id)
    session.flush()
    return result


@router.post("/followups/{followup_id}/close", response_model=PublicationFollowupRead)
def close_followup(
    followup_id: str,
    payload: dict | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """Close a follow-up explicitly. History is preserved."""
    from mission_control.publication import followups as _followups

    body = payload or {}
    result = _followups.close_followup(
        session, followup_id,
        rationale=str(body.get("rationale", "") or ""),
        reviewer=str(body.get("reviewer", "") or ""))
    session.flush()
    return result


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


@router.post("/improvements", status_code=201)
async def request_improvement(payload: dict, request: Request,
                              session: Session = Depends(get_session)) -> dict:
    """Request governed chapter improvement. Mode `inspect` only prepares;
    `generate` / `generate+verify` dispatch a bounded Worker execution
    behind a Work Envelope. Free local-only routes only — paid inference
    is refused, never merely unbudgeted. Synchronous and bounded."""
    from fastapi import HTTPException

    from mission_control.api import harness as harness_api
    from mission_control import models as orm

    settings = request.app.state.settings
    body = payload or {}
    try:
        validated = pubimp.validate_improvement_request(
            session, settings,
            project_id=str(body.get("project_id") or ""),
            chapter_id=str(body.get("chapter_id") or ""),
            strategy=str(body.get("strategy") or ""),
            mode=str(body.get("mode") or ""),
            max_budget_usd=body.get("max_budget_usd", 0),
            actor=str(body.get("actor") or ""),
            authorization_note=str(body.get("authorization_note") or ""))
    except pubimp.ImprovementError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    submission_id = str(body.get("submission_id") or _new_id())
    setting = validated
    book_root = pubimp.book_root_for(settings, setting["project_id"])
    scans = {
        "cruft": pubimp.run_writer_scan("cruft", setting["project_id"],
                                         setting["chapter_id"] + ".md",
                                         book_root),
        "complexity": pubimp.run_writer_scan("complexity", setting["project_id"],
                                              setting["chapter_id"] + ".md",
                                              book_root),
    }
    chapter_text = _read_chapter_text(settings, setting)
    packet = {
        "submission_id": submission_id,
        "chapter": {k: setting[k] for k in (
            "project_id", "chapter_id", "chapter_fingerprint",
            "chapter_bytes")},
        "strategy": setting["strategy"], "mode": setting["mode"],
        "max_budget_usd": setting["max_budget_usd"],
        "actor": setting["actor"],
        "scans": {k: {"available": v.get("available"),
                      "reason": v.get("reason")} for k, v in scans.items()},
    }
    if setting["mode"] == "inspect":
        return {"status": "prepared", "packet": packet,
                "dispatched": False,
                "note": "Inspect only: no episode, envelope, or Worker dispatch was created."}
    # Generate: episode + objective (explicit_user, fingerprint-bound) first.
    # Identity is derived from the submission id so a replay of the same
    # submission reuses the same rows; the envelope digest then matches and
    # the replay is refused (409) BEFORE any second set of side effects.
    submission_key = hashlib.sha256(submission_id.encode("utf-8")).hexdigest()[:12]
    episode_id = f"ep:task:PUB09B-{setting['chapter_id']}-{submission_key}"
    objective_id = f"obj:pub09b-{submission_key}"
    objective_text = (
        f"Improve {setting['chapter_id']} ({setting['strategy']}): produce a "
        f"reviewable revised chapter candidate; verify deterministically; "
        f"record semantic verification as pending.")
    if session.get(orm.WoEpisode, episode_id) is None:
        session.add(orm.WoEpisode(id=episode_id, project_key=setting["project_id"],
                                  title=f"PUB-09B improve {setting['chapter_id']} "
                                        f"({setting['strategy']})",
                                  kind="task", status="established",
                                  source_digest=setting["chapter_fingerprint"]))
    if session.get(orm.WoObjective, objective_id) is None:
        session.add(orm.WoObjective(id=objective_id, episode_id=episode_id,
                                    text=objective_text, authority="explicit_user",
                                    status="current", version=1,
                                    source_digest=setting["chapter_fingerprint"],
                                    extractor="human-reviewed"))
    session.commit()
    envelope_service = getattr(request.app.state, "envelope_service", None)
    if envelope_service is None:
        raise HTTPException(status_code=503,
                            detail="Work Outcome envelope service is unavailable")
    scope = (f"pub09b:{submission_id}:{setting['chapter_id']}:"
             f"{setting['strategy']}:{setting['mode']}:"
             f"{setting['max_budget_usd']}")
    envelope = envelope_service.register_envelope(
        episode_id=episode_id, objective_id=objective_id, scope=scope,
        acceptance_criteria="Author-reviewed candidate; verification recorded; "
                            "no automatic application or publication.",
        acceptance_policy_ref="human-review-required",
        programme_id="PUBLICATION", stage_id="PUB-09B",
        actor=setting["actor"], authorization_note=setting["authorization_note"])
    if envelope.get("status") == "duplicate":
        raise HTTPException(
            status_code=409,
            detail=(f"DUPLICATE_SUBMISSION: this submission was already authorized "
                    f"(envelope {envelope.get('envelope_id')}); inspect the existing "
                    "record instead of dispatching again."))
    if envelope.get("status") != "completed":
        raise HTTPException(status_code=422, detail=envelope.get("error", "Work Envelope authorization failed"))
    prompt = pubimp.compose_prompt(validated, scans, chapter_text)
    timeout_ms = min(int(body.get("timeout_ms") or pubimp.DEFAULT_TIMEOUT_MS),
                     pubimp.MAX_TIMEOUT_MS)
    max_tokens = min(int(body.get("max_output_tokens") or pubimp.DEFAULT_OUTPUT_TOKENS),
                     pubimp.MAX_OUTPUT_TOKENS)
    base = harness_api._worker_base(request)
    timeout = harness_api.httpx.Timeout(timeout_ms / 1000 + 10, connect=5.0)
    try:
        async with harness_api.httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            catalogue = await pubimp.worker_catalogue(client, base)
            route = pubimp.pick_free_local_route(catalogue)
            setting["policy_id"] = route["policy"]
            setting["model_route_requested"] = route["model_route"]
            worker_request = {
                "schema": "worker.work-request.v1",
                "task_id": objective_id, "episode_id": episode_id,
                "objective": prompt,
                "execution": {"backend": "model", "model": route["model_route"],
                              "policy": route["policy"],
                              "strategy_id": route["strategy_id"]},
                "parameters": {"timeout_ms": timeout_ms,
                               "max_output_tokens": max_tokens,
                               "data_policy": "local_only",
                               "output_schema": {"type": "object",
                                                 "additionalProperties": True}},
                "options": {"acceptance": "human"},
                "metadata": {"operation_id": envelope.get("envelope_id")},
            }
            try:
                response = await client.post(f"{base}/v1/work", json=worker_request)
            except harness_api.httpx.TimeoutException as exc:
                raise HTTPException(status_code=504, detail={
                    "code": "WORKER_OUTCOME_UNKNOWN",
                    "envelope_id": envelope.get("envelope_id"),
                    "message": "Worker timed out; the request may have reached execution. "
                               "Do not retry under a new submission ID."}) from exc
            except harness_api.httpx.HTTPError as exc:
                raise HTTPException(status_code=503, detail={
                    "code": "WORKER_UNAVAILABLE",
                    "envelope_id": envelope.get("envelope_id"),
                    "message": f"Worker transport failed ({type(exc).__name__})."}) from exc
            if response.status_code != 200:
                # Workers failures are recorded, not discarded: the author
                # must be able to see that a dispatch happened and why it
                # produced no candidate. No candidate body is stored.
                try:
                    error_body = response.json()
                except ValueError:
                    error_body = None
                result = {
                    "request_id": f"failed-{_new_id(16)}",
                    "status": "FAILED",
                    "output": None,
                    "message": (error_body or {}).get("error", {}).get("message")
                    if isinstance(error_body, dict) else None,
                    "worker_http_status": response.status_code,
                }
            else:
                try:
                    result = response.json()
                except ValueError:
                    result = {
                        "request_id": f"failed-{_new_id(16)}",
                        "status": "FAILED",
                        "output": None,
                        "message": "Worker returned invalid JSON.",
                    }
    except pubimp.ImprovementError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    return _finish_improvement_dispatch(
        request, session, settings, validated, scans, chapter_text,
        episode_id, objective_id, envelope, result,
        timeout_ms, max_tokens, submission_id)


def _finish_improvement_dispatch(request: Request, session: Session,
                                 settings: Any, validated: dict,
                                 scans: dict, chapter_text: str,
                                 episode_id: str, objective_id: str,
                                 envelope: dict, result: Any,
                                 timeout_ms: int, max_tokens: int,
                                 submission_id: str) -> dict:
    wid = result.get("request_id") if isinstance(result, dict) else None
    worker_message = ""
    if isinstance(result, dict):
        worker_message = str(result.get("message") or "").strip()[:300]
    if not isinstance(wid, str) or not wid:
        wid = f"failed-{_new_id(16)}"
        status, note = "failed", "Worker response carried no request id; nothing was generated."
        body_text = ""
    else:
        output = result.get("output") if isinstance(result, dict) else None
        body_text = output if isinstance(output, str) else (
            json.dumps(output)[:pubimp.MAX_BODY_BYTES]
            if output is not None else "")
        status = "reported_complete" if body_text.strip() else "failed"
        note = "" if body_text.strip() else (
            f"Worker reported {str(result.get('status') or 'no output')}"
            + (f": {worker_message}" if worker_message else "")
            + ". Recorded as failed; no candidate was stored.")
    cost = pubimp._worker_cost(result)
    usage = result.get("usage") if isinstance(result, dict) else None
    if isinstance(usage, dict):
        for key in ("cost_usd", "billed_cost_usd", "estimated_cost_usd"):
            try:
                value = float(usage.get(key, 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            cost = max(cost, value)
    if cost > validated["max_budget_usd"] + 1e-9:
        status = "failed"
        note = (note + " " if note else "") + (
            f"Worker-reported cost ${cost:.4f} exceeds the authorized cap "
            f"${validated['max_budget_usd']:.4f}; recorded, not accepted.")
        body_text = ""
    validation = pubimp.deterministic_validation(body_text, chapter_text)
    if status != "failed" and not validation["passed"]:
        status = "failed"
        note = (note + " " if note else "") + "; ".join(validation["problems"])
    truncation = pubimp.worker_truncation(result)
    if status == "reported_complete" and truncation["suspected"]:
        # A ceiling-bound response is a truncated transformation, not a
        # finished one: it stays readable but is ineligible for acceptance.
        status = "incomplete"
        note = (note + " " if note else "") + (
            f"Response consumed {truncation['observed_output_tokens']} of "
            f"{truncation['requested_output_tokens']} requested output tokens; "
            "the chapter is ceiling-bound and incomplete. Regenerate with a "
            "larger budget before review.")
    worker_model, worker_provider = pubimp._worker_identity(result)
    record = {
        "id": wid, "kind": "requested-execution",
        "project_id": validated["project_id"], "chapter_id": validated["chapter_id"],
        "chapter_fingerprint": validated["chapter_fingerprint"],
        "strategy": validated["strategy"], "mode": validated["mode"],
        "max_budget_usd": validated["max_budget_usd"],
        "timeout_ms": timeout_ms, "max_output_tokens": max_tokens,
        "actor": validated["actor"],
        "authorization_note": validated["authorization_note"],
        "submission_id": submission_id,
        "episode_id": episode_id, "objective_id": objective_id,
        "envelope_id": envelope.get("envelope_id"),
        "commission_digest": envelope.get("commission_digest"),
        "model_route": worker_model or validated.get("model_route_requested"),
        "model_provider": worker_provider,
        "policy": validated.get("policy_id"),
        "status": status,
        "eligible": status == "reported_complete",
        "truncation": truncation,
        "worker_status": result.get("status") if isinstance(result, dict) else None,
        "worker_message": worker_message or None,
        "worker_http_status": result.get("worker_http_status") if isinstance(result, dict) else None,
        "cost_usd": cost,
        "validation": validation,
        "verification": {
            "status": "pending",
            "reason": "No plan-scoped Writer verification applies to a fresh "
                      "reconstruction (`transform verify` needs the changed "
                      "passages bound in a PUB-05 plan); PUB-08 eval fabric is "
                      "benchmark infrastructure, not a per-candidate service. "
                      "Deterministic checks above are necessary, not sufficient."},
        "note": note,
        "created_at": now_iso(),
    }
    if body_text.strip() and status in ("reported_complete", "incomplete"):
        pubimp.save_candidate_record(settings, record, body_text)
    else:
        record["available"] = False
        pubimp.save_candidate_record(settings, record, "")
    envelope_service = getattr(request.app.state, "envelope_service", None)
    if envelope_service is not None:
        try:
            envelope_service.link_execution(
                envelope_id=envelope.get("envelope_id"),
                external_ref=wid if wid.startswith("wrq:") else wid[:64],
                model=str((result.get("resolved", {}) or {}).get("resolved_model_route", ""))
                if isinstance(result, dict) else "",
                status=status if status in ("reported_complete", "failed") else "reported_complete",
                proposal_id="")
        except Exception:
            record["link_warning"] = "execution link could not be recorded; the candidate record stands alone"
    return {"status": "completed", "improvement": record,
            "worker_envelope": envelope.get("envelope_id")}


def _read_chapter_text(settings: Any, validated: dict) -> str:
    try:
        return pubimp.read_chapter_text(
            settings, validated["project_id"], validated["chapter_id"])
    except pubimp.ImprovementError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status, detail=exc.detail)


def _new_id(n: int = 16) -> str:
    import uuid as _uuid
    return _uuid.uuid4().hex[:n]


@router.get("/improvements")
def list_improvements(request: Request) -> dict:
    """Dispatched improvement records, newest first. Read-only; a missing
    Worker is reported per record, never as a listing failure."""
    settings = request.app.state.settings
    listing = pubimp.list_candidate_records(settings)
    try:
        from mission_control.api import harness as harness_api

        harness_api._worker_base(request)
        worker_reachable = True
    except Exception:
        worker_reachable = False
    return {"improvements": listing["records"], "count": len(listing["records"]),
            "rejected_records": listing["rejected"],
            "rejections": listing["rejections"],
            "worker_reachable": worker_reachable}


@router.get("/improvements/{record_id}")
async def get_improvement(record_id: str, request: Request) -> dict:
    """One improvement record plus best-effort live Worker status."""
    settings = request.app.state.settings
    record = pubimp.load_candidate_record(settings, record_id)
    if record is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404,
                            detail=f"Unknown improvement '{record_id}'")
    try:
        current = pubimp.read_chapter_text(
            settings, record.get("project_id", ""),
            record.get("chapter_id", ""))
        import hashlib as _hashlib_fp
        current_fp = _hashlib_fp.sha256(
            current.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        record["source_current"] = (current_fp == record.get("chapter_fingerprint"))
    except Exception:
        record["source_current"] = False
        record["source_note"] = "Source chapter is missing or unreadable."
    live: dict[str, Any] = {"reachable": False}
    if isinstance(record.get("id"), str) and record["id"].startswith("wrq_"):
        try:
            from mission_control.api import harness as harness_api

            base = harness_api._worker_base(request)
            timeout = harness_api.httpx.Timeout(5.0, connect=2.0)
            async with harness_api.httpx.AsyncClient(
                    timeout=timeout, trust_env=False) as client:
                summary = await harness_api._get(
                    client, base, f"/v1/work/{record['id']}")
            live = {"reachable": True,
                    "artifact_available": isinstance(summary, dict),
                    "worker_status": summary.get("status") if isinstance(summary, dict) else None}
        except Exception as exc:
            live = {"reachable": False,
                    "reason": f"{type(exc).__name__}: {str(exc)[:160]}"}
    else:
        live = {"reachable": False,
                "reason": "No Worker request id recorded for this improvement."}
    return {"improvement": record, "worker": live}


@router.get("/improvements/{record_id}/body")
def get_improvement_body(record_id: str, request: Request) -> dict:
    """Generated candidate markdown. Read-only, bounded."""
    from fastapi import HTTPException

    settings = request.app.state.settings
    if pubimp.load_candidate_record(settings, record_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Unknown improvement '{record_id}'")
    return pubimp.candidate_body(settings, record_id)


@router.post("/improvements/{record_id}/revalidate")
async def revalidate_improvement(record_id: str, request: Request) -> dict:
    """Re-run the deterministic checks against the stored body and the
    current source. Read-only w.r.t. the manuscript; no inference. This
    exists because the checks improve over time and a historical record
    must be able to say what today's checks find."""
    from fastapi import HTTPException

    settings = request.app.state.settings
    record = pubimp.load_candidate_record(settings, record_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Unknown improvement '{record_id}'")
    body = pubimp.candidate_body(settings, record_id)
    if not body.get("available"):
        raise HTTPException(status_code=422,
                            detail=body.get("reason") or "No candidate body to revalidate")
    try:
        original = pubimp.read_chapter_text(
            settings, record.get("project_id", ""), record.get("chapter_id", ""))
    except pubimp.ImprovementError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    validation = pubimp.deterministic_validation(body["markdown"], original)
    record["validation"] = validation
    record["body_matches_record"] = bool(
        body.get("body_matches_record", True))
    record["revalidated_at"] = now_iso()
    # Ceiling detection is re-derived when the Worker still holds the run.
    if isinstance(record.get("id"), str) and record["id"].startswith("wrq_"):
        try:
            from mission_control.api import harness as harness_api

            base = harness_api._worker_base(request)
            timeout = harness_api.httpx.Timeout(5.0, connect=2.0)
            async with harness_api.httpx.AsyncClient(
                    timeout=timeout, trust_env=False) as client:
                summary = await harness_api._get(
                    client, base, f"/v1/work/{record['id']}")
            truncation = pubimp.worker_truncation(summary)
            record["truncation"] = truncation
            if truncation["suspected"]:
                record["status"] = "incomplete"
                record["eligible"] = False
                note = str(record.get("note") or "")
                marker = "ceiling-bound"
                if marker not in note:
                    record["note"] = (note + " " if note else "") + (
                        f"Response consumed {truncation['observed_output_tokens']} of "
                        f"{truncation['requested_output_tokens']} requested output tokens; "
                        "the chapter is ceiling-bound and incomplete. Regenerate with a "
                        "larger budget before review.")
        except Exception as exc:
            record["truncation_refresh_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    pubimp.save_candidate_record(settings, record, body["markdown"])
    return {"status": "completed", "improvement": record}
