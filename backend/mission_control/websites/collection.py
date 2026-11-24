"""Read-only website collection quality map (BLOG-01 D4).

Pure read-model over the existing post inventory (same Hugo scanner and
identities as listing, evaluation and the D2 site-post context) plus the
existing ``WebsitePostEvaluation`` rows. The builder never writes, never
re-scores, never triggers an evaluation and never calls a model: it only
SELECTs rows and reads live files.

Scope contract (never merged, never asserted without evidence):

- Scores are blog-editorial-v1 only. Rows from any other rubric are
  excluded and counted, never averaged. Writer scales never enter.
- NOT_RUN is not zero; STALE is not current; an absent finding is not a
  verified fix.
- Duplication candidates are deterministic traceable evidence only
  (verbatim shared titles or verbatim shared anchored quotes with content
  digests). Every candidate is ``decision: "pending"``: a human decides,
  this map never merges, renames or judges.
- Contradictions, topic gaps and outdated claims are
  ``status: "unavailable"`` with explicit reasons until paired
  quote+digest evidence exists. They are never asserted here.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.models import WebsitePostEvaluation
from mission_control.websites import context as _context
from mission_control.websites import posts as _posts
from mission_control.websites import rubric as _rubric

SCHEMA = "site-collection-quality.v1"
GENERATOR = "mission.websites.collection.build_collection_quality_map"

# Caps keep the map bounded and honest: examined-row counts are reported.
EVAL_ROW_LIMIT = 500
WEAKEST_DEFAULT_N = 5
MIN_QUOTE_CHARS = 40

LIMITATIONS = [
    "Editorial evidence, not a publication decision.",
    "NOT_RUN is not zero; STALE is not current.",
    "Scores are blog-editorial-v1 only; never average with any other rubric or Writer scale.",
    "Duplication candidates are traceable evidence for a pending human decision, never merge verdicts.",
    "Contradictions, topic gaps and outdated claims are unavailable until paired quote+digest evidence exists.",
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(text: str) -> str:
    """Whitespace-collapsed casefolded form for verbatim comparison."""
    return " ".join(str(text or "").split()).casefold()


def _quote_digest(normalised: str) -> str:
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _live_bodies(
    blog_dir: Path, posts: list[dict[str, Any]]
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Normalised live body text per identity, reusing the D2 body split.

    Returns ``(bodies, unmapped)``. Articles that cannot be read or whose
    body cannot be mapped byte-exactly are excluded from quote matching
    and listed under ``unmapped`` with an explicit reason — never guessed.
    """
    bodies: dict[str, str] = {}
    unmapped: list[dict[str, str]] = []
    for post in posts:
        identity = post["identity"]
        try:
            _text, _sha, truncated = _posts.read_article_text(blog_dir, post["relpath"])
        except Exception as exc:  # NotFound / ValidationProblem: report, never invent.
            unmapped.append({"identity": identity, "reason": f"unreadable: {exc}"})
            continue
        if truncated:
            unmapped.append(
                {"identity": identity, "reason": "exceeds read budget; body not mapped"}
            )
            continue
        candidate = blog_dir / Path(*Path(post["relpath"]).parts)
        try:
            raw = candidate.read_bytes()
        except OSError as exc:
            unmapped.append({"identity": identity, "reason": f"unreadable: {exc}"})
            continue
        if _posts.hash_content(raw) != _sha:
            unmapped.append({"identity": identity, "reason": "changed during read"})
            continue
        split = _context.split_post_body(raw)
        if split["body"] is None:
            unmapped.append(
                {"identity": identity, "reason": str(split.get("note") or "body not mapped")}
            )
            continue
        try:
            bodies[identity] = " ".join(split["body"].decode("utf-8").split())
        except UnicodeDecodeError:
            bodies[identity] = " ".join(split["body"].decode("utf-8", errors="replace").split())
    return bodies, unmapped


def _all_eval_rows(session: Session, website_id: str) -> tuple[list[WebsitePostEvaluation], bool]:
    rows = session.scalars(
        select(WebsitePostEvaluation)
        .where(WebsitePostEvaluation.website_id == website_id)
        .order_by(desc(WebsitePostEvaluation.created_at))
        .limit(EVAL_ROW_LIMIT + 1)
    ).all()
    capped = len(rows) > EVAL_ROW_LIMIT
    return list(rows[:EVAL_ROW_LIMIT]), capped


def _live_body_sha(directory: Path, relpath: str) -> str | None:
    """Sha256 of the live evaluated body bytes, or None when unavailable.

    Same binding as the D5 maintenance projection: the split is byte-exact
    via the D2 ``split_post_body`` path, and unreadable/unmappable sources
    yield no digest — never a guessed one.
    """
    try:
        candidate = directory / Path(*Path(relpath).parts)
        raw = candidate.read_bytes()
    except (OSError, ValueError):
        return None
    try:
        split = _context.split_post_body(raw)
    except Exception:
        return None
    body = split.get("body")
    if not isinstance(body, bytes) or not body:
        return None
    return hashlib.sha256(body).hexdigest()


def _writer_evidence_block(
    session: Session,
    website_id: str,
    directory: Path,
    published: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-post Writer observation state from stored evidence (read-only).

    Never executes the detector, never writes, never averages: each entry
    carries the latest stored observation beside the live body digest with
    an explicit freshness verdict (current/stale/missing/unknown). A rename
    creates a new identity with no transferred history, so a renamed post
    honestly reports missing until it is observed under its new identity.
    """
    from mission_control.models import WebsitePostWriterObservation

    try:
        rows = list(
            session.scalars(
                select(WebsitePostWriterObservation)
                .where(WebsitePostWriterObservation.website_id == website_id)
                .order_by(desc(WebsitePostWriterObservation.created_at))
                .limit(EVAL_ROW_LIMIT)
            ).all()
        )
        capped = len(rows) >= EVAL_ROW_LIMIT
    except Exception:
        rows, capped = [], False
    latest: dict[str, Any] = {}
    history_counts: dict[str, int] = {}
    for row in reversed(rows):  # oldest-first so the newest wins
        latest[row.article_identity] = row
        history_counts[row.article_identity] = history_counts.get(row.article_identity, 0) + 1
    entries: list[dict[str, Any]] = []
    current = stale = missing = unknown = 0
    for post in sorted(published, key=lambda item: item["identity"]):
        identity = post["identity"]
        live_sha = _live_body_sha(directory, post["relpath"])
        row = latest.get(identity)
        if row is None:
            freshness = "missing" if live_sha is not None else "unknown"
            entry: dict[str, Any] = {
                "identity": identity,
                "relpath": post["relpath"],
                "title": post.get("title"),
                "has_evidence": False,
                "freshness": freshness,
                "result": "unknown",
                "stored": None,
                "live_body_sha256": live_sha,
                "history_count": 0,
            }
        elif live_sha is None:
            freshness = "unknown"
            entry = {
                "identity": identity,
                "relpath": post["relpath"],
                "title": post.get("title"),
                "has_evidence": True,
                "freshness": "unknown",
                "result": "unknown",
                "stored": _writer_stored_summary(row),
                "live_body_sha256": None,
                "history_count": history_counts.get(identity, 0),
            }
        else:
            freshness = "current" if row.body_sha256 == live_sha else "stale"
            entry = {
                "identity": identity,
                "relpath": post["relpath"],
                "title": post.get("title"),
                "has_evidence": True,
                "freshness": freshness,
                "result": "passed" if row.status == "complete" else "pending",
                "stored": _writer_stored_summary(row),
                "live_body_sha256": live_sha,
                "history_count": history_counts.get(identity, 0),
            }
        if freshness == "current":
            current += 1
        elif freshness == "stale":
            stale += 1
        elif freshness == "missing":
            missing += 1
        else:
            unknown += 1
        entries.append(entry)
    return {
        "denominator": "published posts only; Writer observations are stored per canonical identity",
        "published": len(published),
        "current": current,
        "stale": stale,
        "missing": missing,
        "unknown": unknown,
        "needs_attention": [
            {"identity": entry["identity"], "freshness": entry["freshness"]}
            for entry in entries
            if entry["freshness"] in ("stale", "missing")
        ],
        "posts": entries,
        "note": (
            "Writer evidence only: a current observation never establishes "
            "editorial quality. Editorial coverage and scores are unchanged."
        ),
        "rows_examined": len(rows),
        "rows_capped": capped,
    }


def _writer_stored_summary(row: Any) -> dict[str, Any]:
    return {
        "observation_id": str(getattr(row, "id", "")),
        "status": str(getattr(row, "status", "")),
        "evaluation_id": str(getattr(row, "evaluation_id", "")),
        "finding_count": int(getattr(row, "finding_count", 0) or 0),
        "observed_at": str(getattr(row, "observed_at", "") or ""),
        "execution_id": getattr(row, "execution_id", None),
        "fingerprint": str(getattr(row, "fingerprint", "") or ""),
    }


def build_collection_quality_map(
    session: Session,
    *,
    website_id: str,
    blog_dir: Path | str,
    weakest_n: int = WEAKEST_DEFAULT_N,
    min_quote_chars: int = MIN_QUOTE_CHARS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build one ``site-collection-quality.v1`` read-model for a website.

    Read-only: resolves the live post inventory with the same
    scanner/identities as listing (hence counts can never contradict
    listing), derives currency from stored CURRENT rows versus live hashes,
    and aggregates scored rows only. Raises the same ``NotFound`` /
    ``ValidationProblem`` errors as listing when the blog directory is
    unavailable.
    """
    directory = Path(blog_dir)
    posts = _posts._live_posts(directory)
    by_identity = {post["identity"]: post for post in posts}

    # Live raw hash per post. Unreadable posts bind no hash (sha None):
    # currency for them is "never", never assumed.
    live_sha: dict[str, str | None] = {}
    for post in posts:
        try:
            _text, sha, _truncated = _posts.read_article_text(directory, post["relpath"])
        except Exception:
            sha = None
        live_sha[post["identity"]] = sha

    # Currency is rubric-bound: only the newest CURRENT blog-editorial-v1
    # row per identity can be current. Rows from any other rubric never
    # drive currency (they are counted under excluded, never merged).
    rows, rows_capped = _all_eval_rows(session, website_id)
    blog_current: dict[str, WebsitePostEvaluation] = {}
    for row in reversed(rows):  # oldest-first so the newest wins
        if row.rubric_id == _rubric.RUBRIC_ID and row.status == "CURRENT":
            blog_current[row.article_identity] = row

    def _currency(identity: str) -> tuple[str, WebsitePostEvaluation | None]:
        latest = blog_current.get(identity)
        freshness, _stale = _posts.evaluation_freshness(latest, live_sha[identity])
        return freshness, latest

    # ------------------------------------------------------- inventory
    status_counts = {"published": 0, "draft": 0, "scheduled": 0, "unknown": 0}
    for post in posts:
        status_counts[post["post_status"]] += 1

    # --------------------------------------------------- coverage (published only)
    published = [post for post in posts if post["post_status"] == "published"]
    current_ids: list[str] = []
    stale_ids: list[str] = []
    unevaluated_ids: list[str] = []
    for post in published:
        freshness, latest = _currency(post["identity"])
        if freshness == "current" and isinstance(latest.overall if latest else None, (int, float)):
            current_ids.append(post["identity"])
        elif freshness == "stale":
            stale_ids.append(post["identity"])
        else:
            unevaluated_ids.append(post["identity"])
    coverage_percent = (len(current_ids) / len(published) * 100.0) if published else None

    # --------------------------------- scores (blog-editorial-v1 only)
    scored: list[dict[str, Any]] = []
    excluded_stale = 0
    excluded_non_current_status = 0
    excluded_other_rubric = 0
    excluded_unscored = 0
    for row in rows:
        if row.rubric_id != _rubric.RUBRIC_ID:
            excluded_other_rubric += 1
            continue
        if row.status != "CURRENT":
            excluded_non_current_status += 1
            continue
        latest = blog_current.get(row.article_identity)
        if latest is None or latest.id != row.id:
            excluded_stale += 1  # superseded by a newer CURRENT row
            continue
        post = by_identity.get(row.article_identity)
        if post is None or post["post_status"] != "published":
            # Evaluation for a post outside the published inventory:
            # not scored, not silently dropped — counted.
            excluded_unscored += 1
            continue
        if _currency(row.article_identity)[0] != "current":
            excluded_stale += 1
            continue
        if not isinstance(row.overall, (int, float)):
            excluded_unscored += 1
            continue
        scored.append(
            {
                "identity": row.article_identity,
                "relpath": post["relpath"],
                "title": post.get("title"),
                "overall": float(row.overall),
                "evaluation_id": row.id,
                "content_sha256": row.content_sha256,
            }
        )
    overall_values = [entry["overall"] for entry in scored]
    ordered = sorted(scored, key=lambda e: (e["overall"], e["identity"]))
    weakest = ordered[: max(int(weakest_n), 0)]

    # -------------------------------------------- review queues (oldest first)
    def _queue_key(identity: str) -> tuple[int, str, str]:
        post = by_identity[identity]
        return (0 if post.get("date") else 1, str(post.get("date") or ""), identity)

    def _queue_entry(identity: str) -> dict[str, Any]:
        post = by_identity[identity]
        latest = blog_current.get(identity)
        return {
            "identity": identity,
            "relpath": post["relpath"],
            "title": post.get("title"),
            "date": post.get("date"),
            "evaluation_id": latest.id if latest else None,
            "overall": latest.overall if latest else None,
        }

    stale_queue = [_queue_entry(identity) for identity in sorted(stale_ids, key=_queue_key)]
    for entry in stale_queue:
        # Stale posts are by construction not in `scored`; carry the
        # evaluated digest from the newest CURRENT blog row for traceability.
        latest = blog_current.get(entry["identity"])
        if latest is not None:
            entry["evaluated_digest"] = latest.content_sha256
        entry["live_digest"] = live_sha[entry["identity"]]
    unevaluated_queue = [
        {
            "identity": identity,
            "relpath": by_identity[identity]["relpath"],
            "title": by_identity[identity].get("title"),
            "date": by_identity[identity].get("date"),
        }
        for identity in sorted(unevaluated_ids, key=_queue_key)
    ]

    # --------------------------------- duplication candidates (evidence only)
    bodies, unmapped = _live_bodies(directory, posts)
    candidates: list[dict[str, Any]] = []

    # Shared verbatim titles across distinct identities.
    title_groups: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        norm_title = _norm(post.get("title") or "")
        if not norm_title:
            continue
        title_groups.setdefault(norm_title, []).append(post)
    for norm_title in sorted(title_groups):
        group = title_groups[norm_title]
        if len({post["identity"] for post in group}) < 2:
            continue
        members = sorted(group, key=lambda p: p["identity"])
        candidates.append(
            {
                "candidate_id": f"dup-title-{len(candidates) + 1:03d}",
                "kind": "shared_title",
                "decision": "pending",
                "note": "Human decision required; not a merge verdict.",
                "evidence": {
                    "normalized_title": norm_title,
                    "digest": _quote_digest(norm_title),
                    "posts": [
                        {
                            "identity": post["identity"],
                            "relpath": post["relpath"],
                            "title": post.get("title"),
                            "content_sha256": _posts.hash_content(
                                (directory / Path(*Path(post["relpath"]).parts)).read_bytes()
                            )
                            if (directory / Path(*Path(post["relpath"]).parts)).is_file()
                            else None,
                        }
                        for post in members
                    ],
                },
            }
        )

    # Shared verbatim anchored quotes: a stored finding/improvement quote
    # (minimum length) that occurs verbatim in the live bodies of two or
    # more distinct posts. Each carrier post must contain it now
    # (quote_anchored against the live body), and the evidence carries the
    # quote, its digest, and every carrier's content digest.
    quote_posts: dict[str, dict[str, Any]] = {}
    for row in rows:
        for field in ("findings", "improvements"):
            items = getattr(row, field, None)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                quote = item.get("source_quote")
                if not isinstance(quote, str):
                    continue
                normalised = " ".join(quote.split())
                if len(normalised) < min_quote_chars:
                    continue
                key = _quote_digest(normalised.casefold())
                slot = quote_posts.setdefault(key, {"quote": normalised, "carriers": {}})
                slot["carriers"].setdefault(
                    row.article_identity,
                    {
                        "identity": row.article_identity,
                        "evaluation_id": row.id,
                        "field": field,
                        "finding_id": str(item.get("finding_id", ""))[:200],
                    },
                )
    for key in sorted(quote_posts):
        slot = quote_posts[key]
        carriers = [
            identity
            for identity in slot["carriers"]
            if identity in bodies and _rubric.quote_anchored(bodies[identity], slot["quote"])
        ]
        if len(carriers) < 2:
            continue
        carriers.sort()
        candidates.append(
            {
                "candidate_id": f"dup-quote-{len(candidates) + 1:03d}",
                "kind": "shared_quote",
                "decision": "pending",
                "note": "Human decision required; not a merge verdict.",
                "evidence": {
                    "quote": slot["quote"][:2000],
                    "quote_truncated": len(slot["quote"]) > 2000,
                    "quote_chars": len(slot["quote"]),
                    "digest": key,
                    "posts": [
                        {
                            "identity": identity,
                            "relpath": by_identity[identity]["relpath"],
                            "title": by_identity[identity].get("title"),
                            "content_sha256": _posts.hash_content(
                                (
                                    directory / Path(*Path(by_identity[identity]["relpath"]).parts)
                                ).read_bytes()
                            ),
                            "evaluation_id": slot["carriers"][identity]["evaluation_id"],
                            "field": slot["carriers"][identity]["field"],
                            "finding_id": slot["carriers"][identity]["finding_id"],
                        }
                        for identity in carriers
                        if identity in by_identity
                    ],
                },
            }
        )
    candidates.sort(key=lambda c: (c["kind"], c["candidate_id"]))

    # ----------------- provisional sections: unavailable until evidenced
    provisional = {
        "contradictions": {
            "status": "unavailable",
            "reason": (
                "No paired-quote contradiction evidence exists. Asserting a "
                "contradiction requires two verbatim anchored quotes with "
                "content digests from distinct posts plus human adjudication; "
                "this read-model records observations only and never pairs "
                "quotes into verdicts."
            ),
        },
        "topic_gaps": {
            "status": "unavailable",
            "reason": (
                "No topic taxonomy or inventory is bound to this collection. "
                "Naming absent topics without a confirmed topic list would "
                "invent scope, so gaps are not inferred."
            ),
        },
        "outdated_claims": {
            "status": "unavailable",
            "reason": (
                "Reading an article never verifies external truth. Marking a "
                "claim outdated requires dated external evidence with "
                "digests, which this read-model does not hold."
            ),
        },
    }

    return {
        "schema": SCHEMA,
        "generated_at": generated_at or _utcnow_iso(),
        "generator": GENERATOR,
        "site": {"website_id": website_id, "blog_dir": directory.name},
        "inventory": {
            "discovered": len(posts),
            "published": status_counts["published"],
            "draft": status_counts["draft"],
            "scheduled": status_counts["scheduled"],
            "unknown": status_counts["unknown"],
        },
        "coverage": {
            "denominator": "published posts only; drafts, scheduled and unknown files cannot be evaluated",
            "published": len(published),
            "evaluated_current": len(current_ids),
            "evaluated_stale": len(stale_ids),
            "unevaluated": len(unevaluated_ids),
            "coverage_percent": coverage_percent,
        },
        "scores": {
            "rubric_id": _rubric.RUBRIC_ID,
            "rubric_version": _rubric.RUBRIC_VERSION,
            "aggregation_method": _rubric.AGGREGATION_METHOD,
            "max_total": _rubric.MAX_TOTAL,
            "denominator": (
                "current blog-editorial-v1 CURRENT evaluations on live content "
                "with numeric overall; stale, superseded, non-CURRENT, "
                "unscored and other-rubric rows are excluded, never zero-filled"
            ),
            "n_scored": len(scored),
            "average": (sum(overall_values) / len(overall_values) if overall_values else None),
            "min": min(overall_values) if overall_values else None,
            "max": max(overall_values) if overall_values else None,
            "weakest": [
                {
                    "identity": entry["identity"],
                    "relpath": entry["relpath"],
                    "title": entry["title"],
                    "overall": entry["overall"],
                    "evaluation_id": entry["evaluation_id"],
                }
                for entry in weakest
            ],
            "excluded": {
                "stale_or_superseded": excluded_stale,
                "non_current_status": excluded_non_current_status,
                "other_rubric": excluded_other_rubric,
                "unscored_or_missing_post": excluded_unscored,
            },
            "rows_examined": len(rows),
            "rows_capped": rows_capped,
        },
        "review_queues": {
            "stale_oldest_first": stale_queue,
            "unevaluated_oldest_first": unevaluated_queue,
        },
        "duplication_candidates": candidates,
        "duplication_unmapped": unmapped,
        "provisional": provisional,
        "writer_evidence": _writer_evidence_block(session, website_id, directory, published),
        "limitations": list(LIMITATIONS),
    }
