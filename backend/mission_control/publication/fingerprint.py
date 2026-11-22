"""Manuscript provenance and fingerprints (MC-PUBLISH-02, Phase D).

Scope ``manuscript-v1``: top-level files of the configured chapter directory
matching the book's chapter pattern, ordered by filename, content-hashed with
CRLF normalized to LF (identical to Mission/Workbench ``build_snapshot`` so
fingerprints are directly comparable to stored assessment revisions).

Deliberately excluded: subdirectories, generated artifacts (``out/``,
``dist/``, ``public/``), absolute machine paths, mtimes, Git state (recorded
separately — a commit may touch docs/tests without changing the manuscript,
and uncommitted edits may change it without moving HEAD).

A fingerprint proves content correspondence within the defined scope only;
it proves nothing about editorial completeness.
"""

from __future__ import annotations

import fnmatch
import hashlib
import subprocess
from pathlib import Path
from typing import Any

SCOPE_VERSION = "manuscript-v1"
ALGORITHM = "sha256-crlf-lf"

MAX_FILES = 5000
MAX_TOTAL_BYTES = 200_000_000


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def fingerprint_manuscript(
    chapter_dir: Path | str | None,
    pattern: str = "*.md",
) -> dict[str, Any]:
    """Reproducible fingerprint of the chapter scope. Read-only, bounded."""
    if chapter_dir is None:
        return {"ok": False, "diagnostics": "No chapter directory configured."}
    root = Path(chapter_dir)
    try:
        if not root.is_dir():
            return {
                "ok": False,
                "root": str(root),
                "diagnostics": f"Chapter directory is not available: {root}.",
            }
    except OSError as exc:
        return {"ok": False, "root": str(root), "diagnostics": f"Cannot access {root}: {exc}."}
    try:
        entries = sorted(
            (p for p in root.iterdir() if p.is_file() and fnmatch.fnmatch(p.name, pattern)),
            key=lambda p: p.name,
        )
    except OSError as exc:
        return {"ok": False, "root": str(root), "diagnostics": f"Cannot list {root}: {exc}."}
    if not entries:
        return {
            "ok": False,
            "root": str(root),
            "algorithm": ALGORITHM,
            "scope_version": SCOPE_VERSION,
            "diagnostics": f"No files matching {pattern!r} in {root}.",
        }
    if len(entries) > MAX_FILES:
        return {
            "ok": False,
            "root": str(root),
            "diagnostics": f"Scope exceeds {MAX_FILES} files; refusing to hash.",
        }
    rows: list[str] = []
    total = 0
    unreadable: list[str] = []
    for path in entries:
        try:
            raw = path.read_bytes()
        except OSError:
            unreadable.append(path.name)
            continue
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            return {
                "ok": False,
                "root": str(root),
                "diagnostics": f"Scope exceeds {MAX_TOTAL_BYTES} bytes; refusing to hash.",
            }
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            unreadable.append(path.name)
            continue
        rows.append(f"{path.name}:{_sha_text(text)}")
    if unreadable:
        return {
            "ok": False,
            "root": str(root),
            "diagnostics": f"Unreadable files in scope: {', '.join(sorted(unreadable))}.",
        }
    fingerprint = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "root": str(root),
        "algorithm": ALGORITHM,
        "scope_version": SCOPE_VERSION,
        "pattern": pattern,
        "file_count": len(rows),
        "fingerprint": fingerprint,
    }


def writer_source_digest(text: str) -> str:
    """Replicate Writer's chapter source digest for exact comparison.

    Writer strips its own frontmatter tables (``[writer.validation]`` and the
    configured status key) then hashes raw text WITHOUT CRLF normalization,
    prefixed with ``sha256:``. Any divergence from Writer's implementation
    fails safe: digests simply won't match and freshness stays ``unknown``.
    """
    import re as _re

    match = _re.match(
        r"\A(?P<fence>\+\+\+|---)\r?\n(?P<body>.*?)(?:\r?\n)(?P=fence)\r?\n",
        text,
        _re.S,
    )
    if match:
        fence = match.group("fence")
        body = match.group("body")
        rest = text[match.end():]
        kept: list[str] = []
        skip_table = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                skip_table = stripped.casefold() in ("[writer.validation]", "[validation]")
                if not skip_table:
                    kept.append(line)
                continue
            if skip_table:
                continue
            name = stripped.split("=")[0].strip().casefold() if "=" in stripped else ""
            if name in ("chapter_status",):
                continue
            kept.append(line)
        normalized = fence + "\n" + "\n".join(kept).strip() + "\n" + fence + "\n" + rest
    else:
        normalized = text
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def git_revision(repo_path: Path | str | None, timeout: int = 10) -> dict[str, Any]:
    """Record Git HEAD + worktree dirtiness separately from content identity."""
    if repo_path is None:
        return {"ok": False, "diagnostics": "No repository path configured."}
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "diagnostics": f"Git is not usable here: {exc}."}
    if head.returncode != 0:
        return {"ok": False, "diagnostics": (head.stderr or "not a git repository").strip()}
    try:
        status = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=timeout,
        )
        dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        dirty = None
    return {"ok": True, "head": head.stdout.strip(), "dirty": dirty}
