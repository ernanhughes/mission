"""Worker HTTP health adapter.

Only the documented health endpoint is called. No work is submitted and no
model spend can occur through this adapter.
"""

from __future__ import annotations

import httpx

from mission_control.adapters.base import Adapter, AdapterResult, AdapterTarget, Observation


class WorkerAdapter(Adapter):
    name = "worker"
    capabilities = ["health", "availability"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        base_url = str(target.config.get("base_url") or "http://127.0.0.1:7317").rstrip("/")
        timeout = float(target.config.get("timeout_seconds", 2))
        timeout = max(0.5, min(timeout, 10.0))
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                response = await client.get(f"{base_url}/health")
            if response.status_code != 200:
                return AdapterResult(
                    available=False,
                    detail=f"Worker health returned HTTP {response.status_code}; no status is inferred.",
                    capabilities=self.capabilities,
                )
            try:
                health = response.json()
            except ValueError:
                return AdapterResult(
                    available=False,
                    detail="Worker health response was not JSON; no status is inferred.",
                    capabilities=self.capabilities,
                    error="Invalid health payload",
                )
            if not isinstance(health, dict):
                return AdapterResult(
                    available=False,
                    detail="Worker health payload had an unexpected shape.",
                    capabilities=self.capabilities,
                    error="Invalid health payload",
                )
            status = str(health.get("status") or "unknown")
            version = str(health.get("version") or "unknown")
            listen = health.get("listen") or health.get("address") or "not stated"
            detail = f"Worker {status}, version {version}, listener {listen}."
            return AdapterResult(
                available=True,
                detail=detail,
                capabilities=self.capabilities,
                observations=[
                    Observation(
                        title=f"Worker health: {status}",
                        detail=detail,
                        external_id=f"worker-health-{status}-{version}",
                        evidence_ref=f"{base_url}/health",
                        provenance="verified_observation",
                        metadata={"status": status, "version": version},
                    )
                ],
            )
        except httpx.TimeoutException:
            return AdapterResult(
                available=False,
                detail=f"Worker health check timed out at {base_url}; Worker may not be running.",
                capabilities=self.capabilities,
            )
        except httpx.HTTPError as exc:
            return AdapterResult(
                available=False,
                detail=(
                    f"Worker is not reachable at {base_url}. No Worker status is claimed. "
                    f"({exc.__class__.__name__})"
                ),
                capabilities=self.capabilities,
            )
