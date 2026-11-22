"""Blog-post listing, evaluation and reviews for website workspaces."""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.api.websites import _state, _websites_root
from mission_control.core.errors import CapabilityUnavailable, NotFound
from mission_control.schemas import (
    WebsitePostDetailRead,
    WebsitePostEvaluateRequest,
    WebsitePostEvaluationRead,
    WebsitePostListRead,
    WebsitePostReviewCreate,
    WebsitePostReviewRead,
    WebsitePostsSummaryRead,
)
from mission_control.websites import evaluate as _evaluate
from mission_control.websites import posts as _posts
from mission_control.websites.service import resolve_site as _resolve_site

router = APIRouter(prefix="/api/websites", tags=["website-posts"])


def _blog_dir(request: Request, site_id: str):
    root = _websites_root(request)
    site = _resolve_site(root, site_id)
    return _posts.resolve_blog_dir(root, site)


@router.get("/{site_id}/posts", response_model=WebsitePostListRead)
def get_posts(
    site_id: str,
    request: Request,
    session: Session = Depends(get_session),
    status: str = "all",
    evaluated: str = "all",
    search: str | None = None,
    sort: str = "date_desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WebsitePostListRead:
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    return WebsitePostListRead(**_posts.list_posts(
        session, website_id=site_id, blog_dir=blog_dir, status=status,
        evaluated=evaluated, search=search, sort=sort, limit=limit, offset=offset))


@router.get("/{site_id}/posts/summary", response_model=WebsitePostsSummaryRead)
def get_posts_summary(
    site_id: str, request: Request, session: Session = Depends(get_session)
) -> WebsitePostsSummaryRead:
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    return WebsitePostsSummaryRead(
        **_posts.posts_summary(session, website_id=site_id, blog_dir=blog_dir))


@router.get("/{site_id}/posts/{identity:path}", response_model=WebsitePostDetailRead)
def get_post(
    site_id: str, identity: str, request: Request,
    session: Session = Depends(get_session),
) -> WebsitePostDetailRead:
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    return WebsitePostDetailRead(
        **_posts.get_post_detail(session, website_id=site_id, blog_dir=blog_dir,
                                 identity=identity))


@router.post("/{site_id}/posts/{identity:path}/evaluate",
             response_model=WebsitePostEvaluationRead)
def evaluate_post(
    site_id: str, identity: str, payload: WebsitePostEvaluateRequest,
    request: Request, session: Session = Depends(get_session),
) -> WebsitePostEvaluationRead:
    """Run one manual editorial evaluation (synchronous; published only).

    No automatic or bulk evaluation: each call evaluates exactly one article.
    """
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    model = _evaluate.resolve_eval_model(payload.model)
    if model is None:
        raise CapabilityUnavailable(_evaluate.blocked_message())
    result = _posts.evaluate_article(
        session, website_id=site_id, blog_dir=blog_dir, identity=identity,
        run_evaluation=partial(_evaluate.run_pi_evaluation, model=model),
        model=model, force=bool(payload.force))
    session.flush()
    return WebsitePostEvaluationRead(**result)


@router.get("/{site_id}/evaluations/{evaluation_id}",
            response_model=WebsitePostEvaluationRead)
def get_evaluation(
    site_id: str, evaluation_id: str, request: Request,
    session: Session = Depends(get_session),
) -> WebsitePostEvaluationRead:
    from mission_control.models import WebsitePostEvaluation as _Model

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    row = session.get(_Model, evaluation_id)
    if row is None or row.website_id != site_id:
        raise NotFound("Evaluation not found.")
    try:
        _text, sha, _truncated = _posts.read_article_text(
            _posts.resolve_blog_dir(
                _websites_root(request),
                _resolve_site(_websites_root(request), site_id)),
            row.relpath)
    except Exception:
        sha = row.content_sha256
    return WebsitePostEvaluationRead(**_posts._evaluation_read(session, row, sha))


@router.get("/{site_id}/evaluations/{evaluation_id}/reviews",
            response_model=list[WebsitePostReviewRead])
def get_reviews(
    site_id: str, evaluation_id: str, request: Request,
    session: Session = Depends(get_session),
) -> list[WebsitePostReviewRead]:
    from mission_control.models import WebsitePostEvaluation as _Model

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    row = session.get(_Model, evaluation_id)
    if row is None or row.website_id != site_id:
        raise NotFound("Evaluation not found.")
    return [WebsitePostReviewRead(**item)
            for item in _posts.list_reviews(session, evaluation_id)]


@router.post("/{site_id}/evaluations/{evaluation_id}/reviews",
             response_model=WebsitePostReviewRead, status_code=201)
def add_review(
    site_id: str, evaluation_id: str, payload: WebsitePostReviewCreate,
    request: Request, session: Session = Depends(get_session),
) -> WebsitePostReviewRead:
    from mission_control.models import WebsitePostEvaluation as _Model

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    row = session.get(_Model, evaluation_id)
    if row is None or row.website_id != site_id:
        raise NotFound("Evaluation not found.")
    result = _posts.record_review(
        session, evaluation_id=evaluation_id, finding_id=payload.finding_id,
        decision=payload.decision, reason=payload.reason, reviewer=payload.reviewer)
    session.flush()
    return WebsitePostReviewRead(**result)
