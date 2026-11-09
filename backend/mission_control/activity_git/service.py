"""Persistent, incremental Git activity index with review evidence.

Design separation (MC-ACTIVITY-01):
- Git history is factual evidence (git_repositories / git_commits).
- An AI review is an assessment of that evidence (git_reviews).
- No quality scores are invented here; only observations and provenance.

Scanning and indexing are read-only with respect to the scanned repositories.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import stat
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, or_, select

from mission_control.activity.service import record_activity
from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.core.paths import is_within, normalize_absolute_path, require_existing_directory
from mission_control.git.history import (
    branches_for,
    commit_bodies,
    commit_stats,
    context_file_at,
    file_diff,
    head_info,
    log_recent,
    ref_snapshot,
    resolve_identity,
    rev_list_all,
    run_git,
    validate_sha,
)
from mission_control.models import DiscoveryRoot, GitCommit, GitRepository, GitReview, Setting
from mission_control.persistence.db import Database, now_iso

logger = logging.getLogger(__name__)

EXCLUDED_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".git", ".hg", ".svn", "coverage", ".coverage",
    # Generated tooling/workbench state: thousands of fixture repos that are
    # not independently managed projects (e.g. workbench .workbench runs).
    ".workbench", ".roborev", ".vscode", ".idea", ".tox", ".eggs",
    "site-packages", "__pypackages__",
}


def _name_excluded(name: str, patterns: list[str]) -> bool:
    import fnmatch

    lowered = name.casefold()
    for pattern in patterns:
        normalized = pattern.replace("\\", "/").casefold()
        if fnmatch.fnmatch(lowered, normalized) or fnmatch.fnmatch(lowered, normalized.strip("*")):
            return True
    return lowered in EXCLUDED_DIRS

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|password|passwd|secret|private[_-]?token|client[_-]?secret)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/=]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[bap]-[A-Za-z0-9\-]{10,}\b"),
    re.compile(r"(?i)\b(connection[_-]?string|mongodb(\+srv)?://\S+:\S+@)\b"),
]

REVIEW_VERDICTS = ("Accept", "Accept with warnings", "Request changes", "Inconclusive")

DEFAULT_CONFIG = {
    "recent_days": 30,
    "max_depth": 4,
    "max_repos_per_scan": 2000,
    "diff_max_bytes": 120_000,
    "backfill_page": 500,
    "prompt_max_chars": 60_000,
    "concurrency": 8,
}

DUBLIN_TZ = "Europe/Dublin"


def _utc_ts(value: str | None) -> int:
    if not value:
        return 0
    try:
        text = value.strip().replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).timestamp())
    except ValueError:
        return 0


def _day_bounds(day: str, tz_name: str = DUBLIN_TZ) -> tuple[int, int]:
    tz = ZoneInfo(tz_name)
    base = datetime.fromisoformat(day).replace(tzinfo=tz)
    start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return int(start.timestamp()), int(end.timestamp())


def _today_bounds(tz_name: str = DUBLIN_TZ) -> tuple[int, int]:
    now = datetime.now(ZoneInfo(tz_name))
    return _day_bounds(now.date().isoformat(), tz_name)


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:24]


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def redact_secrets(text: str) -> tuple[str, list[str]]:
    redactions: list[str] = []
    redacted = text
    for index, pattern in enumerate(SECRET_PATTERNS):
        def _replace(match: re.Match[str]) -> str:
            redactions.append(f"pattern-{index}:{match.group(0)[:24]}…")
            return "[REDACTED-SECRET]"
        redacted = pattern.sub(_replace, redacted)
    return redacted, redactions


def _repo_id_for_path(path: str) -> str:
    return "gitrepo-" + hashlib.sha1(os.path.normcase(path).encode("utf-8")).hexdigest()[:16]


def _root_display_name(path: str) -> str:
    name = Path(path).name or path
    return name


def _root_category(path: str) -> str:
    lowered = path.casefold()
    if "book" in lowered:
        return "books"
    return "software"


class GitActivityService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._task: asyncio.Task[None] | None = None
        self._cancel = threading.Event()
        self._lock = asyncio.Lock()
        # SQLite allows a single writer: index workers share one write lock so
        # concurrent repository syncs queue instead of failing with SQLITE_BUSY.
        # Git subprocess work happens outside the lock and stays parallel.
        # An RLock is used because backfill runs inside the sync's session.
        self._write_lock = threading.RLock()
        self._active_reviews: set[str] = set()
        self._status: dict[str, Any] = self._load_last_status()

    @staticmethod
    def _is_locked_error(exc: Exception) -> bool:
        text = f"{exc.__class__.__name__}: {exc}".casefold()
        return "database is locked" in text or "database table is locked" in text

    @contextmanager
    def _locked_session(self) -> Iterator[Any]:
        """A database session serialized across index worker threads.

        The body runs once under the write lock; only the final commit is
        retried on SQLITE_BUSY, so the generator always yields exactly once.
        """
        with self._write_lock:
            session = self.database.session_factory()
            try:
                yield session
            except Exception:
                session.rollback()
                session.close()
                raise
            last: Exception | None = None
            for _ in range(4):
                try:
                    session.commit()
                    last = None
                    break
                except Exception as exc:  # noqa: BLE001 - retry only busy errors
                    if not self._is_locked_error(exc):
                        session.rollback()
                        session.close()
                        raise
                    last = exc
                    time.sleep(0.25)
            session.close()
            if last is not None:
                raise last

    # ------------------------------------------------------------- status
    def _load_last_status(self) -> dict[str, Any]:
        with self.database.session() as session:
            setting = session.get(Setting, "git_activity.last_scan")
            if setting and isinstance(setting.value, dict):
                return {**setting.value, "running": False}
        return {"running": False, "status": "idle", "scan_id": None}

    @property
    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def get_config(self, session) -> dict[str, Any]:
        setting = session.get(Setting, "activity_git")
        base = dict(DEFAULT_CONFIG)
        if setting and isinstance(setting.value, dict):
            for key, value in setting.value.items():
                if key in base:
                    base[key] = value
        return base

    def update_config(self, session, patch: dict[str, Any]) -> dict[str, Any]:
        config = self.get_config(session)
        for key, value in patch.items():
            if key not in DEFAULT_CONFIG:
                raise ValidationProblem(f"Unknown activity_git setting: {key}")
            if key in {"recent_days", "max_depth", "max_repos_per_scan", "diff_max_bytes", "backfill_page", "prompt_max_chars", "concurrency"}:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValidationProblem(f"activity_git.{key} must be an integer")
            config[key] = value
        bounds = {"recent_days": (1, 365), "max_depth": (0, 8), "max_repos_per_scan": (1, 2000),
                  "diff_max_bytes": (4000, 500_000), "backfill_page": (100, 2000),
                  "prompt_max_chars": (4000, 200_000), "concurrency": (1, 16)}
        for key, (low, high) in bounds.items():
            if not low <= int(config[key]) <= high:
                raise ValidationProblem(f"activity_git.{key} must be between {low} and {high}")
        setting = session.get(Setting, "activity_git")
        if setting is None:
            session.add(Setting(key="activity_git", value=config, updated_at=now_iso()))
        else:
            setting.value = config
            setting.updated_at = now_iso()
        session.flush()
        return config

    # -------------------------------------------------------------- roots
    def list_roots(self, session) -> list[dict[str, Any]]:
        rows = session.scalars(select(DiscoveryRoot).order_by(DiscoveryRoot.path)).all()
        return [
            {
                "path": row.path,
                "name": row.display_name or _root_display_name(row.path),
                "category": row.category or _root_category(row.path),
                "enabled": bool(row.enabled),
                "git_enabled": bool(row.git_enabled),
                "added_at": row.added_at,
                "last_git_sync_at": row.last_git_sync_at,
                "last_git_error": row.last_git_error,
            }
            for row in rows
        ]

    def _authorized_repo_path(self, session, repo: GitRepository) -> str:
        roots = [row.path for row in session.scalars(select(DiscoveryRoot).where(DiscoveryRoot.enabled.is_(True))).all()]
        for root in roots:
            try:
                if is_within(Path(repo.path), Path(root)) or os.path.normcase(repo.path) == os.path.normcase(root):
                    return repo.path
            except OSError:
                continue
        raise ValidationProblem("Repository is not inside a configured, enabled root")

    def add_root(self, session, *, path: str, name: str = "", category: str = "software", enabled: bool = True) -> dict[str, Any]:
        normalized = require_existing_directory(path, field="activity root")
        existing = session.get(DiscoveryRoot, normalized)
        if existing is None:
            existing = DiscoveryRoot(path=normalized, enabled=enabled, added_at=now_iso())
            session.add(existing)
        existing.display_name = (name or _root_display_name(normalized))[:120]
        existing.category = (category or "software")[:60]
        existing.enabled = enabled
        existing.git_enabled = True
        record_activity(session, event_type="system", title="Activity root added",
                        detail=normalized, source="mission-control", provenance="user")
        session.flush()
        return self.list_roots(session)[[row["path"] for row in self.list_roots(session)].index(normalized)]

    def update_root(self, session, path: str, *, name=None, category=None, enabled=None, git_enabled=None) -> dict[str, Any]:
        normalized = normalize_absolute_path(path, field="activity root")
        root = session.get(DiscoveryRoot, normalized)
        if root is None:
            raise NotFound("Activity root not found")
        if name is not None:
            root.display_name = str(name)[:120]
        if category is not None:
            root.category = str(category)[:60]
        if enabled is not None:
            root.enabled = bool(enabled)
        if git_enabled is not None:
            root.git_enabled = bool(git_enabled)
        session.flush()
        rows = self.list_roots(session)
        return next(row for row in rows if row["path"] == normalized)

    def remove_root(self, session, path: str, *, retain_history: bool = True) -> None:
        normalized = normalize_absolute_path(path, field="activity root")
        root = session.get(DiscoveryRoot, normalized)
        if root is None:
            raise NotFound("Activity root not found")
        session.delete(root)
        if not retain_history:
            repos = session.scalars(select(GitRepository).where(GitRepository.root_path == normalized)).all()
            for repo in repos:
                session.delete(repo)
        record_activity(session, event_type="system",
                        title=f"Activity root removed ({'history retained' if retain_history else 'history deleted'})",
                        detail=normalized, source="mission-control", provenance="user")
        session.flush()

    # ---------------------------------------------------------------- scan
    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self._task and not self._task.done():
                raise Conflict("A Git activity scan is already running")
            self._cancel.clear()
            scan_id = f"gitscan-{uuid.uuid4().hex[:12]}"
            self._status = {"scan_id": scan_id, "status": "running", "running": True,
                            "started_at": now_iso(), "finished_at": None, "roots": [],
                            "repos_discovered": 0, "repos_indexed": 0, "commits_new": 0,
                            "errors": [], "backfill_pending": 0, "elapsed_seconds": None}
            self._task = asyncio.create_task(self._run(scan_id))
            return dict(self._status)

    async def cancel(self) -> dict[str, Any]:
        if not self._task or self._task.done():
            return dict(self._status)
        self._cancel.set()
        self._status["status"] = "cancelling"
        return dict(self._status)

    async def shutdown(self) -> None:
        if self._task and not self._task.done():
            self._cancel.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                self._task.cancel()

    def _run(self, scan_id: str) -> Any:
        return self._run_coro(scan_id)

    async def _run_coro(self, scan_id: str) -> None:
        import time as _time
        started = _time.monotonic()
        try:
            with self.database.session() as session:
                roots = [row for row in session.scalars(select(DiscoveryRoot).where(DiscoveryRoot.enabled.is_(True))).all() if row.git_enabled]
                root_paths = [row.path for row in roots]
                config = self.get_config(session)
                discovery_setting = session.get(Setting, "discovery")
                exclusions = discovery_setting.value.get("exclusions", []) if discovery_setting and isinstance(discovery_setting.value, dict) else []
            self._status["roots"] = root_paths
            discovered, truncated = await asyncio.to_thread(self._discover_all, root_paths, config, list(exclusions or []))
            self._status["truncated"] = truncated
            await asyncio.to_thread(self._index_all, scan_id, discovered, config, root_paths)
            with self.database.session() as session:
                pending = session.scalar(select(func.count(GitRepository.id)).where(GitRepository.backfill_complete.is_(False)))
                total_commits = session.scalar(select(func.count()).select_from(GitCommit)) or 0
                total_repos = session.scalar(select(func.count(GitRepository.id))) or 0
            self._status.update({"status": "cancelled" if self._cancel.is_set() else "complete",
                                 "running": False, "finished_at": now_iso(),
                                 "repos_discovered": len(discovered),
                                 "repos_indexed": self._status.get("repos_indexed", 0),
                                 "backfill_pending": int(pending or 0),
                                 "total_repos": int(total_repos or 0),
                                 "total_commits": int(total_commits or 0),
                                 "elapsed_seconds": round(_time.monotonic() - started, 3)})
        except Exception as exc:  # scan must not take down the dashboard
            logger.exception("Git activity scan failed")
            self._status.update({"status": "failed", "running": False,
                                 "finished_at": now_iso(), "error": str(exc)[:500]})
        finally:
            summary = {k: v for k, v in self._status.items() if k != "running"}
            try:
                with self.database.session() as session:
                    setting = session.get(Setting, "git_activity.last_scan")
                    if setting is None:
                        session.add(Setting(key="git_activity.last_scan", value=summary, updated_at=now_iso()))
                    else:
                        setting.value = summary
                        setting.updated_at = now_iso()
            except Exception:  # pragma: no cover - defensive
                logger.exception("Could not persist git activity scan status")

    # ---------------------------------------------------------- discovery
    def _discover_all(self, root_paths: list[str], config: dict[str, Any], exclusions: list[str]) -> tuple[list[dict[str, Any]], bool]:
        found: list[dict[str, Any]] = []
        seen_uids: set[str] = set()
        seen_paths: set[str] = set()
        truncated = False
        for root in root_paths:
            if self._cancel.is_set():
                break
            try:
                for item in self._discover_root(root, int(config["max_depth"]), int(config["max_repos_per_scan"]) - len(found), exclusions):
                    uid = item["repo_uid"]
                    pathkey = os.path.normcase(item["path"])
                    if uid in seen_uids or pathkey in seen_paths:
                        continue
                    seen_uids.add(uid)
                    seen_paths.add(pathkey)
                    item["root_path"] = root
                    found.append(item)
                    if len(found) >= int(config["max_repos_per_scan"]):
                        truncated = True
                        break
                if truncated:
                    break
            except Exception as exc:
                logger.warning("Discovery failed for root %s: %s", root, exc)
        return found, truncated

    def _discover_root(self, root: str, max_depth: int, limit: int, exclusions: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        root_path = Path(root)
        if limit <= 0:
            return results
        if not root_path.exists() or not root_path.is_dir():
            return results

        def walk(directory: Path, depth: int) -> None:
            if len(results) >= limit or self._cancel.is_set():
                return
            try:
                entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
            except (OSError, PermissionError):
                return
            for entry in entries:
                if len(results) >= limit or self._cancel.is_set():
                    return
                if not entry.is_dir():
                    continue
                if _name_excluded(entry.name, exclusions):
                    continue
                if _is_reparse_point(entry):
                    continue
                git_marker = entry / ".git"
                is_repo = git_marker.exists() or entry.suffix == ".git"
                if is_repo or self._looks_like_repo(entry):
                    identity = resolve_identity(str(entry))
                    if identity is not None:
                        results.append({
                            "path": str(Path(identity.toplevel if not identity.is_bare else str(entry)).resolve(strict=False)),
                            "name": Path(identity.toplevel).name if not identity.is_bare else entry.name,
                            "git_dir": identity.git_dir,
                            "repo_uid": identity.repo_uid,
                            "is_bare": identity.is_bare,
                            "is_shallow": identity.is_shallow,
                        })
                        # Continue deeper to catch nested repositories.
                        if depth < max_depth:
                            walk(entry, depth + 1)
                        continue
                if depth < max_depth:
                    walk(entry, depth + 1)

        # The root itself may be a repository.
        identity = resolve_identity(root)
        if identity is not None and (Path(root) / ".git").exists():
            results.append({
                "path": str(Path(identity.toplevel).resolve(strict=False)),
                "name": Path(identity.toplevel).name,
                "git_dir": identity.git_dir,
                "repo_uid": identity.repo_uid,
                "is_bare": identity.is_bare,
                "is_shallow": identity.is_shallow,
            })
        else:
            walk(root_path, 0)
        return results

    def _looks_like_repo(self, path: Path) -> bool:
        # Only treat as repo when git resolution succeeds; this is a cheap
        # pre-check to avoid spawning git for every plain directory.
        if (path / ".git").exists():
            return True
        return False

    # ------------------------------------------------------------- index
    def _index_all(self, scan_id: str, discovered: list[dict[str, Any]], config: dict[str, Any], root_paths: list[str]) -> None:
        indexed = 0
        commits_new = 0
        errors: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=int(config["concurrency"])) as pool:
            futures = {pool.submit(self._sync_one_repo, item, config): item for item in discovered}
            for future in as_completed(futures):
                if self._cancel.is_set():
                    break
                item = futures[future]
                try:
                    added = future.result()
                    indexed += 1
                    commits_new += int(added or 0)
                except Exception as exc:  # pragma: no cover - defensive isolation
                    errors.append({"path": item.get("path", ""), "error": str(exc)[:300]})
        with self._locked_session() as session:
            for root_path in root_paths:
                root = session.get(DiscoveryRoot, root_path)
                if root is not None:
                    root.last_git_sync_at = now_iso()
                    root.last_git_error = None
        self._status["repos_indexed"] = indexed
        self._status["commits_new"] = commits_new
        self._status["errors"] = errors[:50]

    def _sync_one_repo(self, item: dict[str, Any], config: dict[str, Any]) -> int:
        path = item["path"]
        with self._locked_session() as session:
            repo = session.scalar(select(GitRepository).where(GitRepository.path == path))
            if repo is None:
                # Dedupe worktrees sharing one common dir before inserting.
                existing_uid = session.scalar(select(GitRepository).where(GitRepository.repo_uid == item["repo_uid"]))
                if existing_uid is not None:
                    return 0
                repo = GitRepository(
                    id=_repo_id_for_path(path), root_path=item.get("root_path", ""),
                    path=path, name=item.get("name") or Path(path).name,
                    git_dir=item.get("git_dir", ""), repo_uid=item.get("repo_uid", ""),
                    is_bare=bool(item.get("is_bare")), is_shallow=bool(item.get("is_shallow")),
                    updated_at=now_iso(),
                )
                session.add(repo)
                session.flush()
            else:
                repo.root_path = item.get("root_path", repo.root_path)
                repo.git_dir = item.get("git_dir", repo.git_dir) or repo.git_dir
                repo.repo_uid = item.get("repo_uid", repo.repo_uid) or repo.repo_uid
            repo_id = repo.id
        identity = resolve_identity(path)
        if identity is None:
            with self._locked_session() as session:
                repo = session.get(GitRepository, repo_id)
                if repo is not None:
                    repo.accessible = False
                    repo.error = "Repository is not accessible via git"
                    repo.updated_at = now_iso()
            return 0
        branch, head = head_info(path)
        refs = ref_snapshot(path)
        refs_hash = _fingerprint(str(sorted(refs.items())))
        with self._locked_session() as session:
            repo = session.get(GitRepository, repo_id)
            if repo is None:
                return 0
            if refs_hash == (repo.refs_snapshot or "") and repo.last_indexed_at and repo.backfill_complete:
                return 0
            need_reachability = refs_hash != (repo.refs_snapshot or "")
        recent_days = int(config["recent_days"])
        recent = log_recent(path, since_days=recent_days, max_count=2000)
        with self._locked_session() as session:
            existing = set(session.scalars(select(GitCommit.sha).where(GitCommit.repo_id == repo_id)).all())
        new_metas = [meta for meta in recent if meta.sha not in existing]
        added = 0
        if new_metas:
            bodies = commit_bodies(path, [meta.sha for meta in new_metas])
            stats = commit_stats(path, [meta.sha for meta in new_metas])
            branch_map = branches_for(path, {meta.sha for meta in new_metas})
            with self._locked_session() as session:
                for meta in new_metas:
                    files, ins, dels, is_merge, is_root = stats.get(meta.sha, (0, 0, 0, len(meta.parents) > 1, len(meta.parents) == 0))
                    session.add(GitCommit(
                        repo_id=repo_id, sha=meta.sha, short_sha=meta.sha[:8],
                        subject=meta.subject, body=bodies.get(meta.sha, "")[:20000],
                        author_name=meta.author_name, author_email=meta.author_email,
                        author_ts=meta.author_ts, author_tz=meta.author_tz,
                        committer_ts=meta.committer_ts or meta.author_ts, committer_tz=meta.committer_tz,
                        parents=meta.parents, branches=branch_map.get(meta.sha, [])[:20],
                        files_changed=files, insertions=ins, deletions=dels,
                        is_merge=is_merge, is_root=is_root, reachable=True,
                        first_seen_at=now_iso(), observed_at=now_iso(),
                    ))
                    added += 1
        # Reachability is recomputed only when refs changed, outside the lock.
        reachable: set[str] | None = None
        if need_reachability:
            try:
                reachable = set(rev_list_all(path, max_count=20000))
            except Exception:
                logger.debug("Reachability update failed for %s", path)
                reachable = None
        with self._locked_session() as session:
            repo = session.get(GitRepository, repo_id)
            if repo is None:
                return added
            if reachable:
                batch = session.scalars(select(GitCommit).where(GitCommit.repo_id == repo_id)).all()
                for row in batch:
                    row.reachable = row.sha in reachable
                    row.observed_at = now_iso()
            repo.branch = branch
            repo.head_sha = head
            repo.refs_snapshot = refs_hash
            repo.accessible = True
            repo.error = None
            repo.last_indexed_at = now_iso()
            repo.total_commits = int(session.scalar(select(func.count()).select_from(GitCommit).where(GitCommit.repo_id == repo_id)) or 0)
            self._refresh_context_flags(path, repo)
            repo.updated_at = now_iso()
            need_backfill = not repo.backfill_complete
        # Historical backfill runs in its own sessions afterwards: it must
        # never nest inside the open update session above (the outer session
        # holds uncommitted writes that would block the inner one).
        if need_backfill:
            self._backfill_page(repo_id, path, config)
        return added

    def _backfill_page(self, repo_id: str, path: str, config: dict[str, Any]) -> None:
        from mission_control.git.history import _FIELD_SEP, _RECORD_SEP, _parse_log_output  # noqa: SLF001

        page = int(config["backfill_page"])
        with self._locked_session() as session:
            stored = session.get(GitRepository, repo_id)
            before = stored.backfill_before if stored else None
            if before is None:
                oldest = session.scalar(select(func.min(GitCommit.committer_ts)).where(GitCommit.repo_id == repo_id)) or 0
                if not oldest:
                    # No commits indexed yet (e.g. no recent history): start the
                    # cursor at now so older history is picked up below.
                    before = datetime.now(timezone.utc).isoformat()
                else:
                    before = datetime.fromtimestamp(oldest, tz=timezone.utc).isoformat()
        fmt = _FIELD_SEP.join(["%H", "%P", "%aN", "%aE", "%at", "%ct", "%aI", "%cI", "%s"]) + _RECORD_SEP
        proc = run_git(path, ["log", "--all", "--date-order", f"--pretty=format:{fmt}", f"--before={before}", "--max-count", str(page)], timeout=30.0)
        if proc is None or proc.returncode != 0:
            return
        metas = _parse_log_output(proc.stdout or "")
        with self._locked_session() as session:
            existing = set(session.scalars(select(GitCommit.sha).where(GitCommit.repo_id == repo_id)).all())
        fresh = [meta for meta in metas if meta.sha not in existing]
        if fresh:
            bodies = commit_bodies(path, [meta.sha for meta in fresh])
            stats = commit_stats(path, [meta.sha for meta in fresh])
            branch_map = branches_for(path, {meta.sha for meta in fresh})
            with self._locked_session() as session:
                for meta in fresh:
                    files, ins, dels, is_merge, is_root = stats.get(meta.sha, (0, 0, 0, len(meta.parents) > 1, len(meta.parents) == 0))
                    session.add(GitCommit(
                        repo_id=repo_id, sha=meta.sha, short_sha=meta.sha[:8],
                        subject=meta.subject, body=bodies.get(meta.sha, "")[:20000],
                        author_name=meta.author_name, author_email=meta.author_email,
                        author_ts=meta.author_ts, author_tz=meta.author_tz,
                        committer_ts=meta.committer_ts or meta.author_ts, committer_tz=meta.committer_tz,
                        parents=meta.parents, branches=branch_map.get(meta.sha, [])[:20],
                        files_changed=files, insertions=ins, deletions=dels,
                        is_merge=is_merge, is_root=is_root, reachable=True,
                        first_seen_at=now_iso(), observed_at=now_iso(),
                    ))
        with self._locked_session() as session:
            stored = session.get(GitRepository, repo_id)
            if stored is None:
                return
            if len(metas) < page:
                stored.backfill_complete = True
                stored.backfill_before = None
            else:
                oldest_ts = min([meta.committer_ts or meta.author_ts for meta in metas] or [0])
                if oldest_ts:
                    stored.backfill_before = datetime.fromtimestamp(oldest_ts, tz=timezone.utc).isoformat()
                else:
                    stored.backfill_complete = True

    def _refresh_context_flags(self, path: str, repo: GitRepository) -> None:
        top = Path(path)
        agents = top / "AGENTS.md"
        desc = top / "DESCRIPTION.md"
        repo.has_agents = agents.is_file()
        repo.has_description = desc.is_file()
        if repo.has_agents and repo.has_description:
            # Heuristic staleness: description untouched for 90d while repo active in 7d.
            try:
                desc_age_days = (datetime.now(timezone.utc).timestamp() - desc.stat().st_mtime) / 86400
                head_proc = run_git(path, ["log", "-1", "--format=%ct"], timeout=5.0)
                head_age_days = 9999.0
                if head_proc and head_proc.returncode == 0 and (head_proc.stdout or "").strip().isdigit():
                    head_age_days = (datetime.now(timezone.utc).timestamp() - int(head_proc.stdout.strip())) / 86400
                repo.context_status = "stale" if (desc_age_days > 90 and head_age_days < 7) else "ready"
            except OSError:
                repo.context_status = "ready"
        elif repo.has_agents or repo.has_description:
            repo.context_status = "partial"
        else:
            repo.context_status = "missing"

    # ------------------------------------------------------------ queries
    def timeline(self, session, *, root=None, repo_id=None, category=None, author=None,
                 branch=None, review_status=None, search=None, date_from=None, date_to=None,
                 preset="today", limit=100, offset=0, tz_name: str = DUBLIN_TZ) -> tuple[list[dict[str, Any]], int, bool]:
        if preset in {"today", "yesterday", "7d", "30d"}:
            now = datetime.now(ZoneInfo(tz_name))
            if preset == "today":
                start, _ = _day_bounds(now.date().isoformat(), tz_name)
                date_from = start
                date_to = None
            elif preset == "yesterday":
                from datetime import timedelta as _td
                day = (now - _td(days=1)).date().isoformat()
                start, end = _day_bounds(day, tz_name)
                date_from, date_to = start, end
            elif preset == "7d":
                from datetime import timedelta as _td
                date_from = int((now - _td(days=7)).timestamp())
                date_to = None
            elif preset == "30d":
                from datetime import timedelta as _td
                date_from = int((now - _td(days=30)).timestamp())
                date_to = None
        query = (
            select(GitCommit, GitRepository)
            .join(GitRepository, GitRepository.id == GitCommit.repo_id)
            .order_by(desc(GitCommit.committer_ts), GitCommit.sha)
        )
        if root:
            query = query.where(GitRepository.root_path == root)
        if repo_id:
            query = query.where(GitCommit.repo_id == repo_id)
        if category:
            query = query.where(select(DiscoveryRoot.category).where(DiscoveryRoot.path == GitRepository.root_path).scalar_subquery() == category)
        if author:
            needle = f"%{author.casefold()}%"
            query = query.where(or_(GitCommit.author_name.ilike(needle), GitCommit.author_email.ilike(needle)))
        if branch:
            query = query.where(GitCommit.branches.like(f"%{branch}%"))
        if search:
            needle = f"%{search}%"
            query = query.where(or_(GitCommit.subject.ilike(needle), GitRepository.name.ilike(needle), GitCommit.sha.ilike(needle)))
        if date_from is not None:
            query = query.where(GitCommit.committer_ts >= int(date_from))
        if date_to is not None:
            query = query.where(GitCommit.committer_ts <= int(date_to))
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        page = session.execute(query.limit(min(max(limit, 1), 200)).offset(max(offset, 0))).all()
        rows = page
        review_map: dict[tuple[str, str], int] = {}
        if rows:
            pairs = [(row[0].repo_id, row[0].sha) for row in rows]
            repo_ids = list({repo for repo, _ in pairs})
            reviews = session.scalars(select(GitReview).where(GitReview.repo_id.in_(repo_ids), GitReview.status == "completed")).all()
            for review in reviews:
                for sha in (review.commit_shas or ([review.commit_sha] if review.commit_sha else [])):
                    review_map[(review.repo_id, sha)] = review_map.get((review.repo_id, sha), 0) + 1
        items = []
        for commit, repo in rows:
            key = (commit.repo_id, commit.sha)
            count = review_map.get(key, 0)
            items.append({
                "repo_id": repo.id, "repo_name": repo.name, "repo_path": repo.path,
                "root_path": repo.root_path, "sha": commit.sha, "short_sha": commit.short_sha,
                "subject": commit.subject, "author_name": commit.author_name,
                "author_email": commit.author_email, "author_ts": commit.author_ts,
                "committer_ts": commit.committer_ts, "committer_tz": commit.committer_tz,
                "parents": commit.parents, "branches": commit.branches,
                "files_changed": commit.files_changed, "insertions": commit.insertions,
                "deletions": commit.deletions, "is_merge": bool(commit.is_merge),
                "is_root": bool(commit.is_root), "reachable": bool(commit.reachable),
                "review_count": count,
                "review_status": "reviewed" if count else "awaiting",
            })
        if review_status in {"reviewed", "awaiting"}:
            items = [item for item in items if item["review_status"] == review_status]
        # Partial-index signal: any repo still backfilling means counts may grow.
        pending = session.scalar(select(func.count(GitRepository.id)).where(GitRepository.backfill_complete.is_(False))) or 0
        return items, int(total or 0), bool(pending)

    def summary(self, session, *, tz_name: str = DUBLIN_TZ) -> dict[str, Any]:
        today_start, _ = _today_bounds(tz_name)
        now = datetime.now(ZoneInfo(tz_name))
        from datetime import timedelta as _td
        week_start = int((now - _td(days=7)).timestamp())
        commits_today = session.scalar(select(func.count()).select_from(GitCommit).where(GitCommit.committer_ts >= today_start)) or 0
        commits_week = session.scalar(select(func.count()).select_from(GitCommit).where(GitCommit.committer_ts >= week_start)) or 0
        projects_today = session.scalar(select(func.count(func.distinct(GitCommit.repo_id))).where(GitCommit.committer_ts >= today_start)) or 0
        reviewed = session.scalar(select(func.count(func.distinct(GitReview.commit_sha))).where(GitReview.status == "completed")) or 0
        total_indexed = session.scalar(select(func.count()).select_from(GitCommit)) or 0
        repos_indexed = session.scalar(select(func.count(GitRepository.id))) or 0
        pending = session.scalar(select(func.count(GitRepository.id)).where(GitRepository.backfill_complete.is_(False))) or 0
        return {
            "commits_today": int(commits_today), "projects_today": int(projects_today),
            "commits_week": int(commits_week), "commits_reviewed": int(reviewed),
            "commits_indexed": int(total_indexed), "repos_indexed": int(repos_indexed),
            "backfill_pending": int(pending), "complete": not bool(pending),
            "generated_at": now_iso(),
        }

    # ----------------------------------------------------- diff + context
    def get_repo(self, session, repo_id: str) -> GitRepository:
        repo = session.get(GitRepository, repo_id)
        if repo is None:
            raise NotFound("Project repository not found")
        return repo

    def get_commit(self, session, repo_id: str, sha: str) -> tuple[GitRepository, GitCommit]:
        sha = validate_sha(sha)
        repo = self.get_repo(session, repo_id)
        commit = session.get(GitCommit, (repo_id, sha))
        # Fall back to prefix match for short SHAs pasted from the timeline.
        if commit is None and 4 <= len(sha) < 40:
            commit = session.scalars(
                select(GitCommit).where(GitCommit.repo_id == repo_id, GitCommit.sha.like(f"{sha}%")).limit(1)
            ).first()
        if commit is None:
            raise NotFound("Commit is not in the activity index")
        return repo, commit

    def commit_diff(self, session, repo_id: str, sha: str, *, parent: str | None = None, max_bytes: int | None = None) -> dict[str, Any]:
        repo, commit = self.get_commit(session, repo_id, sha)
        self._authorized_repo_path(session, repo)
        if parent is not None:
            parent = validate_sha(parent)
            if parent not in (commit.parents or []):
                raise ValidationProblem("Parent must be one of the commit's recorded parents")
        config = self.get_config(session)
        result = file_diff(repo.path, commit.sha, parent=parent, max_bytes=int(max_bytes or config["diff_max_bytes"]))
        return result

    def _read_current_context(self, repo_path: str) -> dict[str, dict[str, Any] | None]:
        top = Path(repo_path)
        docs: dict[str, dict[str, Any] | None] = {}
        for name in ("AGENTS.md", "DESCRIPTION.md", "README.md"):
            candidate = top / name
            if candidate.is_file():
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                    docs[name] = {"path": str(candidate), "revision": "working-tree",
                                  "text": text[:30_000], "sha": _fingerprint(text)}
                except OSError:
                    docs[name] = None
            else:
                docs[name] = None
        nested: list[dict[str, Any]] = []
        for child in top.iterdir():
            if len(nested) >= 10:
                break
            if child.is_dir() and child.name not in EXCLUDED_DIRS and not child.name.startswith("."):
                agent_file = child / "AGENTS.md"
                if agent_file.is_file():
                    try:
                        text = agent_file.read_text(encoding="utf-8", errors="replace")
                        nested.append({"path": str(agent_file), "revision": "working-tree",
                                       "text": text[:12_000], "sha": _fingerprint(text)})
                    except OSError:
                        continue
        docs["NESTED_AGENTS"] = nested  # type: ignore[assignment]
        return docs

    def context_inventory(self, session, repo_id: str) -> dict[str, Any]:
        repo = self.get_repo(session, repo_id)
        docs = self._read_current_context(repo.path)
        agents = docs.get("AGENTS.md")
        description = docs.get("DESCRIPTION.md")
        nested = docs.get("NESTED_AGENTS") or []
        status = "missing"
        if isinstance(agents, dict) and isinstance(description, dict):
            status = repo.context_status or "ready"
        elif isinstance(agents, dict) or isinstance(description, dict):
            status = "partial"
        return {
            "repo_id": repo.id, "repo_name": repo.name, "repo_path": repo.path,
            "has_agents": bool(isinstance(agents, dict)), "has_description": bool(isinstance(description, dict)),
            "context_status": status, "nested_agents": nested if isinstance(nested, list) else [],
            "agents_path": agents["path"] if isinstance(agents, dict) else None,
            "description_path": description["path"] if isinstance(description, dict) else None,
            "last_indexed_at": repo.last_indexed_at,
        }

    def build_prompt(self, session, repo_id: str, sha: str, *, parent: str | None = None,
                     profile: str = "code", max_bytes: int | None = None) -> dict[str, Any]:
        repo, commit = self.get_commit(session, repo_id, sha)
        self._authorized_repo_path(session, repo)
        config = self.get_config(session)
        diff = file_diff(repo.path, commit.sha, parent=parent, max_bytes=int(max_bytes or config["diff_max_bytes"]))
        redacted_patch, redactions = redact_secrets(diff["patch"])
        # Historical context preferred; fall back to working tree with a label.
        historical: dict[str, str | None] = {}
        context_sources: list[str] = []
        for name in ("AGENTS.md", "DESCRIPTION.md"):
            at_rev = context_file_at(repo.path, commit.sha, name)
            if at_rev is not None:
                historical[name] = at_rev
                context_sources.append(f"{name}@{commit.short_sha} (historical)")
            else:
                current = self._read_current_context(repo.path).get(name)
                if isinstance(current, dict):
                    historical[name] = current["text"]
                    context_sources.append(f"{name} (current working tree; not historical fact)")
                else:
                    historical[name] = None
        agents_text = (historical.get("AGENTS.md") or "").strip()
        desc_text = (historical.get("DESCRIPTION.md") or "").strip()
        context_fp = _fingerprint(f"{agents_text}\n---\n{desc_text}")
        prompt_max = int(config["prompt_max_chars"])
        if profile not in {"code", "prose"}:
            profile = "code"
        if profile == "prose":
            objective = ("Examine the manuscript change for correctness, continuity, clarity, and editorial "
                         "soundness. Do not apply programming quality checks to prose.")
        else:
            objective = ("Examine the commit for correctness, regressions, maintainability, architectural "
                         "compliance, security issues and incomplete requirements.")
        coverage = {
            "repo": repo.path, "sha": commit.sha, "mode": diff["mode"],
            "files_included": len(diff["files"]), "patch_bytes": diff["total_bytes"],
            "truncated": diff["truncated"], "redactions": len(redactions),
            "context_sources": context_sources, "historical_context": any("historical" in source for source in context_sources),
            "profile": profile,
        }
        # Absolute filesystem paths stay server-side: the exported prompt
        # identifies the project by name, never by absolute path.
        root_label = Path(repo.root_path).name if repo.root_path else "unknown root"
        root_row = session.get(DiscoveryRoot, repo.root_path) if repo.root_path else None
        if root_row is not None and (root_row.display_name or "").strip():
            root_label = root_row.display_name.strip()
        header = f"""# Commit review request

## A. Review objective
{objective}

## B. Project context
Project: {repo.name} (root: {root_label})
Context fingerprint: {context_fp}
Context sources: {', '.join(context_sources) if context_sources else 'none found'}

### DESCRIPTION.md
{desc_text[:12000] if desc_text else '(missing — review proceeds without a project description)'}

### AGENTS.md (applicable instructions)
{agents_text[:15000] if agents_text else '(missing — no project-specific agent instructions found)'}

## C. Commit context
- Commit: {commit.sha} ({commit.short_sha})
- Subject: {commit.subject}
- Author: {commit.author_name} <{commit.author_email}>
- Committer timestamp: {commit.committer_ts} ({commit.committer_tz})
- Parents: {', '.join(commit.parents) if commit.parents else '(root commit)'}
- Branches/refs: {', '.join(commit.branches) if commit.branches else '(no ref recorded)'}
- Stats: {commit.files_changed} files, +{commit.insertions}/-{commit.deletions}
- Merge: {bool(commit.is_merge)} | Root: {bool(commit.is_root)} | Reachable: {bool(commit.reachable)}
- Diff mode: {diff['mode']} (merge commits use a documented first-parent comparison)
- Body:
{commit.body[:4000] if commit.body else '(no body)'}

## D. Diff (redacted where secrets were detected)
Redactions: {len(redactions)}
Truncated: {diff['truncated']} (budget {config['diff_max_bytes']} chars)

```diff
{redacted_patch[:prompt_max]}
```
"""
        if len(redacted_patch) > prompt_max:
            header += f"\n[NOTE: patch truncated to {prompt_max} chars of {len(redacted_patch)}; review is PARTIAL.]\n"
        instructions = """
## E. Review instructions
1. Identify genuine correctness defects.
2. Detect likely regressions.
3. Identify security and data-boundary issues.
4. Check violations of project architecture and AGENTS.md requirements.
5. Identify missing tests.
6. Assess implementation scope.
7. Identify unnecessary complexity.
8. Distinguish confirmed defects from hypotheses.
9. Avoid generic praise and speculative findings.
10. Give a clear review verdict.
Every finding must cite files and changed lines where possible. A test that was
not actually executed must never be reported as passed.

## Review output contract
```
Commit:
Project:
Review scope:
Evidence coverage:
Reviewer model:
Review date:

Verdict:
- Accept
- Accept with warnings
- Request changes
- Inconclusive

Findings:
- Severity
- File and line
- Observation
- Why it matters
- Supporting evidence
- Suggested correction
- Confidence

Tests:
- Observed executed tests
- Missing tests
- Tests recommended

Architecture:
- Compliance
- Deviations
- Risks

Summary:
- What changed
- Main concerns
- Recommended next action

Limitations:
- Files not reviewed
- Context missing
- Tests not executed
- Unresolved uncertainties
```
"""
        markdown = header + instructions
        return {
            "markdown": markdown,
            "prompt_hash": _fingerprint(markdown),
            "diff_hash": diff.get("fingerprint", ""),
            "context_fingerprint": context_fp,
            "size_chars": len(markdown),
            "truncated": diff["truncated"] or len(redacted_patch) > prompt_max,
            "redactions": redactions[:50],
            "redaction_count": len(redactions),
            "coverage": coverage,
            "diff": diff,
        }

    def build_range_prompt(self, session, repo_id: str, *, shas: list[str] | None = None,
                           base_sha: str | None = None, target_sha: str | None = None,
                           profile: str = "code") -> dict[str, Any]:
        repo = self.get_repo(session, repo_id)
        self._authorized_repo_path(session, repo)
        config = self.get_config(session)
        if base_sha and target_sha:
            base_sha = validate_sha(base_sha)
            target_sha = validate_sha(target_sha)
            proc = run_git(repo.path, ["diff", "--no-ext-diff", "--no-textconv", "-M", base_sha, target_sha, "--"], timeout=30.0)
            patch = (proc.stdout or "") if proc and proc.returncode == 0 else ""
            redacted, redactions = redact_secrets(patch)
            manifest = {"mode": "cumulative", "base": base_sha, "target": target_sha, "patch_bytes": len(patch)}
            markdown = (f"# Range review request\n\nProject: {repo.name}\nBase: {base_sha}\nTarget: {target_sha}\n"
                        f"Semantics: cumulative diff between base and target.\n\n```diff\n{redacted[:int(config['prompt_max_chars'])]}\n```\n")
            return {"markdown": markdown, "prompt_hash": _fingerprint(markdown),
                    "diff_hash": _fingerprint(patch), "context_fingerprint": "",
                    "size_chars": len(markdown), "truncated": len(patch) > int(config["prompt_max_chars"]),
                    "redactions": redactions[:50], "redaction_count": len(redactions),
                    "coverage": manifest, "commit_shas": []}
        cleaned = [validate_sha(item) for item in (shas or [])][:50]
        if not cleaned:
            raise ValidationProblem("Provide base_sha/target_sha or a non-empty shas list")
        sections = []
        all_redactions: list[str] = []
        truncated_any = False
        for sha in cleaned:
            try:
                _, commit = self.get_commit(session, repo_id, sha)
            except NotFound:
                sections.append(f"## {sha}\n(not in index; skipped)\n")
                continue
            diff = file_diff(repo.path, commit.sha, max_bytes=30_000)
            redacted, redactions = redact_secrets(diff["patch"])
            all_redactions.extend(redactions)
            truncated_any = truncated_any or diff["truncated"]
            sections.append(f"## {commit.short_sha} — {commit.subject}\nParents: {', '.join(commit.parents)}\n\n```diff\n{redacted[:15000]}\n```\n")
        contiguous_note = ("NOTE: the selected commits may not form one contiguous ancestry range. "
                           "Each commit is reviewed as a separate section below; do not assume a single cumulative diff.")
        markdown = f"# Range review request (selected commits)\n\nProject: {repo.name}\n{contiguous_note}\n\n" + "\n".join(sections)
        return {"markdown": markdown, "prompt_hash": _fingerprint(markdown),
                "diff_hash": _fingerprint(markdown), "context_fingerprint": "",
                "size_chars": len(markdown), "truncated": truncated_any,
                "redactions": all_redactions[:50], "redaction_count": len(all_redactions),
                "coverage": {"mode": "selected-commits", "count": len(cleaned), "truncated": truncated_any},
                "commit_shas": cleaned}

    # ------------------------------------------------------------ reviews
    def request_review(self, session, *, repo_id: str, sha: str | None = None,
                       commit_shas: list[str] | None = None, base_sha: str | None = None,
                       target_sha: str | None = None, model: str = "", profile: str = "code") -> GitReview:
        self.get_repo(session, repo_id)  # validates existence; build_* re-checks authorization
        if profile not in {"code", "prose"}:
            profile = "code"
        review_type = "single"
        shas: list[str] = []
        anchor: str | None = None
        if base_sha or target_sha or (commit_shas and len(commit_shas) > 1):
            review_type = "range"
            package = self.build_range_prompt(session, repo_id, shas=commit_shas, base_sha=base_sha, target_sha=target_sha, profile=profile)
            anchor = (commit_shas or [target_sha or ""])[0] if (commit_shas or target_sha) else None
            shas = package.get("commit_shas", commit_shas or [])
        else:
            anchor = validate_sha(sha or (commit_shas[0] if commit_shas else ""))
            if anchor is None:
                raise ValidationProblem("A commit sha is required")
            self.get_commit(session, repo_id, anchor)
            package = self.build_prompt(session, repo_id, anchor, profile=profile)
            shas = [anchor]
        prompt_hash = package["prompt_hash"]
        # Idempotency: do not duplicate an in-flight request for the same evidence.
        existing = session.scalar(select(GitReview).where(
            GitReview.repo_id == repo_id, GitReview.prompt_hash == prompt_hash,
            GitReview.status.in_(["queued", "running"])).order_by(desc(GitReview.created_at)).limit(1))
        if existing is not None:
            return existing
        review = GitReview(
            id=f"rev-{uuid.uuid4().hex[:16]}", repo_id=repo_id, review_type=review_type,
            commit_sha=anchor if review_type == "single" else None,
            base_sha=validate_sha(base_sha) if base_sha else None,
            target_sha=validate_sha(target_sha) if target_sha else None,
            commit_shas=shas, reviewer_type="local", requested_model=(model or "").strip()[:200],
            model_route="configured-local-openai", profile=profile, status="queued",
            prompt=package["markdown"][:200_000], prompt_hash=prompt_hash,
            diff_hash=package.get("diff_hash", ""), context_fingerprint=package.get("context_fingerprint", ""),
            evidence_coverage=package.get("coverage", {}), created_at=now_iso(),
        )
        session.add(review)
        session.flush()
        return review

    async def execute_review(self, review_id: str) -> None:
        if review_id in self._active_reviews:
            return
        self._active_reviews.add(review_id)
        try:
            with self.database.session() as session:
                review = session.get(GitReview, review_id)
                if review is None:
                    # The scheduling request may not have committed yet; retry
                    # briefly rather than dropping the review request.
                    pass
                elif review.status not in {"queued"}:
                    return
                else:
                    review.status = "running"
            with self.database.session() as session:
                review = session.get(GitReview, review_id)
            if review is None:
                await asyncio.sleep(2.0)
                with self.database.session() as session:
                    review = session.get(GitReview, review_id)
                if review is None:
                    return
                with self.database.session() as session:
                    review = session.get(GitReview, review_id)
                    if review is None or review.status not in {"queued"}:
                        return
                    review.status = "running"
            from mission_control.research.inference import complete_local_chat
            with self.database.session() as session:
                review = session.get(GitReview, review_id)
                if review is None:
                    return
                model = (review.requested_model or "").strip()
                prompt = review.prompt
            if not model:
                # Resolve the configured default inside a fresh session.
                from mission_control.research.inference import read_config
                with self.database.session() as session:
                    model = read_config(session).model
            if not model:
                raise ValueError("No model selected and no default model is configured")
            with self.database.session() as chat_session:
                result = await complete_local_chat(
                    chat_session, model=model,
                    messages=[
                        {"role": "system", "content": "You are a rigorous code reviewer. Follow the review output contract exactly. Distinguish confirmed defects from hypotheses."},
                        {"role": "user", "content": prompt[:100_000]},
                    ],
                )
            content = str(result.get("content", ""))
            verdict = self._parse_verdict(content)
            with self.database.session() as session:
                review = session.get(GitReview, review_id)
                if review is None:
                    return
                review.status = "completed"
                review.observed_model = str(result.get("model") or model)[:200]
                review.verdict = verdict
                review.summary = content[:50_000]
                review.findings = self._parse_findings(content)[:100]
                review.usage_info = result.get("usage", {}) if isinstance(result.get("usage"), dict) else {}
                review.completed_at = now_iso()
        except Exception as exc:
            with self.database.session() as session:
                review = session.get(GitReview, review_id)
                if review is not None and review.status in {"queued", "running"}:
                    review.status = "failed"
                    review.error = f"{exc.__class__.__name__}: {str(exc)[:1000]}"
                    review.completed_at = now_iso()
        finally:
            self._active_reviews.discard(review_id)

    @staticmethod
    def _parse_verdict(content: str) -> str:
        match = re.search(r"(?im)^verdict\s*:\s*(.+)$", content)
        if match:
            candidate = match.group(1).strip().lower()
            if "request" in candidate and "change" in candidate:
                return "Request changes"
            if "warning" in candidate:
                return "Accept with warnings"
            if candidate.startswith("accept"):
                return "Accept"
            if "inconclusive" in candidate:
                return "Inconclusive"
        lowered = content.lower()
        if "request changes" in lowered:
            return "Request changes"
        if "accept with warnings" in lowered:
            return "Accept with warnings"
        return "Inconclusive"

    @staticmethod
    def _parse_findings(content: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        in_findings = False
        for line in content.splitlines():
            if re.match(r"(?i)^findings\s*:?\s*$", line.strip()):
                in_findings = True
                continue
            if re.match(r"(?i)^(tests|architecture|summary|limitations)\s*:?\s*$", line.strip()):
                in_findings = False
            if in_findings and line.strip().startswith(("-", "*", "1.", "2.", "3.")):
                findings.append({"observation": line.strip()[:2000], "confidence": "heuristic"})
                if len(findings) >= 100:
                    break
        return findings

    # ------------------------------------------------------------ context
    def propose_context(self, session, repo_id: str, kind: str = "description") -> dict[str, Any]:
        repo = self.get_repo(session, repo_id)
        top = Path(repo.path)
        readme = ""
        for name in ("README.md", "README", "readme.md"):
            candidate = top / name
            if candidate.is_file():
                try:
                    readme = candidate.read_text(encoding="utf-8", errors="replace")[:8000]
                except OSError:
                    readme = ""
                break
        manifest_hint = ""
        for name in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod"):
            if (top / name).is_file():
                manifest_hint = name
                break
        recent = session.scalars(select(GitCommit).where(GitCommit.repo_id == repo_id).order_by(desc(GitCommit.committer_ts)).limit(10)).all()
        recent_lines = "; ".join(commit.subject[:120] for commit in recent[:10])
        if kind == "agents":
            target = top / "AGENTS.md"
            existing = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
            test_cmd = "npm test" if (top / "package.json").is_file() else ("pytest -q" if (top / "pyproject.toml").is_file() else "see README")
            proposal = (f"# Agent instructions — {repo.name}\n\n"
                        f"Project-specific development rules (proposed; requires approval).\n\n"
                        f"- Preserve existing behaviour unless the task requires a change.\n"
                        f"- Run `{test_cmd}` before finishing.\n"
                        f"- Do not rewrite history or modify remotes.\n"
                        f"- Keep diffs scoped; explain scope changes.\n"
                        f"- Evidence: recent work includes: {recent_lines[:500]}\n")
            return {"kind": kind, "path": str(target), "exists": bool(existing),
                    "existing": existing[:20000], "proposal": proposal,
                    "basis": {"readme_chars": len(readme), "manifest": manifest_hint, "recent": [c.subject for c in recent[:5]]}}
        target = top / "DESCRIPTION.md"
        existing = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
        proposal = (f"# {repo.name}\n\n## 1. Project purpose\n{readme[:1500] if readme else '(describe what this project is for)'}\n\n"
                    f"## 2. Problem being solved\n(recent work: {recent_lines[:600]})\n\n"
                    f"## 3. Main capabilities\n- (derived from repository evidence; refine before applying)\n\n"
                    f"## 4. Architecture\n- Repository: {repo.path}\n- Manifest: {manifest_hint or 'not detected'}\n\n"
                    f"## 5. Important components\n- (list top-level directories)\n\n## 6. Technologies\n- (from {manifest_hint or 'manifests'})\n\n"
                    f"## 7. Current development direction\n- {recent_lines[:400]}\n\n## 8. Important dependencies\n- (from manifests)\n\n"
                    f"## 9. Known limitations\n- (unknown; human review required)\n\n## 10. Where to find deeper documentation\n- README and module docs under this repository.\n")
        return {"kind": kind, "path": str(target), "exists": bool(existing),
                "existing": existing[:20000], "proposal": proposal,
                "basis": {"readme_chars": len(readme), "manifest": manifest_hint, "recent": [c.subject for c in recent[:5]]}}

    def apply_context(self, session, repo_id: str, kind: str, content: str, *, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise Conflict("Applying project context requires explicit confirmation")
        repo = self.get_repo(session, repo_id)
        filename = "AGENTS.md" if kind == "agents" else "DESCRIPTION.md"
        target = (Path(repo.path) / filename).resolve(strict=False)
        if not is_within(target, Path(repo.path)):
            raise ValidationProblem("Context path escapes the repository")
        if len(content) > 100_000:
            raise ValidationProblem("Proposed context document is too large")
        self._authorized_repo_path(session, repo)
        target.write_text(content, encoding="utf-8")
        self._refresh_context_flags(repo.path, repo)
        repo.updated_at = now_iso()
        record_activity(session, event_type="system", title=f"Project context updated ({filename})",
                        detail=f"{repo.name}: {filename}", source="mission-control", provenance="user")
        session.flush()
        return {"path": str(target), "kind": kind, "applied": True}
