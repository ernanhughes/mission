"""Worker HTTP readiness adapter (MC-INSPECT-04 A).

Read-only GETs only: /health, /v1/models/availability, /v1/models/usage,
/v1/models/preflight. Never POSTs /v1/models/probe. No work is submitted
and no model spend can occur through this adapter.
"""

from __future__ import annotations

import httpx

from mission_control.adapters.base import Adapter, AdapterResult, AdapterTarget, Observation


class WorkerAdapter(Adapter):
    name = "worker"
    capabilities = ["health", "availability", "model_readiness", "usage"]

    async def _get_json(
        self, client: httpx.AsyncClient, base_url: str, path: str
    ) -> tuple[dict | list | None, str | None]:
        try:
            response = await client.get(f"{base_url}{path}")
        except httpx.TimeoutException:
            return None, "timeout"
        except httpx.HTTPError as exc:
            return None, exc.__class__.__name__
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        try:
            payload = response.json()
        except ValueError:
            return None, "invalid JSON"
        return payload, None

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
            observations = [
                Observation(
                    title=f"Worker health: {status}",
                    detail=detail,
                    external_id=f"worker-health-{status}-{version}",
                    evidence_ref=f"{base_url}/health",
                    provenance="verified_observation",
                    metadata={"status": status, "version": version},
                )
            ]
            # Passive, cached readiness: availability/usage/preflight are GET-only
            # and never trigger POST /v1/models/probe.
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                avail_doc, avail_error = await self._get_json(client, base_url, "/v1/models/availability")
                usage_doc, usage_error = await self._get_json(client, base_url, "/v1/models/usage")
                preflight_doc, _preflight_error = await self._get_json(client, base_url, "/v1/models/preflight")
            if isinstance(avail_doc, dict):
                models = avail_doc.get("models") if isinstance(avail_doc.get("models"), list) else []
                observations.append(
                    Observation(
                        title=f"Worker cached availability: {len(models)} models",
                        detail=(
                            "Cached availability only; it does not guarantee a future "
                            f"inference will succeed. Warnings: {'; '.join(map(str, avail_doc.get('warnings') or [])) or 'none'}."
                            + (f" Error: {avail_error}." if avail_error else "")
                        ),
                        external_id=f"worker-availability-{len(models)}",
                        evidence_ref=f"{base_url}/v1/models/availability",
                        provenance="verified_observation",
                        metadata={"count": len(models), "probing": bool(avail_doc.get("probing"))},
                    )
                )
            else:
                observations.append(
                    Observation(
                        title="Worker availability unknown",
                        detail=f"Availability unavailable ({avail_error or 'no payload'}); unknown, not zero.",
                        external_id="worker-availability-unknown",
                        evidence_ref=f"{base_url}/v1/models/availability",
                        provenance="external_claim",
                        metadata={},
                    )
                )
            if isinstance(usage_doc, dict):
                billed = usage_doc.get("billed") if isinstance(usage_doc.get("billed"), dict) else {}
                observations.append(
                    Observation(
                        title="Worker model usage observed",
                        detail=(
                            f"Scope {usage_doc.get('scope')}; outcomes {usage_doc.get('outcomes')}. "
                            f"Billed unknown calls: {billed.get('unknown_calls') if isinstance(billed, dict) else 'unknown'} "
                            "(unknown remains unknown). Schema "
                            f"{usage_doc.get('schema_version')}."
                        ),
                        external_id="worker-usage-observed",
                        evidence_ref=f"{base_url}/v1/models/usage",
                        provenance="verified_observation",
                        metadata={
                            "outcomes": usage_doc.get("outcomes") or {},
                            "billed": billed,
                            "estimated": usage_doc.get("estimated") or {},
                        },
                    )
                )
            else:
                observations.append(
                    Observation(
                        title="Worker usage unknown",
                        detail=f"Usage unavailable ({usage_error or 'no payload'}); unknown, not zero.",
                        external_id="worker-usage-unknown",
                        evidence_ref=f"{base_url}/v1/models/usage",
                        provenance="external_claim",
                        metadata={},
                    )
                )
            if isinstance(preflight_doc, dict):
                observations.append(
                    Observation(
                        title="Worker preflight observed",
                        detail="Passive preflight snapshot; policy blocks are advisory.",
                        external_id="worker-preflight-observed",
                        evidence_ref=f"{base_url}/v1/models/preflight",
                        provenance="verified_observation",
                        metadata={},
                    )
                )
            return AdapterResult(
                available=True,
                detail=detail,
                capabilities=self.capabilities,
                observations=observations,
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
