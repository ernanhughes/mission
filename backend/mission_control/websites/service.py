"""Website workspaces and managed Hugo preview servers (MC-WEBSITES-CULTIVATION-01).

Discovery is read-only (see ``mission_control.discovery.websites``). Hugo
previews are managed subprocesses, launched with an argument list (never a
shell-interpolated command) from the project's own root:

- bind to ``127.0.0.1`` only, distinct free ports per site (from 1313 up);
- an already-running managed server is reused, never duplicated;
- drafts are not rendered by default (no ``-D``/``--buildDrafts``);
- nothing launches automatically during discovery;
- only discovered/configured website paths can launch.

Process utilities (environment allowlist, port probing, tree termination) are
reused from the existing process manager rather than reimplemented.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import uuid
from pathlib import Path
from subprocess import Popen as _ManagedPopen
from typing import Any

from mission_control.core.errors import (
    CapabilityUnavailable,
    Conflict,
    LaunchProblem,
    NotFound,
)
from mission_control.core.paths import (
    normalize_absolute_path,
    resolve_executable,
)
from mission_control.discovery.websites import (
    DetectedWebsite,
    detect_websites,
    website_read,
)
from mission_control.persistence.db import now_iso
from mission_control.processes.health import port_is_open
from mission_control.processes.manager import (
    WINDOWS_FLAGS,
    build_environment,
)

logger = logging.getLogger(__name__)

FIRST_HUGO_PORT = 1313
READINESS_TIMEOUT_SECONDS = 20.0
READINESS_POLL_SECONDS = 0.4


class WebsitesState:
    """In-memory registry of managed Hugo preview servers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._servers: dict[str, dict[str, Any]] = {}

    def _drop_dead(self) -> None:
        dead = [
            site_id
            for site_id, entry in self._servers.items()
            if entry.get("process") is None or entry["process"].poll() is not None
        ]
        for site_id in dead:
            self._servers.pop(site_id, None)

    def status(self, site_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._drop_dead()
            entry = self._servers.get(site_id)
            if entry is None:
                return None
            return {
                "alive": True,
                "url": entry["url"],
                "port": entry["port"],
                "process_id": entry["process_id"],
            }

    def all_statuses(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            self._drop_dead()
            return {
                site_id: {
                    "alive": True,
                    "url": entry["url"],
                    "port": entry["port"],
                    "process_id": entry["process_id"],
                }
                for site_id, entry in self._servers.items()
            }

    def ports_in_use(self) -> set[int]:
        with self._lock:
            self._drop_dead()
            return {int(entry["port"]) for entry in self._servers.values()}

    def register(self, site_id: str, entry: dict[str, Any]) -> None:
        with self._lock:
            self._drop_dead()
            self._servers[site_id] = entry

    def take(self, site_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._servers.pop(site_id, None)


def _free_port(preferred: int, taken: set[int]) -> int:
    port = max(preferred, FIRST_HUGO_PORT)
    for _ in range(200):
        if port not in taken and not port_is_open("127.0.0.1", port):
            return port
        port += 1
    raise LaunchProblem(
        "No free loopback port is available for a Hugo preview",
        detail="Stop a managed server or free a port near 1313 and try again.",
    )


def _wait_for_port(port: int, *, timeout: float = READINESS_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open("127.0.0.1", port):
            return True
        time.sleep(READINESS_POLL_SECONDS)
    return False


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)
    except (OSError, ValueError):
        pass


def resolve_site(root: Path, site_id: str) -> DetectedWebsite:
    """Resolve a launchable website id against fresh discovery (path-safe).

    Only ids produced by current discovery under the configured root resolve,
    so launch paths are restricted to validated discovered websites.
    """
    websites, _ = detect_websites([root])
    for site in websites:
        if site.site_id == site_id:
            return site
    raise NotFound("Website not found under the configured websites root")


def launch_hugo(state: WebsitesState, site: DetectedWebsite) -> dict[str, Any]:
    """Launch (or reuse) a managed Hugo preview server for one website."""
    if not site.is_hugo:
        raise CapabilityUnavailable(
            "This website is not a Hugo project",
            detail="; ".join(site.evidence) or "No Hugo configuration was observed.",
        )
    try:
        working_directory = normalize_absolute_path(site.path, field="website path")
    except Exception as exc:
        raise LaunchProblem(str(exc)) from exc
    if not Path(working_directory).is_dir():
        raise LaunchProblem(
            "Website directory is unavailable",
            detail=f"{working_directory} is missing or not a directory.",
        )
    executable = resolve_executable("hugo")
    if not executable:
        raise CapabilityUnavailable(
            "Hugo executable not found",
            detail="Install Hugo and ensure 'hugo' is on PATH, then retry the launch.",
        )

    existing = state.status(site.site_id)
    if existing is not None:
        return {
            "id": site.site_id,
            "name": site.name,
            "path": site.path,
            "url": existing["url"],
            "port": existing["port"],
            "process_id": existing["process_id"],
            "reused": True,
            "detail": "Reused the already-running managed Hugo server.",
        }

    port = _free_port(FIRST_HUGO_PORT, state.ports_in_use())
    arguments = ["server", "--bind", "127.0.0.1", "--port", str(port)]
    process_id = f"hugo-{uuid.uuid4().hex[:12]}"
    try:
        process = _ManagedPopen(
            [executable, *arguments],
            cwd=working_directory,
            env=build_environment([]),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            shell=False,
            close_fds=True,
            creationflags=WINDOWS_FLAGS,
            start_new_session=False,
        )
    except (OSError, ValueError) as exc:
        raise LaunchProblem(f"Could not start Hugo: {exc}") from exc

    if process.poll() is not None:
        raise LaunchProblem(
            "Hugo exited before serving",
            detail=f"Process ended with code {process.returncode} immediately after launch.",
        )
    if not _wait_for_port(port):
        _terminate(process)
        raise LaunchProblem(
            f"Hugo did not answer on 127.0.0.1:{port} within {READINESS_TIMEOUT_SECONDS:g}s",
            detail="The managed server was stopped. Inspect the site with 'hugo server' manually for errors.",
        )

    state.register(
        site.site_id,
        {
            "process": process,
            "port": port,
            "url": f"http://127.0.0.1:{port}/",
            "process_id": process_id,
            "pid": process.pid,
            "started_at": now_iso(),
        },
    )
    logger.info("Hugo preview for %s on 127.0.0.1:%s (pid %s)", site.site_id, port, process.pid)
    return {
        "id": site.site_id,
        "name": site.name,
        "path": site.path,
        "url": f"http://127.0.0.1:{port}/",
        "port": port,
        "process_id": process_id,
        "reused": False,
        "detail": f"Hugo serving '{site.name}' from {working_directory}.",
    }


def stop_hugo(state: WebsitesState, site_id: str) -> dict[str, Any]:
    """Stop a managed Hugo preview server (safe no-op when not running)."""
    entry = state.take(site_id)
    if entry is None:
        raise Conflict("No managed Hugo server is running for this website")
    process = entry.get("process")
    if process is not None and process.poll() is None:
        _terminate(process)
    logger.info("Stopped Hugo preview for %s", site_id)
    return {"ok": True, "detail": f"Stopped the managed Hugo server for '{site_id}'."}


def list_websites(root: Path, state: WebsitesState) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Discover websites and join live managed-server status (never launches)."""
    websites, diagnostics = detect_websites([root])
    statuses = state.all_statuses()
    return [website_read(site, running=statuses.get(site.site_id)) for site in websites], diagnostics
