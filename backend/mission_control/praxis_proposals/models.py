"""SQLAlchemy model for imported Praxis proposals (MC-PRAXIS-07).

The row stores the frozen snapshot Mission Control validated, the human
approval that authorised exactly that snapshot (approval_digest), and the
authoritative execution id once Work runs it. Execution results are never
duplicated here; they stay in integration_executions and are joined by id.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from mission_control.models import Base
from mission_control.persistence.db import now_iso


class PraxisProposal(Base):
    __tablename__ = "praxis_proposals"

    proposal_key: Mapped[str] = mapped_column(String, primary_key=True)
    praxis_id: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    content_digest: Mapped[str] = mapped_column(String, nullable=False)
    recipe_digest: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="imported", nullable=False)
    correlation_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    goal_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    goal_source: Mapped[str] = mapped_column(String, default="", nullable=False)
    goal_title: Mapped[str] = mapped_column(String, default="", nullable=False)
    goal_provenance: Mapped[str] = mapped_column(Text, default="", nullable=False)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    capability_versions_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    pi_model: Mapped[str] = mapped_column(String, default="", nullable=False)
    protocol: Mapped[str] = mapped_column(String, default="", nullable=False)
    evidence_refs_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    expected_benefits_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    assumptions_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    risks_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    estimated_cost_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    observed_composition_cost_usd: Mapped[float | None] = mapped_column(Float)
    acceptance_criteria_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    acceptance_provenance: Mapped[str] = mapped_column(Text, default="", nullable=False)
    validation_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(String)
    approved_at: Mapped[str | None] = mapped_column(String)
    approval_digest: Mapped[str | None] = mapped_column(String)
    rejected_by: Mapped[str | None] = mapped_column(String)
    rejected_at: Mapped[str | None] = mapped_column(String)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    execution_id: Mapped[str | None] = mapped_column(String)
    execution_requested_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
