"""MC-INSPECT-04 B: governed Inspect opportunity -> Praxis proposal bridge.

Read-only opportunity lookup from the Inspect snapshot, plus explicit
import into the existing governed proposal lifecycle. No alternative
execution API, no raw action invocation, no auto-approval.

- Draft preview builds a contract-valid payload without importing.
- Import creates an awaiting_approval (or rejected, if advisory) proposal
  via PraxisProposalService; approval/execution stay on the existing routes.
- Originating opportunity ID, repository, revision and verification state
  are preserved in evidence_refs and goal provenance.
- Execution success, acceptance satisfaction and demonstrable improvement
  remain distinct (see proposal evidence endpoint).
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.api.inspect import _reject_traversal, _snapshot
from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.praxis_proposals.schemas import (
    PraxisProposalImport,
    PraxisProposalRead,
)

router = APIRouter(prefix="/api/inspect", tags=["inspect proposals"])


class ProposalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str = ""
    parameters: dict[str, Any] = {}
    acceptance_criteria: list[dict[str, Any]] = []
    acceptance_provenance: str = ""
    expected_benefits: list[str] = []
    owner: str = ""


def _find_opportunity(data: Any, opportunity_id: str) -> dict[str, Any]:
    for opp in data.opportunities:
        if str(opp.get("opportunity_id") or opp.get("id") or "") == opportunity_id:
            return opp
    raise NotFound(f"inspect opportunity not found: {opportunity_id}")


def _redact(value: str, limit: int = 500) -> str:
    text = str(value or "")[:limit]
    # Avoid copying absolute filesystem paths or secrets into proposals.
    # Keep evidence as repository-relative references only.
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) > 3 and (":\\" in stripped or stripped.startswith("/")):
            continue
        if "api_key" in stripped.lower() or "secret" in stripped.lower():
            continue
        lines.append(line)
    return "\n".join(lines)[:limit]


def build_draft(opportunity: dict[str, Any], payload: ProposalDraftRequest) -> dict[str, Any]:
    opp_id = str(opportunity.get("opportunity_id") or opportunity.get("id") or "")
    repository = str(opportunity.get("repository") or "")
    verification = str(opportunity.get("status") or "proposed")
    raw_refs = opportunity.get("evidence_refs") or opportunity.get("evidence") or []
    evidence_refs: list[str] = []
    if isinstance(raw_refs, list):
        for ref in raw_refs[:20]:
            if isinstance(ref, str) and ref.strip():
                evidence_refs.append(ref.strip()[:500])
            elif isinstance(ref, dict):
                path = str(ref.get("path") or ref.get("ref") or "")
                if path and not (":\\" in path or path.startswith("/")):
                    evidence_refs.append(path[:500])
    evidence_refs.append(f"inspect:opportunity:{opp_id}")
    if repository:
        evidence_refs.append(f"inspect:repository:{repository}")

    # Stable proposal identity derived from the opportunity; version is
    # caller-managed for iteration. Digest binding stays with the service.
    proposal_id = f"inspect-{hashlib.sha1(opp_id.encode()).hexdigest()[:12]}"
    goal = {
        "goal_id": opp_id,
        "external_id": opp_id,
        "title": str(opportunity.get("title") or "")[:300],
        "description": _redact(str(opportunity.get("description") or ""), 2000),
        "desired_outcome": _redact(str(opportunity.get("desired_outcome") or ""), 1000),
        "state": "proposed",
        "source": f"inspect:{repository}:{opp_id}",
        "provenance": {
            "origin": "inspect-opportunity",
            "opportunity_id": opp_id,
            "repository": repository,
            "verification_status": verification,
            "draft": True,
            "note": "Source-inspected draft; not runtime verification.",
        },
        "explicit_acceptance": [],
        "inferred_constraints": [],
        "evidence": evidence_refs[:25],
        "themes": [],
        "stale": bool(opportunity.get("stale")),
    }
    steps: list[dict[str, Any]] = []
    if payload.capability_id.strip():
        steps.append(
            {
                "capability_id": payload.capability_id.strip(),
                "parameters": dict(payload.parameters or {}),
                "rationale": _redact(str(opportunity.get("suggested_action") or ""), 1000),
            }
        )
    criteria = list(payload.acceptance_criteria or [])
    return {
        "schema_version": "mc-praxis-proposal-v1",
        "proposal": {
            "id": proposal_id,
            "version": "v1",
            "status": "validated",
            "goal": goal,
            "steps": steps,
            "capability_versions": {},
            "pi_model": "",
            "protocol": "",
            "evidence_refs": evidence_refs[:25],
            "expected_benefits": list(payload.expected_benefits or [])[:10],
            "risks": [],
            "assumptions": [f"Inspect opportunity {opp_id} is {verification}; human review required."],
            "estimated_cost": {},
            "observed_composition_cost_usd": None,
            "correlation": {"inspect_opportunity_id": opp_id, "inspect_repository": repository},
        },
        "acceptance_criteria": criteria,
        "acceptance_provenance": payload.acceptance_provenance or "",
        "ownership": {"kind": "operator", "owner": payload.owner or ""} if payload.owner else None,
    }


@router.post("/opportunities/{opportunity_id}/proposal-draft")
def proposal_draft(
    opportunity_id: str,
    payload: ProposalDraftRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    _reject_traversal(opportunity_id)
    data, _, _, _ = _snapshot(request, session)
    if data is None:
        raise NotFound(f"inspect opportunity not found: {opportunity_id}")
    opportunity = _find_opportunity(data, opportunity_id)
    return {"available": True, "draft": build_draft(opportunity, payload)}


@router.post("/opportunities/{opportunity_id}/proposals", response_model=PraxisProposalRead)
def import_opportunity_proposal(
    opportunity_id: str,
    payload: ProposalDraftRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> PraxisProposalRead:
    _reject_traversal(opportunity_id)
    data, _, _, _ = _snapshot(request, session)
    if data is None:
        raise NotFound(f"inspect opportunity not found: {opportunity_id}")
    opportunity = _find_opportunity(data, opportunity_id)
    # Unverified opportunities cannot become approved actions via this route:
    # import only; approval stays explicit on /api/praxis/proposals/{key}/approve.
    status = str(opportunity.get("status") or "proposed")
    if status in {"resolved", "rejected"}:
        raise ValidationProblem("Resolved or rejected opportunities cannot seed new proposals")
    draft = build_draft(opportunity, payload)
    if not draft["acceptance_criteria"]:
        raise ValidationProblem("At least one acceptance criterion with human: source is required")
    try:
        import_payload = PraxisProposalImport(**draft)
    except Exception as exc:
        raise ValidationProblem(f"Draft is not contract-valid: {exc}") from exc
    service = request.app.state.praxis_proposal_service
    return service.import_proposal(import_payload)
