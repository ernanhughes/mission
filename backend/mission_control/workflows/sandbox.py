"""Resource-bounded execution for generated code.

Generated experiment code is never executed directly by Mission Control. It runs
in a Docker container with no network, a read-only repository mount, a read-only
root filesystem, a temporary writable /tmp, dropped capabilities and explicit
CPU/memory/PID/time limits.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class SandboxUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    backend: str
    image: str
    limits: dict[str, object] = field(default_factory=dict)
    timed_out: bool = False


class SandboxRunner(Protocol):
    def run(
        self, repository: Path, command: list[str], *, timeout_seconds: float
    ) -> SandboxResult:
        ...

    def describe(self) -> dict[str, object]:
        ...


class DockerSandboxRunner:
    def __init__(
        self,
        *,
        image: str | None = None,
        memory: str = "512m",
        cpus: str = "0.5",
        pids_limit: int = 64,
        tmpfs_size: str = "64m",
        user: str = "65534:65534",
        docker: str = "docker",
    ) -> None:
        self.image = image or os.environ.get(
            "MC11_SANDBOX_IMAGE", "mission-control/sandbox-python:3.13"
        )
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit
        self.tmpfs_size = tmpfs_size
        self.user = user
        self.docker = docker
        self._verified: bool | None = None
        self._version: str | None = None

    def _docker(self, *args: str, timeout: float = 20) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.docker, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )

    def availability(self) -> dict[str, object]:
        if self._verified is True:
            return {
                "available": True,
                "backend": "docker",
                "image": self.image,
                "version": self._version,
            }
        try:
            version = self._docker("version", "--format", "{{.Server.Version}}", timeout=10)
            if version.returncode != 0:
                raise SandboxUnavailable(
                    f"Docker daemon unavailable: {(version.stderr or version.stdout).strip()[:500]}"
                )
            inspect = self._docker("image", "inspect", self.image, timeout=10)
            if inspect.returncode != 0:
                raise SandboxUnavailable(
                    f"Sandbox image {self.image!r} is missing. Build it with docker/sandbox/Dockerfile."
                )
            self._version = version.stdout.strip()
            self._verified = True
            return {
                "available": True,
                "backend": "docker",
                "image": self.image,
                "version": self._version,
            }
        except (OSError, subprocess.SubprocessError) as exc:
            raise SandboxUnavailable(f"Docker sandbox unavailable: {exc}") from exc

    def describe(self) -> dict[str, object]:
        return {
            "backend": "docker",
            "image": self.image,
            "network": "none",
            "repository_mount": "read-only",
            "root_filesystem": "read-only",
            "tmpfs": self.tmpfs_size,
            "memory": self.memory,
            "cpus": self.cpus,
            "pids_limit": self.pids_limit,
            "user": self.user,
            "capabilities": "dropped",
        }

    def run(
        self, repository: Path, command: list[str], *, timeout_seconds: float
    ) -> SandboxResult:
        self.availability()
        repository = repository.resolve()
        if not repository.is_dir():
            raise SandboxUnavailable(f"Sandbox repository not found: {repository}")
        name = f"mc11-sandbox-{uuid.uuid4().hex[:16]}"
        arguments = [
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--memory",
            self.memory,
            "--memory-swap",
            self.memory,
            "--cpus",
            self.cpus,
            "--pids-limit",
            str(self.pids_limit),
            "--read-only",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,size={self.tmpfs_size}",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            self.user,
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONUNBUFFERED=1",
            "-e",
            "PYTHONPATH=/work",
            "-e",
            "TMPDIR=/tmp",
            "-v",
            f"{repository}:/work:ro",
            "-w",
            "/work",
            self.image,
            *command,
        ]
        started = time.monotonic()
        try:
            completed = self._docker(*arguments, timeout=max(1.0, timeout_seconds))
        except subprocess.TimeoutExpired as exc:
            self._docker("rm", "-f", name, timeout=10)
            return SandboxResult(
                exit_code=124,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr="Sandbox execution timed out",
                duration_seconds=round(time.monotonic() - started, 3),
                backend="docker",
                image=self.image,
                limits=self.describe(),
                timed_out=True,
            )
        return SandboxResult(
            exit_code=completed.returncode,
            stdout=(completed.stdout or "")[-20000:],
            stderr=(completed.stderr or "")[-10000:],
            duration_seconds=round(time.monotonic() - started, 3),
            backend="docker",
            image=self.image,
            limits=self.describe(),
            timed_out=False,
        )


class DockerUnavailableSandbox:
    """Explicit refusal used when no verified sandbox is configured."""

    def run(self, repository: Path, command: list[str], *, timeout_seconds: float) -> SandboxResult:
        raise SandboxUnavailable(
            "Generated-code execution is disabled because no verified Docker sandbox is available."
        )

    def describe(self) -> dict[str, object]:
        return {"backend": "unavailable", "generated_code_execution": "disabled"}
