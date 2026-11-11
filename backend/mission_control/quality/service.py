"""Manuscript-quality evaluation history (MC-QUALITY-02, Stage F/H).

Append-only observation store. Scores are never invented here: every record
is a persisted observation with model and rubric provenance. Staleness and
compatibility are derived at read time, never by overwriting history.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import Project, QualityCampaign, QualityEvaluation, QualityReview
from mission_control.schemas import (
    QualityCampaignCreate,
    QualityCampaignRead,
    QualityChapterDiscovery,
    QualityChapterSummary,
    QualityDimensionRead,
    QualityEvaluationCreate,
    QualityEvaluationRead,
    QualityReviewCreate,
    QualityReviewRead,
    QualityWorkspaceRead,
)

DIMENSIONS = ("clarity", "argument", "precision", "economy", "voice", "structure")
SCORED_STATES = ("CURRENT", "PARTIAL", "STALE")
UNSCORABLE_STATES = ("NOT_RUN", "RUNNING", "BLOCKED", "ERROR", "CANCELLED")
ALL_STATES = SCORED_STATES + UNSCORABLE_STATES
# WRITER-QUALITY-02: findings observations. Writer-commanded strategies
# record validated portable findings instead of 1-5 rubric scores: no scores
# are invented, so dimensions stay empty and overall stays None on a scored
# status. The guard below only opens for records that carry Writer execution
# provenance (transport "writer-cli") with item-wise validated findings.
WRITER_STRATEGIES = ("deterministic", "direct", "bounded_judge")
# WRITER-QUALITY-01: peer evaluation strategies. deterministic dispatches no
# model; direct is one bounded review; bounded_judge adds typed judgment.
STRATEGIES = ("deterministic", "direct", "bounded_judge")


def _check_strategy(strategy: str | None) -> str:
    value = strategy or "direct"
    if value not in STRATEGIES:
        raise ValidationProblem(
            f"strategy must be one of {', '.join(STRATEGIES)}; got {value!r}"
        )
    return value


def _check_record(status: str, dimensions: dict[str, Any], overall: float | None) -> None:
    if status not in ALL_STATES:
        raise ValidationProblem(
            f"status must be one of {', '.join(ALL_STATES)}; got {status!r}"
        )
    if status in UNSCORABLE_STATES:
        if dimensions:
            raise ValidationProblem(
                f"status {status} must not carry dimension scores"
            )
        if overall is not None:
            raise ValidationProblem(
                f"status {status} must not carry an overall; unknown is not zero"
            )
        return
    _check_dimensions(dimensions, overall)


def _check_writer_findings(
    strategy: str | None, execution: dict[str, Any], findings: list[Any]
) -> bool:
    """True when this record is a Writer findings observation.

    Scored status with empty dimensions and no overall is accepted only for
    Writer-commanded strategies carrying Writer execution provenance and
    item-wise valid findings (family + claim each). Anything else keeps the
    six-dimension rule.
    """
    if (strategy or "") not in WRITER_STRATEGIES:
        return False
    if not isinstance(execution, dict) or execution.get("transport") != "writer-cli":
        return False
    for item in findings or []:
        if not isinstance(item, dict) or not item.get("family") or not item.get("claim"):
            raise ValidationProblem(
                "writer findings observations require family + claim per finding"
            )
    return True


def _check_record_full(
    status: str,
    dimensions: dict[str, Any],
    overall: float | None,
    strategy: str | None,
    execution: dict[str, Any],
    findings: list[Any],
) -> None:
    if (
        status in SCORED_STATES
        and not dimensions
        and overall is None
        and _check_writer_findings(strategy, execution, findings)
    ):
        return
    _check_record(status, dimensions, overall)


def _check_dimensions(dimensions: dict[str, Any], overall: float | None) -> None:
    if set(dimensions) != set(DIMENSIONS):
        raise ValidationProblem("dimensions must contain exactly the six rubric dimensions")
    scores = []
    for name in DIMENSIONS:
        entry = dimensions[name]
        score = entry.get("score") if isinstance(entry, dict) else getattr(entry, "score", None)
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
            raise ValidationProblem(f"score for {name!r} must be an integer 1-5")
        scores.append(score)
    expected = round(sum(scores) / len(scores), 2)
    if overall != expected:
        raise ValidationProblem(
            f"overall {overall} != mean of dimensions {expected}; hand-set overalls are refused"
        )


def record_evaluation(session: Session, payload: QualityEvaluationCreate) -> QualityEvaluation:
    if payload.project_id and session.get(Project, payload.project_id) is None:
        raise ValidationProblem("Project does not exist")
    dims = {
        name: (entry.model_dump() if hasattr(entry, "model_dump") else dict(entry))
        for name, entry in payload.dimensions.items()
    }
    _check_record_full(
        payload.status, dims, payload.overall, payload.strategy,
        dict(payload.execution or {}), list(payload.findings or []),
    )
    if payload.previous_evaluation_id and session.get(
        QualityEvaluation, payload.previous_evaluation_id
    ) is None:
        raise ValidationProblem("Previous evaluation does not exist")
    execution = dict(payload.execution or {})
    # Model provenance lives in execution metadata; promote it to the
    # queryable columns when the caller did not set them explicitly.
    # Explicit top-level values always win.
    requested_model = payload.requested_model or execution.get("requested_model")
    actual_model = payload.actual_model or execution.get("actual_model")
    strategy = _check_strategy(payload.strategy or execution.get("strategy"))
    record = QualityEvaluation(
        id=f"mqeval:{uuid.uuid4().hex[:12]}",
        project_id=payload.project_id,
        book_id=payload.book_id,
        chapter_id=payload.chapter_id,
        source_path=payload.source_path,
        chapter_revision=payload.chapter_revision,
        rubric_id=payload.rubric_id,
        rubric_version=payload.rubric_version,
        prompt_version=payload.prompt_version,
        requested_model=requested_model,
        actual_model=actual_model,
        strategy=strategy,
        status=payload.status,
        overall=payload.overall,
        aggregation_method=payload.aggregation_method,
        dimensions=dims,
        findings=list(payload.findings),
        uncertainty=payload.uncertainty,
        limitations=list(payload.limitations),
        execution=dict(payload.execution),
        previous_evaluation_id=payload.previous_evaluation_id,
        supersedes=payload.supersedes,
        workbench_url=payload.workbench_url,
        campaign_id=payload.campaign_id,
        section_id=payload.section_id,
        section_title=payload.section_title,
        char_span=list(payload.char_span or []),
        section_sha=payload.section_sha,
    )
    session.add(record)
    session.flush()
    return record


def _workbench_link(base: str | None, chapter_id: str) -> str | None:
    if not base:
        return None
    from urllib.parse import quote

    return f"{base.rstrip('/')}/#chapter={quote(chapter_id)}"


def to_read(record: QualityEvaluation, *, derived_state: str = "") -> QualityEvaluationRead:
    dims = {
        name: QualityDimensionRead(**entry)
        for name, entry in (record.dimensions or {}).items()
    }
    return QualityEvaluationRead(
        id=record.id,
        project_id=record.project_id,
        book_id=record.book_id or "",
        chapter_id=record.chapter_id,
        source_path=record.source_path or "",
        chapter_revision=record.chapter_revision,
        rubric_id=record.rubric_id,
        rubric_version=record.rubric_version,
        prompt_version=record.prompt_version,
        requested_model=record.requested_model,
        actual_model=record.actual_model,
        strategy=record.strategy or "direct",
        status=record.status,
        derived_state=derived_state or record.status,
        overall=record.overall,
        aggregation_method=record.aggregation_method,
        dimensions=dims,
        findings=list(record.findings or []),
        uncertainty=record.uncertainty or "",
        limitations=list(record.limitations or []),
        execution=dict(record.execution or {}),
        previous_evaluation_id=record.previous_evaluation_id,
        supersedes=record.supersedes,
        workbench_url=record.workbench_url,
        workbench_link=_workbench_link(record.workbench_url, record.chapter_id),
        campaign_id=record.campaign_id,
        section_id=record.section_id,
        section_title=record.section_title,
        char_span=list(record.char_span or []),
        section_sha=record.section_sha,
        created_at=record.created_at,
    )


def list_evaluations(
    session: Session,
    *,
    project_id: str | None = None,
    chapter_id: str | None = None,
    limit: int = 200,
) -> list[QualityEvaluation]:
    stmt: Select = select(QualityEvaluation).order_by(desc(QualityEvaluation.created_at))
    if project_id:
        stmt = stmt.where(QualityEvaluation.project_id == project_id)
    if chapter_id:
        stmt = stmt.where(QualityEvaluation.chapter_id == chapter_id)
    return list(session.scalars(stmt.limit(limit)).all())


def get_evaluation(session: Session, evaluation_id: str) -> QualityEvaluation:
    record = session.get(QualityEvaluation, evaluation_id)
    if record is None:
        raise NotFound("Evaluation does not exist")
    return record


REVIEW_DECISIONS = ("ACCEPT", "REJECT", "DEFER", "INVESTIGATE")


def record_review(session: Session, payload: QualityReviewCreate) -> QualityReview:
    if payload.decision not in REVIEW_DECISIONS:
        raise ValidationProblem(
            f"decision must be one of {', '.join(REVIEW_DECISIONS)}; got {payload.decision!r}"
        )
    evaluation = session.get(QualityEvaluation, payload.evaluation_id)
    if evaluation is None:
        raise NotFound("Evaluation does not exist")
    record = QualityReview(
        id=f"mqrev:{uuid.uuid4().hex[:12]}",
        evaluation_id=payload.evaluation_id,
        finding_id=payload.finding_id,
        decision=payload.decision,
        reason=payload.reason or "",
        reviewer=payload.reviewer or "",
        source_digest=evaluation.chapter_revision or "",
    )
    session.add(record)
    session.flush()
    return record


def list_reviews(session: Session, evaluation_id: str) -> list[QualityReview]:
    get_evaluation(session, evaluation_id)
    stmt = select(QualityReview).where(
        QualityReview.evaluation_id == evaluation_id
    ).order_by(QualityReview.created_at)
    return list(session.scalars(stmt).all())


def to_review_read(record: QualityReview, current_digest: str = "") -> QualityReviewRead:
    return QualityReviewRead(
        id=record.id,
        evaluation_id=record.evaluation_id,
        finding_id=record.finding_id,
        decision=record.decision,
        reason=record.reason or "",
        reviewer=record.reviewer or "",
        source_digest=record.source_digest or "",
        source_status=(
            "CURRENT"
            if current_digest and record.source_digest == current_digest
            else "STALE"
            if current_digest
            else "CURRENT"
        ),
        created_at=record.created_at,
    )


def workspace(session: Session, project_id: str) -> QualityWorkspaceRead:
    records = list_evaluations(session, project_id=project_id, limit=1000)
    by_chapter: dict[str, list[QualityEvaluation]] = {}
    for record in records:
        by_chapter.setdefault(record.chapter_id, []).append(record)
    chapters: list[QualityChapterSummary] = []
    current_count = 0
    for chapter_id in sorted(by_chapter):
        rows = sorted(by_chapter[chapter_id], key=lambda r: r.created_at)
        whole = [r for r in rows if not r.section_id]
        section_rows = [r for r in rows if r.section_id]
        scored = [r for r in whole if r.status in ("CURRENT", "PARTIAL", "STALE") and r.overall is not None]
        terminals = [r for r in whole if r not in scored]
        newest_scored = scored[-1] if scored else None
        reads: list[QualityEvaluationRead] = []
        current: QualityEvaluationRead | None = None
        for row in whole:
            if row in terminals:
                reads.append(to_read(row, derived_state=row.status.lower()))
                continue
            if row is newest_scored and row.status == "CURRENT":
                state = "current"
            elif newest_scored is not None and row.chapter_revision != newest_scored.chapter_revision:
                state = "stale"
            elif row is not newest_scored:
                state = "historical"
            else:
                state = row.status.lower()
            read = to_read(row, derived_state=state)
            reads.append(read)
            if state == "current":
                current = read
        if current is not None:
            current_count += 1
        chapters.append(
            QualityChapterSummary(
                chapter_id=chapter_id,
                evaluations=reads,
                sections=[to_read(r) for r in section_rows],
                current=current,
            )
        )
    return QualityWorkspaceRead(
        project_id=project_id,
        chapters_total=len(chapters),
        chapters_evaluated=len(chapters),
        chapters_current=current_count,
        chapters=chapters,
        limitations=[
            f"{current_count} of {len(chapters)} chapters have a current evaluation; coverage is explicit, not extrapolated.",
            "Quality, publication hygiene and technical evidence are separate measurements.",
        ],
    )


def compare(session: Session, first_id: str, second_id: str) -> dict[str, Any]:
    first = to_read(get_evaluation(session, first_id))
    second = to_read(get_evaluation(session, second_id))
    deltas = {
        name: second.dimensions[name].score - first.dimensions[name].score
        for name in DIMENSIONS
        if name in first.dimensions and name in second.dimensions
    }
    abs_diffs = [abs(v) for v in deltas.values()]
    same_revision = first.chapter_revision == second.chapter_revision
    same_model = (first.actual_model or "") == (second.actual_model or "")
    same_rubric = (
        first.rubric_id == second.rubric_id
        and first.rubric_version == second.rubric_version
    )
    if first.overall is None or second.overall is None:
        overall_range = None
    else:
        overall_range = round(abs(second.overall - first.overall), 2)
    if same_revision and same_model and same_rubric:
        basis = "same-revision same-model repeat"
    elif same_revision and same_rubric:
        basis = "same-revision cross-model comparison (not within-model repeatability)"
    elif same_rubric:
        basis = "cross-revision comparison (not a repeatability comparison)"
    else:
        basis = "incompatible basis (rubric differs); do not compare numerically"
    return {
        "first_id": first.id,
        "second_id": second.id,
        "chapter_id": first.chapter_id,
        "per_dimension_difference": deltas,
        "mean_absolute_difference": round(sum(abs_diffs) / len(abs_diffs), 2) if abs_diffs else 0.0,
        "max_variation": max(abs_diffs) if abs_diffs else None,
        "overall_range": overall_range,
        "same_revision": same_revision,
        "same_model": same_model,
        "same_rubric": same_rubric,
        "compatible_basis": basis,
    }


# ---------------------------------------------------------- campaigns (03A)

CAMPAIGN_MODES = ("missing", "outdated", "selected", "full")
ACTIVE_CAMPAIGN_STATES = ("pending", "running", "cancelling")


def _sha_file(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def discover_book_chapters(book_root: str) -> list[dict[str, Any]]:
    """Numbered chapters under a book content dir. Read-only; raises ValidationProblem."""
    import os
    import re

    if not book_root or not os.path.isdir(book_root):
        raise ValidationProblem("Book root is not available")
    try:
        files = sorted(
            (p for p in os.listdir(book_root) if re.fullmatch(r"\d{2}-chapter\.md", p or "")),
        )
    except OSError as exc:
        raise ValidationProblem(f"Book directory could not be read: {exc}") from exc
    chapters = []
    for name in files:
        full = os.path.join(book_root, name)
        try:
            with open(full, encoding="utf-8") as handle:
                head = handle.read(4000)
        except OSError:
            continue
        title_match = re.search(r'^title\s*=\s*"(.*?)"', head, re.MULTILINE)
        chapters.append(
            {
                "chapter_id": name,
                "title": title_match.group(1) if title_match else name,
                "source_path": full,
                "revision": _sha_file(full),
            }
        )
    return chapters


def resolve_book_root(session: Session, project_id: str) -> str:
    """Canonical book content dir from the Book record's manuscript paths."""
    import os

    from mission_control.models import Book

    book = session.scalars(select(Book).where(Book.project_id == project_id)).first()
    candidates: list[str] = []
    if book and book.manuscript_paths:
        for root in book.manuscript_paths:
            candidates.append(str(root))
            for name in ("content",):
                nested = os.path.join(str(root), name)
                if os.path.isdir(nested):
                    for entry in sorted(os.listdir(nested)):
                        if entry == "books":
                            sub = os.path.join(nested, entry)
                            try:
                                for book_dir in sorted(os.listdir(sub)):
                                    candidate = os.path.join(sub, book_dir)
                                    if os.path.isdir(candidate):
                                        candidates.append(candidate)
                            except OSError:
                                pass
    for candidate in candidates:
        try:
            if any(
                f.endswith("-chapter.md") for f in os.listdir(candidate)
            ):
                return candidate
        except OSError:
            continue
    raise ValidationProblem("No book content directory with chapters was found")


def eligibility(
    session: Session,
    project_id: str,
    *,
    model: str | None,
    rubric_id: str = "manuscript-prose-v1",
    rubric_version: int = 1,
    prompt_version: str = "1",
) -> list[QualityChapterDiscovery]:
    from mission_control.schemas import QualityChapterDiscovery as Discovery

    book_root = resolve_book_root(session, project_id)
    discovered = discover_book_chapters(book_root)
    records = list_evaluations(session, project_id=project_id, limit=10000)
    latest: dict[str, QualityEvaluation] = {}
    for record in sorted(records, key=lambda r: r.created_at):
        if not record.section_id and record.status in ("CURRENT", "PARTIAL", "STALE"):
            latest[record.chapter_id] = record
    rows = []
    for chapter in discovered:
        current = latest.get(chapter["chapter_id"])
        if current is None:
            state = "missing"
            compatible = False
        elif current.chapter_revision != chapter["revision"]:
            state = "stale"
            compatible = False
        elif (
            current.rubric_id != rubric_id
            or current.rubric_version != rubric_version
            or (current.execution or {}).get("prompt_version", current.prompt_version) != prompt_version
        ):
            state = "other-rubric"
            compatible = False
        elif model is not None and (current.actual_model or "") != model:
            state = "other-model"
            compatible = False
        else:
            state = "current"
            compatible = True
        rows.append(
            Discovery(
                chapter_id=chapter["chapter_id"],
                title=chapter["title"],
                source_path=chapter["source_path"],
                revision=chapter["revision"],
                has_current=state == "current",
                current_model=current.actual_model if current else None,
                current_id=current.id if current else None,
                compatible=compatible,
                eligibility=state,
            )
        )
    return rows


def _campaign_read(record: QualityCampaign) -> QualityCampaignRead:
    from mission_control.schemas import QualityCampaignRead as Read

    return Read(
        id=record.id,
        project_id=record.project_id,
        book_id=record.book_id or "",
        book_root=record.book_root or "",
        mode=record.mode,
        chapter_selection=list(record.chapter_selection or []),
        fingerprints=dict(record.fingerprints or {}),
        rubric_id=record.rubric_id,
        rubric_version=record.rubric_version,
        prompt_version=record.prompt_version,
        model=record.model,
        strategy=record.strategy or "direct",
        status=record.status,
        total=record.total,
        completed=record.completed,
        skipped=record.skipped,
        failed=record.failed,
        remaining=record.remaining,
        usage=dict(record.usage or {}),
        costs_unknown=bool(record.costs_unknown),
        current_chapter=record.current_chapter,
        error=record.error,
        heartbeat_at=record.heartbeat_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )


def create_campaign(session: Session, payload: QualityCampaignCreate) -> QualityCampaign:
    if payload.project_id and session.get(Project, payload.project_id) is None:
        raise ValidationProblem("Project does not exist")
    if payload.mode not in CAMPAIGN_MODES:
        raise ValidationProblem(f"mode must be one of {', '.join(CAMPAIGN_MODES)}")
    strategy = _check_strategy(payload.strategy)
    active = session.scalars(
        select(QualityCampaign).where(
            QualityCampaign.project_id == payload.project_id,
            QualityCampaign.status.in_(ACTIVE_CAMPAIGN_STATES),
        )
    ).first()
    if active is not None:
        raise ValidationProblem(
            f"campaign {active.id} is already {active.status}; stop or resume it instead"
        )
    book_root = payload.book_root or (
        resolve_book_root(session, payload.project_id) if payload.project_id else ""
    )
    rows = eligibility(
        session, payload.project_id or "",
        model=payload.model,
    ) if payload.project_id else [
        r for r in []  # no project: selection must be explicit
    ]
    by_id = {r.chapter_id: r for r in rows}
    if payload.mode == "missing":
        # Anything without a comparable current result: missing, stale,
        # another model, or another rubric. Comparable currents are preserved,
        # never silently overwritten.
        selection = [r.chapter_id for r in rows if not (r.eligibility == "current" and r.compatible)]
    elif payload.mode == "outdated":
        selection = [r.chapter_id for r in rows if r.eligibility in ("stale",)]
    elif payload.mode == "full":
        selection = [r.chapter_id for r in rows]
    else:  # selected
        unknown = [c for c in payload.chapters if c not in by_id]
        if unknown:
            raise ValidationProblem(f"not chapters of this book: {', '.join(unknown)}")
        selection = list(payload.chapters)
    from mission_control.persistence.db import now_iso

    record = QualityCampaign(
        id=f"mqcamp:{uuid.uuid4().hex[:12]}",
        project_id=payload.project_id,
        book_id=payload.book_id,
        book_root=book_root,
        mode=payload.mode,
        chapter_selection=selection,
        fingerprints={c: by_id[c].revision for c in selection},
        rubric_id="manuscript-prose-v1",
        rubric_version=1,
        prompt_version="1",
        model=payload.model,
        strategy=strategy,
        status="pending",
        total=len(selection),
        completed=0,
        skipped=0,
        failed=0,
        remaining=len(selection),
        usage={},
        costs_unknown=True,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    session.add(record)
    session.flush()
    return record


def get_campaign(session: Session, campaign_id: str) -> QualityCampaign:
    record = session.get(QualityCampaign, campaign_id)
    if record is None:
        raise NotFound("Campaign does not exist")
    return record


def list_campaigns(session: Session, project_id: str | None = None) -> list[QualityCampaign]:
    stmt = select(QualityCampaign).order_by(desc(QualityCampaign.created_at))
    if project_id:
        stmt = stmt.where(QualityCampaign.project_id == project_id)
    return list(session.scalars(stmt.limit(50)).all())


def stop_campaign(session: Session, campaign_id: str) -> QualityCampaign:
    from mission_control.persistence.db import now_iso

    record = get_campaign(session, campaign_id)
    if record.status == "running":
        record.status = "cancelling"
    elif record.status == "pending":
        record.status = "partial"
        record.completed_at = now_iso()
        record.error = "stopped before start"
    else:
        raise ValidationProblem(f"campaign is {record.status}; nothing to stop")
    record.updated_at = now_iso()
    session.flush()
    return record


def _campaign_done(session: Session, record: QualityCampaign, status: str, error: str | None = None) -> None:
    from mission_control.persistence.db import now_iso

    record.status = status
    record.error = error
    record.current_chapter = None
    record.remaining = 0
    record.updated_at = now_iso()
    record.completed_at = now_iso()
    session.flush()


def run_campaign(session_factory, campaign_id: str, evaluate_fn) -> QualityCampaign:
    """Execute one campaign sequentially. evaluate_fn(chapter) returns an
    evaluation payload dict (or raises). Progress persists per chapter;
    a failed chapter is recorded and skipped, never aborting the campaign.
    evaluate_fn returning {"status": "BLOCKED"/"ERROR", ...} counts as failed
    with reason, without inventing a score.
    """
    from mission_control.persistence.db import now_iso
    from mission_control.schemas import QualityEvaluationCreate

    with session_factory() as session:
        record = get_campaign(session, campaign_id)
        if record.status not in ("pending", "running"):
            raise ValidationProblem(f"campaign is {record.status}; resume it instead")
        record.status = "running"
        record.error = None
        record.updated_at = now_iso()
        record.heartbeat_at = now_iso()
        session.commit()
        selection = list(record.chapter_selection or [])
        done_chapters = {
            r.chapter_id
            for r in session.scalars(
                select(QualityEvaluation).where(
                    QualityEvaluation.campaign_id == record.id,
                    QualityEvaluation.status.in_(("CURRENT", "PARTIAL")),
                )
            ).all()
        }
        completed = sum(1 for c in selection if c in done_chapters)
        skipped = failed = 0
        failures: dict[str, str] = {}
        in_tokens = out_tokens = 0
        costs: list[float] = []
        usage_unknown = False
        try:
            for chapter_id in selection:
                with session_factory() as check:
                    fresh = get_campaign(check, record.id)
                    if fresh.status == "cancelling":
                        raise _CampaignStop()
                if chapter_id in done_chapters:
                    skipped += 1
                    continue
                with session_factory() as chapter_session:
                    campaign_row = get_campaign(chapter_session, record.id)
                    campaign_row.current_chapter = chapter_id
                    campaign_row.heartbeat_at = now_iso()
                    campaign_row.updated_at = now_iso()
                    chapter_session.commit()
                try:
                    outcome = evaluate_fn(chapter_id)
                except _CampaignStop:
                    raise
                except Exception as exc:  # noqa: BLE001 - per-chapter isolation
                    outcome = {"status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                with session_factory() as chapter_session:
                    campaign_row = get_campaign(chapter_session, record.id)
                    status = str(outcome.get("status", "ERROR"))
                    writer_observation = (
                        isinstance(outcome.get("execution"), dict)
                        and outcome["execution"].get("transport") == "writer-cli"
                        and status in ("CURRENT", "PARTIAL")
                    )
                    if (status in ("CURRENT", "PARTIAL") and outcome.get("overall") is not None) or writer_observation:
                        payload = QualityEvaluationCreate(
                            project_id=record.project_id,
                            book_id=record.book_id,
                            chapter_id=chapter_id,
                            source_path=str(outcome.get("source_path", "")),
                            chapter_revision=str(outcome.get("chapter_revision", "")),
                            rubric_id=str(outcome.get("rubric_id", record.rubric_id)),
                            rubric_version=int(outcome.get("rubric_version", record.rubric_version)),
                            prompt_version=str(outcome.get("prompt_version", record.prompt_version)),
                            requested_model=outcome.get("requested_model"),
                            actual_model=outcome.get("actual_model"),
                            # Campaign strategy is the record of what was
                            # requested; the baseline scorer path is
                            # direct-equivalent. Deterministic campaigns must
                            # supply an evaluate_fn that dispatches no model.
                            strategy=record.strategy or "direct",
                            status=status,
                            overall=outcome.get("overall"),
                            dimensions=dict(outcome.get("dimensions", {})),
                            findings=list(outcome.get("findings", [])),
                            uncertainty=str(outcome.get("uncertainty", "")),
                            limitations=list(outcome.get("limitations", [])),
                            execution=dict(outcome.get("execution", {})),
                        )
                        rec = record_evaluation(chapter_session, payload)
                        rec.campaign_id = record.id
                        chapter_session.flush()
                        completed += 1
                        execution = dict(outcome.get("execution", {}))
                        if isinstance(execution.get("input_tokens"), (int, float)):
                            in_tokens += int(execution["input_tokens"])
                        if isinstance(execution.get("output_tokens"), (int, float)):
                            out_tokens += int(execution["output_tokens"])
                        if isinstance(execution.get("cost_usd"), (int, float)):
                            costs.append(float(execution["cost_usd"]))
                        if execution.get("token_usage", "unknown") == "unknown" and execution.get("transport") != "writer-cli":
                            usage_unknown = True
                        if execution.get("transport") == "writer-cli":
                            # Writer usage records are ingested once, verbatim:
                            # one list entry per Worker dispatch. Cached input
                            # tokens are real billed usage at the cached rate.
                            for record_usage in execution.get("usage", []) or []:
                                if not isinstance(record_usage, dict):
                                    continue
                                detail = record_usage.get("usage") or {}
                                if isinstance(detail, dict):
                                    in_tokens += int(detail.get("input_tokens", 0) or 0)
                                    in_tokens += int(detail.get("cached_input_tokens", 0) or 0)
                                    out_tokens += int(detail.get("output_tokens", 0) or 0)
                                estimate = record_usage.get("catalog_estimate_usd")
                                if isinstance(estimate, (int, float)):
                                    costs.append(float(estimate))
                                else:
                                    usage_unknown = True
                    else:
                        failed += 1
                        reason = str(outcome.get("error", "evaluation failed"))
                        failures[chapter_id] = reason
                        campaign_row.error = f"{chapter_id}: {reason}"
                    campaign_row.completed = completed
                    campaign_row.skipped = skipped
                    campaign_row.failed = failed
                    campaign_row.remaining = max(
                        0, len(selection) - completed - skipped - failed
                    )
                    campaign_row.usage = {
                        "input_tokens": in_tokens,
                        "output_tokens": out_tokens,
                        "cost_usd": round(sum(costs), 4) if costs else 0.0,
                        "failures": failures,
                    }
                    campaign_row.costs_unknown = usage_unknown or not costs
                    campaign_row.heartbeat_at = now_iso()
                    campaign_row.updated_at = now_iso()
                    chapter_session.commit()
        except _CampaignStop:
            with session_factory() as session:
                record = get_campaign(session, campaign_id)
                record.status = "partial"
                record.error = "stopped after the current chapter"
                _finish_counts(session, record, completed, skipped, failed, selection)
                session.commit()
            return get_fresh(session_factory, campaign_id)
        except Exception as exc:  # noqa: BLE001 - crash keeps progress, marks interrupted
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
            _campaign_done(session, record, final, None if failed == 0 else f"{failed} chapter(s) failed; retry them with a selected rerun")
            session.commit()
        return get_fresh(session_factory, campaign_id)


class _CampaignStop(Exception):
    pass


def _finish_counts(session, record, completed, skipped, failed, selection) -> None:
    from mission_control.persistence.db import now_iso

    record.completed = completed
    record.skipped = skipped
    record.failed = failed
    record.remaining = max(0, len(selection) - completed - skipped - failed)
    record.updated_at = now_iso()
    session.flush()


def get_fresh(session_factory, campaign_id: str) -> QualityCampaign:
    with session_factory() as session:
        return get_campaign(session, campaign_id)


def resume_campaign(session: Session, campaign_id: str) -> QualityCampaign:
    from mission_control.persistence.db import now_iso

    record = get_campaign(session, campaign_id)
    if record.status not in ("partial", "interrupted", "failed", "pending"):
        raise ValidationProblem(f"campaign is {record.status}; nothing to resume")
    record.status = "pending"
    record.error = None
    record.updated_at = now_iso()
    session.flush()
    return record
