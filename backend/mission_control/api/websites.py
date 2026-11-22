"""Website workspaces: read-only discovery plus managed Hugo previews."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.paths import normalize_absolute_path
from mission_control.discovery.websites import detect_websites, website_read
from mission_control.schemas import OkResponse, WebsiteLaunchRead, WebsiteRead
from mission_control.websites.service import (
    WebsitesState,
    launch_hugo,
    list_websites,
    resolve_site,
    stop_hugo,
)

router = APIRouter(prefix="/api/websites", tags=["websites"])


def _websites_root(request: Request):
    return request.app.state.settings.websites_root


def _state(request: Request) -> WebsitesState:
    state = getattr(request.app.state, "websites", None)
    if state is None:
        state = WebsitesState()
        request.app.state.websites = state
    return state


@router.get("", response_model=list[WebsiteRead])
def get_websites(request: Request) -> list[WebsiteRead]:
    """Discover website workspaces. Never launches anything."""
    items, _ = list_websites(_websites_root(request), _state(request))
    return [WebsiteRead(**item) for item in items]


@router.get("/diagnostics", response_model=dict)
def get_diagnostics(request: Request) -> dict:
    """Discovery diagnostics: missing roots are explicit, never silent."""
    _, diagnostics = detect_websites([_websites_root(request)])
    return {"root": str(_websites_root(request)), "diagnostics": diagnostics}


@router.get("/{site_id}", response_model=WebsiteRead)
def get_website(site_id: str, request: Request) -> WebsiteRead:
    site = resolve_site(_websites_root(request), site_id)
    return WebsiteRead(**website_read(site, running=_state(request).status(site_id)))


@router.post("/{site_id}/launch", response_model=WebsiteLaunchRead)
def launch_website(site_id: str, request: Request) -> WebsiteLaunchRead:
    """Launch (or reuse) a managed Hugo preview. Argument-based, loopback only."""
    site = resolve_site(_websites_root(request), site_id)
    result = launch_hugo(_state(request), site)
    return WebsiteLaunchRead(**result)


@router.post("/{site_id}/stop", response_model=OkResponse)
def stop_website(site_id: str, request: Request) -> OkResponse:
    # Validate the id against current discovery so only known websites stop.
    resolve_site(_websites_root(request), site_id)
    result = stop_hugo(_state(request), site_id)
    return OkResponse(detail=result["detail"])


@router.post("/{site_id}/open-path", response_model=OkResponse)
def open_website_path(
    site_id: str, request: Request, session: Session = Depends(get_session)
) -> OkResponse:
    """Open the website working directory with the configured editor."""
    from mission_control.core.editor import open_path_with_editor

    site = resolve_site(_websites_root(request), site_id)
    path = normalize_absolute_path(site.path, field="website path")
    command = open_path_with_editor(session, path)
    return OkResponse(detail=f"Opened {path} with {command}")
