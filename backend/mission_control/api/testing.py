"""Central testing visibility for AI Test (AITEST-02 R12).

AI Test remains authoritative for local inventory and evidence; this API is
the governed ingestion + presentation layer.  No pytest plugin ever touches
these tables directly — delivery is via buffered ``aitest mission sync``
POSTs of the versioned ``aitest.event.v1`` envelope (or the bulk sync
document), idempotent by ``event_id``.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.models import (
    AitestEventSeen,
    AitestIssue,
    AitestProject,
    AitestQuality,
    AitestReceipt,
    AitestTest,
)
from mission_control.persistence.db import now_iso, utcnow
from mission_control.schemas import (
    AitestEventIngest,
    AitestIssueRead,
    AitestProjectRead,
    AitestReceiptRead,
    AitestSummaryRead,
    AitestTestRead,
)

router = APIRouter(prefix="/api/tests", tags=["tests"])


def _project_read(p: AitestProject) -> AitestProjectRead:
    return AitestProjectRead(
        project_id=p.project_id, name=p.name, root=p.root,
        remote_url=p.remote_url, mc_project_id=p.mc_project_id,
        integration_state=p.integration_state, policy=p.policy,
        aitest_version=p.aitest_version, last_receipt_id=p.last_receipt_id,
        last_status=p.last_status, last_seen_at=p.last_seen_at,
    )


@router.get("/summary", response_model=AitestSummaryRead)
def tests_summary(session: Session = Depends(get_session)) -> AitestSummaryRead:
    # RETIRED tests are history (tombstones), never part of the live
    # population or its pass/fail totals.
    live = AitestTest.lifecycle != "RETIRED"
    projects = session.scalar(select(func.count(AitestProject.project_id))) or 0
    total = session.scalar(select(func.count(AitestTest.logical_id)).where(live)) or 0
    assessed = session.scalar(
        select(func.count(AitestTest.logical_id)).where(
            live, AitestTest.band != "UNASSESSED")) or 0
    healthy = session.scalar(
        select(func.count(AitestTest.logical_id)).where(
            live, AitestTest.lifecycle == "ACTIVE",
            AitestTest.last_outcome == "passed")) or 0
    failing = session.scalar(
        select(func.count(AitestTest.logical_id)).where(
            live, AitestTest.last_outcome == "failed")) or 0
    quarantined = session.scalar(
        select(func.count(AitestTest.logical_id)).where(
            live, AitestTest.lifecycle == "QUARANTINED")) or 0
    deferred = session.scalar(
        select(func.count(AitestTest.logical_id)).where(
            live, AitestTest.lifecycle.in_(["DEFERRED", "CANDIDATE"]))) or 0
    repair = session.scalar(
        select(func.count(AitestIssue.id)).where(AitestIssue.status == "open")) or 0
    return AitestSummaryRead(
        projects=projects, total_tests=total, assessed=assessed,
        unassessed=max(0, total - assessed), healthy=healthy, failing=failing,
        quarantined=quarantined, deferred=deferred, repair_needed=repair)


@router.get("/projects", response_model=list[AitestProjectRead])
def tests_projects(session: Session = Depends(get_session)) -> list[AitestProjectRead]:
    rows = session.scalars(select(AitestProject).order_by(AitestProject.name)).all()
    return [_project_read(p) for p in rows]


@router.get("/projects/{project_id}", response_model=AitestProjectRead)
def tests_project(project_id: str,
                  session: Session = Depends(get_session)) -> AitestProjectRead:
    p = session.get(AitestProject, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="unknown testing project")
    return _project_read(p)


@router.get("/projects/{project_id}/inventory", response_model=list[AitestTestRead])
def tests_inventory(project_id: str,
                    lifecycle: str | None = Query(default=None),
                    band: str | None = Query(default=None),
                    outcome: str | None = Query(default=None),
                    search: str | None = Query(default=None),
                    limit: int = Query(default=100, le=500),
                    offset: int = Query(default=0, ge=0),
                    session: Session = Depends(get_session)) -> list[AitestTestRead]:
    q = select(AitestTest).where(AitestTest.project_id == project_id)
    if lifecycle:
        q = q.where(AitestTest.lifecycle == lifecycle)
    if band:
        q = q.where(AitestTest.band == band)
    if outcome:
        q = q.where(AitestTest.last_outcome == outcome)
    if search:
        like = f"%{search}%"
        q = q.where((AitestTest.func_name.like(like)) | (AitestTest.relpath.like(like)))
    rows = session.scalars(q.order_by(desc(AitestTest.duration_ms)).limit(limit).offset(offset)).all()
    return [AitestTestRead(project_id=t.project_id, logical_id=t.logical_id,
                           relpath=t.relpath, class_name=t.class_name, func_name=t.func_name,
                           duration_ms=t.duration_ms, band=t.band, lifecycle=t.lifecycle,
                           last_outcome=t.last_outcome, last_seen_at=t.last_seen_at)
            for t in rows]


@router.get("/projects/{project_id}/receipts", response_model=list[AitestReceiptRead])
def tests_receipts(project_id: str,
                   limit: int = Query(default=20, le=100),
                   session: Session = Depends(get_session)) -> list[AitestReceiptRead]:
    rows = session.scalars(
        select(AitestReceipt).where(AitestReceipt.project_id == project_id)
        .order_by(desc(AitestReceipt.created_at)).limit(limit)).all()
    return [AitestReceiptRead(execution_id=r.execution_id, project_id=r.project_id,
                              snapshot_id=r.snapshot_id, status=r.status,
                              discovered=r.discovered, executed=r.executed, passed=r.passed,
                              failed=r.failed, skipped=r.skipped, quarantined=r.quarantined,
                              deferred=r.deferred, timed_out=r.timed_out, unobserved=r.unobserved,
                              duration_ms=r.duration_ms, created_at=r.created_at)
            for r in rows]


@router.get("/projects/{project_id}/issues", response_model=list[AitestIssueRead])
def tests_issues(project_id: str,
                 status: str | None = Query(default=None),
                 session: Session = Depends(get_session)) -> list[AitestIssueRead]:
    q = select(AitestIssue).where(AitestIssue.project_id == project_id)
    if status:
        q = q.where(AitestIssue.status == status)
    rows = session.scalars(q.order_by(desc(AitestIssue.updated_at)).limit(200)).all()
    return [AitestIssueRead(id=i.id, project_id=i.project_id, test_logical_id=i.test_logical_id,
                            kind=i.kind, title=i.title, status=i.status,
                            created_at=i.created_at, updated_at=i.updated_at)
            for i in rows]


@router.post("/rebuild")
def rebuild_registry(session: Session = Depends(get_session)) -> dict:
    """Drop derived test rows so the registry can be re-synced cleanly.

    Source of truth is each project's local AI Test ledger; this endpoint only
    clears MI-derived cache tables (tests/receipts/issues), never projects and
    never any operational application data.  Caller re-syncs afterwards.
    """
    from sqlalchemy import delete as _delete

    tests = session.execute(_delete(AitestTest)).rowcount or 0
    receipts = session.execute(_delete(AitestReceipt)).rowcount or 0
    issues = session.execute(_delete(AitestIssue)).rowcount or 0
    session.flush()
    return {"cleared_tests": tests, "cleared_receipts": receipts,
            "cleared_issues": issues,
            "note": "re-sync projects to repopulate from local ledgers"}


@router.post("/reconcile")
def reconcile_projects(session: Session = Depends(get_session)) -> dict:
    """Merge testing projects that describe the same checkout.

    Keeps the identity with the most registered tests, moves unique test rows
    onto it, and drops the now-empty duplicate.  Only AI Test's own registry
    tables are touched.
    """
    rows = session.scalars(select(AitestProject)).all()
    groups: dict[str, list[AitestProject]] = {}
    for p in rows:
        # Same checkout, or same registered testing name: one identity.
        key = (p.name or "").strip().lower() or (p.root or "").rstrip("\\/").lower()
        groups.setdefault(key, []).append(p)
    merged = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        counts = {
            p.project_id: session.scalar(
                select(func.count(AitestTest.logical_id)).where(
                    AitestTest.project_id == p.project_id)) or 0
            for p in group
        }
        keep = max(group, key=lambda p: counts[p.project_id])
        keep_ids = {
            r[0] for r in session.execute(
                select(AitestTest.logical_id).where(
                    AitestTest.project_id == keep.project_id)).all()
        }
        for dup in group:
            if dup.project_id == keep.project_id:
                continue
            for t in session.scalars(
                    select(AitestTest).where(
                        AitestTest.project_id == dup.project_id)).all():
                if t.logical_id in keep_ids:
                    session.delete(t)
                else:
                    t.project_id = keep.project_id
            session.delete(dup)
            merged.append({"dropped": dup.project_id, "kept": keep.project_id,
                           "root": keep.root})
    session.flush()
    return {"merged": merged, "projects": session.scalar(
        select(func.count(AitestProject.project_id)))}


@router.get("/worker")
def tests_worker() -> dict:
    """Heartbeat from the AI Test assessment worker (local file; untrusted data)."""
    from pathlib import Path

    path = Path.home() / ".aitest" / "worker-status.json"
    try:
        import json as _json

        doc = _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False,
                "reason": "no worker heartbeat yet (start AI Test Worker)"}
    doc["available"] = True
    return doc


@router.get("/project-summaries")
def tests_project_summaries(session: Session = Depends(get_session)) -> list[dict]:
    """Per-project aggregate counts for the global Tests table."""
    rows = session.execute(
        select(
            AitestTest.project_id,
            func.count(AitestTest.logical_id),
            func.sum(case((AitestTest.band == "UNASSESSED", 1), else_=0)),
            func.sum(case((AitestTest.band.in_(["INSTANT", "FAST"]), 1), else_=0)),
            func.sum(case((AitestTest.band.in_(["SLOW", "VERY_SLOW", "EXPENSIVE"]), 1), else_=0)),
            func.sum(case((AitestTest.last_outcome == "failed", 1), else_=0)),
            func.sum(case((AitestTest.lifecycle == "QUARANTINED", 1), else_=0)),
            func.max(AitestTest.last_seen_at),
        ).where(AitestTest.lifecycle != "RETIRED").group_by(AitestTest.project_id)
    ).all()
    out = []
    for pid, total, unassessed, fast, slow, failing, quarantined, last_seen in rows:
        proj = session.get(AitestProject, pid)
        out.append({
            "project_id": pid,
            "name": proj.name if proj else pid,
            "mc_project_id": proj.mc_project_id if proj else "",
            "policy": proj.policy if proj else "",
            "integration_state": proj.integration_state if proj else "",
            "last_status": proj.last_status if proj else "",
            "total": int(total or 0),
            "unassessed": int(unassessed or 0),
            "assessed": int((total or 0) - (unassessed or 0)),
            "fast": int(fast or 0),
            "slow": int(slow or 0),
            "failing": int(failing or 0),
            "quarantined": int(quarantined or 0),
            "last_seen_at": last_seen or "",
        })
    out.sort(key=lambda r: r["name"].lower())
    return out


@router.get("/quality/projects")
def quality_projects(session: Session = Depends(get_session)) -> list[dict]:
    """Latest quality assessment per project (AITEST-03)."""
    out = []
    for q in session.scalars(select(AitestQuality).order_by(AitestQuality.project_id)).all():
        proj = session.get(AitestProject, q.project_id)
        try:
            findings = json.loads(q.findings_json or "{}")
        except ValueError:
            findings = {}
        try:
            recommendations = json.loads(q.recommendations_json or "{}")
        except ValueError:
            recommendations = {}
        out.append({
            "project_id": q.project_id,
            "name": proj.name if proj else q.project_id,
            "mode": q.mode,
            "tests_evaluated": q.tests_evaluated,
            "findings": findings,
            "recommendations": recommendations,
            "verification_gaps": q.verification_gaps,
            "redundancy_candidates": q.redundancy_candidates,
            "coverage_percent": q.coverage_percent,
            "mutations_attempted": q.mutations_attempted,
            "mutations_killed": q.mutations_killed,
            "latest_at": q.latest_at,
            "cost_ms": q.cost_ms,
        })
    return out


@router.get("/projects/{project_id}/quality")
def project_quality(project_id: str,
                    session: Session = Depends(get_session)) -> dict:
    q = session.get(AitestQuality, project_id)
    if q is None:
        raise HTTPException(status_code=404, detail="no quality assessment yet")
    try:
        findings = json.loads(q.findings_json or "{}")
    except ValueError:
        findings = {}
    try:
        recommendations = json.loads(q.recommendations_json or "{}")
    except ValueError:
        recommendations = {}
    return {
        "project_id": project_id, "mode": q.mode, "snapshot": q.snapshot,
        "tests_evaluated": q.tests_evaluated, "findings": findings,
        "recommendations": recommendations,
        "verification_gaps": q.verification_gaps,
        "redundancy_candidates": q.redundancy_candidates,
        "coverage_percent": q.coverage_percent,
        "mutations_attempted": q.mutations_attempted,
        "mutations_killed": q.mutations_killed,
        "latest_at": q.latest_at, "cost_ms": q.cost_ms,
    }


def _upsert_quality(session: Session, project_id: str, payload: dict) -> None:
    row = session.get(AitestQuality, project_id)
    if row is None:
        row = AitestQuality(project_id=project_id)
        session.add(row)
    row.mode = payload.get("mode", row.mode or "")
    row.snapshot = payload.get("snapshot", row.snapshot or "")
    row.tests_evaluated = int(payload.get("tests_evaluated") or 0)
    row.findings_json = json.dumps(payload.get("findings") or {})
    row.recommendations_json = json.dumps(payload.get("recommendations") or {})
    row.verification_gaps = int(payload.get("verification_gaps") or 0)
    row.redundancy_candidates = int(payload.get("redundancy_candidates") or 0)
    if payload.get("coverage_percent") is not None:
        row.coverage_percent = float(payload["coverage_percent"])
    row.mutations_attempted = int(payload.get("mutations_attempted") or 0)
    row.mutations_killed = int(payload.get("mutations_killed") or 0)
    row.latest_at = now_iso()
    row.cost_ms = float(payload.get("cost_ms") or 0)


class SyncDocument(BaseModel):
    project: dict
    tests: list[dict] = []
    receipt: dict | None = None
    issues: list[dict] = []
    quality: dict | None = None


@router.post("/events")
def ingest_event(payload: AitestEventIngest,
                 session: Session = Depends(get_session)) -> dict:
    if payload.schema_version != "aitest.event.v1":
        raise HTTPException(status_code=400, detail="unsupported schema_version")
    if session.get(AitestEventSeen, payload.event_id) is not None:
        return {"ok": True, "duplicate": True}
    session.add(AitestEventSeen(event_id=payload.event_id, received_at=now_iso()))
    _apply_event(session, payload.event_type, payload.project_id, payload.payload,
                 payload.source_snapshot_id, payload.producer_version)
    session.commit()
    return {"ok": True, "duplicate": False}


@router.post("/sync")
def ingest_sync(doc: SyncDocument,
                session: Session = Depends(get_session)) -> dict:
    """Bulk sync from `aitest mission sync` (same idempotency semantics)."""
    p = doc.project
    # Identity reconciliation may adopt an existing row; every child record
    # must use the effective id, never the inbound one.
    pid = _upsert_project(session, p.get("project_id", ""), p)
    for t in doc.tests:
        _upsert_test(session, pid, t)
    if doc.receipt:
        _upsert_receipt(session, pid, doc.receipt)
    for issue in doc.issues:
        _upsert_issue(session, pid, issue)
    if doc.quality:
        _upsert_quality(session, pid, doc.quality)
    session.commit()
    return {"ok": True, "tests": len(doc.tests), "issues": len(doc.issues)}


def _upsert_project(session: Session, project_id: str, p: dict) -> str:
    root = (p.get("root") or "").rstrip("\\/").lower()
    # Identity reconciliation: the same checkout must never appear twice.
    # If another row already owns this root, adopt its id and merge.
    if root:
        for other in session.scalars(select(AitestProject)).all():
            if other.project_id != project_id and (other.root or "").rstrip("\\/").lower() == root:
                existing_ids = {
                    row[0] for row in session.execute(
                        select(AitestTest.logical_id).where(
                            AitestTest.project_id == other.project_id)).all()
                }
                for t in session.scalars(
                        select(AitestTest).where(AitestTest.project_id == project_id)).all():
                    if t.logical_id in existing_ids:
                        session.delete(t)
                    else:
                        t.project_id = other.project_id
                dup = session.get(AitestProject, project_id)
                if dup is not None:
                    session.delete(dup)
                    session.flush()
                project_id = other.project_id
                break
    row = session.get(AitestProject, project_id)
    now = now_iso()
    if row is None:
        session.add(AitestProject(
            project_id=project_id, name=p.get("name", ""), root=p.get("root", ""),
            remote_url=p.get("remote_url", ""), mc_project_id=p.get("mc_project_id", ""),
            integration_state=p.get("integration_state", "observation"),
            policy=p.get("policy", "observe"), aitest_version=p.get("aitest_version", ""),
            last_receipt_id=p.get("last_receipt_id", ""), last_status=p.get("last_status", ""),
            last_seen_at=now, created_at=now, updated_at=now))
        session.flush()
    else:
        # A second checkout of the same repository must not rename or block
        # the primary registered project; it is recorded as a blocked
        # checkout on its own sync only when the names match.
        same_project = (row.name or "").strip().lower() == (p.get("name") or "").strip().lower()
        for k in ("name", "root", "remote_url", "mc_project_id", "integration_state",
                  "policy", "aitest_version", "last_receipt_id", "last_status"):
            if p.get(k) in (None, ""):
                continue
            if not same_project and k in ("name", "integration_state", "policy"):
                continue
            setattr(row, k, p[k])
        row.last_seen_at = now
        row.updated_at = now
    return project_id


def _upsert_test(session: Session, project_id: str, t: dict) -> None:
    row = session.get(AitestTest, {"project_id": project_id, "logical_id": t.get("logical_id", "")})
    if row is None:
        session.add(AitestTest(
            project_id=project_id, logical_id=t.get("logical_id", ""),
            relpath=t.get("relpath", ""), class_name=t.get("class_name", ""),
            func_name=t.get("func_name", ""), duration_ms=t.get("duration_ms", 0),
            band=t.get("band", "UNASSESSED"), lifecycle=t.get("lifecycle", "DISCOVERED"),
            last_outcome=t.get("last_outcome", ""), last_seen_at=t.get("last_seen_at", "")))
    else:
        for k in ("relpath", "class_name", "func_name", "duration_ms", "band",
                  "lifecycle", "last_outcome", "last_seen_at"):
            if t.get(k) not in (None, ""):
                setattr(row, k, t[k])


def _upsert_receipt(session: Session, project_id: str, r: dict) -> None:
    if session.get(AitestReceipt, r.get("execution_id", "")) is not None:
        return
    session.add(AitestReceipt(
        execution_id=r.get("execution_id", ""), project_id=project_id,
        snapshot_id=r.get("snapshot_id", ""), status=r.get("status", "PENDING"),
        discovered=r.get("discovered", 0), executed=r.get("executed", 0),
        passed=r.get("passed", 0), failed=r.get("failed", 0), skipped=r.get("skipped", 0),
        quarantined=r.get("quarantined", 0), deferred=r.get("deferred", 0),
        timed_out=r.get("timed_out", 0), unobserved=r.get("unobserved", 0),
        duration_ms=r.get("duration_ms", 0), receipt_json=json.dumps(r),
        created_at=utcnow().isoformat()))
    proj = session.get(AitestProject, project_id)
    if proj is not None:
        proj.last_receipt_id = r.get("execution_id", "")
        proj.last_status = r.get("status", "")


def _upsert_issue(session: Session, project_id: str, issue: dict) -> None:
    existing = session.scalars(
        select(AitestIssue).where(
            AitestIssue.project_id == project_id,
            AitestIssue.test_logical_id == issue.get("test_logical_id", ""),
            AitestIssue.kind == issue.get("kind", "UNKNOWN"),
            AitestIssue.status == "open")).first()
    now = now_iso()
    if existing is None:
        session.add(AitestIssue(
            project_id=project_id, test_logical_id=issue.get("test_logical_id", ""),
            kind=issue.get("kind", "UNKNOWN"), title=issue.get("title", ""),
            detail_json=json.dumps(issue.get("detail", {})), status="open",
            created_at=now, updated_at=now))
    else:
        existing.title = issue.get("title", existing.title)
        existing.detail_json = json.dumps(issue.get("detail", {}))
        existing.updated_at = now


def _apply_event(session: Session, event_type: str, project_id: str,
                 payload: dict, snapshot: str, producer: str) -> None:
    if event_type == "project.registered":
        _upsert_project(session, project_id, payload)
    elif event_type == "execution.receipt":
        _upsert_receipt(session, project_id, payload)
    elif event_type in ("test.quarantined", "test.failed", "test.recurrence"):
        _upsert_issue(session, project_id, {
            "test_logical_id": payload.get("logical_id", ""),
            "kind": payload.get("kind", event_type),
            "title": payload.get("title", event_type),
            "detail": payload,
        })
