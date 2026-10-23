"""Configured editor invocation used by application and project actions."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from mission_control.core.errors import CapabilityUnavailable
from mission_control.core.paths import resolve_executable, validate_arguments
from mission_control.models import Setting


def open_path_with_editor(session: Session, path: str) -> str:
    target = Path(path)
    if not target.exists():
        raise CapabilityUnavailable("The configured path does not exist")
    working_directory = target if target.is_dir() else target.parent
    setting = session.get(Setting, "editor")
    config = setting.value if setting and isinstance(setting.value, dict) else {}
    command = str(config.get("command") or "").strip()
    if not command:
        raise CapabilityUnavailable(
            "No editor is configured",
            detail="Set an editor command in Settings. Mission Control does not assume an editor path.",
        )
    executable = resolve_executable(command)
    if not executable:
        raise CapabilityUnavailable(
            f"Configured editor was not found: {command}",
            detail="Use a native editor executable (for example Code.exe) or a command available on PATH.",
        )
    if Path(executable).suffix.casefold() in {".bat", ".cmd", ".ps1"}:
        raise CapabilityUnavailable(
            "The configured editor resolves to a shell script",
            detail="Mission Control launches native executables directly. Set Code.exe rather than code.cmd.",
        )
    arguments = validate_arguments(list(config.get("arguments") or []))
    argv = [executable, *arguments]
    if bool(config.get("append_path", True)):
        argv.append(str(target))
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(
            argv,
            cwd=str(working_directory),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        raise CapabilityUnavailable(
            "The configured editor could not be started",
            detail=f"{exc.__class__.__name__}: {exc}",
        ) from exc
    return command
