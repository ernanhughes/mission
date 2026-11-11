"""Live source observation for cultivation (MC-CULTIVATION-02, numbered files).

Read-only filesystem scanning. No model calls, no writes to the scanned tree,
no network.

Hugo blogs: standalone Markdown files and leaf-bundle ``index.md`` files are
posts; ``_index.md`` section files, attachments and dot-directories are
excluded; TOML (``+++``), YAML (``---``) or JSON front matter is parsed;
``draft = true``, future dates and past expiry dates are not published;
missing or invalid metadata lands in ``unknown``, never silently counted.

Numbered script files (e.g. ``Script001.md``): any Markdown file whose name
starts with a numbered ``Script`` prefix counts as one published item.
Identity is the repo-style relative path; the item date prefers the file's
first git addition commit and falls back to filesystem mtime. Dating reads
the repository only (two read-only git processes per scan, with timeouts);
anything else — Morning files, notes, audio, non-Markdown — is excluded,
not counted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
BLOG_SUFFIXES = {".md", ".markdown"}
LEAF_INDEXES = {"index.md", "index.markdown"}
SECTION_INDEXES = {"_index.md", "_index.markdown"}
MAX_FILES = 20000
#: File names counted as numbered-script items (``Script001.md`` and variants
#: such as ``Script052s.md`` or ``Script036 notes.md``).
NUMBERED_SCRIPT_RE = re.compile(r"^Script\d+", re.IGNORECASE)


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
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""


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


def _as_str_list(value: Any) -> list[str]:
    """Normalize Hugo taxonomy metadata to a clean string list."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text[:120]] if text else []
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for entry in value:
            if isinstance(entry, str) and entry.strip():
                out.append(entry.strip()[:120])
            elif entry is not None:
                text = str(entry).strip()
                if text:
                    out.append(text[:120])
        return out[:50]
    return []


def _taxonomy(meta: dict[str, Any]) -> tuple[list[str], list[str], str]:
    """Extract (categories, tags, description) from lower-cased front matter."""
    categories = _as_str_list(meta.get("categories", meta.get("category")))
    tags = _as_str_list(meta.get("tags", meta.get("tag")))
    description = str(meta.get("description") or "")[:500]
    return categories, tags, description


TECHNOLOGY_TERMS = {
    "technology", "tech", "ai", "agents", "programming", "systems",
    "software", "computer", "data", "engineering", "machine learning",
    "ml", "llm", "ai systems", "ai research", "systems thinking",
    "architecture", "vector", "technical",
}

FINANCE_TERMS = {
    "finance", "financial", "fintech", "economics", "economy",
    "markets", "trading", "investment",
}


def _topic_terms(categories: list[str], tags: list[str]) -> list[str]:
    return [str(term).casefold().strip() for term in [*categories, *tags] if str(term).strip()]


def is_technology_post(categories: list[str], tags: list[str]) -> bool:
    """Preferred subject, not a hard requirement. Deterministic, no AI."""
    for term in _topic_terms(categories, tags):
        if "techn" in term:
            return True
        if term in TECHNOLOGY_TERMS:
            return True
    return False


def is_finance_post(categories: list[str], tags: list[str]) -> bool:
    for term in _topic_terms(categories, tags):
        if "financ" in term or "econ" in term:
            return True
        if term in FINANCE_TERMS:
            return True
    return False


def classify_topic(categories: list[str], tags: list[str]) -> str:
    tech = is_technology_post(categories, tags)
    fin = is_finance_post(categories, tags)
    if tech and fin:
        return "both"
    if tech:
        return "technology"
    if fin:
        return "finance"
    if not categories and not tags:
        return "uncategorized"
    return "other"


def _dublin_now() -> datetime:
    from zoneinfo import ZoneInfo

    try:
        return datetime.now(ZoneInfo("Europe/Dublin"))
    except Exception:  # pragma: no cover - tzdata missing
        return datetime.now(timezone.utc)


def dublin_week_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Monday 00:00 -> Sunday 23:59:59.999 in Europe/Dublin."""
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo("Europe/Dublin")
    except Exception:  # pragma: no cover
        tz = timezone.utc  # type: ignore[assignment]
    moment = now or datetime.now(tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    else:
        moment = moment.astimezone(tz)
    monday = (moment - timedelta(days=moment.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999000)
    return monday, sunday


def _classify(path: Path, relpath: str, now: datetime) -> BlogPost | None:
    """Classify one file. Returns None for excluded (non-post) files."""
    name = path.name
    suffix = path.suffix.casefold()
    if name.casefold() in SECTION_INDEXES:
        return None
    if suffix not in BLOG_SUFFIXES:
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
    if name.casefold() in LEAF_INDEXES:
        # A leaf bundle: the directory is the post.
        parent = str(Path(relpath).parent).replace("\\", "/")
        identity = parent if parent != "." else relpath
    if meta is None:
        return BlogPost(identity=identity, title=path.stem, relpath=relpath,
                        state="unknown", reason=error or "missing front matter")
    title = str(meta.get("title") or path.stem)[:300]
    categories, tags, description = _taxonomy(meta)
    draft = meta.get("draft") is True
    date, date_error = _parse_date(meta.get("date", meta.get("publishdate")))
    expiry, _ = _parse_date(meta.get("expirydate"))
    if draft:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="draft", reason="marked draft", date=date, draft=True,
                        categories=categories, tags=tags, description=description)
    if date is not None and date > now:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="draft", reason=f"scheduled for {date.isoformat()}", date=date,
                        categories=categories, tags=tags, description=description)
    if date_error:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="unknown", reason=date_error, date=None,
                        categories=categories, tags=tags, description=description)
    if expiry is not None and expiry <= now:
        return BlogPost(identity=identity, title=title, relpath=relpath,
                        state="draft", reason=f"expired {expiry.isoformat()}", date=date,
                        categories=categories, tags=tags, description=description)
    return BlogPost(identity=identity, title=title, relpath=relpath,
                    state="published", reason=f"{fmt} front matter, dated {date.isoformat()}" if date else f"{fmt} front matter", date=date,
                    categories=categories, tags=tags, description=description)


def _prettify_script_name(stem: str) -> str:
    """Human title from a script filename stem (``Script036 notes``)."""
    return (stem.replace("_", " ").strip() or stem)[:300]


def _git_add_dates(root: Path) -> dict[str, str]:
    """Map repo-relative POSIX path -> oldest addition-commit ISO date.

    Two read-only git processes for the whole tree (rev-parse to confirm the
    source path is the repository root, log for addition commits); returns {}
    when git is unavailable, the directory is not a repository, or any command
    fails — callers fall back to filesystem mtime. Never writes.
    """
    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, shell=False, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Git toplevel lookup failed for %s: %s", root, exc)
        return {}
    if toplevel is None or toplevel.returncode != 0:
        return {}
    try:
        if Path((toplevel.stdout or "").strip()).resolve() != root.resolve():
            return {}
    except OSError:
        return {}
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", "--diff-filter=A", "--reverse",
             "--name-only", "--pretty=format:%aI", "--", "."],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, shell=False, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Git add-date scan failed for %s: %s", root, exc)
        return {}
    if proc is None or proc.returncode != 0:
        return {}
    dates: dict[str, str] = {}
    current: str | None = None
    # Output is one ISO date line per addition commit followed by that
    # commit's added paths; a date line always starts a new group.
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            current = datetime.fromisoformat(line.replace("Z", "+00:00")).isoformat()
            continue
        except ValueError:
            pass
        if current is not None:
            # First (oldest, thanks to --reverse) addition wins.
            dates.setdefault(line.strip('"'), current)
    return dates


def scan_numbered_files(root: str | Path) -> BlogScan:
    """Count numbered script files (``Script001.md`` and variants).

    Every matching file is one published item; anything else is excluded,
    never counted. Identity is the relative path; the item date prefers the
    file's first git addition commit and falls back to filesystem mtime.
    """
    base = Path(root)
    scan = BlogScan()
    if not base.is_dir():
        scan.errors.append({"path": str(base), "error": "Source directory is missing or not a directory"})
        return scan
    add_dates = _git_add_dates(base)
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
                if candidate.suffix.casefold() != ".md" or not NUMBERED_SCRIPT_RE.match(candidate.stem):
                    scan.excluded += 1
                    continue
                try:
                    candidate.read_text(encoding="utf-8", errors="strict")
                except (OSError, UnicodeDecodeError) as exc:
                    scan.posts.append(BlogPost(
                        identity=relpath, title=_prettify_script_name(candidate.stem),
                        relpath=relpath, state="unknown",
                        reason=f"unreadable file: {exc.__class__.__name__}"))
                    scan.unknown += 1
                    continue
                try:
                    info = candidate.stat()
                    mtime_ns = info.st_mtime_ns
                    size = info.st_size
                except OSError:
                    mtime_ns, size = 0, 0
                date: datetime | None = None
                raw_add = add_dates.get(relpath)
                if raw_add:
                    try:
                        date = datetime.fromisoformat(raw_add.replace("Z", "+00:00"))
                    except ValueError:
                        date = None
                if date is None and mtime_ns:
                    date = datetime.fromtimestamp(mtime_ns / 1e9, tz=timezone.utc)
                post = BlogPost(
                    identity=relpath, title=_prettify_script_name(candidate.stem),
                    relpath=relpath, state="published",
                    reason=(f"numbered script, dated {date.isoformat()}" if date
                            else "numbered script"),
                    date=date,
                    fingerprint=_fingerprint_file(candidate, relpath, mtime_ns, size),
                    mtime_ns=mtime_ns, size=size)
                scan.posts.append(post)
                scan.published += 1
    except OSError as exc:
        scan.errors.append({"path": str(base), "error": str(exc)[:300]})
    digest = hashlib.sha256()
    for post in sorted(scan.posts, key=lambda item: item.identity):
        digest.update(post.identity.encode("utf-8"))
        digest.update(post.fingerprint.encode("utf-8"))
        digest.update(post.state.encode("utf-8"))
    scan.fingerprint = digest.hexdigest()[:24]
    return scan


def scan_hugo_blog(root: str | Path, *, now: datetime | None = None) -> BlogScan:
    """Walk a Hugo content section and classify every candidate post file."""
    base = Path(root)
    scan = BlogScan()
    moment = now or datetime.now(timezone.utc)
    if not base.is_dir():
        scan.errors.append({"path": str(base), "error": "Source directory is missing or not a directory"})
        return scan
    seen: set[str] = set()
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
                if candidate.suffix.casefold() not in BLOG_SUFFIXES or candidate.name.casefold() in SECTION_INDEXES:
                    scan.excluded += 1
                    continue
                post = _classify(candidate, relpath, moment)
                if post is None:
                    scan.excluded += 1
                    continue
                # Duplicate prevention: leaf bundles and standalone files can map
                # to the same identity (e.g. ``foo/index.md`` + ``foo/index.markdown``).
                # Keep the first observation, count the rest as excluded, never double-count.
                if post.identity in seen:
                    scan.excluded += 1
                    scan.errors.append({"path": relpath,
                                        "error": f"Duplicate post identity '{post.identity}'; kept first observation"})
                    continue
                seen.add(post.identity)
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


def blog_observation(scan: BlogScan, *, now: datetime | None = None) -> dict[str, Any]:
    """Enriched, deterministic observation from a Hugo scan.

    Keeps the legacy ``published``/``drafts``/``unknown``/``excluded``/
    ``candidates`` keys for backwards compatibility and adds the cultivation
    dimensions: scheduled, technology/finance, Dublin weekly windows, latest
    publication and recent posts. No AI, no filesystem access.
    """
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo("Europe/Dublin")
    except Exception:  # pragma: no cover
        tz = timezone.utc  # type: ignore[assignment]
    moment = now or datetime.now(tz)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz)
    else:
        moment = moment.astimezone(tz)
    week_start, week_end = dublin_week_range(moment)
    prev_start = week_start - timedelta(days=7)
    prev_end = week_start - timedelta(seconds=1)

    def _in_dublin(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz)

    scheduled = 0
    tech = 0
    finance = 0
    latest_at: datetime | None = None
    latest_post: BlogPost | None = None
    this_week = 0
    last_week = 0
    this_week_posts: list[BlogPost] = []
    for post in scan.posts:
        if post.state == "draft" and post.reason.startswith("scheduled for"):
            scheduled += 1
        if post.state != "published":
            continue
        if is_technology_post(post.categories, post.tags):
            tech += 1
        if is_finance_post(post.categories, post.tags):
            finance += 1
        local = _in_dublin(post.date)
        if local is None:
            continue
        if latest_at is None or (post.date is not None and post.date > latest_at):
            latest_at = post.date
            latest_post = post
        if week_start <= local <= week_end:
            this_week += 1
            this_week_posts.append(post)
        elif prev_start <= local <= prev_end:
            last_week += 1

    published_sorted = sorted(
        (p for p in scan.posts if p.state == "published" and p.date is not None),
        key=lambda p: p.date,  # type: ignore[arg-type]
        reverse=True,
    )
    recent: list[dict[str, Any]] = []
    for post in published_sorted[:10]:
        local = _in_dublin(post.date)
        recent.append({
            "identity": post.identity,
            "title": post.title,
            "relpath": post.relpath,
            "date": post.date.isoformat() if post.date else None,
            "date_dublin": local.isoformat() if local else None,
            "categories": list(post.categories),
            "tags": list(post.tags),
            "topic": classify_topic(post.categories, post.tags),
        })
    observed: dict[str, Any] = {
        "published": scan.published,
        "drafts": scan.drafts,
        "unknown": scan.unknown,
        "excluded": scan.excluded,
        "candidates": scan.candidates,
        "errors": scan.errors[:20],
        "fingerprint": scan.fingerprint,
        # Enriched cultivation dimensions.
        "scheduled": scheduled,
        "tech_published": tech,
        "finance_published": finance,
        "latest_published_at": latest_at.isoformat() if latest_at else None,
        "latest_published_title": latest_post.title if latest_post else None,
        "latest_published_relpath": latest_post.relpath if latest_post else None,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_start_date": week_start.date().isoformat(),
        "week_end_date": week_end.date().isoformat(),
        "timezone": "Europe/Dublin",
        "this_week": this_week,
        "last_week": last_week,
        "recent_posts": recent,
        "qualifying_this_week": [
            {"identity": p.identity, "title": p.title, "relpath": p.relpath,
             "date": p.date.isoformat() if p.date else None} for p in sorted(
                this_week_posts, key=lambda p: p.date or datetime.min.replace(tzinfo=timezone.utc))
        ],
    }
    return observed
