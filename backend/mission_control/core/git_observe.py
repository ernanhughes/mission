"""Read-only Git observation.

Only status and metadata commands are used. This module never fetches, pulls,
resets, cleans, checks out or otherwise mutates a repository.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _run_git(repo: Path, args: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Git observation failed for %s: %s", repo, exc)
        return None


def observe_git(repo_path: str, timeout: float = 5.0) -> dict[str, Any]:
    repo = Path(repo_path)
    result: dict[str, Any] = {
        "accessible": repo.exists(),
        "is_git": (repo / ".git").exists(),
        "branch": None,
        "commit": None,
        "last_commit_at": None,
        "dirty": None,
        "error": None,
    }
    if not repo.exists():
        result["error"] = "Repository path does not exist"
        return result
    if not result["is_git"]:
        return result

    status = _run_git(repo, ["status", "--porcelain=v1", "--untracked-files=no", "--branch"], timeout)
    if status is None:
        result["error"] = "Git status timed out or failed"
        return result
    if status.returncode != 0:
        result["error"] = (status.stderr or "Git status failed").strip()[:500]
        return result
    lines = status.stdout.splitlines()
    for line in lines:
        if line.startswith("## "):
            branch = line[3:].split("...", 1)[0]
            result["branch"] = branch.split(" ", 1)[0]
        elif line.strip():
            result["dirty"] = True
    if result["dirty"] is None:
        result["dirty"] = False

    commit = _run_git(repo, ["rev-parse", "HEAD"], timeout)
    if commit and commit.returncode == 0:
        result["commit"] = commit.stdout.strip()
    last = _run_git(repo, ["log", "-1", "--format=%cI"], timeout)
    if last and last.returncode == 0:
        result["last_commit_at"] = last.stdout.strip() or None
    return result
