"""Read-only adapter for Writer's authoritative ``projects.yaml`` registry.

Mission Control never writes Writer's configuration. This module only reads it
and resolves each book's canonical chapter directory using Writer's established
semantics:

- ``project_root`` is kept verbatim (Windows absolute paths stay absolute).
- When ``chapters.path`` is present it is joined to ``project_root`` and the
  top-level ``content_dir`` is ignored (Writer precedence rule).
- Otherwise ``content_dir`` is used (absolute directly, relative joined).
- ``repo.local_path`` is the repository root, falling back to ``project_root``.
- ``book.manuscript`` is a filename only; the chapter directory is the
  canonical manuscript source for the Living Book (never inferred).
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WRITER_REGISTRY = Path(r"C:\Projects\writer\config\web\projects.yaml")

VALID_PUBLICATION_STATUSES = {"published", "development", "research", "registered"}


@dataclass(slots=True)
class WriterBookDefinition:
    project_id: str
    title: str
    project_root: Path
    repo_path: Path
    chapter_dir: Path
    chapter_pattern: str
    metadata_dir: Path | None
    manuscript: str | None
    profile: str
    publication_status: str | None
    preview_route: str | None
    tags: list[str] = field(default_factory=list)
    active: bool = True
    available: bool = False
    chapter_count: int | None = None
    error: str | None = None
    validation_checks: list[dict[str, Any]] = field(default_factory=list)
    human_approval_required: bool = False
    validation_enabled: bool = False
    exclude_prefixes: tuple[str, ...] = ()


@dataclass(slots=True)
class WriterRegistrySnapshot:
    source_path: Path | None
    mtime_ns: int | None
    books: dict[str, WriterBookDefinition]
    errors: list[str] = field(default_factory=list)
    skipped_non_book: list[str] = field(default_factory=list)


def resolve_registry_path(settings: Any | None = None) -> Path:
    """Locate the authoritative Writer registry without guessing manuscripts."""
    raw = os.environ.get("MISSION_CONTROL_WRITER_REGISTRY")
    if raw and str(raw).strip():
        return Path(raw).expanduser()
    if settings is not None:
        candidate = getattr(settings, "writer_registry_path", None)
        if candidate is not None:
            return Path(candidate)
    return DEFAULT_WRITER_REGISTRY


def _norm_tag(value: Any) -> str:
    return str(value or "").strip().casefold()


def is_book_entry(entry: Any) -> bool:
    """Explicit book identification: ``book`` tag present, active.

    Exact tag equality (case-insensitive) so ``non-book`` does not match.
    Excludes the ``writer`` application (``application`` tag, no ``book`` tag)
    and ``programmer_ie`` posts (``blog``/``non-book`` tags, no ``book`` tag).
    """
    if not isinstance(entry, dict):
        return False
    tags = entry.get("tags") or []
    if not isinstance(tags, list):
        return False
    normalized = {_norm_tag(tag) for tag in tags}
    if "book" not in normalized:
        return False
    active = entry.get("active", True)
    return bool(active)


def _join_root(root: Path, raw: Any) -> Path | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return root / candidate


def _resolve_chapter_dir(project_root: Path, entry: dict[str, Any]) -> Path:
    chapters = entry.get("chapters") or {}
    if not isinstance(chapters, dict):
        chapters = {}
    chapters_path = chapters.get("path")
    if chapters_path is not None and str(chapters_path).strip():
        return _join_root(project_root, str(chapters_path).strip()) or (project_root / "chapters")
    content_dir = entry.get("content_dir")
    if content_dir is not None and str(content_dir).strip():
        return _join_root(project_root, str(content_dir).strip()) or (project_root / "chapters")
    return project_root / "chapters"


def _resolve_metadata_dir(project_root: Path, entry: dict[str, Any]) -> Path | None:
    explicit = entry.get("metadata_dir")
    if explicit is not None and str(explicit).strip():
        return _join_root(project_root, str(explicit).strip())
    metadata = entry.get("metadata") or {}
    if isinstance(metadata, dict):
        metadata_path = metadata.get("path")
        if metadata_path is not None and str(metadata_path).strip():
            return _join_root(project_root, str(metadata_path).strip())
    return None


def _publication_status(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    book = entry.get("book") or {}
    if not isinstance(book, dict):
        return None, None
    raw = book.get("publication_status")
    if raw is None or str(raw).strip() == "":
        return None, None
    normalized = str(raw).strip().lower().replace("-", "_")
    if normalized not in VALID_PUBLICATION_STATUSES:
        return None, f"Unknown publication_status {raw!r}"
    return normalized, None


def _title_for(project_id: str, entry: dict[str, Any]) -> str:
    for key in ("label", "name", "title"):
        value = entry.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return project_id


def _count_chapters(chapter_dir: Path, pattern: str) -> int | None:
    try:
        if not chapter_dir.is_dir():
            return None
    except OSError:
        return None
    try:
        return sum(
            1
            for item in chapter_dir.iterdir()
            if item.is_file() and fnmatch.fnmatch(item.name, pattern)
        )
    except OSError:
        return None


class _DuplicateKeyLoader(yaml.SafeLoader):
    """Fail fast on duplicate mapping keys (e.g. duplicated project IDs)."""


def _duplicate_constructor(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False):  # type: ignore[override]
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise ValueError(f"Duplicate mapping key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _duplicate_constructor
)


def load_writer_registry(path: Path | str | None = None) -> WriterRegistrySnapshot:
    """Load Writer's registry read-only. Never raises on missing/invalid config."""
    source = Path(path) if path is not None else DEFAULT_WRITER_REGISTRY
    try:
        stat = source.stat()
        mtime_ns: int | None = int(stat.st_mtime_ns)
    except OSError:
        return WriterRegistrySnapshot(
            source_path=source,
            mtime_ns=None,
            books={},
            errors=[f"Writer registry is not available at {source}."],
        )
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        return WriterRegistrySnapshot(
            source_path=source,
            mtime_ns=mtime_ns,
            books={},
            errors=[f"Writer registry could not be read at {source}: {exc}."],
        )
    try:
        data = yaml.load(text, Loader=_DuplicateKeyLoader)
    except ValueError as exc:
        return WriterRegistrySnapshot(
            source_path=source,
            mtime_ns=mtime_ns,
            books={},
            errors=[f"Writer registry has duplicated keys: {exc}."],
        )
    except yaml.YAMLError as exc:
        return WriterRegistrySnapshot(
            source_path=source,
            mtime_ns=mtime_ns,
            books={},
            errors=[f"Writer registry is invalid YAML at {source}: {exc}."],
        )
    if not isinstance(data, dict):
        return WriterRegistrySnapshot(
            source_path=source,
            mtime_ns=mtime_ns,
            books={},
            errors=[f"Writer registry is not a mapping at {source}."],
        )
    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        return WriterRegistrySnapshot(
            source_path=source,
            mtime_ns=mtime_ns,
            books={},
            errors=[f"Writer registry has no projects mapping at {source}."],
        )
    books: dict[str, WriterBookDefinition] = {}
    errors: list[str] = []
    skipped: list[str] = []
    for project_id, entry in projects.items():
        if not isinstance(entry, dict):
            errors.append(f"Project {project_id!r} is malformed and was skipped.")
            continue
        if not is_book_entry(entry):
            skipped.append(str(project_id))
            continue
        raw_root = entry.get("project_root")
        if raw_root is None or not str(raw_root).strip():
            errors.append(f"Project {project_id!r} has no project_root and was skipped.")
            continue
        project_root = Path(str(raw_root).strip())
        repo = entry.get("repo") or {}
        repo_path = project_root
        if isinstance(repo, dict):
            local_path = repo.get("local_path")
            if local_path is not None and str(local_path).strip():
                repo_path = Path(str(local_path).strip())
        chapter_dir = _resolve_chapter_dir(project_root, entry)
        chapters = entry.get("chapters") or {}
        pattern = "*.md"
        if isinstance(chapters, dict) and chapters.get("pattern"):
            pattern = str(chapters.get("pattern"))
        elif entry.get("glob"):
            pattern = str(entry.get("glob"))
        metadata_dir = _resolve_metadata_dir(project_root, entry)
        book_cfg = entry.get("book") or {}
        manuscript = None
        if isinstance(book_cfg, dict) and book_cfg.get("manuscript"):
            manuscript = str(book_cfg.get("manuscript")).strip() or None
        publication_status, status_error = _publication_status(entry)
        if status_error:
            errors.append(f"Project {project_id!r}: {status_error}; treated as unregistered lifecycle.")
        preview_route = None
        preview = entry.get("preview") or {}
        if isinstance(preview, dict) and preview.get("route_prefix"):
            preview_route = str(preview.get("route_prefix"))
        tags = [str(tag) for tag in (entry.get("tags") or []) if str(tag).strip()]
        profile = str(entry.get("profile") or "technical")
        validation_cfg = entry.get("validation") or {}
        validation_checks: list[dict[str, Any]] = []
        human_approval_required = False
        validation_enabled = False
        if isinstance(validation_cfg, dict):
            validation_enabled = bool(validation_cfg.get("enabled", False))
            raw_checks = validation_cfg.get("checks") or []
            if isinstance(raw_checks, list):
                for check in raw_checks:
                    if isinstance(check, dict) and check.get("id"):
                        validation_checks.append(
                            {
                                "id": str(check.get("id")),
                                "required": bool(check.get("required", False)),
                                "blocking": bool(check.get("blocking", False)),
                            }
                        )
            finalization = validation_cfg.get("finalization") or {}
            if isinstance(finalization, dict):
                human_approval_required = bool(
                    finalization.get("human_approval_required", False)
                )
        count = _count_chapters(chapter_dir, pattern)
        raw_excludes = entry.get("exclude_prefixes") or []
        exclude_prefixes = tuple(
            str(prefix)
            for prefix in (raw_excludes if isinstance(raw_excludes, list) else [])
            if str(prefix).strip()
        )
        available = count is not None and count > 0
        error: str | None = None
        if count is None:
            try:
                exists = chapter_dir.is_dir()
            except OSError:
                exists = False
            if not exists:
                error = f"Registered chapter directory is not available: {chapter_dir}."
            else:
                error = (
                    f"Registered chapter directory has no files matching "
                    f"{pattern!r}: {chapter_dir}."
                )
        books[str(project_id)] = WriterBookDefinition(
            project_id=str(project_id),
            title=_title_for(str(project_id), entry),
            project_root=project_root,
            repo_path=repo_path,
            chapter_dir=chapter_dir,
            chapter_pattern=pattern,
            metadata_dir=metadata_dir,
            manuscript=manuscript,
            profile=profile,
            publication_status=publication_status,
            preview_route=preview_route,
            tags=tags,
            active=bool(entry.get("active", True)),
            available=available,
            chapter_count=count,
            error=error,
            validation_checks=validation_checks,
            human_approval_required=human_approval_required,
            validation_enabled=validation_enabled,
            exclude_prefixes=exclude_prefixes,
        )
    return WriterRegistrySnapshot(
        source_path=source,
        mtime_ns=mtime_ns,
        books=books,
        errors=errors,
        skipped_non_book=skipped,
    )
