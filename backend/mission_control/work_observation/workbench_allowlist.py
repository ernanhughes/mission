"""Workbench evidence allow-list (WORK-OUTCOME-01 W1 entry decision).

Deny-by-default. Only explicitly validated structured evidence records may be
ingested; raw prompts/replies, manuscript text, engine logs, credentials and
bulk fixtures are never ingested even if present. Absolute host paths are
relativized to ``project_id:chapter_file`` at the boundary.

Full format inventory: W1-ENTRY-GATE §2 (this commission verified keys).
"""

from __future__ import annotations

import re
from pathlib import Path

# Relative-path patterns (POSIX or Windows separators) under a Workbench home.
ALLOWED_PATTERNS = (
    r"editorial-decisions\.jsonl$",
    r"editorial-candidates\.jsonl$",
    r"preferences\.json$",
    r"instance\.json$",
    r"active\.json$",
    r"ledgers/[^/]+\.jsonl$",
    r"runs/metadata-book/[^/]+\.json$",
    r"runs/metadata-book/[^/]+\.events\.jsonl$",
    r"metadata-book-runs\.jsonl$",
    r"[^/]*publication-preflight\.json$",
    r"activity/workbench\.jsonl$",
    r"errors/events\.jsonl$",
    r"errors/groups\.json$",
    r"scores\.jsonl$",
)

_ALLOWED_RES = [re.compile(p, re.IGNORECASE) for p in ALLOWED_PATTERNS]

# Projections: which top-level keys survive per allow-listed record kind.
LEDGER_FIELDS = ("event", "proposal", "paragraph", "commit", "operation",
                 "undoes", "experiment", "candidate", "ts")

DENIED_HINTS = (".prompt.txt", ".reply.txt", "sessions/", "sidecar.json",
                ".bundle", ".patch", ".env", "token")


def normalize_home_path(value: str) -> str:
    return value.replace("\\", "/")


def is_allowed(home_relative_path: str) -> bool:
    """True only for explicitly allow-listed structured evidence paths."""
    rel = normalize_home_path(home_relative_path).lstrip("/")
    lowered = rel.lower()
    if any(hint in lowered for hint in DENIED_HINTS):
        return False
    return any(rx.search(rel) for rx in _ALLOWED_RES)


def relativize(path_value: str, home: Path | str = "") -> str:
    """Reduce an absolute host path to a portable ``project:file``-style ref.

    W1 keeps the file name plus parent when the path escapes the home dir;
    callers with a known book root should relativize further. Never returns
    the original absolute path unchanged when it looks like one.
    """
    text = (path_value or "").strip()
    if not text:
        return ""
    norm = text.replace("\\", "/")
    home_norm = str(home).replace("\\", "/").rstrip("/") if home else ""
    if home_norm and norm.lower().startswith(home_norm.lower()):
        return norm[len(home_norm):].lstrip("/")
    if re.match(r"^[A-Za-z]:/", norm):
        parts = norm.split("/")
        return "/".join(parts[-2:]) if len(parts) > 1 else norm
    return norm
