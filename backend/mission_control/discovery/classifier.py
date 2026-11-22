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
    reason: str = ""


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


def _has_source_layout(path: Path) -> list[str]:
    """Structural source-layout markers: the repository builds or runs software."""
    found = []
    for dirname in ("src", "backend", "frontend", "cli", "api", "lib", "bin", "server", "cmd", "pkg", "app"):
        if (path / dirname).is_dir():
            found.append(dirname + "/")
    for filename in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "Makefile", "justfile"):
        if (path / filename).is_file():
            found.append(filename)
    for filename in ("main.py", "cli.py", "server.py", "index.js", "index.ts", "main.go"):
        if (path / "src" / filename).is_file() or (path / filename).is_file():
            found.append(filename)
    return found


def _manuscript_deliverable(path: Path) -> tuple[bool, list[str]]:
    """True when a book manuscript tree is the deliverable, not just a topic.

    README keywords alone never qualify: documentation can discuss any subject,
    including books, while the repository itself builds or runs software.
    """
    if (path / "content" / "books").is_dir():
        return True, ["content/books manuscript tree present"]
    if (path / "bookbuilder.toml").is_file():
        return True, ["bookbuilder.toml present: manuscript build is the deliverable"]
    book_dir = path / "book"
    if book_dir.is_dir() and (book_dir / "planning").is_dir():
        return True, ["book/planning manuscript tree present"]
    chapters = path / "chapters"
    if chapters.is_dir():
        try:
            md_count = sum(1 for entry in chapters.iterdir() if entry.suffix == ".md")
        except OSError:
            md_count = 0
        if md_count >= 3:
            return True, [f"chapters/ holds {md_count} manuscript files"]
    return False, []


def _software_deliverable(
    path: Path, scripts: list[str], commands: list[str], layout: list[str]
) -> tuple[bool, list[str]]:
    """True when the repository builds or runs software of its own."""
    signals = []
    if scripts or commands:
        signals.append("declared runnable entry points")
    if layout:
        signals.append("source layout: " + ", ".join(sorted(set(layout))[:8]))
    return bool(signals), signals


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
        return Classification(
            "unknown",
            0.2,
            ["No repository, source or documentation markers found"],
            reason="No repository, source or documentation markers found; owner review required.",
        )

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

    layout = _has_source_layout(path)
    if layout:
        evidence.append("Source layout present: " + ", ".join(sorted(set(layout))[:8]))
    manuscript, manuscript_evidence = _manuscript_deliverable(path)
    evidence.extend(manuscript_evidence)
    deliverable, _ = _software_deliverable(path, scripts, commands, layout)
    research_signal = (
        (path / "artifacts").exists()
        or (path / "experiments").exists()
        or "research" in readme[:3000]
        or "investigation" in readme[:3000]
    )

    discusses_books = (
        "book" in readme[:2000]
        or ("chapters" in readme and "manuscript" in readme)
        or ("chapter" in readme[:2000] and "book" in readme[:4000])
    )
    if discusses_books and not manuscript:
        # Subject matter is not the deliverable. Software that supports book
        # production (authoring CLIs, workbenches, orchestration) must not be
        # classified as a book because its documentation discusses books.
        evidence.append("README discusses books; treated as subject matter, not the deliverable")

    if manuscript and not deliverable:
        confidence = 0.94 if (path / "content" / "books").exists() or (path / "book").exists() else 0.8
        return Classification(
            "book",
            confidence,
            evidence,
            reason="A manuscript tree is the deliverable and no runnable software entry points were found.",
        )
    if (path / "hugo.toml").exists() and (path / "content").exists():
        return Classification(
            "publishing_site",
            0.92,
            evidence,
            reason="Hugo site with content tree: the deliverable is a published site.",
        )
    if (path / "docker-compose.yml").exists() or (path / "docker-compose.yaml").exists():
        if scripts or commands or "service" in readme[:3000] or "server" in readme[:3000]:
            return Classification(
                "background_service",
                0.82,
                evidence,
                reason="Compose configuration plus service evidence: the deliverable is a running service.",
            )
    if scripts:
        return Classification(
            "executable_application",
            0.85,
            evidence,
            reason="Declared runnable entry points are the deliverable.",
        )
    if commands:
        return Classification(
            "executable_application",
            0.72,
            evidence,
            reason="Package commands are the deliverable.",
        )
    if lower_name.endswith(("-r1", "-r2", "-experiment")) or re.search(r"-v\d+$", lower_name):
        return Classification(
            "experiment",
            0.72,
            evidence,
            reason="Name and layout match a bounded experiment, not a maintained system.",
        )
    if research_signal:
        return Classification(
            "research_project",
            0.78,
            evidence,
            reason="Research artifacts or investigation language with no runnable deliverable found.",
        )
    if pyproject.exists() or package_json.exists():
        return Classification(
            "library",
            0.7,
            evidence,
            reason="Dependency manifest with no runnable entry points: consumed as a library.",
        )
    if readme and (path / ".git").exists():
        return Classification(
            "supporting_repository",
            0.55,
            evidence,
            reason="Versioned repository with documentation but no identified deliverable.",
        )
    if (path / ".git").exists():
        return Classification(
            "unknown",
            0.45,
            evidence,
            reason="Git history exists but no deliverable evidence was found; owner review required.",
        )
    return Classification(
        "unknown",
        0.3,
        evidence,
        reason="No repository, source or documentation markers found; owner review required.",
    )


def marker_summary(path: Path) -> dict[str, Any]:
    try:
        entries = sorted(entry.name for entry in path.iterdir())[:50]
    except OSError:
        entries = []
    return {"markers": entries}
