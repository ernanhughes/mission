"""WORK-OUTCOME-01 W3: validated extraction schemas (proposals, not truth).

Every model output is validated against these contracts before anything is
persisted. Unknown source ids, fabricated quotations, unsupported authorities
and oversized outputs are rejected with metadata-only error records.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Authority = Literal[
    "explicit_user", "accepted_proposal", "standing", "derived",
    "ai_decision", "suggested", "excluded", "deferred", "superseded",
    "ambiguous",
]
ExtractionMethod = Literal["deterministic", "model"]
SCHEMA_VERSION = "w3-extract-v1"
MAX_ITEMS = 50
MAX_TEXT_CHARS = 2000


class SourceRef(BaseModel):
    kind: str = Field(max_length=32)
    ref: str = Field(max_length=300)


class ObjectiveProposal(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    authority: Literal["explicit_user", "accepted_proposal", "inferred", "unknown"] = "inferred"
    sources: list[SourceRef] = Field(default_factory=list)

    @field_validator("sources")
    @classmethod
    def _non_empty(cls, v: list[SourceRef]) -> list[SourceRef]:
        if not v:
            raise ValueError("objective requires at least one source")
        return v


class RequirementProposal(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    authority: Authority = "ambiguous"
    mandatory: bool = True
    kind: Literal["functional", "constraint", "gate"] = "functional"
    sources: list[SourceRef] = Field(default_factory=list)

    @field_validator("sources")
    @classmethod
    def _non_empty(cls, v: list[SourceRef]) -> list[SourceRef]:
        if not v:
            raise ValueError("requirement requires at least one source")
        return v


class ClaimProposal(BaseModel):
    claimant: str = Field(max_length=120)
    text: str = Field(max_length=MAX_TEXT_CHARS)
    scope: str = Field(default="", max_length=500)
    source: SourceRef | None = None
    qualified: bool = False


class EvidenceLinkProposal(BaseModel):
    requirement_index: int | None = None
    claim_index: int | None = None
    evidence_kind: str = Field(max_length=64)
    evidence_ref: str = Field(max_length=500)


class TriageProposal(BaseModel):
    classification: str = Field(max_length=40)
    reason: str = Field(default="", max_length=500)


class ExtractionPacket(BaseModel):
    """One bounded model response for one episode or session."""

    episode_id: str | None = Field(default=None, max_length=160)
    session_id: str | None = Field(default=None, max_length=160)
    objectives: list[ObjectiveProposal] = Field(default_factory=list)
    requirements: list[RequirementProposal] = Field(default_factory=list)
    claims: list[ClaimProposal] = Field(default_factory=list)
    evidence_links: list[EvidenceLinkProposal] = Field(default_factory=list)
    triage: TriageProposal | None = None

    @field_validator("objectives", "requirements", "claims", "evidence_links")
    @classmethod
    def _bounded(cls, v: list[Any]) -> list[Any]:
        if len(v) > MAX_ITEMS:
            raise ValueError(f"too many items (>{MAX_ITEMS})")
        return v


VALID_TRIAGE = {
    "SUBSTANTIVE_NEW_WORK", "CONTINUATION_OF_EXISTING_WORK",
    "REVIEW_OR_CORRECTION", "RESEARCH_OR_INVESTIGATION", "DESIGN_OR_PLANNING",
    "TRIVIAL_INTERACTION", "DUPLICATE_OR_QUOTED_HISTORY", "NON_PROJECT_ACTIVITY",
    "INSUFFICIENT_EVIDENCE", "AMBIGUOUS",
}
VALID_AUTHORITIES = {
    "explicit_user", "accepted_proposal", "standing", "derived",
    "ai_decision", "suggested", "excluded", "deferred", "superseded",
    "ambiguous",
}

# Tool-call paraphrases: agent-internal file operations restated as user
# requirements (observed with small/weak models, W4 pilot). They are not
# user requirements; validation rejects them so they cannot enter the
# store as explicit_user obligations.
TOOL_PARAPHRASE_RES = [
    __import__("re").compile(r"\baccess file path\b", __import__("re").I),
    __import__("re").compile(r"^\s*(read|open|edit|write|create|delete|list)\s+(file|files|the file|a file)\b", __import__("re").I),
    __import__("re").compile(r"\bread the file\b", __import__("re").I),
]


def is_tool_paraphrase(text: str) -> bool:
    norm = " ".join((text or "").split())
    return any(rx.search(norm) for rx in TOOL_PARAPHRASE_RES)

# Instruction-echo phrases: outputs that restate the extraction instruction
# instead of extracting (observed with small local models, W3 pilot).
# Matched case-insensitively against normalized text.
VACUITY_PHRASES = (
    "extract work requirements",
    "extract requirements",
    "from the evidence packet",
    "evidence packet",
)


def is_vacuous(text: str) -> bool:
    norm = " ".join((text or "").lower().split())
    return any(p in norm for p in VACUITY_PHRASES)


EVAL_VACUITY_PHRASES = (
    "evaluate requirements against the provided evidence",
    "provided evidence",
    "a participant assertion is never verification",
    "never verification by itself",
    "copy exactly",
    "abstain with insufficient_evidence",
    "abstain with insufficient evidence",
)


def is_eval_vacuous(text: str) -> bool:
    norm = " ".join((text or "").lower().split())
    return any(p in norm for p in EVAL_VACUITY_PHRASES)
