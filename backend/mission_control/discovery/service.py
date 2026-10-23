"""Background discovery lifecycle and persistence."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select

from mission_control.activity.service import record_activity
from mission_control.core.errors import Conflict
from mission_control.discovery.scanner import ScanResult, scan_roots
from mission_control.models import (
    Application,
    DiscoveryRoot,
    ProjectRepository,
    Repository,
    Setting,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.persistence.seed import repository_id

logger = logging.getLogger(__name__)


class DiscoveryService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._task: asyncio.Task[None] | None = None
        self._cancel = threading.Event()
        self._status: dict[str, Any] = self._load_last_status()
        self._lock = asyncio.Lock()

    def _load_last_status(self) -> dict[str, Any]:
        with self.database.session() as session:
            setting = session.get(Setting, "discovery.last_scan")
            if setting and isinstance(setting.value, dict):
                return {**setting.value, "running": False}
        return {"running": False, "status": "idle", "scan_id": None}

    @property
    def status(self) -> dict[str, Any]:
        return dict(self._status)

    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self._task and not self._task.done():
                raise Conflict("A discovery scan is already running")
            self._cancel.clear()
            scan_id = f"scan-{uuid.uuid4().hex[:12]}"
            self._status = {
                "scan_id": scan_id,
                "status": "running",
                "running": True,
                "started_at": now_iso(),
                "finished_at": None,
                "roots": [],
                "counts": {},
                "errors": [],
                "truncated": False,
                "cancelled": False,
                "scanned_directories": 0,
                "elapsed_seconds": None,
            }
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

    async def _run(self, scan_id: str) -> None:
        try:
            with self.database.session() as session:
                roots = [
                    row.path
                    for row in session.scalars(
                        select(DiscoveryRoot).where(DiscoveryRoot.enabled.is_(True))
                    )
                ]
                discovery_settings = session.get(Setting, "discovery")
                config = discovery_settings.value if discovery_settings else {}
            exclusions = config.get("exclusions", []) if isinstance(config, dict) else []
            max_depth = int(config.get("max_depth", 1)) if isinstance(config, dict) else 1
            max_candidates = (
                int(config.get("max_candidates", 500)) if isinstance(config, dict) else 500
            )
            timeout = float(config.get("timeout_seconds", 120)) if isinstance(config, dict) else 120.0
            git_timeout = (
                float(config.get("git_timeout_seconds", 5)) if isinstance(config, dict) else 5.0
            )
            self._status["roots"] = roots
            result = await asyncio.to_thread(
                scan_roots,
                roots,
                exclusion_patterns=exclusions,
                max_depth=max_depth,
                max_candidates=max_candidates,
                timeout_seconds=timeout,
                git_timeout_seconds=git_timeout,
                cancel_event=self._cancel,
            )
            await asyncio.to_thread(self._persist, scan_id, result, roots)
            counts = Counter(candidate.classification for candidate in result.candidates)
            self._status.update(
                {
                    "status": "cancelled" if result.cancelled else "complete",
                    "running": False,
                    "finished_at": now_iso(),
                    "counts": dict(counts),
                    "errors": result.errors[:50],
                    "truncated": result.truncated,
                    "cancelled": result.cancelled,
                    "scanned_directories": result.scanned_directories,
                    "elapsed_seconds": result.elapsed_seconds,
                    "candidate_count": len(result.candidates),
                    "excluded_count": result.excluded_count,
                    "skipped_links": result.skipped_links[:20],
                }
            )
        except Exception as exc:  # discovery failure must not take down the dashboard
            logger.exception("Discovery scan failed")
            self._status.update(
                {
                    "status": "failed",
                    "running": False,
                    "finished_at": now_iso(),
                    "error": str(exc)[:500],
                }
            )
        finally:
            summary = {
                key: value
                for key, value in self._status.items()
                if key not in {"running"}
            }
            try:
                with self.database.session() as session:
                    setting = session.get(Setting, "discovery.last_scan")
                    if setting is None:
                        session.add(
                            Setting(key="discovery.last_scan", value=summary, updated_at=now_iso())
                        )
                    else:
                        setting.value = summary
                        setting.updated_at = now_iso()
            except Exception:  # pragma: no cover - defensive
                logger.exception("Could not persist last discovery scan")

    def _persist(self, scan_id: str, result: ScanResult, roots: list[str]) -> None:
        with self.database.session() as session:
            linked_paths = {
                os.path.normcase(row)
                for row in session.scalars(select(Application.repository_path)).all()
                if row
            }
            linked_paths.update(
                os.path.normcase(row.path)
                for row in session.scalars(
                    select(Repository).join(
                        ProjectRepository, ProjectRepository.repository_id == Repository.id
                    )
                )
            )
            count = 0
            for candidate in result.candidates:
                existing = session.scalar(
                    select(Repository).where(Repository.path == candidate.path)
                )
                repo = existing or Repository(
                    id=repository_id(candidate.path),
                    path=candidate.path,
                    name=candidate.name,
                    first_seen_at=now_iso(),
                )
                repo.name = candidate.name
                repo.classification = candidate.classification
                repo.confidence = candidate.confidence
                repo.evidence = candidate.evidence[:20]
                repo.source_root = candidate.source_root
                repo.is_git = candidate.is_git
                repo.accessible = candidate.accessible
                repo.candidate = os.path.normcase(candidate.path) not in linked_paths
                git = candidate.git or {}
                repo.branch = git.get("branch")
                repo.commit_hash = git.get("commit")
                repo.last_commit_at = git.get("last_commit_at")
                repo.dirty = git.get("dirty")
                repo.last_observed_at = now_iso()
                if candidate.error:
                    repo.notes = candidate.error[:500]
                if existing is None:
                    session.add(repo)
                count += 1
            counts = Counter(candidate.classification for candidate in result.candidates)
            record_activity(
                session,
                event_type="discovery_scan",
                title=f"Discovered {count} repository candidates",
                detail=", ".join(f"{key}: {value}" for key, value in sorted(counts.items())),
                source="mission-control",
                provenance="verified_observation",
                metadata={
                    "scan_id": scan_id,
                    "roots": roots,
                    "counts": dict(counts),
                    "cancelled": result.cancelled,
                    "truncated": result.truncated,
                },
            )
            session.flush()
