"""Read-only OpenCode cost API (MC-COST-01).

All endpoints are GET-only and never invoke a model. Missing, locked or
incompatible sources return explicit unavailable envelopes, never silent
zeros.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from mission_control.core.errors import NotFound
from mission_control.opencode_cost import OpencodeCostStore, resolve_bounds
from mission_control.schemas import (
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
                "cache_read": 0,
            },
        )
        bucket["sessions"] += 1
        bucket["requests"] += int(entry.get("requests") or 0)
        bucket["recorded_cost"] += float(entry.get("recorded_cost") or 0)
        bucket["input"] += int(entry.get("input") or 0)
        bucket["output"] += int(entry.get("output") or 0)
        bucket["cache_read"] += int(entry.get("cache_read") or 0)
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
        },
        by_model=[
            CostModelRead(
                model=str(item.get("model") or ""),
                provider=str(item.get("provider") or ""),
                variant=str(item.get("variant") or ""),
                requests=int(item.get("requests") or 0),
                recorded_cost=float(item.get("recorded_cost") or 0),
                input=int(item.get("input") or 0),
                output=int(item.get("output") or 0),
                reasoning=int(item.get("reasoning") or 0),
                cache_read=int(item.get("cache_read") or 0),
                cache_write=int(item.get("cache_write") or 0),
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
                cache_read=int(item.get("cache_read") or 0),
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
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CostSessionListRead:
    label, tz_name, start_ms, end_ms = resolve_bounds(
        preset=preset, date=date, date_from=date_from, date_to=date_to, timezone=timezone
    )
    void = (label, tz_name)
    _ = void
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
                requests=int(entry.get("requests") or 0),
                recorded_cost=float(entry.get("recorded_cost") or 0),
                input=int(entry.get("input") or 0),
                output=int(entry.get("output") or 0),
                reasoning=int(entry.get("reasoning") or 0),
                cache_read=int(entry.get("cache_read") or 0),
                cache_write=int(entry.get("cache_write") or 0),
                rollup_cost=float(m.get("rollup_cost") or 0),
                time_created=int(m.get("time_created") or 0),
                time_updated=int(m.get("time_updated") or 0),
            )
        )
    items.sort(key=lambda item: (-item.recorded_cost, -item.requests, item.session_id))
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
