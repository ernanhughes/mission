"""Technical-confidence assessments (MC-QUALITY-03B).

Claim inventory, evidence discovery and verification records. Read-only
with respect to manuscripts: assessment never mutates book content.
Staleness is derived at read time from stored source_revision values.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import (
    Project,
    QualityCampaign,
    TechnicalClaim,
    TechnicalClaimLink,
    TechnicalEvidence,
    TechnicalEvidenceRequirement,
    TechnicalExtractionCoverage,
    TechnicalGap,
    TechnicalObjective,
    TechnicalObjectiveClaim,
    TechnicalRegion,
    TechnicalRequirementLink,
    TechnicalVerification,
)
from mission_control.schemas import (
    TechnicalChapterAssessment,
    TechnicalClaimCreate,
    TechnicalClaimRead,
    TechnicalEvidenceCreate,
    TechnicalEvidenceRead,
    TechnicalVerificationCreate,
    TechnicalVerificationRead,
)

CLAIM_TYPES = (
    "DEFINITION", "MATHEMATICAL", "ALGORITHMIC", "IMPLEMENTATION",
    "API_CONTRACT", "ARCHITECTURAL", "EXPERIMENTAL", "RESEARCH",
    "FACTUAL", "HYPOTHESIS", "DESIGN_PROPOSAL",
)
EPISTEMIC_ROLES = (
    "DEFINED", "DOCUMENTED", "OBSERVED", "DERIVED",
    "PROPOSED", "HYPOTHESIS", "ILLUSTRATIVE",
)
VERIFICATION_STATUSES = (
    "VERIFIED_DETERMINISTICALLY", "SUPPORTED_BY_EXECUTED_EVIDENCE",
    "SUPPORTED_BY_DOCUMENTATION", "SEMANTICALLY_SUPPORTED",
    "CONTRADICTED_BY_EVIDENCE", "INSUFFICIENT_EVIDENCE",
    "REQUIRES_EXTERNAL_VERIFICATION", "UNRESOLVED", "NOT_RUN", "NOT_APPLICABLE",
)
VERIFICATION_METHODS = ("deterministic", "documentary", "semantic", "human")


def _check_claim(payload: TechnicalClaimCreate) -> None:
    if payload.claim_type not in CLAIM_TYPES:
        raise ValidationProblem(f"unknown claim type {payload.claim_type!r}")
    if payload.epistemic_role not in EPISTEMIC_ROLES:
        raise ValidationProblem(f"unknown epistemic role {payload.epistemic_role!r}")
    if len(payload.source_excerpt) > 2000:
        raise ValidationProblem("source excerpt exceeds 2000 chars")


def record_claim(session: Session, payload: TechnicalClaimCreate) -> TechnicalClaim:
    if payload.project_id and session.get(Project, payload.project_id) is None:
        raise ValidationProblem("Project does not exist")
    _check_claim(payload)
    if payload.campaign_id and session.get(QualityCampaign, payload.campaign_id) is None:
        raise ValidationProblem("Campaign does not exist")
    if payload.anchor_method not in ("exact", "normalized", "none"):
        raise ValidationProblem(f"unknown anchor method {payload.anchor_method!r}")
    digest = hashlib.sha256(
        f"{payload.chapter_id}|{payload.claim_text}|{payload.source_excerpt}".encode()
    ).hexdigest()[:16]
    existing = session.get(TechnicalClaim, f"tclaim:{digest}")
    if existing is not None:
        # Deterministic identity: re-extraction of the same assertion is a
        # no-op, preserving the original record and its history.
        return existing
    quote_validated = _verify_excerpt(payload.source_path, payload.source_excerpt,
                                      payload.quote_validated)
    record = TechnicalClaim(
        id=f"tclaim:{digest}",
        project_id=payload.project_id,
        book_id=payload.book_id,
        chapter_id=payload.chapter_id,
        source_path=payload.source_path,
        source_revision=payload.source_revision,
        source_start_line=payload.source_start_line,
        source_end_line=payload.source_end_line,
        source_excerpt=payload.source_excerpt,
        claim_text=payload.claim_text,
        normalized_assertion=payload.normalized_assertion or payload.claim_text,
        claim_type=payload.claim_type,
        epistemic_role=payload.epistemic_role,
        assumptions=list(payload.assumptions),
        qualifications=list(payload.qualifications),
        extraction_method=payload.extraction_method,
        model_id=payload.model_id,
        prompt_version=payload.prompt_version,
        extraction_status="CURRENT",
        quote_validated=quote_validated,
        anchor_method=payload.anchor_method,
        source_char_start=payload.source_char_start,
        source_char_end=payload.source_char_end,
        campaign_id=payload.campaign_id,
    )
    session.add(record)
    session.flush()
    return record


def _verify_excerpt(source_path: str, excerpt: str, claimed: bool) -> bool:
    """Verify independently against the readable source file when possible.

    A verifiable excerpt found verbatim is marked valid even if the caller
    did not claim it; an excerpt absent from a readable source is flagged
    invalid even if claimed. Only when the source cannot be read does the
    caller's claim stand in. Nothing is ever rewritten.
    """
    if not excerpt or len(excerpt) > 2000:
        return False
    if not source_path:
        return bool(claimed)
    try:
        with open(source_path, encoding="utf-8") as handle:
            text = handle.read().replace("\r\n", "\n")
    except OSError:
        return bool(claimed)
    return excerpt.replace("\r\n", "\n") in text


def get_claim(session: Session, claim_id: str) -> TechnicalClaim:
    record = session.get(TechnicalClaim, claim_id)
    if record is None:
        raise NotFound("Claim does not exist")
    return record


def list_claims(
    session: Session,
    *,
    project_id: str | None = None,
    chapter_id: str | None = None,
    claim_type: str | None = None,
    limit: int = 500,
) -> list[TechnicalClaim]:
    stmt: Select = select(TechnicalClaim).order_by(desc(TechnicalClaim.created_at))
    if project_id:
        stmt = stmt.where(TechnicalClaim.project_id == project_id)
    if chapter_id:
        stmt = stmt.where(TechnicalClaim.chapter_id == chapter_id)
    if claim_type:
        stmt = stmt.where(TechnicalClaim.claim_type == claim_type)
    return list(session.scalars(stmt.limit(limit)).all())


def record_evidence(session: Session, payload: TechnicalEvidenceCreate) -> TechnicalEvidence:
    if payload.verification_status not in VERIFICATION_STATUSES:
        raise ValidationProblem(f"unknown verification status {payload.verification_status!r}")
    get_claim(session, payload.claim_id)
    digest = hashlib.sha256(
        f"{payload.claim_id}|{payload.source_location}|{payload.evidence_excerpt}".encode()
    ).hexdigest()[:16]
    existing = session.get(TechnicalEvidence, f"tev:{digest}")
    if existing is not None:
        return existing
    record = TechnicalEvidence(
        id=f"tev:{digest}",
        claim_id=payload.claim_id,
        evidence_type=payload.evidence_type,
        source_location=payload.source_location,
        source_revision=payload.source_revision,
        source_span=payload.source_span,
        evidence_excerpt=payload.evidence_excerpt,
        discovery_method=payload.discovery_method,
        verification_method=payload.verification_method,
        verification_status=payload.verification_status,
        limitations=payload.limitations,
    )
    session.add(record)
    session.flush()
    return record


def list_evidence(session: Session, claim_id: str) -> list[TechnicalEvidence]:
    get_claim(session, claim_id)
    stmt = select(TechnicalEvidence).where(
        TechnicalEvidence.claim_id == claim_id
    ).order_by(TechnicalEvidence.created_at)
    return list(session.scalars(stmt).all())


def record_verification(
    session: Session, payload: TechnicalVerificationCreate
) -> TechnicalVerification:
    if payload.method not in VERIFICATION_METHODS:
        raise ValidationProblem(f"unknown verification method {payload.method!r}")
    if payload.status not in VERIFICATION_STATUSES:
        raise ValidationProblem(f"unknown verification status {payload.status!r}")
    get_claim(session, payload.claim_id)
    if payload.evidence_id and session.get(TechnicalEvidence, payload.evidence_id) is None:
        raise ValidationProblem("Evidence does not exist")
    record = TechnicalVerification(
        id=f"tver:{uuid.uuid4().hex[:12]}",
        claim_id=payload.claim_id,
        evidence_id=payload.evidence_id,
        method=payload.method,
        status=payload.status,
        detail=payload.detail,
        spec_id=payload.spec_id,
        spec_version=payload.spec_version,
        model_id=payload.model_id,
        prompt_version=payload.prompt_version,
        prompt_hash=payload.prompt_hash,
        token_usage=payload.token_usage,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
        campaign_id=payload.campaign_id,
    )
    session.add(record)
    session.flush()
    return record


def list_verifications(session: Session, claim_id: str) -> list[TechnicalVerification]:
    get_claim(session, claim_id)
    stmt = select(TechnicalVerification).where(
        TechnicalVerification.claim_id == claim_id
    ).order_by(TechnicalVerification.created_at)
    return list(session.scalars(stmt).all())


def to_claim_read(record: TechnicalClaim, *, current_revision: str = "") -> TechnicalClaimRead:
    if current_revision:
        derived = "current" if record.source_revision == current_revision else "stale"
    else:
        derived = "current" if record.extraction_status == "CURRENT" else record.extraction_status.lower()
    return TechnicalClaimRead(
        id=record.id,
        project_id=record.project_id,
        book_id=record.book_id or "",
        chapter_id=record.chapter_id,
        source_path=record.source_path or "",
        source_revision=record.source_revision,
        source_start_line=record.source_start_line,
        source_end_line=record.source_end_line,
        source_excerpt=record.source_excerpt or "",
        claim_text=record.claim_text,
        normalized_assertion=record.normalized_assertion or "",
        claim_type=record.claim_type,
        epistemic_role=record.epistemic_role,
        assumptions=list(record.assumptions or []),
        qualifications=list(record.qualifications or []),
        extraction_method=record.extraction_method,
        model_id=record.model_id,
        prompt_version=record.prompt_version,
        extraction_status=record.extraction_status,
        quote_validated=bool(record.quote_validated),
        anchor_method=record.anchor_method or "none",
        source_char_start=record.source_char_start,
        source_char_end=record.source_char_end,
        campaign_id=record.campaign_id,
        derived_state=derived,
        created_at=record.created_at,
    )


def chapter_assessment(
    session: Session, project_id: str, chapter_id: str
) -> TechnicalChapterAssessment:
    claims = list_claims(session, project_id=project_id, chapter_id=chapter_id, limit=10000)
    by_status: dict[str, int] = {}
    by_method: dict[str, int] = {}
    unresolved = 0
    revision = ""
    for claim in claims:
        verifications = list_verifications(session, claim.id)
        if not verifications:
            status = "NOT_RUN"
        else:
            latest = verifications[-1]
            status = latest.status
            by_method[latest.method] = by_method.get(latest.method, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        if status in ("UNRESOLVED", "INSUFFICIENT_EVIDENCE", "REQUIRES_EXTERNAL_VERIFICATION",
                      "CONTRADICTED_BY_EVIDENCE"):
            unresolved += 1
        revision = revision or claim.source_revision
    return TechnicalChapterAssessment(
        chapter_id=chapter_id,
        source_revision=revision,
        claims_total=len(claims),
        claims_source_verified=sum(1 for c in claims if c.quote_validated),
        claims_unresolved=unresolved,
        by_status=by_status,
        by_method=by_method,
        claims=[to_claim_read(c) for c in claims],
    )


def book_overview(session: Session, project_id: str) -> dict[str, Any]:
    chapters = sorted({r.chapter_id for r in list_claims(session, project_id=project_id, limit=100000)})
    totals: dict[str, int] = {}
    methods: dict[str, int] = {}
    unresolved = total = 0
    for chapter_id in chapters:
        assessment = chapter_assessment(session, project_id, chapter_id)
        total += assessment.claims_total
        unresolved += assessment.claims_unresolved
        for status, count in assessment.by_status.items():
            totals[status] = totals.get(status, 0) + count
        for method, count in assessment.by_method.items():
            methods[method] = methods.get(method, 0) + count
    return {
        "project_id": project_id,
        "chapters_with_claims": len(chapters),
        "claims_total": total,
        "by_status": totals,
        "by_method": methods,
        "claims_unresolved": unresolved,
    }

def to_evidence_read(record: TechnicalEvidence) -> TechnicalEvidenceRead:
    return TechnicalEvidenceRead(
        id=record.id,
        claim_id=record.claim_id,
        evidence_type=record.evidence_type,
        source_location=record.source_location,
        source_revision=record.source_revision or "",
        source_span=record.source_span or "",
        evidence_excerpt=record.evidence_excerpt or "",
        discovery_method=record.discovery_method or "",
        verification_method=record.verification_method or "",
        verification_status=record.verification_status,
        limitations=record.limitations or "",
        created_at=record.created_at,
    )


def to_verification_read(record: TechnicalVerification) -> TechnicalVerificationRead:
    return TechnicalVerificationRead(
        id=record.id,
        claim_id=record.claim_id,
        evidence_id=record.evidence_id,
        method=record.method,
        status=record.status,
        detail=record.detail or "",
        spec_id=record.spec_id or "",
        spec_version=record.spec_version,
        model_id=record.model_id,
        prompt_version=record.prompt_version or "",
        prompt_hash=record.prompt_hash,
        token_usage=record.token_usage,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        campaign_id=record.campaign_id,
        created_at=record.created_at,
    )


_STOPWORDS = frozenset(
    "the a an of to in and or for with on as at by from that this these those "
    "is are was were be been being it its their his her our your they them we you "
    "he she him her us not no nor but if then than so such can will just "
    "into over under between through during per via within without".split()
)


def _terms(text: str) -> set[str]:
    import re

    return {
        token
        for token in re.findall(r"[a-z][a-z0-9\-]{3,}", text.lower())
        if token not in _STOPWORDS
    }


def cross_chapter_candidates(
    session: Session, claim_id: str, *, limit: int = 5
) -> list[dict[str, Any]]:
    """Deterministic candidate discovery: other-chapter claims sharing
    distinctive terminology. Candidates only; compatibility is judged
    separately by a bounded semantic comparison.
    """
    anchor = get_claim(session, claim_id)
    anchor_terms = _terms(f"{anchor.claim_text} {anchor.normalized_assertion or ''}")
    if not anchor_terms:
        return []
    scored = []
    for other in list_claims(session, project_id=anchor.project_id, limit=10000):
        if other.id == anchor.id or other.chapter_id == anchor.chapter_id:
            continue
        other_terms = _terms(f"{other.claim_text} {other.normalized_assertion or ''}")
        shared = sorted(anchor_terms & other_terms)
        if len(shared) >= 2:
            scored.append({
                "claim_id": other.id,
                "chapter_id": other.chapter_id,
                "claim_text": other.claim_text,
                "claim_type": other.claim_type,
                "shared_terms": shared,
                "shared_count": len(shared),
            })
    scored.sort(key=lambda item: (-item["shared_count"], item["chapter_id"]))
    return scored[:limit]


class _TechStop(Exception):
    pass


def run_technical_campaign(session_factory, campaign_id: str, evaluate_fn) -> Any:
    """Durable per-chapter technical assessment.

    evaluate_fn(chapter) returns {"claims": [claim payloads...]} or raises,
    or returns {"status": "BLOCKED"/"ERROR", "error": ...}. Progress and
    failures persist per chapter; one failure never aborts the campaign.
    Reuses the quality campaign progress/recovery columns.
    """
    from mission_control.persistence.db import now_iso
    from mission_control.quality.service import (
        _campaign_done,
        _finish_counts,
        get_campaign,
        get_fresh,
    )

    with session_factory() as session:
        record = get_campaign(session, campaign_id)
        if record.status == "completed":
            # Idempotent re-run: nothing left to do, history untouched.
            return get_fresh(session_factory, campaign_id)
        if record.status not in ("pending", "running"):
            raise ValidationProblem(f"campaign is {record.status}; resume it instead")
        record.status = "running"
        record.error = None
        record.updated_at = now_iso()
        record.heartbeat_at = now_iso()
        session.commit()
        selection = list(record.chapter_selection or [])
        done = {
            r.chapter_id
            for r in session.scalars(
                select(TechnicalClaim).where(
                    TechnicalClaim.campaign_id == record.id
                )
            ).all()
        }
        completed = len([c for c in selection if c in done])
        skipped = failed = 0
        failures: dict[str, str] = {}
        usage_in = usage_out = 0
        try:
            for chapter_id in selection:
                with session_factory() as check:
                    fresh = get_campaign(check, record.id)
                    if fresh.status == "cancelling":
                        raise _TechStop()
                if chapter_id in done:
                    skipped += 1
                    continue
                with session_factory() as chapter_session:
                    row = get_campaign(chapter_session, record.id)
                    row.current_chapter = chapter_id
                    row.heartbeat_at = now_iso()
                    row.updated_at = now_iso()
                    chapter_session.commit()
                try:
                    outcome = evaluate_fn(chapter_id)
                except _TechStop:
                    raise
                except Exception as exc:  # noqa: BLE001 - per-chapter isolation
                    outcome = {"status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                if isinstance(outcome, dict) and outcome.get("status") in ("BLOCKED", "ERROR") and "claims" not in outcome:
                    failed += 1
                    failures[chapter_id] = str(outcome.get("error", "failed"))
                    with session_factory() as chapter_session:
                        row = get_campaign(chapter_session, record.id)
                        row.error = f"{chapter_id}: {failures[chapter_id]}"
                        row.usage = {**(row.usage or {}), "failures": failures}
                        row.failed = failed
                        row.skipped = skipped
                        row.remaining = max(0, len(selection) - completed - skipped - failed)
                        row.updated_at = now_iso()
                        chapter_session.commit()
                    continue
                claims_in = outcome.get("claims", []) if isinstance(outcome, dict) else []
                usage = dict(outcome.get("usage", {}) or {}) if isinstance(outcome, dict) else {}
                try:
                    with session_factory() as chapter_session:
                        for entry in claims_in:
                            payload = TechnicalClaimCreate(
                                project_id=record.project_id,
                                book_id=record.book_id,
                                chapter_id=chapter_id,
                                source_path=str(entry.get("source_path", "")),
                                source_revision=str(entry.get("chapter_revision", "")),
                                source_start_line=entry.get("source_start_line"),
                                source_end_line=entry.get("source_end_line"),
                                source_excerpt=str(entry.get("source_excerpt", "") or entry.get("source_quote", "")),
                                claim_text=str(entry.get("claim_text", "")),
                                claim_type=str(entry.get("claim_type", "")),
                                epistemic_role=str(entry.get("epistemic_role", "")),
                                assumptions=list(entry.get("assumptions", []) or []),
                                qualifications=list(entry.get("qualifications", []) or []),
                                model_id=outcome.get("actual_model") if isinstance(outcome, dict) else None,
                                prompt_version=str(entry.get("prompt_version", "1") or "1"),
                                quote_validated=bool(entry.get("quote_validated", False)),
                                anchor_method=str(entry.get("anchor_method", "none") or "none"),
                                source_char_start=entry.get("source_char_start"),
                                source_char_end=entry.get("source_char_end"),
                                campaign_id=record.id,
                            )
                            record_claim(chapter_session, payload)
                        completed += 1
                        if isinstance(usage.get("input_tokens"), int):
                            usage_in += usage["input_tokens"]
                        if isinstance(usage.get("output_tokens"), int):
                            usage_out += usage["output_tokens"]
                        chapter_session.commit()
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    failures[chapter_id] = f"persist failed: {type(exc).__name__}: {str(exc)[:200]}"
                with session_factory() as chapter_session:
                    row = get_campaign(chapter_session, record.id)
                    row.completed = completed
                    row.skipped = skipped
                    row.failed = failed
                    row.remaining = max(0, len(selection) - completed - skipped - failed)
                    row.usage = {**(row.usage or {}), "input_tokens": usage_in,
                                 "output_tokens": usage_out, "failures": failures}
                    row.updated_at = now_iso()
                    chapter_session.commit()
        except _TechStop:
            with session_factory() as session:
                record = get_campaign(session, campaign_id)
                record.status = "partial"
                record.error = "stopped after the current chapter"
                _finish_counts(session, record, completed, skipped, failed, selection)
                session.commit()
            return get_fresh(session_factory, campaign_id)
        except Exception as exc:  # noqa: BLE001 - crash keeps progress
            with session_factory() as session:
                record = get_campaign(session, campaign_id)
                record.status = "interrupted"
                record.error = f"{type(exc).__name__}: {str(exc)[:300]}"
                _finish_counts(session, record, completed, skipped, failed, selection)
                session.commit()
            return get_fresh(session_factory, campaign_id)
        with session_factory() as session:
            record = get_campaign(session, campaign_id)
            _finish_counts(session, record, completed, skipped, failed, selection)
            final = "completed" if failed == 0 else "partial"
            _campaign_done(
                session, record, final,
                None if failed == 0 else f"{failed} chapter(s) failed; retry them with a selected rerun",
            )
            session.commit()
        return get_fresh(session_factory, campaign_id)


# ---------------------------------------------------------- 03C completeness

COVERAGE_STATUSES = (
    "NOT_STARTED", "RUNNING", "COMPLETED_WITHIN_BUDGET", "LIMIT_REACHED",
    "PARTIAL", "FAILED", "STALE",
    "OUTPUT_LIMIT_EXCEEDED", "TRUNCATED", "EMPTY",
)
REQUIREMENT_SATISFACTION = (
    "SATISFIED", "PARTIALLY_SATISFIED", "UNSATISFIED", "UNRESOLVED",
    "WAIVED_WITH_RATIONALE", "NOT_APPLICABLE", "NOT_ASSESSED", "STALE",
)
REQUIREMENT_APPLICABILITY = ("APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED")
GAP_TYPES = (
    "MISSING_LOCAL_ARTIFACT", "EXPERIMENT_NOT_RUN", "INCOMPLETE_EXPERIMENT",
    "MISSING_BASELINE", "MISSING_ASSUMPTIONS", "INSUFFICIENT_DERIVATION",
    "DOCUMENTATION_NOT_VERIFIED", "SOURCE_UNAVAILABLE", "INADEQUATE_SPAN",
    "CONFLICTING_EVIDENCE", "NOT_SEARCHED", "EXTRACTION_COVERAGE_GAP",
)
GAP_STATUSES = ("OPEN", "RESOLVED", "STALE")
LINK_RELATIONS = ("satisfies", "partially_satisfies", "contradicts", "depends_on")
CLAIM_LINK_RELATIONS = ("depends_on", "restates", "contradicts", "refines")


def _region_id(chapter_id: str, source_hash: str, char_start: int, char_end: int, title: str) -> str:
    digest = hashlib.sha256(
        f"{chapter_id}|{source_hash}|{char_start}|{char_end}|{title}".encode()
    ).hexdigest()[:16]
    return f"treg:{digest}"


def sync_regions(
    session: Session,
    *,
    project_id: str | None,
    book_id: str,
    chapter_id: str,
    source_path: str,
    source_hash: str,
    units: list[dict],
) -> list[TechnicalRegion]:
    """Idempotent region inventory from plan_sections-style units."""
    from mission_control.models import TechnicalRegion

    records = []
    for unit in units:
        title = str(unit.get("title", ""))
        span = unit.get("char_span", [0, 0]) or [0, 0]
        record = TechnicalRegion(
            id=_region_id(chapter_id, source_hash, int(span[0]), int(span[1]), title),
            project_id=project_id,
            book_id=book_id,
            chapter_id=chapter_id,
            title=title,
            source_path=source_path,
            source_hash=source_hash,
            char_start=int(span[0]),
            char_end=int(span[1]),
            byte_start=int((unit.get("byte_span", [0, 0]) or [0, 0])[0]),
            byte_end=int((unit.get("byte_span", [0, 0]) or [0, 0])[1]),
            unit_hash=str(unit.get("id", "")),
            parent_region_id=None,
            depth=0,
            source_kind="section",
        )
        existing = session.get(TechnicalRegion, record.id)
        if existing is None:
            session.add(record)
            session.flush()
            records.append(record)
        else:
            records.append(existing)
    return records


def list_regions(
    session: Session, *, project_id: str | None = None, chapter_id: str | None = None
) -> list["TechnicalRegion"]:
    from mission_control.models import TechnicalRegion

    stmt = select(TechnicalRegion).order_by(TechnicalRegion.chapter_id, TechnicalRegion.char_start)
    if project_id:
        stmt = stmt.where(TechnicalRegion.project_id == project_id)
    if chapter_id:
        stmt = stmt.where(TechnicalRegion.chapter_id == chapter_id)
    return list(session.scalars(stmt).all())


def record_coverage(
    session: Session,
    *,
    region_id: str,
    campaign_id: str | None = None,
    source_hash: str = "",
    extractor_version: str = "technical-claim-v1",
    model_id: str | None = None,
    prompt_version: str = "1",
    requested_limit: int = 40,
    returned_count: int = 0,
    status: str = "COMPLETED_WITHIN_BUDGET",
    limit_reached: bool = False,
    truncated: bool = False,
    error: str = "",
) -> "TechnicalExtractionCoverage":
    from mission_control.models import TechnicalExtractionCoverage

    if status not in COVERAGE_STATUSES:
        raise ValidationProblem(f"unknown coverage status {status!r}")
    if session.get(TechnicalRegion, region_id) is None:
        raise NotFound("Region does not exist")
    record = TechnicalExtractionCoverage(
        id=f"tcov:{uuid.uuid4().hex[:12]}",
        region_id=region_id,
        campaign_id=campaign_id,
        source_hash=source_hash,
        extractor_version=extractor_version,
        model_id=model_id,
        prompt_version=prompt_version,
        requested_limit=requested_limit,
        returned_count=returned_count,
        status=status,
        limit_reached=bool(limit_reached),
        truncated=bool(truncated),
        error=error,
    )
    session.add(record)
    session.flush()
    return record


def latest_coverage(
    session: Session, region_id: str
) -> "TechnicalExtractionCoverage | None":
    from mission_control.models import TechnicalExtractionCoverage

    stmt = (
        select(TechnicalExtractionCoverage)
        .where(TechnicalExtractionCoverage.region_id == region_id)
        .order_by(desc(TechnicalExtractionCoverage.created_at))
        .limit(1)
    )
    return session.scalars(stmt).first()


# ---------------------------------------------------------- 04A-03B strategy runs

EXTRACTION_STRATEGIES = ("whole_continuation", "region_single", "region_grouped")
RUN_STATUSES = (
    "NOT_RUN", "RUNNING", "COMPLETED_WITHIN_BUDGET", "LIMIT_REACHED",
    "OUTPUT_LIMIT_EXCEEDED", "TRUNCATED", "EMPTY", "PARTIAL", "FAILED", "STALE",
)

# Token-estimate heuristic for request planning (04A-03B). Prompt overhead
# dominates small regions (~3.5k input tokens measured on the 04A-01 probe);
# body text is estimated at ~4 chars/token. Estimates, never guarantees —
# actual usage is metered per run and enforced against ceilings.
PLAN_PROMPT_OVERHEAD_TOKENS = 3500
PLAN_CHARS_PER_TOKEN = 4


def record_extraction_run(
    session: Session, payload: "TechnicalExtractionRunCreate"
) -> "TechnicalExtractionRun":
    from mission_control.models import TechnicalExtractionRun

    if payload.strategy not in EXTRACTION_STRATEGIES:
        raise ValidationProblem(f"unknown strategy {payload.strategy!r}")
    if payload.status not in RUN_STATUSES:
        raise ValidationProblem(f"unknown run status {payload.status!r}")
    if payload.requested_limit < 1 or payload.requested_limit > 200:
        raise ValidationProblem("requested_limit must be 1..200")
    if payload.campaign_id and session.get(QualityCampaign, payload.campaign_id) is None:
        raise ValidationProblem("Campaign does not exist")
    record = TechnicalExtractionRun(
        id=f"trun:{uuid.uuid4().hex[:12]}",
        campaign_id=payload.campaign_id,
        strategy=payload.strategy,
        chapter_id=payload.chapter_id,
        region_ids=list(payload.region_ids or []),
        requested_limit=payload.requested_limit,
        returned_count=payload.returned_count,
        accepted_count=payload.accepted_count,
        status=payload.status,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
        model_id=payload.model_id,
        prompt_version=payload.prompt_version,
        source_revision=payload.source_revision,
        manifest_hash=payload.manifest_hash,
        error=payload.error,
    )
    session.add(record)
    session.flush()
    return record


def list_extraction_runs(
    session: Session, *, campaign_id: str | None = None,
    chapter_id: str | None = None, limit: int = 500,
) -> list["TechnicalExtractionRun"]:
    from mission_control.models import TechnicalExtractionRun

    stmt = select(TechnicalExtractionRun).order_by(desc(TechnicalExtractionRun.created_at))
    if campaign_id:
        stmt = stmt.where(TechnicalExtractionRun.campaign_id == campaign_id)
    if chapter_id:
        stmt = stmt.where(TechnicalExtractionRun.chapter_id == chapter_id)
    return list(session.scalars(stmt.limit(limit)).all())


def plan_extraction_requests(
    *,
    chapter_id: str,
    chapter_chars: int,
    regions: list[dict],
    strategy: str,
    requested_limit: int = 40,
    context_chars: int = 800,
    target_request_chars: int = 9000,
) -> list[dict]:
    """Deterministic, model-free request plan for one chapter (04A-03B).

    Each spec carries target char spans (not counted as processed until a
    run completes), context windows marked read-only, and heuristic token
    estimates. Grouping prefers whole adjacent regions that fit the target
    size without splitting equations/captions — here approximated by not
    splitting individual regions; callers pass pre-sized regions.
    """
    if strategy not in EXTRACTION_STRATEGIES:
        raise ValidationProblem(f"unknown strategy {strategy!r}")
    if requested_limit < 1 or requested_limit > 200:
        raise ValidationProblem("requested_limit must be 1..200")

    def estimate(input_chars: int, output_claims: int) -> dict:
        # ~240 output tokens/claim measured on the 04A-01 probe (875/7
        # with margin); input is overhead + body estimate.
        return {
            "input_tokens": PLAN_PROMPT_OVERHEAD_TOKENS + max(0, input_chars) // PLAN_CHARS_PER_TOKEN,
            "output_tokens": 800 + output_claims * 240,
        }

    specs: list[dict] = []
    if strategy == "whole_continuation":
        est = estimate(chapter_chars, requested_limit)
        specs.append({
            "strategy": strategy, "chapter_id": chapter_id,
            "region_ids": [r["id"] for r in regions],
            "char_span": [0, chapter_chars],
            "context_chars": 0, "requested_limit": requested_limit,
            "pass": 1, "role": "initial",
            "estimated_input_tokens": est["input_tokens"],
            "estimated_output_tokens": est["output_tokens"],
        })
        # Bounded continuation pass excludes already-seen claims.
        specs.append({
            "strategy": strategy, "chapter_id": chapter_id,
            "region_ids": [r["id"] for r in regions],
            "char_span": [0, chapter_chars],
            "context_chars": 0, "requested_limit": requested_limit,
            "pass": 2, "role": "continuation",
            "excludes_claims_from_pass": 1,
            "estimated_input_tokens": est["input_tokens"] + requested_limit * 40,
            "estimated_output_tokens": est["output_tokens"],
        })
        return specs

    # Region strategies: group adjacent regions up to the target size.
    ordered = sorted(regions, key=lambda r: (r.get("char_start", 0), r.get("id", "")))
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for region in ordered:
        size = max(0, region.get("char_end", 0) - region.get("char_start", 0))
        if strategy == "region_single" or (current and current_chars + size > target_request_chars):
            if current:
                groups.append(current)
            current, current_chars = [], 0
        current.append(region)
        current_chars += size
    if current:
        groups.append(current)
    for index, group in enumerate(groups, start=1):
        lo = min(r.get("char_start", 0) for r in group)
        hi = max(r.get("char_end", 0) for r in group)
        body = hi - lo
        est = estimate(body + 2 * context_chars, requested_limit)
        # Calibrated cap: ~150 tokens/claim measured (04A-01 probe), claims
        # scale ~1 per 1200 chars; floor 600 for JSON scaffolding; the 16k
        # model-interface limit is the hard per-request bound.
        est["output_tokens"] = min(
            16000, 600 + 150 * max(1, min(requested_limit, body // 1200)))
        specs.append({
            "strategy": strategy, "chapter_id": chapter_id,
            "region_ids": [r["id"] for r in group],
            "char_span": [lo, hi],
            "context_chars": context_chars, "requested_limit": requested_limit,
            "pass": index, "role": "grouped" if len(group) > 1 else "single",
            "estimated_input_tokens": est["input_tokens"],
            "estimated_output_tokens": est["output_tokens"],
        })
    return specs


def check_budget(*, used_input: int, used_output: int, used_calls: int,
                 max_input: int, max_output: int, max_calls: int) -> None:
    """Hard budget gate for extraction execution (04A-03B)."""
    if used_calls >= max_calls:
        raise ValidationProblem(
            f"call budget exhausted ({used_calls}/{max_calls}); stop, do not continue")
    if used_input >= max_input:
        raise ValidationProblem(
            f"input token budget exhausted ({used_input}/{max_input}); stop, do not continue")
    if used_output >= max_output:
        raise ValidationProblem(
            f"output token budget exhausted ({used_output}/{max_output}); stop, do not continue")


def classify_cli_output(out: dict) -> dict:
    """Map one extractor CLI result to a campaign action (04A-03B).

    Returns {"action": "persist"|"quarantine"|"fail", "run_status": ...,
    "error": ...}. Quarantined output (over-limit, truncated, empty) is
    metered but never persisted as complete extraction; the work unit fails
    and stays eligible for retry. Pure and deterministic — the API layer
    applies it, tests assert it.
    """
    status = str(out.get("status", ""))
    if status in ("BLOCKED", "ERROR") and "claims" not in out:
        return {"action": "fail", "run_status": "FAILED",
                "error": str(out.get("error", "evaluator failed"))[:300]}
    if status in ("OUTPUT_LIMIT_EXCEEDED", "TRUNCATED", "EMPTY"):
        usage = f" (metered {out.get('input_tokens', 0)} in / {out.get('output_tokens', 0)} out)"
        return {"action": "quarantine", "run_status": status,
                "error": f"extraction quarantined as {status}{usage}"}
    if status == "LIMIT_REACHED":
        return {"action": "persist", "run_status": "LIMIT_REACHED", "error": ""}
    return {"action": "persist",
            "run_status": "COMPLETED_WITHIN_BUDGET" if status in ("CURRENT", "") else "PARTIAL",
            "error": ""}


def find_duplicate_candidates(claims: list) -> list[dict]:
    """Candidate duplicate pairs across extraction passes (04A-03B).

    Source identity is strong evidence; normalized-text similarity is a
    candidate, never an automatic merge. Callers link via `restates`
    relations after review; nothing here rewrites claims."""
    import re as _re

    def norm(text: str | None) -> str:
        return _re.sub(r"\s+", " ", (text or "").strip().lower())

    pairs: list[dict] = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            reasons: list[str] = []
            if norm(getattr(claims[i], "claim_text", "")) and \
                    norm(getattr(claims[i], "claim_text", "")) == norm(getattr(claims[j], "claim_text", "")):
                reasons.append("same-normalized-claim-text")
            if norm(getattr(claims[i], "source_excerpt", "")) and \
                    norm(getattr(claims[i], "source_excerpt", "")) == norm(getattr(claims[j], "source_excerpt", "")):
                reasons.append("same-source-excerpt")
            if reasons:
                pairs.append({
                    "first_id": getattr(claims[i], "id", ""),
                    "second_id": getattr(claims[j], "id", ""),
                    "reasons": reasons,
                })
    return pairs


def record_requirement(
    session: Session, payload: "TechnicalRequirementCreate"
) -> "TechnicalEvidenceRequirement":
    from mission_control.models import TechnicalEvidenceRequirement

    get_claim(session, payload.claim_id)
    if payload.applicability not in REQUIREMENT_APPLICABILITY:
        raise ValidationProblem(f"unknown applicability {payload.applicability!r}")
    digest = hashlib.sha256(
        f"{payload.claim_id}|{payload.requirement_key}|{payload.spec_version}".encode()
    ).hexdigest()[:16]
    record = TechnicalEvidenceRequirement(
        id=f"treq:{digest}",
        claim_id=payload.claim_id,
        requirement_key=payload.requirement_key,
        label=payload.label,
        requirement_type=payload.requirement_type,
        acceptance_rule=payload.acceptance_rule,
        rationale=payload.rationale,
        spec_version=payload.spec_version,
        applicability=payload.applicability,
        applicability_reason=payload.applicability_reason,
        satisfaction="NOT_ASSESSED",
        campaign_id=payload.campaign_id,
    )
    existing = session.get(TechnicalEvidenceRequirement, record.id)
    if existing is not None:
        return existing
    session.add(record)
    session.flush()
    return record


def list_requirements(session: Session, claim_id: str) -> list["TechnicalEvidenceRequirement"]:
    from mission_control.models import TechnicalEvidenceRequirement

    get_claim(session, claim_id)
    stmt = (
        select(TechnicalEvidenceRequirement)
        .where(TechnicalEvidenceRequirement.claim_id == claim_id)
        .order_by(TechnicalEvidenceRequirement.requirement_key)
    )
    return list(session.scalars(stmt).all())


def set_requirement_status(
    session: Session,
    requirement_id: str,
    *,
    satisfaction: str,
    detail: str = "",
    waived_reason: str = "",
) -> "TechnicalEvidenceRequirement":
    from mission_control.models import TechnicalEvidenceRequirement

    if satisfaction not in REQUIREMENT_SATISFACTION:
        raise ValidationProblem(f"unknown satisfaction {satisfaction!r}")
    record = session.get(TechnicalEvidenceRequirement, requirement_id)
    if record is None:
        raise NotFound("Requirement does not exist")
    if satisfaction == "WAIVED_WITH_RATIONALE" and not waived_reason.strip():
        raise ValidationProblem("a waived requirement needs an explicit reason")
    if satisfaction == "WAIVED_WITH_RATIONALE":
        record.waived_reason = waived_reason
    record.satisfaction = satisfaction
    record.satisfaction_detail = detail
    session.flush()
    return record


def link_requirement_evidence(
    session: Session, payload: "TechnicalRequirementLinkCreate"
) -> "TechnicalRequirementLink":
    from mission_control.models import TechnicalEvidenceRequirement, TechnicalRequirementLink

    if session.get(TechnicalEvidenceRequirement, payload.requirement_id) is None:
        raise NotFound("Requirement does not exist")
    if payload.evidence_id and session.get(TechnicalEvidence, payload.evidence_id) is None:
        raise NotFound("Evidence does not exist")
    if payload.relation not in LINK_RELATIONS:
        raise ValidationProblem(f"unknown relation {payload.relation!r}")
    record = TechnicalRequirementLink(
        id=f"trlink:{uuid.uuid4().hex[:12]}",
        requirement_id=payload.requirement_id,
        evidence_id=payload.evidence_id,
        relation=payload.relation,
        note=payload.note,
    )
    session.add(record)
    session.flush()
    return record


def link_claims(session: Session, payload: "TechnicalClaimLinkCreate") -> "TechnicalClaimLink":
    from mission_control.models import TechnicalClaimLink

    if payload.relation not in CLAIM_LINK_RELATIONS:
        raise ValidationProblem(f"unknown relation {payload.relation!r}")
    get_claim(session, payload.from_claim_id)
    get_claim(session, payload.to_claim_id)
    if payload.from_claim_id == payload.to_claim_id:
        raise ValidationProblem("a claim cannot link to itself")
    record = TechnicalClaimLink(
        id=f"tclink:{uuid.uuid4().hex[:12]}",
        from_claim_id=payload.from_claim_id,
        to_claim_id=payload.to_claim_id,
        relation=payload.relation,
        note=payload.note,
    )
    session.add(record)
    session.flush()
    return record


def record_gap(session: Session, payload: "TechnicalGapCreate") -> "TechnicalGap":
    from mission_control.models import TechnicalGap

    if payload.gap_type not in GAP_TYPES:
        raise ValidationProblem(f"unknown gap type {payload.gap_type!r}")
    if payload.claim_id:
        get_claim(session, payload.claim_id)
    record = TechnicalGap(
        id=f"tgap:{uuid.uuid4().hex[:12]}",
        project_id=payload.project_id,
        book_id=payload.book_id,
        chapter_id=payload.chapter_id,
        claim_id=payload.claim_id,
        requirement_id=payload.requirement_id,
        gap_type=payload.gap_type,
        title=payload.title,
        detail=payload.detail,
        searched_scope=payload.searched_scope,
        status="OPEN",
        priority_rationale=payload.priority_rationale,
        campaign_id=payload.campaign_id,
    )
    session.add(record)
    session.flush()
    return record


def list_gaps(
    session: Session, *, project_id: str | None = None, chapter_id: str | None = None,
    status: str | None = None, limit: int = 500,
) -> list["TechnicalGap"]:
    from mission_control.models import TechnicalGap

    stmt = select(TechnicalGap).order_by(desc(TechnicalGap.created_at))
    if project_id:
        stmt = stmt.where(TechnicalGap.project_id == project_id)
    if chapter_id:
        stmt = stmt.where(TechnicalGap.chapter_id == chapter_id)
    if status:
        stmt = stmt.where(TechnicalGap.status == status)
    return list(session.scalars(stmt.limit(limit)).all())


def set_gap_status(session: Session, gap_id: str, status: str) -> "TechnicalGap":
    from mission_control.models import TechnicalGap

    if status not in ("OPEN", "RESOLVED", "STALE"):
        raise ValidationProblem(f"unknown gap status {status!r}")
    record = session.get(TechnicalGap, gap_id)
    if record is None:
        raise NotFound("Gap does not exist")
    record.status = status
    session.flush()
    return record


def record_objective(session: Session, payload: "TechnicalObjectiveCreate") -> "TechnicalObjective":
    from mission_control.models import TechnicalObjective

    if payload.source not in ("explicit", "inferred"):
        raise ValidationProblem("objective source must be explicit or inferred")
    if payload.status not in ("proposed", "confirmed", "dropped"):
        raise ValidationProblem(f"unknown objective status {payload.status!r}")
    record = TechnicalObjective(
        id=f"tobj:{uuid.uuid4().hex[:12]}",
        project_id=payload.project_id,
        book_id=payload.book_id,
        chapter_id=payload.chapter_id,
        statement=payload.statement,
        source=payload.source,
        status=payload.status,
    )
    session.add(record)
    session.flush()
    return record


def link_objective_claim(session: Session, payload: "TechnicalObjectiveClaimCreate") -> "TechnicalObjectiveClaim":
    from mission_control.models import TechnicalObjective, TechnicalObjectiveClaim

    if session.get(TechnicalObjective, payload.objective_id) is None:
        raise NotFound("Objective does not exist")
    get_claim(session, payload.claim_id)
    if payload.role not in ("supports", "partially_supports", "contradicts", "context"):
        raise ValidationProblem(f"unknown link role {payload.role!r}")
    record = TechnicalObjectiveClaim(
        objective_id=payload.objective_id,
        claim_id=payload.claim_id,
        role=payload.role,
    )
    session.merge(record)
    session.flush()
    return record


def list_objectives(
    session: Session, *, project_id: str | None = None, chapter_id: str | None = None
) -> list["TechnicalObjective"]:
    from mission_control.models import TechnicalObjective

    stmt = select(TechnicalObjective).order_by(TechnicalObjective.created_at)
    if project_id:
        stmt = stmt.where(TechnicalObjective.project_id == project_id)
    if chapter_id:
        stmt = stmt.where(TechnicalObjective.chapter_id == chapter_id)
    return list(session.scalars(stmt).all())


def chapter_completeness(
    session: Session, project_id: str, chapter_id: str, book_root: str | None = None
) -> dict:
    """Coverage + requirements + gaps for one chapter, computed from stored rows.

    live_revision is read from disk when book_root is provided; otherwise
    staleness falls back to recorded source hashes.
    """
    import hashlib
    import os

    claims = [c for c in list_claims(session, project_id=project_id, chapter_id=chapter_id, limit=10000)
              if not c.source_excerpt or True]
    try:
        from mission_control.quality.service import resolve_book_root
        root = book_root or resolve_book_root(session, project_id)
        chapter_path = os.path.join(root, chapter_id)
        live_revision = None
        if os.path.isfile(chapter_path):
            digest = hashlib.sha256()
            with open(chapter_path, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk.replace(b"\r\n", b"\n"))
            live_revision = digest.hexdigest()
    except Exception:  # noqa: BLE001 - discovery failures degrade to recorded hashes
        live_revision = None
        root = None
    from mission_control.models import TechnicalEvidenceRequirement

    regions = [r for r in list_regions(session, project_id=project_id, chapter_id=chapter_id)]
    coverages = []
    for region in regions:
        cov = latest_coverage(session, region.id)
        coverages.append((region, cov))
    processed = sum(1 for _, cov in coverages if cov and cov.status in ("COMPLETED_WITHIN_BUDGET", "LIMIT_REACHED", "PARTIAL"))
    capped = sum(1 for _, cov in coverages if cov and cov.status == "LIMIT_REACHED")
    failed = sum(1 for _, cov in coverages if cov and cov.status == "FAILED")
    not_started = sum(1 for _, cov in coverages if cov is None or cov.status == "NOT_STARTED")
    stale_regions = sum(
        1 for region, cov in coverages
        if cov and live_revision and cov.source_hash and cov.source_hash != live_revision
    )
    req_rows = []
    for claim in claims:
        req_rows.extend(
            session.scalars(
                select(TechnicalEvidenceRequirement).where(
                    TechnicalEvidenceRequirement.claim_id == claim.id
                )
            ).all()
        )
    by_satisfaction: dict[str, int] = {}
    by_applicability: dict[str, int] = {}
    for req in req_rows:
        by_satisfaction[req.satisfaction] = by_satisfaction.get(req.satisfaction, 0) + 1
        by_applicability[req.applicability] = by_applicability.get(req.applicability, 0) + 1
    gaps = [g for g in list_gaps(session, project_id=project_id, chapter_id=chapter_id, limit=1000)
            if g.status == "OPEN"]
    stale_claims = [c.id for c in claims if live_revision and c.source_revision != live_revision]
    source_verified = sum(1 for c in claims if c.quote_validated)
    return {
        "chapter_id": chapter_id,
        "live_revision": live_revision,
        "regions_total": len(coverages),
        "regions_processed": processed,
        "regions_capped": capped,
        "regions_failed": failed,
        "regions_not_started": not_started,
        "regions_stale": stale_regions,
        "claims_total": len(claims),
        "claims_source_verified": source_verified,
        "claims_stale": len(stale_claims),
        "requirements_total": len(req_rows),
        "by_satisfaction": by_satisfaction,
        "by_applicability": by_applicability,
        "open_gaps": len(gaps),
        "gap_types": sorted({g.gap_type for g in gaps}),
        "assessment": (
            "COMPLETE" if (coverages and processed == len(coverages) and not gaps and by_satisfaction.get("UNRESOLVED", 0) == 0)
            else "PARTIAL" if (coverages or claims) else "NOT_ASSESSED"
        ),
    }
