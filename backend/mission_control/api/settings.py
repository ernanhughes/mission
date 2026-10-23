"""Settings API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.schemas import SettingsPatch, SettingsRead
from mission_control.settings.service import get_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
def read_settings(session: Session = Depends(get_session)) -> SettingsRead:
    return get_settings(session)


@router.patch("", response_model=SettingsRead)
def patch_settings(
    payload: SettingsPatch, session: Session = Depends(get_session)
) -> SettingsRead:
    return update_settings(session, payload)
