"""MC-PRAXIS-07 API: governed Praxis proposal import, approval, execution.

No route accepts a raw action invocation. Execution is only reachable through
an approved, digest-matched proposal, and the underlying ActionSpec's own
confirmation requirement is still applied by IntegrationService.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from mission_control.praxis_proposals.schemas import (
    PraxisProposalApprove,
    PraxisProposalEvidence,
    PraxisProposalExecuteRequest,
    PraxisProposalImport,
    PraxisProposalRead,
    PraxisProposalReject,
)
from mission_control.praxis_proposals.service import PraxisProposalService

router = APIRouter(prefix="/api/praxis/proposals", tags=["praxis proposals"])


def _service(request: Request) -> PraxisProposalService:
    return request.app.state.praxis_proposal_service


@router.post("", response_model=PraxisProposalRead)
def import_proposal(payload: PraxisProposalImport, request: Request) -> PraxisProposalRead:
    return _service(request).import_proposal(payload)


@router.get("", response_model=list[PraxisProposalRead])
def list_proposals(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> list[PraxisProposalRead]:
    return _service(request).list_proposals(limit)


@router.get("/{proposal_key}", response_model=PraxisProposalRead)
def get_proposal(proposal_key: str, request: Request) -> PraxisProposalRead:
    return _service(request).get_proposal(proposal_key)


@router.post("/{proposal_key}/approve", response_model=PraxisProposalRead)
def approve_proposal(
    proposal_key: str, payload: PraxisProposalApprove, request: Request
) -> PraxisProposalRead:
    return _service(request).approve(
        proposal_key,
        approved_by=payload.approved_by,
        confirm=payload.confirm,
        note=payload.note,
    )


@router.post("/{proposal_key}/reject", response_model=PraxisProposalRead)
def reject_proposal(
    proposal_key: str, payload: PraxisProposalReject, request: Request
) -> PraxisProposalRead:
    return _service(request).reject(
        proposal_key,
        rejected_by=payload.rejected_by,
        reason=payload.reason,
        confirm=payload.confirm,
    )


@router.post("/{proposal_key}/execute", response_model=PraxisProposalRead)
async def execute_proposal(
    proposal_key: str, payload: PraxisProposalExecuteRequest, request: Request
) -> PraxisProposalRead:
    return await _service(request).execute(
        proposal_key, requested_by=payload.requested_by, confirm=payload.confirm
    )


@router.get("/{proposal_key}/evidence", response_model=PraxisProposalEvidence)
def proposal_evidence(proposal_key: str, request: Request) -> PraxisProposalEvidence:
    return _service(request).evidence(proposal_key)
