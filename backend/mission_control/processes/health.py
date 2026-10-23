"""Bounded health probes.

A responding endpoint is evidence of availability, not proof that a particular
configured application owns the listener. Ownership is tracked separately by
the process manager.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from mission_control.models import LaunchDefinition


@dataclass(slots=True)
class ProbeResult:
    state: str
    detail: str
    source: str


async def probe(definition: LaunchDefinition | None, *, timeout: float = 2.0) -> ProbeResult:
    if definition is None or definition.health_type == "none":
        return ProbeResult("not_configured", "No health check is configured", "configuration")
    if definition.health_type == "http":
        if not definition.health_url:
            return ProbeResult("misconfigured", "HTTP health check has no URL", "configuration")
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=False, trust_env=False
            ) as client:
                response = await client.get(definition.health_url)
            if 200 <= response.status_code < 400:
                return ProbeResult(
                    "healthy", f"HTTP {response.status_code} from {definition.health_url}", "health_check"
                )
            return ProbeResult(
                "unhealthy",
                f"HTTP {response.status_code} from {definition.health_url}",
                "health_check",
            )
        except httpx.TimeoutException:
            return ProbeResult(
                "unavailable", f"Health check timed out after {timeout:g}s", "health_check"
            )
        except httpx.HTTPError as exc:
            return ProbeResult("unavailable", f"Health check failed: {exc.__class__.__name__}", "health_check")
    if definition.health_type == "tcp":
        port = definition.expected_port
        host = "127.0.0.1"
        if definition.health_url:
            parsed = urlparse(definition.health_url)
            host = parsed.hostname or host
            port = parsed.port or port
        if not port:
            return ProbeResult("misconfigured", "TCP health check has no port", "configuration")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port)), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return ProbeResult("healthy", f"TCP connection succeeded to {host}:{port}", "health_check")
        except (OSError, asyncio.TimeoutError):
            return ProbeResult("unavailable", f"No TCP listener at {host}:{port}", "health_check")
    if definition.health_type == "process":
        return ProbeResult(
            "process_only",
            "This definition relies on managed process state; no endpoint probe is configured",
            "configuration",
        )
    return ProbeResult("misconfigured", f"Unknown health type: {definition.health_type}", "configuration")


def port_is_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
