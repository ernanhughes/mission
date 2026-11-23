"""Read-only OpenCode cost API (MC-COST-01).

All endpoints are GET-only and never invoke a model. Missing, locked or
incompatible sources return explicit unavailable envelopes, never silent
zeros.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from mission_control.core.errors import NotFound
from mission_control.opencode_cost import OpencodeCostStore, resolve_bounds
from mission_control.schemas import (
    CostAttributionRead,
    CostCatalogueRead,
    CostEfficiencyRead,
    CostMinuteRead,
    CostModelRead,
    CostProjectRead,
    CostSessionDetailRead,
    CostSessionListRead,
    CostSessionRead,
    CostSpikesRead,
    CostStatusRead,
    CostSummaryRead,
)

router = APIRouter(prefix="/api/cost", tags=["cost"])


def _store(request: Request) -> OpencodeCostStore:
    store = getattr(request.app.state, "opencode_cost", None)
    if store is None:
        raise NotFound("Cost adapter is not available")
    return store


def _build_project_rows(scan: dict) -> list[dict]:
    projects_meta: dict = scan.get("session_meta", {})
    projects_table: dict = scan.get("projects", {})
    per_session: dict = scan.get("per_session", {})
    agg: dict[str, dict] = {}
    for sid, entry in per_session.items():
        meta = projects_meta.get(sid, {})
        pid = str(meta.get("project_id") or "")
        table = projects_table.get(pid, {}) if pid else {}
        worktree = str(table.get("worktree") or meta.get("directory") or "")
        key = pid or f"unknown:{worktree or sid}"
        bucket = agg.setdefault(
            key,
            {
                "project_id": pid,
                "worktree": worktree,
                "name": table.get("name"),
                "sessions": 0,
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
        bucket["sessions"] += 1
        bucket["requests"] += int(entry.get("requests") or 0)
        bucket["recorded_cost"] += float(entry.get("recorded_cost") or 0)
        bucket["input"] += int(entry.get("input") or 0)
        bucket["output"] += int(entry.get("output") or 0)
        bucket["reasoning"] += int(entry.get("reasoning") or 0)
        bucket["cache_read"] += int(entry.get("cache_read") or 0)
        bucket["cache_write"] += int(entry.get("cache_write") or 0)
        bucket["throughput"] += int(entry.get("throughput") or 0)
        if not bucket["worktree"] and meta.get("directory"):
            bucket["worktree"] = str(meta.get("directory"))
        if bucket["name"] is None and table.get("name") is not None:
            bucket["name"] = table.get("name")
    # Explicit Unknown bucket when nothing attributable
    rows = sorted(agg.values(), key=lambda item: (-item["recorded_cost"], -item["requests"]))
    return rows


@router.get("/status", response_model=CostStatusRead)
def cost_status(request: Request) -> CostStatusRead:
    state = _store(request).status()
    return CostStatusRead(
        available=state.available,
        source_path=state.source_path,
        reason=state.reason,
        error=state.error,
        sessions=state.sessions,
        messages=state.messages,
    )


@router.get("/summary", response_model=CostSummaryRead)
def cost_summary(
    request: Request,
    preset: str = Query(default="today"),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    timezone: str = Query(default="Europe/Dublin"),
) -> CostSummaryRead:
    label, tz_name, start_ms, end_ms = resolve_bounds(
        preset=preset, date=date, date_from=date_from, date_to=date_to, timezone=timezone
    )
    scan = _store(request).scan_window(start_ms, end_ms)
    if not scan.get("available"):
        return CostSummaryRead(
            available=False,
            source_path=str(scan.get("source_path") or ""),
            reason=str(scan.get("reason") or "unavailable"),
            error=scan.get("error"),
            date_label=label,
            timezone=tz_name,
            start_ms=start_ms,
            end_ms=end_ms,
        )
    totals = scan.get("totals", {})
    rows = _build_project_rows(scan)
    return CostSummaryRead(
        available=True,
        source_path=str(scan.get("source_path") or ""),
        reason="ok",
        date_label=label,
        timezone=tz_name,
        start_ms=start_ms,
        end_ms=end_ms,
        totals={
            "requests": int(totals.get("requests") or 0),
            "recorded_cost": float(totals.get("recorded_cost") or 0),
            "input": int(totals.get("input") or 0),
            "output": int(totals.get("output") or 0),
            "reasoning": int(totals.get("reasoning") or 0),
            "cache_read": int(totals.get("cache_read") or 0),
            "cache_write": int(totals.get("cache_write") or 0),
            "throughput": int(totals.get("throughput") or 0),
        },
        by_model=[
            CostModelRead(
                model=str(item.get("model") or ""),
                provider=str(item.get("provider") or ""),
                variant=str(item.get("variant") or ""),
                billing_category=str(item.get("billing_category") or "unknown"),
                billing_reason=str(item.get("billing_reason") or ""),
                requests=int(item.get("requests") or 0),
                recorded_cost=float(item.get("recorded_cost") or 0),
                input=int(item.get("input") or 0),
                output=int(item.get("output") or 0),
                reasoning=int(item.get("reasoning") or 0),
                cache_read=int(item.get("cache_read") or 0),
                cache_write=int(item.get("cache_write") or 0),
                throughput=int(item.get("throughput") or 0),
            )
            for item in (scan.get("per_model") or [])
        ],
        by_project=[
            CostProjectRead(
                project_id=str(item.get("project_id") or ""),
                worktree=str(item.get("worktree") or ""),
                name=item.get("name"),
                sessions=int(item.get("sessions") or 0),
                requests=int(item.get("requests") or 0),
                recorded_cost=float(item.get("recorded_cost") or 0),
                input=int(item.get("input") or 0),
                output=int(item.get("output") or 0),
                reasoning=int(item.get("reasoning") or 0),
                cache_read=int(item.get("cache_read") or 0),
                cache_write=int(item.get("cache_write") or 0),
                throughput=int(item.get("throughput") or 0),
            )
            for item in rows[:50]
        ],
        timeline=[
            CostMinuteRead(
                minute=str(item.get("minute") or ""),
                requests=int(item.get("requests") or 0),
                recorded_cost=float(item.get("recorded_cost") or 0),
            )
            for item in (scan.get("per_minute") or [])
        ],
        failures={k: int(v or 0) for k, v in (scan.get("failures") or {}).items()},
        scanned=int(scan.get("scanned") or 0),
        truncated=bool(scan.get("truncated")),
    )


@router.get("/sessions", response_model=CostSessionListRead)
def cost_sessions(
    request: Request,
    preset: str = Query(default="today"),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    timezone: str = Query(default="Europe/Dublin"),
    project_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="cost"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CostSessionListRead:
    label, tz_name, start_ms, end_ms = resolve_bounds(
        preset=preset, date=date, date_from=date_from, date_to=date_to, timezone=timezone
    )
    void = (label, tz_name)
    _ = void
    normalized_sort = (sort or "cost").strip().lower()
    if normalized_sort not in {"cost", "requests", "throughput", "input", "cache_read", "output", "updated"}:
        from mission_control.core.errors import ValidationProblem as _VP

        raise _VP("Unknown sort key")
    scan = _store(request).scan_window(start_ms, end_ms)
    if not scan.get("available"):
        return CostSessionListRead(
            available=False,
            source_path=str(scan.get("source_path") or ""),
            reason=str(scan.get("reason") or "unavailable"),
            error=scan.get("error"),
            total=0,
            limit=limit,
            offset=offset,
            items=[],
        )
    per_session: dict = scan.get("per_session", {})
    meta: dict = scan.get("session_meta", {})
    projects_table: dict = scan.get("projects", {})
    items: list[CostSessionRead] = []
    needle = (search or "").strip().casefold()
    for sid, entry in per_session.items():
        m = meta.get(sid, {})
        pid = str(m.get("project_id") or "")
        if project_id and pid != project_id and sid != project_id:
            # Allow filtering by worktree as well as project id.
            table = projects_table.get(pid, {})
            if str(table.get("worktree") or "") != project_id:
                continue
        title = str(m.get("title") or "")
        directory = str(m.get("directory") or "")
        if needle and needle not in f"{title} {directory} {sid}".casefold():
            continue
        table = projects_table.get(pid, {}) if pid else {}
        items.append(
            CostSessionRead(
                session_id=sid,
                project_id=pid,
                project_worktree=str(table.get("worktree") or directory),
                project_name=table.get("name"),
                parent_id=m.get("parent_id"),
                title=m.get("title"),
                directory=directory,
                model=str(m.get("model") or ""),
                agent=m.get("agent"),
                billing_category=str(entry.get("billing_category") or "unknown"),
                billing_reason=str(entry.get("billing_reason") or ""),
                billing_mixed=bool(entry.get("billing_mixed")),
                models=list(entry.get("models") or []),
                requests=int(entry.get("requests") or 0),
                recorded_cost=float(entry.get("recorded_cost") or 0),
                input=int(entry.get("input") or 0),
                output=int(entry.get("output") or 0),
                reasoning=int(entry.get("reasoning") or 0),
                cache_read=int(entry.get("cache_read") or 0),
                cache_write=int(entry.get("cache_write") or 0),
                throughput=int(entry.get("throughput") or 0),
                max_input=int(entry.get("max_input") or 0),
                rollup_cost=float(m.get("rollup_cost") or 0),
                time_created=int(m.get("time_created") or 0),
                time_updated=int(m.get("time_updated") or 0),
            )
        )
    sort_keys = {
        "cost": lambda item: (-item.recorded_cost, -item.requests, item.session_id),
        "requests": lambda item: (-item.requests, -item.throughput, item.session_id),
        "throughput": lambda item: (-item.throughput, -item.requests, item.session_id),
        "input": lambda item: (-item.input, -item.requests, item.session_id),
        "cache_read": lambda item: (-item.cache_read, -item.requests, item.session_id),
        "output": lambda item: (-item.output, -item.requests, item.session_id),
        "updated": lambda item: (-item.time_updated, item.session_id),
    }
    items.sort(key=sort_keys[normalized_sort])
    total = len(items)
    page = items[offset : offset + limit]
    return CostSessionListRead(
        available=True,
        source_path=str(scan.get("source_path") or ""),
        reason="ok",
        total=total,
        limit=limit,
        offset=offset,
        items=page,
    )


@router.get("/sessions/{session_id}", response_model=CostSessionDetailRead)
def cost_session_detail(request: Request, session_id: str) -> CostSessionDetailRead:
    detail = _store(request).session_detail(session_id)
    if not detail.get("available"):
        # Distinguish not-found (raised) from unavailable envelope.
        return CostSessionDetailRead(
            available=False,
            source_path=str(detail.get("source_path") or ""),
            reason=str(detail.get("reason") or "unavailable"),
            error=detail.get("error"),
            session_id=session_id,
        )
    sess = detail.get("session", {})
    return CostSessionDetailRead(
        available=True,
        source_path=str(detail.get("source_path") or ""),
        reason="ok",
        session_id=str(sess.get("session_id") or session_id),
        project_id=str(sess.get("project_id") or ""),
        project_worktree=str(sess.get("project_worktree") or ""),
        project_name=sess.get("project_name"),
        parent_id=sess.get("parent_id"),
        children=list(detail.get("session", {}).get("children", []) or detail.get("children", []) or sess.get("children", []) or []),
        title=sess.get("title"),
        directory=str(sess.get("directory") or ""),
        model=str(sess.get("model") or ""),
        agent=sess.get("agent"),
        rollup_cost=float(sess.get("rollup_cost") or 0),
        rollup_input=int((sess.get("rollup") or {}).get("input") or 0),
        rollup_output=int((sess.get("rollup") or {}).get("output") or 0),
        rollup_reasoning=int((sess.get("rollup") or {}).get("reasoning") or 0),
        rollup_cache_read=int((sess.get("rollup") or {}).get("cache_read") or 0),
        rollup_cache_write=int((sess.get("rollup") or {}).get("cache_write") or 0),
        time_created=int(sess.get("time_created") or 0),
        time_updated=int(sess.get("time_updated") or 0),
        calls=detail.get("calls", []),
        by_model=detail.get("by_model", []),
        failures=detail.get("failures", []),
        message_counts=dict(detail.get("message_counts", {}) or {}),
    )


@router.get("/spikes", response_model=CostSpikesRead)
def cost_spikes(
    request: Request,
    preset: str = Query(default="today"),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    timezone: str = Query(default="Europe/Dublin"),
) -> CostSpikesRead:
    """Deterministic investigation: what caused the spending burst? No LLM."""
    label, tz_name, start_ms, end_ms = resolve_bounds(
        preset=preset, date=date, date_from=date_from, date_to=date_to, timezone=timezone
    )
    scan = _store(request).scan_window(start_ms, end_ms)
    if not scan.get("available"):
        return CostSpikesRead(
            available=False,
            source_path=str(scan.get("source_path") or ""),
            reason=str(scan.get("reason") or "unavailable"),
            error=scan.get("error"),
            date_label=label,
            timezone=tz_name,
            start_ms=start_ms,
            end_ms=end_ms,
            findings=[],
        )
    findings: list[dict] = []
    per_minute: list[dict] = list(scan.get("per_minute") or [])
    if per_minute:
        peak = max(per_minute, key=lambda item: int(item.get("requests") or 0))
        if int(peak.get("requests") or 0) >= 20:
            findings.append(
                {
                    "id": "high-call-rate",
                    "title": f"High call rate at {peak.get('minute')} UTC ({peak.get('requests')} requests/min)",
                    "detail": "Deterministic: busiest UTC minute in the selected window. Open the minute's sessions to verify concurrency, retries and overlapping agents.",
                    "severity": "info",
                    "session_ids": [],
                    "minutes": [str(peak.get("minute") or "")],
                }
            )
    failures: dict = dict(scan.get("failures") or {})
    if int(failures.get("go_limit") or 0) > 0:
        findings.append(
            {
                "id": "go-limit",
                "title": f"Go allowance rejections observed ({failures.get('go_limit')} idle failures)",
                "detail": "Local idle records report provider.go-limit (monthly). Dollar `cost` stays zero for these calls; allowance impact is not retained locally.",
                "severity": "warning",
                "session_ids": [],
                "minutes": [],
            }
        )
    if int(failures.get("no_route") or 0) > 0:
        findings.append(
            {
                "id": "no-route",
                "title": f"Free-model route failures observed ({failures.get('no_route')})",
                "detail": "provider.no-route for free models (e.g. nemotron/space-bunny via opencode-go). These are availability signals, not spending.",
                "severity": "info",
                "session_ids": [],
                "minutes": [],
            }
        )
    per_model: list[dict] = list(scan.get("per_model") or [])
    zero_cost_models = [m for m in per_model if float(m.get("recorded_cost") or 0) == 0 and int(m.get("requests") or 0) > 0]
    if zero_cost_models:
        top = sorted(zero_cost_models, key=lambda m: -int(m.get("requests") or 0))[:3]
        names = ", ".join(f"{m.get('provider')}/{m.get('model')} ({m.get('requests')})" for m in top)
        findings.append(
            {
                "id": "zero-cost-volume",
                "title": "High-volume zero-cost models dominate the window",
                "detail": f"Top zero-cost routes by request count: {names}. Zero dollar cost does not mean zero Go allowance use; verify provider-side allowance for these routes.",
                "severity": "warning",
                "session_ids": [],
                "minutes": [],
            }
        )
    # Low cache reuse: sessions with large input but small cache_read.
    per_session: dict = scan.get("per_session", {})
    low_cache = [
        sid
        for sid, entry in per_session.items()
        if int(entry.get("input") or 0) > 100_000 and int(entry.get("cache_read") or 0) < int(entry.get("input") or 0) // 2
    ]
    if low_cache:
        findings.append(
            {
                "id": "low-cache-reuse",
                "title": f"Possible low cache reuse in {len(low_cache)} session(s)",
                "detail": "Heuristic: input > 100k with cache_read < input/2. Check x-opencode-session stability, repeated system prompts and large context serialization in those sessions.",
                "severity": "info",
                "session_ids": sorted(low_cache)[:10],
                "minutes": [],
            }
        )
    # Overlapping agents: parent sessions with multiple children active in window.
    meta: dict = scan.get("session_meta", {})
    children_by_parent: dict[str, list[str]] = {}
    for sid, m in meta.items():
        parent = m.get("parent_id")
        if parent:
            children_by_parent.setdefault(str(parent), []).append(sid)
    overlapped = {p: kids for p, kids in children_by_parent.items() if len(kids) > 1}
    if overlapped:
        sample_parent = sorted(overlapped.keys())[0]
        findings.append(
            {
                "id": "parallel-agents",
                "title": f"Parallel subagents detected ({len(overlapped)} parent(s) with >1 child in window)",
                "detail": f"Example parent {sample_parent} with children {', '.join(overlapped[sample_parent][:5])}. Concurrency multiplies request volume even when per-request cost is unchanged.",
                "severity": "info",
                "session_ids": [sample_parent, *overlapped[sample_parent][:5]],
                "minutes": [],
            }
        )
    # Large single-call contexts: max uncached input per session.
    per_session: dict = scan.get("per_session", {})
    large_context = sorted(
        ((sid, int(entry.get("max_input") or 0)) for sid, entry in per_session.items()),
        key=lambda pair: -pair[1],
    )
    if large_context and large_context[0][1] >= 200_000:
        top = [(sid, mx) for sid, mx in large_context[:5] if mx >= 200_000]
        findings.append(
            {
                "id": "large-context",
                "title": f"Large single-call contexts ({len(top)} session(s) ≥ 200k uncached input)",
                "detail": "Largest uncached input per session: "
                + ", ".join(f"{sid[:12]}… ({mx:,} tokens)" for sid, mx in top)
                + ". Large prompts raise per-call tokens even at low call counts; check serialized context before repeating.",
                "severity": "info",
                "session_ids": [sid for sid, _ in top],
                "minutes": [],
            }
        )
    # Repeated operations: unusually high call counts per session.
    repeated = sorted(
        ((sid, int(entry.get("requests") or 0)) for sid, entry in per_session.items()),
        key=lambda pair: -pair[1],
    )
    if repeated and repeated[0][1] >= 100:
        top = [(sid, n) for sid, n in repeated[:5] if n >= 100]
        findings.append(
            {
                "id": "repeated-operations",
                "title": f"Repeated operations ({len(top)} session(s) ≥ 100 calls)",
                "detail": "Highest call counts: "
                + ", ".join(f"{sid[:12]}… ({n} calls)" for sid, n in top)
                + ". Inspect timelines for loops, retries or duplicated prompts.",
                "severity": "info",
                "session_ids": [sid for sid, _ in top],
                "minutes": [],
            }
        )
    if not findings:
        findings.append(
            {
                "id": "no-spike",
                "title": "No deterministic spike pattern detected",
                "detail": "Request rate, failures, zero-cost volume, cache reuse and parallelism show no outlier in this window. This is an observation, not proof of absence.",
                "severity": "info",
                "session_ids": [],
                "minutes": [],
            }
        )
    return CostSpikesRead(
        available=True,
        source_path=str(scan.get("source_path") or ""),
        reason="ok",
        date_label=label,
        timezone=tz_name,
        start_ms=start_ms,
        end_ms=end_ms,
        findings=findings,  # type: ignore[arg-type]
    )


@router.get("/efficiency", response_model=CostEfficiencyRead)
def cost_efficiency(
    request: Request,
    preset: str = Query(default="today"),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    timezone: str = Query(default="Europe/Dublin"),
) -> CostEfficiencyRead:
    """Advisory model-efficiency recommendations. Observes only.

    Never switches models, never starts a paid call, never touches Worker
    configuration. Every recommendation links to recorded sessions and
    requires human verification of quality/latency first.
    """
    label, tz_name, start_ms, end_ms = resolve_bounds(
        preset=preset, date=date, date_from=date_from, date_to=date_to, timezone=timezone
    )
    store = _store(request)
    scan = store.scan_window(start_ms, end_ms)
    if not scan.get("available"):
        return CostEfficiencyRead(
            available=False,
            source_path=str(scan.get("source_path") or ""),
            reason=str(scan.get("reason") or "unavailable"),
            error=scan.get("error"),
            date_label=label,
            timezone=tz_name,
            start_ms=start_ms,
            end_ms=end_ms,
            recommendations=[],
        )
    return CostEfficiencyRead(
        available=True,
        source_path=str(scan.get("source_path") or ""),
        reason="ok",
        date_label=label,
        timezone=tz_name,
        start_ms=start_ms,
        end_ms=end_ms,
        recommendations=store.build_efficiency(scan),  # type: ignore[arg-type]
    )


@router.get("/attribution", response_model=CostAttributionRead)
def cost_attribution(
    request: Request,
    preset: str = Query(default="today"),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    timezone: str = Query(default="Europe/Dublin"),
) -> CostAttributionRead:
    """Which caller-identity fields are retained, and what is missing.

    Counts sessions/requests in the window that cannot be attributed to a
    known project (Unknown bucket). Missing fields document the
    instrumentation Mission Control, Worker, Pi and ALIVE still need.
    """
    label, tz_name, start_ms, end_ms = resolve_bounds(
        preset=preset, date=date, date_from=date_from, date_to=date_to, timezone=timezone
    )
    void = (label, tz_name)
    _ = void
    store = _store(request)
    audit = store.caller_identity_audit()
    scan = store.scan_window(start_ms, end_ms)
    if not scan.get("available"):
        return CostAttributionRead(
            available=False,
            source_path=str(scan.get("source_path") or ""),
            reason=str(scan.get("reason") or "unavailable"),
            error=scan.get("error"),
            retained=list(audit.get("retained") or []),
            missing=list(audit.get("missing") or []),
            instrumentation=list(audit.get("instrumentation") or []),
        )
    per_session: dict = scan.get("per_session", {})
    meta: dict = scan.get("session_meta", {})
    projects_table: dict = scan.get("projects", {})
    unknown_sessions = 0
    unknown_requests = 0
    for sid, entry in per_session.items():
        pid = str((meta.get(sid, {}) or {}).get("project_id") or "")
        if not pid or pid not in projects_table:
            unknown_sessions += 1
            unknown_requests += int(entry.get("requests") or 0)
    return CostAttributionRead(
        available=True,
        source_path=str(scan.get("source_path") or ""),
        reason="ok",
        retained=list(audit.get("retained") or []),
        missing=list(audit.get("missing") or []),
        instrumentation=list(audit.get("instrumentation") or []),
        unknown_sessions=unknown_sessions,
        unknown_requests=unknown_requests,
    )


_GO_MODELS_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_GO_MODELS_TTL_SECONDS = 600.0


async def _fetch_go_models() -> dict[str, Any]:
    """Best-effort fetch of the public Go model list. Never raises.

    Keyless, read-only, short timeout, cached for 10 minutes. Any failure
    degrades to unavailable so models stay classified as unknown.
    """
    import time as _time

    now = _time.monotonic()
    cached = _GO_MODELS_CACHE.get("payload")
    if cached is not None and (now - float(_GO_MODELS_CACHE.get("at") or 0)) < _GO_MODELS_TTL_SECONDS:
        return cached
    result: dict[str, Any] = {"available": False, "models": [], "detail": "unavailable"}
    try:
        import httpx as _httpx

        async with _httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
            response = await client.get("https://opencode.ai/inference/go/v1/models")
        if response.status_code != 200:
            result["detail"] = f"Go model list returned HTTP {response.status_code}"
        else:
            payload = response.json()
            items: list[Any] = []
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict):
                for key in ("data", "models", "items"):
                    if isinstance(payload.get(key), list):
                        items = payload[key]
                        break
            models: list[dict[str, Any]] = []
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                model_id = str(entry.get("id") or entry.get("model") or entry.get("name") or "")
                if not model_id:
                    continue
                provider = str(entry.get("provider") or entry.get("providerID") or "opencode-go")
                price = entry.get("pricing") or entry.get("price") or entry.get("cost") or ""
                models.append({"id": model_id, "provider": provider, "price": price})
            result = {"available": True, "models": models, "detail": f"Go lists {len(models)} model(s)."}
    except Exception as exc:  # noqa: BLE001 - best-effort catalogue, never fails the page
        result = {"available": False, "models": [], "detail": f"Go model list unreachable ({exc.__class__.__name__})."}
    _GO_MODELS_CACHE["at"] = now
    _GO_MODELS_CACHE["payload"] = result
    return result


@router.get("/catalogue", response_model=CostCatalogueRead)
async def cost_catalogue(request: Request) -> CostCatalogueRead:
    """Model availability/pricing catalogue. Read-only, never a model call.

    Pi catalogue comes from `pi --list-models` (starts no session). The Go
    list is a keyless public fetch with a short timeout and a 10-minute
    cache. Anything unreachable stays unknown — never assumed free or paid.
    """
    import asyncio as _asyncio

    store = _store(request)
    try:
        from mission_control.research import pi_backend as _pi

        pi = await _asyncio.to_thread(_pi.discover_pi_models, 5.0)
    except Exception as exc:  # noqa: BLE001 - catalogue must never fail the page
        pi = {"available": False, "models": [], "detail": f"Pi catalogue failed ({exc.__class__.__name__})."}
    go = await _fetch_go_models()
    pi_models = [
        {
            "id": str(item.get("id") or ""),
            "provider": str((str(item.get("id") or "").split("/")[0]) or ""),
            "available": True,
            "list_price_note": "",
        }
        for item in (pi.get("models") or [])
        if isinstance(item, dict) and item.get("id")
    ]
    go_models = [
        {
            "id": str(item.get("id") or ""),
            "provider": str(item.get("provider") or "opencode-go"),
            "available": True,
            "list_price_note": str(item.get("price") or ""),
        }
        for item in (go.get("models") or [])
        if isinstance(item, dict) and item.get("id")
    ]
    return CostCatalogueRead(
        available=True,
        source_path=store.source_path,
        reason="ok",
        pi_available=bool(pi.get("available")),
        pi_models=pi_models,  # type: ignore[arg-type]
        pi_detail=str(pi.get("detail") or ""),
        go_available=bool(go.get("available")),
        go_models=go_models,  # type: ignore[arg-type]
        go_detail=str(go.get("detail") or ""),
    )
