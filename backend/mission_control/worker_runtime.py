"""MC-INSPECT-04 A: read-only Worker model readiness + usage.

Only GET endpoints are ever called:
- GET /health
- GET /v1/models/availability (cached, never triggers a probe)
- GET /v1/models/usage (worker.model-usage.v1)
- GET /v1/models/preflight (optional model query, passive)

Never calls POST /v1/models/probe. Cached availability is explicitly
labelled as cached and never implies a future inference will succeed.
Unknown billed costs stay None (unknown), never collapsed to zero.
Worker outages return honest unavailable states, never 500, and never
affect Projects/Inspect availability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:7317"
TIMEOUT_SECONDS = 3.0

CACHED_NOTE = (
    "Cached availability does not guarantee a future inference call will succeed. "
    "Observations expire after ~5 minutes and are per Worker process."
)
UNKNOWN_COST_NOTE = "Unknown billed cost remains unknown; it is never treated as zero."
NO_PROBE_NOTE = "Passive dashboard never invokes POST /v1/models/probe."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get(base_url: str, path: str) -> tuple[Any | None, str | None]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, trust_env=False) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        try:
            return resp.json(), None
        except ValueError:
            return None, "Invalid JSON payload"
    except httpx.TimeoutException:
        return None, "Timed out; Worker may not be running"
    except httpx.HTTPError as exc:
        return None, f"Not reachable ({exc.__class__.__name__})"


def _age_seconds(iso: str | None) -> float | None:
    if not iso or not isinstance(iso, str):
        return None
    try:
        parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed).total_seconds()
    except ValueError:
        return None


def read_worker_runtime(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    checked_at = _now_iso()

    health, health_error = _get(base, "/health")
    reachable = health is not None and isinstance(health, dict)
    connection = {
        "reachable": reachable,
        "status": str(health.get("status")) if reachable else "unknown",
        "version": str(health.get("version")) if reachable else "unknown",
        "listener": str(health.get("listen") or health.get("address") or "not stated") if reachable else "not stated",
        "error": health_error,
    }

    avail_doc, avail_error = _get(base, "/v1/models/availability")
    availability: dict[str, Any] = {
        "available": False,
        "error": avail_error,
        "freshness_note": CACHED_NOTE,
        "models": [],
        "warnings": [],
    }
    if isinstance(avail_doc, dict):
        models = avail_doc.get("models") if isinstance(avail_doc.get("models"), list) else []
        trimmed: list[dict[str, Any]] = []
        for row in models[:200]:
            if not isinstance(row, dict):
                continue
            obs = row.get("observation") if isinstance(row.get("observation"), dict) else None
            tested_at = obs.get("tested_at") if obs else None
            trimmed.append(
                {
                    "id": str(row.get("id") or ""),
                    "provider": str(row.get("provider") or ""),
                    "status": str(row.get("status") or "unknown"),
                    "free": row.get("free"),
                    "tested_at": tested_at,
                    "age_seconds": _age_seconds(tested_at) if tested_at else None,
                    "failure_type": str((obs.get("failure") or {}).get("type")) if obs and isinstance(obs.get("failure"), dict) else None,
                    "blocked": bool((row.get("provider_state") or {}).get("request_admissible") == "BLOCKED") if isinstance(row.get("provider_state"), dict) else None,
                }
            )
        availability = {
            "available": True,
            "error": None,
            "schema_version": str(avail_doc.get("schema_version") or "unknown"),
            "discovered_at": avail_doc.get("discovered_at"),
            "probing": bool(avail_doc.get("probing")),
            "models": trimmed,
            "warnings": list(avail_doc.get("warnings") or []),
            "freshness_note": CACHED_NOTE,
        }

    usage_doc, usage_error = _get(base, "/v1/models/usage")
    usage: dict[str, Any] = {
        "available": False,
        "error": usage_error,
        "unknown_note": UNKNOWN_COST_NOTE,
    }
    if isinstance(usage_doc, dict):
        billed = usage_doc.get("billed") if isinstance(usage_doc.get("billed"), dict) else {}
        estimated = usage_doc.get("estimated") if isinstance(usage_doc.get("estimated"), dict) else {}
        usage = {
            "available": True,
            "error": None,
            "schema_version": str(usage_doc.get("schema_version") or "unknown"),
            "scope": usage_doc.get("scope"),
            "outcomes": usage_doc.get("outcomes") or {},
            "failure_causes": usage_doc.get("failure_causes") or {},
            "usage_counts": usage_doc.get("usage") or {},
            "billed": billed,
            "estimated": estimated,
            "unknown_note": UNKNOWN_COST_NOTE,
            # Explicit unknown coverage: never collapse to zero.
            "billed_unknown_calls": billed.get("unknown_calls") if isinstance(billed, dict) else None,
            "models_count": len(usage_doc.get("models") or []) if isinstance(usage_doc.get("models"), list) else 0,
            "models": [
                {
                    "model": str(m.get("model") or m.get("id") or ""),
                    "calls": m.get("calls"),
                    "billed_usd": m.get("billed_usd"),
                    "estimated_usd": m.get("estimated_usd"),
                    "unknown_calls": m.get("unknown_calls"),
                }
                for m in (usage_doc.get("models") or [])[:100]
                if isinstance(m, dict)
            ],
            "warnings": list(usage_doc.get("warnings") or []),
        }

    preflight_doc, preflight_error = _get(base, "/v1/models/preflight")
    preflight: dict[str, Any] = {
        "available": False,
        "error": preflight_error,
    }
    if isinstance(preflight_doc, dict):
        preflight = {
            "available": True,
            "error": None,
            "document": preflight_doc,
        }

    available = reachable
    return {
        "available": available,
        "base_url": base,
        "checked_at": checked_at,
        "connection": connection,
        "availability": availability,
        "usage": usage,
        "preflight": preflight,
        "notes": [CACHED_NOTE, UNKNOWN_COST_NOTE, NO_PROBE_NOTE],
    }
