"""Script organisation (MC-SCRIPTS-04 Phase D).

Preview-first renumbering with stable identities. Files are presentation;
``scr-`` IDs are identity. No automatic merging or deletion. The real
collection is never renamed without an approved manifest bound to exact
source fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import ScriptLink, ScriptMigration, ScriptRecord, Setting
from mission_control.persistence.db import now_iso
from mission_control.scripts.service import (
    _current_library_key,
    _new_id,
    _prettify,
    _record_event,
    describe_root,
    get_scripts_config,
    library_key_for_root,
)

logger = logging.getLogger(__name__)

RELATIONSHIP_KINDS = ("exact_duplicate", "possible_duplicate", "revision", "alternate", "independent")
MERGE_KINDS = ("exact_duplicate", "revision", "alternate")
SCRIPT_REF_RE = re.compile(r"\bScript\s?(\d+)\b", re.IGNORECASE)
SUFFIX_RE = re.compile(r"^Script(\d+)(.*)$", re.IGNORECASE)
MAX_PREVIEW_ITEMS = 500


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _manifest_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(manifest).encode("utf-8")).hexdigest()


def _suffix_of(relpath: str) -> str:
    stem = Path(relpath).stem
    match = SUFFIX_RE.match(stem or "")
    if not match:
        return stem
    return (match.group(2) or "")


def _order_key(record: ScriptRecord) -> tuple[Any, ...]:
    number = record.script_number if record.script_number is not None else 10**9
    return (int(number), _suffix_of(str(record.current_relpath)).lower(), str(record.current_relpath).lower())


def _library_records(session: Session, library_key: str) -> list[ScriptRecord]:
    rows = list(session.scalars(select(ScriptRecord).where(
        ScriptRecord.library_key == library_key).order_by(
            ScriptRecord.script_number, ScriptRecord.current_relpath)).all())
    if not rows:
        rows = list(session.scalars(select(ScriptRecord).where(
            ScriptRecord.library_key == "").order_by(
                ScriptRecord.script_number, ScriptRecord.current_relpath)).all())
    return rows


def discover_relationships(session: Session) -> dict[str, Any]:
    """Propose version/duplicate relationships. Confirmed links are kept."""
    from mission_control.scripts.service import _counts

    key = _current_library_key(session)
    records = [row for row in _library_records(session, key) if not row.missing]
    # Remove previous auto proposals; confirmed judgements survive.
    auto = session.scalars(select(ScriptLink).where(
        ScriptLink.confirmed.is_(False), ScriptLink.note.like("auto:%"))).all()
    for link in auto:
        session.delete(link)
    session.flush()
    proposed = 0
    # Exact duplicates: identical content.
    sha_groups: dict[str, list[ScriptRecord]] = {}
    for row in records:
        if row.content_sha256:
            sha_groups.setdefault(row.content_sha256, []).append(row)
    for sha, group in sha_groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda row: row.id)
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                _upsert_link(session, first.id, second.id, "exact_duplicate", False,
                             note=f"auto: identical sha256 {sha[:16]}…",
                             evidence=f"identical sha256 {sha[:16]}…; sizes {[first.file_size, second.file_size]}",
                             confidence="high")
                proposed += 1
    # Same-number groups: alternate vs possible duplicate.
    number_groups: dict[int, list[ScriptRecord]] = {}
    for row in records:
        if row.script_number is not None:
            number_groups.setdefault(int(row.script_number), []).append(row)
    pair_kinds: dict[tuple[str, str], str] = {}
    for number, group in number_groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda row: row.id)
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                if first.content_sha256 and first.content_sha256 == second.content_sha256:
                    continue  # already an exact duplicate
                pair = tuple(sorted((first.id, second.id)))
                suffixes = (_suffix_of(first.current_relpath), _suffix_of(second.current_relpath))
                kind = "alternate" if any(suffixes) else "possible_duplicate"
                if pair in pair_kinds:
                    continue
                pair_kinds[pair] = kind
                evidence = (f"shared script number {number}; "
                            f"{first.current_relpath!r} vs {second.current_relpath!r}; "
                            f"{'different content' if first.content_sha256 != second.content_sha256 else 'unhashed'}")
                _upsert_link(session, pair[0], pair[1], kind, False,
                             note=f"auto: {evidence}",
                             evidence=evidence,
                             confidence="medium")
                proposed += 1
    session.flush()
    counts = _counts(session, key)
    return {"library_key": key, "proposed": proposed, "works": work_groups(session),
            "counts": counts}


def _upsert_link(session: Session, source_id: str, target_id: str, kind: str,
                 confirmed: bool, *, note: str = "", evidence: str = "",
                 confidence: str = "unconfirmed") -> ScriptLink:
    if kind not in RELATIONSHIP_KINDS:
        raise ValidationProblem(f"Unknown relationship kind: {kind}")
    ordered = sorted((source_id, target_id))
    link = session.get(ScriptLink, (ordered[0], ordered[1], kind))
    if link is None:
        link = ScriptLink(source_id=ordered[0], target_id=ordered[1], kind=kind,
                          confirmed=bool(confirmed), note=note[:2000],
                          evidence=evidence[:2000], confidence=confidence[:40],
                          updated_at=now_iso(), created_at=now_iso())
        session.add(link)
    else:
        if confirmed:
            link.confirmed = True
        if note:
            link.note = note[:2000]
        if evidence:
            link.evidence = evidence[:2000]
        if confidence:
            link.confidence = confidence[:40]
        link.updated_at = now_iso()
    session.flush()
    return link


def list_relationships(session: Session) -> list[dict[str, Any]]:
    key = _current_library_key(session)
    ids = {row.id for row in _library_records(session, key)}
    rows = session.scalars(select(ScriptLink).order_by(
        ScriptLink.confirmed, ScriptLink.kind, ScriptLink.source_id)).all()
    items = []
    for link in rows:
        if link.source_id not in ids and link.target_id not in ids:
            continue
        items.append({"source_id": link.source_id, "target_id": link.target_id,
                      "kind": link.kind, "confirmed": bool(link.confirmed),
                      "note": link.note, "evidence": link.evidence or "",
                      "confidence": link.confidence or "unconfirmed",
                      "updated_at": link.updated_at, "created_at": link.created_at})
    return items


def confirm_relationship(session: Session, source_id: str, target_id: str, kind: str, *,
                         confirmed: bool = True, note: str = "") -> dict[str, Any]:
    if kind not in RELATIONSHIP_KINDS:
        raise ValidationProblem(f"Unknown relationship kind: {kind}")
    if source_id == target_id:
        raise ValidationProblem("A script cannot relate to itself")
    if kind == "independent" and not confirmed:
        raise ValidationProblem("Marking scripts independent is a confirmed judgement")
    key = _current_library_key(session)
    first = session.get(ScriptRecord, source_id)
    second = session.get(ScriptRecord, target_id)
    if first is None or second is None:
        raise NotFound("Script not found")
    if first.library_key not in ("", key) or second.library_key not in ("", key):
        raise ValidationProblem("Both scripts must belong to the current library")
    link = _upsert_link(session, source_id, target_id, kind, confirmed,
                        note=note or f"{'Confirmed' if confirmed else 'Proposed'} {kind} by explicit review.",
                        evidence="", confidence="confirmed" if confirmed else "unconfirmed")
    _record_event(session, source_id, "relationship_confirmed" if confirmed else "relationship_proposed",
                  to_value=kind, note=f"{source_id[:12]}… ↔ {target_id[:12]}…: {kind}.")
    _record_event(session, target_id, "relationship_confirmed" if confirmed else "relationship_proposed",
                  to_value=kind, note=f"{source_id[:12]}… ↔ {target_id[:12]}…: {kind}.")
    return {"source_id": link.source_id, "target_id": link.target_id, "kind": link.kind,
            "confirmed": bool(link.confirmed), "note": link.note,
            "evidence": link.evidence, "confidence": link.confidence}


def work_groups(session: Session) -> dict[str, Any]:
    """Distinct works from confirmed merge-kind links; unconfirmed never merge."""
    key = _current_library_key(session)
    records = [row for row in _library_records(session, key) if not row.missing]
    parent = {row.id: row.id for row in records}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(first: str, second: str) -> None:
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parent[root_b] = root_a

    links = session.scalars(select(ScriptLink).where(ScriptLink.confirmed.is_(True))).all()
    ids = set(parent)
    for link in links:
        if link.kind in MERGE_KINDS and link.source_id in ids and link.target_id in ids:
            union(link.source_id, link.target_id)
    groups: dict[str, list[ScriptRecord]] = {}
    for row in records:
        groups.setdefault(find(row.id), []).append(row)
    works = []
    for root_id, members in groups.items():
        ordered = sorted(members, key=_order_key)
        canonical = ordered[0]
        works.append({"work_id": f"work-{hashlib.sha256(root_id.encode()).hexdigest()[:12]}",
                      "root_id": root_id, "member_ids": [row.id for row in ordered],
                      "members": [{"id": row.id, "relpath": row.current_relpath,
                                   "number": row.script_number, "status": row.status,
                                   "completed_at": row.completed_at, "archived": bool(row.archived)}
                                  for row in ordered],
                      "canonical_id": canonical.id, "canonical_number": canonical.script_number,
                      "size": len(ordered)})
    works.sort(key=lambda work: ((work["canonical_number"] if work["canonical_number"] is not None else 10**9),
                                 work["members"][0]["relpath"].lower()))
    for index, work in enumerate(works, start=1):
        work["work_number"] = index
    completed_files = sum(1 for row in records if row.status == "completed")
    completed_works = sum(1 for work in works if any(
        member["status"] == "completed" for member in work["members"]))
    return {"library_key": key, "works": works, "work_count": len(works),
            "file_count": len(records),
            "completed_files": completed_files, "completed_works": completed_works}


def plan_migration(session: Session) -> dict[str, Any]:
    """Read-only dry run. Never writes files, registry, or cultivation data."""
    from mission_control.scripts.service import _counts

    config = get_scripts_config(session)
    key = library_key_for_root(config["root"])
    info = describe_root(config["root"])
    if info["status"] != "accessible":
        raise ValidationProblem(info.get("error") or "Script directory unavailable")
    root = Path(info["root"])
    records = sorted([row for row in _library_records(session, key) if not row.missing],
                     key=_order_key)
    if not records:
        raise ValidationProblem("No present scripts to organise in this library")
    if len(records) > MAX_PREVIEW_ITEMS:
        raise ValidationProblem("Library too large for a single migration preview")
    width = max(3, len(str(len(records))))
    items = []
    references: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        proposed_name = f"Script{index:0{width}d}.md"
        parent = Path(str(record.current_relpath)).parent
        proposed = proposed_name if str(parent) in (".", "") else str(parent / proposed_name).replace("\\", "/")
        current_abs = root / str(record.current_relpath)
        try:
            with open(current_abs, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
        except OSError as exc:
            raise ValidationProblem(f"Cannot fingerprint {record.current_relpath}: {exc.__class__.__name__}") from None
        if digest != (record.content_sha256 or digest):
            raise ValidationProblem(f"Registry fingerprint is stale for {record.current_relpath}; sync first")
        matches = _scan_references(current_abs)
        for match in matches:
            references.append({"source_id": record.id, "source": str(record.current_relpath), **match})
        items.append({"id": record.id, "current": str(record.current_relpath),
                      "proposed": proposed, "current_number": record.script_number,
                      "proposed_number": index, "sha256": digest,
                      "status": record.status, "archived": bool(record.archived),
                      "completed_at": record.completed_at,
                      "work_hint": _work_hint(session, record.id)})
    # Collision warnings: destinations occupied by files outside the plan.
    planned_sources = {item["current"] for item in items}
    planned_dests = [item["proposed"] for item in items]
    collisions: list[dict[str, Any]] = []
    if len(set(planned_dests)) != len(planned_dests):
        raise ValidationProblem("Planner produced duplicate destinations; aborting")
    import os as _os
    for item in items:
        if item["current"] == item["proposed"]:
            continue
        candidate = root / item["proposed"]
        if _os.path.normcase(str(candidate.resolve(strict=False))) == _os.path.normcase(
                str((root / item["current"]).resolve(strict=False))):
            continue
        if candidate.exists() and item["proposed"] not in planned_sources:
            collisions.append({"destination": item["proposed"], "reason": "occupied by a file outside the migration plan"})
    manifest = {"version": 1, "library_key": key, "root": str(root),
                "width": width, "items": items, "references": references,
                "collisions": collisions,
                "counts": _counts(session, key),
                "works": work_groups(session)}
    manifest_hash = _manifest_hash(manifest)
    row = ScriptMigration(id=_new_id("mig"), library_key=key, status="preview",
                          manifest=manifest, manifest_hash=manifest_hash,
                          report={"collisions": collisions,
                                  "reference_count": len(references),
                                  "blocked": [item["current"] for item in items if item["current"] == item["proposed"] and False]},
                          created_at=now_iso(), updated_at=now_iso())
    session.add(row)
    session.flush()
    return {"migration_id": row.id, "status": "preview", "manifest_hash": manifest_hash,
            "manifest": manifest}


def _work_hint(session: Session, script_id: str) -> dict[str, Any] | None:
    links = session.scalars(select(ScriptLink).where(
        (ScriptLink.source_id == script_id) | (ScriptLink.target_id == script_id))).all()
    if not links:
        return None
    kinds = sorted({link.kind for link in links})
    return {"kinds": kinds, "confirmed": any(link.confirmed for link in links)}


def _scan_references(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return [{"line": 0, "match": "", "context": "unreadable file; skipped",
                 "safe_to_update": False}]
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in SCRIPT_REF_RE.finditer(line):
            start = max(0, match.start() - 40)
            findings.append({"line": number, "match": match.group(0),
                             "context": line[start:match.end() + 40].strip()[:160],
                             "safe_to_update": False})
            if len(findings) >= 50:
                return findings
    return findings


def get_migration(session: Session, migration_id: str) -> ScriptMigration:
    row = session.get(ScriptMigration, migration_id)
    if row is None:
        raise NotFound("Migration not found")
    return row


def list_migrations(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(ScriptMigration).order_by(ScriptMigration.created_at.desc()).limit(50)).all()
    return [migration_read(row) for row in rows]


def migration_read(row: ScriptMigration) -> dict[str, Any]:
    manifest = dict(row.manifest or {})
    items = manifest.get("items", [])
    return {"id": row.id, "library_key": row.library_key, "status": row.status,
            "manifest_hash": row.manifest_hash, "approved_at": row.approved_at,
            "applied_at": row.applied_at, "rolled_back_at": row.rolled_back_at,
            "error": row.error, "report": dict(row.report or {}),
            "item_count": len(items) if isinstance(items, list) else 0,
            "created_at": row.created_at, "updated_at": row.updated_at}


def approve_migration(session: Session, migration_id: str, *, expected_hash: str) -> dict[str, Any]:
    row = get_migration(session, migration_id)
    if row.status != "preview":
        raise ValidationProblem(f"Only previews can be approved (status={row.status})")
    if not expected_hash or expected_hash != row.manifest_hash:
        raise ValidationProblem("Manifest hash mismatch; the preview is stale")
    row.status = "approved"
    row.approved_at = now_iso()
    row.updated_at = now_iso()
    session.flush()
    _record_migration_event(session, row.id, "approved", note="Preview approved; fingerprints bound.")
    return migration_read(row)


def _record_migration_event(session: Session, migration_id: str, event_type: str, *, note: str = "") -> None:
    setting_key = f"scripts_migration_log_{migration_id}"
    existing = session.get(Setting, setting_key)
    entry = {"event": event_type, "note": note[:1000], "at": now_iso()}
    if existing is None:
        session.add(Setting(key=setting_key, value=[entry], updated_at=now_iso()))
    else:
        value = list(existing.value or [])
        value.append(entry)
        existing.value = value[-200:]
        existing.updated_at = now_iso()
    session.flush()


def git_safety(session: Session, root: Path) -> dict[str, Any]:
    """Read-only git inspection. Never stages, commits, resets, or cleans."""
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10, shell=False, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"is_repo": False, "detail": f"git unavailable ({exc.__class__.__name__})",
                "blocking": [], "warnings": [], "dirty": []}
    if top.returncode != 0:
        return {"is_repo": False, "detail": "not a git repository",
                "blocking": [], "warnings": [], "dirty": []}
    try:
        proc = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "-uall"],
                              capture_output=True, text=True, timeout=20,
                              shell=False, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"is_repo": True, "detail": f"status failed ({exc.__class__.__name__})",
                "blocking": ["git status unavailable"], "warnings": [], "dirty": []}
    if proc.returncode != 0:
        return {"is_repo": True, "detail": "git status failed",
                "blocking": ["git status failed"], "warnings": [], "dirty": []}
    dirty: list[dict[str, str]] = []
    for line in (proc.stdout or "").splitlines():
        if len(line) < 4:
            continue
        index, worktree, path = line[0], line[1], line[3:].strip().strip('"')
        dirty.append({"index": index, "worktree": worktree, "path": path})
    unmerged = [entry["path"] for entry in dirty if entry["index"] == "U" or entry["worktree"] == "U"
                or (entry["index"], entry["worktree"]) in {("A", "A"), ("D", "D")}]
    return {"is_repo": True, "detail": f"{len(dirty)} change(s) observed (read-only)",
            "blocking": [f"unmerged path: {path}" for path in unmerged],
            "warnings": [], "dirty": dirty}


def cultivation_snapshot(session: Session) -> dict[str, Any]:
    from mission_control.cultivation import service as cult

    published = cult.get_goal(session, "scripts_published")
    from mission_control.models import CultivationGoal as GoalModel
    weekly_goal = session.get(GoalModel, "weekly_script")
    return {
        "published": cult.goal_read(session, published)["progress"],
        "weekly": cult.goal_read(session, weekly_goal)["progress"] if weekly_goal else None,
        "registry": dict(session.get(Setting, "scripts_sync").value.get("counts", {})
                         if session.get(Setting, "scripts_sync") and isinstance(
                             session.get(Setting, "scripts_sync").value, dict) else {}),
    }


def apply_migration(session: Session, migration_id: str, *, expected_hash: str) -> dict[str, Any]:
    from mission_control.scripts.service import _safe_join as _join

    row = get_migration(session, migration_id)
    if row.status not in ("approved", "failed", "applying"):
        raise ValidationProblem(f"Only approved migrations can be applied (status={row.status})")
    if expected_hash != row.manifest_hash:
        raise ValidationProblem("Manifest hash mismatch; the preview is stale")
    manifest = dict(row.manifest or {})
    items: list[dict[str, Any]] = list(manifest.get("items", []) or [])
    library_key = str(manifest.get("library_key") or "")
    if not items:
        raise ValidationProblem("Migration manifest is empty")
    config = get_scripts_config(session)
    if library_key_for_root(config["root"]) != library_key:
        raise ValidationProblem("Configured library changed since the preview; re-plan")
    info = describe_root(config["root"])
    if info["status"] != "accessible":
        raise ValidationProblem(info.get("error") or "Script directory unavailable")
    root = Path(info["root"])
    # Freshness: every source fingerprint must still match.
    for item in items:
        candidate = root / str(item["current"])
        if not candidate.is_file():
            # Already applied/renamed? Check the destination instead (resume).
            final = root / str(item["proposed"])
            if final.is_file():
                continue
            raise ValidationProblem(f"Source fingerprint stale: {item['current']} is missing")
        try:
            with open(candidate, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            raise ValidationProblem(f"Source fingerprint stale: cannot read {item['current']}")
        if digest != str(item.get("sha256") or ""):
            raise ValidationProblem(f"Source fingerprint stale: {item['current']} changed since preview")
    # Destinations must be free except for planned rotations.
    planned_sources = {str(item["current"]) for item in items}
    for item in items:
        if str(item["current"]) == str(item["proposed"]):
            continue
        candidate = root / str(item["proposed"])
        if candidate.exists() and str(item["proposed"]) not in planned_sources:
            raise ValidationProblem(f"Destination conflict: {item['proposed']} is occupied outside the plan")
    # Git safety: block on dirty tracked sources or destinations, unmerged paths.
    safety = git_safety(session, root)
    if safety["blocking"]:
        row.status = "failed"
        row.error = "; ".join(safety["blocking"])[:2000]
        row.updated_at = now_iso()
        session.flush()
        raise ValidationProblem(row.error)
    # Untracked entries (??) are warnings, not blocks; staged/unstaged tracked changes block.
    tracked_dirty = {entry["path"].replace("\\", "/") for entry in safety.get("dirty", [])
                     if not (entry["index"] == "?" and entry["worktree"] == "?")}
    for item in items:
        if str(item["current"]) in tracked_dirty:
            raise ValidationProblem(f"Git working tree has uncommitted changes to {item['current']}; commit, stash, or discard outside Mission Control first")
    before = cultivation_snapshot(session)
    row.status = "applying"
    row.error = None
    row.updated_at = now_iso()
    session.flush()
    report = dict(row.report or {})
    steps: list[dict[str, Any]] = list(report.get("steps", []) or [])
    done = {step["id"] for step in steps if step.get("done")}
    try:
        temps: dict[str, str] = {step["id"]: step["temp"] for step in steps if step.get("temp")}
        for item in items:
            if item["id"] in done:
                continue
            if str(item["current"]) == str(item["proposed"]):
                steps.append({"id": item["id"], "temp": None, "done": True, "note": "already correctly named"})
                continue
            source = _join(root, str(item["current"]))
            temp_name = f"__migrate_{uuid.uuid4().hex[:8]}_{Path(str(item['proposed'])).name}"
            parent = Path(str(item["proposed"])).parent
            temp_rel = temp_name if str(parent) in (".", "") else str(parent / temp_name).replace("\\", "/")
            temp_abs = root / temp_rel
            if temp_abs.exists():
                raise RuntimeError(f"Temporary path collision: {temp_rel}")
            os.replace(str(source), str(temp_abs))
            temps[item["id"]] = temp_rel
            steps.append({"id": item["id"], "temp": temp_rel, "done": False,
                          "from": str(item["current"]), "to": str(item["proposed"])})
            report["steps"] = steps
            row.report = report
            row.updated_at = now_iso()
            session.flush()
        # Phase 2: temps -> finals + registry updates.
        for item in items:
            if item["id"] in done:
                continue
            if str(item["current"]) == str(item["proposed"]):
                continue
            temp_rel = temps.get(item["id"])
            if temp_rel is None:
                raise RuntimeError(f"Missing temp step for {item['id']}")
            temp_abs = root / temp_rel
            final_abs = _join(root, str(item["proposed"]))
            if final_abs.exists():
                # Resume case: final already in place with correct content.
                try:
                    with open(final_abs, "rb") as handle:
                        existing = hashlib.sha256(handle.read()).hexdigest()
                except OSError:
                    existing = ""
                if existing != str(item.get("sha256") or ""):
                    raise RuntimeError(f"Destination occupied with unexpected content: {item['proposed']}")
            else:
                os.replace(str(temp_abs), str(final_abs))
            with open(final_abs, "rb") as handle:
                final_hash = hashlib.sha256(handle.read()).hexdigest()
            if final_hash != str(item.get("sha256") or ""):
                raise RuntimeError(f"Hash mismatch after rename: {item['proposed']}")
            for step in steps:
                if step["id"] == item["id"]:
                    step["done"] = True
            report["steps"] = steps
            row.report = report
            row.updated_at = now_iso()
            session.flush()
        # Registry paths are updated in two passes via collision-free
        # placeholders: direct sequential updates would violate the
        # (library_key, current_relpath) uniqueness on rotations
        # (e.g. 056_a -> 057 while record 057 still holds that path).
        _finalize_registry_paths(session, root, items, row)
    except Exception as exc:
        row.status = "failed"
        row.error = str(exc)[:2000]
        row.report = report
        row.updated_at = now_iso()
        session.flush()
        raise ValidationProblem(row.error) from None
    after = cultivation_snapshot(session)
    _assert_cultivation_preserved(before, after)
    # Refresh sync fingerprint so status reflects new paths.
    from mission_control.scripts import service as svc
    sync_result = svc.sync_scripts(session)
    row.status = "applied"
    row.applied_at = now_iso()
    row.error = None
    row.report = {**report, "git": {k: v for k, v in safety.items() if k != "dirty"},
                  "git_dirty_count": len(safety.get("dirty", [])),
                  "cultivation_before": _summarise(before), "cultivation_after": _summarise(after),
                  "sync": {"status": sync_result.get("status"), "counts": sync_result.get("counts", {})},
                  "works": work_groups(session)}
    row.updated_at = now_iso()
    session.flush()
    _record_migration_event(session, row.id, "applied", note=f"Renamed {len(items)} file(s); identities preserved.")
    return migration_read(row)


def _finalize_registry_paths(session: Session, root: Path,
                              items: list[dict[str, Any]], row: ScriptMigration) -> None:
    """Point every registry record at its final path, preserving identity.

    Two passes via unique placeholders: a direct sequential update would
    violate the (library_key, current_relpath) uniqueness on rotations where
    one record's destination is still held by a later record.
    """
    records: dict[str, ScriptRecord] = {}
    olds: dict[str, str] = {}
    for item in items:
        record = session.get(ScriptRecord, item["id"])
        if record is None:
            raise RuntimeError(f"Registry record vanished: {item['id']}")
        records[item["id"]] = record
        olds[item["id"]] = str(record.current_relpath)
    for item in items:
        if str(item["current"]) == str(item["proposed"]):
            continue
        records[item["id"]].current_relpath = (
            f"__migrate_hold_{item['id'][-8:]}_{Path(str(item['proposed'])).name}")
        records[item["id"]].updated_at = now_iso()
    session.flush()
    for item in items:
        if str(item["current"]) == str(item["proposed"]):
            continue
        record = records[item["id"]]
        final_abs = root / str(item["proposed"])
        record.current_relpath = str(item["proposed"])
        record.script_number = int(item.get("proposed_number") or record.script_number or 0) or None
        record.title = _prettify(Path(str(item["proposed"])).stem)
        try:
            record.file_size = final_abs.stat().st_size
            record.mtime_ns = final_abs.stat().st_mtime_ns
        except OSError:
            pass
        record.missing = False
        record.last_seen_at = now_iso()
        record.updated_at = now_iso()
    session.flush()
    for item in items:
        if str(item["current"]) == str(item["proposed"]):
            continue
        _record_event(session, item["id"], "renamed", from_value=olds[item["id"]],
                      to_value=str(item["proposed"]),
                      note=f"Migration {row.id[:12]}…: {olds[item['id']]} → {item['proposed']}. Identity preserved.")


def _summarise(snapshot: dict[str, Any]) -> dict[str, Any]:
    published = (snapshot.get("published") or {})
    weekly = (snapshot.get("weekly") or {})
    return {"published_current": published.get("current"), "weekly_current": (weekly or {}).get("current"),
            "registry_counts": snapshot.get("registry", {})}


def _assert_cultivation_preserved(before: dict[str, Any], after: dict[str, Any]) -> None:
    before_pub = (before.get("published") or {}).get("current")
    after_pub = (after.get("published") or {}).get("current")
    if before_pub != after_pub:
        raise RuntimeError(f"Cultivation lifetime count changed ({before_pub} → {after_pub}); aborting")
    before_statuses = sorted(((before.get("registry", {}) or {}).get("by_status", {}) or {}).items())
    after_statuses = sorted(((after.get("registry", {}) or {}).get("by_status", {}) or {}).items())
    if before_statuses != after_statuses:
        raise RuntimeError("Lifecycle distribution changed during migration; aborting")


def rollback_migration(session: Session, migration_id: str) -> dict[str, Any]:
    from mission_control.scripts.service import _safe_join as _join

    row = get_migration(session, migration_id)
    if row.status not in ("applied", "failed"):
        raise ValidationProblem(f"Only applied or failed migrations can be rolled back (status={row.status})")
    manifest = dict(row.manifest or {})
    items: list[dict[str, Any]] = list(manifest.get("items", []) or [])
    root = Path(str(manifest.get("root") or ""))
    if not root.is_dir():
        raise ValidationProblem("Original library root is unavailable; cannot roll back safely")
    errors: list[str] = []
    for item in reversed(items):
        try:
            record = session.get(ScriptRecord, item["id"])
            if record is None:
                errors.append(f"{item['id']}: record missing")
                continue
            if str(record.current_relpath) != str(item["proposed"]) and str(record.current_relpath) != str(item["current"]):
                errors.append(f"{item['id']}: unexpected current path {record.current_relpath}")
                continue
            if str(record.current_relpath) == str(item["current"]):
                continue  # already back
            source = _join(root, str(item["proposed"]))
            if not source.is_file():
                errors.append(f"{item['proposed']}: final file missing")
                continue
            dest = _join(root, str(item["current"]))
            if dest.exists():
                errors.append(f"{item['current']}: original path occupied")
                continue
            os.replace(str(source), str(dest))
            record.current_relpath = str(item["current"])
            record.script_number = int(item.get("current_number") or record.script_number or 0) or None
            record.title = _prettify(Path(str(item["current"])).stem)
            record.updated_at = now_iso()
            session.flush()
            _record_event(session, record.id, "rollback", from_value=str(item["proposed"]),
                          to_value=str(item["current"]),
                          note=f"Migration {row.id[:12]}… rolled back.")
        except (OSError, ValidationProblem) as exc:
            errors.append(f"{item['id']}: {exc}")
    if errors:
        row.status = "failed"
        row.error = "; ".join(errors)[:2000]
        row.updated_at = now_iso()
        session.flush()
        raise ValidationProblem(row.error)
    row.status = "rolled_back"
    row.rolled_back_at = now_iso()
    row.error = None
    row.updated_at = now_iso()
    session.flush()
    from mission_control.scripts import service as svc
    sync_result = svc.sync_scripts(session)
    row.report = {**dict(row.report or {}), "rollback_sync": sync_result.get("counts", {})}
    session.flush()
    _record_migration_event(session, row.id, "rolled_back", note="Original filenames restored; identities preserved.")
    return migration_read(row)
