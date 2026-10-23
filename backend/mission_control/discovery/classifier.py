"""Advisory classification based on observable repository evidence.

Classification never asserts that a safe launch command exists. Every result
carries evidence and confidence and remains editable by the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENERATED_NAMES = {
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    "p1-runs",
    "worker-smoke",
}
GENERATED_SUFFIXES = ("-review-pack", "-review-pack-v3", "-bundles", ".egg-info", "-demo")
SOURCE_MARKERS = {
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "setup.py",
    "README.md",
    "readme.md",
    "hugo.toml",
    "bookbuilder.toml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "AGENTS.md",
}
DIRECTORY_MARKERS = {
    "src",
    "tests",
    "docs",
    "content",
    "book",
    "planning",
    "artifacts",
    "experiments",
    "research",
    "chapters",
}


@dataclass(slots=True)
class Classification:
    classification: str
    confidence: float
    evidence: list[str]


def top_level_markers(path: Path) -> set[str]:
    markers: set[str] = set()
    try:
        for entry in path.iterdir():
            if entry.name.lower() in {".git", ".hg", ".svn"}:
                markers.add(entry.name.lower())
            elif entry.is_file():
                markers.add(entry.name)
            elif entry.is_dir() and entry.name.lower() in DIRECTORY_MARKERS:
                markers.add(entry.name)
    except (OSError, PermissionError):
        return markers
    return markers


def _read_text(path: Path, limit: int = 16_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _pyproject_scripts(path: Path) -> list[str]:
    text = _read_text(path)
    if "[project.scripts]" not in text:
        return []
    try:
        section = text.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
    except IndexError:
        return []
    return [line.split("=", 1)[0].strip() for line in section.splitlines() if "=" in line]


def _package_commands(path: Path) -> list[str]:
    try:
        data = json.loads(_read_text(path, 64_000))
    except (json.JSONDecodeError, OSError):
        return []
    commands: list[str] = []
    if isinstance(data, dict):
        bin_field = data.get("bin")
        if isinstance(bin_field, str):
            commands.append(str(data.get("name", "bin")))
        elif isinstance(bin_field, dict):
            commands.extend(str(key) for key in bin_field)
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            commands.extend(
                f"npm run {name}" for name in scripts if name in {"start", "dev", "serve"}
            )
    return commands


def classify(path: Path) -> Classification:
    lower_name = path.name.lower()
    markers = top_level_markers(path)
    evidence: list[str] = []

    if lower_name in GENERATED_NAMES or lower_name.endswith(GENERATED_SUFFIXES):
        evidence.append(f"Name matches a generated/artifact pattern: {path.name}")
        return Classification("generated_artifact", 0.9, evidence)

    if not markers and not (path / ".git").exists():
        return Classification("unknown", 0.2, ["No repository, source or documentation markers found"])

    readme = ""
    for readme_name in ("README.md", "readme.md"):
        readme_path = path / readme_name
        if readme_path.exists():
            readme = _read_text(readme_path).lower()
            evidence.append(f"{readme_name} present")
            break

    pyproject = path / "pyproject.toml"
    package_json = path / "package.json"
    scripts = _pyproject_scripts(pyproject) if pyproject.exists() else []
    commands = _package_commands(package_json) if package_json.exists() else []
    if pyproject.exists():
        evidence.append("pyproject.toml present")
    if package_json.exists():
        evidence.append("package.json present")
    if (path / ".git").exists():
        evidence.append(".git directory present")

    if scripts or commands:
        evidence.append("Declared commands: " + ", ".join(sorted(set(scripts + commands))[:6]))
        evidence.append("A declared command is not a verified launch command")
    if (path / "hugo.toml").exists():
        evidence.append("hugo.toml present")
    if (path / "content" / "books").exists():
        evidence.append("content/books manuscript tree present")
    if (path / "planning").exists():
        evidence.append("planning directory present")
    if (path / "book").exists():
        evidence.append("book directory present")
    if (path / "artifacts").exists():
        evidence.append("artifacts directory present")
    if (path / "experiments").exists():
        evidence.append("experiments directory present")
    if (path / "docker-compose.yml").exists() or (path / "docker-compose.yaml").exists():
        evidence.append("Docker Compose configuration present")

    book_signal = (
        "content/books" in str(path).replace("\\", "/").lower()
        or (path / "content" / "books").exists()
        or "book" in readme[:2000]
        or (path / "book" / "planning").exists()
        or ("chapters" in readme and "manuscript" in readme)
        or "chapter" in readme[:2000] and "book" in readme[:4000]
    )
    research_signal = (
        (path / "artifacts").exists()
        or (path / "experiments").exists()
        or "research" in readme[:3000]
        or "investigation" in readme[:3000]
    )
    if book_signal:
        confidence = 0.94 if (path / "content" / "books").exists() or (path / "book").exists() else 0.8
        return Classification("book", confidence, evidence)
    if (path / "hugo.toml").exists() and (path / "content").exists():
        return Classification("publishing_site", 0.92, evidence)
    if (path / "docker-compose.yml").exists() or (path / "docker-compose.yaml").exists():
        if scripts or commands or "service" in readme[:3000] or "server" in readme[:3000]:
            return Classification("background_service", 0.82, evidence)
    if scripts:
        return Classification("executable_application", 0.85, evidence)
    if commands:
        return Classification("executable_application", 0.72, evidence)
    if lower_name.endswith(("-r1", "-r2", "-experiment")) or re.search(r"-v\d+$", lower_name):
        return Classification("experiment", 0.72, evidence)
    if research_signal:
        return Classification("research_project", 0.78, evidence)
    if pyproject.exists() or package_json.exists():
        return Classification("library", 0.7, evidence)
    if readme and (path / ".git").exists():
        return Classification("supporting_repository", 0.55, evidence)
    if (path / ".git").exists():
        return Classification("unknown", 0.45, evidence)
    return Classification("unknown", 0.3, evidence)


def marker_summary(path: Path) -> dict[str, Any]:
    try:
        entries = sorted(entry.name for entry in path.iterdir())[:50]
    except OSError:
        entries = []
    return {"markers": entries}
