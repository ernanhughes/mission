"""Bounded execution of configured, read-only or reviewed local tools."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from mission_control.core.logging import redact_text
from mission_control.core.paths import resolve_executable

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


@dataclass(slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    executable: str


def _environment(env_names: list[str]) -> dict[str, str]:
    env = {key: os.environ[key] for key in _ENV_ALLOWLIST if key in os.environ}
    for name in env_names:
        if name in os.environ:
            env[name] = os.environ[name]
    env["MISSION_CONTROL_INTEGRATION"] = "1"
    # Captured output must not depend on the Windows console code page.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _run(
    executable: str,
    arguments: list[str],
    working_directory: str,
    env_names: list[str],
    timeout: float,
) -> CommandResult:
    started = time.monotonic()
    completed = subprocess.run(
        [executable, *arguments],
        cwd=working_directory,
        env=_environment(env_names),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
        check=False,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    return CommandResult(
        exit_code=completed.returncode,
        stdout=redact_text(completed.stdout[-5_000_000:]),
        stderr=redact_text(completed.stderr[-20_000:]),
        duration_seconds=round(time.monotonic() - started, 3),
        executable=executable,
    )


async def run_tool(
    executable_setting: str,
    arguments: list[str],
    *,
    working_directory: str,
    env_names: list[str] | None = None,
    timeout_seconds: float = 60.0,
) -> CommandResult:
    executable = resolve_executable(executable_setting)
    if not executable:
        raise FileNotFoundError(f"Configured integration executable was not found: {executable_setting}")
    if Path(executable).suffix.casefold() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("Integration commands must use a native executable, not a shell script")
    cwd = Path(working_directory)
    if not cwd.is_dir():
        raise ValueError(f"Integration working directory does not exist: {working_directory}")
    if any("\x00" in item or "\n" in item or "\r" in item for item in arguments):
        raise ValueError("Integration arguments contain control characters")
    return await asyncio.wait_for(
        asyncio.to_thread(
            _run,
            executable,
            arguments,
            str(cwd),
            list(env_names or []),
            float(max(1.0, min(timeout_seconds, 300.0))),
        ),
        timeout=timeout_seconds + 2,
    )
