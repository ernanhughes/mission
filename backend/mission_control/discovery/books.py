"""Detect book workspaces from the content/books manuscript convention.

A directory shaped like::

    <book root>/<project>/content/books/<book>/_index.md

is a book manuscript. Detection is read-only against the manuscript tree; the
only writes are Mission Control's own project and book records for newly
detected books. Existing book workspaces are never overwritten.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.models import Book, Project, ProjectRepository, Repository
from mission_control.persistence.db import now_iso
from mission_control.persistence.seed import repository_id

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "published": "published",
    "production": "production",
    "editorial": "editorial_review",
    "editorial_review": "editorial_review",
    "verification": "verification",
    "draft": "drafting",
    "drafting": "drafting",
    "development": "drafting",
    "research": "drafting",
}

_ACRONYMS = {
    "ai": "AI",
    "dspy": "DSPy",
    "llm": "LLM",
    "pytorch": "PyTorch",
}


@dataclass(slots=True)
class DetectedBook:
    project_dir: Path
    book_dir: Path
    title: str
    subtitle: str
    description: str
    publication_status: str
    published_url: str | None
    chapter_count: int
    planning_status: Path | None

    @property
    def title_key(self) -> str:
        return _normalize_title(self.title)

    @property
    def standalone(self) -> bool:
        return self.project_dir.name.casefold() == self.book_dir.name.casefold()

    @property
    def project_name(self) -> str:
        if self.book_dir.name.casefold() in {"chapters", "content", "book", "books"}:
            return _humanize(self.project_dir.name)
        return _humanize(self.book_dir.name)


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _humanize(value: str) -> str:
    words = [word for word in re.split(r"[-_.\s]+", value) if word]
    return " ".join(_ACRONYMS.get(word.casefold(), word[:1].upper() + word[1:]) for word in words)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:60] or "book"


def _read_front_matter(index: Path) -> dict[str, Any]:
    try:
        text = index.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff \t\r\n")
    except OSError:
        return {}

    if text.startswith("+++"):
        end = text.find("\n+++", 3)
        if end == -1:
            return {}
        block = text[3:end].strip()
        try:
            return tomllib.loads(block)
        except tomllib.TOMLDecodeError:
            return _fallback_metadata(block)

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end == -1:
            return {}
        try:
            value = yaml.safe_load(text[3:end])
        except yaml.YAMLError:
            return {}
        return value if isinstance(value, dict) else {}

    return {}


def _fallback_metadata(block: str) -> dict[str, Any]:
    """Read individual TOML keys when one malformed line breaks the file."""
    metadata: dict[str, Any] = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z0-9_]+)\s*=\s*['\"]?(.*?)['\"]?\s*$", line.strip())
        if match:
            metadata[match.group(1)] = match.group(2)
    return metadata


def _published_url(metadata: dict[str, Any]) -> str | None:
    for key in ("publication_amazon_url", "publication_aws", "publication_url"):
        value = metadata.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def _detect_book(project_dir: Path, book_dir: Path) -> DetectedBook | None:
    chapter_files = list(book_dir.glob("*.md"))
    if not chapter_files:
        return None
    metadata = _read_front_matter(book_dir / "_index.md")
    title = str(metadata.get("title") or "").strip() or _humanize(book_dir.name)
    subtitle = str(metadata.get("subtitle") or "").strip()
    description = str(metadata.get("description") or "").strip()
    publication_status = str(metadata.get("publication_status") or "").strip().casefold()
    status = _STATUS_MAP.get(publication_status, "planned")
    planning_status = project_dir / "planning" / "STATUS.md"
    standalone = project_dir.name.casefold() == book_dir.name.casefold()
    return DetectedBook(
        project_dir=project_dir,
        book_dir=book_dir,
        title=title,
        subtitle=subtitle,
        description=description,
        publication_status=status,
        published_url=_published_url(metadata),
        chapter_count=len(chapter_files),
        planning_status=(
            planning_status if standalone and planning_status.is_file() else None
        ),
    )


def detect_books(roots: Iterable[str | Path]) -> list[DetectedBook]:
    detected: list[DetectedBook] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        try:
            projects = sorted(path for path in root_path.iterdir() if path.is_dir())
        except OSError:
            continue
        for project_dir in projects:
            books_dir = project_dir / "content" / "books"
            if not books_dir.is_dir():
                continue
            try:
                book_dirs = sorted(path for path in books_dir.iterdir() if path.is_dir())
            except OSError:
                continue
            for book_dir in book_dirs:
                try:
                    book = _detect_book(project_dir, book_dir)
                except OSError:
                    continue
                if book is not None:
                    detected.append(book)

    # Aggregator repositories (aibussin.com, new-books) contain copies of
    # standalone book repositories. Keep one workspace per title, preferring a
    # standalone repository and then the copy with the most chapter files.
    groups: dict[str, list[DetectedBook]] = {}
    for book in detected:
        groups.setdefault(book.title_key, []).append(book)
    canonical = [
        sorted(copies, key=_canonical_sort_key)[0] for copies in groups.values()
    ]
    return sorted(canonical, key=lambda book: book.title.casefold())


def _canonical_sort_key(book: DetectedBook) -> tuple[int, int, int, str]:
    return (
        0 if book.standalone else 1,
        -book.chapter_count,
        len(str(book.book_dir)),
        str(book.book_dir).casefold(),
    )


def _paths_overlap(candidate: str, book_dir: Path) -> bool:
    if not candidate:
        return False
    try:
        left = os.path.normcase(os.path.abspath(candidate))
        right = os.path.normcase(os.path.abspath(book_dir))
    except OSError:
        return False
    return (
        left == right
        or left.startswith(right + os.sep)
        or right.startswith(left + os.sep)
    )


def _existing_book(
    session: Session, detected: DetectedBook
) -> Book | None:
    for book, project in session.execute(
        select(Book, Project).join(Project, Project.id == Book.project_id)
    ).all():
        if _normalize_title(book.title) == detected.title_key:
            return book
        if project.id in {_slugify(detected.book_dir.name), _workspace_slug(detected)}:
            return book
        for path in book.manuscript_paths or []:
            if _paths_overlap(path, detected.book_dir):
                return book
    return None


def _new_project_id(session: Session, base: str) -> str:
    project_id = base
    counter = 2
    while session.get(Project, project_id) is not None:
        project_id = f"{base}-{counter}"
        counter += 1
    return project_id


def _link_repository(
    session: Session,
    project_id: str,
    project_dir: Path,
    evidence: str = "Detected manuscript tree under content/books",
) -> None:
    path = str(project_dir)
    repo = session.scalar(select(Repository).where(Repository.path == path))
    if repo is None:
        repo = Repository(
            id=repository_id(path),
            path=path,
            name=project_dir.name,
            classification="book",
            confidence=0.95,
            evidence=[evidence],
            source_root=str(project_dir.parent),
            is_git=(project_dir / ".git").exists(),
            accessible=True,
            candidate=False,
            first_seen_at=now_iso(),
        )
        session.add(repo)
        session.flush()
    else:
        repo.candidate = False
    if session.get(ProjectRepository, (project_id, repo.id)) is None:
        session.add(
            ProjectRepository(project_id=project_id, repository_id=repo.id, role="manuscript")
        )


def _create_book_workspace(
    session: Session,
    detected: DetectedBook,
    index: int,
    *,
    evidence: str = "Detected manuscript tree under content/books",
    note_prefix: str = "Detected automatically",
    link_all: bool = False,
) -> None:
    project_id = _new_project_id(session, _workspace_slug(detected))
    project = Project(
        id=project_id,
        name=detected.project_name,
        description=detected.description or detected.subtitle,
        kind="book",
        status="active",
        priority=1000 + index,
        pinned=False,
        archived=False,
        display_order=1000 + index,
        current_milestone="",
        next_action="",
        notes=(
            f"{note_prefix} from {detected.book_dir}. "
            "Status and next action remain user-maintained."
        ),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    session.add(project)
    session.flush()
    session.add(
        Book(
            id=f"book-{project_id}",
            project_id=project_id,
            title=detected.title,
            status=detected.publication_status,
            current_milestone="",
            next_action="",
            manuscript_paths=[
                str(detected.book_dir),
                *(
                    [str(detected.planning_status)]
                    if detected.planning_status is not None
                    else []
                ),
            ],
            implementation_paths=[],
            published_url=detected.published_url,
            local_url=None,
            quality_review_state="not_reviewed",
            last_activity_at=None,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
    )
    session.flush()
    if detected.standalone or link_all:
        _link_repository(session, project_id, detected.project_dir, evidence=evidence)


def _sync_books(
    session: Session,
    detected_books: list[DetectedBook],
    *,
    evidence: str,
    note_prefix: str,
    activity_dedupe_prefix: str,
    activity_title: str,
    link_all: bool = False,
) -> list[str]:
    """Shared book-workspace creator. Existing rows are never overwritten."""
    session.flush()
    created: list[str] = []
    created_paths: list[str] = []
    for index, detected in enumerate(detected_books):
        if _existing_book(session, detected) is not None:
            continue
        _create_book_workspace(
            session, detected, index,
            evidence=evidence, note_prefix=note_prefix, link_all=link_all,
        )
        created.append(detected.title)
        created_paths.append(str(detected.book_dir))

    if created:
        digest = hashlib.sha1("|".join(sorted(created_paths)).encode("utf-8")).hexdigest()[:12]
        record_activity(
            session,
            event_type="system",
            title=f"{activity_title} ({len(created)} workspaces)",
            detail=", ".join(created[:20]),
            source="mission-control",
            provenance="verified_observation",
            metadata={"paths": created_paths, "count": len(created)},
            dedupe_key=f"{activity_dedupe_prefix}-{digest}",
        )
        session.flush()
    return created


def sync_detected_books(session: Session, roots: Iterable[str | Path]) -> list[str]:
    """Create missing book workspaces and return the titles that were added."""
    return _sync_books(
        session,
        detect_books(roots),
        evidence="Detected manuscript tree under content/books",
        note_prefix="Detected automatically",
        activity_dedupe_prefix="detected-books",
        activity_title="Detected book workspaces",
    )


_GENERIC_MANUSCRIPT_DIRS = {"chapters", "content", "book", "books"}


def _workspace_slug(detected: DetectedBook) -> str:
    """Stable project-id base: manuscript name, or project name for flat layouts."""
    if detected.book_dir.name.casefold() in _GENERIC_MANUSCRIPT_DIRS:
        return _slugify(detected.project_dir.name)
    return _slugify(detected.book_dir.name)


# ------------------------------------------------- fiction book collection
#
# Fiction manuscripts use a flat layout: each project directory holds its own
# manuscript (``chapters/``, ``book/chapters/`` or ``content/``) instead of
# the technical ``content/books/<book>`` tree. Detection is read-only and
# reuses the same DetectedBook, identity, dedupe and workspace helpers as the
# technical collection. A compiled ``.epub`` is a local build artifact, not
# publication evidence: fiction projects default to drafting and only count
# as published with explicit ``publication_status``/URL evidence.

_FICTION_MANUSCRIPT_CANDIDATES = ("book/chapters", "chapters", "content")


def _fiction_manuscript_dir(project_dir: Path) -> Path | None:
    """Return the manuscript directory holding chapter files, if any."""
    books_dir = project_dir / "content" / "books"
    if books_dir.is_dir():
        try:
            nested = sorted(path for path in books_dir.iterdir() if path.is_dir())
        except OSError:
            nested = []
        for book_dir in nested:
            try:
                if any(item.is_file() and item.suffix.casefold() == ".md" for item in book_dir.iterdir()):
                    return book_dir
            except OSError:
                continue
    for candidate in _FICTION_MANUSCRIPT_CANDIDATES:
        manuscript = project_dir / candidate
        if not manuscript.is_dir():
            continue
        try:
            chapters = [
                item for item in manuscript.iterdir()
                if item.is_file() and item.suffix.casefold() == ".md"
            ]
        except OSError:
            continue
        if chapters:
            return manuscript
    return None


def _detect_fiction_book(project_dir: Path, manuscript_dir: Path) -> DetectedBook | None:
    try:
        chapter_files = [
            item for item in manuscript_dir.iterdir()
            if item.is_file() and item.suffix.casefold() == ".md"
        ]
    except OSError:
        return None
    if not chapter_files:
        return None
    metadata = _read_front_matter(manuscript_dir / "_index.md")
    title = str(metadata.get("title") or "").strip() or _humanize(project_dir.name)
    subtitle = str(metadata.get("subtitle") or "").strip()
    description = str(metadata.get("description") or "").strip()
    raw_status = str(metadata.get("publication_status") or "").strip().casefold()
    if raw_status:
        status = _STATUS_MAP.get(raw_status, "planned")
    else:
        # Chapters on disk are drafting evidence, never publication evidence.
        status = "drafting"
    planning_status: Path | None = None
    for candidate in (project_dir / "planning" / "plan.md", project_dir / "planning" / "STATUS.md"):
        try:
            if candidate.is_file():
                planning_status = candidate
                break
        except OSError:
            continue
    return DetectedBook(
        project_dir=project_dir,
        book_dir=manuscript_dir,
        title=title,
        subtitle=subtitle,
        description=description,
        publication_status=status,
        published_url=_published_url(metadata),
        chapter_count=len(chapter_files),
        planning_status=planning_status,
    )


def detect_fiction_books(roots: Iterable[str | Path]) -> list[DetectedBook]:
    """Discover fiction manuscripts. Read-only; tooling/research dirs excluded.

    A project counts as a fiction book only when a manuscript directory with
    at least one Markdown chapter file is observed. Empty ``chapters/`` trees
    (research notes), tooling repositories and asset directories are excluded,
    not invented.
    """
    detected: list[DetectedBook] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        try:
            projects = sorted(path for path in root_path.iterdir() if path.is_dir())
        except OSError:
            continue
        for project_dir in projects:
            if project_dir.name.startswith("."):
                continue
            try:
                if not project_dir.is_dir():
                    continue
            except OSError:
                continue
            try:
                manuscript_dir = _fiction_manuscript_dir(project_dir)
            except OSError:
                continue
            if manuscript_dir is None:
                continue
            try:
                book = _detect_fiction_book(project_dir, manuscript_dir)
            except OSError:
                continue
            if book is not None:
                detected.append(book)

    groups: dict[str, list[DetectedBook]] = {}
    for book in detected:
        groups.setdefault(book.title_key, []).append(book)
    canonical = [
        sorted(copies, key=_canonical_sort_key)[0] for copies in groups.values()
    ]
    return sorted(canonical, key=lambda book: book.title.casefold())


def sync_fiction_books(session: Session, roots: Iterable[str | Path]) -> list[str]:
    """Create missing fiction book workspaces; never touches manuscripts."""
    return _sync_books(
        session,
        detect_fiction_books(roots),
        evidence="Detected fiction manuscript tree (chapters/content)",
        note_prefix="Detected fiction book automatically",
        activity_dedupe_prefix="detected-fiction-books",
        activity_title="Detected fiction book workspaces",
        link_all=True,
    )
