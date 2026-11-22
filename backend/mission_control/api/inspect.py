"""Read-only Inspect consumer-snapshot API (MC-INSPECT-01 Stage 3).

Serves the JSON snapshot produced by Inspect (manifest + projects,
capabilities, usage, opportunities, coverage, compositions) as plain GET
endpoints. No Pi, no subprocess, no network, no database writes.

Empty/missing snapshot is a 200 empty state (``available: false``), never a
500. Invalid refreshes keep serving the last valid snapshot with
``stale_refresh: true`` (see ``mission_control.inspect_snapshots``).

There are no user-supplied filesystem paths: ``{id}`` parameters are lookup
keys into already-loaded in-memory data. Values containing path separators
or ``..`` are rejected with 404 before any lookup.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import NotFound
from mission_control.inspect_snapshots import SnapshotData, get_store, map_inspect_project
from mission_control.models import Application
from mission_control.schemas import (
    InspectCapabilityListRead,
    InspectCompositionListRead,
    InspectCoverageRead,
    InspectManifestRead,
    InspectOpportunityListRead,
    InspectProjectListRead,
    InspectProjectRead,
    InspectUsageRead,
)

router = APIRouter(prefix="/api/inspect", tags=["inspect"])


def _reject_traversal(value: str) -> str:
    """Ids are in-memory lookup keys, never file paths; reject path-like input."""
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise NotFound(f"inspect record not found: {value}")
    return value


def _snapshot(
    request: Request, session: Session
) -> tuple[SnapshotData | None, bool, str, list[Application]]:
    store = get_store(request.app.state.settings.inspect_dir)
    data, stale = store.view()
    applications = list(session.scalars(select(Application)).all())
    return data, stale, str(store.root), applications


def _empty_state(stale: bool, root: str) -> dict:
    return {"available": False, "stale_refresh": stale, "snapshot_dir": root}


def _mapped_project(
    project: dict, applications: list[Application]
) -> InspectProjectRead:
    inspect_id = str(project.get("id", ""))
    mission_id, mapped = map_inspect_project(
        inspect_id, project.get("path"), applications
    )
    return InspectProjectRead(
        id=inspect_id,
        mission_application_id=mission_id,
        mapped=mapped,
        record=project,
    )


@router.get("/manifest", response_model=InspectManifestRead)
def read_manifest(
    request: Request, session: Session = Depends(get_session)
) -> InspectManifestRead:
    data, stale, root, _ = _snapshot(request, session)
    if data is None:
        return InspectManifestRead(**_empty_state(stale, root))
    manifest = data.manifest
    return InspectManifestRead(
        available=True,
        stale_refresh=stale,
        snapshot_dir=root,
        contract_version=manifest.get("contract_version"),
        generated_at=manifest.get("generated_at"),
        inspect_version=manifest.get("inspect_version") or {},
        sources=manifest.get("sources") or [],
        counts=manifest.get("counts") or {},
        validation=manifest.get("validation") or {},
    )


@router.get("/projects", response_model=InspectProjectListRead)
def list_projects(
    request: Request, session: Session = Depends(get_session)
) -> InspectProjectListRead:
    data, stale, root, applications = _snapshot(request, session)
    if data is None:
        return InspectProjectListRead(**_empty_state(stale, root), total=0, projects=[])
    projects = [_mapped_project(project, applications) for project in data.projects]
    return InspectProjectListRead(
        available=True,
        stale_refresh=stale,
        snapshot_dir=root,
        total=len(projects),
        projects=projects,
    )


@router.get("/projects/{project_id}", response_model=InspectProjectRead)
def read_project(
    project_id: str, request: Request, session: Session = Depends(get_session)
) -> InspectProjectRead:
    _reject_traversal(project_id)
    data, _, _, applications = _snapshot(request, session)
    if data is None:
        raise NotFound(f"inspect project not found: {project_id}")
    for project in data.projects:
        if str(project.get("id", "")) == project_id:
            return _mapped_project(project, applications)
    raise NotFound(f"inspect project not found: {project_id}")


@router.get("/capabilities", response_model=InspectCapabilityListRead)
def list_capabilities(
    request: Request,
    session: Session = Depends(get_session),
    project: str | None = Query(default=None),
    subsystem: str | None = Query(default=None),
    access: str | None = Query(default=None),
    verification: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> InspectCapabilityListRead:
    data, stale, root, _ = _snapshot(request, session)
    if data is None:
        return InspectCapabilityListRead(
            **_empty_state(stale, root), total=0, capabilities=[]
        )
    needle = q.strip().lower() if q and q.strip() else None
    matched: list[dict] = []
    for capability in data.capabilities:
        if project is not None and capability.get("repository") != project:
            continue
        if subsystem is not None and capability.get("subsystem") != subsystem:
            continue
        if access is not None and access not in (capability.get("accessibility") or []):
            continue
        if verification is not None and capability.get("operational_status") != verification:
            continue
        if risk is not None and capability.get("risk") != risk:
            continue
        if needle:
            haystack = " ".join(
                str(capability.get(key, "")) for key in ("id", "name", "description")
            ).lower()
            if needle not in haystack:
                continue
        matched.append(capability)
    return InspectCapabilityListRead(
        available=True,
        stale_refresh=stale,
        snapshot_dir=root,
        total=len(matched),
        capabilities=matched,
    )


@router.get("/capabilities/{capability_id}")
def read_capability(
    capability_id: str, request: Request, session: Session = Depends(get_session)
) -> dict:
    _reject_traversal(capability_id)
    data, stale, _, _ = _snapshot(request, session)
    if data is None:
        raise NotFound(f"inspect capability not found: {capability_id}")
    for capability in data.capabilities:
        if str(capability.get("id", "")) == capability_id:
            return {
                "available": True,
                "stale_refresh": stale,
                "capability": capability,
            }
    raise NotFound(f"inspect capability not found: {capability_id}")


@router.get("/usage/{capability_id}", response_model=InspectUsageRead)
def read_usage(
    capability_id: str, request: Request, session: Session = Depends(get_session)
) -> InspectUsageRead:
    _reject_traversal(capability_id)
    data, stale, root, _ = _snapshot(request, session)
    if data is None:
        return InspectUsageRead(
            **_empty_state(stale, root), capability_id=capability_id, total=0, usages=[]
        )
    usages = [
        usage for usage in data.usages if usage.get("capability_id") == capability_id
    ]
    return InspectUsageRead(
        available=True,
        stale_refresh=stale,
        snapshot_dir=root,
        capability_id=capability_id,
        total=len(usages),
        usages=usages,
    )


@router.get("/opportunities", response_model=InspectOpportunityListRead)
def list_opportunities(
    request: Request,
    session: Session = Depends(get_session),
    project: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> InspectOpportunityListRead:
    data, stale, root, _ = _snapshot(request, session)
    if data is None:
        return InspectOpportunityListRead(
            **_empty_state(stale, root), total=0, opportunities=[]
        )
    matched: list[dict] = []
    for opportunity in data.opportunities:
        if project is not None and not (
            opportunity.get("repository") == project
            or project in (opportunity.get("project_ids") or [])
        ):
            continue
        if category is not None and opportunity.get("category") != category:
            continue
        if status is not None and opportunity.get("status") != status:
            continue
        matched.append(opportunity)
    return InspectOpportunityListRead(
        available=True,
        stale_refresh=stale,
        snapshot_dir=root,
        total=len(matched),
        opportunities=matched,
    )


@router.get("/coverage/{project_id}", response_model=InspectCoverageRead)
def read_coverage(
    project_id: str, request: Request, session: Session = Depends(get_session)
) -> InspectCoverageRead:
    _reject_traversal(project_id)
    data, stale, root, applications = _snapshot(request, session)
    if data is None:
        raise NotFound(f"inspect coverage not found: {project_id}")
    for record in data.coverages:
        if record.get("repository_id") == project_id or record.get("repository") == project_id:
            inspect_path = next(
                (
                    project.get("path")
                    for project in data.projects
                    if str(project.get("id", "")) == project_id
                ),
                None,
            )
            mission_id, mapped = map_inspect_project(project_id, inspect_path, applications)
            return InspectCoverageRead(
                available=True,
                stale_refresh=stale,
                snapshot_dir=root,
                project_id=project_id,
                mission_application_id=mission_id,
                mapped=mapped,
                record=record,
            )
    raise NotFound(f"inspect coverage not found: {project_id}")


@router.get("/compositions", response_model=InspectCompositionListRead)
def list_compositions(
    request: Request,
    session: Session = Depends(get_session),
    project: str | None = Query(default=None),
) -> InspectCompositionListRead:
    data, stale, root, _ = _snapshot(request, session)
    if data is None:
        return InspectCompositionListRead(
            **_empty_state(stale, root), total=0, compositions=[]
        )
    matched = [
        composition
        for composition in data.compositions
        if project is None or composition.get("repository") == project
    ]
    return InspectCompositionListRead(
        available=True,
        stale_refresh=stale,
        snapshot_dir=root,
        total=len(matched),
        compositions=matched,
    )
