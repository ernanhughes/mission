"""Work commercial opportunity adapter using Work's documented JSON CLI.

The CLI is read-only for the commands used here. Mission Control never writes a
Work decision or outcome to PostgreSQL in this release; user decisions are
stored locally with an explicit ``local_only`` synchronisation state.
"""

from __future__ import annotations

import json
from typing import Any

from mission_control.adapters.base import (
    ActionSpec,
    Adapter,
    AdapterResult,
    AdapterTarget,
    Observation,
    ResourceSeed,
)
from mission_control.integrations.runner import run_tool


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class WorkAdapter(Adapter):
    name = "work"
    capabilities = [
        "health",
        "list_resources",
        "get_resource",
        "search_resources",
        "list_actions",
        "list_events",
    ]
    actions = [
        ActionSpec(
            id="sync_decision",
            title="Synchronise a decision to Work",
            description=(
                "Work exposes `work decide`, but writing to its PostgreSQL state is a "
                "separate approval boundary. Mission Control records decisions locally "
                "until this action is explicitly enabled and verified."
            ),
            risk="local_state",
            capability="execute_action",
            approval_required=True,
            side_effect="local_state",
            enabled=False,
            unavailable_reason=(
                "Read-only Work integration. Local decisions are preserved and labelled "
                "local_only; no Work database write is performed."
            ),
        )
    ]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.repo_by_name("work") or target.primary_repository
        if repo is None:
            return AdapterResult(
                available=False,
                detail="Work repository is unavailable.",
                capabilities=self.capabilities,
                actions=self.actions,
            )
        executable = str(
            target.config.get("executable")
            or (repo / ".venv" / "Scripts" / "work.exe")
        )
        working_directory = str(target.config.get("working_directory") or repo)
        arguments = list(target.config.get("arguments") or ["opportunities", "--json"])
        env_names = list(target.config.get("env_names") or ["WORK_DATABASE_URL"])
        timeout = float(target.config.get("timeout_seconds", 90))
        try:
            result = await run_tool(
                executable,
                arguments,
                working_directory=working_directory,
                env_names=env_names,
                timeout_seconds=timeout,
            )
        except Exception as exc:
            return AdapterResult(
                available=False,
                detail="Work CLI could not be executed; no opportunity data was invented.",
                capabilities=self.capabilities,
                actions=self.actions,
                error=f"{exc.__class__.__name__}: {str(exc)[:400]}",
            )
        if result.exit_code != 0:
            return AdapterResult(
                available=False,
                detail="Work CLI returned a non-zero exit code; no opportunity data was imported.",
                capabilities=self.capabilities,
                actions=self.actions,
                error=(result.stderr or result.stdout or "No diagnostic output")[-1200:],
            )
        try:
            opportunities = json.loads(result.stdout)
            if not isinstance(opportunities, list):
                raise ValueError("Work JSON root is not a list")
        except (ValueError, json.JSONDecodeError) as exc:
            return AdapterResult(
                available=False,
                detail="Work CLI output was not the expected JSON list; no data was imported.",
                capabilities=self.capabilities,
                actions=self.actions,
                error=f"{exc.__class__.__name__}: {str(exc)[:400]}",
            )
        limit = max(1, min(int(target.config.get("limit", 300)), 500))
        resources = [self._resource(item) for item in opportunities[:limit] if isinstance(item, dict)]
        qualified = sum(
            1
            for resource in resources
            if bool((resource.data.get("qualification") or {}).get("qualified"))
        )
        detail = (
            f"Read {len(resources)} opportunities from Work's JSON CLI "
            f"({qualified} qualified by Work's recorded policy). "
            "Mission Control did not write to Work."
        )
        return AdapterResult(
            available=True,
            detail=detail,
            capabilities=self.capabilities,
            actions=self.actions,
            observations=[
                Observation(
                    title=f"Work opportunity snapshot: {len(resources)} records",
                    detail=detail,
                    external_id=f"work-opportunities-{len(resources)}-{qualified}",
                    evidence_ref="work:opportunities --json",
                    provenance="external_claim",
                    metadata={"count": len(resources), "qualified": qualified},
                )
            ],
            resources=resources,
        )

    def _resource(self, item: dict[str, Any]) -> ResourceSeed:
        opportunity_id = str(item.get("id") or "")
        observation = item.get("observation") or {}
        qualification = item.get("qualification") or {}
        raw = observation.get("raw") or {}
        title = str(observation.get("title") or "Untitled Work opportunity")[:400]
        state = str(item.get("state") or "UNKNOWN")
        qualified = bool(qualification.get("qualified"))
        buyer = str(observation.get("buyer") or raw.get("buyer_name") or "")
        qualification_state = "qualified" if qualified else "not qualified"
        amount = observation.get("amount")
        currency = observation.get("currency")
        location = str(
            raw.get("location")
            or raw.get("buyer_country")
            or raw.get("country")
            or ""
        )
        remote = raw.get("remote") if isinstance(raw.get("remote"), bool) else None
        evidence_urls = [
            value
            for value in _safe_list(observation.get("evidence_urls"))
            if isinstance(value, str)
        ]
        evidence = evidence_urls + [
            value
            for value in _safe_list(qualification.get("evidence"))
            if isinstance(value, str)
        ]
        payload = {
            "source_mode": "work-cli-json",
            "opportunity_id": opportunity_id,
            "state": state,
            "qualification_state": qualification_state,
            "track": observation.get("track"),
            "source": observation.get("source"),
            "source_url": observation.get("url"),
            "buyer": buyer,
            "location": location,
            "remote": remote,
            "availability": observation.get("availability"),
            "published_at": observation.get("published_at"),
            "collected_at": observation.get("collected_at"),
            "verified_at": observation.get("verified_at"),
            "expires_at": observation.get("expires_at"),
            "compensation": {
                "amount": amount,
                "currency": currency,
                "money_type": observation.get("money_type"),
                "basis": observation.get("compensation_basis"),
                "total_value": raw.get("total_value"),
                "total_value_currency": raw.get("total_value_currency"),
            },
            "qualification": qualification,
            "observation": {
                key: observation.get(key)
                for key in (
                    "summary",
                    "eligibility",
                    "eligibility_text",
                    "skills",
                    "money_type",
                    "demand_verified",
                    "payout_conditions",
                    "synthetic",
                )
            },
            "source_ref": "work:opportunities --json",
        }
        return ResourceSeed(
            resource_type="work_opportunity",
            external_id=opportunity_id,
            title=title,
            summary=str(
                qualification.get("next_action")
                or observation.get("summary")
                or "Work opportunity"
            )[:1400],
            state=f"{state} / {qualification_state}",
            evidence=evidence[:12],
            data=payload,
            source_version="work-cli-v1",
            source_timestamp=str(
                observation.get("collected_at") or observation.get("published_at") or ""
            )
            or None,
            stale_after_seconds=1800,
        )
