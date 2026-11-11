"""Script registry (MC-SCRIPTS-02 Phase B, MC-SCRIPTS-03 Phase C).

Stable identity lives in ``script_records`` in the existing SQLite database,
scoped to a library (the configured root). Filenames are observations, never
identity. New files start at ``discovered`` and only explicit user action
moves them to ``completed`` with a durable timestamp. File dates are never
manufactured into completion evidence. Read-only toward the source tree.
No model calls anywhere in this module.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.core.paths import is_within, normalize_absolute_path
from mission_control.models import CultivationItem, CultivationMembership, Setting
from mission_control.models import ScriptEvent, ScriptLink, ScriptRecord
from mission_control.persistence.db import now_iso
from mission_control.persistence.seed import DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

SCRIPT_STATUSES = ("discovered", "draft", "in_review", "ready", "completed")
SCRIPT_NUMBER_RE = re.compile(r"^Script(\d+)", re.IGNORECASE)
DEFAULT_ROOT = r"C:\script"
DEFAULT_EXTENSIONS = [".md"]
DUBLIN_TZ = "Europe/Dublin"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def library_key_for_root(root_raw: str) -> str:
    return normalize_absolute_path(root_raw, field="scripts.root")


def validate_scripts_patch(patch: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    if "root" in patch:
        raw = patch["root"]
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValidationProblem("scripts.root must be a non-empty absolute path")
        if not isinstance(raw, str):
            raise ValidationProblem("scripts.root must be a string")
        cleaned["root"] = normalize_absolute_path(raw, field="scripts.root")[:1024]
    if "extensions" in patch:
        values = patch["extensions"]
        if not isinstance(values, list) or not values:
            raise ValidationProblem("scripts.extensions must be a non-empty list")
        seen: list[str] = []
        for item in values[:10]:
            if not isinstance(item, str):
                raise ValidationProblem("scripts.extensions must be strings")
            text = item.strip().lower()
            if not text.startswith(".") or len(text) > 12:
                raise ValidationProblem("scripts.extensions must look like '.md'")
            if text not in seen:
                seen.append(text)
        cleaned["extensions"] = seen
    unknown = set(patch) - {"root", "extensions"}
    if unknown:
        raise ValidationProblem(f"Unknown scripts settings: {', '.join(sorted(unknown))}")
    return cleaned


def get_scripts_config(session: Session) -> dict[str, Any]:
    setting = session.get(Setting, "scripts")
    if setting and isinstance(setting.value, dict):
        root = str(setting.value.get("root") or DEFAULT_ROOT)
        extensions = setting.value.get("extensions") or list(DEFAULT_EXTENSIONS)
    else:
        defaults = dict(DEFAULT_SETTINGS.get("scripts", {}))
        root = str(defaults.get("root") or DEFAULT_ROOT)
        extensions = list(defaults.get("extensions") or DEFAULT_EXTENSIONS)
    try:
        library_key = library_key_for_root(root)
    except ValidationProblem:
        library_key = root
    return {"root": root, "extensions": [str(item).lower() for item in extensions],
            "library_key": library_key}


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    import stat as _stat

    if _stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _safe_join(root: Path, relpath: str) -> Path:
    if not relpath or relpath.startswith(("/", "\\")) or ".." in Path(relpath).parts:
        raise ValidationProblem("Script path must stay inside the configured root")
    candidate = (root / relpath).resolve(strict=False)
    if not is_within(candidate, root.resolve(strict=False)):
        raise ValidationProblem("Script path must stay inside the configured root")
    if _is_reparse_point(candidate):
        raise ValidationProblem("Refusing to follow a symlink or reparse point")
    return candidate


def _parse_number(stem: str) -> int | None:
    match = SCRIPT_NUMBER_RE.match(stem or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _prettify(stem: str) -> str:
    return (stem.replace("_", " ").strip() or stem)[:300]


def _sha256_file(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    try:
        size = 0
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise ValidationProblem(f"Script is unreadable: {exc.__class__.__name__}") from None
    try:
        info = path.stat()
        mtime_ns, file_size = info.st_mtime_ns, info.st_size
    except OSError:
        mtime_ns, file_size = 0, size
    return digest.hexdigest(), file_size, mtime_ns


def _record_event(session: Session, script_id: str, event_type: str, *,
                  from_value: str | None = None, to_value: str | None = None,
                  note: str = "") -> None:
    session.add(ScriptEvent(
        id=_new_id("sev"), script_id=script_id, event_type=event_type,
        from_value=from_value, to_value=to_value, note=note[:2000],
        created_at=now_iso()))
    session.flush()


def _status_of(record: ScriptRecord) -> str:
    return str(record.status or "discovered")


def get_record(session: Session, script_id: str) -> ScriptRecord:
    record = session.get(ScriptRecord, script_id)
    if record is None:
        raise NotFound("Script not found")
    return record


def describe_root(root_raw: str) -> dict[str, Any]:
    try:
        normalized = normalize_absolute_path(root_raw, field="scripts.root")
    except ValidationProblem as exc:
        return {"root": root_raw, "status": "invalid", "error": exc.message,
                "exists": False, "is_dir": False, "readable": False}
    path = Path(normalized)
    exists = path.exists()
    is_dir = path.is_dir() if exists else False
    readable = False
    writable = False
    if is_dir:
        try:
            readable = os.access(str(path), os.R_OK) and path.stat() is not None
        except OSError:
            readable = False
        try:
            writable = bool(os.access(str(path), os.W_OK))
        except OSError:
            writable = False
    if not exists:
        return {"root": normalized, "status": "unavailable", "error": "Directory does not exist",
                "exists": False, "is_dir": False, "readable": False, "writable": False}
    if not is_dir:
        return {"root": normalized, "status": "unavailable", "error": "Path is not a directory",
                "exists": True, "is_dir": False, "readable": False, "writable": False}
    if not readable:
        return {"root": normalized, "status": "unavailable", "error": "Directory is not readable",
                "exists": True, "is_dir": True, "readable": False, "writable": bool(writable)}
    return {"root": normalized, "status": "accessible", "error": None,
            "exists": True, "is_dir": True, "readable": True, "writable": bool(writable)}


def _last_status(session: Session) -> dict[str, Any] | None:
    setting = session.get(Setting, "scripts_sync")
    if setting and isinstance(setting.value, dict):
        return dict(setting.value)
    return None


def _save_status(session: Session, payload: dict[str, Any]) -> None:
    setting = session.get(Setting, "scripts_sync")
    if setting is None:
        session.add(Setting(key="scripts_sync", value=payload, updated_at=now_iso()))
    else:
        setting.value = payload
        setting.updated_at = now_iso()
    session.flush()


# --------------------------------------------------- Dublin week helpers

def dublin_week_bounds(ref: datetime | None = None) -> dict[str, str]:
    tz = ZoneInfo(DUBLIN_TZ)
    now = ref.astimezone(tz) if ref is not None else datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    end = start + timedelta(days=7) - timedelta(microseconds=1)
    label = f"Week of {start.date().isoformat()} (Mon–Sun, Europe/Dublin)"
    return {"week_start": start.isoformat(), "week_end": end.isoformat(),
            "week_start_date": start.date().isoformat(),
            "week_end_date": end.date().isoformat(), "label": label,
            "timezone": DUBLIN_TZ}


def _in_current_week(stamp_iso: str, *, now: datetime | None = None) -> bool:
    try:
        stamp = datetime.fromisoformat(str(stamp_iso).replace("Z", "+00:00"))
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ZoneInfo("UTC"))
    bounds = dublin_week_bounds(now)
    try:
        start = datetime.fromisoformat(bounds["week_start"])
        end = datetime.fromisoformat(bounds["week_end"])
    except ValueError:
        return False
    return start <= stamp.astimezone(start.tzinfo) <= end


def _maybe_record_weekly(session: Session, record: ScriptRecord, completed_at: str,
                         *, force: bool = True) -> bool:
    """Record one weekly unit for a genuine completion. Deduplicated per script per week."""
    from mission_control.models import CultivationGoal, CultivationMeasurement

    goal = session.get(CultivationGoal, "weekly_script")
    if goal is None or goal.measurement_type != "recurring":
        return False
    if not _in_current_week(completed_at):
        return False
    bounds = dublin_week_bounds()
    marker = f"script-registry:{record.id}"
    existing = session.scalars(select(CultivationMeasurement).where(
        CultivationMeasurement.goal_id == goal.id,
        CultivationMeasurement.source == marker,
        CultivationMeasurement.observed_at >= bounds["week_start"],
        CultivationMeasurement.observed_at <= bounds["week_end"]).limit(1)).first()
    if existing is not None:
        return False
    if not force:
        return False
    session.add(CultivationMeasurement(
        id=_new_id("msr"), goal_id=goal.id, value=1.0, observed_at=completed_at,
        note=f"Script completed: {record.current_relpath} ({record.id}).",
        source=marker, created_at=now_iso()))
    session.flush()
    return True


# --------------------------------------------------- sync

def sync_scripts(session: Session, *, root_override: str | None = None) -> dict[str, Any]:
    from mission_control.cultivation.sources import scan_numbered_files

    config = get_scripts_config(session)
    root_raw = root_override or config["root"]
    info = describe_root(root_raw)
    previous = _last_status(session)
    if info["status"] != "accessible":
        kept = dict(previous or {})
        result = {"status": "stale" if kept.get("fingerprint") else "unavailable",
                  "root": info["root"], "error": info.get("error"),
                  "stale": True, "preserved": bool(kept.get("fingerprint")),
                  "observed": kept.get("observed", {}),
                  "counts": kept.get("counts", {}),
                  "last_sync_at": kept.get("last_sync_at")}
        last = dict(kept)
        last.update({"last_status": result["status"], "last_error": result["error"],
                     "updated_at": now_iso(), "root": info["root"]})
        _save_status(session, last)
        return result
    root = Path(info["root"])
    library_key = library_key_for_root(info["root"])
    scan = scan_numbered_files(str(root))
    if scan.candidates == 0:
        observed = {"discovered": 0, "total": 0, "candidates": 0, "excluded": 0,
                    "fingerprint": scan.fingerprint, "empty": True}
        return _persist_sync(session, root, library_key, scan, {}, observed, empty=True)
    observations: dict[str, dict[str, Any]] = {}
    for post in scan.posts:
        try:
            candidate = _safe_join(root, post.relpath)
        except ValidationProblem:
            continue
        sha, size, mtime_ns = _sha256_file(candidate)
        number = _parse_number(Path(post.relpath).stem)
        observations[post.relpath] = {
            "sha": sha, "size": size, "mtime_ns": mtime_ns,
            "number": number, "title": _prettify(Path(post.relpath).stem),
        }
    return _persist_sync(session, root, library_key, scan, observations, None, empty=False)


def _persist_sync(session: Session, root: Path, library_key: str, scan: Any,
                  observations: Any, observed_override: dict[str, Any] | None,
                  *, empty: bool) -> dict[str, Any]:
    if empty:
        counts = _counts(session, library_key)
        payload = {"status": "ok_empty", "root": str(root), "library_key": library_key,
                   "error": None, "stale": False, "empty": True,
                   "observed": observed_override or {}, "counts": counts,
                   "last_sync_at": now_iso(), "fingerprint": scan.fingerprint,
                   "new": [], "renamed": [], "missing": [], "changed": [],
                   "duplicate_numbers": {}, "duplicate_content": {}}
        _save_status(session, {"fingerprint": scan.fingerprint, "observed": payload["observed"],
                               "counts": counts, "last_sync_at": payload["last_sync_at"],
                               "last_status": "ok_empty", "last_error": None,
                               "root": str(root), "library_key": library_key,
                               "updated_at": now_iso()})
        return payload
    assert isinstance(observations, dict)
    # Adopt Phase B records with an empty key into the current library.
    for record in session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == "")).all():
        conflict = session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == library_key,
            ScriptRecord.current_relpath == record.current_relpath).limit(1)).first()
        if conflict is None:
            record.library_key = library_key
            record.updated_at = now_iso()
    session.flush()
    # Records from other libraries are invisible to this sync.
    by_path: dict[str, ScriptRecord] = {}
    for record in session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == library_key)).all():
        by_path.setdefault(str(record.current_relpath), record)
    seen: set[str] = set()
    new_ids: list[str] = []
    renamed: list[dict[str, str]] = []
    changed: list[str] = []
    unmatched_new: dict[str, dict[str, Any]] = {}
    for relpath, obs in sorted(observations.items()):
        record = by_path.get(relpath)
        if record is None:
            unmatched_new[relpath] = obs
            continue
        seen.add(record.id)
        record.missing = False
        record.last_seen_at = now_iso()
        if record.content_sha256 != obs["sha"]:
            old = (record.content_sha256 or "")[:12]
            record.content_sha256 = obs["sha"]
            record.file_size = int(obs["size"])
            record.mtime_ns = int(obs["mtime_ns"])
            changed.append(record.id)
            _record_event(session, record.id, "content_changed", from_value=old,
                          to_value=obs["sha"][:12], note=f"Content changed: {relpath}. Status preserved.")
        else:
            record.file_size = int(obs["size"])
            record.mtime_ns = int(obs["mtime_ns"])
        record.script_number = obs["number"]
        if obs["title"] and record.title != obs["title"]:
            record.title = obs["title"]
        record.updated_at = now_iso()
    missing_records = [row for rel, row in by_path.items() if row.id not in seen]
    hash_to_missing: dict[str, list[ScriptRecord]] = {}
    for row in missing_records:
        if row.content_sha256:
            hash_to_missing.setdefault(row.content_sha256, []).append(row)
    hash_to_new: dict[str, list[str]] = {}
    for relpath, obs in unmatched_new.items():
        hash_to_new.setdefault(obs["sha"], []).append(relpath)
    db_hash_counts: dict[str, int] = {}
    for row in by_path.values():
        if row.content_sha256:
            db_hash_counts[row.content_sha256] = db_hash_counts.get(row.content_sha256, 0) + 1
    consumed_new: set[str] = set()
    for sha, rows in hash_to_missing.items():
        newcomers = hash_to_new.get(sha, [])
        if len(rows) == 1 and len(newcomers) == 1 and db_hash_counts.get(sha, 0) == 1:
            record = rows[0]
            relpath = newcomers[0]
            obs = unmatched_new[relpath]
            old_rel = str(record.current_relpath)
            record.current_relpath = relpath
            record.missing = False
            record.last_seen_at = now_iso()
            record.script_number = obs["number"]
            record.title = obs["title"] or record.title
            record.file_size = int(obs["size"])
            record.mtime_ns = int(obs["mtime_ns"])
            record.updated_at = now_iso()
            seen.add(record.id)
            consumed_new.add(relpath)
            renamed.append({"id": record.id, "from": old_rel, "to": relpath})
            _record_event(session, record.id, "renamed", from_value=old_rel,
                          to_value=relpath, note="Rename reconciled by unique content match; identity preserved.")
    for relpath in sorted(unmatched_new):
        if relpath in consumed_new:
            continue
        obs = unmatched_new[relpath]
        record = ScriptRecord(
            id=_new_id("scr"), library_key=library_key,
            current_relpath=relpath, original_relpath=relpath,
            script_number=obs["number"], title=obs["title"] or relpath,
            content_sha256=obs["sha"], file_size=int(obs["size"]), mtime_ns=int(obs["mtime_ns"]),
            status="discovered", archived=False, missing=False,
            discovered_at=now_iso(), last_seen_at=now_iso(),
            created_at=now_iso(), updated_at=now_iso())
        session.add(record)
        session.flush()
        seen.add(record.id)
        new_ids.append(record.id)
        _record_event(session, record.id, "discovered", to_value="discovered",
                      note=f"Discovered: {relpath}. File existence is not completion.")
    missing_ids: list[str] = []
    for row in missing_records:
        if row.id in seen:
            continue
        if not row.missing:
            row.missing = True
            row.updated_at = now_iso()
            _record_event(session, row.id, "missing", note=f"Missing from scan: {row.current_relpath}. History kept.")
        missing_ids.append(row.id)
    session.flush()
    counts = _counts(session, library_key)
    duplicate_numbers = _duplicate_numbers(session, library_key)
    duplicate_content = _duplicate_content(session, library_key)
    observed = {"discovered": counts["total"], "total": counts["total"],
                "completed": counts["completed"],
                "candidates": scan.candidates, "excluded": scan.excluded,
                "fingerprint": scan.fingerprint}
    payload = {"status": "ok", "root": str(root), "library_key": library_key,
               "error": None, "stale": False, "empty": False, "observed": observed,
               "counts": counts, "last_sync_at": now_iso(), "fingerprint": scan.fingerprint,
               "new": new_ids, "renamed": renamed, "missing": missing_ids,
               "changed": changed, "duplicate_numbers": duplicate_numbers,
               "duplicate_content": duplicate_content}
    _save_status(session, {"fingerprint": scan.fingerprint, "observed": observed,
                           "counts": counts, "last_sync_at": payload["last_sync_at"],
                           "last_status": "ok", "last_error": None,
                           "root": str(root), "library_key": library_key,
                           "updated_at": now_iso()})
    return payload


def _counts(session: Session, library_key: str | None = None) -> dict[str, Any]:
    key = library_key if library_key is not None else _current_library_key(session)
    query = select(ScriptRecord).where(ScriptRecord.library_key == key)
    rows = session.scalars(query).all()
    # Include legacy unscoped rows only when the current library has none yet
    # (first sync after the Phase C migration).
    if not rows:
        rows = session.scalars(select(ScriptRecord).where(ScriptRecord.library_key == "")).all()
    by_status: dict[str, int] = {}
    completed = archived = missing = 0
    ready = needs_review = 0
    for row in rows:
        status_key = _status_of(row)
        by_status[status_key] = by_status.get(status_key, 0) + 1
        # Archived completed scripts still count: archival is organisation,
        # not un-achievement. Missing files leave the qualifying set but keep
        # history.
        if status_key == "completed" and not row.missing:
            completed += 1
        if status_key == "ready" and not row.missing and not row.archived:
            ready += 1
        if status_key in ("draft", "in_review") and not row.missing and not row.archived:
            needs_review += 1
        if row.archived:
            archived += 1
        if row.missing:
            missing += 1
    present = sum(1 for row in rows if not row.missing)
    return {"total": len(rows), "by_status": by_status, "completed": completed,
            "ready": ready, "needs_review": needs_review, "present": present,
            "archived": int(archived), "missing": int(missing)}


def _current_library_key(session: Session) -> str:
    try:
        return library_key_for_root(get_scripts_config(session)["root"])
    except ValidationProblem:
        return ""


def _duplicate_numbers(session: Session, library_key: str | None = None) -> dict[str, list[str]]:
    key = library_key if library_key is not None else _current_library_key(session)
    groups: dict[Any, list[str]] = {}
    for row in session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == key, ScriptRecord.missing.is_(False))).all():
        if row.script_number is None:
            continue
        groups.setdefault(int(row.script_number), []).append(row.id)
    return {str(number): sorted(ids) for number, ids in groups.items() if len(ids) > 1}


def _duplicate_content(session: Session, library_key: str | None = None) -> dict[str, list[str]]:
    key = library_key if library_key is not None else _current_library_key(session)
    groups: dict[str, list[str]] = {}
    for row in session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == key, ScriptRecord.missing.is_(False))).all():
        if not row.content_sha256:
            continue
        groups.setdefault(row.content_sha256[:16], []).append(row.id)
    return {digest: sorted(ids) for digest, ids in groups.items() if len(ids) > 1}


def list_records(session: Session, *, status: str | None = None,
                 search: str | None = None, include_archived: bool = True,
                 include_missing: bool = True, completed: bool | None = None,
                 duplicate: bool | None = None,
                 limit: int = 200, offset: int = 0) -> tuple[list[ScriptRecord], int]:
    key = _current_library_key(session)
    query = select(ScriptRecord).where(ScriptRecord.library_key == key).order_by(
        ScriptRecord.script_number, ScriptRecord.current_relpath)
    if status:
        if status not in SCRIPT_STATUSES:
            raise ValidationProblem(f"Unknown status: {status}")
        query = query.where(ScriptRecord.status == status)
    if completed is True:
        query = query.where(ScriptRecord.status == "completed")
    elif completed is False:
        query = query.where(ScriptRecord.status != "completed")
    if not include_archived:
        query = query.where(ScriptRecord.archived.is_(False))
    if not include_missing:
        query = query.where(ScriptRecord.missing.is_(False))
    if search:
        needle = f"%{search}%"
        query = query.where(ScriptRecord.title.ilike(needle) | ScriptRecord.current_relpath.ilike(needle))
    rows = list(session.scalars(query).all())
    if duplicate:
        dup_ids = set()
        for ids in list(_duplicate_numbers(session, key).values()):
            dup_ids.update(ids)
        for ids in list(_duplicate_content(session, key).values()):
            dup_ids.update(ids)
        rows = [row for row in rows if row.id in dup_ids]
    total = len(rows)
    sliced = rows[max(offset, 0):max(offset, 0) + min(max(limit, 1), 500)]
    return sliced, int(total)


def record_read(session: Session, record: ScriptRecord) -> dict[str, Any]:
    from mission_control.scripts import intelligence as _intel

    events = session.scalars(select(ScriptEvent).where(
        ScriptEvent.script_id == record.id).order_by(ScriptEvent.created_at.desc()).limit(50)).all()
    links = session.scalars(select(ScriptLink).where(
        (ScriptLink.source_id == record.id) | (ScriptLink.target_id == record.id)).limit(50)).all()
    key = _current_library_key(session)
    dup_numbers = _duplicate_numbers(session, key)
    dup_content = _duplicate_content(session, key)
    from mission_control.models import ScriptTag
    tag_rows = session.scalars(select(ScriptTag).where(
        ScriptTag.script_id == record.id)).all()
    return {
        "id": record.id, "library_key": record.library_key or key,
        "current_relpath": record.current_relpath,
        "original_relpath": record.original_relpath, "script_number": record.script_number,
        "title": record.title, "content_sha256": record.content_sha256,
        "file_size": record.file_size, "mtime_ns": record.mtime_ns,
        "status": _status_of(record), "archived": bool(record.archived),
        "missing": bool(record.missing), "discovered_at": record.discovered_at,
        "last_seen_at": record.last_seen_at, "completed_at": record.completed_at,
        "review_status": record.review_status, "last_review_at": record.last_review_at,
        "legacy_item_id": record.legacy_item_id,
        "created_at": record.created_at, "updated_at": record.updated_at,
        "usage_count": int(record.usage_count or 0),
        "personal_rating": record.personal_rating,
        "personal_target": record.personal_target or "",
        "personal_effect": record.personal_effect or "",
        "last_used_at": record.last_used_at,
        "latest_review": _intel.latest_review_summary(session, record),
        "duplicate_number_group": next(
            (ids for number, ids in dup_numbers.items() if record.id in ids), None),
        "duplicate_content_group": next(
            (ids for digest, ids in dup_content.items() if record.id in ids), None),
        "tags": [{"tag": link.tag, "origin": link.origin} for link in tag_rows],
        "events": [{"id": item.id, "event_type": item.event_type, "from_value": item.from_value,
                    "to_value": item.to_value, "note": item.note, "created_at": item.created_at}
                   for item in events],
        "links": [{"source_id": item.source_id, "target_id": item.target_id, "kind": item.kind,
                   "confirmed": bool(item.confirmed), "note": item.note,
                   "evidence": item.evidence or "", "confidence": item.confidence or "unconfirmed",
                   "updated_at": item.updated_at} for item in links],
    }


def status_read(session: Session) -> dict[str, Any]:
    config = get_scripts_config(session)
    info = describe_root(config["root"])
    saved = _last_status(session) or {}
    key = config["library_key"]
    fresh_counts = _counts(session, key)
    # When the directory is unavailable, never substitute zero: show the last
    # known inventory with a stale status.
    if saved.get("last_status") in ("stale", "unavailable") and isinstance(saved.get("counts"), dict):
        counts = dict(saved["counts"])
        stale_view = True
    else:
        counts = fresh_counts
        stale_view = False
    bounds = dublin_week_bounds()
    libraries = sorted({str(row.library_key or "") for row in
                        session.scalars(select(ScriptRecord)).all() if str(row.library_key or "")})
    # Duplicates follow the displayed inventory: the preserved library when
    # stale, otherwise the current library.
    dup_key = str(saved.get("library_key", "") or key) if stale_view else key
    return {
        "root": info["root"], "library_key": key, "configured": True,
        "exists": info.get("exists", False), "is_dir": info.get("is_dir", False),
        "readable": info.get("readable", False), "writable": info.get("writable", False),
        "status": saved.get("last_status", "never_synced"),
        "last_sync_at": saved.get("last_sync_at"),
        "last_error": saved.get("last_error"),
        "fingerprint": saved.get("fingerprint", ""),
        "observed": dict(saved.get("observed", {}) or {}),
        "counts": counts,
        "duplicate_numbers": _duplicate_numbers(session, dup_key),
        "duplicate_content": _duplicate_content(session, dup_key),
        "extensions": config["extensions"],
        "week": bounds,
        "libraries": libraries,
    }


def set_status(session: Session, script_id: str, status: str, *,
               note: str = "", completed_at: str | None = None,
               record_weekly: bool = True) -> ScriptRecord:
    if status not in SCRIPT_STATUSES:
        raise ValidationProblem(f"Unknown status: {status}")
    record = get_record(session, script_id)
    previous = _status_of(record)
    if completed_at is not None and status != "completed":
        raise ValidationProblem("completed_at is only valid when marking completed")
    stamp: str | None = None
    if status == "completed":
        if completed_at:
            try:
                datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            except ValueError:
                raise ValidationProblem("completed_at must be an ISO-8601 timestamp") from None
            stamp = str(completed_at)
        else:
            stamp = now_iso()
    if previous == status and (status != "completed" or record.completed_at):
        return record
    record.status = status
    if status == "completed":
        record.completed_at = stamp
    elif previous == "completed":
        record.completed_at = None
    record.updated_at = now_iso()
    session.flush()
    _record_event(session, record.id, "completed" if status == "completed" else (
        "reopened" if previous == "completed" else "status_changed"),
        from_value=previous, to_value=status,
        note=note or f"Status {previous} -> {status} by explicit action.")
    if status == "completed" and stamp:
        _maybe_record_weekly(session, record, stamp, force=record_weekly)
    return record


def bulk_set_status(session: Session, script_ids: list[str], status: str, *,
                    note: str = "", completed_at: str | None = None,
                    as_historical: bool = False) -> dict[str, Any]:
    if status not in SCRIPT_STATUSES:
        raise ValidationProblem(f"Unknown status: {status}")
    if not isinstance(script_ids, list) or not script_ids:
        raise ValidationProblem("script_ids must be a non-empty list")
    if len(script_ids) > 200:
        raise ValidationProblem("Bulk classification is limited to 200 scripts at once")
    if completed_at is not None and status != "completed":
        raise ValidationProblem("completed_at is only valid when marking completed")
    updated: list[str] = []
    skipped: list[str] = []
    for script_id in script_ids:
        try:
            record = get_record(session, str(script_id))
        except NotFound:
            skipped.append(str(script_id))
            continue
        # Historical baseline: classify now but never mint a current-week unit.
        record_weekly = not (as_historical and status == "completed")
        stamp = completed_at
        if status == "completed" and as_historical and not completed_at:
            stamp = None  # set_status mints now(); weekly suppressed via record_weekly=False
        set_status(session, record.id, status, note=note or (
            "Historical baseline; original date unknown, classified now." if as_historical
            else ""), completed_at=stamp, record_weekly=record_weekly)
        # When explicitly historical with unknown date, annotate the stamp.
        if status == "completed" and as_historical and not completed_at:
            _record_event(session, record.id, "historical_baseline",
                          note="Classified as historical baseline; completion date unknown, not counted toward the current week.")
        updated.append(record.id)
    return {"updated": updated, "skipped": skipped, "count": len(updated)}


def set_archived(session: Session, script_id: str, *, archived: bool, note: str = "") -> ScriptRecord:
    record = get_record(session, script_id)
    record.archived = bool(archived)
    record.updated_at = now_iso()
    session.flush()
    _record_event(session, record.id, "archived" if archived else "unarchived",
                  note=note or ("Archived." if archived else "Restored from archive."))
    return record


def read_content(session: Session, script_id: str, *, max_chars: int = 200_000) -> dict[str, Any]:
    record = get_record(session, script_id)
    library_root = str(record.library_key or get_scripts_config(session)["root"])
    root = Path(describe_root(library_root)["root"])
    target = _safe_join(root, str(record.current_relpath))
    if not target.is_file():
        raise NotFound("Script file is missing from the source tree")
    try:
        text = target.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValidationProblem(f"Script is unreadable: {exc.__class__.__name__}") from None
    sha, _, _ = _sha256_file(target)
    return {"id": record.id, "relpath": record.current_relpath, "title": record.title,
            "content": text[:max_chars], "truncated": len(text) > max_chars,
            "content_sha256": sha, "stored_sha256": record.content_sha256,
            "matches_stored": sha == record.content_sha256}


def migrate_library(session: Session, *, source_key: str, dest_key: str,
                    dry_run: bool = True) -> dict[str, Any]:
    try:
        source = library_key_for_root(source_key)
        dest = library_key_for_root(dest_key)
    except ValidationProblem as exc:
        raise ValidationProblem(exc.message) from None
    if source == dest:
        raise ValidationProblem("Source and destination libraries must differ")
    moving = session.scalars(select(ScriptRecord).where(
        ScriptRecord.library_key == source)).all()
    conflicts: list[str] = []
    for record in moving:
        clash = session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == dest,
            ScriptRecord.current_relpath == record.current_relpath).limit(1)).first()
        if clash is not None:
            conflicts.append(record.current_relpath)
    if dry_run or conflicts:
        return {"dry_run": True, "source": source, "dest": dest,
                "would_move": len(moving), "conflicts": sorted(conflicts)}
    for record in moving:
        record.library_key = dest
        record.updated_at = now_iso()
        _record_event(session, record.id, "library_migrated",
                      from_value=source, to_value=dest,
                      note="Explicit authorised library migration; identity preserved.")
    session.flush()
    return {"dry_run": False, "source": source, "dest": dest,
            "moved": len(moving), "conflicts": []}


def migrate_legacy_items(session: Session) -> dict[str, int]:
    try:
        key = _current_library_key(session)
    except ValidationProblem:
        key = ""
    created = adopted_completed = 0
    items = session.scalars(select(CultivationItem).where(
        CultivationItem.source_application == "numbered_files")).all()
    for item in items:
        ref = str(item.source_ref or "")
        relpath = ref.split(":", 1)[1] if ":" in ref else None
        if not relpath:
            continue
        existing = session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == key,
            ScriptRecord.current_relpath == relpath).limit(1)).first()
        if existing is None:
            existing = session.scalars(select(ScriptRecord).where(
                ScriptRecord.library_key == "",
                ScriptRecord.current_relpath == relpath).limit(1)).first()
        if existing is not None:
            if existing.library_key == "":
                existing.library_key = key
            if existing.legacy_item_id is None:
                existing.legacy_item_id = item.id
                existing.updated_at = now_iso()
            continue
        memberships = session.scalars(select(CultivationMembership).where(
            CultivationMembership.item_id == item.id)).all()
        verified = False
        completed_at: str | None = None
        for membership in memberships:
            evidence = dict(membership.quality_evidence or {})
            if evidence.get("manual_hold") or evidence.get("qualified_by") == "user":
                verified = True
                completed_at = membership.completed_at
                break
        record = ScriptRecord(
            id=_new_id("scr"), library_key=key,
            current_relpath=relpath, original_relpath=relpath,
            script_number=_parse_number(Path(relpath).stem), title=item.title or relpath,
            content_sha256="", file_size=0, mtime_ns=0,
            status="completed" if verified else "discovered",
            archived=False, missing=False, discovered_at=now_iso(),
            last_seen_at=now_iso(), completed_at=completed_at,
            legacy_item_id=item.id, created_at=now_iso(), updated_at=now_iso())
        session.add(record)
        session.flush()
        _record_event(session, record.id, "legacy_migrated",
                      to_value=record.status,
                      note="Adopted path-derived item; auto-observed stays discovered.")
        created += 1
        if verified:
            adopted_completed += 1
    return {"created": created, "adopted_completed": adopted_completed}
