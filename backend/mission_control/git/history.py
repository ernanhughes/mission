"""Read-only Git helpers for the activity index.

Only metadata, log, diff and show commands are used. This module never fetches,
pulls, resets, cleans, checks out or otherwise mutates a repository. Shell
execution is disabled; hook execution is suppressed through the environment.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_SHA_RE = re.compile(r"^[0-9a-f]{4,64}$", re.IGNORECASE)
_FIELD_SEP = "\x1fMCFLD\x1f"
_RECORD_SEP = "\x1eMCREC\x1e"
_TZ_RE = re.compile(r"([+-]\d{2}:?\d{2}|Z)$")


def _tz(value: str) -> str:
    """Extract the numeric timezone offset from a strict-ISO-8601 date.

    Git has no short numeric-tz placeholder (``%az``/``%cz`` are left
    literal), so the offset is taken from the ``%aI``/``%cI`` expansion.
    """
    match = _TZ_RE.search((value or "").strip())
    if not match:
        return ""
    text = match.group(1)
    if text == "Z":
        return "+00:00"
    return text[:3] + ":" + text[-2:] if ":" not in text else text

_BASE_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key.upper() in {"PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL"}}
    env.update(_BASE_ENV)
    return env


def validate_sha(value: str, *, field: str = "sha") -> str:
    text = (value or "").strip().lower()
    if not _SHA_RE.match(text):
        raise ValueError(f"{field} must be a hex commit identifier")
    return text


def run_git(repo: str | Path, args: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "-c", "core.hooksPath=", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
            env=_env(),
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Git command failed for %s: %s", repo, exc)
        return None


@dataclass(slots=True)
class RepoIdentity:
    toplevel: str
    git_dir: str
    common_dir: str
    repo_uid: str
    is_bare: bool = False
    is_shallow: bool = False
    is_worktree: bool = False


def resolve_identity(path: str) -> RepoIdentity | None:
    repo = Path(path)
    if not repo.exists():
        return None
    proc = run_git(repo, ["rev-parse", "--absolute-git-dir"])
    if proc is None or proc.returncode != 0:
        return None
    git_dir = (proc.stdout or "").strip()
    if not git_dir:
        return None
    bare = run_git(repo, ["rev-parse", "--is-bare-repository"])
    is_bare = bool(bare and bare.returncode == 0 and bare.stdout.strip() == "true")
    toplevel = ""
    if not is_bare:
        top = run_git(repo, ["rev-parse", "--show-toplevel"])
        if top and top.returncode == 0:
            toplevel = (top.stdout or "").strip()
    common = run_git(repo, ["rev-parse", "--git-common-dir"])
    common_dir = (common.stdout.strip() if common and common.returncode == 0 else git_dir)
    if not Path(common_dir).is_absolute():
        common_dir = str((repo / common_dir).resolve(strict=False))
    if not Path(git_dir).is_absolute():
        git_dir = str((repo / git_dir).resolve(strict=False))
    try:
        uid_source = str(Path(common_dir).resolve(strict=False))
    except OSError:
        uid_source = common_dir
    shallow_file = Path(git_dir) / "shallow"
    is_shallow = shallow_file.exists()
    git_path = Path(git_dir)
    is_worktree = git_path.is_file() or (git_path.name == "worktrees")
    if not toplevel and not is_bare:
        toplevel = str(repo.resolve(strict=False))
    repo_uid = hashlib.sha1(uid_source.casefold().encode("utf-8")).hexdigest()[:24]
    return RepoIdentity(
        toplevel=toplevel or str(repo.resolve(strict=False)),
        git_dir=git_dir,
        common_dir=common_dir,
        repo_uid=f"git-{repo_uid}",
        is_bare=is_bare,
        is_shallow=is_shallow,
        is_worktree=is_worktree,
    )


@dataclass(slots=True)
class CommitMeta:
    sha: str
    parents: list[str] = field(default_factory=list)
    author_name: str = ""
    author_email: str = ""
    author_ts: int = 0
    committer_ts: int = 0
    author_tz: str = ""
    committer_tz: str = ""
    subject: str = ""


def _parse_log_output(output: str) -> list[CommitMeta]:
    commits: list[CommitMeta] = []
    for record in output.split(_RECORD_SEP):
        record = record.strip("\r\n")
        if not record.strip():
            continue
        parts = record.split(_FIELD_SEP)
        if len(parts) < 9:
            continue
        sha = parts[0].strip()[-40:]
        try:
            validate_sha(sha)
        except ValueError:
            continue
        parents = [p for p in parts[1].split() if p]
        try:
            author_ts = int(parts[4].strip() or 0)
        except ValueError:
            author_ts = 0
        try:
            committer_ts = int(parts[5].strip() or 0)
        except ValueError:
            committer_ts = 0
        commits.append(
            CommitMeta(
                sha=sha.lower(),
                parents=[p.lower() for p in parents if _SHA_RE.match(p)],
                author_name=parts[2].strip()[:200],
                author_email=parts[3].strip()[:200],
                author_ts=author_ts,
                committer_ts=committer_ts,
                author_tz=_tz(parts[6]),
                committer_tz=_tz(parts[7]),
                subject=parts[8].strip().splitlines()[0][:1000] if parts[8].strip() else "",
            )
        )
    return commits


def log_recent(repo: str, *, since_days: int = 30, max_count: int = 2000, before: str | None = None) -> list[CommitMeta]:
    # NOTE: %az/%cz are not git placeholders (left literal); offsets come from %aI/%cI.
    fmt = _FIELD_SEP.join(["%H", "%P", "%aN", "%aE", "%at", "%ct", "%aI", "%cI", "%s"]) + _RECORD_SEP
    args = ["log", "--all", "--date-order", f"--pretty=format:{fmt}"]
    if before:
        args.append(f"--before={before}")
    else:
        args.append(f"--since={since_days}.days.ago")
    if max_count:
        args.extend(["--max-count", str(max_count)])
    proc = run_git(repo, args, timeout=30.0)
    if proc is None or proc.returncode != 0:
        return []
    return _parse_log_output(proc.stdout or "")


def rev_list_all(repo: str, *, max_count: int | None = None) -> list[str]:
    args = ["rev-list", "--all", "--date-order"]
    if max_count:
        args.extend(["--max-count", str(max_count)])
    proc = run_git(repo, args, timeout=30.0)
    if proc is None or proc.returncode != 0:
        return []
    shas = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip().lower()
        if _SHA_RE.match(text) and len(text) >= 40:
            shas.append(text)
    return shas


def ref_snapshot(repo: str) -> dict[str, str]:
    proc = run_git(repo, ["for-each-ref", "--format=%(objectname) %(refname)", "refs/heads", "refs/remotes", "refs/tags"], timeout=10.0)
    refs: dict[str, str] = {}
    if proc and proc.returncode == 0:
        for line in (proc.stdout or "").splitlines():
            bits = line.strip().split(None, 1)
            if len(bits) == 2:
                refs[bits[1]] = bits[0].lower()
    return refs


def head_info(repo: str) -> tuple[str | None, str | None]:
    branch: str | None = None
    head: str | None = None
    proc = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"], timeout=5.0)
    if proc and proc.returncode == 0:
        value = (proc.stdout or "").strip()
        branch = None if value in ("", "HEAD") else value[:200]
    commit = run_git(repo, ["rev-parse", "HEAD"], timeout=5.0)
    if commit and commit.returncode == 0:
        value = (commit.stdout or "").strip().lower()
        if _SHA_RE.match(value):
            head = value
    return branch, head


def commit_bodies(repo: str, shas: list[str]) -> dict[str, str]:
    if not shas:
        return {}
    fmt = f"%H{_FIELD_SEP}%B{_RECORD_SEP}"
    result: dict[str, str] = {}
    for index in range(0, len(shas), 100):
        chunk = shas[index : index + 100]
        proc = run_git(repo, ["log", "--no-walk", f"--pretty=format:{fmt}", *chunk], timeout=30.0)
        if proc is None or proc.returncode != 0:
            continue
        for record in (proc.stdout or "").split(_RECORD_SEP):
            if not record.strip():
                continue
            bits = record.split(_FIELD_SEP, 1)
            if len(bits) != 2:
                continue
            sha = bits[0].strip()[-40:].lower()
            if _SHA_RE.match(sha):
                result[sha] = bits[1].strip()[:20000]
    return result


def commit_stats(repo: str, shas: list[str]) -> dict[str, tuple[int, int, int, bool, bool]]:
    """Return sha -> (files_changed, insertions, deletions, is_merge, is_root)."""
    if not shas:
        return {}
    result: dict[str, tuple[int, int, int, bool, bool]] = {}
    for index in range(0, len(shas), 50):
        chunk = shas[index : index + 50]
        proc = run_git(
            repo,
            ["show", "--numstat", "--pretty=format:COMMIT:%H PARENTS:%P", "--first-parent", *chunk, "--"],
            timeout=30.0,
        )
        if proc is None or proc.returncode != 0:
            continue
        current: str | None = None
        parents: list[str] = []
        files = 0
        ins = 0
        dels = 0
        binary_files = 0

        def flush() -> None:
            if current:
                result[current] = (files, ins, dels, len(parents) > 1, len(parents) == 0)

        for line in (proc.stdout or "").splitlines():
            if line.startswith("COMMIT:"):
                flush()
                head, _, parent_part = line[7:].partition(" PARENTS:")
                current = head.strip().lower()
                parents = [p for p in parent_part.split() if p]
                files, ins, dels = 0, 0, 0
                binary_files = 0
                continue
            if current is None or not line.strip():
                continue
            bits = line.split("\t")
            if len(bits) < 3:
                continue
            files += 1
            try:
                if bits[0] == "-" and bits[1] == "-":
                    binary_files += 1
                    continue
                ins += int(bits[0])
                dels += int(bits[1])
            except ValueError:
                continue
        flush()
    return result


def branches_for(repo: str, shas: set[str]) -> dict[str, list[str]]:
    refs = ref_snapshot(repo)
    mapping: dict[str, list[str]] = {sha: [] for sha in shas}
    if not refs:
        return mapping
    # Map each ref tip to its history? Expensive. Instead map direct tip matches
    # plus branch containment for HEAD only. Keep cheap: tips + HEAD branch.
    for ref, sha in refs.items():
        if sha in mapping:
            mapping[sha].append(ref.replace("refs/heads/", "").replace("refs/remotes/", "").replace("refs/tags/", "")[:200])
    return mapping


def file_diff(
    repo: str,
    sha: str,
    *,
    parent: str | None = None,
    max_bytes: int = 120_000,
) -> dict:
    sha = validate_sha(sha)
    if parent is not None:
        parent = validate_sha(parent)
    if parent:
        args = ["diff", "--no-ext-diff", "--no-textconv", "-M", "--find-renames", f"{parent}", sha, "--"]
    else:
        # Documented first-parent comparison for merges; root commits show full addition.
        args = ["show", "--pretty=format:", "--no-ext-diff", "--no-textconv", "--first-parent", "--find-renames", "-M", sha, "--"]
    proc = run_git(repo, args, timeout=30.0)
    mode = "first-parent" if not parent else "explicit-parent"
    if proc is None:
        return {"patch": "", "truncated": True, "total_bytes": 0, "fingerprint": "",
                "error": "Git diff timed out", "files": [], "mode": mode}
    if proc.returncode != 0:
        return {"patch": "", "truncated": True, "total_bytes": 0, "fingerprint": "",
                "error": (proc.stderr or "Git diff failed")[:500], "files": [], "mode": mode}
    patch = proc.stdout or ""
    truncated = False
    if len(patch) > max_bytes:
        patch = patch[:max_bytes] + "\n... [truncated: patch exceeds context budget]\n"
        truncated = True
    files: list[dict] = []
    stat = run_git(repo, ["show", "--numstat", "--pretty=format:", "--first-parent", sha, "--"], timeout=15.0)
    if stat and stat.returncode == 0:
        for line in (stat.stdout or "").splitlines():
            bits = line.split("\t")
            if len(bits) < 3:
                continue
            old, new = bits[0], bits[1]
            path = bits[2]
            old_path = None
            if " => " in path or " =>" in path or "=> " in path:
                # rename format "old => new" (possibly with braces)
                old_path = path
            files.append(
                {
                    "path": path[:500],
                    "old_path": old_path,
                    "insertions": None if old == "-" else (int(old) if old.isdigit() else 0),
                    "deletions": None if new == "-" else (int(new) if new.isdigit() else 0),
                    "binary": old == "-" and new == "-",
                    "status": "binary" if (old == "-" and new == "-") else "changed",
                }
            )
    fingerprint = hashlib.sha256(patch.encode("utf-8", errors="replace")).hexdigest()[:24]
    return {
        "patch": patch,
        "truncated": truncated,
        "total_bytes": len(proc.stdout or ""),
        "files": files,
        "mode": "first-parent" if not parent else "explicit-parent",
        "fingerprint": fingerprint,
    }


def context_file_at(repo: str, sha: str, relpath: str) -> str | None:
    sha = validate_sha(sha)
    if ".." in relpath.replace("\\", "/").split("/"):
        return None
    proc = run_git(repo, ["show", f"{sha}:{relpath}"], timeout=10.0)
    if proc is None or proc.returncode != 0:
        return None
    text = proc.stdout or ""
    if len(text) > 60_000:
        text = text[:60_000]
    return text
