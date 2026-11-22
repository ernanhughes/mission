"""Synchronise Mission Control books with Writer's registry (read-only source).

Precedence (explicit):

- Writer owns manuscript location (chapter directory), chapter pattern,
  manuscript filename, profile, publication lifecycle status and preview route.
- Mission Control owns operational planning state: milestones, goals, pinning,
  focus, status, next actions, quality review state and activity.

The sync never edits manuscripts, never changes publication status, never
commits/pushes, and never writes Writer's configuration.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.persistence.db import now_iso
from mission_control.persistence.seed import repository_id
from mission_control.writer_registry.adapter import (
    WriterBookDefinition,
    WriterRegistrySnapshot,
    load_writer_registry,
    resolve_registry_path,
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_title(value: str) -> str:
    return _NON_ALNUM.sub(" ", str(value or "").casefold()).strip()


def _norm_path(value: str | None) -> str:
    if not value:
        return ""
    try:
        return os.path.normcase(os.path.normpath(value))
    except OSError:
        return os.path.normcase(str(value))


def _existing_source_available(paths: list[str], pattern: str = "*.md") -> bool:
    """True when the configured first manuscript path holds chapter files."""
    import fnmatch

    if not paths or not paths[0]:
        return False
    try:
        directory = Path(paths[0])
        if not directory.is_dir():
            return False
        return any(
            item.is_file() and fnmatch.fnmatch(item.name, pattern)
            for item in directory.iterdir()
        )
    except OSError:
        return False


def _book_conflict(session: Session, definition: WriterBookDefinition) -> str | None:
    """Return a conflicting Mission project id, if any, else None."""
    from mission_control.models import Book

    wanted = _normalize_title(definition.title)
    wanted_dir = _norm_path(str(definition.chapter_dir))
    for book in session.scalars(select(Book)).all():
        if book.project_id == definition.project_id:
            return None  # stable identity match, not a conflict
        if wanted and _normalize_title(book.title) == wanted:
            return str(book.project_id)
        for existing in book.manuscript_paths or []:
            if existing and _norm_path(str(existing)) == wanted_dir:
                return str(book.project_id)
    return None


def sync_writer_books(
    session: Session,
    snapshot: WriterRegistrySnapshot | Path | str | None = None,
    *,
    create_missing: bool = True,
) -> dict[str, Any]:
    """Align Mission books with Writer definitions. Returns a summary dict."""
    from mission_control.models import Book, Project, ProjectRepository, Repository

    if snapshot is None or isinstance(snapshot, (str, Path)):
        snapshot = load_writer_registry(
            Path(snapshot) if snapshot is not None else resolve_registry_path()
        )
    assert isinstance(snapshot, WriterRegistrySnapshot)

    updated: list[str] = []
    created: list[str] = []
    unavailable: list[str] = []
    conflicts: list[str] = []
    ambiguities: list[str] = []
    chapter_counts: dict[str, int | None] = {}
    errors = list(snapshot.errors)

    for project_id, definition in sorted(snapshot.books.items()):
        chapter_counts[project_id] = definition.chapter_count
        if not definition.available:
            unavailable.append(project_id)

        project = session.get(Project, project_id)
        book = session.scalar(select(Book).where(Book.project_id == project_id))

        if project is None or book is None:
            conflict = _book_conflict(session, definition)
            if conflict is not None:
                conflicts.append(f"{project_id} conflicts with existing {conflict}; not duplicated")
                continue
            if not create_missing:
                continue
            if project is None:
                project = Project(
                    id=project_id,
                    name=definition.title,
                    description=f"Book workspace synchronised from Writer registry ({definition.chapter_dir}).",
                    kind="book",
                    status="active",
                    priority=1000,
                    pinned=False,
                    archived=False,
                    display_order=1000,
                    current_milestone="",
                    next_action="",
                    notes="Created from Writer's authoritative project registry; operational state remains user-maintained.",
                    created_at=now_iso(),
                    updated_at=now_iso(),
                )
                session.add(project)
                session.flush()
            if book is None:
                session.add(
                    Book(
                        id=f"book-{project_id}",
                        project_id=project_id,
                        title=definition.title,
                        status="planned",
                        current_milestone="",
                        next_action="",
                        manuscript_paths=[str(definition.chapter_dir)],
                        implementation_paths=[],
                        published_url=None,
                        local_url=None,
                        quality_review_state="not_reviewed",
                        last_activity_at=None,
                        created_at=now_iso(),
                        updated_at=now_iso(),
                    )
                )
                session.flush()
                created.append(project_id)
                book = session.scalar(select(Book).where(Book.project_id == project_id))

        if book is None:
            continue

        # Writer owns the canonical chapter directory (first manuscript path),
        # but a working configured source is never silently replaced by a
        # missing registry path. Operational fields (status, milestones,
        # actions, review state) are never touched here.
        desired = str(definition.chapter_dir)
        existing_paths = list(book.manuscript_paths or [])
        if not existing_paths:
            book.manuscript_paths = [desired]
            book.updated_at = now_iso()
            updated.append(project_id)
        elif _norm_path(existing_paths[0]) != _norm_path(desired):
            if definition.available or not _existing_source_available(
                existing_paths, definition.chapter_pattern
            ):
                book.manuscript_paths = [desired, *[p for p in existing_paths[1:] if p]]
                book.updated_at = now_iso()
                updated.append(project_id)
            else:
                ambiguities.append(
                    f"{project_id}: Writer registry path unavailable "
                    f"({desired}); kept working source {existing_paths[0]}"
                )

        # Ensure the repository row exists and is linked (read-only evidence).
        try:
            repo_path_str = str(definition.repo_path)
            repo = session.scalar(select(Repository).where(Repository.path == repo_path_str))
            if repo is None:
                # repository_id() is a casefold hash: the same repo stored with
                # different case (e.g. C:\ vs c:\) shares the id. Reuse by id
                # instead of inserting a duplicate row.
                repo = session.get(Repository, repository_id(repo_path_str))
            if repo is None:
                for candidate in session.scalars(select(Repository)).all():
                    if _norm_path(candidate.path) == _norm_path(repo_path_str):
                        repo = candidate
                        break
            if repo is None:
                repo = Repository(
                    id=repository_id(repo_path_str),
                    path=repo_path_str,
                    name=definition.repo_path.name or project_id,
                    classification="book",
                    confidence=0.9,
                    evidence=["Synchronised from Writer's authoritative project registry"],
                    source_root=str(definition.repo_path.parent),
                    is_git=(definition.repo_path / ".git").exists(),
                    accessible=definition.repo_path.exists(),
                    candidate=False,
                    first_seen_at=now_iso(),
                )
                session.add(repo)
                session.flush()
            else:
                try:
                    repo.accessible = definition.repo_path.exists()
                except OSError:
                    repo.accessible = False
            link = session.get(ProjectRepository, (project_id, repo.id))
            if link is None:
                session.add(
                    ProjectRepository(
                        project_id=project_id, repository_id=repo.id, role="manuscript"
                    )
                )
        except OSError:
            pass

    session.flush()
    if updated or created:
        record_activity(
            session,
            event_type="system",
            title=f"Writer registry sync ({len(updated)} updated, {len(created)} created)",
            detail=", ".join([*updated, *created][:20]),
            source="mission-control",
            provenance="verified_observation",
            metadata={"updated": updated, "created": created, "unavailable": unavailable},
            dedupe_key=f"writer-registry-sync-{len(updated)}-{len(created)}",
        )
        session.flush()

    return {
        "registry": str(snapshot.source_path) if snapshot.source_path else None,
        "mtime_ns": snapshot.mtime_ns,
        "books": len(snapshot.books),
        "updated": sorted(set(updated)),
        "created": sorted(set(created)),
        "unavailable": sorted(set(unavailable)),
        "conflicts": conflicts,
        "ambiguities": ambiguities,
        "errors": errors,
        "chapter_counts": chapter_counts,
        "skipped_non_book": list(snapshot.skipped_non_book),
    }


def book_source_diagnostic(
    session: Session,
    project_id: str,
    snapshot: WriterRegistrySnapshot | None = None,
) -> dict[str, Any]:
    """Per-book source diagnostics for the Book workspace UI."""
    from mission_control.models import Book, Project

    if snapshot is None:
        snapshot = load_writer_registry(resolve_registry_path())
    project = session.get(Project, project_id)
    book = session.scalar(select(Book).where(Book.project_id == project_id))
    definition = snapshot.books.get(project_id) if snapshot else None

    manuscript_paths = list(book.manuscript_paths or []) if book else []
    resolved: str | None = str(definition.chapter_dir) if definition else None
    chapter_count = definition.chapter_count if definition else None
    if (definition is None or not definition.available) and manuscript_paths:
        # Fall back to on-disk count for non-registered or drifted books
        # (display only; the Writer location stays authoritative).
        try:
            first = Path(manuscript_paths[0])
            if first.is_dir():
                chapter_count = sum(
                    1 for item in first.iterdir() if item.is_file() and item.suffix.casefold() == ".md"
                )
        except OSError:
            chapter_count = None

    if definition is None:
        integration = "not_registered"
    elif definition.error is not None:
        integration = "registered_unavailable"
    else:
        integration = "registered_available"

    return {
        "project_id": project_id,
        "project_name": project.name if project else None,
        "book_id": book.id if book else None,
        "book_title": book.title if book else None,
        "registry_source": str(snapshot.source_path) if snapshot and snapshot.source_path else None,
        "registry_mtime_ns": snapshot.mtime_ns if snapshot else None,
        "writer_registered": definition is not None,
        "writer_integration_status": integration,
        "resolved_chapter_dir": resolved,
        "manuscript_paths": manuscript_paths,
        "chapter_count": chapter_count,
        "chapter_pattern": definition.chapter_pattern if definition else None,
        "manuscript": definition.manuscript if definition else None,
        "profile": definition.profile if definition else None,
        "publication_status": definition.publication_status if definition else None,
        "preview_route": definition.preview_route if definition else None,
        "available": bool(definition.available) if definition else False,
        "configuration_error": definition.error if definition else None,
        "registry_errors": list(snapshot.errors) if snapshot else [],
        "validation_enabled": definition.validation_enabled if definition else False,
        "validation_checks": list(definition.validation_checks) if definition else [],
        "human_approval_required": definition.human_approval_required
        if definition
        else False,
    }


def classify_discovery(
    *,
    detected_technical: list[Any],
    detected_fiction: list[Any],
    snapshot: WriterRegistrySnapshot,
    session: Session,
) -> dict[str, Any]:
    """Distinguish registered/available, registered/unavailable, discovered/unregistered, ambiguous."""
    from mission_control.models import Book

    registered_dirs = {_norm_path(str(defn.chapter_dir)): pid for pid, defn in snapshot.books.items()}
    mission_dirs = set()
    for book in session.scalars(select(Book)).all():
        for path in book.manuscript_paths or []:
            if path:
                mission_dirs.add(_norm_path(str(path)))

    def _key(detected: Any) -> str:
        book_dir = getattr(detected, "book_dir", None)
        return _norm_path(str(book_dir)) if book_dir else ""

    registered_available: list[str] = []
    registered_unavailable: list[str] = []
    for pid, defn in snapshot.books.items():
        (registered_available if defn.available else registered_unavailable).append(pid)

    discovered_unregistered: list[str] = []
    ambiguous: list[str] = []
    seen: set[str] = set()
    for detected in [*detected_technical, *detected_fiction]:
        key = _key(detected)
        if not key or key in seen:
            continue
        seen.add(key)
        if key in registered_dirs:
            continue  # already registered (canonical)
        if key in mission_dirs:
            ambiguous.append(str(getattr(detected, "book_dir", key)))
        else:
            discovered_unregistered.append(str(getattr(detected, "book_dir", key)))

    return {
        "registered_available": sorted(registered_available),
        "registered_unavailable": sorted(registered_unavailable),
        "discovered_unregistered": sorted(discovered_unregistered),
        "ambiguous_or_conflicting": sorted(ambiguous),
        "registry_errors": list(snapshot.errors),
    }
