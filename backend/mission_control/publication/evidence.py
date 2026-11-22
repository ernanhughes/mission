"""Evidence contract for the Publishing workbench (MC-PUBLISH-01).

Mission Control aggregates publication-readiness evidence from existing
systems (Writer, proof tooling, Bookbuilder, Hugo). It never re-implements
their validation logic and never invents verdicts.

Result vocabulary (evidence outcome only)::

    passed / failed / pending / unavailable / unknown

``unknown`` means no evidence was supplied. Missing evidence is never a
failure or a pass.

Freshness is orthogonal to the result. A previously passing check may be
``stale`` after the manuscript changed; freshness never rewrites the
source-native verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EvidenceResult = Literal["passed", "failed", "pending", "unavailable", "unknown"]
EvidenceFreshness = Literal["current", "stale", "unknown"]

VALID_RESULTS: frozenset[str] = frozenset(
    {"passed", "failed", "pending", "unavailable", "unknown"}
)
VALID_FRESHNESS: frozenset[str] = frozenset({"current", "stale", "unknown"})


@dataclass(slots=True)
class EvidenceItem:
    book_id: str
    evidence_type: str
    source_system: str
    source_reference: str = ""
    source_revision: str = ""
    observed_at: str = ""
    executed_at: str = ""
    result: EvidenceResult = "unknown"
    freshness: EvidenceFreshness = "unknown"
    diagnostics: str = ""
    available_actions: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result not in VALID_RESULTS:
            raise ValueError(f"Invalid evidence result: {self.result!r}")
        if self.freshness not in VALID_FRESHNESS:
            raise ValueError(f"Invalid evidence freshness: {self.freshness!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "evidence_type": self.evidence_type,
            "source_system": self.source_system,
            "source_reference": self.source_reference,
            "source_revision": self.source_revision,
            "observed_at": self.observed_at,
            "executed_at": self.executed_at,
            "result": self.result,
            "freshness": self.freshness,
            "diagnostics": self.diagnostics,
            "available_actions": list(self.available_actions),
            "detail": dict(self.detail),
        }


def unknown_evidence(
    book_id: str,
    evidence_type: str,
    source_system: str,
    diagnostics: str = "",
    available_actions: list[str] | None = None,
) -> EvidenceItem:
    """Explicit unknown: no evidence supplied, never a pass or fail."""
    return EvidenceItem(
        book_id=book_id,
        evidence_type=evidence_type,
        source_system=source_system,
        result="unknown",
        freshness="unknown",
        diagnostics=diagnostics or "No evidence supplied by the owning system.",
        available_actions=list(available_actions or []),
    )
