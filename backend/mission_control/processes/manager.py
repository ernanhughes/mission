"""Windows process launching, ownership, logs and health observation."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import psutil
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.config import RuntimeSettings
from mission_control.core.errors import (
    CapabilityUnavailable,
    Conflict,
    LaunchProblem,
    NotFound,
    ValidationProblem,
)
from mission_control.core.logging import redact_text
from mission_control.core.paths import (
    is_within,
    require_existing_directory,
    resolve_executable,
)
from mission_control.models import (
    Application,
    HealthObservation,
    LaunchDefinition,
    ProcessInstance,
    Setting,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.processes.health import port_is_open, probe

logger = logging.getLogger(__name__)

WINDOWS_FLAGS = 0
if os.name == "nt":
    # Detach from Mission Control's console and process group so a backend
    # restart does not silently kill a server. asyncio subprocess transports
    # kill their child when the event loop closes, so managed launches use a
    # native Popen plus psutil-based status observation instead.
    WINDOWS_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

_ENV_ALLOWLIST = (
    "SYSTEMROOT",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PROCESSOR_ARCHITECTURE",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
)


def build_environment(env_names: list[str]) -> dict[str, str]:
    env = {name: os.environ[name] for name in _ENV_ALLOWLIST if name in os.environ}
    for name in env_names:
        if name in os.environ:
            env[name] = os.environ[name]
    # Never inherit unrelated credentials. This marker is harmless and makes
    # child diagnostics clear.
    env["MISSION_CONTROL_MANAGED"] = "1"
    return env


def _command_preview(executable: str, arguments: list[str]) -> str:
    def quote(value: str) -> str:
        if not value or any(character.isspace() for character in value):
            return '"' + value.replace('"', '\\"') + '"'
        return value

    return redact_text(" ".join([quote(executable), *(quote(arg) for arg in arguments)]))[:2000]


def _process_identity_matches(pid: int, create_time: float | None) -> bool:
    try:
        proc = psutil.Process(pid)
        if create_time is not None and abs(proc.create_time() - create_time) > 1.0:
            return False
        return proc.is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
        return False


def _terminate_tree(pid: int, create_time: float | None, timeout: float = 5.0) -> tuple[bool, str]:
    if not _process_identity_matches(pid, create_time):
        return False, "The recorded process is no longer the same process; refusing to terminate it"
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            parent.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        _, alive = psutil.wait_procs([parent, *children], timeout=timeout)
        for leftover in alive:
            try:
                leftover.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if alive:
            psutil.wait_procs(alive, timeout=2.0)
        return True, "Process tree terminated"
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
        return False, f"Could not terminate process cleanly: {exc}"


class ProcessManager:
    def __init__(self, database: Database, settings: RuntimeSettings) -> None:
        self.database = database
        self.settings = settings
        self._live: dict[str, subprocess.Popen[bytes]] = {}
        self._stopping: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()
        self._monitor_task: asyncio.Task[None] | None = None
        self._shutting_down = False

    # ------------------------------------------------------------------ state
    def reconcile_live(self, session: Session, application_id: str | None = None) -> None:
        query = select(ProcessInstance).where(ProcessInstance.status == "running")
        if application_id:
            query = query.where(ProcessInstance.application_id == application_id)
        for record in session.scalars(query).all():
            live = self._live.get(record.id)
            if live is not None and live.poll() is None:
                continue
            if record.pid and _process_identity_matches(record.pid, record.create_time):
                if not record.reattached and record.id not in self._live:
                    record.reattached = True
                continue
            # A freshly launched process can briefly disappear from psutil's
            # snapshot while Windows finalises it. Re-check before declaring it
            # lost; PID-reuse protection still requires the creation time match.
            time.sleep(0.12)
            if record.pid and _process_identity_matches(record.pid, record.create_time):
                record.reattached = True
                continue
            logger.warning(
                "Marking process %s lost: pid=%s pid_exists=%s recorded_create_time=%s",
                record.id,
                record.pid,
                psutil.pid_exists(record.pid) if record.pid else False,
                record.create_time,
            )
            record.status = "lost"
            record.ended_at = now_iso()
            record.error = record.error or "Process ended while Mission Control was not observing it"
            record_activity(
                session,
                event_type="application_stopped",
                title="Managed process was lost",
                detail=record.error,
                application_id=record.application_id,
                process_id=record.id,
                source="mission-control",
                provenance="verified_observation",
                dedupe_key=f"process-lost-{record.id}",
            )

    def active_process(self, session: Session, application_id: str) -> ProcessInstance | None:
        self.reconcile_live(session, application_id)
        return session.scalar(
            select(ProcessInstance)
            .where(
                ProcessInstance.application_id == application_id,
                ProcessInstance.status == "running",
            )
            .order_by(desc(ProcessInstance.started_at))
        )

    def running_count(self, session: Session) -> int:
        self.reconcile_live(session)
        return int(
            session.scalar(
                select(func.count())
                .select_from(ProcessInstance)
                .where(ProcessInstance.status == "running")
            )
            or 0
        )

    def _max_managed(self) -> int:
        with self.database.session() as session:
            setting = session.get(Setting, "processes")
            return int(setting.value.get("max_managed", 5)) if setting else 5

    def _choose_definition(
        self, session: Session, application: Application, launch_id: str | None
    ) -> LaunchDefinition:
        if launch_id:
            definition = session.get(LaunchDefinition, launch_id)
            if definition is None or definition.application_id != application.id:
                raise NotFound("Launch definition not found for this application")
            if not definition.enabled:
                raise CapabilityUnavailable(
                    "That launch definition is disabled", detail=definition.verification_note or None
                )
            return definition
        definitions = session.scalars(
            select(LaunchDefinition).where(
                LaunchDefinition.application_id == application.id,
                LaunchDefinition.enabled.is_(True),
            )
        ).all()
        primary = next((item for item in definitions if item.is_primary), None)
        if primary:
            return primary
        if definitions:
            return definitions[0]
        raise CapabilityUnavailable(
            "No enabled launch definition",
            detail="Configure and enable a launch definition in the application settings.",
        )

    # ----------------------------------------------------------------- launch
    async def launch(
        self,
        application_id: str,
        *,
        launch_id: str | None = None,
        confirm: bool = False,
    ) -> ProcessInstance:
        with self.database.session() as session:
            application = session.get(Application, application_id)
            if application is None:
                raise NotFound("Application not found")
            if not application.enabled or application.archived:
                raise CapabilityUnavailable("Application is disabled or archived")
            if application.control_policy.get("allow_launch") is False:
                raise CapabilityUnavailable("Launching is disabled by this application's control policy")
            definition = self._choose_definition(session, application, launch_id)
            if application.control_policy.get("confirmation_required") and not confirm:
                raise Conflict("This application requires explicit confirmation")
            if definition.launch_type not in {"command", "server"}:
                raise CapabilityUnavailable(
                    f"Launch type '{definition.launch_type}' is not a managed process",
                    detail="Use the URL or repository action instead.",
                )
            active = self.active_process(session, application_id)
            if active:
                raise Conflict(
                    "This application already has a managed process",
                    detail=f"Process {active.id} is running with PID {active.pid}.",
                )
            if self.running_count(session) >= self._max_managed():
                raise Conflict("Managed process limit reached", detail="Stop a process or raise the limit in Settings.")
            working_directory = (
                definition.working_directory
                or application.working_directory
                or application.repository_path
            )
            if not working_directory:
                raise LaunchProblem("No working directory is configured")
            try:
                working_directory = require_existing_directory(
                    working_directory, field="working directory"
                )
            except ValidationProblem as exc:
                self._record_failure(
                    session,
                    application,
                    definition,
                    exc.message,
                    working_directory,
                    definition.executable,
                )
                raise LaunchProblem(exc.message) from exc
            executable_setting = definition.executable
            if not executable_setting:
                self._record_failure(
                    session,
                    application,
                    definition,
                    "No executable is configured for this launch definition",
                    working_directory,
                    None,
                )
                raise LaunchProblem("No executable is configured for this launch definition")
            executable = resolve_executable(executable_setting)
            if not executable:
                message = f"Executable not found: {executable_setting}"
                self._record_failure(
                    session, application, definition, message, working_directory, executable_setting
                )
                raise LaunchProblem(
                    message,
                    detail="Check the executable name or path. Mission Control does not invoke a shell to resolve it.",
                )
            if definition.expected_port:
                if port_is_open("127.0.0.1", definition.expected_port):
                    raise Conflict(
                        f"Port {definition.expected_port} is already in use",
                        detail=(
                            "Mission Control will not claim or terminate the existing listener. "
                            "Use its health/URL action to inspect it instead."
                        ),
                    )
            arguments = list(definition.arguments or [])
            process_id = f"proc-{uuid.uuid4().hex[:16]}"
            log_path = self.settings.log_dir / f"{process_id}.log"
            command_preview = _command_preview(executable, arguments)
            env = build_environment(list(definition.env_names or []))
            started_at = now_iso()
            header = (
                f"Mission Control managed process {process_id}\n"
                f"Application: {application.name} ({application.id})\n"
                f"Command: {command_preview}\n"
                f"Working directory: {working_directory}\n"
                f"Started: {started_at}\n"
                "Environment: allowlisted Windows variables plus explicitly named variables; values omitted.\n"
                "---\n"
            ).encode("utf-8", "replace")
            try:
                with open(log_path, "ab", buffering=0) as log_handle:
                    log_handle.write(header)
                    process = subprocess.Popen(
                        [executable, *arguments],
                        cwd=working_directory,
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        shell=False,
                        close_fds=True,
                        creationflags=WINDOWS_FLAGS,
                        start_new_session=os.name != "nt",
                    )
            except (OSError, ValueError) as exc:
                message = f"Could not start process: {exc}"
                self._record_failure(
                    session,
                    application,
                    definition,
                    message,
                    working_directory,
                    executable,
                    log_path,
                    command_preview,
                )
                raise LaunchProblem(message) from exc
            try:
                create_time = psutil.Process(process.pid).create_time()
            except (psutil.Error, OSError):
                create_time = None
            record = ProcessInstance(
                id=process_id,
                application_id=application.id,
                launch_definition_id=definition.id,
                pid=process.pid,
                create_time=create_time,
                status="running",
                started_at=started_at,
                log_path=str(log_path),
                working_directory=working_directory,
                command_preview=command_preview,
                owned=True,
                reattached=False,
            )
            session.add(record)
            application.last_launch_success_at = started_at
            application.updated_at = now_iso()
            record_activity(
                session,
                event_type="application_launch",
                title=f"Launched {application.name}",
                detail=command_preview,
                application_id=application.id,
                process_id=record.id,
                source="mission-control",
                provenance="verified_observation",
                metadata={"pid": process.pid, "working_directory": working_directory},
            )
            session.flush()
            session.expunge(record)
        self._live[process_id] = process
        task = asyncio.create_task(
            self._watch(process_id, process, application_id, log_path),
            name=f"mission-control-watch-{process_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    def _record_failure(
        self,
        session: Session,
        application: Application,
        definition: LaunchDefinition,
        message: str,
        working_directory: str | None,
        executable: str | None,
        log_path: Path | None = None,
        command_preview: str | None = None,
    ) -> ProcessInstance:
        timestamp = now_iso()
        application.last_launch_failure_at = timestamp
        application.last_failure_detail = redact_text(message)[:2000]
        application.updated_at = timestamp
        record = ProcessInstance(
            id=f"proc-{uuid.uuid4().hex[:16]}",
            application_id=application.id,
            launch_definition_id=definition.id,
            pid=None,
            status="failed",
            started_at=timestamp,
            ended_at=timestamp,
            exit_code=None,
            log_path=str(log_path) if log_path else None,
            working_directory=working_directory,
            command_preview=command_preview,
            owned=True,
            error=redact_text(message)[:2000],
        )
        session.add(record)
        record_activity(
            session,
            event_type="application_launch_failed",
            title=f"Failed to launch {application.name}",
            detail=redact_text(message)[:2000],
            application_id=application.id,
            process_id=record.id,
            source="mission-control",
            provenance="verified_observation",
        )
        session.flush()
        # This path raises immediately afterwards; commit so diagnostics
        # survive the caller's rollback.
        session.commit()
        return record

    async def _watch(
        self,
        process_id: str,
        process: subprocess.Popen[bytes],
        application_id: str,
        log_path: Path,
    ) -> None:
        # Poll instead of using a blocking wait thread. Cancelling this task at
        # shutdown does not terminate the detached child.
        while process.poll() is None:
            await asyncio.sleep(0.4)
        exit_code = process.returncode if process.returncode is not None else -1
        stopped = process_id in self._stopping
        timestamp = now_iso()
        try:
            with self.database.session() as session:
                record = session.get(ProcessInstance, process_id)
                if record and record.status in {"running", "starting"}:
                    if stopped:
                        record.status = "stopped"
                    else:
                        record.status = "exited" if exit_code == 0 else "failed"
                    record.exit_code = exit_code
                    record.ended_at = timestamp
                    if exit_code not in (0, None) and not stopped:
                        record.error = f"Process exited with code {exit_code}"
                    application = session.get(Application, application_id)
                    if application and exit_code not in (0, None) and not stopped:
                        application.last_launch_failure_at = timestamp
                        application.last_failure_detail = f"Process exited with code {exit_code}"
                        application.updated_at = timestamp
                        record_activity(
                            session,
                            event_type="application_launch_failed",
                            title=f"{application.name} exited with code {exit_code}",
                            detail="Inspect the process log for the failure.",
                            application_id=application_id,
                            process_id=process_id,
                            source="mission-control",
                            provenance="verified_observation",
                        )
                    elif application:
                        record_activity(
                            session,
                            event_type="application_stopped",
                            title=f"{application.name} stopped",
                            detail=(
                                "Stopped by Mission Control."
                                if stopped
                                else f"Process exited with code {exit_code}."
                            ),
                            application_id=application_id,
                            process_id=process_id,
                            source="mission-control",
                            provenance="verified_observation",
                        )
        except Exception:  # pragma: no cover - never crash the event loop
            logger.exception("Could not record exit for process %s", process_id)
        finally:
            self._live.pop(process_id, None)
            self._stopping.discard(process_id)
            try:
                self._redact_log_file(log_path)
            except Exception:  # pragma: no cover - defensive
                logger.warning("Could not redact log file %s", log_path)

    @staticmethod
    def _redact_log_file(path: Path) -> None:
        if not path.exists() or path.stat().st_size > 5_000_000:
            return
        raw = path.read_bytes()
        text = redact_text(raw.decode("utf-8", "replace"))
        if text != raw.decode("utf-8", "replace"):
            path.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------- stop
    async def stop(self, process_id: str) -> ProcessInstance:
        with self.database.session() as session:
            record = session.get(ProcessInstance, process_id)
            if record is None:
                raise NotFound("Process not found")
            if record.status != "running":
                raise Conflict(f"Process is not running (status: {record.status})")
            if not record.owned:
                raise CapabilityUnavailable("Mission Control does not own this process")
            if not record.pid:
                raise Conflict("Process has no recorded PID")
            if not _process_identity_matches(record.pid, record.create_time):
                record.status = "lost"
                record.ended_at = now_iso()
                record.error = "Process identity no longer matches; refusing to terminate"
                session.flush()
                raise Conflict(record.error)
            self._stopping.add(process_id)
            definition = (
                session.get(LaunchDefinition, record.launch_definition_id)
                if record.launch_definition_id
                else None
            )
            grace = 15.0 if definition and definition.shutdown_behavior == "wait" else 5.0
            ok, message = await asyncio.to_thread(
                _terminate_tree, record.pid, record.create_time, grace
            )
            if not ok:
                self._stopping.discard(process_id)
                raise Conflict(message)
            record.status = "stopped"
            record.ended_at = now_iso()
            record.error = None
            record_activity(
                session,
                event_type="application_stopped",
                title=f"Stopped {record.application_id}",
                detail=message,
                application_id=record.application_id,
                process_id=record.id,
                source="mission-control",
                provenance="verified_observation",
            )
            session.flush()
            session.expunge(record)
        self._live.pop(process_id, None)
        self._stopping.discard(process_id)
        return record

    async def stop_application(self, application_id: str) -> ProcessInstance:
        with self.database.session() as session:
            record = self.active_process(session, application_id)
            if record is None:
                raise Conflict("No Mission Control-owned process is running for this application")
            process_id = record.id
        return await self.stop(process_id)

    async def restart(self, application_id: str, *, launch_id: str | None = None, confirm: bool = False) -> ProcessInstance:
        with self.database.session() as session:
            active = self.active_process(session, application_id)
        if active:
            await self.stop(active.id)
            await asyncio.sleep(0.2)
        return await self.launch(application_id, launch_id=launch_id, confirm=confirm)

    # ------------------------------------------------------------------ health
    async def check_health(
        self,
        application_id: str,
        *,
        definition: LaunchDefinition | None = None,
        timeout: float = 2.0,
    ) -> HealthObservation:
        with self.database.session() as session:
            application = session.get(Application, application_id)
            if application is None:
                raise NotFound("Application not found")
            if definition is None:
                definition = session.scalar(
                    select(LaunchDefinition)
                    .where(
                        LaunchDefinition.application_id == application_id,
                        LaunchDefinition.health_type != "none",
                    )
                    .order_by(desc(LaunchDefinition.is_primary), LaunchDefinition.id)
                )
            result = await probe(definition, timeout=timeout)
            previous = session.scalar(
                select(HealthObservation)
                .where(HealthObservation.application_id == application_id)
                .order_by(desc(HealthObservation.observed_at))
            )
            observation = HealthObservation(
                application_id=application_id,
                process_instance_id=None,
                state=result.state,
                detail=result.detail,
                source=result.source,
                observed_at=now_iso(),
                stale_after_seconds=60,
            )
            session.add(observation)
            if previous is None or previous.state != result.state:
                record_activity(
                    session,
                    event_type="application_health",
                    title=f"{application.name}: {result.state}",
                    detail=result.detail,
                    application_id=application_id,
                    source=definition.health_url if definition else "mission-control",
                    provenance="verified_observation",
                )
            session.flush()
            session.expunge(observation)
            return observation

    def start_monitor(self) -> None:
        if not self.settings.start_monitor or self._monitor_task:
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop(), name="mission-control-health-monitor")

    async def _monitor_loop(self) -> None:
        while not self._shutting_down:
            interval = 30
            try:
                with self.database.session() as session:
                    setting = session.get(Setting, "processes")
                    if setting and isinstance(setting.value, dict):
                        interval = max(10, int(setting.value.get("health_check_interval_seconds", 30)))
                    applications = session.scalars(
                        select(Application.id)
                        .join(LaunchDefinition, LaunchDefinition.application_id == Application.id)
                        .where(
                            Application.enabled.is_(True),
                            Application.archived.is_(False),
                            LaunchDefinition.enabled.is_(True),
                            LaunchDefinition.health_type != "none",
                        )
                        .distinct()
                    ).all()
                for application_id in applications:
                    if self._shutting_down:
                        break
                    try:
                        await self.check_health(application_id, timeout=2.0)
                    except Exception:
                        logger.warning("Health check failed for %s", application_id, exc_info=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Health monitor iteration failed")
            await asyncio.sleep(interval)

    async def shutdown(self) -> None:
        self._shutting_down = True
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except (asyncio.CancelledError, Exception):
                pass
        # Managed processes are intentionally left running so that a Mission
        # Control restart can reattach to them. The UI exposes Stop explicitly.

    # ------------------------------------------------------------------- logs
    def read_log(self, process_id: str, lines: int = 200) -> dict[str, Any]:
        with self.database.session() as session:
            record = session.get(ProcessInstance, process_id)
            if record is None:
                raise NotFound("Process not found")
            log_path_value = record.log_path
        if not log_path_value:
            return {"process_id": process_id, "lines": [], "truncated": False, "path": None}
        path = Path(log_path_value)
        if not is_within(path, self.settings.log_dir) or not path.exists():
            raise NotFound("Log file is unavailable")
        max_bytes = 300_000
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            raw = handle.read()
        text = redact_text(raw.decode("utf-8", "replace"))
        all_lines = text.splitlines()
        requested = max(1, min(lines, 2000))
        selected = all_lines[-requested:]
        return {
            "process_id": process_id,
            "lines": selected,
            "truncated": size > len(raw),
            "path": str(path),
        }

    async def reconcile_startup(self) -> None:
        with self.database.session() as session:
            self.reconcile_live(session)
        for path in self.settings.log_dir.glob("proc-*.log"):
            try:
                self._redact_log_file(path)
            except Exception:  # pragma: no cover
                pass
