"""Writer evaluation envelopes as Mission Control read-model records.

Consumes ``writer.evaluation-envelope.v1`` JSON produced by Writer-owned
evaluation code (see LIVING-WORK-BOOKS-01 W1). Mission never re-scores,
never rewrites, and never merges these with prose/technical/artifact or
publication measures.

Storage: existing ``integration_records`` with
``resource_type="writer_evaluation"`` and ``external_id=<evaluation_id>``.
No migration, no new table, no shared database with Writer. History is
preserved: a new evaluation for the same provider+chapter marks the
previous current row historical; replaying the same ``evaluation_id`` is
an idempotent no-op that creates nothing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mission_control.models import Book, IntegrationRecord
from mission_control.persistence.db import Database, now_iso

SCHEMA_VERSION = "writer.evaluation-envelope.v1"
RESOURCE_TYPE = "writer_evaluation"
APPLICATION_ID = "writer"

# Gate B: only qualified W1 providers are accepted. Unknown providers are
# rejected explicitly, never silently stored.
QUALIFIED_PROVIDERS = ("artifact", "qc")

ENVELOPE_STATUSES = ("complete", "partial", "empty", "unavailable")

# Display-level freshness derived at read time, never stored.
DERIVED_CURRENT = "CURRENT"
DERIVED_STALE = "STALE"
DERIVED_NOT_RUN = "NOT_RUN"
DERIVED_UNAVAILABLE = "UNAVAILABLE"
DERIVED_UNVERIFIED = "UNVERIFIED"


class EnvelopeValidationError(ValueError):
    """Raised when a presented envelope is not a valid W1 envelope."""


def _require_str(record: dict[str, Any], key: str, *, where: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise EnvelopeValidationError(f"{where}.{key} must be a non-empty string")
    return value


def _require_str_allowing_empty(record: dict[str, Any], key: str, *, where: str) -> str:
    # Shape is enforced, content is preserved verbatim: an empty native
    # claim/rationale is itself information, not a schema violation.
    value = record.get(key)
    if not isinstance(value, str):
        raise EnvelopeValidationError(f"{where}.{key} must be a string")
    return value


def validate_envelope(payload: Any) -> dict[str, Any]:
    """Strict structural validation. Returns the payload unchanged.

    Checks identity, provenance, and shape only. Scores, findings, and
    coverage are carried verbatim; nothing is computed or reinterpreted.
    Raises EnvelopeValidationError on any violation.
    """
    if not isinstance(payload, dict):
        raise EnvelopeValidationError("envelope must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise EnvelopeValidationError(f"schema_version must be {SCHEMA_VERSION!r}")
    _require_str(payload, "evaluation_id", where="envelope")
    status = payload.get("status")
    if status not in ENVELOPE_STATUSES:
        raise EnvelopeValidationError(f"status must be one of {ENVELOPE_STATUSES}")
    work = payload.get("work_object")
    if not isinstance(work, dict):
        raise EnvelopeValidationError("work_object must be an object")
    _require_str(work, "target_id", where="work_object")
    source_hash = _require_str(work, "source_hash", where="work_object")
    if len(source_hash) != 64 or any(ch not in "0123456789abcdef" for ch in source_hash.lower()):
        raise EnvelopeValidationError("work_object.source_hash must be sha256 hex")
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
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
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
        _require_str_allowing_empty(finding, "claim", where=f"findings[{index}]")
    return payload


def _record_id(evaluation_id: str) -> str:
    digest = hashlib.sha256(
        f"{APPLICATION_ID}:{RESOURCE_TYPE}:{evaluation_id}".encode("utf-8")
    ).hexdigest()[:32]
    return f"wreval-{digest}"


def ingest_envelope(
    database: Database,
    payload: dict[str, Any],
    *,
    project_id: str | None = None,
    ingested_by: str = "operator",
) -> dict[str, Any]:
    """Validate and store one envelope. Idempotent on ``evaluation_id``.

    Returns ``{"record_id", "evaluation_id", "created": bool}``.
    ``created=False`` means an exact replay: nothing was written.
    A new evaluation for the same provider+chapter marks the previous
    current row historical; history rows are never modified or deleted.
    """
    envelope = validate_envelope(payload)
    evaluation_id = envelope["evaluation_id"]
    provider = envelope["producer"]["runtime_name"]
    target_id = envelope["work_object"]["target_id"]
    with database.session() as session:
        try:
            existing = session.scalar(
                select(IntegrationRecord).where(
                    IntegrationRecord.application_id == APPLICATION_ID,
                    IntegrationRecord.resource_type == RESOURCE_TYPE,
                    IntegrationRecord.external_id == evaluation_id,
                )
            )
            if existing is not None:
                return {
                    "record_id": existing.id,
                    "evaluation_id": evaluation_id,
                    "created": False,
                }
            prior = session.scalars(
                select(IntegrationRecord).where(
                    IntegrationRecord.application_id == APPLICATION_ID,
                    IntegrationRecord.resource_type == RESOURCE_TYPE,
                    IntegrationRecord.current.is_(True),
                )
            ).all()
            for row in prior:
                data = row.data if isinstance(row.data, dict) else {}
                producer = data.get("producer", {})
                work = data.get("work_object", {})
                if (
                    isinstance(producer, dict)
                    and isinstance(work, dict)
                    and producer.get("runtime_name") == provider
                    and work.get("target_id") == target_id
                ):
                    row.current = False
                    row.updated_at = now_iso()
            record = IntegrationRecord(
                id=_record_id(evaluation_id),
                application_id=APPLICATION_ID,
                resource_type=RESOURCE_TYPE,
                external_id=evaluation_id,
                project_id=project_id,
                title=f"{provider} evaluation: {target_id}",
                summary=(
                    f"{envelope['status']}: {len(envelope['dimensions'])} "
                    f"dimension(s), {len(envelope['findings'])} finding(s)"
                ),
                state=str(envelope["status"]),
                source_version=str(envelope.get("producer", {}).get("method_version", "")),
                source_timestamp=envelope.get("observed_at"),
                observed_at=now_iso(),
                stale_after_seconds=0,
                evidence=[str(envelope["work_object"].get("source_path") or "")],
                data=envelope,
                search_text=(f"writer_evaluation {provider} {target_id} {envelope['status']}")[
                    :30_000
                ],
                current=True,
            )
            session.add(record)
            session.commit()
            return {
                "record_id": record.id,
                "evaluation_id": evaluation_id,
                "created": True,
            }
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(IntegrationRecord).where(
                    IntegrationRecord.application_id == APPLICATION_ID,
                    IntegrationRecord.resource_type == RESOURCE_TYPE,
                    IntegrationRecord.external_id == evaluation_id,
                )
            )
            if existing is None:  # pragma: no cover - defensive
                raise
            return {
                "record_id": existing.id,
                "evaluation_id": evaluation_id,
                "created": False,
            }


def chapter_file_sha(path: str | Path) -> str | None:
    """sha256 of a chapter file, or None when unreadable. Read-only."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _stem(chapter_id: str) -> str:
    """Envelope target_ids are extension-less stems ("39-chapter") while
    callers may use filenames ("39-chapter.md"). Normalize for lookup only;
    the compared bytes still decide freshness."""
    return chapter_id[: -len(".md")] if chapter_id.endswith(".md") else chapter_id


def resolve_chapter_sha(database: Database, project_id: str, target_id: str) -> str | None:
    """Best-either server-side chapter hash via the book manuscript paths.

    Accepts stem or filename form. Returns None when no exactly-one
    candidate file exists. Conservative by design: ambiguity refuses
    rather than guesses.
    """
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == project_id))
        if book is None:
            return None
        stem = _stem(target_id)
        candidates: list[Path] = []
        for root in book.manuscript_paths or []:
            try:
                base = Path(root)
                if not base.is_absolute() or not base.is_dir():
                    continue
                for candidate in (base / stem, base / f"{stem}.md"):
                    if candidate.is_file() and candidate not in candidates:
                        candidates.append(candidate)
            except OSError:
                continue
        if len(candidates) != 1:
            return None
        return chapter_file_sha(candidates[0])


def chapter_evaluations_from_session(
    session,
    project_id: str,
    chapter_id: str,
    *,
    source_hash: str | None,
) -> dict[str, Any]:
    """Session-core of chapter_evaluations (no session management)."""
    rows = session.scalars(
        select(IntegrationRecord)
        .where(
            IntegrationRecord.application_id == APPLICATION_ID,
            IntegrationRecord.resource_type == RESOURCE_TYPE,
        )
        .order_by(IntegrationRecord.observed_at.desc())
    ).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        data = row.data if isinstance(row.data, dict) else {}
        work = data.get("work_object", {})
        if not isinstance(work, dict) or work.get("target_id") != chapter_id:
            continue
        if project_id and row.project_id and row.project_id != project_id:
            continue
        items.append(
            {
                "record_id": row.id,
                "evaluation_id": row.external_id,
                "current": bool(row.current),
                "observed_at": row.observed_at,
                "envelope": data,
            }
        )
    for item in items:
        envelope = item["envelope"]
        env_status = envelope.get("status")
        env_hash = (envelope.get("work_object", {}) or {}).get("source_hash")
        if env_status == "unavailable":
            item["derived"] = DERIVED_UNAVAILABLE
        elif source_hash is None:
            item["derived"] = DERIVED_UNVERIFIED
        elif env_hash == source_hash:
            item["derived"] = DERIVED_CURRENT
        else:
            item["derived"] = DERIVED_STALE
    if not items:
        overall = DERIVED_NOT_RUN
    elif any(item["current"] and item["derived"] == DERIVED_UNAVAILABLE for item in items):
        overall = DERIVED_UNAVAILABLE
    elif any(item["current"] and item["derived"] == DERIVED_CURRENT for item in items):
        overall = DERIVED_CURRENT
    elif any(item["current"] for item in items) and all(
        item["derived"] in (DERIVED_STALE, DERIVED_UNVERIFIED) for item in items if item["current"]
    ):
        overall = (
            DERIVED_STALE
            if all(item["derived"] == DERIVED_STALE for item in items if item["current"])
            else DERIVED_UNVERIFIED
        )
    else:
        overall = DERIVED_UNVERIFIED
    return {
        "project_id": project_id,
        "chapter_id": chapter_id,
        "overall": overall,
        "source_hash_compared": source_hash,
        "evaluations": items,
    }


def chapter_evaluations(
    database: Database,
    project_id: str,
    chapter_id: str,
    *,
    source_hash: str | None = None,
) -> dict[str, Any]:
    """Current + historical Writer evaluations for one chapter.

    ``source_hash`` (the bytes the caller actually read) drives freshness:
    equal -> CURRENT, different -> STALE, absent-but-unresolvable ->
    UNVERIFIED, no records -> NOT_RUN, envelope unavailable -> UNAVAILABLE.
    Chapter ids accept stem or filename form ("39-chapter" == "39-chapter.md").
    """
    chapter_id = _stem(chapter_id)
    if source_hash is None:
        source_hash = resolve_chapter_sha(database, project_id, chapter_id)
    with database.session() as session:
        return chapter_evaluations_from_session(
            session, project_id, chapter_id, source_hash=source_hash
        )
