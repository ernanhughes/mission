"""MC-PRAXIS-07: governed Praxis proposal import, approval, execution, evidence.

Mission Control remains authoritative: a proposal is inert data until an
identified human approves the exact immutable snapshot, and execution then goes
through the existing IntegrationService with the ActionSpec's own confirmation
requirement. Execution results are never copied into the proposal row.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.core.errors import (
    Conflict,
    NotFound,
    ValidationProblem,
)
from mission_control.integrations.service import (
    INTEGRATION_APPLICATIONS,
    IntegrationService,
    _validate_parameters,
)
from mission_control.models import Application, IntegrationExecution, IntegrationRecord
from mission_control.adapters.service import get_app_adapter
from mission_control.persistence.db import Database, now_iso
from mission_control.praxis_proposals.models import PraxisProposal
from mission_control.praxis_proposals.preflight import (
    capability_metadata,
    compute_preflight,
)
from mission_control.praxis_proposals.schemas import (
    PraxisProposalEvidence,
    PraxisProposalImport,
    PraxisProposalRead,
)

SCHEMA_VERSION = "mc-praxis-proposal-v1"

# Pilot scope: one execution-safe ActionSpec per proposal. Multi-step dataflow
# needs typed bindings, which do not exist yet (PRAXIS-06 finding).
MAX_EXECUTABLE_STEPS = 1

# A Pi agent, Praxis itself, or any automated system may not authorise work.
SELF_APPROVAL_DENYLIST = {
    "pi", "praxis", "agent", "agents", "model", "llm", "system", "auto",
    "automatic", "bot", "machine", "ai", "assistant", "orchestrator",
    "praxis-agent", "service", "worker",
}

_CAPABILITY_ID = re.compile(r"^([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)$")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _proposal_read(row: PraxisProposal) -> PraxisProposalRead:
    return PraxisProposalRead(
        proposal_key=row.proposal_key,
        praxis_id=row.praxis_id,
        version=row.version,
        content_digest=row.content_digest,
        recipe_digest=row.recipe_digest,
        status=row.status,
        correlation_id=row.correlation_id,
        goal_id=row.goal_id,
        goal_source=row.goal_source,
        goal_title=row.goal_title,
        goal_provenance=row.goal_provenance,
        steps=list(row.steps_json or []),
        capability_versions=dict(row.capability_versions_json or {}),
        pi_model=row.pi_model,
        protocol=row.protocol,
        evidence_refs=list(row.evidence_refs_json or []),
        expected_benefits=list(row.expected_benefits_json or []),
        assumptions=list(row.assumptions_json or []),
        risks=list(row.risks_json or []),
        estimated_cost=dict(row.estimated_cost_json or {}),
        observed_composition_cost_usd=row.observed_composition_cost_usd,
        acceptance_criteria=list(row.acceptance_criteria_json or []),
        acceptance_provenance=row.acceptance_provenance,
        validation=list(row.validation_json or []),
        preflight=list(row.preflight_json or []),
        execution_config=dict(row.execution_config_json or {}),
        ownership_kind=row.ownership_kind,
        owner=row.owner,
        withdrawn_at=row.withdrawn_at,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        approval_digest=row.approval_digest,
        rejected_by=row.rejected_by,
        rejected_at=row.rejected_at,
        rejection_reason=row.rejection_reason,
        execution_id=row.execution_id,
        execution_requested_at=row.execution_requested_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PraxisProposalService:
    def __init__(self, database: Database, integrations: IntegrationService) -> None:
        self.database = database
        self.integrations = integrations

    # ---------------------------------------------------------------- import
    def import_proposal(self, payload: PraxisProposalImport) -> PraxisProposalRead:
        if payload.schema_version != SCHEMA_VERSION:
            raise ValidationProblem(
                f"Unsupported proposal schema: {payload.schema_version!r}"
            )
        proposal = payload.proposal
        if not proposal.id or not proposal.version:
            raise ValidationProblem("Proposal id and version are required")
        key = f"{proposal.id}@{proposal.version}"
        content = proposal.model_dump()
        digest = canonical_digest(content)
        recipe_digest = canonical_digest(
            {"steps": [step.model_dump() for step in proposal.steps]}
        )

        with self.database.session() as session:
            existing = session.get(PraxisProposal, key)
            if existing is not None:
                if existing.content_digest != digest:
                    raise Conflict(
                        "Proposal version already imported with different content; "
                        "publish a new version instead of overwriting an approved plan"
                    )
                return self._read_with_execution(session, existing)

            validation = self._validate_import(session, payload, recipe_digest)
            valid = all(item["ok"] for item in validation)
            status = "awaiting_approval" if valid else "rejected"
            goal = proposal.goal
            ownership = payload.ownership or {}
            ownership_kind = str(ownership.get("kind") or "operator")
            if ownership_kind not in {"operator", "test"}:
                raise ValidationProblem(
                    "ownership.kind must be 'operator' or 'test'")
            row = PraxisProposal(
                proposal_key=key,
                praxis_id=proposal.id,
                version=proposal.version,
                content_digest=digest,
                recipe_digest=recipe_digest,
                status=status,
                correlation_id=f"mcprop-{uuid.uuid4().hex[:16]}",
                goal_id=goal.goal_id,
                goal_source=goal.source,
                goal_title=goal.title[:500],
                goal_provenance=json.dumps(goal.provenance, sort_keys=True),
                steps_json=[step.model_dump() for step in proposal.steps],
                capability_versions_json=dict(proposal.capability_versions),
                pi_model=proposal.pi_model,
                protocol=proposal.protocol,
                evidence_refs_json=list(proposal.evidence_refs),
                expected_benefits_json=list(proposal.expected_benefits),
                assumptions_json=list(proposal.assumptions),
                risks_json=list(proposal.risks),
                estimated_cost_json=dict(proposal.estimated_cost),
                observed_composition_cost_usd=proposal.observed_composition_cost_usd,
                acceptance_criteria_json=[
                    item.model_dump() for item in payload.acceptance_criteria
                ],
                acceptance_provenance=payload.acceptance_provenance,
                validation_json=validation,
                preflight_json=[],
                execution_config_json={},
                ownership_kind=ownership_kind,
                owner=str(ownership.get("owner") or ""),
                rejection_reason=None if valid else "Proposal failed validation",
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(row)
            session.flush()
            row.preflight_json = compute_preflight(session, row)
            session.flush()
            return self._read_with_execution(session, row)

    def _validate_import(
        self, session: Session, payload: PraxisProposalImport, recipe_digest: str
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        def check(name: str, ok: bool, detail: str = "") -> None:
            findings.append({"check": name, "ok": ok, "detail": detail[:500]})

        proposal = payload.proposal
        check("schema_version", payload.schema_version == SCHEMA_VERSION,
              payload.schema_version)
        check("client_status_not_trusted",
              proposal.status in {"validated", "advisory"},
              f"client claimed {proposal.status!r}; MC revalidates everything")
        check("single_executable_step",
              len(proposal.steps) == MAX_EXECUTABLE_STEPS,
              f"{len(proposal.steps)} step(s); pilot limit is "
              f"{MAX_EXECUTABLE_STEPS} (typed bindings not implemented)")
        check("recipe_digest_present", bool(recipe_digest), recipe_digest[:31])

        if proposal.steps:
            step = proposal.steps[0]
            match = _CAPABILITY_ID.match(step.capability_id)
            check("capability_id_format", match is not None, step.capability_id)
            if match:
                application_id, action_id = match.group(1), match.group(2)
                check("application_known",
                      application_id in INTEGRATION_APPLICATIONS, application_id)
                if application_id in INTEGRATION_APPLICATIONS:
                    self._validate_capability(
                        session, application_id, action_id, step.parameters, check)

        criteria = payload.acceptance_criteria
        check("acceptance_criteria_present", bool(criteria),
              f"{len(criteria)} criterion(s)")
        human_sourced = [
            item for item in criteria
            if item.source.strip().casefold().startswith("human:")
        ]
        check("acceptance_human_sourced", bool(human_sourced),
              "at least one criterion must cite a human decision point")
        check("acceptance_provenance_present",
              bool(payload.acceptance_provenance.strip()),
              payload.acceptance_provenance[:120])

        placeholders = [
            key for key, value in (proposal.steps[0].parameters.items()
                                   if proposal.steps else [])
            if isinstance(value, str) and "<" in value and ">" in value
        ]
        check("no_placeholders", not placeholders,
              ", ".join(placeholders) if placeholders else "concrete values")
        return findings

    def _validate_capability(
        self, session: Session, application_id: str, action_id: str,
        parameters: dict[str, Any], check: Any,
    ) -> None:
        application = session.get(Application, application_id)
        check("application_present", application is not None, application_id)
        if application is None:
            return
        check("application_adapter_enabled", bool(application.adapter_enabled),
              f"adapter_enabled={application.adapter_enabled}")
        adapter = get_app_adapter(application.integration_adapter or "")
        check("adapter_registered", adapter is not None,
              application.integration_adapter or "")
        if adapter is None:
            return
        action = next((item for item in adapter.actions if item.id == action_id), None)
        check("action_exists", action is not None, action_id)
        if action is None:
            return
        check("action_enabled", action.enabled,
              action.unavailable_reason or "enabled")
        check("approval_required_preserved", action.approval_required,
              "ActionSpec requires explicit confirmation")
        try:
            _validate_parameters(action.parameters_schema, parameters)
            check("parameters_valid", True, "schema satisfied")
        except ValidationProblem as exc:
            check("parameters_valid", False, str(exc))
            return
        if not action.enabled:
            return
        try:
            adapter.validate_action(
                action_id, parameters,
                self.integrations._action_context(session, application))
            check("action_semantics_valid", True, "adapter accepted parameters")
        except ValueError as exc:
            check("action_semantics_valid", False, str(exc))
            return
        properties = action.parameters_schema.get("properties") or {}
        book_id = parameters.get("book_id")
        if "book_id" in properties and book_id is not None:
            record = session.scalar(
                select(IntegrationRecord).where(
                    IntegrationRecord.application_id == "writer",
                    IntegrationRecord.resource_type == "writer_editing_book",
                    IntegrationRecord.external_id == str(book_id))
            )
            check("book_registered", record is not None, str(book_id))
            if record is None:
                return
            root = str((record.data or {}).get("project_root") or "")
            check("book_root_known", bool(root),
                  root or "resource has no project_root")
            supplied = parameters.get("book_root")
            if supplied is not None and root:
                check("book_root_resolved",
                      str(supplied).replace("\\", "/").casefold()
                      == root.replace("\\", "/").casefold(),
                      f"registered root is {root}")

    # --------------------------------------------------------------- approve
    def approve(self, proposal_key: str, *, approved_by: str,
                confirm: bool, note: str = "") -> PraxisProposalRead:
        approver = (approved_by or "").strip()
        if not confirm:
            raise Conflict("Explicit human confirmation is required to approve")
        if len(approver) < 2:
            raise ValidationProblem("approval must identify a human approver")
        if approver.casefold() in SELF_APPROVAL_DENYLIST:
            raise ValidationProblem(
                "A Pi agent or automated system cannot approve its own proposal"
            )
        with self.database.session() as session:
            row = self._get(session, proposal_key)
            if row.status != "awaiting_approval":
                raise Conflict(
                    f"Proposal is {row.status!r}; only awaiting_approval can be approved"
                )
            row.approved_by = approver
            row.approved_at = now_iso()
            row.approval_digest = row.content_digest
            row.status = "approved"
            row.updated_at = now_iso()
            session.flush()
            return self._read_with_execution(session, row)

    # --------------------------------------------------------------- withdraw
    def withdraw(self, proposal_key: str, *, owner: str, reason: str,
                 confirm: bool) -> PraxisProposalRead:
        """Withdraw a test-owned proposal. Operator proposals are never deleted."""
        if not confirm:
            raise Conflict("Explicit confirmation is required to withdraw")
        if not (reason or "").strip():
            raise ValidationProblem("A withdrawal reason is required")
        if not (owner or "").strip():
            raise ValidationProblem("owner is required")
        with self.database.session() as session:
            row = self._get(session, proposal_key)
            if row.ownership_kind != "test":
                raise ValidationProblem(
                    "Only test-owned proposals can be withdrawn; operator "
                    "proposals require an explicit governance decision")
            if row.owner.casefold() != owner.strip().casefold():
                raise ValidationProblem("owner does not match proposal owner")
            if row.status in {"approved", "execution_requested", "running",
                              "succeeded", "failed"}:
                raise Conflict(
                    f"Proposal is {row.status!r}; it cannot be withdrawn")
            row.status = "withdrawn"
            row.withdrawn_at = now_iso()
            row.updated_at = now_iso()
            session.flush()
            return self._read_with_execution(session, row)

    # ---------------------------------------------------------------- reject
    def reject(self, proposal_key: str, *, rejected_by: str,
               reason: str, confirm: bool) -> PraxisProposalRead:
        if not confirm:
            raise Conflict("Explicit confirmation is required to reject")
        if not (rejected_by or "").strip():
            raise ValidationProblem("rejected_by is required")
        if not (reason or "").strip():
            raise ValidationProblem("A rejection reason is required")
        with self.database.session() as session:
            row = self._get(session, proposal_key)
            if row.status in {"succeeded", "failed", "running", "execution_requested"}:
                raise Conflict(f"Proposal is {row.status!r}; cannot reject after execution")
            row.rejected_by = rejected_by.strip()
            row.rejected_at = now_iso()
            row.rejection_reason = reason.strip()[:2000]
            row.status = "rejected"
            row.updated_at = now_iso()
            session.flush()
            return self._read_with_execution(session, row)

    # --------------------------------------------------------------- execute
    async def execute(self, proposal_key: str, *, requested_by: str,
                      confirm: bool) -> PraxisProposalRead:
        if not confirm:
            raise Conflict("Explicit confirmation is required to request execution")
        if not (requested_by or "").strip():
            raise ValidationProblem("requested_by is required")
        with self.database.session() as session:
            row = self._get(session, proposal_key)
            if row.status == "execution_requested" or row.execution_id:
                raise Conflict("This proposal has already been executed; "
                               "repeat execution is refused")
            if row.status != "approved":
                raise Conflict(
                    f"Proposal is {row.status!r}; only an approved proposal can execute"
                )
            if row.approval_digest != row.content_digest:
                raise Conflict("Approval does not match the current proposal snapshot")
            step = (row.steps_json or [{}])[0]
            match = _CAPABILITY_ID.match(str(step.get("capability_id", "")))
            if match is None:
                raise ValidationProblem("Stored capability id is invalid")
            application_id, action_id = match.group(1), match.group(2)
            parameters = dict(step.get("parameters") or {})
            row.status = "execution_requested"
            row.execution_requested_at = now_iso()
            application = session.get(Application, application_id)
            config = dict(application.adapter_config or {}) if application else {}
            row.execution_config_json = {
                "capability_id": step.get("capability_id"),
                "capability_version": "mc09.1",
                "timeout_seconds": config.get("timeout_seconds"),
                "captured_at": now_iso(),
            }
            row.updated_at = now_iso()
            session.flush()
            key, correlation = row.proposal_key, row.correlation_id

        try:
            execution = await self.integrations.start_action(
                application_id, action_id, parameters, confirm=True)
        except Exception:
            with self.database.session() as session:
                row = session.get(PraxisProposal, key)
                if row is not None:
                    row.status = "approved"
                    row.execution_requested_at = None
                    row.updated_at = now_iso()
            raise
        with self.database.session() as session:
            row = session.get(PraxisProposal, key)
            if row is None:  # pragma: no cover - defensive
                raise NotFound("Proposal disappeared during execution request")
            row.execution_id = execution.id
            row.status = "running"
            row.updated_at = now_iso()
            session.flush()
            read = _proposal_read(row)
        read.correlation_id = correlation
        return read

    # ----------------------------------------------------------------- read
    def list_proposals(self, limit: int = 50) -> list[PraxisProposalRead]:
        with self.database.session() as session:
            rows = session.scalars(
                select(PraxisProposal)
                .order_by(desc(PraxisProposal.updated_at))
                .limit(max(1, min(limit, 200)))
            ).all()
            return [self._read_with_execution(session, row) for row in rows]

    def get_proposal(self, proposal_key: str) -> PraxisProposalRead:
        with self.database.session() as session:
            return self._read_with_execution(session, self._get(session, proposal_key))

    def evidence(self, proposal_key: str) -> PraxisProposalEvidence:
        with self.database.session() as session:
            row = self._get(session, proposal_key)
            read = self._read_with_execution(session, row)
            execution = None
            if row.execution_id:
                record = session.get(IntegrationExecution, row.execution_id)
                if record is not None:
                    execution = {
                        "id": record.id,
                        "application_id": record.application_id,
                        "action_id": record.action_id,
                        "status": record.status,
                        "risk": record.risk,
                        "approval_required": record.approval_required,
                        "approved_at": record.approved_at,
                        "started_at": record.started_at,
                        "ended_at": record.ended_at,
                        "exit_code": record.exit_code,
                        "output_present": bool(record.output),
                        "error": record.error,
                        "result": dict(record.result or {}),
                        "artifact_ref": record.artifact_ref,
                        "created_at": record.created_at,
                    }
            correlation = {
                "correlation_id": row.correlation_id,
                "goal_id": row.goal_id,
                "proposal_key": row.proposal_key,
                "recipe_digest": row.recipe_digest,
                "content_digest": row.content_digest,
                "approval_digest": row.approval_digest,
                "approved_by": row.approved_by,
                "execution_id": row.execution_id,
            }
            return PraxisProposalEvidence(
                proposal=read,
                execution=execution,
                correlation=correlation,
                evaluation_boundary={
                    "mc_asserts": [
                        "capability and parameters validated against ActionSpec",
                        "registered resources resolved by Mission Control",
                        "approval identity and digest recorded",
                        "execution record is authoritative",
                    ],
                    "mc_does_not_assert": [
                        "goal achievement",
                        "artifact quality",
                        "cost in dollars (not measured)",
                        "strategy effectiveness or improvement",
                    ],
                    "praxis_must_evaluate": [
                        "independent correctness where deterministic checks exist",
                        "goal achievement against approved acceptance criteria",
                        "effectiveness and improvement claims with explicit uncertainty",
                    ],
                    "capability_metadata": capability_metadata(session, row),
                    "preflight_is_advisory": True,
                },
            )

    # -------------------------------------------------------------- helpers
    def _get(self, session: Session, proposal_key: str) -> PraxisProposal:
        row = session.get(PraxisProposal, proposal_key)
        if row is None:
            raise NotFound("Praxis proposal not found")
        if row.execution_id and row.status in {"running", "execution_requested"}:
            self._refresh_execution_status(session, row)
        return row

    def _refresh_execution_status(self, session: Session, row: PraxisProposal) -> None:
        record = session.get(IntegrationExecution, row.execution_id or "")
        if record is None:
            return
        mapping = {
            "queued": "running",
            "running": "running",
            "succeeded": "succeeded",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        status = mapping.get(record.status)
        if status and status != row.status:
            row.status = status
            row.updated_at = now_iso()
            session.flush()

    def _read_with_execution(
        self, session: Session, row: PraxisProposal
    ) -> PraxisProposalRead:
        if row.execution_id and row.status in {"running", "execution_requested"}:
            self._refresh_execution_status(session, row)
        read = _proposal_read(row)
        # Advisory preflight is recomputed on read so the reviewer sees the
        # current environment; it is not part of the approval digest.
        read.preflight = compute_preflight(session, row)
        return read
