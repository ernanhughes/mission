"""Whole-library review batches (MC-SCRIPTS-05 Phase E2.1).

Bounded, resumable, idempotent: each step reviews a small number of scripts
sequentially through the E1 single-review path. One failure never invalidates
other results; restart recovery falls out of the database state. Reviews never
change lifecycle, completion, or effectiveness.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.models import ScriptBatch, ScriptBatchItem, ScriptRecord, ScriptReview
from mission_control.persistence.db import now_iso
from mission_control.scripts import intelligence as intellect
from mission_control.scripts.service import (
    _current_library_key,
    _new_id,
    list_records,
)

logger = logging.getLogger(__name__)

BATCH_STATUSES = ("open", "in_progress", "paused", "cancelled", "complete")
TERMINAL_BATCH = ("cancelled", "complete")
ITEM_STATUSES = ("pending", "reviewed", "failed", "skipped")
DEFAULT_STEP_LIMIT = 1
MAX_STEP_LIMIT = 5
MAX_BATCH_SCRIPTS = 2000


def _active_batch(session: Session, library_key: str) -> ScriptBatch | None:
    return session.scalars(select(ScriptBatch).where(
        ScriptBatch.library_key == library_key,
        ScriptBatch.status.not_in(TERMINAL_BATCH)).limit(1)).first()


def _latest_current_review(session: Session, record: ScriptRecord) -> ScriptReview | None:
    row = session.scalars(select(ScriptReview).where(
        ScriptReview.script_id == record.id).order_by(desc(ScriptReview.created_at)).limit(1)).first()
    if row is None:
        return None
    return row if intellect.review_freshness(record, row) == "CURRENT" else None


def _resolve_batch_model(session: Session, requested: str) -> tuple[str, str]:
    from mission_control.research import inference as _inference
    return _inference.resolve_model(session, requested or "")


def create_batch(session: Session, *, scope: str = "missing",
                 script_ids: list[str] | None = None,
                 status_filter: str | None = None,
                 model: str = "", force: bool = False) -> ScriptBatch:
    from mission_control.scripts.service import SCRIPT_STATUSES

    key = _current_library_key(session)
    if _active_batch(session, key) is not None:
        raise Conflict("A review batch is already active for this library; "
                       "cancel or complete it before starting another.")
    requested_model = (model or "").strip()
    if "/" in requested_model and len(requested_model) > 200:
        raise ValidationProblem("The selected model identifier is invalid.")
    if scope not in ("all", "missing", "stale", "ids", "status"):
        raise ValidationProblem(f"Unknown batch scope: {scope}")
    if scope == "ids" and not script_ids:
        raise ValidationProblem("scope=ids needs script_ids")
    if scope == "status" and status_filter not in SCRIPT_STATUSES:
        raise ValidationProblem(f"Unknown status filter: {status_filter}")

    if scope == "ids":
        records: list[ScriptRecord] = []
        seen: set[str] = set()
        for script_id in (script_ids or [])[:MAX_BATCH_SCRIPTS]:
            if script_id in seen:
                continue
            seen.add(str(script_id))
            record = session.get(ScriptRecord, str(script_id))
            if record is None or record.library_key not in ("", key):
                continue
            records.append(record)
    else:
        rows, _ = list_records(session, status=status_filter if scope == "status" else None,
                               include_archived=True, include_missing=False,
                               limit=MAX_BATCH_SCRIPTS)
        if scope == "missing":
            reviewed_ids = {row.script_id for row in session.scalars(select(ScriptReview)).all()}
            records = [row for row in rows if row.id not in reviewed_ids]
        elif scope == "stale":
            records = [row for row in rows if _latest_current_review(session, row) is None]
        else:
            records = rows
    if not records:
        batch = ScriptBatch(id=_new_id("bat"), library_key=key, status="complete",
                            model=requested_model, rubric_version="script-review-v1",
                            schema_version=intellect.REVIEW_SCHEMA,
                            selection={"scope": scope, "force": bool(force),
                                       "status_filter": status_filter,
                                       "requested": len(script_ids or []) if scope == "ids" else None},
                            counts={"total": 0, "pending": 0, "reviewed": 0,
                                    "failed": 0, "skipped": 0, "reused": 0},
                            created_at=now_iso(), updated_at=now_iso())
        session.add(batch)
        session.flush()
        return batch
    batch = ScriptBatch(id=_new_id("bat"), library_key=key, status="open",
                        model=requested_model, rubric_version="script-review-v1",
                        schema_version=intellect.REVIEW_SCHEMA,
                        selection={"scope": scope, "force": bool(force),
                                   "status_filter": status_filter,
                                   "requested": len(script_ids or []) if scope == "ids" else None},
                        counts={}, created_at=now_iso(), updated_at=now_iso())
    session.add(batch)
    session.flush()
    for record in records:
        session.add(ScriptBatchItem(batch_id=batch.id, script_id=record.id,
                                   status="pending", updated_at=now_iso()))
    session.flush()
    _refresh_counts(session, batch)
    return batch


def _refresh_counts(session: Session, batch: ScriptBatch) -> dict[str, int]:
    items = session.scalars(select(ScriptBatchItem).where(
        ScriptBatchItem.batch_id == batch.id)).all()
    counts = {"total": len(items), "pending": 0, "reviewed": 0, "failed": 0,
              "skipped": 0, "reused": 0}
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
        if item.reused:
            counts["reused"] += 1
    batch.counts = counts
    batch.updated_at = now_iso()
    session.flush()
    return counts


def batch_read(session: Session, batch: ScriptBatch) -> dict[str, Any]:
    items = session.scalars(select(ScriptBatchItem).where(
        ScriptBatchItem.batch_id == batch.batch_id if hasattr(batch, "batch_id") else ScriptBatchItem.batch_id == batch.id)).all()
    rows = []
    for item in items:
        record = session.get(ScriptRecord, item.script_id)
        rows.append({"script_id": item.script_id,
                     "relpath": record.current_relpath if record else None,
                     "title": record.title if record else None,
                     "status": item.status, "review_id": item.review_id,
                     "reused": bool(item.reused), "attempts": item.attempts,
                     "error": item.error})
    rows.sort(key=lambda row: (row["relpath"] or ""))
    return {"id": batch.id, "library_key": batch.library_key, "status": batch.status,
            "model": batch.model, "rubric_version": batch.rubric_version,
            "schema_version": batch.schema_version, "selection": dict(batch.selection or {}),
            "counts": dict(batch.counts or {}), "error": batch.error,
            "items": rows, "created_at": batch.created_at, "updated_at": batch.updated_at}


def get_batch(session: Session, batch_id: str) -> ScriptBatch:
    batch = session.get(ScriptBatch, batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    return batch


async def step_batch(session: Session, batch_id: str, *, limit: int = DEFAULT_STEP_LIMIT) -> dict[str, Any]:
    """Review up to `limit` pending items sequentially. Bounded per call."""
    batch = get_batch(session, batch_id)
    if batch.status in TERMINAL_BATCH:
        raise ValidationProblem(f"Batch is {batch.status}; start a new batch to review more.")
    limit = max(1, min(int(limit or DEFAULT_STEP_LIMIT), MAX_STEP_LIMIT))
    batch.status = "in_progress"
    batch.updated_at = now_iso()
    session.flush()
    key = batch.library_key
    effective_model, _route = _resolve_batch_model(session, batch.model)
    pending = session.scalars(select(ScriptBatchItem).where(
        ScriptBatchItem.batch_id == batch.id,
        ScriptBatchItem.status == "pending").limit(limit)).all()
    force = bool((batch.selection or {}).get("force"))
    for item in pending:
        record = session.get(ScriptRecord, item.script_id)
        if record is None or record.missing or record.library_key not in ("", key):
            item.status = "skipped"
            item.error = "Script record is missing or unavailable."
            item.updated_at = now_iso()
            continue
        if not force:
            current = _latest_current_review(session, record)
            if current is not None and (not batch.model or current.model == effective_model):
                item.status = "reviewed"
                item.review_id = current.id
                item.reused = True
                item.attempts = int(item.attempts or 0) + 1
                item.error = None
                item.updated_at = now_iso()
                continue
        item.attempts = int(item.attempts or 0) + 1
        try:
            review = await intellect.run_review(session, record.id, model=batch.model)
        except Exception as exc:  # per-item failure; the batch survives
            item.status = "failed"
            item.error = f"{exc.__class__.__name__}: {str(exc)[:500]}"
            item.updated_at = now_iso()
            logger.info("Batch %s: script %s failed (%s)", batch.id, record.id, item.error)
            continue
        item.status = "reviewed"
        item.review_id = review["id"]
        item.reused = False
        item.error = None
        item.updated_at = now_iso()
    counts = _refresh_counts(session, batch)
    if counts["pending"] == 0:
        batch.status = "complete"
        batch.updated_at = now_iso()
        session.flush()
    return batch_read(session, batch)


def pause_batch(session: Session, batch_id: str) -> dict[str, Any]:
    batch = get_batch(session, batch_id)
    if batch.status in TERMINAL_BATCH:
        raise ValidationProblem(f"Batch is {batch.status}.")
    batch.status = "paused"
    batch.updated_at = now_iso()
    session.flush()
    return batch_read(session, batch)


def cancel_batch(session: Session, batch_id: str) -> dict[str, Any]:
    batch = get_batch(session, batch_id)
    if batch.status in TERMINAL_BATCH:
        raise ValidationProblem(f"Batch is already {batch.status}.")
    batch.status = "cancelled"
    batch.updated_at = now_iso()
    session.flush()
    return batch_read(session, batch)


def retry_batch(session: Session, batch_id: str) -> dict[str, Any]:
    """Reset failed items to pending so the next step retries only failures."""
    batch = get_batch(session, batch_id)
    if batch.status in ("complete", "cancelled"):
        raise ValidationProblem(f"Batch is {batch.status}; start a new batch instead.")
    reset = 0
    for item in session.scalars(select(ScriptBatchItem).where(
            ScriptBatchItem.batch_id == batch.id,
            ScriptBatchItem.status == "failed")).all():
        item.status = "pending"
        item.error = None
        item.updated_at = now_iso()
        reset += 1
    batch.status = "in_progress" if batch.status == "paused" else batch.status
    if batch.status == "open":
        batch.status = "in_progress"
    batch.updated_at = now_iso()
    session.flush()
    _refresh_counts(session, batch)
    return {**batch_read(session, batch), "reset": reset}


def list_batches(session: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    key = _current_library_key(session)
    rows = session.scalars(select(ScriptBatch).where(
        ScriptBatch.library_key == key).order_by(
            ScriptBatch.created_at.desc()).limit(min(max(limit, 1), 100))).all()
    return [batch_read(session, row) for row in rows]
