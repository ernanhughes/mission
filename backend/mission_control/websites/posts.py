"""Blog-post listing, evaluation history and reviews (MC-WEBSITES-POSTS-01).

Post discovery reuses the Cultivation Hugo scanner
(``mission_control.cultivation.sources.scan_hugo_blog``) on the website's own
``content/<section>`` directory, so Posts counts can never contradict the
Cultivation blog counts: same scanner, same directory, same identities.

Evaluation records are website-scoped and chapter-independent: blog articles
are never forced into book-specific records and no fictitious Project entries
are introduced. History is append-only; staleness is derived at read time by
comparing ``content_sha256`` against the live file hash.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.cultivation.sources import scan_hugo_blog
from mission_control.discovery.websites import DetectedWebsite
from mission_control.models import WebsitePostEvaluation, WebsitePostReview
from mission_control.persistence.db import now_iso
from mission_control.websites import rubric as _rubric

logger = logging.getLogger(__name__)

POST_STATUSES = ("published", "draft", "scheduled", "unknown")
EVALUATION_FILTERS = ("all", "current", "stale", "unevaluated")
EVALterminal_STATUSES = ("BLOCKED", "ERROR", "CANCELLED", "NOT_RUN")

MAX_CONTENT_CHARS = 200_000


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def resolve_blog_dir(root: Path, site: DetectedWebsite) -> Path:
    """Resolve ``content/<section>`` for a website or explain why there is none."""
    if not site.is_hugo:
        raise ValidationProblem(
            f"Website '{site.name}' is not a Hugo project and has no blog section."
        )
    if not site.content_section:
        raise ValidationProblem(
            f"Website '{site.name}' has no confirmed blog section "
            "(no post/posts/blog/articles directory under content/)."
        )
    blog_dir = Path(site.path) / "content" / site.content_section
    if not blog_dir.is_dir():
        raise NotFound(f"Blog directory is unavailable: {blog_dir}")
    return blog_dir


def article_status(state: str, reason: str) -> str:
    if state == "published":
        return "published"
    if state == "draft" and reason.startswith("scheduled for"):
        return "scheduled"
    if state == "draft":
        return "draft"
    return "unknown"


def hash_content(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_article_text(blog_dir: Path, relpath: str) -> tuple[str, str, bool]:
    """Return (text, sha256, truncated) for an article, confined to blog_dir."""
    candidate = (blog_dir / Path(*Path(relpath).parts)).resolve(strict=False)
    try:
        blog_root = blog_dir.resolve(strict=False)
    except OSError:
        raise NotFound("Blog directory is unavailable.")
    if candidate != blog_root and blog_root not in candidate.parents:
        raise ValidationProblem("Article path escapes the blog directory.")
    try:
        raw = candidate.read_bytes()
    except OSError:
        raise NotFound(f"Article is unavailable: {relpath}")
    digest = hash_content(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_CONTENT_CHARS:
        return text[:MAX_CONTENT_CHARS], digest, True
    return text, digest, False


def _live_posts(blog_dir: Path, *, published_only: bool = False) -> list[dict[str, Any]]:
    """Scan and normalise posts. Same scanner/identities as Cultivation."""
    scan = scan_hugo_blog(blog_dir)
    posts: list[dict[str, Any]] = []
    for post in scan.posts:
        status = article_status(post.state, post.reason)
        if published_only and status != "published":
            continue
        posts.append({
            "identity": post.identity,
            "title": post.title,
            "relpath": post.relpath,
            "date": post.date.isoformat() if post.date else None,
            "post_status": status,
        })
    return posts


def latest_current_evaluation(
    session: Session, website_id: str, identity: str
) -> WebsitePostEvaluation | None:
    """Newest CURRENT evaluation, if any (history keeps the rest)."""
    return session.scalars(select(WebsitePostEvaluation).where(
        WebsitePostEvaluation.website_id == website_id,
        WebsitePostEvaluation.article_identity == identity,
        WebsitePostEvaluation.status == "CURRENT",
    ).order_by(desc(WebsitePostEvaluation.created_at)).limit(1)).first()


def evaluation_freshness(
    evaluation: WebsitePostEvaluation | None, live_sha: str | None
) -> tuple[str, bool]:
    """Return (freshness, stale). Only CURRENT rows on the live hash are current."""
    if evaluation is None or live_sha is None:
        return "never", False
    if evaluation.content_sha256 == live_sha:
        return "current", False
    return "stale", True


def _summaries(
    session: Session, website_id: str, posts: list[dict[str, Any]], blog_dir: Path
) -> dict[str, dict[str, Any]]:
    """Evaluation summary per article identity (current/stale/unevaluated)."""
    out: dict[str, dict[str, Any]] = {}
    for post in posts:
        try:
            _text, sha, _truncated = read_article_text(blog_dir, post["relpath"])
        except (NotFound, ValidationProblem):
            sha = None
        current = latest_current_evaluation(session, website_id, post["identity"])
        freshness, stale = evaluation_freshness(current, sha)
        out[post["identity"]] = {
            "evaluation_id": current.id if current else None,
            "overall": current.overall if current else None,
            "status": current.status if current else None,
            "freshness": freshness,
            "evaluated_at": current.created_at if current else None,
            "stale": stale,
            "rubric_id": current.rubric_id if current else None,
            "rubric_version": current.rubric_version if current else None,
        }
    return out


def list_posts(
    session: Session,
    *,
    website_id: str,
    blog_dir: Path,
    status: str = "all",
    evaluated: str = "all",
    search: str | None = None,
    sort: str = "date_desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Searchable, sortable, paginated article list with evaluation summaries."""
    if status not in ("all", *POST_STATUSES):
        raise ValidationProblem(f"Unknown post status filter: {status}")
    if evaluated not in EVALUATION_FILTERS:
        raise ValidationProblem(f"Unknown evaluation filter: {evaluated}")
    posts = _live_posts(blog_dir)
    counts = {"published": 0, "drafts": 0, "scheduled": 0, "unknown": 0}
    for post in posts:
        if post["post_status"] == "published":
            counts["published"] += 1
        elif post["post_status"] == "draft":
            counts["drafts"] += 1
        elif post["post_status"] == "scheduled":
            counts["scheduled"] += 1
        else:
            counts["unknown"] += 1
    summaries = _summaries(session, website_id, posts, blog_dir)
    needle = (search or "").strip().casefold()
    filtered = []
    for post in posts:
        summary = summaries[post["identity"]]
        if status != "all" and post["post_status"] != status:
            continue
        if evaluated != "all" and summary["freshness"] != evaluated:
            continue
        if needle and needle not in post["title"].casefold() and needle not in post["relpath"].casefold():
            continue
        filtered.append({**post, "website_id": website_id, "evaluation": summary})
    if sort == "title_asc":
        filtered.sort(key=lambda item: item["title"].casefold())
    elif sort == "title_desc":
        filtered.sort(key=lambda item: item["title"].casefold(), reverse=True)
    elif sort == "score_desc":
        filtered.sort(key=lambda item: (
            item["evaluation"]["overall"] is None, -(item["evaluation"]["overall"] or 0)))
    elif sort == "score_asc":
        filtered.sort(key=lambda item: (
            item["evaluation"]["overall"] is None, item["evaluation"]["overall"] or 0))
    else:  # date_desc: undated articles sort last, stable by identity.
        filtered.sort(key=lambda item: (item["date"] is None, item["date"] or "", item["identity"]),
                      reverse=False)
        dated = [item for item in filtered if item["date"]]
        undated = [item for item in filtered if not item["date"]]
        dated.sort(key=lambda item: str(item["date"]), reverse=True)
        filtered = dated + undated
    total = len(filtered)
    page = filtered[max(offset, 0):max(offset, 0) + min(max(limit, 1), 200)]
    for item in page:
        try:
            text, _sha, _truncated = read_article_text(blog_dir, item["relpath"])
            item["word_count"] = len(text.split())
        except (NotFound, ValidationProblem):
            item["word_count"] = 0
    return {"items": page, "total": total, "limit": limit, "offset": offset,
            "published": counts["published"], "drafts": counts["drafts"],
            "scheduled": counts["scheduled"], "unknown": counts["unknown"]}


def _evaluation_read(
    session: Session, row: WebsitePostEvaluation, live_sha: str | None
) -> dict[str, Any]:
    """Return a read dict for one evaluation row."""
    dimensions = []
    stored = row.dimensions if isinstance(row.dimensions, dict) else {}
    for dim in _rubric.DIMENSIONS:
        entry = stored.get(dim.id) if isinstance(stored.get(dim.id), dict) else {}
        score = entry.get("score") if isinstance(entry, dict) else None
        dimensions.append({
            "id": dim.id, "label": dim.label,
            "score": score if isinstance(score, int) and not isinstance(score, bool) else None,
            "max_points": dim.max_points,
            "explanation": str(entry.get("explanation", "") if isinstance(entry, dict) else ""),
        })
    improvements = []
    for index, item in enumerate(row.improvements if isinstance(row.improvements, list) else []):
        if not isinstance(item, dict):
            continue
        quote = item.get("source_quote")
        improvements.append({
            "finding_id": str(item.get("finding_id", f"improvement-{index + 1}"))[:200],
            "rank": int(item.get("rank", index + 1)),
            "title": str(item.get("title", ""))[:300],
            "problem": str(item.get("problem", ""))[:4000],
            "why_it_matters": str(item.get("why_it_matters", ""))[:4000],
            "suggestion": str(item.get("suggestion", ""))[:4000],
            "source_heading": item.get("source_heading"),
            "source_quote": quote,
            "quote_anchored": bool(item.get("quote_anchored", False)),
        })
    findings = []
    for item in row.findings if isinstance(row.findings, list) else []:
        if not isinstance(item, dict):
            continue
        findings.append({
            "finding_id": str(item.get("finding_id", ""))[:200],
            "kind": str(item.get("kind", "observation"))[:60],
            "title": str(item.get("title", ""))[:300],
            "detail": str(item.get("detail", ""))[:4000],
            "source_heading": item.get("source_heading"),
            "source_quote": item.get("source_quote"),
            "quote_anchored": bool(item.get("quote_anchored", False)),
        })
    freshness, stale = evaluation_freshness(row, live_sha)
    return {
        "id": row.id, "website_id": row.website_id,
        "article_identity": row.article_identity, "relpath": row.relpath,
        "content_sha256": row.content_sha256, "rubric_id": row.rubric_id,
        "rubric_version": row.rubric_version, "prompt_version": row.prompt_version,
        "requested_model": row.requested_model, "actual_model": row.actual_model,
        "status": row.status, "overall": row.overall,
        "aggregation_method": row.aggregation_method,
        "dimensions": dimensions, "assessment": row.assessment,
        "strengths": list(row.strengths or []), "weaknesses": list(row.weaknesses or []),
        "improvements": improvements, "findings": findings,
        "uncertainty": row.uncertainty, "limitations": list(row.limitations or []),
        "execution": dict(row.execution or {}),
        "previous_evaluation_id": row.previous_evaluation_id,
        "freshness": freshness, "stale": stale,
        "created_at": row.created_at,
    }


def get_post_detail(
    session: Session, *, website_id: str, blog_dir: Path, identity: str
) -> dict[str, Any]:
    """Article detail: source info, content, full evaluation history."""
    posts = {post["identity"]: post for post in _live_posts(blog_dir)}
    post = posts.get(identity)
    if post is None:
        raise NotFound("Article not found in the blog directory.")
    text, sha, truncated = read_article_text(blog_dir, post["relpath"])
    history = session.scalars(select(WebsitePostEvaluation).where(
        WebsitePostEvaluation.website_id == website_id,
        WebsitePostEvaluation.article_identity == identity,
    ).order_by(desc(WebsitePostEvaluation.created_at)).limit(50)).all()
    reads = [_evaluation_read(session, row, sha) for row in history]
    current = next((entry for entry in reads
                    if entry["status"] == "CURRENT" and not entry["stale"]), None)
    summary = _summaries(session, website_id, [post], blog_dir)[identity]
    return {
        "post": {**post, "website_id": website_id,
                 "word_count": len(text.split()), "evaluation": summary},
        "content": text, "content_truncated": truncated, "content_sha256": sha,
        "evaluations": reads, "current": current,
    }


def _anchor_flags(items: list[Any], source_text: str) -> list[dict[str, Any]]:
    """Attach deterministic quote-anchored flags. Never invent positions."""
    flagged: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        quote = entry.get("source_quote")
        entry["quote_anchored"] = (
            _rubric.quote_anchored(source_text, str(quote)) if quote else False
        )
        flagged.append(entry)
    return flagged


def record_evaluation(
    session: Session,
    *,
    website_id: str,
    identity: str,
    relpath: str,
    content_sha256: str,
    source_text: str,
    scores: dict[str, Any],
    explanations: dict[str, str] | None = None,
    assessment: str = "",
    strengths: list[str] | None = None,
    weaknesses: list[str] | None = None,
    improvements: list[Any] | None = None,
    findings: list[Any] | None = None,
    uncertainty: str = "",
    limitations: list[str] | None = None,
    requested_model: str | None = None,
    actual_model: str | None = None,
    prompt_version: str | None = None,
    execution: dict[str, Any] | None = None,
    status: str = "CURRENT",
    force: bool = False,
) -> dict[str, Any]:
    """Persist one evaluation observation. Never fabricates scores.

    A repeated identical request (same article, same content hash, already
    CURRENT) returns the existing observation instead of duplicating it;
    ``force=True`` records an explicit re-evaluation linked via
    previous_evaluation_id.
    """
    if status not in ("CURRENT", "BLOCKED", "ERROR", "PARTIAL"):
        raise ValidationProblem(f"Unknown evaluation status: {status}")
    if status == "CURRENT":
        total, cleaned, errors = _rubric.validate_scores(scores or {})
        if errors:
            raise ValidationProblem("; ".join(errors[:5]))
    else:
        total, cleaned = 0, {}
    if not force and status == "CURRENT":
        existing = session.scalars(select(WebsitePostEvaluation).where(
            WebsitePostEvaluation.website_id == website_id,
            WebsitePostEvaluation.article_identity == identity,
            WebsitePostEvaluation.content_sha256 == content_sha256,
            WebsitePostEvaluation.status == "CURRENT",
        ).order_by(desc(WebsitePostEvaluation.created_at)).limit(1)).first()
        if existing is not None:
            return _evaluation_read(session, existing, content_sha256)
    previous = latest_current_evaluation(session, website_id, identity)
    dimensions = {
        dim.id: {"score": cleaned.get(dim.id),
                 "explanation": str((explanations or {}).get(dim.id, ""))[:4000]}
        for dim in _rubric.DIMENSIONS
    } if status == "CURRENT" else {}
    improvement_items: list[dict[str, Any]] = []
    for index, item in enumerate((improvements or [])[:10]):
        entry = dict(item) if isinstance(item, dict) else {"title": str(item)}
        entry.setdefault("finding_id", f"improvement-{index + 1}")
        improvement_items.append(entry)
    row = WebsitePostEvaluation(
        id=_new_id("wpe"), website_id=website_id, article_identity=identity,
        relpath=relpath, content_sha256=content_sha256,
        rubric_id=_rubric.RUBRIC_ID, rubric_version=_rubric.RUBRIC_VERSION,
        prompt_version=prompt_version or _rubric.PROMPT_VERSION,
        requested_model=requested_model, actual_model=actual_model,
        status=status, overall=float(total) if status == "CURRENT" else None,
        aggregation_method=_rubric.AGGREGATION_METHOD,
        dimensions=dimensions, assessment=assessment[:8000],
        strengths=[str(item)[:2000] for item in (strengths or [])][:20],
        weaknesses=[str(item)[:2000] for item in (weaknesses or [])][:20],
        improvements=_anchor_flags(improvement_items, source_text),
        findings=_anchor_flags(
            [dict(item) if isinstance(item, dict) else {"title": str(item)}
             for item in (findings or [])][:50], source_text),
        uncertainty=uncertainty[:4000],
        limitations=[str(item)[:2000] for item in (limitations or [])][:20],
        execution=dict(execution or {}),
        previous_evaluation_id=previous.id if previous else None,
        created_at=now_iso(),
    )
    session.add(row)
    session.flush()
    return _evaluation_read(session, row, content_sha256)


def evaluate_article(
    session: Session,
    *,
    website_id: str,
    blog_dir: Path,
    identity: str,
    run_evaluation: Any,
    model: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run one manual editorial evaluation (published articles only).

    ``run_evaluation`` is an injected callable
    ``(model=, title=, relpath=, article_text=) -> outcome`` so tests never
    touch a real model. Outcomes that are not CURRENT are recorded as
    BLOCKED/ERROR history without scores.
    """
    posts = {post["identity"]: post for post in _live_posts(blog_dir)}
    post = posts.get(identity)
    if post is None:
        raise NotFound("Article not found in the blog directory.")
    if post["post_status"] != "published":
        raise ValidationProblem(
            f"Only published articles can be evaluated (this one is {post['post_status']})."
        )
    text, sha, truncated = read_article_text(blog_dir, post["relpath"])
    if truncated:
        raise ValidationProblem(
            "Article exceeds the evaluation budget; refused rather than truncated."
        )
    outcome = run_evaluation(
        model=model, title=post["title"], relpath=post["relpath"], article_text=text)
    if not isinstance(outcome, dict):
        raise ValidationProblem("Evaluator returned an unusable outcome.")
    status = str(outcome.get("status", "ERROR"))
    execution = dict(outcome.get("execution", {}) or {})
    if status != "CURRENT":
        error = str(outcome.get("error", "Evaluator did not produce a result."))
        execution["error"] = error[:2000]
        return record_evaluation(
            session, website_id=website_id, identity=identity, relpath=post["relpath"],
            content_sha256=sha, source_text=text, scores={}, requested_model=model,
            actual_model=outcome.get("actual_model") or model,
            execution=execution, status=status if status in ("BLOCKED", "ERROR", "PARTIAL") else "ERROR",
            uncertainty=error[:2000], force=force)
    return record_evaluation(
        session, website_id=website_id, identity=identity, relpath=post["relpath"],
        content_sha256=sha, source_text=text, scores=outcome.get("scores", {}),
        explanations=outcome.get("explanations", {}),
        assessment=str(outcome.get("assessment", "")),
        strengths=outcome.get("strengths", []), weaknesses=outcome.get("weaknesses", []),
        improvements=outcome.get("improvements", []), findings=outcome.get("findings", []),
        uncertainty=str(outcome.get("uncertainty", "")),
        limitations=outcome.get("limitations", []),
        requested_model=model, actual_model=outcome.get("actual_model") or model,
        prompt_version=outcome.get("prompt_version"),
        execution=execution, status="CURRENT", force=force)


def record_review(
    session: Session, *, evaluation_id: str, finding_id: str, decision: str,
    reason: str = "", reviewer: str = "",
) -> dict[str, Any]:
    """Author decision on one finding. Append-only; AI judgments untouched."""
    evaluation = session.get(WebsitePostEvaluation, evaluation_id)
    if evaluation is None:
        raise NotFound("Evaluation not found.")
    if decision not in _rubric.EVALUATION_DECISIONS:
        raise ValidationProblem(
            f"Unknown decision: {decision}. Use one of: {', '.join(_rubric.EVALUATION_DECISIONS)}."
        )
    known_ids = {
        str(item.get("finding_id", "")) for item in evaluation.findings
        if isinstance(item, dict)
    } | {
        str(item.get("finding_id", "")) for item in evaluation.improvements
        if isinstance(item, dict)
    }
    if finding_id not in known_ids and finding_id != "__overall__":
        raise ValidationProblem(f"Unknown finding id: {finding_id}")
    review = WebsitePostReview(
        id=_new_id("wpr"), evaluation_id=evaluation.id, finding_id=finding_id,
        decision=decision, reason=reason[:4000], reviewer=reviewer[:120],
        source_digest=evaluation.content_sha256, created_at=now_iso())
    session.add(review)
    session.flush()
    return {"id": review.id, "evaluation_id": review.evaluation_id,
            "finding_id": review.finding_id, "decision": review.decision,
            "reason": review.reason, "reviewer": review.reviewer,
            "source_digest": review.source_digest, "created_at": review.created_at}


def list_reviews(session: Session, evaluation_id: str) -> list[dict[str, Any]]:
    evaluation = session.get(WebsitePostEvaluation, evaluation_id)
    if evaluation is None:
        raise NotFound("Evaluation not found.")
    rows = session.scalars(select(WebsitePostReview).where(
        WebsitePostReview.evaluation_id == evaluation_id,
    ).order_by(desc(WebsitePostReview.created_at)).limit(200)).all()
    return [{"id": row.id, "evaluation_id": row.evaluation_id,
             "finding_id": row.finding_id, "decision": row.decision,
             "reason": row.reason, "reviewer": row.reviewer,
             "source_digest": row.source_digest,
             "created_at": row.created_at} for row in rows]


def posts_summary(
    session: Session, *, website_id: str, blog_dir: Path
) -> dict[str, Any]:
    """Collection reporting. Currency counts cover published articles only
    (drafts, scheduled and unknown files cannot be evaluated); averages use
    current scored evaluations only."""
    posts = _live_posts(blog_dir)
    summaries = _summaries(session, website_id, posts, blog_dir)
    published = [post for post in posts if post["post_status"] == "published"]
    fresh = [post for post in published
             if summaries[post["identity"]]["freshness"] == "current"
             and isinstance(summaries[post["identity"]]["overall"], (int, float))]
    stale = sum(1 for post in published
                if summaries[post["identity"]]["freshness"] == "stale")
    unevaluated = len(published) - len(fresh) - stale
    scored = [summaries[post["identity"]]["overall"] for post in fresh]
    average = sum(scored) / len(scored) if scored else None
    coverage = (len(fresh) / len(published) * 100.0) if published else None
    return {
        "website_id": website_id, "discovered": len(posts), "published": len(published),
        "evaluated_current": len(fresh), "evaluated_stale": stale,
        "unevaluated": unevaluated, "average_score": average,
        "average_denominator": len(scored), "rubric_id": _rubric.RUBRIC_ID,
        "rubric_version": _rubric.RUBRIC_VERSION, "coverage_percent": coverage,
    }
