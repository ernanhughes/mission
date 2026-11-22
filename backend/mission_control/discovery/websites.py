"""Website workspace discovery (MC-WEBSITES-CULTIVATION-01).

Read-only discovery of website workspaces under the configured websites root
(``C:\\websites`` by default, ``MISSION_CONTROL_WEBSITES_ROOT`` override).
Each immediate subdirectory is one website workspace with its own identity;
nothing here duplicates Project or Application registry entries.

A directory is classified as Hugo only when Hugo configuration or structure is
observed (``hugo.toml``/``hugo.yaml``/``hugo.json``/``config.toml``/``config.yaml``/
``config.json``, a ``config/`` directory, or ``content/`` + ``layouts/``).
Anything else is a non-Hugo site. A missing root is an explicit diagnostic,
never an invented list.
"""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

HUGO_CONFIG_FILES = (
    "hugo.toml",
    "hugo.yaml",
    "hugo.yml",
    "hugo.json",
    "config.toml",
    "config.yaml",
    "config.yml",
    "config.json",
)

HUGO_CONTENT_MARKERS = ("content", "layouts", "static", "archetypes", "themes")

_ACRONYMS = {
    "ai": "AI",
    "cms": "CMS",
    "api": "API",
    "ie": "ie",
}


def _humanize(value: str) -> str:
    words = [word for word in re.split(r"[-_.\s]+", value) if word]
    pretty: list[str] = []
    for word in words:
        lowered = word.casefold()
        if lowered in _ACRONYMS:
            pretty.append(_ACRONYMS[lowered])
        else:
            pretty.append(word[:1].upper() + word[1:])
    return " ".join(pretty) or value


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:60] or "website"


def _read_hugo_title(root: Path, config_file: str) -> str | None:
    """Read the site title from a Hugo config file (best effort, read-only)."""
    try:
        text = (root / config_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        if config_file.endswith(".toml"):
            data = tomllib.loads(text)
        elif config_file.endswith(".json"):
            import json as _json

            data = _json.loads(text)
        else:
            data = yaml.safe_load(text)
    except Exception:
        return None
    if isinstance(data, dict):
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()[:120]
    return None


@dataclass(slots=True)
class DetectedWebsite:
    """One discovered website workspace (read-only observation)."""

    site_id: str
    name: str
    path: str
    is_hugo: bool
    evidence: list[str] = field(default_factory=list)
    hugo_config: str | None = None
    content_section: str | None = None
    title: str | None = None


def _classify_hugo(site_dir: Path) -> tuple[bool, str | None, list[str]]:
    """Decide Hugo vs non-Hugo from configuration files and structure."""
    for config_file in HUGO_CONFIG_FILES:
        if (site_dir / config_file).is_file():
            return True, config_file, [f"Hugo configuration observed: {config_file}"]
    if (site_dir / "config").is_dir():
        try:
            nested = [
                item.name
                for item in (site_dir / "config").iterdir()
                if item.is_file() and item.suffix.casefold() in {".toml", ".yaml", ".yml", ".json"}
            ]
        except OSError:
            nested = []
        if nested:
            return True, f"config/{sorted(nested)[0]}", [
                f"Hugo configuration directory observed: config/ ({', '.join(sorted(nested)[:5])})"
            ]
    markers = [name for name in HUGO_CONTENT_MARKERS if (site_dir / name).is_dir()]
    if "content" in markers and "layouts" in markers:
        return True, None, [
            "Hugo structure observed: content/ + layouts/ (no top-level config file)"
        ]
    return False, None, ["No Hugo configuration or structure observed; treated as a non-Hugo site"]


def _content_section(site_dir: Path, *, is_hugo: bool) -> str | None:
    """Authoritative posts/articles section for a Hugo site, if determinable."""
    if not is_hugo:
        return None
    content = site_dir / "content"
    if not content.is_dir():
        return None
    try:
        sections = sorted(
            item.name for item in content.iterdir() if item.is_dir()
        )
    except OSError:
        return None
    for preferred in ("post", "posts", "blog", "articles"):
        if preferred in sections:
            return preferred
    return sections[0] if sections else None


def detect_websites(roots: list[str | Path] | str | Path) -> tuple[list[DetectedWebsite], list[dict[str, str]]]:
    """Discover website workspaces. Returns (websites, diagnostics).

    A missing root produces a diagnostic entry, never an invented list.
    """
    if isinstance(roots, (str, Path)):
        roots = [roots]
    websites: list[DetectedWebsite] = []
    diagnostics: list[dict[str, str]] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            diagnostics.append(
                {"path": str(root_path), "error": "Websites root is missing or not a directory"}
            )
            logger.warning("Websites root unavailable: %s", root_path)
            continue
        try:
            children = sorted(
                path for path in root_path.iterdir() if path.is_dir() and not path.name.startswith(".")
            )
        except OSError as exc:
            diagnostics.append({"path": str(root_path), "error": str(exc)[:300]})
            continue
        for site_dir in children:
            try:
                is_hugo, hugo_config, evidence = _classify_hugo(site_dir)
            except OSError:
                continue
            title = _read_hugo_title(site_dir, hugo_config) if hugo_config and is_hugo else None
            name = _humanize(site_dir.name)
            if title and title.casefold() not in {name.casefold(), site_dir.name.casefold()}:
                display = f"{name} — {title}"
            else:
                display = title or name
            websites.append(
                DetectedWebsite(
                    site_id=f"website-{_slugify(site_dir.name)}",
                    name=display,
                    path=str(site_dir),
                    is_hugo=is_hugo,
                    evidence=evidence,
                    hugo_config=hugo_config,
                    content_section=_content_section(site_dir, is_hugo=is_hugo),
                    title=title,
                )
            )
    return sorted(websites, key=lambda site: site.name.casefold()), diagnostics


def website_read(site: DetectedWebsite, *, running: dict[str, Any] | None = None) -> dict[str, Any]:
    """Display record for one website plus optional managed-server status."""
    from mission_control.core.paths import resolve_executable

    path = Path(site.path)
    available = path.is_dir()
    hugo_available = resolve_executable("hugo") is not None
    launch_supported = bool(site.is_hugo and available and hugo_available)
    running = running or {}
    return {
        "id": site.site_id,
        "name": site.name,
        "path": site.path,
        "is_hugo": site.is_hugo,
        "site_type": "hugo" if site.is_hugo else "static",
        "evidence": list(site.evidence),
        "hugo_config": site.hugo_config,
        "content_section": site.content_section,
        "title": site.title,
        "available": available,
        "launch_supported": launch_supported,
        "hugo_available": hugo_available,
        "running": bool(running.get("alive")),
        "preview_url": running.get("url"),
        "port": running.get("port"),
        "process_id": running.get("process_id"),
    }
