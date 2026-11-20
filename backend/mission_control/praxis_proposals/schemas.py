"""API schemas for the Praxis proposal contract (MC-PRAXIS-07)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PraxisProposalStep(BaseModel):
    capability_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class PraxisProposalGoal(BaseModel):
    goal_id: str = ""
    external_id: str = ""
    title: str = ""
    description: str = ""
    desired_outcome: str = ""
    state: str = ""
    source: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    explicit_acceptance: list[str] = Field(default_factory=list)
    inferred_constraints: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    stale: bool | None = None


class PraxisProposalPayload(BaseModel):
    id: str
    version: str
    status: str = "validated"  # informational; Mission Control revalidates
    goal: PraxisProposalGoal
    steps: list[PraxisProposalStep]
    capability_versions: dict[str, str] = Field(default_factory=dict)
    pi_model: str = ""
    protocol: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    expected_benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    estimated_cost: dict[str, Any] = Field(default_factory=dict)
    observed_composition_cost_usd: float | None = None
    correlation: dict[str, Any] = Field(default_factory=dict)


class PraxisAcceptanceCriterion(BaseModel):
    id: str
    statement: str
    source: str  # must identify a human decision point, e.g. "human:ernan"


class PraxisProposalImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    proposal: PraxisProposalPayload
    acceptance_criteria: list[PraxisAcceptanceCriterion]
    acceptance_provenance: str
    ownership: dict[str, str] | None = None


class PraxisProposalWithdraw(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str
    reason: str
    confirm: bool = False


class PraxisProposalApprove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str
    confirm: bool = False
    note: str = ""


class PraxisProposalReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rejected_by: str
    reason: str
    confirm: bool = False


class PraxisProposalExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str
    confirm: bool = False


class PraxisProposalRead(BaseModel):
    proposal_key: str
    praxis_id: str
    version: str
    content_digest: str
    recipe_digest: str
    status: str
    correlation_id: str
    goal_id: str
    goal_source: str
    goal_title: str
    goal_provenance: str
    steps: list[dict[str, Any]]
    capability_versions: dict[str, Any]
    pi_model: str
    protocol: str
    evidence_refs: list[str]
    expected_benefits: list[str]
    assumptions: list[str]
    risks: list[str]
    estimated_cost: dict[str, Any]
    observed_composition_cost_usd: float | None
    acceptance_criteria: list[dict[str, Any]]
    acceptance_provenance: str
    validation: list[dict[str, Any]]
    preflight: list[dict[str, Any]]
    execution_config: dict[str, Any]
    ownership_kind: str
    owner: str
    withdrawn_at: str | None
    approved_by: str | None
    approved_at: str | None
    approval_digest: str | None
    rejected_by: str | None
    rejected_at: str | None
    rejection_reason: str | None
    execution_id: str | None
    execution_requested_at: str | None
    created_at: str
    updated_at: str


class PraxisProposalEvidence(BaseModel):
    """Correlated evidence: proposal identity plus authoritative execution."""

    proposal: PraxisProposalRead
    execution: dict[str, Any] | None
    correlation: dict[str, Any]
    evaluation_boundary: dict[str, Any]
