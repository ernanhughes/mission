"""Operational Inspect control panel (MC-INSPECT-04).

Read-only snapshot serving lives in ``api.inspect``; this router owns
*actions*: durable, cancellable Inspect CLI jobs plus the all-project
inventory (registry + consumer snapshot + job state).

Safety contract (no exceptions):
- Only fixed allowlisted argv is ever launched (``python inspect.py <op>``);
  no user-supplied paths, no shell, no command strings from capabilities.
- Repository ids are lookup keys validated against the known inventory
  (consumer snapshot projects or the Application registry). For registry
  applications never inspected, the server-side stored ``repository_path``
  is passed — never a request-supplied path — and only after verifying it
  is an existing git checkout.
- One active long operation per repository; bounded global concurrency.
- Jobs write only to Inspect's own output/state directories (the CLI's
  doing, with cwd pinned to the Inspect checkout). Inspected source repos
  are never mutated by jobs; ``stamp`` output files are Inspect-owned and
  reported as such. Failed/cancelled runs never replace published outputs.
- Reconciliation is evidence-based (pid liveness + the CLI's own logged
  result JSON), never guessed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.config import RuntimeSettings
from mission_control.inspect_snapshots import (
    get_store,
    map_inspect_project,
    normalize_repository_path,
)
from mission_control.models import Application, InspectRun
from mission_control.persistence.db import now_iso
from mission_control.schemas import (
    InspectInventoryProject,
    InspectInventoryRead,
    InspectJobListRead,
    InspectRunRead,
)

router = APIRouter(prefix="/api/inspect/ops", tags=["inspect-ops"])

# operation -> (argv tail, label, repo_required, long_running)
OPERATIONS: dict[str, tuple[list[str], str, bool, bool]] = {
    "inspect": (["inspect"], "Inspect (resume-safe)", True, True),
    "full": (["inspect", "--force"], "Full inspection", True, True),
    "enrich": (["enrich", "--force"], "Enrich capabilities", True, True),
    "stamp": (["stamp"], "Stamp project card", True, True),
    "validate": (["validate"], "Validate outputs", False, False),
    "export": (["export"], "Publish consumer snapshot", False, False),
    "refresh": (["snapshot"], "Refresh state snapshot", False, False),
}
ACTIVE = ("queued", "running")
GLOBAL_CONCURRENCY_LIMIT = 4
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _checkout_dir(settings: RuntimeSettings) -> Path:
    return Path(settings.inspect_checkout_dir)


def _logs_dir(settings: RuntimeSettings) -> Path:
    d = settings.log_dir / "inspect-ops"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kill_tree(pid: int | None) -> None:
    try:
        import psutil

        if not pid:
            return
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        proc.kill()
    except Exception:
        pass


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        import psutil

        return psutil.pid_exists(pid)
    except Exception:
        return False


def _known_snapshot_ids(settings: RuntimeSettings) -> tuple[set[str], dict[str, dict]]:
    """Snapshot project ids + records by id (empty when no snapshot published)."""
    store = get_store(settings.inspect_dir)
    data, _stale = store.view()
    if data is None:
        return set(), {}
    by_id = {str(p.get("id", "")): p for p in data.projects if p.get("id")}
    return set(by_id), by_id


def _registry_apps(session: Session) -> list[Application]:
    return list(session.scalars(select(Application)).all())


def _resolve_repo_target(
    session: Session, repository_id: str, settings: RuntimeSettings
) -> tuple[str, str, str | None]:
    """Validate a request-supplied repo key -> (argv_target, mission_app_id, app_path).

    ``argv_target`` is either a snapshot-validated inspect id or a
    server-side registry path (verified git checkout). Request input never
    reaches argv by any other route.
    """
    if not _ID_RE.match(repository_id):
        raise HTTPException(status_code=404, detail="unknown repository")
    snapshot_ids, snapshot_by_id = _known_snapshot_ids(settings)
    if repository_id in snapshot_ids:
        apps = _registry_apps(session)
        mission_id, _ = map_inspect_project(repository_id, None, apps)
        # Prefer the live path pinned in the snapshot record: the Inspect CLI
        # can only resolve ids present in its discovery registry, while an
        # explicit existing path always resolves.
        record = snapshot_by_id.get(repository_id, {})
        live_path = (record.get("path") or "").strip()
        if live_path and Path(live_path).is_dir():
            return live_path, mission_id, live_path
        return repository_id, mission_id, None
    # Registry application never inspected: use its stored path (server-side).
    app = session.get(Application, repository_id)
    if app is None or not app.repository_path:
        raise HTTPException(status_code=404, detail="unknown repository")
    repo_path = Path(app.repository_path)
    if not repo_path.is_dir() or not (repo_path / ".git").exists():
        raise HTTPException(
            status_code=409, detail="repository path is missing or not a git checkout"
        )
    return app.repository_path, app.id, app.repository_path


def _active_runs(session: Session) -> list[InspectRun]:
    return list(
        session.scalars(
            select(InspectRun).where(InspectRun.status.in_(ACTIVE))
        ).all()
    )


def _parse_log_result(run: InspectRun) -> dict:
    """Read the CLI's own reported result from the job log tail.

    The CLI prints its result with ``json.dumps(..., indent=2)``, so the
    object may span several lines. Try decoding progressively larger tails
    (last line, last two lines, ...) and return the first object that carries
    a ``result`` key.
    """
    try:
        lines = Path(run.log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    tail = [line for line in lines if line.strip()][-25:]
    for width in range(1, len(tail) + 1):
        candidate = "\n".join(tail[-width:])
        try:
            doc = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(doc, dict) and doc.get("result"):
            return doc
    return {}


_RESULT_TO_STATUS = {
    "complete": "completed",
    "partial": "partial",
    "skipped": "completed",
    "dry-run": "completed",
    "failed": "failed",
}


def _reconcile(session: Session, run: InspectRun) -> None:
    if run.status not in ACTIVE:
        return
    if _pid_alive(run.pid):
        if run.status == "queued":
            run.status = "running"
            run.started_at = run.started_at or now_iso()
        return
    run.finished_at = now_iso()
    doc = _parse_log_result(run)
    result = str(doc.get("result", "") or "")
    run.status = _RESULT_TO_STATUS.get(result, "failed")
    if isinstance(doc.get("validation"), str):
        run.validation_status = doc["validation"]
    elif isinstance(doc.get("validation"), dict):
        run.validation_status = str(doc["validation"].get("status", ""))
    try:
        run.result_json = json.dumps(doc)[:2000]
    except (TypeError, ValueError):
        run.result_json = "{}"
    if run.status == "failed" and not run.error:
        run.error = "no result recorded (collection or launch failure)"


def _run_read(session: Session, run: InspectRun) -> InspectRunRead:
    _reconcile(session, run)
    try:
        summary = json.loads(run.result_json or "{}")
    except ValueError:
        summary = {}
    if not isinstance(summary, dict):
        summary = {}
    return InspectRunRead(
        run_id=run.run_id,
        repository_id=run.repository_id,
        mission_application_id=run.mission_application_id,
        operation=run.operation,
        scope=run.scope,
        status=run.status,
        pid=run.pid,
        requested_at=run.requested_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        exit_code=run.exit_code,
        validation_status=run.validation_status,
        result_summary=summary,
        error=run.error,
        cancellable=run.status in ACTIVE,
    )


class OpRequest(BaseModel):
    repository_id: str = ""
    operation: str = "inspect"


def _launch(
    session: Session, repository_id: str, operation: str, settings: RuntimeSettings
) -> dict:
    if operation not in OPERATIONS:
        raise HTTPException(status_code=400, detail=f"unknown operation {operation!r}")
    argv_tail, _label, repo_required, long = OPERATIONS[operation]
    checkout = _checkout_dir(settings)
    if not (checkout / "inspect.py").is_file():
        raise HTTPException(status_code=409, detail="Inspect checkout is not available")
    mission_app_id = ""
    argv_target = ""
    if repo_required:
        if not repository_id:
            raise HTTPException(status_code=400, detail="repository_id is required")
        argv_target, mission_app_id, _ = _resolve_repo_target(
            session, repository_id, settings
        )
    active = _active_runs(session)
    if len(active) >= GLOBAL_CONCURRENCY_LIMIT:
        raise HTTPException(
            status_code=409,
            detail=f"concurrency limit reached ({GLOBAL_CONCURRENCY_LIMIT} active runs)",
        )
    if long and repository_id:
        for other in active:
            if other.repository_id == repository_id or (
                mission_app_id and other.mission_application_id == mission_app_id
            ):
                _reconcile(session, other)
                if other.status in ACTIVE:
                    return {
                        "run": _run_read(session, other).model_dump(),
                        "duplicate": True,
                    }
    run = InspectRun(
        run_id="inspect-" + uuid.uuid4().hex[:16],
        repository_id=repository_id,
        mission_application_id=mission_app_id,
        operation=operation,
        scope="full",
        status="queued",
        command="",
        requested_at=now_iso(),
        log_path=str(_logs_dir(settings) / f"inspect-{uuid.uuid4().hex[:12]}.log"),
    )
    argv = [sys.executable, "inspect.py", *argv_tail]
    if repo_required:
        # Insert repo target right after the verb: inspect <target> [--force].
        argv = [sys.executable, "inspect.py", argv_tail[0], argv_target, *argv_tail[1:]]
    run.command = " ".join(argv)
    session.add(run)
    session.flush()
    try:
        with open(run.log_path, "wb") as log:
            proc = subprocess.Popen(
                argv,
                cwd=str(checkout),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                close_fds=True,
                creationflags=0x08000000 if os.name == "nt" else 0,
                start_new_session=(os.name != "nt"),
            )
            run.pid = proc.pid
            run.status = "running"
            run.started_at = now_iso()
    except Exception as exc:  # noqa: BLE001 - launch failure is a job outcome
        run.status = "failed"
        run.error = f"launch failed: {exc}"
        run.finished_at = now_iso()
    session.flush()
    return {"run": _run_read(session, run).model_dump(), "duplicate": False}


def _inventory_rows(
    session: Session, settings: RuntimeSettings
) -> tuple[list[dict], list[dict], dict[str, int]]:
    apps = _registry_apps(session)
    snapshot_ids, by_id = _known_snapshot_ids(settings)
    store = get_store(settings.inspect_dir)
    data, _stale = store.view()
    sources = {str(s.get("repository", "")): s for s in (data.manifest.get("sources") or [])} if data else {}
    caps_by_repo: dict[str, int] = {}
    use_by_repo: dict[str, int] = {}
    cov_by_repo: set[str] = set()
    if data:
        for cap in data.capabilities:
            repo = str(cap.get("repository", ""))
            caps_by_repo[repo] = caps_by_repo.get(repo, 0) + 1
        for usage in data.usages:
            repo = str(usage.get("repository", ""))
            use_by_repo[repo] = use_by_repo.get(repo, 0) + 1
        for cov in data.coverages:
            repo = str(cov.get("repository", "") or cov.get("repository_id", ""))
            if repo:
                cov_by_repo.add(repo)
    # Job state: active run + latest run per repository key.
    active_by_repo: dict[str, InspectRun] = {}
    latest_by_repo: dict[str, InspectRun] = {}
    for run in session.scalars(select(InspectRun).order_by(desc(InspectRun.requested_at))).all():
        _reconcile(session, run)
        for key in (run.repository_id, run.mission_application_id):
            if key and key not in latest_by_repo:
                latest_by_repo[key] = run
        if run.status in ACTIVE and run.repository_id not in active_by_repo:
            active_by_repo[run.repository_id] = run
    session.flush()

    rows: list[dict] = []
    seen_inspect: set[str] = set()
    snapshot_by_path: dict[str | None, str] = {}
    for sid, record in by_id.items():
        snapshot_by_path.setdefault(normalize_repository_path(record.get("path")), sid)
    for app in sorted(apps, key=lambda a: (a.archived, a.name.lower())):
        # Identity mapping: inspect id == mission id for the known pair,
        # otherwise repository-path equality against the snapshot projects.
        inspect_id = ""
        if app.id in by_id:
            inspect_id = app.id
        else:
            hit = snapshot_by_path.get(normalize_repository_path(app.repository_path))
            if hit:
                inspect_id = hit
        mapped = inspect_id != ""
        record = by_id.get(inspect_id, {}) if inspect_id else {}
        path = app.repository_path or (record.get("path", "") if record else "")
        reachable = bool(path) and Path(path).is_dir()
        source = sources.get(inspect_id, {}) if inspect_id else {}
        if inspect_id:
            seen_inspect.add(inspect_id)
        active = active_by_repo.get(inspect_id) if inspect_id else None
        latest = (latest_by_repo.get(inspect_id) or latest_by_repo.get(app.id)) if inspect_id else latest_by_repo.get(app.id)
        execution = "never-inspected"
        if active is not None:
            execution = active.status
        elif source:
            execution = str(source.get("inspection_status", "complete") or "complete")
            if execution not in ("complete", "partial", "failed"):
                execution = "complete"
        elif latest is not None and latest.status in ("failed",):
            execution = "failed"
        stale = bool(source.get("stale")) if source else False
        freshness = "unknown"
        if source:
            freshness = "source-changed" if stale else "current"
        enrichment = "unknown"
        if inspect_id and (inspect_id in caps_by_repo or source):
            has_cov = inspect_id in cov_by_repo
            has_use = use_by_repo.get(inspect_id, 0) > 0
            enrichment = "complete" if (has_cov and has_use) else ("partial" if (has_cov or has_use) else "missing")
        evidence = "unknown"
        # Evidence vocabulary is derived from published capabilities only.
        if inspect_id and inspect_id in caps_by_repo and data:
            statuses = {
                str(c.get("operational_status", ""))
                for c in data.capabilities
                if str(c.get("repository", "")) == inspect_id
            }
            if statuses == {"source-inspected-only"}:
                evidence = "source-inspected"
            elif "live-demo" in statuses:
                evidence = "live-demonstrated"
            elif statuses:
                evidence = "tested-not-demonstrated"
        if execution == "never-inspected":
            primary = "inspect"
        elif execution in ("running", "queued"):
            primary = "view"
        elif execution == "partial":
            primary = "inspect"
        elif stale:
            primary = "inspect"
        elif enrichment in ("missing", "partial"):
            primary = "enrich"
        else:
            primary = "view"
        rows.append(
            {
                "inspect_id": inspect_id or app.id,
                "name": app.name,
                "mission_application_id": app.id,
                "mapped": mapped,
                "repository_path": path or None,
                "reachable": reachable,
                "execution": execution,
                "freshness": freshness,
                "enrichment": enrichment,
                "evidence": evidence,
                "capabilities": caps_by_repo.get(inspect_id, 0),
                "usages": use_by_repo.get(inspect_id, 0),
                "last_run_id": latest.run_id if latest else None,
                "last_run_status": latest.status if latest else None,
                "last_run_at": (latest.finished_at or latest.started_at or latest.requested_at) if latest else None,
                "inspected_head_sha": source.get("head_sha"),
                "stale_reason": str(source.get("stale_reason", "") or ""),
                "primary_action": primary,
                "available_actions": (
                    ["inspect", "full", "enrich", "stamp", "view"]
                    if reachable
                    else ["view"]
                ),
            }
        )
    unmapped: list[dict] = []
    for sid in sorted(snapshot_ids - seen_inspect):
        source = sources.get(sid, {})
        unmapped.append(
            {
                "inspect_id": sid,
                "name": sid,
                "mission_application_id": None,
                "mapped": False,
                "repository_path": (by_id.get(sid, {}) or {}).get("path"),
                "reachable": False,
                "execution": str(source.get("inspection_status", "complete") or "complete"),
                "freshness": "source-changed" if source.get("stale") else "current",
                "enrichment": "unknown",
                "evidence": "unknown",
                "capabilities": caps_by_repo.get(sid, 0),
                "usages": use_by_repo.get(sid, 0),
                "last_run_id": latest_by_repo.get(sid).run_id if latest_by_repo.get(sid) else None,
                "last_run_status": latest_by_repo.get(sid).status if latest_by_repo.get(sid) else None,
                "last_run_at": None,
                "inspected_head_sha": source.get("head_sha"),
                "stale_reason": str(source.get("stale_reason", "") or ""),
                "primary_action": "view",
                "available_actions": ["view"],
            }
        )
    counts = {
        "total": len(rows),
        "mapped": sum(1 for r in rows if r["mapped"]),
        "never_inspected": sum(1 for r in rows if r["execution"] == "never-inspected"),
        "stale": sum(1 for r in rows if r["freshness"] == "source-changed"),
        "running": sum(1 for r in rows if r["execution"] in ("running", "queued")),
        "failed": sum(1 for r in rows if r["execution"] == "failed"),
        "partial": sum(1 for r in rows if r["execution"] == "partial"),
        "current": sum(1 for r in rows if r["freshness"] == "current"),
        "needs_enrichment": sum(1 for r in rows if r["enrichment"] in ("missing", "partial")),
        "unmapped": len(unmapped),
    }
    return rows, unmapped, counts


@router.get("/inventory", response_model=InspectInventoryRead)
def get_inventory(
    request: Request, session: Session = Depends(get_session)
) -> InspectInventoryRead:
    settings: RuntimeSettings = request.app.state.settings
    store = get_store(settings.inspect_dir)
    data, stale = store.view()
    rows, unmapped, counts = _inventory_rows(session, settings)
    return InspectInventoryRead(
        available=data is not None,
        stale_refresh=stale,
        total=len(rows),
        counts=counts,
        projects=[InspectInventoryProject(**r) for r in rows],
        unmapped=[InspectInventoryProject(**u) for u in unmapped],
    )


@router.post("/runs")
def start_run(
    payload: OpRequest, request: Request, session: Session = Depends(get_session)
) -> dict:
    settings: RuntimeSettings = request.app.state.settings
    return _launch(session, payload.repository_id, payload.operation, settings)


@router.get("/runs", response_model=InspectJobListRead)
def list_runs(
    repository_id: str | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> InspectJobListRead:
    query = select(InspectRun).order_by(desc(InspectRun.requested_at))
    if repository_id:
        query = query.where(
            (InspectRun.repository_id == repository_id)
            | (InspectRun.mission_application_id == repository_id)
        )
    runs = list(session.scalars(query.limit(min(max(limit, 1), 200))).all())
    out = [_run_read(session, r) for r in runs]
    session.flush()
    return InspectJobListRead(total=len(out), runs=out)


@router.get("/runs/{run_id}", response_model=InspectRunRead)
def get_run(run_id: str, session: Session = Depends(get_session)) -> InspectRunRead:
    if not _ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="unknown run")
    run = session.get(InspectRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    data = _run_read(session, run)
    session.flush()
    return data


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    if not _ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="unknown run")
    run = session.get(InspectRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    _reconcile(session, run)
    if run.status not in ACTIVE:
        return {"run": _run_read(session, run).model_dump(), "cancelled": False,
                "reason": f"already {run.status}"}
    _kill_tree(run.pid or 0)
    run.status = "cancelled"
    run.finished_at = now_iso()
    session.flush()
    return {"run": _run_read(session, run).model_dump(), "cancelled": True}
