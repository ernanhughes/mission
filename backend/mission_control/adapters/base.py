"""Adapter contracts for the unified application interface.

The contract is deliberately small: adapters declare capabilities and actions,
return normalised resources with source attribution, and may execute only the
actions they register. Mission Control persists the read model and execution
lifecycle; the source application remains the authority.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ADAPTER_PROTOCOL_VERSION = "mc09.1"


@dataclass(slots=True)
class AdapterTarget:
    name: str
    application_id: str | None = None
    project_id: str | None = None
    repository_paths: list[tuple[str, str]] = field(default_factory=list)
    documentation_paths: list[str] = field(default_factory=list)
    related_project_ids: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    data_dir: str | None = None

    @property
    def primary_repository(self) -> Path | None:
        if not self.repository_paths:
            return None
        path = Path(self.repository_paths[0][0])
        return path if path.exists() else None

    def repo_by_name(self, name: str) -> Path | None:
        for path, _role in self.repository_paths:
            if Path(path).name.casefold() == name.casefold():
                return Path(path)
        return None


@dataclass(slots=True)
class Observation:
    title: str
    detail: str
    external_id: str
    evidence_ref: str | None = None
    provenance: str = "external_claim"
    occurred_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RecommendationSeed:
    title: str
    rationale: str
    evidence: list[str] = field(default_factory=list)
    external_id: str = ""
    project_id: str | None = None
    provenance: str = "derived_observation"
    source_ref: str | None = None


@dataclass(slots=True)
class ResourceSeed:
    resource_type: str
    external_id: str
    title: str
    summary: str = ""
    state: str = ""
    evidence: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    source_version: str | None = None
    source_timestamp: str | None = None
    stale_after_seconds: int = 900


@dataclass(slots=True)
class ActionSpec:
    id: str
    title: str
    description: str
    risk: str
    approval_required: bool = True
    capability: str = "execute_action"
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    unavailable_reason: str | None = None
    side_effect: str = "read_only"


@dataclass(slots=True)
class ActionContext:
    application_id: str
    data_dir: Path
    allowed_repository_paths: list[str] = field(default_factory=list)
    application_repository_path: str | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionResult:
    status: str = "succeeded"
    output: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    artifact_ref: str | None = None
    exit_code: int | None = None
    error: str | None = None


@dataclass(slots=True)
class AdapterResult:
    available: bool
    detail: str
    capabilities: list[str] = field(default_factory=list)
    error: str | None = None
    observations: list[Observation] = field(default_factory=list)
    recommendations: list[RecommendationSeed] = field(default_factory=list)
    resources: list[ResourceSeed] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)


class Adapter(ABC):
    name: str
    capabilities: list[str]
    protocol_version: str = ADAPTER_PROTOCOL_VERSION
    actions: list[ActionSpec] = []

    @abstractmethod
    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        raise NotImplementedError

    def validate_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> None:
        """Reject invalid action parameters before an execution is queued.

        Adapters that accept actions should override this. The same validation
        must still run at execution time because registrations can change.
        """

    async def execute_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> ActionResult:
        raise NotImplementedError(f"Action '{action_id}' is not supported by {self.name}")
