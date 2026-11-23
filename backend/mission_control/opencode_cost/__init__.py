"""Read-only OpenCode usage adapter (MC-COST-01).

Mission Control never writes to the OpenCode database. Every query opens
the file with ``mode=ro`` and closes it immediately. Missing, locked or
incompatible files are reported as explicit unavailable states, never as
silent zero usage.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DUBLIN_TZ = "Europe/Dublin"
_PRESET_CHOICES = {"today", "yesterday", "7d", "30d", "custom"}
_MAX_SCAN_MESSAGES = 100_000

# MC-COST-02 thresholds (deterministic, advisory only — never enforcement).
_HIGH_REQUESTS_MODEL = 50
_HIGH_CALL_SESSION = 100
_LARGE_SESSION_INPUT = 200_000


def throughput_of(entry: dict[str, Any]) -> int:
    """Provider-aligned token throughput.

    Follows provider accounting where ``output`` includes ``reasoning``:
    throughput = uncached input + output + cache reads + cache writes.
    ``reasoning`` is shown separately for diagnostics and is NOT added,
    to avoid double-counting. Local records carry output and reasoning as
    separate counters, so this is documented as an approximation.
    """
    def _num(value: Any) -> int:
        try:
            num = int(value or 0)
        except (TypeError, ValueError):
            return 0
        return num if num >= 0 else 0

    return (
        _num(entry.get("input"))
        + _num(entry.get("output"))
        + _num(entry.get("cache_read"))
        + _num(entry.get("cache_write"))
    )


def classify_billing(provider: str, model_id: str) -> dict[str, str]:
    """Heuristic billing route — never authoritative.

    The authoritative ``opencode.billing_source`` (free/balance/go/go-plus/byok)
    is a provider-response field and is NOT retained in the local database.
    This classification is inferred from provider/model identifiers only, and
    every consumer must surface the accompanying reason. Never infer billing
    from a zero-dollar cost alone.
    """
    raw_provider = (provider or "").strip()
    raw_model = (model_id or "").strip()
    lowered_model = raw_model.lower()
    if raw_model and raw_model != "unknown" and "free" in lowered_model:
        return {
            "category": "free-candidate",
            "reason": "model id suggests a free tier; authoritative billing_source is not retained locally",
        }
    if raw_provider == "opencode-go":
        return {
            "category": "go-candidate",
            "reason": "provider is opencode-go (Go allowance route); authoritative billing_source is not retained locally",
        }
    if not raw_provider or raw_provider == "unknown":
        return {
            "category": "unknown",
            "reason": "no provider recorded; billing route cannot be determined",
        }
    return {
        "category": "direct-candidate",
        "reason": f"provider '{raw_provider}' is not the Go route; likely separately billed or BYOK — verify against provider records",
    }


def _validate_timezone(tz_name: str | None) -> str:
    name = (tz_name or DUBLIN_TZ).strip() or DUBLIN_TZ
    if len(name) > 80:
        from mission_control.core.errors import ValidationProblem as _VP

        raise _VP("Unknown timezone")
    try:
        ZoneInfo(name)
    except Exception:
        from mission_control.core.errors import ValidationProblem as _VP

        raise _VP("Unknown timezone") from None
    return name


def _validate_day(day: str) -> str:
    from mission_control.core.errors import ValidationProblem as _VP

    text = (day or "").strip()
    import re

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        raise _VP("date must be ISO YYYY-MM-DD")
    try:
        datetime.fromisoformat(text)
    except ValueError:
        raise _VP("date must be ISO YYYY-MM-DD") from None
    return text


def _day_start_end_ms(day: str, tz_name: str) -> tuple[int, int]:
    """Start-inclusive / end-exclusive bounds for one calendar day in ms."""
    tz = ZoneInfo(tz_name)
    year, month, dom = (int(part) for part in day.split("-"))
    start_dt = datetime(year, month, dom, 0, 0, 0, tzinfo=tz)
    base = datetime(year, month, dom).date() + timedelta(days=1)
    end_dt = datetime(base.year, base.month, base.day, 0, 0, 0, tzinfo=tz)
    return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)


def resolve_bounds(
    *,
    preset: str,
    date: str | None,
    date_from: str | None,
    date_to: str | None,
    timezone: str | None,
    now: datetime | None = None,
) -> tuple[str, str, int, int]:
    """Compute UTC ms bounds from Dublin calendar days.

    Returns (validated_date_label, validated_tz, start_ms, end_ms).
    `date` selects a single day; otherwise preset/custom range applies.
    """
    from mission_control.core.errors import ValidationProblem as _VP

    normalized = (preset or "today").strip().lower()
    if normalized not in _PRESET_CHOICES:
        raise _VP("Unknown date preset")
    tz_name = _validate_timezone(timezone)
    tz = ZoneInfo(tz_name)
    current = now or datetime.now(tz)

    if date:
        day = _validate_day(date)
        start_ms, end_ms = _day_start_end_ms(day, tz_name)
        return day, tz_name, start_ms, end_ms

    if normalized == "today":
        day = current.date().isoformat()
        start_ms, end_ms = _day_start_end_ms(day, tz_name)
        return day, tz_name, start_ms, end_ms
    if normalized == "yesterday":
        day = (current.date() - timedelta(days=1)).isoformat()
        start_ms, end_ms = _day_start_end_ms(day, tz_name)
        return day, tz_name, start_ms, end_ms
    if normalized in {"7d", "30d"}:
        days = 7 if normalized == "7d" else 30
        end_dt = datetime(
            current.year, current.month, current.day, 0, 0, 0, tzinfo=tz
        ) + timedelta(days=1)
        start_dt = end_dt - timedelta(days=days)
        return (
            f"last-{days}d",
            tz_name,
            int(start_dt.timestamp() * 1000),
            int(end_dt.timestamp() * 1000),
        )
    # custom
    if not date_from and not date_to:
        raise _VP("Custom date range requires date_from or date_to")
    start_ms: int | None = None
    end_ms: int | None = None
    if date_from:
        day_from = _validate_day(date_from)
        start_ms, _ = _day_start_end_ms(day_from, tz_name)
    if date_to:
        day_to = _validate_day(date_to)
        _, end_ms = _day_start_end_ms(day_to, tz_name)
    if start_ms is None:
        start_ms = 0
    if end_ms is None:
        end_ms = int(current.timestamp() * 1000) + 1
    if start_ms >= end_ms:
        raise _VP("Custom date range is empty")
    label = f"{date_from or '...'}..{date_to or '...'}"
    return label, tz_name, start_ms, end_ms


@dataclass(slots=True)
class CostStatus:
    available: bool
    source_path: str
    reason: str
    error: str | None = None
    sessions: int = 0
    messages: int = 0


def _connect_ro(path: Path, timeout: float = 5.0) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def _is_locked_error(exc: Exception) -> bool:
    text = f"{exc.__class__.__name__}: {exc}".casefold()
    return "database is locked" in text or "database table is locked" in text


class OpencodeCostStore:
    """Narrow read-only reader over OpenCode's SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    @property
    def source_path(self) -> str:
        return self._db_path.as_posix()

    def status(self) -> CostStatus:
        path = self._db_path
        if not path.exists():
            return CostStatus(
                available=False,
                source_path=path.as_posix(),
                reason="OpenCode database file was not found at the configured path.",
                error="missing",
            )
        if not path.is_file():
            return CostStatus(
                available=False,
                source_path=path.as_posix(),
                reason="Configured OpenCode path is not a file.",
                error="not_a_file",
            )
        try:
            with _connect_ro(path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('session_v2','session_message','project')"
                )
                found = {row[0] for row in cur.fetchall()}
                missing = {"session_v2", "session_message", "project"} - found
                if missing:
                    return CostStatus(
                        available=False,
                        source_path=path.as_posix(),
                        reason=f"OpenCode database is missing expected tables: {', '.join(sorted(missing))}.",
                        error="incompatible_schema",
                    )
                sessions = cur.execute("SELECT COUNT(*) FROM session_v2").fetchone()[0]
                messages = cur.execute("SELECT COUNT(*) FROM session_message").fetchone()[0]
                return CostStatus(
                    available=True,
                    source_path=path.as_posix(),
                    reason="OpenCode database is readable.",
                    sessions=int(sessions or 0),
                    messages=int(messages or 0),
                )
        except sqlite3.OperationalError as exc:
            if _is_locked_error(exc):
                return CostStatus(
                    available=False,
                    source_path=path.as_posix(),
                    reason="OpenCode database is temporarily locked (live WAL writer). Retry shortly.",
                    error="locked",
                )
            return CostStatus(
                available=False,
                source_path=path.as_posix(),
                reason=f"OpenCode database could not be opened: {exc.__class__.__name__}.",
                error=str(exc)[:300],
            )
        except (sqlite3.DatabaseError, OSError) as exc:
            return CostStatus(
                available=False,
                source_path=path.as_posix(),
                reason="OpenCode database could not be read.",
                error=f"{exc.__class__.__name__}: {str(exc)[:300]}",
            )

    def _fetch_projects(self, conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        try:
            rows = conn.execute("SELECT id, worktree, name FROM project").fetchall()
        except sqlite3.DatabaseError:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            out[str(row["id"])] = {
                "id": str(row["id"]),
                "worktree": str(row["worktree"] or ""),
                "name": row["name"],
            }
        return out

    @staticmethod
    def _parse_assistant(data_text: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(data_text)
        except (ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
        tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
        cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
        try:
            cost = float(payload.get("cost") or 0)
        except (TypeError, ValueError):
            cost = 0.0
        def _num(value: Any) -> int:
            try:
                num = int(value or 0)
            except (TypeError, ValueError):
                return 0
            return num if num >= 0 else 0
        return {
            "model_id": str(model.get("id") or "unknown"),
            "provider": str(model.get("providerID") or model.get("provider") or "unknown"),
            "variant": str(model.get("variant") or ""),
            "cost": cost if cost == cost and cost >= 0 else 0.0,
            "input": _num(tokens.get("input")),
            "output": _num(tokens.get("output")),
            "reasoning": _num(tokens.get("reasoning")),
            "cache_read": _num(cache.get("read")),
            "cache_write": _num(cache.get("write")),
        }

    def scan_window(
        self, start_ms: int, end_ms: int
    ) -> dict[str, Any]:
        """Aggregate assistant messages whose time_created falls in window.

        Returns totals, per-minute buckets, per-model, per-session and errors.
        Never raises for missing/locked/incompatible sources: callers check
        status() first, but this also returns an explicit unavailable envelope.
        """
        state = self.status()
        if not state.available:
            return {
                "available": False,
                "reason": state.reason,
                "error": state.error,
                "source_path": state.source_path,
            }
        try:
            with _connect_ro(self._db_path) as conn:
                projects = self._fetch_projects(conn)
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT session_id, seq, time_created, data
                    FROM session_message
                    WHERE type='assistant' AND time_created >= ? AND time_created < ?
                    ORDER BY time_created ASC
                    """,
                    (int(start_ms), int(end_ms)),
                )
                totals = {
                    "requests": 0,
                    "recorded_cost": 0.0,
                    "input": 0,
                    "output": 0,
                    "reasoning": 0,
                    "cache_read": 0,
                    "cache_write": 0,
                    "throughput": 0,
                }
                per_minute: dict[str, dict[str, Any]] = {}
                per_model: dict[str, dict[str, Any]] = {}
                per_session: dict[str, dict[str, Any]] = {}
                scanned = 0
                truncated = False
                for row in cur:
                    scanned += 1
                    if scanned > _MAX_SCAN_MESSAGES:
                        truncated = True
                        break
                    parsed = self._parse_assistant(str(row["data"]))
                    if parsed is None:
                        continue
                    totals["requests"] += 1
                    totals["recorded_cost"] += parsed["cost"]
                    totals["input"] += parsed["input"]
                    totals["output"] += parsed["output"]
                    totals["reasoning"] += parsed["reasoning"]
                    totals["cache_read"] += parsed["cache_read"]
                    totals["cache_write"] += parsed["cache_write"]
                    totals["throughput"] += (
                        parsed["input"] + parsed["output"]
                        + parsed["cache_read"] + parsed["cache_write"]
                    )
                    # Use UTC minute label for stability; frontend formats Dublin separately.
                    utc_min = datetime.fromtimestamp(int(row["time_created"]) / 1000, tz=__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M")
                    bucket = per_minute.setdefault(
                        utc_min, {"minute": utc_min, "requests": 0, "recorded_cost": 0.0}
                    )
                    bucket["requests"] += 1
                    bucket["recorded_cost"] += parsed["cost"]
                    model_key = f"{parsed['provider']}/{parsed['model_id']}"
                    billing = classify_billing(parsed["provider"], parsed["model_id"])
                    entry = per_model.setdefault(
                        model_key,
                        {
                            "model": parsed["model_id"],
                            "provider": parsed["provider"],
                            "variant": parsed["variant"],
                            "billing_category": billing["category"],
                            "billing_reason": billing["reason"],
                            "requests": 0,
                            "recorded_cost": 0.0,
                            "input": 0,
                            "output": 0,
                            "reasoning": 0,
                            "cache_read": 0,
                            "cache_write": 0,
                            "throughput": 0,
                        },
                    )
                    entry["requests"] += 1
                    entry["recorded_cost"] += parsed["cost"]
                    entry["input"] += parsed["input"]
                    entry["output"] += parsed["output"]
                    entry["reasoning"] += parsed["reasoning"]
                    entry["cache_read"] += parsed["cache_read"]
                    entry["cache_write"] += parsed["cache_write"]
                    entry["throughput"] += (
                        parsed["input"] + parsed["output"]
                        + parsed["cache_read"] + parsed["cache_write"]
                    )
                    if parsed["variant"] and not entry["variant"]:
                        entry["variant"] = parsed["variant"]
                    sid = str(row["session_id"])
                    sentry = per_session.setdefault(
                        sid,
                        {
                            "session_id": sid,
                            "requests": 0,
                            "recorded_cost": 0.0,
                            "input": 0,
                            "output": 0,
                            "reasoning": 0,
                            "cache_read": 0,
                            "cache_write": 0,
                            "throughput": 0,
                            "max_input": 0,
                            "models": {},
                        },
                    )
                    sentry["requests"] += 1
                    sentry["recorded_cost"] += parsed["cost"]
                    sentry["input"] += parsed["input"]
                    sentry["output"] += parsed["output"]
                    sentry["reasoning"] += parsed["reasoning"]
                    sentry["cache_read"] += parsed["cache_read"]
                    sentry["cache_write"] += parsed["cache_write"]
                    sentry["throughput"] += (
                        parsed["input"] + parsed["output"]
                        + parsed["cache_read"] + parsed["cache_write"]
                    )
                    if parsed["input"] > int(sentry["max_input"] or 0):
                        sentry["max_input"] = parsed["input"]
                    sentry["models"][model_key] = int(sentry["models"].get(model_key, 0)) + 1

                # Dominant billing route per session (heuristic, never authoritative)
                # plus a plain model list for drill-down. Children are separate
                # sessions, so parent totals never include child messages.
                for sentry in per_session.values():
                    model_counts: dict[str, int] = dict(sentry.get("models") or {})
                    model_keys = sorted(model_counts.keys())
                    sentry["models"] = model_keys
                    if len(model_keys) == 1:
                        dominant = model_keys[0]
                        provider, _, model_id = dominant.partition("/")
                        billing = classify_billing(provider, model_id)
                        sentry["billing_category"] = billing["category"]
                        sentry["billing_reason"] = billing["reason"]
                        sentry["billing_mixed"] = False
                    elif model_keys:
                        dominant = max(model_keys, key=lambda k: (model_counts.get(k, 0), k))
                        provider, _, model_id = dominant.partition("/")
                        billing = classify_billing(provider, model_id)
                        sentry["billing_category"] = billing["category"]
                        sentry["billing_reason"] = (
                            "dominant of "
                            + str(len(model_keys))
                            + " routes in session; "
                            + billing["reason"]
                        )
                        sentry["billing_mixed"] = True
                    else:
                        sentry["billing_category"] = "unknown"
                        sentry["billing_reason"] = "no model recorded for this session"
                        sentry["billing_mixed"] = False

                # Session metadata for sessions seen in window (bounded).
                session_meta: dict[str, dict[str, Any]] = {}
                if per_session:
                    ids = list(per_session.keys())[:5000]
                    placeholders = ",".join(["?"] * len(ids))
                    try:
                        for srow in conn.execute(
                            f"SELECT id, project_id, parent_id, title, directory, model, agent, cost, time_created, time_updated FROM session_v2 WHERE id IN ({placeholders})",
                            ids,
                        ).fetchall():
                            session_meta[str(srow["id"])] = {
                                "session_id": str(srow["id"]),
                                "project_id": str(srow["project_id"] or ""),
                                "parent_id": srow["parent_id"],
                                "title": srow["title"],
                                "directory": str(srow["directory"] or ""),
                                "model": str(srow["model"] or ""),
                                "agent": srow["agent"],
                                "rollup_cost": float(srow["cost"] or 0),
                                "time_created": int(srow["time_created"] or 0),
                                "time_updated": int(srow["time_updated"] or 0),
                            }
                    except sqlite3.DatabaseError:
                        session_meta = {}

                # Failure signals in window (bounded, no bodies).
                failures = {"go_limit": 0, "no_route": 0, "failed_idle": 0, "subagent_errors": 0}
                try:
                    failures["go_limit"] = conn.execute(
                        "SELECT COUNT(*) FROM session_message WHERE type='idle' AND time_created >= ? AND time_created < ? AND data LIKE '%provider.go-limit%'",
                        (int(start_ms), int(end_ms)),
                    ).fetchone()[0]
                    failures["no_route"] = conn.execute(
                        "SELECT COUNT(*) FROM session_message WHERE type='idle' AND time_created >= ? AND time_created < ? AND data LIKE '%provider.no-route%'",
                        (int(start_ms), int(end_ms)),
                    ).fetchone()[0]
                    failures["failed_idle"] = conn.execute(
                        "SELECT COUNT(*) FROM session_message WHERE type='idle' AND time_created >= ? AND time_created < ? AND data LIKE '%outcome%failed%'",
                        (int(start_ms), int(end_ms)),
                    ).fetchone()[0]
                    failures["subagent_errors"] = conn.execute(
                        "SELECT COUNT(*) FROM session_message WHERE type='synthetic' AND time_created >= ? AND time_created < ? AND (data LIKE '%GoUsageLimit%' OR data LIKE '%monthly usage limit%')",
                        (int(start_ms), int(end_ms)),
                    ).fetchone()[0]
                except sqlite3.DatabaseError:
                    pass

                return {
                    "available": True,
                    "source_path": self._db_path.as_posix(),
                    "reason": "ok",
                    "totals": totals,
                    "per_minute": sorted(per_minute.values(), key=lambda item: item["minute"]),
                    "per_model": sorted(
                        per_model.values(), key=lambda item: (-item["requests"], item["provider"])
                    ),
                    "per_session": per_session,
                    "session_meta": session_meta,
                    "projects": projects,
                    "failures": failures,
                    "scanned": scanned,
                    "truncated": truncated,
                }
        except sqlite3.OperationalError as exc:
            if _is_locked_error(exc):
                return {
                    "available": False,
                    "reason": "OpenCode database is temporarily locked (live WAL writer). Retry shortly.",
                    "error": "locked",
                    "source_path": self._db_path.as_posix(),
                }
            return {
                "available": False,
                "reason": f"OpenCode database could not be opened: {exc.__class__.__name__}.",
                "error": str(exc)[:300],
                "source_path": self._db_path.as_posix(),
            }
        except (sqlite3.DatabaseError, OSError) as exc:
            return {
                "available": False,
                "reason": "OpenCode database could not be read.",
                "error": f"{exc.__class__.__name__}: {str(exc)[:300]}",
                "source_path": self._db_path.as_posix(),
            }

    def build_efficiency(self, scan: dict[str, Any]) -> list[dict[str, Any]]:
        """Deterministic, advisory-only efficiency recommendations.

        Every recommendation links to recorded session IDs, states the
        evidence, and requires human verification of quality/latency before
        any model change. The action is always informational: Mission Control
        observes here; Worker would decide elsewhere. No model is ever
        switched, no paid call is ever made.
        """
        if not scan.get("available"):
            return []
        recs: list[dict[str, Any]] = []
        per_model: list[dict[str, Any]] = list(scan.get("per_model") or [])
        per_session: dict[str, dict[str, Any]] = dict(scan.get("per_session") or {})
        meta: dict[str, dict[str, Any]] = dict(scan.get("session_meta", {}) or {})

        def _sessions_for_model(model_key: str, limit: int = 5) -> list[str]:
            matched = [
                sid for sid, entry in per_session.items()
                if model_key in (entry.get("models") or [])
            ]
            matched.sort(key=lambda sid: -int(per_session[sid].get("requests", 0)))
            return matched[:limit]

        for item in sorted(per_model, key=lambda m: -int(m.get("requests") or 0)):
            requests = int(item.get("requests") or 0)
            if requests < _HIGH_REQUESTS_MODEL:
                continue
            model_key = f"{item.get('provider')}/{item.get('model')}"
            category = str(item.get("billing_category") or "unknown")
            evidence = _sessions_for_model(model_key)
            if category == "go-candidate":
                recs.append({
                    "id": f"verify-free-{model_key}".replace("/", "-").replace(" ", "_"),
                    "title": f"High Go-route usage: {model_key} ({requests} calls)",
                    "detail": (
                        f"{requests} calls consumed uncached input {int(item.get('input') or 0):,} "
                        f"plus {int(item.get('cache_read') or 0):,} cached reads. "
                        "A free-candidate model may cover routine calls in these sessions. "
                        "Verify quality and latency on a sample before moving anything; "
                        "do not switch models automatically."
                    ),
                    "severity": "info",
                    "model": model_key,
                    "billing_category": category,
                    "session_ids": evidence,
                    "action": "none (advisory only)",
                })
            elif category == "direct-candidate":
                recs.append({
                    "id": f"verify-route-{model_key}".replace("/", "-").replace(" ", "_"),
                    "title": f"Separately-billed route in use: {model_key} ({requests} calls)",
                    "detail": (
                        f"{requests} calls recorded {float(item.get('recorded_cost') or 0):.4f} "
                        "in balance charges. Verify whether a Go or free route meets "
                        "this workload's quality and latency bar before changing anything."
                    ),
                    "severity": "info",
                    "model": model_key,
                    "billing_category": category,
                    "session_ids": evidence,
                    "action": "none (advisory only)",
                })
            elif category == "free-candidate":
                recs.append({
                    "id": f"confirm-free-{model_key}".replace("/", "-").replace(" ", "_"),
                    "title": f"Volume already on free-candidate route: {model_key} ({requests} calls)",
                    "detail": (
                        "No switch is suggested. Confirm output quality is acceptable; "
                        "route classification is heuristic and billing_source is not retained locally."
                    ),
                    "severity": "info",
                    "model": model_key,
                    "billing_category": category,
                    "session_ids": evidence,
                    "action": "none (advisory only)",
                })

        for sid, entry in sorted(per_session.items(), key=lambda kv: -int(kv[1].get("input", 0))):
            if int(entry.get("input") or 0) < _LARGE_SESSION_INPUT:
                break
            if int(entry.get("cache_read") or 0) >= int(entry.get("input") or 0) // 2:
                continue
            title = (meta.get(sid, {}).get("title") or sid[:12])
            recs.append({
                "id": f"cache-reuse-{sid[:12]}",
                "title": f"Low cache reuse in session '{title}'",
                "detail": (
                    f"Uncached input {int(entry.get('input') or 0):,} with cache reads "
                    f"{int(entry.get('cache_read') or 0):,}. Prefer a stable session identity, "
                    "smaller serialized context, and bounded parallelism; re-measure before and after."
                ),
                "severity": "info",
                "model": "",
                "billing_category": str(entry.get("billing_category") or "unknown"),
                "session_ids": [sid],
                "action": "none (advisory only)",
            })
            if len([r for r in recs if r["id"].startswith("cache-reuse-")]) >= 5:
                break

        for sid, entry in sorted(per_session.items(), key=lambda kv: -int(kv[1].get("requests", 0))):
            if int(entry.get("requests") or 0) < _HIGH_CALL_SESSION:
                break
            title = (meta.get(sid, {}).get("title") or sid[:12])
            recs.append({
                "id": f"call-volume-{sid[:12]}",
                "title": f"High call volume in session '{title}' ({int(entry.get('requests') or 0)} calls)",
                "detail": (
                    "Possible repeated operations or agent fan-out. Inspect the session's "
                    "call timeline and child agents for loops or duplicated prompts before deciding."
                ),
                "severity": "info",
                "model": "",
                "billing_category": str(entry.get("billing_category") or "unknown"),
                "session_ids": [sid],
                "action": "none (advisory only)",
            })
            if len([r for r in recs if r["id"].startswith("call-volume-")]) >= 5:
                break

        return recs[:20]

    def caller_identity_audit(self) -> dict[str, Any]:
        """Which caller-identity fields exist locally, and what is missing.

        Read-only: inspects the live schema shape plus one bounded probe.
        """
        retained = [
            "session_v2.id — stable OpenCode session identity",
            "session_v2.project_id → project.worktree — owning checkout",
            "session_v2.parent_id — parent/child agent tree",
            "session_v2.directory — working directory the session ran in",
            "session_v2.agent — agent name recorded per session",
            "session_message.model — actual provider/model/variant per request",
        ]
        missing = [
            "OS process id / command line that launched the call",
            "application name (Mission Control, Worker, Pi, ALIVE, Translator)",
            "x-opencode-session header value sent to the provider",
            "provider billing_source / allowance / list_cost per request",
        ]
        instrumentation = [
            "Mission Control: tag Pi invocations with a stable per-task session id instead of --no-session where continuity is intended",
            "Worker: propagate parent workflow/run ids into the session title or metadata it controls",
            "Pi: forward x-opencode-session on every adapter so Go can route and cache",
            "ALIVE/Translator: include an application caller header on direct inference calls, or route them through a tagged session",
        ]
        return {
            "retained": retained,
            "missing": missing,
            "instrumentation": instrumentation,
        }

    def session_detail(self, session_id: str) -> dict[str, Any]:
        """Full verifiable detail for one session (message-level, no bodies)."""
        state = self.status()
        if not state.available:
            return {
                "available": False,
                "reason": state.reason,
                "error": state.error,
                "source_path": state.source_path,
            }
        cleaned = (session_id or "").strip()
        if not cleaned or len(cleaned) > 120:
            from mission_control.core.errors import ValidationProblem as _VP

            raise _VP("Unknown session")
        try:
            with _connect_ro(self._db_path) as conn:
                srow = conn.execute(
                    "SELECT id, project_id, parent_id, title, directory, model, agent, cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, tokens_cache_write, time_created, time_updated FROM session_v2 WHERE id=?",
                    (cleaned,),
                ).fetchone()
                if srow is None:
                    from mission_control.core.errors import NotFound as _NF

                    raise _NF("Session not found")
                projects = self._fetch_projects(conn)
                project = projects.get(str(srow["project_id"] or ""), None)
                children = [
                    str(r["id"])
                    for r in conn.execute(
                        "SELECT id FROM session_v2 WHERE parent_id=? ORDER BY time_created ASC LIMIT 100",
                        (cleaned,),
                    ).fetchall()
                ]
                messages = conn.execute(
                    "SELECT seq, type, time_created, data FROM session_message WHERE session_id=? ORDER BY seq ASC LIMIT 5000",
                    (cleaned,),
                ).fetchall()
                calls: list[dict[str, Any]] = []
                by_model: dict[str, dict[str, Any]] = {}
                failures: list[dict[str, Any]] = []
                for mrow in messages:
                    mtype = str(mrow["type"])
                    if mtype == "assistant":
                        parsed = self._parse_assistant(str(mrow["data"]))
                        if parsed is None:
                            continue
                        calls.append(
                            {
                                "seq": int(mrow["seq"]),
                                "time_created": int(mrow["time_created"]),
                                "model": parsed["model_id"],
                                "provider": parsed["provider"],
                                "variant": parsed["variant"],
                                "cost": parsed["cost"],
                                "input": parsed["input"],
                                "output": parsed["output"],
                                "reasoning": parsed["reasoning"],
                                "cache_read": parsed["cache_read"],
                                "cache_write": parsed["cache_write"],
                                "throughput": (
                                    parsed["input"] + parsed["output"]
                                    + parsed["cache_read"] + parsed["cache_write"]
                                ),
                            }
                        )
                        key = f"{parsed['provider']}/{parsed['model_id']}"
                        billing = classify_billing(parsed["provider"], parsed["model_id"])
                        entry = by_model.setdefault(
                            key,
                            {
                                "model": parsed["model_id"],
                                "provider": parsed["provider"],
                                "variant": parsed["variant"],
                                "billing_category": billing["category"],
                                "billing_reason": billing["reason"],
                                "requests": 0,
                                "recorded_cost": 0.0,
                                "input": 0,
                                "output": 0,
                                "reasoning": 0,
                                "cache_read": 0,
                                "cache_write": 0,
                                "throughput": 0,
                            },
                        )
                        entry["requests"] += 1
                        entry["recorded_cost"] += parsed["cost"]
                        entry["input"] += parsed["input"]
                        entry["output"] += parsed["output"]
                        entry["reasoning"] += parsed["reasoning"]
                        entry["cache_read"] += parsed["cache_read"]
                        entry["cache_write"] += parsed["cache_write"]
                        entry["throughput"] += (
                            parsed["input"] + parsed["output"]
                            + parsed["cache_read"] + parsed["cache_write"]
                        )
                    elif mtype == "idle":
                        text = str(mrow["data"])
                        failed = '"outcome"' in text and '"failed"' in text
                        if not failed:
                            try:
                                parsed_idle = json.loads(text)
                                failed = isinstance(parsed_idle, dict) and parsed_idle.get("outcome") == "failed"
                            except (ValueError, TypeError):
                                failed = False
                        if failed:
                            failures.append(
                                {
                                    "seq": int(mrow["seq"]),
                                    "time_created": int(mrow["time_created"]),
                                    "kind": "go-limit"
                                    if "provider.go-limit" in text
                                    else ("no-route" if "provider.no-route" in text else "failed"),
                                    "excerpt": text[:400],
                                }
                            )
                    elif mtype == "synthetic":
                        text = str(mrow["data"])
                        if "GoUsageLimit" in text or "monthly usage limit" in text:
                            failures.append(
                                {
                                    "seq": int(mrow["seq"]),
                                    "time_created": int(mrow["time_created"]),
                                    "kind": "subagent-go-limit",
                                    "excerpt": text[:400],
                                }
                            )
                return {
                    "available": True,
                    "source_path": self._db_path.as_posix(),
                    "session": {
                        "session_id": str(srow["id"]),
                        "project_id": str(srow["project_id"] or ""),
                        "project_worktree": (project or {}).get("worktree", ""),
                        "project_name": (project or {}).get("name"),
                        "parent_id": srow["parent_id"],
                        "children": children,
                        "title": srow["title"],
                        "directory": str(srow["directory"] or ""),
                        "model": str(srow["model"] or ""),
                        "agent": srow["agent"],
                        "rollup_cost": float(srow["cost"] or 0),
                        "rollup": {
                            "input": int(srow["tokens_input"] or 0),
                            "output": int(srow["tokens_output"] or 0),
                            "reasoning": int(srow["tokens_reasoning"] or 0),
                            "cache_read": int(srow["tokens_cache_read"] or 0),
                            "cache_write": int(srow["tokens_cache_write"] or 0),
                        },
                        "time_created": int(srow["time_created"] or 0),
                        "time_updated": int(srow["time_updated"] or 0),
                    },
                    "calls": calls,
                    "by_model": sorted(by_model.values(), key=lambda item: -item["requests"]),
                    "failures": failures[:50],
                    "message_counts": {
                        row_type: count
                        for row_type, count in (
                            conn.execute(
                                "SELECT type, COUNT(*) AS c FROM session_message WHERE session_id=? GROUP BY type",
                                (cleaned,),
                            ).fetchall()
                        )
                    },
                }
        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
            if isinstance(exc, sqlite3.OperationalError) and _is_locked_error(exc):
                return {
                    "available": False,
                    "reason": "OpenCode database is temporarily locked (live WAL writer). Retry shortly.",
                    "error": "locked",
                    "source_path": self._db_path.as_posix(),
                }
            return {
                "available": False,
                "reason": "OpenCode database could not be read.",
                "error": f"{exc.__class__.__name__}: {str(exc)[:300]}",
                "source_path": self._db_path.as_posix(),
            }
