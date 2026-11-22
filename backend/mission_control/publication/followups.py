"""Governed follow-ups: promote a publishing blocker to explicit, traceable
work (MC-PUBLISH-03).

A follow-up bridges evidence and action. It carries provenance (evidence type,
source reference, fingerprint, observed_at) so it can be re-checked against
fresh evidence: open -> re-evidenced -> closed. History is never rewritten;
closing marks the row. The actual work item is a regular Mission Control task
or decision created through the existing projects service — no parallel work
system, no silent side effects. Every transition records an activity entry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.models import Project, PublicationFollowup
from mission_control.persistence.db import now_iso
from mission_control.schemas import DecisionCreate, TaskCreate

logger = logging.getLogger(__name__)

FOLLOWUP_STATUSES = ("open", "re-evidenced", "closed")
FOLLOWUP_TARGETS = ("task", "decision")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def fingerprint_evidence(item: dict[str, Any]) -> str:
    """Stable fingerprint of one evidence item for re-check comparison."""
    canonical = json.dumps(
        {key: item.get(key) for key in sorted(item.keys())},
        sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def create_followup(
    session: Session,
    *,
    project_id: str,
    book_id: str = "",
    evidence_type: str,
    source_reference: str = "",
    fingerprint: str = "",
    observed_at: str = "",
    target_type: str = "task",
    title: str = "",
    rationale: str = "",
    reviewer: str = "",
) -> dict[str, Any]:
    """Promote a blocker to a task or decision, carrying its provenance."""
    if session.get(Project, project_id) is None:
        raise NotFound("Project not found.")
    if not str(evidence_type or "").strip():
        raise ValidationProblem("A follow-up needs the evidence_type it came from.")
    if target_type not in FOLLOWUP_TARGETS:
        raise ValidationProblem(
            f"Unknown follow-up target: {target_type}. Use one of: {', '.join(FOLLOWUP_TARGETS)}.")
    heading = title.strip() or f"Publishing follow-up: {evidence_type}"
    provenance = (
        f"Promoted from publishing evidence '{evidence_type}' "
        f"({source_reference or 'no source reference'}; observed {observed_at or 'unknown'}). "
        f"{rationale.strip()}"
    ).strip()
    if target_type == "decision":
        from mission_control.projects import service as _projects

        target = _projects.create_decision(
            session,
            DecisionCreate(project_id=project_id, title=heading[:300],
                           rationale=provenance[:4000], status="deferred"),
        )
        target_id: str | None = target.id
    else:
        from mission_control.projects import service as _projects

        target = _projects.create_task(
            session,
            TaskCreate(project_id=project_id, title=heading[:300],
                       description=provenance[:4000], status="open"),
        )
        target_id = target.id
    row = PublicationFollowup(
        id=_new_id("pfl"), project_id=project_id, book_id=book_id or "",
        evidence_type=str(evidence_type)[:120], source_reference=source_reference[:2000],
        fingerprint=fingerprint[:64], observed_at=observed_at[:40],
        target_type=target_type, target_id=target_id,
        title=heading[:300], rationale=rationale[:4000],
        status="open", reviewer=reviewer[:120],
        created_at=now_iso(), updated_at=now_iso())
    session.add(row)
    session.flush()
    record_activity(
        session, event_type="publishing_followup",
        title=f"Publishing follow-up opened: {heading}",
        detail=f"Evidence '{evidence_type}' promoted to {target_type} {target_id}.",
        project_id=project_id, source="mission-control", provenance="verified_observation",
        metadata={"followup_id": row.id, "target_type": target_type,
                  "target_id": target_id, "evidence_type": evidence_type},
        dedupe_key=f"followup-open-{row.id}",
    )
    logger.info("Opened publishing follow-up %s for %s (%s)", row.id, project_id, evidence_type)
    return followup_read(row)


def followup_read(row: PublicationFollowup) -> dict[str, Any]:
    return {"id": row.id, "project_id": row.project_id, "book_id": row.book_id,
            "evidence_type": row.evidence_type, "source_reference": row.source_reference,
            "fingerprint": row.fingerprint, "observed_at": row.observed_at,
            "target_type": row.target_type, "target_id": row.target_id,
            "title": row.title, "rationale": row.rationale, "status": row.status,
            "reviewer": row.reviewer, "created_at": row.created_at,
            "updated_at": row.updated_at}


def list_followups(
    session: Session, *, project_id: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    query = select(PublicationFollowup).order_by(desc(PublicationFollowup.created_at))
    if project_id:
        query = query.where(PublicationFollowup.project_id == project_id)
    if status:
        if status not in FOLLOWUP_STATUSES:
            raise ValidationProblem(f"Unknown follow-up status: {status}")
        query = query.where(PublicationFollowup.status == status)
    return [followup_read(row) for row in session.scalars(query.limit(200)).all()]


def get_followup(session: Session, followup_id: str) -> PublicationFollowup:
    row = session.get(PublicationFollowup, followup_id)
    if row is None:
        raise NotFound("Follow-up not found.")
    return row


def recheck_followup(session: Session, settings: Any, followup_id: str) -> dict[str, Any]:
    """Re-read fresh evidence and compare fingerprints.

    A changed fingerprint moves the follow-up to re-evidenced; an identical
    one leaves it open. Nothing is auto-closed: closing stays an explicit
    author action.
    """
    from mission_control.publication import publishing as _publishing

    row = get_followup(session, followup_id)
    if row.status == "closed":
        raise Conflict("A closed follow-up is history; open a new one instead of re-checking it.")
    summary = _publishing.get_publishing_summary(session, settings, row.project_id)
    candidates = [
        item for item in summary.get("evidence", [])
        if isinstance(item, dict) and item.get("evidence_type") == row.evidence_type
    ]
    current = None
    for item in candidates:
        if not row.source_reference or item.get("source_reference") == row.source_reference:
            current = item
            break
    if current is None and candidates:
        # Same evidence type, different reference: still the same dimension,
        # so re-check against it rather than reporting the evidence gone.
        current = candidates[0]
    if current is None:
        raise NotFound("The originating evidence is no longer reported; the follow-up stays open.")
    fresh = fingerprint_evidence(current)
    changed = bool(row.fingerprint) and fresh != row.fingerprint
    previous = row.status
    if changed:
        row.status = "re-evidenced"
        row.fingerprint = fresh
        row.observed_at = str(current.get("observed_at") or summary.get("observed_at") or now_iso())
        row.updated_at = now_iso()
    session.flush()
    record_activity(
        session, event_type="publishing_followup",
        title=f"Publishing follow-up re-checked: {row.title}",
        detail=("Evidence changed since promotion; marked re-evidenced."
                if changed and previous != "re-evidenced"
                else "Evidence matches the promotion snapshot; still open."),
        project_id=row.project_id, source="mission-control", provenance="verified_observation",
        metadata={"followup_id": row.id, "changed": changed,
                  "evidence_type": row.evidence_type},
        dedupe_key=f"followup-recheck-{row.id}-{fresh[:12]}",
    )
    return {"followup": followup_read(row), "changed": changed,
            "current": current, "previous_status": previous}


def close_followup(
    session: Session, followup_id: str, *, rationale: str = "", reviewer: str = ""
) -> dict[str, Any]:
    row = get_followup(session, followup_id)
    if row.status == "closed":
        return followup_read(row)
    row.status = "closed"
    if rationale.strip():
        row.rationale = (row.rationale + "\n\nClose-out: " + rationale.strip())[:4000]
    if reviewer.strip():
        row.reviewer = reviewer.strip()[:120]
    row.updated_at = now_iso()
    session.flush()
    record_activity(
        session, event_type="publishing_followup",
        title=f"Publishing follow-up closed: {row.title}",
        detail=rationale.strip() or "Closed by the author.",
        project_id=row.project_id, source="mission-control", provenance="verified_observation",
        metadata={"followup_id": row.id},
        dedupe_key=f"followup-close-{row.id}",
    )
    return followup_read(row)
