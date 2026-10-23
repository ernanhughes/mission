"""Filesystem path and launch-argument validation.

Mission Control accepts paths from an authenticated local administrator editing
the registry. It never accepts an executable, working directory or raw command
from a launch request. These helpers keep traversal, shell metacharacters and
device paths out of stored configuration.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path, PureWindowsPath

from mission_control.core.errors import ValidationProblem

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_SHELL_CHARS = re.compile(r"[&|;<>^`\r\n\x00]")
_URL = re.compile(r"^https?://[^\s]+$")


def normalize_absolute_path(raw: str, *, field: str = "path") -> str:
    value = (raw or "").strip().strip('"')
    if not value:
        raise ValidationProblem(f"{field} must not be empty")
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValidationProblem(f"{field} contains control characters")
    pure = PureWindowsPath(value)
    if not pure.is_absolute() and not Path(value).is_absolute():
        raise ValidationProblem(f"{field} must be an absolute path")
    if ".." in pure.parts or ".." in Path(value).parts:
        raise ValidationProblem(f"{field} must not contain '..'")
    normalized = str(Path(value).expanduser().resolve(strict=False))
    if normalized.startswith("\\\\?\\") or normalized.startswith("\\\\.\\"):
        raise ValidationProblem(f"{field} must not use a device path")
    return normalized


def require_existing_directory(raw: str, *, field: str = "path") -> str:
    normalized = normalize_absolute_path(raw, field=field)
    path = Path(normalized)
    if not path.exists():
        raise ValidationProblem(f"{field} does not exist: {normalized}")
    if not path.is_dir():
        raise ValidationProblem(f"{field} is not a directory: {normalized}")
    return normalized


def is_within(child: Path, parent: Path) -> bool:
    try:
        child_text = os.path.normcase(str(child.resolve(strict=False)))
        parent_text = os.path.normcase(str(parent.resolve(strict=False)))
        return os.path.commonpath([child_text, parent_text]) == parent_text
    except ValueError:
        return False


def validate_executable(raw: str | None, *, field: str = "executable") -> str | None:
    """Validate a stored executable name or path.

    This intentionally does not require the executable to exist: an
    administrator may save an incomplete definition, which is then reported as
    misconfigured rather than silently treated as launchable.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValidationProblem(f"{field} contains control characters")
    if _SHELL_CHARS.search(value):
        raise ValidationProblem(f"{field} contains shell control characters")
    if value.endswith((".bat", ".cmd", ".ps1")):
        raise ValidationProblem(
            f"{field} must be a native executable; shell scripts are not launched by Mission Control"
        )
    if len(value) > 1024:
        raise ValidationProblem(f"{field} is too long")
    return value


def resolve_executable(raw: str) -> str | None:
    candidate = Path(raw)
    if candidate.is_absolute():
        return str(candidate) if candidate.is_file() else None
    return shutil.which(raw)


def validate_arguments(arguments: list[str] | None) -> list[str]:
    values = arguments or []
    if not isinstance(values, list):
        raise ValidationProblem("arguments must be a list of strings")
    cleaned: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            raise ValidationProblem(f"argument {index} must be a string")
        if "\x00" in item or "\n" in item or "\r" in item:
            raise ValidationProblem(f"argument {index} contains control characters")
        if len(item) > 4096:
            raise ValidationProblem(f"argument {index} is too long")
        cleaned.append(item)
    if len(cleaned) > 64:
        raise ValidationProblem("too many arguments (maximum 64)")
    return cleaned


def validate_env_names(names: list[str] | None) -> list[str]:
    values = names or []
    if not isinstance(values, list):
        raise ValidationProblem("env_names must be a list of strings")
    cleaned: list[str] = []
    for name in values:
        if not isinstance(name, str) or not _ENV_NAME.match(name):
            raise ValidationProblem(f"invalid environment variable name: {name!r}")
        if name.upper() in {"PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP"}:
            raise ValidationProblem(f"{name} is provided by Mission Control and cannot be overridden")
        cleaned.append(name)
    return sorted(set(cleaned))


def validate_url(raw: str | None, *, field: str = "url") -> str | None:
    if raw is None or not raw.strip():
        return None
    value = raw.strip()
    if not _URL.match(value):
        raise ValidationProblem(f"{field} must be an http or https URL")
    return value


def validate_relative_glob(raw: str, *, field: str = "exclusion pattern") -> str:
    value = (raw or "").strip()
    if not value:
        raise ValidationProblem(f"{field} must not be empty")
    if ".." in PureWindowsPath(value).parts or value.startswith(("/", "\\")):
        raise ValidationProblem(f"{field} must be a relative pattern")
    if len(value) > 200:
        raise ValidationProblem(f"{field} is too long")
    return value
