"""Test execution orchestration (AITEST-02D-UI).

All executions run through the AI Test CLI in the project's own interpreter,
which keeps supervision, deadlines, leases, snapshots and receipt semantics
intact.  The HTTP request returns a durable job identity immediately; the job
is reconciled on read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.models import AitestProject, AitestRun, AitestReceipt
from mission_control.persistence.db import now_iso, utcnow

router = APIRouter(prefix="/api/tests", tags=["tests"])

# Operation -> (extra aitest args, budget seconds, label)
OPERATIONS: dict[str, tuple[list[str], int, str]] = {
    "intelligent": (["run"], 300, "Intelligent testing"),
    "fast": (["run", "--changed"], 90, "Fast (changed) tests"),
    "failed": (["run", "--failed"], 180, "Failed tests only"),
    "full": (["run", "--full", "--policy", "release"], 300, "Full verification"),
    "discover": (["inventory"], 180, "Discover tests"),
    "profile": (["profile", "--batch", "25"], 180, "Profile unassessed tests"),
    "diagnose": (["triage"], 120, "Diagnose"),
    "quality": (["quality", "assess"], 240, "Evaluate test quality"),
}
ACTIVE = ("queued", "running")


def _aitest_python(root: str) -> str:
    """Interpreter that has AI Test installed for this project."""
    try:
        from aitest import ecosystem  # type: ignore

        env = ecosystem.resolve_env({"path": root})
        return env.get("python") or sys.executable
    except Exception:
        return sys.executable


def _logs_dir() -> Path:
    d = Path(__file__).resolve().parents[3] / "data" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kill_tree(pid: int) -> None:
    try:
        import psutil

        p = psutil.Process(pid)
        for child in p.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        p.kill()
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


def _reconcile(session: Session, run: AitestRun) -> None:
    """Advance a run's lifecycle from real evidence (never guess)."""
    if run.status not in ACTIVE:
        return
    if _pid_alive(run.pid):
        if run.status == "queued":
            run.status = "running"
            run.started_at = run.started_at or now_iso()
        return
    # Process finished: attach the receipt this run produced (never an older
    # inventory/receipt that predates the request).
    run.finished_at = now_iso()
    run.status = "completed"
    verification_ops = ("intelligent", "fast", "failed", "full")
    receipt = None
    q = select(AitestReceipt).where(
        AitestReceipt.project_id == run.project_id,
        AitestReceipt.executed > 0,
        AitestReceipt.status.in_(["FULL_PASS", "TARGETED_PASS", "TEST_FAILURE",
                                  "TIMED_OUT", "INCOMPLETE"]),
    )
    if run.started_at:
        q = q.where(AitestReceipt.created_at >= run.started_at)
    if run.operation in verification_ops:
        receipt = session.scalars(q.order_by(desc(AitestReceipt.created_at)).limit(1)).first()
    if receipt is None and run.operation in verification_ops:
        # Evidence lives in the project's local ledger until it is synced;
        # ingest it now so the UI result reflects the run we just finished.
        try:
            proj = session.get(AitestProject, run.project_id)
            if proj and proj.root:
                py = _aitest_python(proj.root)
                base = os.environ.get("MISSION_CONTROL_BASE_URL", "http://127.0.0.1:8790")
                subprocess.run(
                    [py, "-m", "aitest", "mission", "sync", "--root", proj.root,
                     "--base", base, "--mc-project", proj.mc_project_id or proj.name],
                    capture_output=True, timeout=180)
                session.expire_all()
                # Exact attribution: the run writes its execution id locally.
                exe = ""
                try:
                    marker = Path(proj.root) / ".aitest" / "last_run.json"
                    exe = json.loads(marker.read_text(encoding="utf-8")).get("execution_id", "")
                except Exception:
                    exe = ""
                if exe:
                    receipt = session.get(AitestReceipt, exe)
                if receipt is None:
                    receipt = session.scalars(
                        q.order_by(desc(AitestReceipt.created_at)).limit(1)).first()
        except Exception:
            receipt = receipt
    if receipt is not None:
        run.receipt_execution_id = receipt.execution_id
        run.verification_status = receipt.status
        run.counts_json = json.dumps({
            "discovered": receipt.discovered, "executed": receipt.executed,
            "passed": receipt.passed, "failed": receipt.failed,
            "skipped": receipt.skipped, "quarantined": receipt.quarantined,
            "deferred": receipt.deferred, "timed_out": receipt.timed_out,
            "unobserved": receipt.unobserved,
            "duration_ms": receipt.duration_ms,
        })
        if receipt.failed:
            run.status = "failed"
        elif receipt.status in ("TIMED_OUT", "INCOMPLETE", "INFRASTRUCTURE_FAILURE"):
            run.status = "incomplete"
    elif run.operation not in ("intelligent", "fast", "failed", "full"):
        # discover/profile/diagnose produce reports, not verification receipts.
        run.status = "completed"
        run.verification_status = ""
    else:
        run.verification_status = ""
        run.error = run.error or "no receipt produced (collection or setup failure)"

def _run_read(session: Session, run: AitestRun) -> dict:
    _reconcile(session, run)
    proj = session.get(AitestProject, run.project_id)
    try:
        counts = json.loads(run.counts_json or "{}")
    except ValueError:
        counts = {}
    return {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "project_name": proj.name if proj else run.project_id,
        "operation": run.operation,
        "label": OPERATIONS.get(run.operation, (None, None, run.operation))[2],
        "status": run.status,
        "pid": run.pid,
        "requested_at": run.requested_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "exit_code": run.exit_code,
        "verification_status": run.verification_status,
        "counts": counts,
        "error": run.error,
        "receipt_execution_id": run.receipt_execution_id,
        "cancellable": run.status in ACTIVE,
    }


class RunRequest(BaseModel):
    operation: str = "intelligent"


def _launch(session: Session, project: AitestProject, operation: str) -> dict:
    if operation not in OPERATIONS:
        raise HTTPException(status_code=400, detail=f"unknown operation {operation!r}")
    root = project.root
    if not root or not Path(root).is_dir():
        raise HTTPException(status_code=409,
                            detail="project directory is missing; cannot execute")
    extra, budget, _label = OPERATIONS[operation]
    py = _aitest_python(root)
    argv = [py, "-m", "aitest", *extra]
    if operation not in ("discover", "quality"):
        argv += ["--budget", str(budget)]
    if operation in ("discover", "profile", "diagnose", "quality"):
        argv += ["--root", root]
    # Deduplicate equivalent active work.
    existing = session.scalars(
        select(AitestRun).where(
            AitestRun.project_id == project.project_id,
            AitestRun.operation == operation,
            AitestRun.status.in_(ACTIVE))
    ).first()
    if existing is not None:
        _reconcile(session, existing)
        if existing.status in ACTIVE:
            return {"run": _run_read(session, existing), "duplicate": True}
    run = AitestRun(
        run_id="run-" + uuid.uuid4().hex[:16],
        project_id=project.project_id,
        operation=operation,
        status="queued",
        command=" ".join(argv),
        requested_at=now_iso(),
        log_path=str(_logs_dir() / f"aitest-{uuid.uuid4().hex[:12]}.log"),
    )
    session.add(run)
    session.flush()
    log = open(run.log_path, "wb")
    try:
        proc = subprocess.Popen(
            argv, cwd=root, stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, close_fds=True,
            creationflags=0x08000000 if os.name == "nt" else 0,
            start_new_session=(os.name != "nt"),
        )
        run.pid = proc.pid
        run.status = "running"
        run.started_at = now_iso()
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = f"launch failed: {exc}"
        run.finished_at = now_iso()
    finally:
        log.close()
    session.flush()
    return {"run": _run_read(session, run), "duplicate": False}


@router.post("/projects/{project_id}/run")
def run_project(project_id: str, payload: RunRequest,
                session: Session = Depends(get_session)) -> dict:
    project = session.get(AitestProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="unknown testing project")
    return _launch(session, project, payload.operation)


@router.post("/run-all")
def run_all(session: Session = Depends(get_session)) -> dict:
    projects = session.scalars(
        select(AitestProject).where(AitestProject.root != "")).all()
    submitted, skipped, blocked = [], [], []
    for p in projects:
        if not p.root or not Path(p.root).is_dir():
            blocked.append(p.project_id)
            continue
        try:
            res = _launch(session, p, "intelligent")
            (skipped if res["duplicate"] else submitted).append(p.project_id)
        except HTTPException as exc:
            blocked.append(f"{p.project_id}: {exc.detail}")
    return {"submitted": submitted, "already_active": skipped, "blocked": blocked}


@router.get("/jobs")
def list_jobs(limit: int = 50, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.scalars(
        select(AitestRun).order_by(desc(AitestRun.requested_at)).limit(min(limit, 200))
    ).all()
    out = [_run_read(session, r) for r in rows]
    session.flush()
    return out


@router.get("/jobs/{run_id}")
def get_job(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(AitestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    data = _run_read(session, run)
    session.flush()
    return data


@router.post("/jobs/{run_id}/cancel")
def cancel_job(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(AitestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run")
    _reconcile(session, run)
    if run.status not in ACTIVE:
        return {"run": _run_read(session, run), "cancelled": False,
                "reason": f"already {run.status}"}
    _kill_tree(run.pid or 0)
    run.status = "cancelled"
    run.finished_at = now_iso()
    session.flush()
    return {"run": _run_read(session, run), "cancelled": True}


# --------------------------------------------------------------- worker control
def _worker_state_path() -> Path:
    return Path.home() / ".aitest" / "worker-status.json"


def _pause_marker() -> Path:
    return Path.home() / ".aitest" / "worker.pause"


def _worker_heartbeat() -> dict:
    try:
        return json.loads(_worker_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _worker_alive() -> bool:
    hb = _worker_heartbeat()
    pid = hb.get("pid")
    updated = float(hb.get("updated_at") or 0)
    return bool(pid) and _pid_alive(pid) and (utcnow().timestamp() - updated) < 300


@router.get("/worker/status")
def worker_status() -> dict:
    hb = _worker_heartbeat()
    alive = _worker_alive()
    return {
        "available": bool(hb),
        "running": alive,
        "paused": _pause_marker().exists(),
        "pid": hb.get("pid"),
        "state": hb.get("state", "unknown"),
        "current_project": hb.get("current_project", ""),
        "current_job": hb.get("current_job", ""),
        "cycles": hb.get("cycles", 0),
        "completed_batches": hb.get("completed_batches", 0),
        "last_project": hb.get("last_project", ""),
        "last_result": hb.get("last_result", ""),
        "last_error": hb.get("last_error", ""),
        "updated_at": hb.get("updated_at", 0),
    }


@router.post("/worker/{action}")
def worker_control(action: str) -> dict:
    home = Path.home() / ".aitest"
    home.mkdir(parents=True, exist_ok=True)
    if action == "pause":
        _pause_marker().touch()
        return {"ok": True, "paused": True,
                "note": "worker idles at the next safe job boundary"}
    if action == "resume":
        try:
            _pause_marker().unlink()
        except FileNotFoundError:
            pass
        return {"ok": True, "paused": False}
    if action == "stop":
        hb = _worker_heartbeat()
        if hb.get("pid"):
            _kill_tree(int(hb["pid"]))
        return {"ok": True, "stopped": True}
    if action == "start":
        if _worker_alive():
            return {"ok": True, "already_running": True, "pid": _worker_heartbeat().get("pid")}
        try:
            from aitest import ecosystem  # type: ignore

            py = ecosystem.resolve_env({"path": str(Path(__file__).resolve().parents[3])}).get(
                "python")
        except Exception:
            py = sys.executable
        log = open(_logs_dir() / "aitest-worker-mc.log", "ab")
        try:
            proc = subprocess.Popen(
                [py or sys.executable, "-m", "aitest", "service", "start",
                 "--foreground", "--ecosystem"],
                cwd=str(Path(__file__).resolve().parents[3]),
                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                close_fds=True,
                creationflags=0x08000000 if os.name == "nt" else 0,
                start_new_session=(os.name != "nt"))
        finally:
            log.close()
        return {"ok": True, "started": True, "pid": proc.pid}
    if action == "restart":
        hb = _worker_heartbeat()
        if hb.get("pid"):
            _kill_tree(int(hb["pid"]))
        return worker_control("start")
    raise HTTPException(status_code=400, detail="unknown worker action")
