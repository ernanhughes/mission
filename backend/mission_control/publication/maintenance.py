"""Automatic deterministic maintenance (MC-BOOK-PIPELINE-01, M4A).

Policy: eligible deterministic processing runs automatically; everything
else stays governed. The ONLY automatic stage in M4A is deterministic MRI
(the M3-demonstrated operation). All decisions are pure functions over
read-only inputs so they can be unit-tested without executing anything.

Two separate dimensions, never merged (author §3/§5):

- Execution: did the run complete (receipt status)?
- Freshness: does the stored artifact match the live source (projection)?
- Expenditure: provider spend, from receipt provenance (null model fields
  plus local-only flags mean zero provider spend).
- Semantic assessment: the projection result (passed/failed/pending) —
  never upgraded by a receipt.
- Attention: unexpected warnings, failures, staleness, blocks.

Current-ness is decided exclusively by the projection. A run that produces
a matching artifact flips the cell on the next read; a receipt alone flips
nothing.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mission_control.publication.pipeline import (
    STAGES_BY_ID,
    ChapterRef,
    WriterBookDefinition,
    _editing_summary_candidates,
    _parse_editing_doc,
    _project_matrices,
    _repo_roots,
    discover_chapters,
    load_writer_registry,
    resolve_registry_path,
)

logger = logging.getLogger(__name__)

#: Standing execution policy version. Bumped only after a verified engine or
#: contract change; a bump invalidates stored fingerprints and requeues
#: affected work (this is the version-aware trigger, not timestamps).
MAINTENANCE_POLICY_VERSION = "pipeline-auto-v1"

#: Pinned deterministic MRI flags. Changing these requires a new policy
#: version (and re-verification), never a parameter.
MRI_FLAGS_VERSION = "mri-deterministic-v1"

#: Stages allowlisted for automatic maintenance in M4A.
AUTO_STAGES = ("mri",)

#: The automatic twin of the governed M3 action. approval_required=False:
#: runs are authorized once by the standing policy (this module version +
#: the enabled setting), not per execution. Every run still persists a full
#: receipt row with provenance.
MRI_AUTO_ACTION_ID = "mri_observe_chapter_auto"

SETTING_ENABLED = "pipeline_auto_enabled"
SETTING_PAUSED_BOOKS = "pipeline_auto_paused_books"

DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_COOLDOWN_SECONDS = 300.0
RECENT_EXECUTIONS_SCAN = 500


# ---------------------------------------------------------------------------
# Standing policy (settings table; no migration, mirrors identity aliases)
# ---------------------------------------------------------------------------


def _read_setting(session: Any, key: str, default: Any) -> Any:
    from mission_control.models import Setting

    try:
        row = session.get(Setting, key)
    except Exception:
        return default
    if row is None or not isinstance(row.value, type(default)):
        return default
    return row.value


def _write_setting(session: Any, key: str, value: Any) -> None:
    from mission_control.models import Setting
    from mission_control.persistence.db import now_iso

    try:
        row = session.get(Setting, key)
    except Exception as exc:
        raise ValueError(f"Settings store is unavailable: {exc}") from exc
    if row is None:
        session.add(Setting(key=key, value=value, updated_at=now_iso()))
    else:
        row.value = value
        row.updated_at = now_iso()


def is_auto_enabled(session: Any) -> bool:
    """Master switch. Default False: nothing runs until explicitly enabled."""
    return bool(_read_setting(session, SETTING_ENABLED, False))


def set_auto_enabled(session: Any, enabled: bool) -> bool:
    _write_setting(session, SETTING_ENABLED, bool(enabled))
    return bool(enabled)


def paused_books(session: Any) -> list[str]:
    value = _read_setting(session, SETTING_PAUSED_BOOKS, [])
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item).strip()})


def set_book_paused(session: Any, project_id: str, paused: bool) -> list[str]:
    paused_set = set(paused_books(session))
    if paused:
        paused_set.add(project_id)
    else:
        paused_set.discard(project_id)
    ordered = sorted(paused_set)
    _write_setting(session, SETTING_PAUSED_BOOKS, ordered)
    return ordered


# ---------------------------------------------------------------------------
# Execution fingerprint (source + config + versions, never timestamps)
# ---------------------------------------------------------------------------


def auto_fingerprint(
    *,
    source_digest: str | None,
    metadata_digest: str | None,
    profile: str,
    flags_version: str = MRI_FLAGS_VERSION,
    policy_version: str = MAINTENANCE_POLICY_VERSION,
) -> str:
    """Stable identity of the inputs an automatic run depends on.

    A stored fingerprint that no longer matches means the work must be
    redone even if the projection still reads current (e.g. after a policy
    bump for a verified engine change). Timestamps and caches never participate.
    """
    canonical = json.dumps(
        {
            "source_digest": source_digest,
            "metadata_digest": metadata_digest,
            "profile": profile,
            "flags_version": flags_version,
            "policy_version": policy_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _metadata_file_digest(metadata_file: str | None) -> str | None:
    if not metadata_file:
        return None
    try:
        return hashlib.sha256(Path(metadata_file).read_bytes()).hexdigest()
    except OSError:
        return None


def build_auto_inputs(
    *,
    source_digest: str | None,
    metadata_file: str | None,
    profile: str,
) -> dict[str, Any]:
    """Fingerprint inputs for one automatic run, recorded in its receipt.

    Compared against live-recomputed inputs by :func:`decide_unit`: any
    drift (source edit, metadata edit, profile/flags/policy change) makes
    the stored fingerprint stale and requeues the work.
    """
    metadata_digest = _metadata_file_digest(metadata_file)
    fingerprint = auto_fingerprint(
        source_digest=source_digest,
        metadata_digest=metadata_digest,
        profile=profile,
    )
    return {
        "source_digest": source_digest,
        "metadata_digest": metadata_digest,
        "profile": profile,
        "flags_version": MRI_FLAGS_VERSION,
        "policy_version": MAINTENANCE_POLICY_VERSION,
        "fingerprint": fingerprint,
    }


# ---------------------------------------------------------------------------
# Decision (pure; no I/O, no execution)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MaintenanceDecision:
    action: str  # run | skip | blocked | wait
    reason: str
    fingerprint: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def decide_unit(
    *,
    stage_id: str,
    enabled: bool,
    book_paused: bool,
    cell: dict[str, Any] | None,
    live_source_digest: str | None,
    live_metadata_digest: str | None,
    profile: str,
    active_execution_id: str | None,
    last_receipt: dict[str, Any] | None,
    consecutive_failures: int,
    last_failure_at: str | None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    now_iso: str | None = None,
) -> MaintenanceDecision:
    """Decide what automatic maintenance owes one chapter-stage.

    ``cell`` is the M1/M2 projection (authority for current-ness).
    ``last_receipt`` is the latest automatic execution record for the same
    target, if any (authority for what already ran). Nothing here executes.
    """
    if stage_id not in AUTO_STAGES:
        stage = STAGES_BY_ID.get(stage_id)
        klass = stage.execution_class if stage else "governed"
        return MaintenanceDecision(
            action="skip",
            reason=(
                f"Stage {stage_id!r} is not allowlisted for automatic "
                f"maintenance (execution class: {klass})."
            ),
        )
    if not enabled:
        return MaintenanceDecision(action="wait", reason="Automatic maintenance is disabled.")
    if book_paused:
        return MaintenanceDecision(
            action="blocked", reason="Automatic maintenance is paused for this book."
        )
    if active_execution_id:
        return MaintenanceDecision(
            action="wait",
            reason=f"An automatic run is already active ({active_execution_id}).",
            detail={"active_execution_id": active_execution_id},
        )
    fingerprint = auto_fingerprint(
        source_digest=live_source_digest,
        metadata_digest=live_metadata_digest,
        profile=profile,
    )
    if cell is None:
        return MaintenanceDecision(
            action="blocked",
            reason="Chapter is not applicable or its source is unavailable.",
            fingerprint=fingerprint,
        )
    if not cell.get("applicable", True):
        return MaintenanceDecision(
            action="skip",
            reason="Stage does not apply to this chapter.",
            fingerprint=fingerprint,
        )
    if cell.get("freshness") == "current":
        if last_receipt is None:
            # Projection is authority for current-ness: good evidence needs
            # no rerun merely to mint a receipt.
            return MaintenanceDecision(
                action="skip",
                reason="Evidence is current; no provenance refresh needed.",
                fingerprint=fingerprint,
            )
        if last_receipt.get("fingerprint") == fingerprint:
            return MaintenanceDecision(
                action="skip",
                reason="Evidence is current and inputs match the last automatic run.",
                fingerprint=fingerprint,
            )
        return MaintenanceDecision(
            action="run",
            reason="Evidence reads current but inputs changed since the last automatic run; refreshing provenance.",
            fingerprint=fingerprint,
        )
    if live_source_digest is None:
        return MaintenanceDecision(
            action="blocked",
            reason="Live source is unreadable; will not queue blind work.",
            fingerprint=fingerprint,
        )
    if consecutive_failures >= max_attempts and _same_fingerprint_failures(
        last_receipt, fingerprint, consecutive_failures
    ):
        return MaintenanceDecision(
            action="blocked",
            reason=(
                f"Blocked after {consecutive_failures} consecutive failures "
                "for identical inputs; manual review required."
            ),
            fingerprint=fingerprint,
            detail={"consecutive_failures": consecutive_failures},
        )
    if last_failure_at and _within_cooldown(last_failure_at, cooldown_seconds, now_iso):
        return MaintenanceDecision(
            action="wait",
            reason="Backing off after a recent failure.",
            fingerprint=fingerprint,
            detail={"last_failure_at": last_failure_at},
        )
    state = "missing" if not cell.get("has_evidence") else str(cell.get("freshness"))
    return MaintenanceDecision(
        action="run",
        reason=f"Evidence is {state}; eligible for automatic refresh.",
        fingerprint=fingerprint,
    )


def _same_fingerprint_failures(
    last_receipt: dict[str, Any] | None, fingerprint: str, consecutive_failures: int
) -> bool:
    if consecutive_failures <= 0:
        return False
    if last_receipt is None:
        return True
    stored = last_receipt.get("fingerprint")
    return stored is None or stored == fingerprint


def _within_cooldown(last_failure_at: str, cooldown_seconds: float, now_iso: str | None) -> bool:
    try:
        failed = datetime.fromisoformat(str(last_failure_at).replace("Z", "+00:00"))
        now = (
            datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
            if now_iso
            else datetime.now(timezone.utc)
        )
        return (now - failed).total_seconds() < cooldown_seconds
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Receipt history (execution rows are the durable state; no new tables)
# ---------------------------------------------------------------------------


def _recent_auto_executions(session: Any, limit: int = RECENT_EXECUTIONS_SCAN) -> list[Any]:
    from sqlalchemy import desc, select

    from mission_control.models import IntegrationExecution

    try:
        return list(
            session.scalars(
                select(IntegrationExecution)
                .where(
                    IntegrationExecution.application_id == "writer",
                    IntegrationExecution.action_id.in_([MRI_AUTO_ACTION_ID, "mri_observe_chapter"]),
                )
                .order_by(desc(IntegrationExecution.created_at))
                .limit(limit)
            ).all()
        )
    except Exception:
        return []


def _target_key(parameters: dict[str, Any] | None) -> tuple[str, str] | None:
    if not isinstance(parameters, dict):
        return None
    chapter = str(parameters.get("chapter_file") or "").strip()
    output = str(parameters.get("output_dir") or "").strip()
    if not chapter or not output:
        return None
    return (chapter, output)


def index_receipts_by_target(executions: list[Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Latest receipt, active run, and consecutive-failure counts per target."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for execution in sorted(
        executions, key=lambda e: str(getattr(e, "created_at", "") or ""), reverse=True
    ):
        key = _target_key(getattr(execution, "parameters", None))
        if key is None:
            continue
        entry = index.setdefault(
            key, {"latest": None, "active_id": None, "failures": 0, "last_failure_at": None}
        )
        status = str(getattr(execution, "status", ""))
        if status in ("queued", "running") and entry["active_id"] is None:
            entry["active_id"] = str(getattr(execution, "id", ""))
        if entry["latest"] is None and status in ("succeeded", "failed"):
            result = getattr(execution, "result", None)
            fingerprint = (result or {}).get("auto_fingerprint")
            if fingerprint is None and isinstance((result or {}).get("auto_inputs"), dict):
                fingerprint = (result or {})["auto_inputs"].get("fingerprint")
            entry["latest"] = {
                "status": status,
                "fingerprint": fingerprint if isinstance(result, dict) else None,
                "artifact_ref": getattr(execution, "artifact_ref", None),
                "ended_at": getattr(execution, "ended_at", None),
            }
        if status == "failed" and entry["last_failure_at"] is None:
            entry["last_failure_at"] = getattr(execution, "ended_at", None)
        if status == "failed":
            entry["failures"] += 0  # counted below in chronological order instead
    # Consecutive failures since the last success, oldest-first.
    for key in index:
        failures = 0
        for execution in sorted(
            [e for e in executions if _target_key(getattr(e, "parameters", None)) == key],
            key=lambda e: str(getattr(e, "created_at", "") or ""),
        ):
            status = str(getattr(execution, "status", ""))
            if status == "failed":
                failures += 1
                if index[key]["last_failure_at"] is None:
                    index[key]["last_failure_at"] = getattr(execution, "ended_at", None)
            elif status == "succeeded":
                failures = 0
        index[key]["failures"] = failures
    return index


# ---------------------------------------------------------------------------
# Maintenance service (bounded, sequential, restart-safe by construction)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MaintenanceReport:
    started_at: str
    elapsed_ms: int
    enabled: bool
    books_scanned: int
    dry_run: bool = False
    eligible: list[dict[str, Any]] = field(default_factory=list)
    dispatched: list[dict[str, Any]] = field(default_factory=list)
    skipped: int = 0
    blocked: int = 0
    waiting: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "elapsed_ms": self.elapsed_ms,
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "books_scanned": self.books_scanned,
            "eligible": list(self.eligible),
            "dispatched": list(self.dispatched),
            "skipped": self.skipped,
            "blocked": self.blocked,
            "waiting": self.waiting,
            "errors": list(self.errors),
        }


class MaintenanceService:
    """Periodic automatic maintenance over the existing execution lifecycle.

    Sequential by design (one dispatch per pass at most): bounded without a
    pool. State beyond the current pass lives in execution rows (durable)
    and the projection (authoritative); only debounce windows are in memory
    and are safe to lose (reconciliation recomputes from receipts).
    """

    def __init__(
        self,
        database: Any,
        settings: Any,
        integration_service: Any,
        *,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        debounce_passes: int = 2,
    ) -> None:
        self._database = database
        self._settings = settings
        self._integrations = integration_service
        self._interval = max(5.0, float(interval_seconds))
        self._max_attempts = max(1, int(max_attempts))
        self._cooldown = max(0.0, float(cooldown_seconds))
        self._debounce_passes = max(1, int(debounce_passes))
        self._debounce: dict[tuple[str, str, str], tuple[str | None, int]] = {}
        self._dispatch_cooldowns: dict[tuple[str, str, str], float] = {}
        self._task: asyncio.Task[None] | None = None
        self._last_report: MaintenanceReport | None = None

    @property
    def last_report(self) -> MaintenanceReport | None:
        return self._last_report

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="pipeline-maintenance")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        await self.run_once()
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Automatic maintenance pass failed; will retry next interval")

    async def run_once(
        self, *, dispatch: bool | None = None, dry_run: bool = False
    ) -> MaintenanceReport:
        """One reconciliation pass.

        ``dispatch=None`` follows the enabled setting. ``dry_run=True``
        computes decisions as if enabled but never dispatches, so callers can
        preview what *would* run without running it.
        """
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        report = MaintenanceReport(
            started_at=started_at, elapsed_ms=0, enabled=False, books_scanned=0
        )
        report.dry_run = dry_run
        try:
            snapshot = load_writer_registry(resolve_registry_path(self._settings))
        except Exception as exc:
            report.errors.append(f"Writer registry could not be loaded: {exc}.")
            return self._finish(report, started)
        with self._database.session() as session:
            setting_enabled = is_auto_enabled(session)
            paused = set(paused_books(session))
            decide_enabled = (
                True if dry_run else (setting_enabled if dispatch is None else bool(dispatch))
            )
            may_dispatch = (setting_enabled if dispatch is None else bool(dispatch)) and not dry_run
            report.enabled = setting_enabled
            try:
                executions = _recent_auto_executions(session)
            except Exception as exc:
                report.errors.append(f"Execution history is unavailable: {exc}.")
                return self._finish(report, started)
            receipts = index_receipts_by_target(executions)
            store_docs: dict[str, tuple[Any | None, str | None]] = {}
            for project_id in sorted(snapshot.books):
                definition = snapshot.books[project_id]
                chapters, discovery = discover_chapters(definition)
                if discovery.get("error"):
                    report.errors.append(f"{project_id}: {discovery.get('error')}")
                    continue
                report.books_scanned += 1
                repo_roots = _repo_roots(definition)
                editing_path, editing_info = _editing_summary_candidates(
                    self._settings, snapshot.source_path, repo_roots
                )
                store_key = str(editing_path) if editing_path is not None else "__none__"
                if store_key not in store_docs:
                    store_docs[store_key] = (
                        _parse_editing_doc(editing_path)
                        if editing_path is not None
                        else (None, None)
                    )
                matrix, _summaries = _project_matrices(
                    definition,
                    project_id,
                    chapters,
                    discovery,
                    repo_roots,
                    editing_path,
                    editing_info,
                    store_docs[store_key],
                )
                cells = matrix.get("mri", [])
                for chapter in chapters:
                    cell = next((c for c in cells if c["chapter_id"] == chapter.chapter_id), None)
                    unit = self._decide_target(
                        project_id=project_id,
                        chapter=chapter,
                        cell=cell,
                        definition=definition,
                        enabled=decide_enabled,
                        book_paused=project_id in paused,
                        receipts=receipts,
                        metadata_digest=_metadata_file_digest(
                            self._metadata_path(definition, chapter)
                        ),
                    )
                    if unit["decision"].action == "run":
                        report.eligible.append(unit["public"])
                    elif unit["decision"].action == "blocked":
                        report.blocked += 1
                    elif unit["decision"].action == "wait":
                        report.waiting += 1
                    else:
                        report.skipped += 1
                    if unit["decision"].action == "run" and may_dispatch and not report.dispatched:
                        dispatched = await self._dispatch(session, unit)
                        if dispatched is not None:
                            report.dispatched.append(dispatched)
                        else:
                            report.blocked += 1
                            self._dispatch_cooldowns[
                                (project_id, unit["chapter"].chapter_id, "mri")
                            ] = time.monotonic() + self._cooldown
                session.commit()
        return self._finish(report, started)

    def _finish(self, report: MaintenanceReport, started: float) -> MaintenanceReport:
        report.elapsed_ms = int((time.perf_counter() - started) * 1000)
        self._last_report = report
        return report

    @staticmethod
    def _metadata_path(definition: WriterBookDefinition, chapter: ChapterRef) -> str | None:
        if definition.metadata_dir is None:
            return None
        candidate = definition.metadata_dir / f"{chapter.chapter_id}.yaml"
        try:
            return str(candidate) if candidate.is_file() else None
        except OSError:
            return None

    def _decide_target(
        self,
        *,
        project_id: str,
        chapter: ChapterRef,
        cell: dict[str, Any] | None,
        definition: WriterBookDefinition,
        enabled: bool,
        book_paused: bool,
        receipts: dict[tuple[str, str], dict[str, Any]],
        metadata_digest: str | None,
    ) -> dict[str, Any]:
        live_source = (cell or {}).get("live_digest")
        target = (str(chapter.path), "")
        receipt_entry: dict[str, Any] | None = None
        for key, entry in receipts.items():
            if key[0] == str(chapter.path):
                receipt_entry = entry
                target = key
                break
        last_receipt = receipt_entry["latest"] if receipt_entry else None
        active_id = receipt_entry["active_id"] if receipt_entry else None
        failures = receipt_entry["failures"] if receipt_entry else 0
        last_failure_at = receipt_entry["last_failure_at"] if receipt_entry else None
        decision = decide_unit(
            stage_id="mri",
            enabled=enabled,
            book_paused=book_paused,
            cell=cell,
            live_source_digest=live_source,
            live_metadata_digest=metadata_digest,
            profile=definition.profile,
            active_execution_id=active_id,
            last_receipt=last_receipt,
            consecutive_failures=failures,
            last_failure_at=last_failure_at,
            max_attempts=self._max_attempts,
            cooldown_seconds=self._cooldown,
        )
        if decision.action == "run" and live_source is not None:
            key = (project_id, chapter.chapter_id, "mri")
            if len(self._debounce) > 5000:
                self._debounce.pop(next(iter(self._debounce)))
            seen = self._debounce.get(key)
            if seen is None or seen[0] != live_source:
                self._debounce[key] = (live_source, 1)
                decision = MaintenanceDecision(
                    action="wait",
                    reason="Digest changed; waiting one pass to debounce mid-save edits.",
                    fingerprint=decision.fingerprint,
                )
            elif seen[1] < self._debounce_passes - 1:
                self._debounce[key] = (live_source, seen[1] + 1)
                decision = MaintenanceDecision(
                    action="wait",
                    reason="Digest changed; waiting one pass to debounce mid-save edits.",
                    fingerprint=decision.fingerprint,
                )
            else:
                cooled = self._dispatch_cooldowns.get(key, 0.0)
                if cooled and time.monotonic() < cooled:
                    decision = MaintenanceDecision(
                        action="wait",
                        reason="Dispatch failed recently; cooling down before retry.",
                        fingerprint=decision.fingerprint,
                    )
        public = {
            "project_id": project_id,
            "chapter_id": chapter.chapter_id,
            "stage_id": "mri",
            "decision": decision.action,
            "reason": decision.reason,
            "fingerprint": decision.fingerprint,
            "result": (cell or {}).get("result"),
            "freshness": (cell or {}).get("freshness"),
            "has_evidence": bool((cell or {}).get("has_evidence")),
        }
        return {
            "decision": decision,
            "public": public,
            "target": target,
            "chapter": chapter,
            "definition": definition,
            "metadata_digest": metadata_digest,
        }

    async def _dispatch(self, session: Any, unit: dict[str, Any]) -> dict[str, Any] | None:
        chapter: ChapterRef = unit["chapter"]
        definition: WriterBookDefinition = unit["definition"]
        metadata_file = self._metadata_path(definition, chapter)
        output_dir = self._mri_output_dir(definition)
        if output_dir is None:
            return None
        try:
            from mission_control.integrations.service import IntegrationService

            assert isinstance(self._integrations, IntegrationService)
            execution = await self._integrations.start_action(
                "writer",
                MRI_AUTO_ACTION_ID,
                {
                    "chapter_file": str(chapter.path),
                    "output_dir": str(output_dir),
                    "profile": definition.profile
                    if definition.profile in ("technical", "fiction")
                    else "technical",
                    "policy_version": MAINTENANCE_POLICY_VERSION,
                    **({"metadata_file": metadata_file} if metadata_file else {}),
                },
                confirm=True,
            )
        except Exception:
            logger.exception("Automatic dispatch failed for %s", chapter.chapter_id)
            return None
        return {
            "execution_id": execution.id,
            "project_id": unit["public"]["project_id"],
            "chapter_id": chapter.chapter_id,
            "stage_id": "mri",
        }

    @staticmethod
    def _mri_output_dir(definition: WriterBookDefinition) -> Path | None:
        for root in (definition.repo_path, definition.project_root):
            try:
                candidate = Path(root) / ".writer" / "mri" / definition.project_id
            except (OSError, TypeError):
                continue
            try:
                candidate.mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
            try:
                if candidate.is_dir():
                    return candidate
            except OSError:
                continue
        return None


# ---------------------------------------------------------------------------
# Status snapshot for the UI (read-only)
# ---------------------------------------------------------------------------


def maintenance_retry(
    session: Any,
    settings: Any,
    integration_service: Any,
    *,
    project_id: str,
    chapter_id: str,
    stage_id: str = "mri",
) -> dict[str, Any]:
    """Dispatch one automatic run for a specific chapter-stage as a recovery control.

    Resolves all Writer paths server-side from the registry (the UI never
    supplies filesystem paths). Only allowlisted automatic stages may run;
    governed stages must use their own explicit flows.
    """
    from mission_control.adapters.writer import _validate_mri_observe_chapter

    if stage_id not in AUTO_STAGES:
        stage = STAGES_BY_ID.get(stage_id)
        klass = stage.execution_class if stage else "governed"
        raise ValueError(
            f"Stage {stage_id!r} is not automatic (execution class: {klass}); "
            "manual retry is not available for it in M4A."
        )
    snapshot = load_writer_registry(resolve_registry_path(settings))
    definition = snapshot.books.get(project_id) if snapshot else None
    if definition is None:
        raise ValueError(f"Unknown book {project_id!r}.")
    chapters, discovery = discover_chapters(definition)
    if discovery.get("error"):
        raise ValueError(str(discovery.get("error")))
    chapter = next((c for c in chapters if c.chapter_id == chapter_id), None)
    if chapter is None:
        raise ValueError(f"Chapter {chapter_id!r} is not applicable for {project_id!r}.")
    output_dir = MaintenanceService._mri_output_dir(definition)
    if output_dir is None:
        raise ValueError("No writable Writer report directory is available for this book.")
    metadata_file = MaintenanceService._metadata_path(definition, chapter)
    parameters: dict[str, Any] = {
        "chapter_file": str(chapter.path),
        "output_dir": str(output_dir),
        "profile": definition.profile
        if definition.profile in ("technical", "fiction")
        else "technical",
        "policy_version": MAINTENANCE_POLICY_VERSION,
    }
    if metadata_file:
        parameters["metadata_file"] = metadata_file
    _validate_mri_observe_chapter(parameters)
    return {
        "application_id": "writer",
        "action_id": MRI_AUTO_ACTION_ID,
        "parameters": parameters,
    }


def maintenance_status(database: Any, settings: Any) -> dict[str, Any]:
    """Read-only maintenance state: policy, switches, queue preview, activity."""
    started = time.perf_counter()
    with database.session() as session:
        enabled = is_auto_enabled(session)
        paused = paused_books(session)
    try:
        snapshot = load_writer_registry(resolve_registry_path(settings))
    except Exception as exc:
        return {
            "policy_version": MAINTENANCE_POLICY_VERSION,
            "auto_stages": list(AUTO_STAGES),
            "enabled": enabled,
            "paused_books": paused,
            "book_count": 0,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "books": [],
            "queue_preview": [],
            "active": [],
            "recent_failures": [],
            "diagnostics": f"Writer registry could not be loaded: {exc}.",
        }
    books: list[dict[str, Any]] = []
    try:
        with database.session() as session:
            executions = _recent_auto_executions(session)
        receipts = index_receipts_by_target(executions)
        active = [
            {
                "execution_id": entry["active_id"],
                "chapter_file": key[0],
            }
            for key, entry in receipts.items()
            if entry.get("active_id")
        ]
        recent_failures: list[dict[str, Any]] = []
        for execution in executions:
            if str(getattr(execution, "status", "")) != "failed":
                continue
            parameters = getattr(execution, "parameters", None) or {}
            recent_failures.append(
                {
                    "execution_id": str(getattr(execution, "id", "")),
                    "chapter_file": str(parameters.get("chapter_file", "")),
                    "error": str(getattr(execution, "error", "") or "")[:500],
                    "ended_at": str(getattr(execution, "ended_at", "") or ""),
                }
            )
            if len(recent_failures) >= 20:
                break
    except Exception as exc:
        receipts = {}
        active = []
        recent_failures = [{"error": f"Execution history is unavailable: {exc}."}]
    for project_id in sorted(snapshot.books):
        books.append({"project_id": project_id, "paused": project_id in paused})
    return {
        "policy_version": MAINTENANCE_POLICY_VERSION,
        "auto_stages": list(AUTO_STAGES),
        "enabled": enabled,
        "paused_books": paused,
        "book_count": len(books),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "books": books,
        "queue_preview": [],
        "active": active,
        "recent_failures": recent_failures,
        "queue_note": (
            "Queue preview is computed on demand by POST "
            "/api/pipeline/maintenance/reconcile (dry run when disabled)."
        ),
        "refresh_note": "Read-only. Dispatch only happens inside a reconcile pass when enabled.",
    }
