"""Blog-post listing, evaluation and reviews for website workspaces."""

from __future__ import annotations

from functools import partial

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.api.websites import _state, _websites_root
from mission_control.core.errors import CapabilityUnavailable, NotFound, ValidationProblem
from mission_control.schemas import (
    WebsitePostDetailRead,
    WebsitePostEvaluateRequest,
    WebsitePostEvaluationRead,
    WebsitePostListRead,
    WebsitePostReviewCreate,
    WebsitePostReviewRead,
    WebsitePostsSummaryRead,
)
from mission_control.websites import collection as _collection
from mission_control.websites import evaluate as _evaluate
from mission_control.websites import post_artifact as _post_artifact
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
    return WebsitePostListRead(
        **_posts.list_posts(
            session,
            website_id=site_id,
            blog_dir=blog_dir,
            status=status,
            evaluated=evaluated,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/{site_id}/posts/summary", response_model=WebsitePostsSummaryRead)
def get_posts_summary(
    site_id: str, request: Request, session: Session = Depends(get_session)
) -> WebsitePostsSummaryRead:
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    return WebsitePostsSummaryRead(
        **_posts.posts_summary(session, website_id=site_id, blog_dir=blog_dir)
    )


@router.get("/{site_id}/posts/{identity:path}", response_model=WebsitePostDetailRead)
def get_post(
    site_id: str,
    identity: str,
    request: Request,
    session: Session = Depends(get_session),
) -> WebsitePostDetailRead:
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    return WebsitePostDetailRead(
        **_posts.get_post_detail(session, website_id=site_id, blog_dir=blog_dir, identity=identity)
    )


@router.post("/{site_id}/posts/{identity:path}/writer-observation", response_model=dict)
def observe_post_writer(
    site_id: str, identity: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    """Run one deterministic Writer artifact observation for a post.

    Read-only and model-free: the detector runs in-process on the post's
    live body bytes and the validated envelope is returned without storing
    anything or modifying the manuscript. A manually invoked, governed
    operation — never automatic. Unknown identities 404 via the D2
    resolution path; unmappable bodies 422 without fabricating evidence.
    """
    from mission_control.persistence.db import now_iso

    _state(request)
    blog_dir = _blog_dir(request, site_id)
    envelope = _post_artifact.artifact_envelope_for_live_post(
        blog_dir, identity=identity, observed_at=now_iso()
    )
    if envelope is None:
        raise ValidationProblem(
            "Post body cannot be mapped to evaluated bytes "
            "(unterminated front matter); no observation was made."
        )
    return envelope


@router.get("/{site_id}/collection/quality", response_model=dict)
def get_collection_quality(
    site_id: str,
    request: Request,
    session: Session = Depends(get_session),
    weakest_n: int = Query(default=5, ge=0, le=50),
    min_quote_chars: int = Query(default=40, ge=10, le=500),
) -> dict:
    """Read-only collection quality map for a website's blog section.

    Projects stored editorial evaluations plus live file state; never
    validates, scores, evaluates, or writes. Writer evidence appears only
    where a stored evaluation already carries it — nothing is executed here.
    """
    _state(request)
    blog_dir = _blog_dir(request, site_id)
    return _collection.build_collection_quality_map(
        session,
        website_id=site_id,
        blog_dir=blog_dir,
        weakest_n=weakest_n,
        min_quote_chars=min_quote_chars,
    )


@router.post("/{site_id}/posts/{identity:path}/evaluate", response_model=WebsitePostEvaluationRead)
def evaluate_post(
    site_id: str,
    identity: str,
    payload: WebsitePostEvaluateRequest,
    request: Request,
    session: Session = Depends(get_session),
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
        session,
        website_id=site_id,
        blog_dir=blog_dir,
        identity=identity,
        run_evaluation=partial(_evaluate.run_pi_evaluation, model=model),
        model=model,
        force=bool(payload.force),
    )
    session.flush()
    return WebsitePostEvaluationRead(**result)


@router.get("/{site_id}/evaluations/{evaluation_id}", response_model=WebsitePostEvaluationRead)
def get_evaluation(
    site_id: str,
    evaluation_id: str,
    request: Request,
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
                _websites_root(request), _resolve_site(_websites_root(request), site_id)
            ),
            row.relpath,
        )
    except Exception:
        sha = row.content_sha256
    return WebsitePostEvaluationRead(**_posts._evaluation_read(session, row, sha))


@router.get(
    "/{site_id}/evaluations/{evaluation_id}/reviews", response_model=list[WebsitePostReviewRead]
)
def get_reviews(
    site_id: str,
    evaluation_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> list[WebsitePostReviewRead]:
    from mission_control.models import WebsitePostEvaluation as _Model

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    row = session.get(_Model, evaluation_id)
    if row is None or row.website_id != site_id:
        raise NotFound("Evaluation not found.")
    return [WebsitePostReviewRead(**item) for item in _posts.list_reviews(session, evaluation_id)]


@router.post(
    "/{site_id}/evaluations/{evaluation_id}/reviews",
    response_model=WebsitePostReviewRead,
    status_code=201,
)
def add_review(
    site_id: str,
    evaluation_id: str,
    payload: WebsitePostReviewCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> WebsitePostReviewRead:
    from mission_control.models import WebsitePostEvaluation as _Model

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    row = session.get(_Model, evaluation_id)
    if row is None or row.website_id != site_id:
        raise NotFound("Evaluation not found.")
    result = _posts.record_review(
        session,
        evaluation_id=evaluation_id,
        finding_id=payload.finding_id,
        decision=payload.decision,
        reason=payload.reason,
        reviewer=payload.reviewer,
    )
    session.flush()
    return WebsitePostReviewRead(**result)


@router.get("/{site_id}/writer-maintenance/status", response_model=dict)
def get_writer_maintenance_status(
    site_id: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    """Read-only automatic Writer maintenance state for blog posts.

    Never dispatches, never writes: policy version, master switch,
    per-site pause, and recent execution activity.
    """
    from mission_control.websites import maintenance as _maintenance

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    database = request.app.state.database
    settings = request.app.state.settings
    return _maintenance.maintenance_status(database, settings)


@router.post("/{site_id}/writer-maintenance/enabled", response_model=dict)
def set_writer_maintenance_enabled(
    site_id: str,
    payload: dict,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Master switch for automatic Writer maintenance. Records standing authorization."""
    from mission_control.websites import maintenance as _maintenance

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    result = _maintenance.set_auto_enabled(session, bool(payload.get("enabled", False)))
    session.commit()
    return {"enabled": result, "policy_version": _maintenance.BLOG_AUTO_POLICY_VERSION}


@router.post("/{site_id}/writer-maintenance/pause", response_model=dict)
def set_writer_maintenance_paused(
    site_id: str,
    payload: dict,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Pause or resume automatic Writer maintenance for one site."""
    from mission_control.websites import maintenance as _maintenance

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    target = str(payload.get("website_id") or site_id).strip() or site_id
    paused = _maintenance.set_website_paused(session, target, bool(payload.get("paused", True)))
    session.commit()
    return {"website_id": target, "paused_websites": paused}


@router.post("/{site_id}/writer-maintenance/reconcile", response_model=dict)
async def run_writer_maintenance_reconcile(
    site_id: str, payload: dict | None = None, request: Request = None
) -> dict:
    """Run one blog maintenance reconciliation pass.

    ``dry_run`` defaults to True (preview only): nothing is dispatched
    unless the caller explicitly passes ``dry_run: false`` AND the master
    switch is enabled. Catalogue-wide automatic processing stays off.
    """
    from mission_control.websites import maintenance as _maintenance

    _state(request)
    _resolve_site(_websites_root(request), site_id)
    database = request.app.state.database
    settings = request.app.state.settings
    integration_service = getattr(request.app.state, "integration_service", None)
    if integration_service is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Integration service is unavailable.")
    service = _maintenance.BlogMaintenanceService(database, settings, integration_service)
    dry_run = True if payload is None else bool(payload.get("dry_run", True))
    report = await service.run_once(dry_run=dry_run)
    return report.to_dict()


@router.get("/{site_id}/writer-observations/{identity:path}", response_model=dict)
def list_writer_observations(
    site_id: str,
    identity: str,
    request: Request,
    session: Session = Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Stored Writer observation history for one post, newest first.

    Read-only: append-only evidence with per-row digest binding. An empty
    history reports ``missing``/``unknown`` — never a fabricated observation.
    """
    from sqlalchemy import desc, select

    from mission_control.models import WebsitePostWriterObservation

    _state(request)
    blog_dir = _blog_dir(request, site_id)
    match = next(
        (post for post in _posts._live_posts(blog_dir) if post["identity"] == identity), None
    )
    if match is None:
        raise NotFound("Post not found.")
    rows = list(
        session.scalars(
            select(WebsitePostWriterObservation)
            .where(
                WebsitePostWriterObservation.website_id == site_id,
                WebsitePostWriterObservation.article_identity == match["identity"],
            )
            .order_by(desc(WebsitePostWriterObservation.created_at))
            .limit(limit)
        ).all()
    )
    return {
        "website_id": site_id,
        "identity": match["identity"],
        "relpath": match["relpath"],
        "history_count": len(rows),
        "observations": [
            {
                "observation_id": row.id,
                "status": row.status,
                "evaluation_id": row.evaluation_id,
                "body_sha256": row.body_sha256,
                "content_sha256": row.content_sha256,
                "finding_count": row.finding_count,
                "execution_id": row.execution_id,
                "fingerprint": row.fingerprint,
                "observed_at": row.observed_at,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }
