"""Bounded, cancellable filesystem discovery with read-only Git observation."""

from __future__ import annotations

import fnmatch
import logging
import os
import stat
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mission_control.core.git_observe import observe_git
from mission_control.discovery.classifier import classify, top_level_markers

logger = logging.getLogger(__name__)

EXCLUDED_ALWAYS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


@dataclass(slots=True)
class Candidate:
    path: str
    name: str
    source_root: str
    classification: str
    confidence: float
    evidence: list[str]
    is_git: bool
    accessible: bool = True
    git: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class ScanResult:
    candidates: list[Candidate] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    skipped_links: list[str] = field(default_factory=list)
    excluded_count: int = 0
    truncated: bool = False
    cancelled: bool = False
    elapsed_seconds: float = 0.0
    scanned_directories: int = 0


def _is_excluded(name: str, relative: str, patterns: list[str]) -> bool:
    lower_name = name.casefold()
    lower_rel = relative.replace("\\", "/").casefold()
    for pattern in patterns:
        normalized = pattern.replace("\\", "/").casefold()
        if fnmatch.fnmatch(lower_name, normalized) or fnmatch.fnmatch(lower_rel, normalized):
            return True
    return lower_name in EXCLUDED_ALWAYS


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _has_candidate_markers(path: Path) -> bool:
    markers = top_level_markers(path)
    return bool(markers) or (path / ".git").exists()


def scan_roots(
    roots: list[str],
    *,
    exclusion_patterns: list[str],
    max_depth: int = 1,
    max_candidates: int = 500,
    timeout_seconds: float = 120.0,
    git_timeout_seconds: float = 5.0,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    started = time.monotonic()
    result = ScanResult()
    seen: set[str] = set()
    cancel_event = cancel_event or threading.Event()

    def timed_out() -> bool:
        return time.monotonic() - started > timeout_seconds

    def add_candidate(path: Path, root: str, depth: int) -> bool:
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key in seen:
            return False
        seen.add(key)
        evidence: list[str] = []
        try:
            info = classify(path)
        except Exception as exc:  # classification must never abort a scan
            logger.warning("Classification failed for %s: %s", path, exc)
            result.errors.append({"path": str(path), "error": f"Classification failed: {exc}"})
            return False
        evidence.extend(info.evidence)
        candidate = Candidate(
            path=str(path.resolve(strict=False)),
            name=path.name,
            source_root=str(Path(root).resolve(strict=False)),
            classification=info.classification,
            confidence=info.confidence,
            evidence=evidence,
            is_git=(path / ".git").exists(),
            accessible=True,
        )
        result.candidates.append(candidate)
        return True

    def walk(directory: Path, root: str, depth: int) -> None:
        if result.cancelled or result.truncated:
            return
        if cancel_event.is_set():
            result.cancelled = True
            return
        if timed_out():
            result.truncated = True
            result.errors.append({"path": str(directory), "error": "Scan time limit reached"})
            return
        if len(result.candidates) >= max_candidates:
            result.truncated = True
            return
        result.scanned_directories += 1
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except (OSError, PermissionError) as exc:
            result.errors.append({"path": str(directory), "error": str(exc)[:300]})
            return
        for entry in entries:
            if cancel_event.is_set():
                result.cancelled = True
                return
            if not entry.is_dir():
                continue
            relative = str(entry.relative_to(Path(root)))
            if _is_excluded(entry.name, relative, exclusion_patterns):
                result.excluded_count += 1
                continue
            if _is_reparse_point(entry):
                result.skipped_links.append(str(entry))
                continue
            candidate = _has_candidate_markers(entry)
            if candidate:
                added = add_candidate(entry, root, depth)
                if added and len(result.candidates) >= max_candidates:
                    result.truncated = True
                    return
                # A repository root is not traversed further: nested worktrees
                # are not separate first-class applications.
                continue
            if depth < max_depth:
                walk(entry, root, depth + 1)
            else:
                # Directory without markers at the configured boundary.
                evidence = [f"No repository/source markers at depth {depth}"]
                key = os.path.normcase(str(entry.resolve(strict=False)))
                if key not in seen:
                    seen.add(key)
                    result.candidates.append(
                        Candidate(
                            path=str(entry.resolve(strict=False)),
                            name=entry.name,
                            source_root=str(Path(root).resolve(strict=False)),
                            classification="unknown",
                            confidence=0.15,
                            evidence=evidence,
                            is_git=False,
                        )
                    )

    for root in roots:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            result.errors.append({"path": root, "error": "Discovery root is missing or not a directory"})
            continue
        if _is_reparse_point(root_path):
            result.skipped_links.append(str(root_path))
            continue
        walk(root_path, root, 0)

    if result.candidates and not cancel_event.is_set():
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(result.candidates)))) as pool:
            futures = {
                pool.submit(observe_git, candidate.path, git_timeout_seconds): candidate
                for candidate in result.candidates
                if candidate.is_git
            }
            for future in as_completed(futures):
                if cancel_event.is_set():
                    result.cancelled = True
                    break
                candidate = futures[future]
                try:
                    candidate.git = future.result()
                    candidate.accessible = bool(candidate.git.get("accessible", True))
                    if candidate.git.get("error"):
                        candidate.evidence.append(f"Git: {candidate.git['error']}")
                except Exception as exc:  # pragma: no cover - defensive isolation
                    candidate.git = {"accessible": True, "error": str(exc)[:300]}
                    result.errors.append({"path": candidate.path, "error": str(exc)[:300]})

    result.candidates.sort(key=lambda item: (item.source_root.casefold(), item.name.casefold()))
    result.elapsed_seconds = round(time.monotonic() - started, 3)
    return result
