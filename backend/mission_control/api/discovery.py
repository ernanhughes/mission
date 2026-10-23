"""Discovery roots, scans and repository candidates."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.models import Repository
from mission_control.projects.service import refresh_repositories
from mission_control.schemas import (
    CandidateRead,
    DiscoveryRootCreate,
    DiscoveryRootRead,
    DiscoveryRootUpdate,
    OkResponse,
    ScanRead,
)
from mission_control.settings.service import (
    add_discovery_root,
    remove_discovery_root,
    set_discovery_root_enabled,
)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/roots", response_model=list[DiscoveryRootRead])
def get_roots(session: Session = Depends(get_session)) -> list[DiscoveryRootRead]:
    from mission_control.models import DiscoveryRoot

    return [
        DiscoveryRootRead(path=root.path, enabled=root.enabled, added_at=root.added_at)
        for root in session.scalars(select(DiscoveryRoot).order_by(DiscoveryRoot.path)).all()
    ]


@router.post("/roots", response_model=DiscoveryRootRead, status_code=201)
def add_root(
    payload: DiscoveryRootCreate, session: Session = Depends(get_session)
) -> DiscoveryRootRead:
    return add_discovery_root(session, payload)


@router.patch("/roots", response_model=DiscoveryRootRead)
def update_root(
    payload: DiscoveryRootUpdate, session: Session = Depends(get_session)
) -> DiscoveryRootRead:
    return set_discovery_root_enabled(session, payload.path, payload.enabled)


@router.delete("/roots", response_model=OkResponse)
def delete_root(path: str, session: Session = Depends(get_session)) -> OkResponse:
    remove_discovery_root(session, path)
    return OkResponse(detail="Discovery root removed")


@router.post("/scan", response_model=ScanRead, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(request: Request) -> ScanRead:
    result = await request.app.state.discovery.start()
    return ScanRead(**result)


@router.get("/scan", response_model=ScanRead)
def scan_status(request: Request) -> ScanRead:
    return ScanRead(**request.app.state.discovery.status)


@router.post("/scan/cancel", response_model=ScanRead)
async def cancel_scan(request: Request) -> ScanRead:
    result = await request.app.state.discovery.cancel()
    return ScanRead(**result)


@router.get("/candidates", response_model=list[CandidateRead])
def list_candidates(
    session: Session = Depends(get_session),
    classification: str | None = None,
    search: str | None = None,
    include_linked: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CandidateRead]:
    query = select(Repository).order_by(desc(Repository.last_observed_at), Repository.name)
    if not include_linked:
        query = query.where(Repository.candidate.is_(True))
    if classification:
        query = query.where(Repository.classification == classification)
    if search:
        needle = f"%{search.casefold()}%"
        query = query.where(
            Repository.name.ilike(needle) | Repository.path.ilike(needle)
        )
    rows = session.scalars(query.limit(limit).offset(offset)).all()
    return [
        CandidateRead(
            id=item.id,
            name=item.name,
            path=item.path,
            classification=item.classification,
            confidence=item.confidence,
            evidence=item.evidence,
            role=None,
            source_root=item.source_root,
            is_git=item.is_git,
            branch=item.branch,
            commit_hash=item.commit_hash,
            last_commit_at=item.last_commit_at,
            dirty=item.dirty,
            accessible=item.accessible,
            candidate=item.candidate,
            last_observed_at=item.last_observed_at,
            notes=item.notes,
        )
        for item in rows
    ]


@router.post("/refresh-repositories", response_model=OkResponse)
async def refresh_repository_metadata(request: Request) -> OkResponse:
    count = await asyncio.to_thread(refresh_repositories, request.app.state.database)
    return OkResponse(detail=f"Observed {count} repositories read-only")
