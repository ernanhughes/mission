"""Adapter contracts.

Adapters only read. They return observations with source attribution; the
adapter service is responsible for persistence and deduplication.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AdapterTarget:
    name: str
    application_id: str | None = None
    project_id: str | None = None
    repository_paths: list[tuple[str, str]] = field(default_factory=list)
    documentation_paths: list[str] = field(default_factory=list)
    related_project_ids: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

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
class AdapterResult:
    available: bool
    detail: str
    capabilities: list[str] = field(default_factory=list)
    error: str | None = None
    observations: list[Observation] = field(default_factory=list)
    recommendations: list[RecommendationSeed] = field(default_factory=list)


class Adapter(ABC):
    name: str
    capabilities: list[str]

    @abstractmethod
    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        raise NotImplementedError
