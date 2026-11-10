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
        if project.id == _slugify(detected.book_dir.name):
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


def _link_repository(session: Session, project_id: str, project_dir: Path) -> None:
    path = str(project_dir)
    repo = session.scalar(select(Repository).where(Repository.path == path))
    if repo is None:
        repo = Repository(
            id=repository_id(path),
            path=path,
            name=project_dir.name,
            classification="book",
            confidence=0.95,
            evidence=["Detected manuscript tree under content/books"],
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


def sync_detected_books(session: Session, roots: Iterable[str | Path]) -> list[str]:
    """Create missing book workspaces and return the titles that were added."""
    session.flush()
    created: list[str] = []
    created_paths: list[str] = []
    for index, detected in enumerate(detect_books(roots)):
        if _existing_book(session, detected) is not None:
            continue
        project_id = _new_project_id(session, _slugify(detected.book_dir.name))
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
                f"Detected automatically from {detected.book_dir}. "
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
        if detected.standalone:
            _link_repository(session, project_id, detected.project_dir)
        created.append(detected.title)
        created_paths.append(str(detected.book_dir))

    if created:
        digest = hashlib.sha1("|".join(sorted(created_paths)).encode("utf-8")).hexdigest()[:12]
        record_activity(
            session,
            event_type="system",
            title=f"Detected {len(created)} book workspaces",
            detail=", ".join(created[:20]),
            source="mission-control",
            provenance="verified_observation",
            metadata={"paths": created_paths, "count": len(created)},
            dedupe_key=f"detected-books-{digest}",
        )
        session.flush()
    return created
