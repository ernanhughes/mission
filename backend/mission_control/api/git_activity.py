"""Unified project activity, Git history and AI review (MC-ACTIVITY-01).

Collection (git history) is factual evidence; review is an assessment of
that evidence. Opening activity endpoints never starts an AI model call.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.activity_git.service import GitActivityService
from mission_control.api.deps import get_session
from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import GitRepository, GitReview, GitReviewFeedback
from mission_control.persistence.db import now_iso
from mission_control.schemas import (
    GitCommitRead,
    GitDailyProjectRead,
    GitDailyProjectsRead,
    GitDailyPromptRequest,
    GitDailyReviewRequest,
    GitRepoRead,
    GitReviewCreate,
    GitReviewFeedbackCreate,
    GitReviewRead,
    GitRootCreate,
    GitRootRead,
    GitRootUpdate,
    GitSummaryRead,
    GitTimelineRead,
    OkResponse,
    ScanRead,
)
import uuid

router = APIRouter(prefix="/api/git-activity", tags=["git-activity"])


def _service(request: Request) -> GitActivityService:
    service = getattr(request.app.state, "git_activity", None)
    if service is None:
        raise NotFound("Git activity service is not available")
    return service


def _repo_read(row: GitRepository) -> GitRepoRead:
    return GitRepoRead(
        id=row.id, root_path=row.root_path, path=row.path, name=row.name,
        branch=row.branch, head_sha=row.head_sha, accessible=bool(row.accessible),
        is_bare=bool(row.is_bare), is_shallow=bool(row.is_shallow),
        last_indexed_at=row.last_indexed_at, backfill_complete=bool(row.backfill_complete),
        total_commits=row.total_commits, has_agents=bool(row.has_agents),
        has_description=bool(row.has_description), context_status=row.context_status,
        error=row.error,
    )


def _review_read(session: Session, row: GitReview) -> GitReviewRead:
    feedback = session.scalars(
        select(GitReviewFeedback).where(GitReviewFeedback.review_id == row.id).order_by(GitReviewFeedback.created_at)
    ).all()
    return GitReviewRead(
        id=row.id, repo_id=row.repo_id, review_type=row.review_type,
        commit_sha=row.commit_sha, base_sha=row.base_sha, target_sha=row.target_sha,
        commit_shas=list(row.commit_shas or []), reviewer_type=row.reviewer_type,
        requested_model=row.requested_model, observed_model=row.observed_model,
        model_route=row.model_route, profile=row.profile, status=row.status,
        verdict=row.verdict, findings=list(row.findings or []), summary=row.summary,
        tests=dict(row.tests or {}), architecture=dict(row.architecture or {}),
        limitations=list(row.limitations or []), prompt_hash=row.prompt_hash,
        diff_hash=row.diff_hash, context_fingerprint=row.context_fingerprint,
        evidence_coverage=dict(row.evidence_coverage or {}),
        usage_info=dict(row.usage_info or {}), error=row.error,
        created_at=row.created_at, completed_at=row.completed_at,
        feedback=[{"id": item.id, "rating": item.rating, "detail": item.detail, "created_at": item.created_at} for item in feedback],
    )


# ------------------------------------------------------------------ roots
@router.get("/roots", response_model=list[GitRootRead])
def list_roots(request: Request, session: Session = Depends(get_session)) -> list[GitRootRead]:
    return [GitRootRead(**row) for row in _service(request).list_roots(session)]


@router.post("/roots", response_model=GitRootRead, status_code=201)
def add_root(request: Request, payload: GitRootCreate, session: Session = Depends(get_session)) -> GitRootRead:
    return GitRootRead(**_service(request).add_root(
        session, path=payload.path, name=payload.name, category=payload.category, enabled=payload.enabled))


@router.patch("/roots", response_model=GitRootRead)
def update_root(request: Request, payload: GitRootUpdate, path: str,
                session: Session = Depends(get_session)) -> GitRootRead:
    return GitRootRead(**_service(request).update_root(
        session, path, name=payload.name, category=payload.category,
        enabled=payload.enabled, git_enabled=payload.git_enabled))


@router.delete("/roots", response_model=OkResponse)
def delete_root(request: Request, path: str, retain_history: bool = True,
                session: Session = Depends(get_session)) -> OkResponse:
    _service(request).remove_root(session, path, retain_history=retain_history)
    return OkResponse(detail="Activity root removed")


# ------------------------------------------------------------------- scan
@router.post("/scan", response_model=ScanRead, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(request: Request) -> ScanRead:
    return ScanRead(**await _service(request).start())


@router.get("/scan", response_model=ScanRead)
def scan_status(request: Request) -> ScanRead:
    return ScanRead(**_service(request).status)


@router.post("/scan/cancel", response_model=ScanRead)
async def cancel_scan(request: Request) -> ScanRead:
    return ScanRead(**await _service(request).cancel())


@router.get("/config", response_model=dict)
def get_config(request: Request, session: Session = Depends(get_session)) -> dict:
    return _service(request).get_config(session)


@router.patch("/config", response_model=dict)
def update_config(request: Request, payload: dict, session: Session = Depends(get_session)) -> dict:
    return _service(request).update_config(session, payload)


# ------------------------------------------------------------------ repos
@router.get("/repos", response_model=list[GitRepoRead])
def list_repos(request: Request, session: Session = Depends(get_session),
               root: str | None = None, search: str | None = None,
               context: str | None = None,
               limit: int = Query(default=200, ge=1, le=500),
               offset: int = Query(default=0, ge=0)) -> list[GitRepoRead]:
    query = select(GitRepository).order_by(GitRepository.name)
    if root:
        query = query.where(GitRepository.root_path == root)
    if search:
        needle = f"%{search}%"
        query = query.where((GitRepository.name.ilike(needle)) | (GitRepository.path.ilike(needle)))
    if context and context != "all":
        query = query.where(GitRepository.context_status == context)
    rows = session.scalars(query.limit(limit).offset(offset)).all()
    return [_repo_read(row) for row in rows]


@router.get("/repos/{repo_id}", response_model=GitRepoRead)
def get_repo(request: Request, repo_id: str, session: Session = Depends(get_session)) -> GitRepoRead:
    return _repo_read(_service(request).get_repo(session, repo_id))


# ---------------------------------------------------------------- timeline
@router.get("/timeline", response_model=GitTimelineRead)
def timeline(request: Request, session: Session = Depends(get_session),
             root: str | None = None, repo_id: str | None = None,
             category: str | None = None, author: str | None = None,
             branch: str | None = None, review_status: str | None = None,
             search: str | None = None,
             preset: str = Query(default="today"),
             date_from: int | None = None, date_to: int | None = None,
             limit: int = Query(default=100, ge=1, le=200),
             offset: int = Query(default=0, ge=0)) -> GitTimelineRead:
    service = _service(request)
    if preset not in {"today", "yesterday", "7d", "30d", "custom", "all"}:
        raise ValidationProblem("Unknown date preset")
    effective_preset = preset if preset != "custom" else "all"
    if preset == "custom" and date_from is None and date_to is None:
        raise ValidationProblem("Custom date range requires date_from or date_to")
    items, total, pending = service.timeline(
        session, root=root or None, repo_id=repo_id or None,
        category=category or None, author=author or None, branch=branch or None,
        review_status=review_status or None, search=search or None,
        date_from=date_from, date_to=date_to, preset=effective_preset,
        limit=limit, offset=offset)
    return GitTimelineRead(items=[GitCommitRead(**item) for item in items],
                           total=total, partial=bool(pending), limit=limit, offset=offset)


@router.get("/summary", response_model=GitSummaryRead)
def summary(request: Request, session: Session = Depends(get_session)) -> GitSummaryRead:
    return GitSummaryRead(**_service(request).summary(session))


# ----------------------------------------------------------------- commit
@router.get("/commits/{repo_id}/{sha}")
def commit_detail(request: Request, repo_id: str, sha: str,
                  session: Session = Depends(get_session)) -> dict:
    service = _service(request)
    repo, commit = service.get_commit(session, repo_id, sha)
    reviews = session.scalars(
        select(GitReview).where(GitReview.repo_id == repo_id).order_by(desc(GitReview.created_at)).limit(50)).all()
    relevant = [_review_read(session, review) for review in reviews
                if commit.sha in (review.commit_shas or ([review.commit_sha] if review.commit_sha else []))]
    return {
        "repo": _repo_read(repo).model_dump(),
        "commit": {
            "repo_id": commit.repo_id, "sha": commit.sha, "short_sha": commit.short_sha,
            "subject": commit.subject, "body": commit.body,
            "author_name": commit.author_name, "author_email": commit.author_email,
            "author_ts": commit.author_ts, "author_tz": commit.author_tz,
            "committer_ts": commit.committer_ts, "committer_tz": commit.committer_tz,
            "parents": commit.parents, "branches": commit.branches,
            "files_changed": commit.files_changed, "insertions": commit.insertions,
            "deletions": commit.deletions, "is_merge": bool(commit.is_merge),
            "is_root": bool(commit.is_root), "reachable": bool(commit.reachable),
        },
        "reviews": [review.model_dump() for review in relevant],
    }


@router.get("/commits/{repo_id}/{sha}/diff")
def commit_diff(request: Request, repo_id: str, sha: str,
                parent: str | None = None, max_bytes: int | None = None,
                session: Session = Depends(get_session)) -> dict:
    return _service(request).commit_diff(session, repo_id, sha, parent=parent, max_bytes=max_bytes)


@router.get("/commits/{repo_id}/{sha}/prompt")
def commit_prompt(request: Request, repo_id: str, sha: str,
                  parent: str | None = None, profile: str = "code",
                  max_bytes: int | None = None,
                  session: Session = Depends(get_session)) -> dict:
    """Copy-review-prompt package. Never starts a model call."""
    package = _service(request).build_prompt(session, repo_id, sha, parent=parent, profile=profile, max_bytes=max_bytes)
    diff = package.pop("diff")
    return {**package, "files": diff["files"], "diff_mode": diff["mode"], "diff_bytes": diff["total_bytes"]}


@router.post("/range/prompt")
def range_prompt(request: Request, payload: dict, session: Session = Depends(get_session)) -> dict:
    service = _service(request)
    repo_id = str(payload.get("repo_id") or "")
    if not repo_id:
        raise ValidationProblem("repo_id is required")
    return service.build_range_prompt(
        session, repo_id, shas=payload.get("shas"), base_sha=payload.get("base_sha"),
        target_sha=payload.get("target_sha"), profile=str(payload.get("profile") or "code"))


# ----------------------------------------------------------------- reviews
@router.get("/models")
async def review_models(request: Request, session: Session = Depends(get_session)) -> dict:
    from mission_control.research.inference import discover_local_models
    return await discover_local_models(session)


@router.post("/reviews", response_model=GitReviewRead, status_code=201)
async def request_review(request: Request, payload: GitReviewCreate,
                         session: Session = Depends(get_session)) -> GitReviewRead:
    service = _service(request)
    review = service.request_review(
        session, repo_id=payload.repo_id, sha=payload.sha,
        commit_shas=payload.commit_shas, base_sha=payload.base_sha,
        target_sha=payload.target_sha, model=payload.model, profile=payload.profile,
        daily_date=payload.daily_date, daily_timezone=payload.daily_timezone,
        daily_mode=payload.daily_mode)
    review_id = review.id
    read = _review_read(session, review).model_dump()
    # Commit before scheduling background execution: the worker opens its own
    # session and must see the queued row (avoids a commit-visibility race).
    session.commit()
    asyncio.create_task(service.execute_review(review_id))
    return GitReviewRead(**read)


@router.get("/reviews", response_model=list[GitReviewRead])
def list_reviews(request: Request, session: Session = Depends(get_session),
                 repo_id: str | None = None, sha: str | None = None,
                 status_filter: str | None = Query(default=None, alias="status"),
                 limit: int = Query(default=50, ge=1, le=200)) -> list[GitReviewRead]:
    query = select(GitReview).order_by(desc(GitReview.created_at))
    if repo_id:
        query = query.where(GitReview.repo_id == repo_id)
    if status_filter:
        query = query.where(GitReview.status == status_filter)
    rows = session.scalars(query.limit(limit)).all()
    if sha:
        sha = sha.strip().lower()
        rows = [row for row in rows if sha in (row.commit_shas or ([row.commit_sha] if row.commit_sha else []))]
    return [_review_read(session, row) for row in rows]


@router.get("/reviews/{review_id}", response_model=GitReviewRead)
def get_review(request: Request, review_id: str, session: Session = Depends(get_session)) -> GitReviewRead:
    row = session.get(GitReview, review_id)
    if row is None:
        raise NotFound("Review not found")
    return _review_read(session, row)


@router.post("/reviews/{review_id}/feedback", response_model=GitReviewRead)
def review_feedback(request: Request, review_id: str, payload: GitReviewFeedbackCreate,
                    session: Session = Depends(get_session)) -> GitReviewRead:
    row = session.get(GitReview, review_id)
    if row is None:
        raise NotFound("Review not found")
    if payload.rating not in {"useful", "correct", "false_positive", "missed_issue", "accepted", "rejected", "needs_followup"}:
        raise ValidationProblem("Unknown feedback rating")
    session.add(GitReviewFeedback(id=f"fdb-{uuid.uuid4().hex[:16]}", review_id=review_id,
                                  rating=payload.rating, detail=payload.detail, created_at=now_iso()))
    session.flush()
    return _review_read(session, row)


# ------------------------------------------------------- daily project
@router.get("/daily/projects", response_model=GitDailyProjectsRead)
def daily_projects(request: Request, session: Session = Depends(get_session),
                   date: str = Query(...), timezone: str = Query(default="Europe/Dublin")) -> GitDailyProjectsRead:
    data = _service(request).daily_projects(session, day=date, tz_name=timezone)
    return GitDailyProjectsRead(
        date=data["date"], timezone=data["timezone"], start_ts=data["start_ts"], end_ts=data["end_ts"],
        total_commits=data["total_commits"], total_repos=data["total_repos"],
        projects=[GitDailyProjectRead(**item) for item in data["projects"]],
        partial=data["partial"], backfill_pending=data["backfill_pending"])


@router.post("/daily/prompt")
def daily_prompt(request: Request, payload: GitDailyPromptRequest,
                 session: Session = Depends(get_session)) -> dict:
    """Copy-prompt package for a whole project-day. Never starts a model call."""
    service = _service(request)
    package = service.build_daily_prompt(
        session, payload.repo_id, payload.date, payload.timezone,
        mode=payload.mode, profile=payload.profile)
    diff = {"files": [], "mode": "project-day"}
    return {**{k: v for k, v in package.items() if k != "diff"}, "files": diff["files"],
            "diff_mode": "project-day", "diff_bytes": package["size_chars"]}


@router.post("/daily/reviews", response_model=GitReviewRead, status_code=201)
async def request_daily_review(request: Request, payload: GitDailyReviewRequest,
                               session: Session = Depends(get_session)) -> GitReviewRead:
    service = _service(request)
    review = service.request_daily_review(
        session, repo_id=payload.repo_id, day=payload.date, tz_name=payload.timezone,
        mode=payload.mode, profile=payload.profile, model=payload.model)
    review_id = review.id
    read = _review_read(session, review).model_dump()
    session.commit()
    asyncio.create_task(service.execute_review(review_id))
    return GitReviewRead(**read)


@router.get("/daily/reviews", response_model=list[GitReviewRead])
def list_daily_reviews(request: Request, session: Session = Depends(get_session),
                       repo_id: str = Query(...), date: str = Query(...),
                       timezone: str = Query(default="Europe/Dublin"),
                       limit: int = Query(default=20, ge=1, le=100)) -> list[GitReviewRead]:
    query = select(GitReview).where(
        GitReview.repo_id == repo_id, GitReview.review_type == "daily").order_by(desc(GitReview.created_at))
    rows = session.scalars(query.limit(limit)).all()
    filtered = [row for row in rows
                if (row.evidence_coverage or {}).get("daily_date") == date
                and ((row.evidence_coverage or {}).get("timezone") or "Europe/Dublin") == (timezone or "Europe/Dublin")]
    return [_review_read(session, row) for row in filtered]


# ----------------------------------------------------------------- context
@router.get("/context/{repo_id}")
def context_inventory(request: Request, repo_id: str, session: Session = Depends(get_session)) -> dict:
    return _service(request).context_inventory(session, repo_id)


@router.post("/context/{repo_id}/propose")
def propose_context(request: Request, repo_id: str, payload: dict,
                    session: Session = Depends(get_session)) -> dict:
    kind = str(payload.get("kind") or "description")
    if kind not in {"description", "agents"}:
        raise ValidationProblem("kind must be description or agents")
    return _service(request).propose_context(session, repo_id, kind)


@router.post("/context/{repo_id}/apply")
def apply_context(request: Request, repo_id: str, payload: dict,
                  session: Session = Depends(get_session)) -> dict:
    kind = str(payload.get("kind") or "description")
    content = str(payload.get("content") or "")
    confirm = bool(payload.get("confirm"))
    if kind not in {"description", "agents"}:
        raise ValidationProblem("kind must be description or agents")
    if not content.strip():
        raise ValidationProblem("content must not be empty")
    return _service(request).apply_context(session, repo_id, kind, content, confirm=confirm)
