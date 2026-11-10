"""Live source observation for cultivation (MC-CULTIVATION-02).

Read-only filesystem scanning. No model calls, no writes to the scanned tree,
no network. Counts follow the site's actual publication conventions:

- standalone Markdown files and leaf-bundle ``index.md`` files are posts;
- ``_index.md`` section files, attachments and dot-directories are excluded;
- TOML (``+++``), YAML (``---``) or JSON front matter is parsed;
- ``draft = true``, future dates and past expiry dates are not published;
- missing or invalid metadata lands in ``unknown``, never silently counted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ATTACHMENT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg", ".pdf",
    ".css", ".js", ".json", ".xml", ".txt", ".csv", ".toml",
}
SECTION_INDEX = "_index.md"
LEAF_INDEX = "index.md"
MAX_FILES = 20000


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _parse_front_matter(text: str) -> tuple[str, dict[str, Any] | None, str | None]:
    """Return (format, metadata, error). Only a leading delimiter counts."""
    if text.startswith("+++"):
        end = text.find("\n+++", 3)
        if end == -1:
            return "toml", None, "unterminated TOML front matter"
        try:
            data = tomllib.loads(text[3:end].strip("\n"))
        except tomllib.TOMLDecodeError as exc:
            return "toml", None, f"invalid TOML front matter: {exc}"
        return "toml", _lower_keys(data), None
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end == -1:
            return "yaml", None, "unterminated YAML front matter"
        try:
            data = yaml.safe_load(text[3:end].strip("\n")) or {}
        except yaml.YAMLError as exc:
            return "yaml", None, f"invalid YAML front matter: {exc}"
        if not isinstance(data, dict):
            return "yaml", None, "YAML front matter is not a mapping"
        return "yaml", _lower_keys(data), None
    if text.startswith("{"):
        try:
            data, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError as exc:
            return "json", None, f"invalid JSON front matter: {exc}"
        if not isinstance(data, dict):
            return "json", None, "JSON front matter is not an object"
        return "json", _lower_keys(data), None
    return "none", None, "missing front matter"


def _lower_keys(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    return {str(key).lower(): value for key, value in data.items()}


def _parse_date(value: Any) -> tuple[datetime | None, str | None]:
    """Accept datetimes, ISO strings and plain dates (YAML/TOML unquoted dates).

    Git-style numeric tricks do not apply here; the value comes from parsed
    front matter, but an unexpected type is still reported, never guessed.
    """
    from datetime import date as _date

    if value is None or value is False or value == "":
        return None, "missing date"
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, _date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None, f"unparseable date: {value!r}"[:120]
    else:
        return None, f"unexpected date type: {type(value).__name__}"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed, None


@dataclass(slots=True)
class BlogPost:
    identity: str  # repo-style relative POSIX path, stable across scans
    title: str
    relpath: str
    state: str  # published | draft | unknown | excluded
    reason: str
    date: datetime | None = None
    draft: bool = False
    fingerprint: str = ""
    mtime_ns: int = 0
    size: int = 0


@dataclass(slots=True)
class BlogScan:
    posts: list[BlogPost] = field(default_factory=list)
    published: int = 0
    drafts: int = 0
    unknown: int = 0
    excluded: int = 0
    candidates: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    fingerprint: str = ""


def _fingerprint_file(path: Path, relpath: str, mtime_ns: int, size: int) -> str:
    digest = hashlib.sha256()
    digest.update(relpath.encode("utf-8"))
    digest.update(str(mtime_ns).encode("utf-8"))
    digest.update(str(size).encode("utf-8"))
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError as exc:
        logger.debug("Could not hash %s: %s", path, exc)
        return ""
    return digest.hexdigest()[:24]


def _classify(path: Path, relpath: str, now: datetime) -> BlogPost | None:
    """Classify one file. Returns None for excluded (non-post) files."""
    name = path.name
    suffix = path.suffix.casefold()
    if name == SECTION_INDEX:
        return None
    if suffix != ".md":
        return None
    if suffix in ATTACHMENT_SUFFIXES:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        return BlogPost(identity=relpath, title=path.stem, relpath=relpath,
                        state="unknown", reason=f"unreadable file: {exc.__class__.__name__}")
    fmt, meta, error = _parse_front_matter(text)
    identity = relpath
    if name == LEAF_INDEX:
        # A leaf bundle: the directory is the post.
        parent = str(Path(relpath).parent).replace("\\", "/")
        identity = parent if parent != "." else relpath
    if meta is None:
        return BlogPost(identity=identity, title=path.stem, relpath=relpath,
                        state="unknown", reason=error or "missing front matter")
    title = str(meta.get("title") or path.stem)[:300]
    draft = meta.get("draft") is True
    date, date_error = _parse_date(meta.get("date", meta.get("publishdate")))
    expiry, _ = _parse_date(meta.get("expirydate"))
    if draft:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="draft", reason="marked draft", date=date, draft=True)
    if date is not None and date > now:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="draft", reason=f"scheduled for {date.isoformat()}", date=date)
    if date_error:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="unknown", reason=date_error, date=None)
    if expiry is not None and expiry <= now:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="draft", reason=f"expired {expiry.isoformat()}", date=date)
    return BlogPost(identity=identity, title=title, relpath=relpath,
                    state="published", reason=f"{fmt} front matter, dated {date.isoformat()}" if date else f"{fmt} front matter", date=date)


def scan_hugo_blog(root: str | Path, *, now: datetime | None = None) -> BlogScan:
    """Walk a Hugo content section and classify every candidate post file."""
    base = Path(root)
    scan = BlogScan()
    moment = now or datetime.now(timezone.utc)
    if not base.is_dir():
        scan.errors.append({"path": str(base), "error": "Source directory is missing or not a directory"})
        return scan
    try:
        walker = os.walk(base, followlinks=False)
        for directory, dirnames, filenames in walker:
            current = Path(directory)
            if _is_reparse_point(current):
                dirnames[:] = []
                continue
            # Never descend into hidden/tooling directories.
            dirnames[:] = sorted(name for name in dirnames
                                 if not name.startswith(".") and not _is_reparse_point(current / name))
            for filename in sorted(filenames):
                if scan.candidates >= MAX_FILES:
                    scan.errors.append({"path": str(current), "error": "File cap reached; scan truncated"})
                    break
                candidate = current / filename
                if _is_reparse_point(candidate):
                    continue
                relpath = str(candidate.relative_to(base)).replace("\\", "/")
                scan.candidates += 1
                if candidate.suffix.casefold() != ".md" or candidate.name == SECTION_INDEX:
                    scan.excluded += 1
                    continue
                post = _classify(candidate, relpath, moment)
                if post is None:
                    scan.excluded += 1
                    continue
                try:
                    info = candidate.stat()
                    post.mtime_ns = info.st_mtime_ns
                    post.size = info.st_size
                    post.fingerprint = _fingerprint_file(candidate, relpath, post.mtime_ns, post.size)
                except OSError:
                    pass
                scan.posts.append(post)
                if post.state == "published":
                    scan.published += 1
                elif post.state == "draft":
                    scan.drafts += 1
                else:
                    scan.unknown += 1
    except OSError as exc:
        scan.errors.append({"path": str(base), "error": str(exc)[:300]})
    digest = hashlib.sha256()
    for post in sorted(scan.posts, key=lambda item: item.identity):
        digest.update(post.identity.encode("utf-8"))
        digest.update(post.fingerprint.encode("utf-8"))
        digest.update(post.state.encode("utf-8"))
    scan.fingerprint = digest.hexdigest()[:24]
    return scan
