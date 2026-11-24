"""Automatic deterministic Writer maintenance for blog posts (BLOG-01 D5).

Bounded, read-only-until-dispatch maintenance over the existing
``integration_executions`` lifecycle. Only the verified deterministic Writer
artifact observation may run automatically, only for eligible posts, one at
a time, with standing (not per-run) authorization recorded in settings.

Separation of concerns (never merged):
- execution: did the run complete (receipt status);
- freshness: does the stored body sha match the live body (projection);
- expenditure: always zero provider spend (deterministic local detector);
- editorial judgement: untouched (blog-editorial-v1 lives elsewhere);
- human review: untouched (existing reviews flow).

A successfully executed detector does not establish editorial quality.
Unknown, missing, stale, and unavailable stay explicit and distinct.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mission_control.websites import posts as _posts

logger = logging.getLogger(__name__)

BLOG_AUTO_POLICY_VERSION = "blog-auto-v1"
BLOG_FLAGS_VERSION = "writer-artifact-detection.v1"
BLOG_AUTO_ACTION_ID = "writer_observe_post_auto"

SETTING_ENABLED = "blog_auto_enabled"
SETTING_PAUSED_SITES = "blog_auto_paused_websites"

DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_COOLDOWN_SECONDS = 300.0
RECENT_EXECUTIONS_SCAN = 200


def auto_fingerprint(
    *,
    source_digest: str | None,
    metadata_digest: str | None,
    profile: str,
    flags_version: str = BLOG_FLAGS_VERSION,
    policy_version: str = BLOG_AUTO_POLICY_VERSION,
) -> str:
    """Stable identity of the inputs an automatic run depends on.

    Intentional contract-copy of the book-pipeline fingerprint (same
    canonical JSON scheme) so receipts stay comparable if the two
    maintenance tracks are ever unified. Kept local so D5 does not
    depend on the uncommitted pipeline-maintenance module: timestamps
    and caches never participate.
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


# ---------------------------------------------------------------------------
# Standing policy (settings table; no migration)


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

    row = session.get(Setting, key)
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


def paused_websites(session: Any) -> list[str]:
    value = _read_setting(session, SETTING_PAUSED_SITES, [])
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item).strip()})


def set_website_paused(session: Any, website_id: str, paused: bool) -> list[str]:
    paused_set = set(paused_websites(session))
    if paused:
        paused_set.add(website_id)
    else:
        paused_set.discard(website_id)
    ordered = sorted(paused_set)
    _write_setting(session, SETTING_PAUSED_SITES, ordered)
    return ordered


def build_auto_inputs(*, source_digest: str | None, content_digest: str | None) -> dict[str, Any]:
    """Fingerprint inputs for one automatic post observation."""
    fingerprint = auto_fingerprint(
        source_digest=source_digest,
        metadata_digest=content_digest,
        profile="post",
        flags_version=BLOG_FLAGS_VERSION,
        policy_version=BLOG_AUTO_POLICY_VERSION,
    )
    return {
        "source_digest": source_digest,
        "metadata_digest": content_digest,
        "profile": "post",
        "flags_version": BLOG_FLAGS_VERSION,
        "policy_version": BLOG_AUTO_POLICY_VERSION,
        "fingerprint": fingerprint,
    }


# ---------------------------------------------------------------------------
# Projection: stored Writer evidence vs live bytes (read-only)


def _live_body(blog_dir: Path, relpath: str) -> tuple[bytes | None, str | None, str | None]:
    """Return (body_bytes, body_sha256, diagnostic) for the live post body.

    Unreadable, unmappable, or over-budget sources yield ``None`` bytes with
    an explicit reason — never guessed bytes.
    """
    from mission_control.websites import context as _context

    try:
        candidate = blog_dir / Path(*Path(relpath).parts)
        raw = candidate.read_bytes()
    except (OSError, ValueError) as exc:
        return None, None, f"Post file is not accessible: {exc}."
    if len(raw) > 2_000_000:
        return None, None, "Post exceeds the automatic-observation budget (2 MB)."
    try:
        split = _context.split_post_body(raw)
    except Exception as exc:
        return None, None, f"Post body cannot be mapped: {exc}."
    body = split.get("body")
    if not isinstance(body, bytes) or not body:
        return None, None, str(split.get("note") or "Post body cannot be mapped.")
    return body, hashlib.sha256(body).hexdigest(), None


def project_post_state(
    session: Any, *, website_id: str, identity: str, relpath: str, blog_dir: Path
) -> dict[str, Any]:
    """Current stored Writer evidence for one post plus the live digest.

    Read-only. ``has_evidence`` is False until a stored observation exists;
    freshness compares the stored body sha against the live evaluated body.
    """
    from mission_control.models import WebsitePostWriterObservation
    from sqlalchemy import desc, select

    try:
        rows = session.scalars(
            select(WebsitePostWriterObservation)
            .where(
                WebsitePostWriterObservation.website_id == website_id,
                WebsitePostWriterObservation.article_identity == identity,
            )
            .order_by(desc(WebsitePostWriterObservation.created_at))
            .limit(50)
        ).all()
    except Exception:
        rows = []
    stored = rows[0] if rows else None
    _body, live_digest, unavailable_reason = _live_body(blog_dir, relpath)
    if stored is None:
        return {
            "has_evidence": False,
            "freshness": "missing" if live_digest else "unknown",
            "result": "unknown",
            "stored": None,
            "live_digest": live_digest,
            "history_count": len(rows),
            "unavailable_reason": unavailable_reason,
        }
    if live_digest is None:
        return {
            "has_evidence": True,
            "freshness": "unknown",
            "result": "unknown",
            "stored": _observation_summary(stored),
            "live_digest": None,
            "history_count": len(rows),
            "unavailable_reason": unavailable_reason,
        }
    match = stored.body_sha256 == live_digest
    return {
        "has_evidence": True,
        "freshness": "current" if match else "stale",
        "result": "passed" if stored.status == "complete" else "pending",
        "stored": _observation_summary(stored),
        "live_digest": live_digest,
        "history_count": len(rows),
        "unavailable_reason": None,
    }


def _observation_summary(row: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(row, "id", "")),
        "status": str(getattr(row, "status", "")),
        "evaluation_id": str(getattr(row, "evaluation_id", "")),
        "finding_count": int(getattr(row, "finding_count", 0) or 0),
        "observed_at": str(getattr(row, "observed_at", "") or ""),
        "created_at": str(getattr(row, "created_at", "") or ""),
        "execution_id": getattr(row, "execution_id", None),
        "fingerprint": str(getattr(row, "fingerprint", "") or ""),
    }


# ---------------------------------------------------------------------------
# Decision (pure; no I/O, no execution)


@dataclass(slots=True)
class MaintenanceDecision:
    action: str  # run | skip | blocked | wait
    reason: str
    fingerprint: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def decide_post(
    *,
    enabled: bool,
    site_paused: bool,
    state: dict[str, Any] | None,
    live_source_digest: str | None,
    live_content_digest: str | None,
    active_execution_id: str | None,
    last_receipt: dict[str, Any] | None,
    consecutive_failures: int,
    last_failure_at: str | None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    now_iso: str | None = None,
) -> MaintenanceDecision:
    """Decide what automatic maintenance owes one post."""
    if not enabled:
        return MaintenanceDecision(action="wait", reason="Automatic maintenance is disabled.")
    if site_paused:
        return MaintenanceDecision(
            action="blocked", reason="Automatic maintenance is paused for this site."
        )
    if active_execution_id:
        return MaintenanceDecision(
            action="wait",
            reason=f"An automatic run is already active ({active_execution_id}).",
            detail={"active_execution_id": active_execution_id},
        )
    fingerprint = auto_fingerprint(
        source_digest=live_source_digest,
        metadata_digest=live_content_digest,
        profile="post",
        flags_version=BLOG_FLAGS_VERSION,
        policy_version=BLOG_AUTO_POLICY_VERSION,
    )
    if state is None:
        return MaintenanceDecision(
            action="blocked",
            reason="Post is not applicable or its source is unavailable.",
            fingerprint=fingerprint,
        )
    if not state.get("applicable", True):
        return MaintenanceDecision(
            action="skip", reason="Post is not applicable.", fingerprint=fingerprint
        )
    if state.get("freshness") == "current":
        if last_receipt is None:
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
            reason="Evidence reads current but inputs changed since the last automatic run.",
            fingerprint=fingerprint,
        )
    if live_source_digest is None:
        return MaintenanceDecision(
            action="blocked",
            reason=state.get("unavailable_reason")
            or "Live source is unreadable; will not queue blind work.",
            fingerprint=fingerprint,
        )
    if consecutive_failures >= max_attempts and _same_fingerprint_failures(
        last_receipt, fingerprint, consecutive_failures
    ):
        return MaintenanceDecision(
            action="blocked",
            reason=f"Blocked after {consecutive_failures} consecutive failures for identical inputs; manual review required.",
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
    if state.get("has_evidence"):
        state_label = f"stale ({state.get('result', 'unknown')})"
    else:
        state_label = "missing"
    return MaintenanceDecision(
        action="run",
        reason=f"Writer evidence is {state_label}; eligible for automatic refresh.",
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
    from datetime import timezone

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
# Receipt history (durable; no new tables beyond the observation store)


def _recent_auto_executions(session: Any, limit: int = RECENT_EXECUTIONS_SCAN) -> list[Any]:
    from sqlalchemy import desc, select

    from mission_control.models import IntegrationExecution

    try:
        return list(
            session.scalars(
                select(IntegrationExecution)
                .where(
                    IntegrationExecution.application_id == "writer",
                    IntegrationExecution.action_id.in_(
                        ["writer_observe_post_auto", "writer_observe_post"]
                    ),
                )
                .order_by(desc(IntegrationExecution.created_at))
                .limit(limit)
            ).all()
        )
    except Exception:
        return []


def index_receipts_by_target(executions: list[Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Latest receipt, active run, and consecutive failures per (site, post)."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for execution in sorted(
        executions, key=lambda e: str(getattr(e, "created_at", "") or ""), reverse=True
    ):
        parameters = getattr(execution, "parameters", None) or {}
        key = (str(parameters.get("website_id", "")), str(parameters.get("article_identity", "")))
        if not key[0] or not key[1]:
            continue
        entry = index.setdefault(
            key, {"latest": None, "active_id": None, "failures": 0, "last_failure_at": None}
        )
        status = str(getattr(execution, "status", ""))
        if status in ("queued", "running") and entry["active_id"] is None:
            entry["active_id"] = str(getattr(execution, "id", ""))
        if entry["latest"] is None and status in ("succeeded", "failed"):
            result = getattr(execution, "result", None)
            fingerprint = None
            if isinstance(result, dict):
                fingerprint = result.get("auto_fingerprint")
                if fingerprint is None and isinstance(result.get("auto_inputs"), dict):
                    fingerprint = result["auto_inputs"].get("fingerprint")
            entry["latest"] = {
                "status": status,
                "fingerprint": fingerprint,
                "artifact_ref": getattr(execution, "artifact_ref", None),
                "ended_at": getattr(execution, "ended_at", None),
            }
    for key in index:
        failures = 0
        for execution in sorted(
            [e for e in executions if _execution_key(e) == key],
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


def _execution_key(execution: Any) -> tuple[str, str]:
    parameters = getattr(execution, "parameters", None) or {}
    return (str(parameters.get("website_id", "")), str(parameters.get("article_identity", "")))


# ---------------------------------------------------------------------------
# Maintenance service (sequential, bounded, restart-safe by construction)


@dataclass(slots=True)
class MaintenanceReport:
    started_at: str
    elapsed_ms: int
    enabled: bool
    websites_scanned: int
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
            "websites_scanned": self.websites_scanned,
            "eligible": list(self.eligible),
            "dispatched": list(self.dispatched),
            "skipped": self.skipped,
            "blocked": self.blocked,
            "waiting": self.waiting,
            "errors": list(self.errors),
        }


class BlogMaintenanceService:
    """Sequential automatic Writer maintenance for blog posts.

    One dispatch per pass at most. State beyond the current pass lives in
    execution rows (durable) and stored observations (durable); only the
    debounce window is in-memory and safe to lose.
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
        self._debounce: dict[tuple[str, str], tuple[str | None, int]] = {}
        self._dispatch_cooldowns: dict[tuple[str, str], float] = {}
        self._task: asyncio.Task[None] | None = None
        self._last_report: MaintenanceReport | None = None

    @property
    def last_report(self) -> MaintenanceReport | None:
        return self._last_report

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="blog-maintenance")

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
                logger.exception("Blog maintenance pass failed; will retry next interval.")

    async def run_once(
        self, *, dispatch: bool | None = None, dry_run: bool = False
    ) -> MaintenanceReport:
        """One reconciliation pass. ``dispatch=None`` follows the enabled setting."""
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        report = MaintenanceReport(
            started_at=started_at, elapsed_ms=0, enabled=False, websites_scanned=0, dry_run=dry_run
        )
        try:
            with self._database.session() as session:
                setting_enabled = is_auto_enabled(session)
                paused = set(paused_websites(session))
                decide_enabled = (
                    True if dry_run else (setting_enabled if dispatch is None else bool(dispatch))
                )
                may_dispatch = (
                    setting_enabled if dispatch is None else bool(dispatch)
                ) and not dry_run
                report.enabled = setting_enabled
                try:
                    executions = _recent_auto_executions(session)
                except Exception as exc:
                    report.errors.append(f"Execution history is unavailable: {exc}.")
                    return self._finish(report, started)
                receipts = index_receipts_by_target(executions)
                try:
                    from mission_control.discovery.websites import detect_websites

                    detected, _diagnostics = detect_websites([self._settings.websites_root])
                except Exception as exc:
                    report.errors.append(f"Website discovery is unavailable: {exc}.")
                    return self._finish(report, started)
                for site in detected:
                    if not getattr(site, "content_section", None):
                        continue
                    project_id = str(site.id)
                    report.websites_scanned += 1
                    try:
                        blog_dir = Path(site.path) / "content" / site.content_section
                    except (OSError, TypeError, ValueError):
                        report.errors.append(f"{project_id}: blog directory is not resolvable.")
                        continue
                    for post in self._published_posts(blog_dir):
                        unit = self._decide_post(
                            project_id=project_id,
                            blog_dir=blog_dir,
                            post=post,
                            enabled=decide_enabled,
                            site_paused=project_id in paused,
                            receipts=receipts,
                        )
                        if unit["decision"].action == "run":
                            report.eligible.append(unit["public"])
                        elif unit["decision"].action == "blocked":
                            report.blocked += 1
                        elif unit["decision"].action == "wait":
                            report.waiting += 1
                        else:
                            report.skipped += 1
                        if (
                            unit["decision"].action == "run"
                            and may_dispatch
                            and not report.dispatched
                        ):
                            dispatched = await self._dispatch(session, unit)
                            if dispatched is not None:
                                report.dispatched.append(dispatched)
                            else:
                                report.blocked += 1
                                self._dispatch_cooldowns[
                                    (project_id, unit["chapter"]["identity"])
                                ] = time.monotonic() + self._cooldown
                        session.commit()
        except Exception as exc:
            report.errors.append(f"Maintenance pass failed: {exc}.")
        return self._finish(report, started)

    def _finish(self, report: MaintenanceReport, started: float) -> MaintenanceReport:
        report.elapsed_ms = int((time.perf_counter() - started) * 1000)
        self._last_report = report
        return report

    @staticmethod
    def _published_posts(blog_dir: Path) -> list[dict[str, Any]]:
        try:
            posts = _posts._live_posts(blog_dir)
        except Exception:
            return []
        return [p for p in posts if p.get("post_status") == "published"]

    def _decide_post(
        self,
        *,
        project_id: str,
        blog_dir: Path,
        post: dict[str, Any],
        enabled: bool,
        site_paused: bool,
        receipts: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        from mission_control.models import WebsitePostWriterObservation
        from sqlalchemy import desc, select

        identity = str(post.get("identity", ""))
        relpath = str(post.get("relpath", ""))
        with self._database.session() as session:
            try:
                rows = list(
                    session.scalars(
                        select(WebsitePostWriterObservation)
                        .where(
                            WebsitePostWriterObservation.website_id == project_id,
                            WebsitePostWriterObservation.article_identity == identity,
                        )
                        .order_by(desc(WebsitePostWriterObservation.created_at))
                        .limit(50)
                    ).all()
                )
            except Exception:
                rows = []
        body, live_digest, unreadable = _live_body_for_decision(blog_dir, relpath)
        if rows:
            latest = rows[0]
            if live_digest is None:
                state: dict[str, Any] = {
                    "has_evidence": True,
                    "freshness": "unknown",
                    "result": "unknown",
                }
            else:
                match = latest.body_sha256 == live_digest
                state = {
                    "has_evidence": True,
                    "freshness": "current" if match else "stale",
                    "result": "passed" if latest.status == "complete" else "pending",
                }
        else:
            state = {
                "has_evidence": False,
                "freshness": "missing" if live_digest is not None else "unknown",
                "result": "unknown",
            }
        entry = receipts.get((project_id, identity))
        last_receipt = entry["latest"] if entry else None
        active_id = entry["active_id"] if entry else None
        failures = entry["failures"] if entry else 0
        last_failure = entry["last_failure_at"] if entry else None
        live_content = None
        if live_digest is not None:
            try:
                candidate = blog_dir / Path(*Path(relpath).parts)
                live_content = hashlib.sha256(candidate.read_bytes()).hexdigest()
            except (OSError, ValueError):
                live_content = None
        decision = decide_post(
            enabled=enabled,
            site_paused=site_paused,
            state={**state, "applicable": True},
            live_source_digest=live_digest,
            live_metadata_digest=live_content,
            active_execution_id=active_id,
            last_receipt=last_receipt,
            consecutive_failures=failures,
            last_failure_at=last_failure,
            max_attempts=self._max_attempts,
            cooldown_seconds=self._cooldown,
        )
        if decision.action == "run" and live_digest is not None:
            key = (project_id, identity)
            if len(self._debounce) > 5000:
                self._debounce.pop(next(iter(self._debounce)))
            seen = self._debounce.get(key)
            if seen is None or seen[0] != live_digest:
                self._debounce[key] = (live_digest, 1)
                decision = MaintenanceDecision(
                    action="wait",
                    reason="Digest changed; waiting one pass to debounce mid-save edits.",
                    fingerprint=decision.fingerprint,
                )
            elif seen[1] < self._debounce_passes - 1:
                self._debounce[key] = (live_digest, seen[1] + 1)
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
        return {
            "decision": decision,
            "public": {
                "project_id": project_id,
                "chapter_id": identity,
                "stage_id": "writer_observation",
                "decision": decision.action,
                "reason": decision.reason,
                "fingerprint": decision.fingerprint,
                "has_evidence": state["has_evidence"],
                "freshness": state["freshness"],
                "result": state["result"],
            },
            "target": (project_id, identity),
            "chapter": {"identity": identity, "relpath": relpath},
            "definition": {"website_id": project_id, "blog_dir": str(blog_dir)},
            "metadata_digest": live_content,
        }

    async def _dispatch(self, session: Any, unit: dict[str, Any]) -> dict[str, Any] | None:
        from mission_control.integrations.service import IntegrationService

        target = unit["target"]
        chapter = unit["chapter"]
        definition = unit["definition"]
        try:
            assert isinstance(self._integrations, IntegrationService)
            execution = await self._integrations.start_action(
                "writer",
                BLOG_AUTO_ACTION_ID,
                {
                    "website_id": target[0],
                    "article_identity": chapter["identity"],
                    "blog_dir": definition["blog_dir"],
                    "policy_version": BLOG_AUTO_POLICY_VERSION,
                },
                confirm=True,
            )
        except Exception:
            logger.exception("Automatic blog dispatch failed for %s", target)
            return None
        return {
            "execution_id": execution.id,
            "project_id": target[0],
            "chapter_id": chapter["identity"],
            "stage_id": "writer_observation",
        }


def _live_body_for_decision(
    blog_dir: Path, relpath: str
) -> tuple[bytes | None, str | None, str | None]:
    body, digest, reason = _live_body(blog_dir, relpath)
    return body, digest, reason


def store_observation(
    session: Any,
    *,
    website_id: str,
    identity: str,
    envelope: dict[str, Any],
    execution_id: str | None,
    fingerprint_inputs: dict[str, Any],
) -> Any:
    """Persist one verified Writer observation (append-only, never overwrite).

    The envelope must already have passed the D2 ``validate_post_envelope``
    boundary (the adapter and the manual endpoint both enforce this before
    returning it). Each call inserts a new row with a unique id so reruns
    preserve history; idempotency across retries is keyed on ``execution_id``
    (see :func:`ingest_completed_execution`), never by overwriting.
    """
    from mission_control.models import WebsitePostWriterObservation
    from mission_control.persistence.db import now_iso

    if not isinstance(envelope, dict):
        raise ValueError("Envelope must be a mapping.")
    work = envelope.get("work_object", {})
    if not isinstance(work, dict):
        raise ValueError("Envelope work_object must be a mapping.")
    if not work.get("source_hash"):
        raise ValueError("Envelope is missing its evaluated-body binding (source_hash).")
    findings = envelope.get("findings")
    row = WebsitePostWriterObservation(
        id=f"wpo-{uuid.uuid4().hex[:16]}",
        website_id=website_id,
        article_identity=identity,
        relpath=str(work.get("relpath") or identity),
        content_sha256=str(work.get("content_sha256") or ""),
        body_sha256=str(work.get("source_hash") or ""),
        producer_runtime=str(
            (envelope.get("producer") or {}).get("runtime_name", "") or "artifact"
        ),
        method=str((envelope.get("producer") or {}).get("method", "") or "analyze_text"),
        method_version=str(
            (envelope.get("producer") or {}).get("method_version", "")
            or "writer-artifact-detection.v1"
        ),
        status=str(envelope.get("status", "complete")),
        evaluation_id=str(envelope.get("evaluation_id", "")),
        envelope=dict(envelope),
        finding_count=len(findings) if isinstance(findings, list) else 0,
        execution_id=execution_id,
        policy_version=str(fingerprint_inputs.get("policy_version", BLOG_AUTO_POLICY_VERSION)),
        flags_version=str(fingerprint_inputs.get("flags_version", BLOG_FLAGS_VERSION)),
        fingerprint=str(fingerprint_inputs.get("fingerprint", "")),
        observed_at=str(envelope.get("observed_at", "") or now_iso()),
        created_at=now_iso(),
    )
    session.add(row)
    session.flush()
    return row


def ingest_completed_execution(session: Any, *, execution: Any, blog_dir: Path) -> Any | None:
    """Persist the observation for one succeeded automatic execution, once.

    Idempotent: returns the existing row when ``execution.id`` was already
    ingested, ``None`` when the execution is not a succeeded automatic post
    observation. Re-validates the stored envelope binding before writing so
    a receipt alone can never fabricate evidence.
    """
    from mission_control.models import WebsitePostWriterObservation
    from mission_control.websites import post_artifact as _post_artifact
    from sqlalchemy import select

    if getattr(execution, "action_id", "") != BLOG_AUTO_ACTION_ID:
        return None
    if getattr(execution, "status", "") != "succeeded":
        return None
    parameters = getattr(execution, "parameters", None) or {}
    website_id = str(parameters.get("website_id") or "")
    identity = str(parameters.get("article_identity") or "")
    if not website_id or not identity:
        return None
    existing = session.scalars(
        select(WebsitePostWriterObservation).where(
            WebsitePostWriterObservation.execution_id == str(getattr(execution, "id", ""))
        )
    ).first()
    if existing is not None:
        return existing
    result = getattr(execution, "result", None) or {}
    auto_inputs = result.get("auto_inputs") if isinstance(result, dict) else None
    if not isinstance(auto_inputs, dict):
        return None
    try:
        envelope = _post_artifact.artifact_envelope_for_live_post(
            blog_dir, identity=identity, observed_at=str(result.get("observed_at") or "")
        )
    except Exception:
        return None
    if envelope is None:
        return None
    if str((envelope.get("work_object") or {}).get("source_hash") or "") != str(
        result.get("source_digest") or ""
    ):
        return None
    return store_observation(
        session,
        website_id=website_id,
        identity=identity,
        envelope=envelope,
        execution_id=str(getattr(execution, "id", "")),
        fingerprint_inputs=auto_inputs,
    )


# ---------------------------------------------------------------------------
# Read-only status for the UI (no dispatch here)


def maintenance_status(database: Any, settings: Any) -> dict[str, Any]:
    """Read-only automatic-maintenance state for blog posts."""
    started = time.perf_counter()
    with database.session() as session:
        enabled = is_auto_enabled(session)
        paused = paused_websites(session)
    books: list[dict[str, Any]] = []
    try:
        from mission_control.discovery.websites import detect_websites

        detected, _diagnostics = detect_websites([settings.websites_root])
        for site in detected:
            if getattr(site, "content_section", None):
                books.append({"project_id": str(site.id), "paused": str(site.id) in paused})
    except Exception as exc:
        books.append({"project_id": "", "paused": False, "diagnostics": str(exc)})
    active: list[dict[str, str]] = []
    recent_failures: list[dict[str, str]] = []
    try:
        with database.session() as session:
            executions = _recent_auto_executions(session)
        receipts = index_receipts_by_target(executions)
        for key, entry in receipts.items():
            if entry.get("active_id"):
                active.append({"execution_id": entry["active_id"], "chapter_file": key[1]})
        for execution in executions:
            if str(getattr(execution, "status", "")) != "failed":
                continue
            parameters = getattr(execution, "parameters", None) or {}
            recent_failures.append(
                {
                    "execution_id": str(getattr(execution, "id", "")),
                    "chapter_file": str(parameters.get("article_identity", "")),
                    "error": str(getattr(execution, "error", "") or "")[:500],
                    "ended_at": str(getattr(execution, "ended_at", "") or ""),
                }
            )
            if len(recent_failures) >= 20:
                break
    except Exception as exc:
        recent_failures.append({"error": f"Execution history is unavailable: {exc}."})
    return {
        "policy_version": BLOG_AUTO_POLICY_VERSION,
        "auto_stages": ["writer_observation"],
        "enabled": enabled,
        "paused_books": paused,
        "book_count": len([b for b in books if b.get("project_id")]),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "books": books,
        "queue_preview": [],
        "active": active,
        "recent_failures": recent_failures,
        "queue_note": "Queue preview is computed on demand by POST .../reconcile (dry run when disabled).",
        "refresh_note": "Read-only. Dispatch happens inside a reconcile pass when enabled.",
    }
