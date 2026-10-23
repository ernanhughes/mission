"""Settings validation, persistence and safe secret handling."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.core.paths import (
    require_existing_directory,
    resolve_executable,
    validate_arguments,
    validate_executable,
    validate_relative_glob,
    validate_url,
)
from mission_control.models import Application, DiscoveryRoot, Setting
from mission_control.persistence.db import now_iso
from mission_control.persistence.seed import DEFAULT_SETTINGS
from mission_control.schemas import (
    DiscoveryRootCreate,
    DiscoveryRootRead,
    SettingsPatch,
    SettingsRead,
)

_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_SECRET_FIELDS = {"api_key", "key", "token", "password", "secret", "authorization"}


def _merge(session: Session, key: str, patch: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    unknown = set(patch) - allowed
    if unknown:
        raise ValidationProblem(f"Unknown {key} settings: {', '.join(sorted(unknown))}")
    if any(field.casefold() in _SECRET_FIELDS for field in patch):
        raise ValidationProblem("Secrets must not be stored in settings; name an environment variable instead")
    setting = session.get(Setting, key)
    current = dict(setting.value) if setting and isinstance(setting.value, dict) else dict(DEFAULT_SETTINGS.get(key, {}))
    current.update(patch)
    if setting is None:
        session.add(Setting(key=key, value=current, updated_at=now_iso()))
    else:
        setting.value = current
        setting.updated_at = now_iso()
    return current


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationProblem(f"{field} must be a boolean")
    return value


def _int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValidationProblem(f"{field} must be an integer between {minimum} and {maximum}")
    return value


def _str(value: Any, field: str, max_length: int = 500) -> str:
    if not isinstance(value, str):
        raise ValidationProblem(f"{field} must be a string")
    if len(value) > max_length:
        raise ValidationProblem(f"{field} is too long")
    return value


def update_settings(session: Session, payload: SettingsPatch) -> SettingsRead:
    if payload.discovery is not None:
        patch = payload.discovery
        if "exclusions" in patch:
            exclusions = patch["exclusions"]
            if not isinstance(exclusions, list):
                raise ValidationProblem("discovery.exclusions must be a list")
            cleaned = [validate_relative_glob(item) for item in exclusions[:500]]
            patch = {**patch, "exclusions": cleaned}
        for field in ("max_depth", "max_candidates", "timeout_seconds", "git_timeout_seconds"):
            if field in patch:
                limits = {
                    "max_depth": (1, 3),
                    "max_candidates": (1, 2000),
                    "timeout_seconds": (10, 600),
                    "git_timeout_seconds": (1, 30),
                }[field]
                _int(patch[field], f"discovery.{field}", *limits)
        _merge(
            session,
            "discovery",
            patch,
            {"exclusions", "max_depth", "max_candidates", "timeout_seconds", "git_timeout_seconds"},
        )
    if payload.editor is not None:
        patch = dict(payload.editor)
        if "command" in patch:
            patch["command"] = validate_executable(_str(patch["command"], "editor.command", 1024), field="editor command") or ""
            if patch["command"]:
                resolved = resolve_executable(patch["command"])
                if resolved and Path(resolved).suffix.casefold() in {".cmd", ".bat", ".ps1"}:
                    raise ValidationProblem(
                        "The configured editor resolves to a shell script. "
                        "Set the native executable instead (for example Code.exe)."
                    )
        if "arguments" in patch:
            patch["arguments"] = validate_arguments(patch["arguments"])
        if "append_path" in patch:
            _bool(patch["append_path"], "editor.append_path")
        _merge(session, "editor", patch, {"command", "arguments", "append_path"})
    if payload.browser is not None:
        patch = dict(payload.browser)
        if "open_mode" in patch:
            if patch["open_mode"] not in {"new_tab", "external"}:
                raise ValidationProblem("browser.open_mode must be 'new_tab' or 'external'")
        _merge(session, "browser", patch, {"open_mode"})
    if payload.processes is not None:
        patch = dict(payload.processes)
        if "max_managed" in patch:
            _int(patch["max_managed"], "processes.max_managed", 1, 20)
        if "health_check_interval_seconds" in patch:
            _int(patch["health_check_interval_seconds"], "processes.health_check_interval_seconds", 10, 3600)
        if "log_tail_lines" in patch:
            _int(patch["log_tail_lines"], "processes.log_tail_lines", 20, 2000)
        _merge(
            session,
            "processes",
            patch,
            {"max_managed", "health_check_interval_seconds", "log_tail_lines"},
        )
    if payload.adapters is not None:
        patch = dict(payload.adapters)
        if "refresh_interval_minutes" in patch:
            _int(patch["refresh_interval_minutes"], "adapters.refresh_interval_minutes", 1, 1440)
        if "timeout_seconds" in patch:
            _int(patch["timeout_seconds"], "adapters.timeout_seconds", 1, 60)
        _merge(session, "adapters", patch, {"refresh_interval_minutes", "timeout_seconds"})
    if payload.retention is not None:
        patch = dict(payload.retention)
        for field in ("activity_days", "briefing_days", "log_days"):
            if field in patch:
                _int(patch[field], f"retention.{field}", 1, 3650)
        _merge(session, "retention", patch, {"activity_days", "briefing_days", "log_days"})
    if payload.ai is not None:
        patch = dict(payload.ai)
        if any(field.casefold() in _SECRET_FIELDS for field in patch):
            raise ValidationProblem("AI API keys are never stored; configure an environment variable name")
        for field in ("enabled", "consent"):
            if field in patch:
                _bool(patch[field], f"ai.{field}")
        if "provider" in patch and patch["provider"] != "openai-compatible":
            raise ValidationProblem("Only the openai-compatible provider is implemented")
        if "base_url" in patch:
            patch["base_url"] = validate_url(_str(patch["base_url"], "ai.base_url", 500) or None)
        if "model" in patch:
            patch["model"] = _str(patch["model"], "ai.model", 200)
        if "api_key_env" in patch:
            env_name = _str(patch["api_key_env"], "ai.api_key_env", 64)
            if env_name and not _KEY_PATTERN.match(env_name):
                raise ValidationProblem("ai.api_key_env must be a valid environment variable name")
            patch["api_key_env"] = env_name
        if "timeout_seconds" in patch:
            _int(patch["timeout_seconds"], "ai.timeout_seconds", 5, 180)
        current_setting = session.get(Setting, "ai")
        current_ai = (
            dict(current_setting.value)
            if current_setting and isinstance(current_setting.value, dict)
            else dict(DEFAULT_SETTINGS["ai"])
        )
        merged = {**current_ai, **patch}
        # Validate the resulting configuration, not just the patch.
        if merged.get("enabled"):
            if not merged.get("consent"):
                raise ValidationProblem("AI features require explicit consent")
            if not merged.get("base_url") or not merged.get("model"):
                raise ValidationProblem("AI features require a base_url and model")
        _merge(session, "ai", patch, {"enabled", "consent", "provider", "base_url", "model", "api_key_env", "timeout_seconds"})
    if payload.startup is not None:
        patch = dict(payload.startup)
        if "profile_enabled" in patch:
            _bool(patch["profile_enabled"], "startup.profile_enabled")
        if "profile_applications" in patch:
            values = patch["profile_applications"]
            if not isinstance(values, list) or len(values) > 10:
                raise ValidationProblem("startup.profile_applications must be a list of at most 10 app ids")
            for app_id in values:
                if session.get(Application, app_id) is None:
                    raise ValidationProblem(f"Startup profile application does not exist: {app_id}")
        _merge(
            session,
            "startup",
            patch,
            {"profile_enabled", "profile_applications"},
        )
    if payload.ui is not None:
        patch = dict(payload.ui)
        if "theme" in patch and patch["theme"] not in {"system", "light", "dark"}:
            raise ValidationProblem("ui.theme must be system, light or dark")
        _merge(session, "ui", patch, {"theme"})
    record_activity(
        session,
        event_type="system",
        title="Settings updated",
        detail="Configuration changed through the local settings page.",
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return get_settings(session)


def get_settings(session: Session) -> SettingsRead:
    values: dict[str, dict[str, Any]] = {}
    for key in ("discovery", "editor", "browser", "processes", "adapters", "retention", "ai", "startup", "ui"):
        setting = session.get(Setting, key)
        values[key] = dict(setting.value) if setting and isinstance(setting.value, dict) else dict(DEFAULT_SETTINGS.get(key, {}))
    roots = [
        {"path": root.path, "enabled": root.enabled, "added_at": root.added_at}
        for root in session.scalars(select(DiscoveryRoot).order_by(DiscoveryRoot.path)).all()
    ]
    ai = values["ai"]
    ai_configured = bool(ai.get("enabled") and ai.get("consent") and ai.get("base_url") and ai.get("model"))
    env_name = str(ai.get("api_key_env") or "")
    ai_key_present = bool(env_name and os.environ.get(env_name))
    return SettingsRead(
        **values,
        discovery_roots=roots,
        ai_configured=ai_configured,
        ai_key_present=ai_key_present,
    )


def add_discovery_root(session: Session, payload: DiscoveryRootCreate) -> DiscoveryRootRead:
    try:
        path = require_existing_directory(payload.path, field="discovery root")
    except ValidationProblem as exc:
        raise ValidationProblem(exc.message) from exc
    if session.get(DiscoveryRoot, path):
        raise Conflict("Discovery root already exists")
    root = DiscoveryRoot(path=path, enabled=payload.enabled, added_at=now_iso())
    session.add(root)
    record_activity(
        session,
        event_type="system",
        title="Discovery root added",
        detail=path,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return DiscoveryRootRead(path=root.path, enabled=root.enabled, added_at=root.added_at)


def set_discovery_root_enabled(session: Session, path: str, enabled: bool) -> DiscoveryRootRead:
    root = session.get(DiscoveryRoot, path)
    if root is None:
        raise NotFound("Discovery root not found")
    root.enabled = enabled
    record_activity(
        session,
        event_type="system",
        title=f"Discovery root {'enabled' if enabled else 'disabled'}",
        detail=path,
        source="mission-control",
        provenance="user",
    )
    session.flush()
    return DiscoveryRootRead(path=root.path, enabled=root.enabled, added_at=root.added_at)


def remove_discovery_root(session: Session, path: str) -> None:
    root = session.get(DiscoveryRoot, path)
    if root is None:
        raise NotFound("Discovery root not found")
    session.delete(root)
    record_activity(
        session,
        event_type="system",
        title="Discovery root removed",
        detail=path,
        source="mission-control",
        provenance="user",
    )
    session.flush()
