"""Canonical book identity resolution (MC-PUBLISH-02, Phase B).

A book is a logical publishing work. Its logical identity (the Mission
``project_id``) is separate from Writer project IDs, filesystem locations,
Git repos, Hugo routes, Bookbuilder slugs and ALIVE's ephemeral ids.

Rules (deterministic):

1. Exact verified identifiers resolve first (Mission project id, explicit alias).
2. Explicit aliases resolve next and remain stable.
3. String-normalized matches generate *suggestions* (``candidate``), never merges.
4. Similar titles alone never establish identity.
5. Identical directory names alone never establish identity.
6. A shared Git repository does not imply shared book identity.
7. Different paths may legitimately represent the same book.
8. Conflicting explicit mappings fail closed.
9. Ambiguity stays visible; ``unavailable`` never means the book ceased to exist.

Aliases persist in the ``book_identity_aliases`` Setting (explicit,
author-approved mappings only) so no primary key is rewritten and no schema
migration is required. History (assessments, approvals, evaluations, activity)
is untouched because rows keep their existing ``project_id`` keys.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

ALIASES_SETTING_KEY = "book_identity_aliases"

# Systems that may own an external identifier for a book.
KNOWN_SYSTEMS = frozenset(
    {"mission", "writer", "alive", "bookbuilder", "hugo", "git", "proof"}
)

# How an alias was verified. Only explicit author action creates aliases;
# normalized correspondence only ever produces candidates.
VERIFICATION_EXPLICIT_AUTHOR = "explicit_author_mapping"
VERIFICATION_EXACT_ID = "exact_id"


def normalize_identity(value: str | None) -> str:
    """Suggestion-level normalization: separators collapse, case folds.

    Used ONLY to propose candidates. Never resolves identity by itself.
    """
    if not value:
        return ""
    return _NON_ALNUM.sub("-", str(value).strip().casefold()).strip("-")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_aliases(session: Session) -> list[dict[str, Any]]:
    """Read the explicit alias map. Never raises on missing/malformed data."""
    from mission_control.models import Setting

    row = session.get(Setting, ALIASES_SETTING_KEY)
    if row is None or not isinstance(row.value, list):
        return []
    aliases: list[dict[str, Any]] = []
    for entry in row.value:
        if isinstance(entry, dict) and entry.get("canonical_project_id") and entry.get("external_id"):
            aliases.append(dict(entry))
    return aliases


def _write_aliases(session: Session, aliases: list[dict[str, Any]]) -> None:
    from mission_control.models import Setting
    from mission_control.persistence.db import now_iso

    row = session.get(Setting, ALIASES_SETTING_KEY)
    if row is None:
        session.add(Setting(key=ALIASES_SETTING_KEY, value=aliases, updated_at=now_iso()))
    else:
        row.value = aliases
        row.updated_at = now_iso()


def save_alias(
    session: Session,
    *,
    canonical_project_id: str,
    system: str,
    external_id: str,
    verification_method: str = VERIFICATION_EXPLICIT_AUTHOR,
    source_reference: str = "",
    known_writer_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Persist an explicit alias. Fails closed on conflicts and fabrications.

    - The canonical Mission project must exist.
    - One external id per system maps to at most one canonical book.
    - A ``writer`` external id must exist in the Writer registry
      (never fabricate a Writer project id).
    """
    from mission_control.models import Project

    system = str(system or "").strip().casefold()
    external_id = str(external_id or "").strip()
    canonical_project_id = str(canonical_project_id or "").strip()
    if system not in KNOWN_SYSTEMS:
        raise ValueError(f"Unknown identity system: {system!r}.")
    if not external_id:
        raise ValueError("external_id must not be empty.")
    if session.get(Project, canonical_project_id) is None:
        raise ValueError(f"Unknown canonical project: {canonical_project_id!r}.")
    if verification_method not in (VERIFICATION_EXPLICIT_AUTHOR, VERIFICATION_EXACT_ID):
        raise ValueError(f"Unsupported verification method: {verification_method!r}.")
    if system == "writer" and known_writer_ids is not None and external_id not in known_writer_ids:
        raise ValueError(
            f"Writer project {external_id!r} is not in the Writer registry; "
            "aliases cannot fabricate Writer project ids."
        )
    aliases = get_aliases(session)
    for entry in aliases:
        if (
            str(entry.get("system", "")).casefold() == system
            and str(entry.get("external_id", "")) == external_id
        ):
            if str(entry.get("canonical_project_id")) == canonical_project_id:
                return dict(entry)  # idempotent re-registration
            raise ValueError(
                f"Conflicting alias: {system}:{external_id} already maps to "
                f"{entry.get('canonical_project_id')!r}."
            )
    entry = {
        "canonical_project_id": canonical_project_id,
        "system": system,
        "external_id": external_id,
        "alias_type": "equivalent_work",
        "verification_method": verification_method,
        "verified_at": utcnow_iso(),
        "source_reference": source_reference,
    }
    aliases.append(entry)
    _write_aliases(session, aliases)
    return dict(entry)


def delete_alias(session: Session, *, system: str, external_id: str) -> bool:
    """Remove an explicit alias. Returns True when one was removed."""
    system = str(system or "").strip().casefold()
    external_id = str(external_id or "").strip()
    aliases = get_aliases(session)
    kept = [
        entry
        for entry in aliases
        if not (
            str(entry.get("system", "")).casefold() == system
            and str(entry.get("external_id", "")) == external_id
        )
    ]
    if len(kept) == len(aliases):
        return False
    _write_aliases(session, kept)
    return True


def resolve(
    session: Session,
    *,
    system: str,
    external_id: str,
    writer_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Resolve an external identifier to a canonical Mission project.

    Returns ``{"state", "canonical_project_id", "via", "candidates"}`` where
    state is one of ``resolved`` / ``candidate`` / ``conflict`` /
    ``unregistered``. ``mission`` ids that exist resolve immediately.
    Normalized matches only ever produce ``candidate`` with suggestions.
    """
    from mission_control.models import Project

    system = str(system or "").strip().casefold()
    external_id = str(external_id or "").strip()
    if not external_id:
        return {"state": "unregistered", "canonical_project_id": None, "via": None, "candidates": []}
    if system == "mission" and session.get(Project, external_id) is not None:
        return {
            "state": "resolved",
            "canonical_project_id": external_id,
            "via": VERIFICATION_EXACT_ID,
            "candidates": [],
        }
    for entry in get_aliases(session):
        if (
            str(entry.get("system", "")).casefold() == system
            and str(entry.get("external_id", "")) == external_id
        ):
            return {
                "state": "resolved",
                "canonical_project_id": str(entry.get("canonical_project_id")),
                "via": str(entry.get("verification_method")),
                "candidates": [],
            }
    # Suggestion level only: normalized correspondence across namespaces.
    wanted = normalize_identity(external_id)
    candidates: list[str] = []
    if wanted:
        if system == "writer" and writer_ids is not None:
            for wid in sorted(writer_ids):
                if wid != external_id and normalize_identity(wid) == wanted:
                    candidates.append(wid)
        else:
            for project in session.query(Project).all():
                if project.id != external_id and normalize_identity(project.id) == wanted:
                    candidates.append(project.id)
        # Cross-namespace: writer external id vs mission project ids.
        if system == "writer":
            for project in session.query(Project).all():
                if normalize_identity(project.id) == wanted and project.id not in candidates:
                    candidates.append(project.id)
    if len(candidates) == 1:
        return {
            "state": "candidate",
            "canonical_project_id": None,
            "via": "normalized_suggestion",
            "candidates": candidates,
        }
    if len(candidates) > 1:
        return {
            "state": "conflict",
            "canonical_project_id": None,
            "via": "normalized_suggestion",
            "candidates": sorted(candidates),
        }
    return {"state": "unregistered", "canonical_project_id": None, "via": None, "candidates": []}


def _mission_source_ok(session: Session, project_id: str) -> bool:
    """A working Mission manuscript source exists (chapter files on disk)."""
    from mission_control.models import Book

    book = session.scalar(select(Book).where(Book.project_id == project_id))
    if book is None or not book.manuscript_paths:
        return False
    import fnmatch as _fnmatch

    first = (book.manuscript_paths or [None])[0]
    if not first:
        return False
    try:
        directory = Path(first)
        if not directory.is_dir():
            return False
        return any(
            item.is_file() and _fnmatch.fnmatch(item.name, "*.md")
            for item in directory.iterdir()
        )
    except OSError:
        return False


def identity_status(
    session: Session,
    project_id: str,
    writer_ids: set[str] | None = None,
    writer_available: dict[str, bool] | None = None,
    mission_manuscript_ok: bool | None = None,
) -> dict[str, Any]:
    """Resolution status for one Mission book: resolved/candidate/conflict/unregistered/unavailable."""
    from mission_control.models import Project

    if session.get(Project, project_id) is None:
        return {"state": "unregistered", "reason": "No Mission project with this id."}
    if writer_ids is not None and project_id in writer_ids:
        if writer_available is not None and not writer_available.get(project_id, False):
            if mission_manuscript_ok is None:
                mission_manuscript_ok = _mission_source_ok(session, project_id)
            if mission_manuscript_ok:
                return {
                    "state": "resolved",
                    "reason": (
                        "Exact Writer project id match; the Writer location is "
                        "unavailable, so the working Mission source is preserved "
                        "(Writer drift reported separately)."
                    ),
                    "writer_id": project_id,
                }
            return {
                "state": "unavailable",
                "reason": "Registered in Writer but no usable manuscript source exists anywhere.",
                "writer_id": project_id,
            }
        return {"state": "resolved", "reason": "Exact Writer project id match.", "writer_id": project_id}
    for entry in get_aliases(session):
        if str(entry.get("canonical_project_id")) == project_id and str(entry.get("system")) == "writer":
            return {
                "state": "resolved",
                "reason": f"Explicit {entry.get('verification_method')} alias.",
                "writer_id": str(entry.get("external_id")),
            }
    if writer_ids is not None:
        wanted = normalize_identity(project_id)
        matches = sorted(w for w in writer_ids if normalize_identity(w) == wanted and w != project_id)
        if len(matches) == 1:
            return {
                "state": "candidate",
                "reason": (
                    f"Normalized suggestion only: Writer {matches[0]!r} resembles "
                    f"{project_id!r}. Requires author approval; never auto-merged."
                ),
                "writer_id": None,
                "candidates": matches,
            }
        if len(matches) > 1:
            return {
                "state": "conflict",
                "reason": f"Multiple Writer ids normalize to {project_id!r}: {matches}.",
                "writer_id": None,
                "candidates": matches,
            }
    if mission_manuscript_ok is False and (writer_ids is None or project_id not in (writer_ids or set())):
        return {"state": "unavailable", "reason": "No usable manuscript source is configured."}
    return {"state": "unregistered", "reason": "No Writer project matched this Mission book."}


def list_identity_conflicts(
    session: Session,
    writer_ids: set[str],
    writer_available: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """All books needing attention: candidates, conflicts, unregistered writers, unavailable."""
    from mission_control.models import Project

    candidates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    unavailable: list[str] = []
    mission_ids = {p.id for p in session.query(Project).all()}
    for pid in sorted(mission_ids):
        status = identity_status(session, pid, writer_ids, writer_available)
        if status["state"] == "candidate":
            candidates.append({"project_id": pid, **status})
        elif status["state"] == "conflict":
            conflicts.append({"project_id": pid, **status})
        elif status["state"] == "unavailable":
            unavailable.append(pid)
    # Writer books with no Mission counterpart (no auto-registration here).
    unregistered_writer = sorted(w for w in writer_ids if w not in mission_ids)
    still_unmapped = [w for w in unregistered_writer if normalize_identity(w) not in {normalize_identity(m) for m in mission_ids}]
    suggested = [w for w in unregistered_writer if w not in still_unmapped]
    return {
        "candidates": candidates,
        "conflicts": conflicts,
        "unavailable": sorted(unavailable),
        "unregistered_writer": still_unmapped,
        "suggested_writer_mappings": suggested,
    }
