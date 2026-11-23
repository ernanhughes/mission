"""Read-only site-posts-context.v1 builder (BLOG-01 D1).

Composes a per-post read-model from existing website/post records plus
caller-supplied Writer post-envelope dicts. The builder is a pure read
operation over existing rows: it never writes, never re-scores, never
calls a model, and never creates a canonical table.

Bindings (never interchanged):

- ``content_sha256`` is authoritative and always the sha256 of the RAW
  file bytes (front matter included). Blog-editorial rows bind it, and
  editorial freshness is derived from it: a front-matter-only edit
  conservatively flips the editorial assessment to stale.
- ``source_hash`` is the sha256 of the EVALUATED body bytes (the bytes a
  Writer provider actually observed). A Writer envelope's freshness
  follows its own binding: it stays current while the body is unchanged,
  even when front matter churn flips the raw hash. The raw/location
  binding travels alongside as ``content_sha256`` with an explicit
  ``location_match`` flag, so reviewers can triage metadata-only churn.
- ``text_sha256`` is a non-authoritative hint: the sha256 of the live
  body bytes. It never drives freshness; it only lets reviewers compare
  ``source_hash`` against the present body without re-reading the file.

Writer input is validated only (``validate_post_envelope`` mirrors the
shape rules of ``mission_control.writer.evaluations`` and adds the post
convention ``work_object.kind == "post"`` plus identity binding). One
bad envelope never poisons the context: it is reported under
``value["rejected"]`` and excluded from the measures.

Offset mapping: ``raw_byte == body_offset_bytes + body_byte``. When the
split cannot be established byte-exactly the offset is ``None`` and the
extraction block says so explicitly — positions are never invented.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import WebsitePostEvaluation
from mission_control.websites import posts as _posts
from mission_control.websites import rubric as _rubric
from mission_control.writer.evaluations import (
    ENVELOPE_STATUSES,
    QUALIFIED_PROVIDERS,
    SCHEMA_VERSION as WRITER_ENVELOPE_VERSION,
    EnvelopeValidationError,
)

SCHEMA = "site-posts-context.v1"
EXTRACT_VERSION = "post-body-split.v1"
GENERATOR = "mission.websites.context.build_site_post_context"

MEASURE_WRITER_ID = "mission.site.post.evaluations"
MEASURE_EDITORIAL_ID = "mission.site.post.editorial"

LINEAGE_NOTE = (
    "identity is scanner-derived (relpath for standalone md; parent dir for "
    "leaf bundles); moves/renames create a new identity; relpath is location, "
    "not identity"
)

TOP_LEVEL_LIMITATIONS = [
    "Editorial evidence, not a publication decision.",
    "NOT_RUN is not zero; STALE is not current.",
    "Absent finding is not a verified fix.",
]

WRITER_LIMITATIONS = [
    "Writer evaluations use native provider scales; never average across providers.",
    "Historical entries describe earlier source revisions; only CURRENT describes the compared bytes.",
    "An absent finding is not a verified fix; resolution needs a comparable reassessment.",
]

EDITORIAL_LIMITATIONS = [
    "Single-model judgment; reading verifies nothing external.",
    "Scores are blog-editorial-v1 only; never average with any other rubric.",
]

LOCATION_DRIFT_NOTE = (
    "Location binding drifted while evaluated bytes are unchanged "
    "(front-matter/relpath churn): Writer observation still describes the "
    "current body; editorial freshness follows the raw hash and is stale."
)

MAX_HISTORY_CODES = 200
EVAL_HISTORY_LIMIT = 50


# ------------------------------------------------------- body split


def split_post_body(raw: bytes) -> dict[str, Any]:
    """Byte-exact front-matter split.

    Returns ``{"body": bytes | None, "offset": int | None,
    "format": str | None, "note": str | None}``. Only a leading ``+++``
    or ``---`` delimiter counts (mirroring the scanner); anything else
    means the whole file is the body at offset 0. Unterminated front
    matter yields ``body=None`` with an explicit note — never a guess.
    """
    for delimiter, fmt in ((b"+++", "toml"), (b"---", "yaml")):
        if raw.startswith(delimiter):
            end = raw.find(b"\n" + delimiter, len(delimiter))
            if end == -1:
                return {
                    "body": None,
                    "offset": None,
                    "format": fmt,
                    "note": f"unterminated {fmt} front matter; body not mapped",
                }
            eol = raw.find(b"\n", end + 1)
            if eol == -1:
                return {
                    "body": b"",
                    "offset": len(raw),
                    "format": fmt,
                    "note": "closing delimiter is the final line; body is empty",
                }
            return {"body": raw[eol + 1 :], "offset": eol + 1, "format": fmt, "note": None}
    return {"body": raw, "offset": 0, "format": "none", "note": None}


def body_span_to_raw(start: int, end: int, body_offset_bytes: int | None) -> tuple[int, int] | None:
    """Map a body-relative [start, end) span to raw-file bytes.

    Returns ``None`` when the offset is unavailable or the span is not a
    well-formed non-negative range — callers must treat that as
    explicitly unmapped, never as zero.
    """
    if body_offset_bytes is None:
        return None
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        return None
    if start < 0 or end < start:
        return None
    return (body_offset_bytes + start, body_offset_bytes + end)


# ------------------------------------------------------- envelope validation


def _require_str(record: Any, key: str, *, where: str) -> str:
    if not isinstance(record, dict):
        raise EnvelopeValidationError(f"{where} must be an object")
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise EnvelopeValidationError(f"{where}.{key} must be a non-empty string")
    return value


def _require_sha_hex(record: dict[str, Any], key: str, *, where: str) -> str:
    value = _require_str(record, key, where=where)
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
        raise EnvelopeValidationError(f"{where}.{key} must be sha256 hex")
    return value


def validate_post_envelope(payload: Any, *, identity: str) -> dict[str, Any]:
    """Validate one Writer post envelope for ``identity``. Returns it unchanged.

    Shape rules mirror ``mission_control.writer.evaluations`` (same
    schema version, statuses, qualified providers, dimension/finding
    structure); the post convention additionally requires
    ``work_object.kind == "post"`` and ``work_object.target_id ==
    identity``. Optional post-adapter fields (``content_sha256``,
    ``text_sha256``, ``body_offset_bytes``) are type-checked when
    present and ignored when absent. Raises EnvelopeValidationError.
    """
    if not isinstance(payload, dict):
        raise EnvelopeValidationError("envelope must be a JSON object")
    if payload.get("schema_version") != WRITER_ENVELOPE_VERSION:
        raise EnvelopeValidationError(f"schema_version must be {WRITER_ENVELOPE_VERSION!r}")
    evaluation_id = _require_str(payload, "evaluation_id", where="envelope")
    _require_str(payload, "observed_at", where="envelope")
    status = payload.get("status")
    if status not in ENVELOPE_STATUSES:
        raise EnvelopeValidationError(f"status must be one of {ENVELOPE_STATUSES}")
    work = payload.get("work_object")
    if not isinstance(work, dict):
        raise EnvelopeValidationError("work_object must be an object")
    if work.get("kind") != "post":
        raise EnvelopeValidationError(
            "work_object.kind must be 'post' for site-posts context "
            f"(evaluation {evaluation_id!r} declares {work.get('kind')!r})"
        )
    target_id = _require_str(work, "target_id", where="work_object")
    if target_id != identity:
        raise EnvelopeValidationError(
            f"work_object.target_id {target_id!r} does not match post {identity!r}"
        )
    _require_sha_hex(work, "source_hash", where="work_object")
    for key in ("content_sha256", "text_sha256"):
        if work.get(key) is not None:
            _require_sha_hex(work, key, where="work_object")
    if work.get("body_offset_bytes") is not None:
        offset = work.get("body_offset_bytes")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise EnvelopeValidationError(
                "work_object.body_offset_bytes must be a non-negative int"
            )
    producer = payload.get("producer")
    if not isinstance(producer, dict):
        raise EnvelopeValidationError("producer must be an object")
    runtime_name = _require_str(producer, "runtime_name", where="producer")
    if runtime_name not in QUALIFIED_PROVIDERS:
        raise EnvelopeValidationError(
            f"producer.runtime_name {runtime_name!r} is not a qualified W1 provider"
        )
    for key in ("dimensions", "findings", "limitations"):
        if not isinstance(payload.get(key), list):
            raise EnvelopeValidationError(f"{key} must be a list")
    if not isinstance(payload.get("provenance"), dict):
        raise EnvelopeValidationError("provenance must be an object")
    for index, dimension in enumerate(payload["dimensions"]):
        if not isinstance(dimension, dict):
            raise EnvelopeValidationError(f"dimensions[{index}] must be an object")
        _require_str(dimension, "dimension", where=f"dimensions[{index}]")
        scale = dimension.get("scale")
        if not isinstance(scale, dict):
            raise EnvelopeValidationError(f"dimensions[{index}].scale must be an object")
        _require_str(scale, "scale_type", where=f"dimensions[{index}].scale")
        _require_str(scale, "description", where=f"dimensions[{index}].scale")
    for index, finding in enumerate(payload["findings"]):
        if not isinstance(finding, dict):
            raise EnvelopeValidationError(f"findings[{index}] must be an object")
        _require_str(finding, "family", where=f"findings[{index}]")
        _require_str(finding, "code", where=f"findings[{index}]")
        claim = finding.get("claim")
        if not isinstance(claim, str):
            raise EnvelopeValidationError(f"findings[{index}].claim must be a string")
    return payload


# ------------------------------------------------------- builder


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finding_codes(envelope: Mapping[str, Any]) -> tuple[list[str], bool, int]:
    codes = sorted(
        {
            str(finding.get("code", ""))
            for finding in envelope.get("findings", [])
            if isinstance(finding, dict) and finding.get("code")
        }
    )
    total = len(codes)
    if total > MAX_HISTORY_CODES:
        return codes[:MAX_HISTORY_CODES], True, total
    return codes, False, total


def _writer_measure(
    *,
    identity: str,
    live_raw_sha: str,
    live_text_sha: str | None,
    envelopes: Sequence[Any],
) -> dict[str, Any]:
    """Writer post-evaluations measure. Validates, never scores."""
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    inputs = list(envelopes or [])
    for index, payload in enumerate(inputs):
        try:
            envelope = validate_post_envelope(payload, identity=identity)
        except EnvelopeValidationError as exc:
            evaluation_id = payload.get("evaluation_id") if isinstance(payload, dict) else None
            producer = (payload.get("producer") if isinstance(payload, dict) else None) or {}
            rejected.append(
                {
                    "index": index,
                    "evaluation_id": evaluation_id if isinstance(evaluation_id, str) else None,
                    "provider": producer.get("runtime_name")
                    if isinstance(producer, dict)
                    else None,
                    "error": str(exc),
                }
            )
            continue
        evaluation_id = envelope["evaluation_id"]
        if evaluation_id in seen:
            rejected.append(
                {
                    "index": index,
                    "evaluation_id": evaluation_id,
                    "provider": envelope["producer"]["runtime_name"],
                    "error": "duplicate evaluation_id; kept newest by (observed_at, evaluation_id)",
                }
            )
            continue
        seen.add(evaluation_id)
        valid.append(envelope)

    ordered = sorted(
        valid,
        key=lambda env: (str(env.get("observed_at", "")), str(env["evaluation_id"])),
        reverse=True,
    )
    # Newest observation per provider describes the post; older ones are history.
    current_ids: set[str] = set()
    for provider in {env["producer"]["runtime_name"] for env in ordered}:
        for env in ordered:
            if env["producer"]["runtime_name"] == provider:
                current_ids.add(env["evaluation_id"])
                break

    evaluations: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    location_drift = False
    for env in ordered:
        work = env["work_object"]
        if env.get("status") == "unavailable":
            derived = "UNAVAILABLE"
            body_match: bool | None = None
            location_match: bool | None = None
        else:
            body_match = None if live_text_sha is None else work.get("source_hash") == live_text_sha
            env_raw = work.get("content_sha256")
            if env_raw is None or live_raw_sha is None:
                location_match = None
            else:
                location_match = env_raw == live_raw_sha
            derived = (
                "CURRENT"
                if body_match is True
                else "STALE"
                if body_match is False
                else "UNVERIFIED"
            )
            if body_match is True and location_match is False:
                location_drift = True
        if env["evaluation_id"] in current_ids:
            evaluations.append(
                {
                    "evaluation_id": env["evaluation_id"],
                    "provider": env["producer"]["runtime_name"],
                    "observed_at": env.get("observed_at"),
                    "current": True,
                    "derived": derived,
                    "body_match": body_match,
                    "location_match": location_match,
                    "envelope": env,
                }
            )
        else:
            codes, codes_capped, codes_total = _finding_codes(env)
            history.append(
                {
                    "evaluation_id": env["evaluation_id"],
                    "provider": env["producer"]["runtime_name"],
                    "observed_at": env.get("observed_at"),
                    "status": env.get("status"),
                    "source_hash": work.get("source_hash"),
                    "content_sha256": work.get("content_sha256"),
                    "finding_codes": codes,
                    "finding_codes_truncated": codes_capped,
                    "finding_codes_total": codes_total,
                    "body_match": body_match,
                    "location_match": location_match,
                    "derived": derived,
                }
            )

    providers = sorted({env["producer"]["runtime_name"] for env in ordered})
    if not ordered:
        status = "NOT_RUN"
        detail = f"No Writer evaluations supplied for {identity} (NOT_RUN)."
    elif any(item["derived"] == "CURRENT" for item in evaluations):
        status = "CURRENT"
        detail = (
            f"{len(evaluations)} current, {len(history)} historical Writer "
            f"evaluation(s) for {identity} (providers: {', '.join(providers)})."
        )
    elif any(item["derived"] == "STALE" for item in evaluations):
        status = "STALE"
        detail = (
            f"Newest Writer evaluation(s) for {identity} describe earlier "
            f"body bytes (STALE); {len(history)} historical."
        )
    else:
        status = "UNAVAILABLE"
        detail = (
            f"Writer evaluation(s) for {identity} cannot be verified against "
            f"live bytes (UNAVAILABLE)."
        )
    limitations = list(WRITER_LIMITATIONS)
    if location_drift:
        limitations.append(LOCATION_DRIFT_NOTE)
    if live_text_sha is None:
        limitations.append(
            "Live body bytes are unavailable (unreadable or over budget); "
            "envelope freshness is UNVERIFIED, never assumed."
        )
    return {
        "id": MEASURE_WRITER_ID,
        "kind": "post_evaluations",
        "scope": "post",
        "status": status,
        "label": "Post evaluations",
        "detail": detail,
        "value": {
            "evaluations": evaluations,
            "history": history,
            "rejected": rejected,
            "coverage": {
                "providers": providers,
                "current": len(evaluations),
                "historical": len(history),
                "rejected": len(rejected),
            },
        },
        "limitations": limitations,
    }


def _editorial_measure(
    session: Session, *, website_id: str, identity: str, live_raw_sha: str | None
) -> dict[str, Any]:
    """Blog-editorial-v1 measure. Carries stored rows verbatim, plus reviews."""
    rows = session.scalars(
        select(WebsitePostEvaluation)
        .where(
            WebsitePostEvaluation.website_id == website_id,
            WebsitePostEvaluation.article_identity == identity,
        )
        .order_by(desc(WebsitePostEvaluation.created_at))
        .limit(EVAL_HISTORY_LIMIT)
    ).all()
    reads = [_posts._evaluation_read(session, row, live_raw_sha) for row in rows]
    for read, row in zip(reads, rows):
        read["reviews"] = _posts.list_reviews(session, row.id)
    current = next(
        (entry for entry in reads if entry["status"] == "CURRENT" and not entry["stale"]),
        None,
    )
    history_refs = []
    for entry in reads:
        if current is not None and entry["id"] == current["id"]:
            continue
        history_refs.append(
            {
                "evaluation_id": entry["id"],
                "status": entry["status"],
                "overall": entry["overall"],
                "content_sha256": entry["content_sha256"],
                "freshness": entry["freshness"],
                "stale": entry["stale"],
                "previous_evaluation_id": entry["previous_evaluation_id"],
                "requested_model": entry["requested_model"],
                "actual_model": entry["actual_model"],
                "created_at": entry["created_at"],
                "reviews": entry["reviews"],
            }
        )
    if current is not None:
        status = "CURRENT"
        detail = (
            f"CURRENT {current['id']} overall {current['overall']} "
            f"on {str(current['content_sha256'])[:12]}; "
            f"{len(history_refs)} historical entr{'y' if len(history_refs) == 1 else 'ies'}."
        )
    elif any(entry["status"] == "CURRENT" for entry in reads):
        status = "STALE"
        detail = (
            f"Latest blog-editorial-v1 CURRENT evaluation(s) for {identity} "
            f"are stale on live {str(live_raw_sha)[:12] if live_raw_sha else 'unknown'}; "
            f"{len(reads)} row(s) total, none current."
        )
    elif reads:
        latest = reads[0]["status"]
        status = "BLOCKED"
        detail = (
            f"No CURRENT blog-editorial-v1 evaluation for {identity}; "
            f"latest terminal outcome is {latest} ({len(reads)} row(s), no scores)."
        )
    else:
        status = "NOT_RUN"
        detail = f"No blog-editorial-v1 evaluations recorded for {identity} (NOT_RUN)."
    return {
        "id": MEASURE_EDITORIAL_ID,
        "kind": "model_judgment",
        "scope": "post",
        "status": status,
        "label": "Post editorial evaluation",
        "detail": detail,
        "value": {
            "current": current,
            "history_refs": history_refs,
            "rubric_id": _rubric.RUBRIC_ID,
            "rubric_version": _rubric.RUBRIC_VERSION,
        },
        "limitations": list(EDITORIAL_LIMITATIONS),
    }


def build_site_post_context(
    session: Session,
    *,
    website_id: str,
    blog_dir: Path | str,
    identity: str,
    writer_envelopes: Sequence[Any] | None = None,
    blog_section: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build one ``site-posts-context.v1`` read-model for a single post.

    Read-only: resolves the live post via the same scanner/identities as
    listing, binds the live raw + body hashes, then composes the Writer
    and editorial measures. Supports editorial-only (``writer_envelopes``
    empty), Writer-only (no editorial rows), both, or neither (all
    measures report ``NOT_RUN`` honestly).
    """
    if writer_envelopes is not None and not isinstance(writer_envelopes, (list, tuple)):
        raise ValidationProblem("writer_envelopes must be a list of envelope objects")
    directory = Path(blog_dir)
    live = {post["identity"]: post for post in _posts._live_posts(directory)}
    post = live.get(identity)
    if post is None:
        raise NotFound("Article not found in the blog directory.")
    _text, live_raw_sha, truncated = _posts.read_article_text(directory, post["relpath"])

    # Split the exact bytes that were hashed above: re-read and refuse on
    # mid-read drift rather than mapping bytes that no longer match the hash.
    candidate = directory / Path(*Path(post["relpath"]).parts)
    try:
        raw = candidate.read_bytes()
    except OSError:
        raise NotFound(f"Article is unavailable: {post['relpath']}") from None
    if _posts.hash_content(raw) != live_raw_sha:
        raise ValidationProblem("Article changed during read; retry the request.")
    split = split_post_body(raw)
    if truncated:
        live_text_sha: str | None = None
        body_offset: int | None = None
        body_format: str | None = None
        body_length: int | None = None
        extraction_note = (
            "article exceeds the read budget; body bytes not mapped (refused rather than guessed)"
        )
    elif split["body"] is None:
        live_text_sha = None
        body_offset = None
        body_format = split["format"]
        body_length = None
        extraction_note = split["note"]
    else:
        import hashlib as _hashlib

        live_text_sha = _hashlib.sha256(split["body"]).hexdigest()
        body_offset = split["offset"]
        body_format = split["format"]
        body_length = len(split["body"])
        extraction_note = split["note"]

    writer_measure = _writer_measure(
        identity=identity,
        live_raw_sha=live_raw_sha,
        live_text_sha=live_text_sha,
        envelopes=writer_envelopes or [],
    )
    editorial_measure = _editorial_measure(
        session, website_id=website_id, identity=identity, live_raw_sha=live_raw_sha
    )

    section = blog_section or directory.name
    return {
        "schema": SCHEMA,
        "generated_at": generated_at or _utcnow_iso(),
        "generator": GENERATOR,
        "site": {"website_id": website_id, "blog_dir": section},
        "post": {
            "article_identity": identity,
            "relpath": post["relpath"],
            "title": post.get("title"),
            "content_sha256": live_raw_sha,
            "text_sha256": live_text_sha,
            "body_offset_bytes": body_offset,
            "body_format": body_format,
            "post_status": post["post_status"],
            "truncated": truncated,
            "lineage_note": LINEAGE_NOTE,
        },
        "extraction": {
            "version": EXTRACT_VERSION,
            "front_matter_format": body_format,
            "body_offset_bytes": body_offset,
            "body_byte_length": body_length,
            "note": extraction_note,
        },
        "measures": [writer_measure, editorial_measure],
        "limitations": list(TOP_LEVEL_LIMITATIONS),
    }
