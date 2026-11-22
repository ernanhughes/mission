"""Mission-side Living Book orchestration.

The project page owns the book identity, the reading room owns presentation, and ALIVE
owns source custody, reading state, notes, conversations and model receipts.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.living_book.client import (
    AliveClient,
    LivingBookError,
    LivingBookUnavailable,
)
from mission_control.living_book.quality import (
    build_quality_context,
    quality_summary,
)
from mission_control.models import Application, Book, Project, ProjectRepository, Repository

CHAPTER_FILE = re.compile(r"^\d{2,3}-.*\.md$", re.IGNORECASE)
IMAGE_SUFFIXES = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
PROJECT_REVIEW_TTL = 30 * 24 * 3600


class LivingBookProblem(RuntimeError):
    def __init__(self, message: str, *, state: str = "error", status: int = 409):
        super().__init__(message)
        self.state = state
        self.status = status


def _norm(path: str | None) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(path))


def _client(session: Session, settings) -> AliveClient:
    application = session.get(Application, "alive")
    base_url = settings.alive_url
    if application is not None and isinstance(application.adapter_config, dict):
        base_url = str(application.adapter_config.get("base_url") or base_url)
    return AliveClient(base_url)


def _chapter_dir(path: str) -> bool:
    try:
        with os.scandir(path) as entries:
            return any(entry.is_file() and CHAPTER_FILE.match(entry.name) for entry in entries)
    except OSError:
        return False


def _quick_size(path: str, *, max_files: int = 20_000, max_bytes: int = 500_000_000):
    files = 0
    total = 0
    truncated = False
    try:
        for root, directories, names in os.walk(path, followlinks=False):
            directories[:] = [
                item
                for item in directories
                if item not in {".git", "node_modules", ".venv", "venv", "__pycache__"}
                and not os.path.islink(os.path.join(root, item))
            ]
            for name in names:
                full = os.path.join(root, name)
                try:
                    info = os.stat(full, follow_symlinks=False)
                except OSError:
                    continue
                files += 1
                total += int(info.st_size)
                if files >= max_files or total >= max_bytes:
                    return {
                        "files": files,
                        "bytes": total,
                        "truncated": True,
                        "reason": "The folder exceeds the preview limit.",
                    }
    except OSError as error:
        return {"files": files, "bytes": total, "truncated": True, "reason": str(error)}
    return {"files": files, "bytes": total, "truncated": truncated, "reason": ""}


def _project_context(session: Session, project_id: str) -> dict[str, Any]:
    project = session.get(Project, project_id)
    if project is None:
        raise LivingBookProblem("Project not found.", state="not_found", status=404)
    book = session.scalar(select(Book).where(Book.project_id == project_id))
    if book is None:
        raise LivingBookProblem(
            "This project has no book workspace, so there is no manuscript to read.",
            state="not_a_book",
            status=409,
        )
    manuscript_roots = [
        str(Path(path).expanduser().resolve())
        for path in (book.manuscript_paths or [])
        if path and os.path.isdir(path) and _chapter_dir(path)
    ]
    if not manuscript_roots:
        attempted = list(book.manuscript_paths or [])
        detail = (
            "No manuscript folder with numbered chapter files is configured for this book."
        )
        if attempted:
            detail = (
                f"{detail} Checked {len(attempted)} configured "
                f"path(s): {attempted[0]}"
                + (f" (+{len(attempted) - 1} more)" if len(attempted) > 1 else "")
                + ". Refresh the Writer registry (POST /api/books/writer-sync) "
                "to repair the chapter directory."
            )
        else:
            detail = (
                f"{detail} No manuscript paths are stored for project "
                f"{project_id!r}. Refresh the Writer registry "
                "(POST /api/books/writer-sync) to repair the chapter directory."
            )
        raise LivingBookProblem(
            detail,
            state="no_manuscript",
            status=409,
        )
    repositories = session.execute(
        select(Repository, ProjectRepository.role)
        .join(ProjectRepository, ProjectRepository.repository_id == Repository.id)
        .where(ProjectRepository.project_id == project_id)
        .order_by(ProjectRepository.role, Repository.name)
    ).all()
    return {
        "project": project,
        "book": book,
        "manuscript_root": manuscript_roots[0],
        "repositories": [(repo, role) for repo, role in repositories],
    }


def _candidates(context: dict[str, Any]) -> list[dict[str, Any]]:
    manuscript_root = context["manuscript_root"]
    manuscript_norm = _norm(manuscript_root)
    candidates: list[dict[str, Any]] = [
        {
            "kind": "manuscript",
            "path": manuscript_root,
            "manuscript_root": manuscript_root,
            "available": True,
            "recommended": True,
            "detail": "Only the manuscript chapter folder.",
        }
    ]
    for repository, role in context["repositories"]:
        path = str(Path(repository.path).expanduser().resolve())
        if not os.path.isdir(path) or _norm(path) == manuscript_norm:
            continue
        try:
            if os.path.commonpath([manuscript_norm, _norm(path)]) != _norm(path):
                continue
        except ValueError:
            continue
        size = _quick_size(path)
        has_evidence = any(
            os.path.isdir(os.path.join(path, name))
            for name in ("planning", "editorial", "research", "experiments")
        )
        candidates.append(
            {
                "kind": "repository",
                "path": path,
                "manuscript_root": manuscript_root,
                "available": not size["truncated"] and size["files"] > 0,
                "recommended": False,
                "files": size["files"],
                "bytes": size["bytes"],
                "detail": (
                    f"Whole book repository, {size['files']} files, "
                    f"{size['bytes'] / 1_000_000:.1f} MB"
                    + (" including editorial/quality evidence." if has_evidence else ".")
                ),
                "reason": size["reason"],
                "role": role,
            }
        )
        if has_evidence and candidates[-1]["available"]:
            candidates[-1]["recommended"] = True
            candidates[0]["recommended"] = False
    candidates.sort(key=lambda item: (not item["recommended"], item["kind"] != "manuscript"))
    return candidates


def _registered_book_async(client: AliveClient, manuscript_root: str):
    async def find():
        listed = await client.list_books(manuscript_root)
        wanted = _norm(manuscript_root)
        for book in listed.get("books", []):
            if _norm(book.get("manuscript_root")) == wanted:
                return book
        return None

    return find()


async def _book_for(client: AliveClient, context: dict[str, Any]) -> dict[str, Any]:
    book = await _registered_book_async(client, context["manuscript_root"])
    if book is None:
        raise LivingBookProblem(
            "This book is not connected to ALIVE yet.",
            state="not_connected",
            status=409,
        )
    return book


def _base_status(context: dict[str, Any], session: Session, settings) -> dict[str, Any]:
    quality = quality_summary(session, settings, context["project"].id)
    return {
        "project_id": context["project"].id,
        "project_name": context["project"].name,
        "book_title": context["book"].title,
        "manuscript_root": context["manuscript_root"],
        "quality": quality,
        "candidates": [],
    }


async def status(session: Session, settings, project_id: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    base = _base_status(context, session, settings)
    try:
        client = _client(session, settings)
        health = await client.health()
        base["alive_url"] = client.base_url
        if health.get("status") == "unavailable":
            return {
                **base,
                "available": False,
                "state": "unavailable",
                "detail": health.get("detail") or "ALIVE is not running.",
                "book": None,
            }
        book = await _registered_book_async(client, context["manuscript_root"])
        if book is None:
            return {
                **base,
                "available": True,
                "state": "not_connected",
                "detail": "Connect this book to ALIVE to open the reading room.",
                "book": None,
                "candidates": _candidates(context),
            }
        detail = await client.book(book["id"])
        state = "ready"
        if not detail.get("ready"):
            state = "needs_source"
        elif not (detail.get("model") or {}).get("ready"):
            state = "model_unavailable"
        return {
            **base,
            "available": True,
            "state": state,
            "detail": detail.get("error") or "",
            "book": detail,
        }
    except LivingBookUnavailable as error:
        return {
            **base,
            "available": False,
            "state": "unavailable",
            "detail": str(error),
            "book": None,
        }
    except LivingBookError as error:
        return {
            **base,
            "available": False,
            "state": "error",
            "detail": str(error),
            "book": None,
        }


async def candidates(session: Session, project_id: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    return {
        "project_id": project_id,
        "manuscript_root": context["manuscript_root"],
        "candidates": _candidates(context),
    }


async def connect_preview(session: Session, settings, project_id: str, root: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    candidate = next(
        (item for item in _candidates(context) if _norm(item["path"]) == _norm(root)),
        None,
    )
    if candidate is None:
        raise LivingBookProblem(
            "That folder is not an eligible source for this book.",
            state="invalid_source",
            status=422,
        )
    if not candidate["available"]:
        raise LivingBookProblem(
            candidate.get("reason") or "That folder is too large for the source preview.",
            state="source_too_large",
            status=422,
        )
    client = _client(session, settings)
    preview = await client.preview_source(candidate["path"])
    return {
        "candidate": candidate,
        "preview": preview,
        "manuscript_root": context["manuscript_root"],
    }


async def connect(
    session: Session,
    settings,
    project_id: str,
    root: str,
    *,
    approve: bool,
    label: str | None = None,
) -> dict[str, Any]:
    if not approve:
        raise LivingBookProblem(
            "Read-only source access must be explicitly approved.",
            state="approval_required",
            status=403,
        )
    context = _project_context(session, project_id)
    candidate = next(
        (item for item in _candidates(context) if _norm(item["path"]) == _norm(root)),
        None,
    )
    if candidate is None or not candidate["available"]:
        raise LivingBookProblem(
            "That folder is not an eligible source for this book.",
            state="invalid_source",
            status=422,
        )
    client = _client(session, settings)
    try:
        preview = await client.preview_source(candidate["path"])
        confirmed_root = str(preview.get("root") or candidate["path"])
        registered = await client.register_source(
            (label or context["project"].name)[:120],
            candidate["path"],
            confirmed_root,
        )
        capture = registered.get("capture") or {}
        if not capture.get("id") or not capture.get("content_sha256"):
            raise LivingBookProblem(
                "ALIVE did not return a complete source capture.",
                state="register_failed",
                status=502,
            )
        approval = await client.approve_source(
            str(capture["id"]),
            content_sha256=str(capture["content_sha256"]),
            request_id=f"mission-living-book-{project_id}-{capture['id']}"[:100],
            ttl_seconds=PROJECT_REVIEW_TTL,
        )
        book = await client.register_book(
            {
                "approval_ref": approval["id"],
                "source_root": confirmed_root,
                "manuscript_root": context["manuscript_root"],
                "title": context["book"].title[:200],
                "label": (label or context["project"].name)[:120],
            }
        )
    except LivingBookUnavailable as error:
        raise LivingBookProblem(
            str(error), state="alive_unavailable", status=503
        ) from None
    except LivingBookError as error:
        if (error.status or 0) >= 500:
            raise LivingBookProblem(
                f"ALIVE failed internally (HTTP {error.status}) during connect: {error}. "
                + (
                    f"ALIVE reference {error.correlation_id}. "
                    if error.correlation_id
                    else ""
                )
                + "Inspect the ALIVE backend log under Mission Control data/logs "
                "(proc-*.log), or restart ALIVE from Applications and try again.",
                state="alive_error",
                status=502,
            ) from None
        raise
    return {
        "book": book,
        "capture": capture,
        "approval": approval,
        "candidate": candidate,
    }


async def book_detail(session: Session, settings, project_id: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.book(book["id"])


async def chapter(session: Session, settings, project_id: str, chapter_id: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.chapter(book["id"], chapter_id)


async def set_reading(
    session: Session, settings, project_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.reading(book["id"], body)


async def annotations(session: Session, settings, project_id: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.annotations(book["id"])


async def add_annotation(
    session: Session, settings, project_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.add_annotation(book["id"], body)


async def remove_annotation(
    session: Session, settings, project_id: str, annotation_id: str
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.remove_annotation(book["id"], annotation_id)


async def note(
    session: Session,
    settings,
    project_id: str,
    chapter_id: str,
    *,
    regenerate: bool = False,
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    quality = build_quality_context(session, settings, project_id, chapter_id)
    return await client.build_note(
        book["id"],
        chapter_id,
        {"quality_context": quality, "regenerate": regenerate},
    )


async def read_note(
    session: Session, settings, project_id: str, chapter_id: str
) -> dict[str, Any] | None:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.note(book["id"], chapter_id)


async def ask(session: Session, settings, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    chapter_id = body.get("chapter_id")
    quality = build_quality_context(session, settings, project_id, chapter_id)
    return await client.ask(
        book["id"],
        {
            "message": body["message"],
            "chapter_id": chapter_id,
            "scope": body.get("scope", "chapter"),
            "selection": body.get("selection"),
            "conversation_id": body.get("conversation_id"),
            "idempotency_key": body["idempotency_key"],
            "quality_context": quality,
        },
    )


async def conversation(
    session: Session, settings, project_id: str, conversation_id: str
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.conversation(book["id"], conversation_id)


async def represent(
    session: Session, settings, project_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.represent(
        book["id"],
        {
            "chapter_id": body.get("chapter_id"),
            "task": body.get("task", "explain"),
            "quote": body.get("quote"),
            "start": body.get("start"),
            "end": body.get("end"),
            "conversation_id": body.get("conversation_id"),
            "idempotency_key": body["idempotency_key"],
        },
    )


async def representations(
    session: Session, settings, project_id: str, chapter_id: str | None
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.representations(book["id"], chapter_id)


async def representation(
    session: Session, settings, project_id: str, representation_id: str
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.representation(book["id"], representation_id)


async def reject_representation(
    session: Session, settings, project_id: str, representation_id: str
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.reject_representation(book["id"], representation_id)


async def quality(
    session: Session, settings, project_id: str, chapter_id: str | None
) -> dict[str, Any]:
    _project_context(session, project_id)
    return build_quality_context(session, settings, project_id, chapter_id)


async def refresh(session: Session, settings, project_id: str) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.refresh(book["id"])


async def revoke_session(
    session: Session, settings, project_id: str, consent_ref: str
) -> dict[str, Any]:
    context = _project_context(session, project_id)
    client = _client(session, settings)
    book = await _book_for(client, context)
    return await client.revoke_session(book["id"], consent_ref)


def asset(session: Session, project_id: str, path: str) -> tuple[Path, str]:
    context = _project_context(session, project_id)
    relative = path.replace("\\", "/").lstrip("/")
    if not relative or "\x00" in relative or ".." in Path(relative).parts or ":" in relative:
        raise LivingBookProblem("Invalid book asset path.", state="invalid_asset", status=422)
    suffix = Path(relative).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise LivingBookProblem(
            "Only book images can be served.", state="invalid_asset", status=422
        )
    roots: list[Path] = [Path(context["manuscript_root"])]
    for repository, _role in context["repositories"]:
        root = Path(repository.path)
        roots.extend([root / "public", root / "static"])
        if relative.startswith("images/"):
            roots.append(root)
    for root in roots:
        try:
            candidate = (root / relative).resolve(strict=False)
            root_resolved = root.resolve(strict=False)
        except OSError:
            continue
        if os.path.commonpath([_norm(str(candidate)), _norm(str(root_resolved))]) != _norm(
            str(root_resolved)
        ):
            continue
        if candidate.is_file():
            return candidate, IMAGE_SUFFIXES[suffix]
    raise LivingBookProblem("Book image not found.", state="not_found", status=404)
