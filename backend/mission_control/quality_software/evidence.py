"""Bounded, read-only software evidence collector (MC-PROJECTS-QUALITY-02).

Collects a machine-readable manifest for one project workspace: identity,
source/test structure, manifests, docs, interfaces, Git history, Inspect
observations and charter state. Never executes repository scripts; test
execution stays an explicit, separately authorized operation.

Bounds: file inventory caps, excerpt caps, total manifest cap. Generated
files, build artifacts, caches and irrelevant directories are excluded with
the existing discovery policies. Secrets are redacted; private source never
leaves the machine inside an evaluation prompt unless the configured model
route is loopback-local.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.activity_git.service import redact_secrets
from mission_control.models import (
    Application,
    GitCommit,
    GitRepository,
    Project,
    ProjectRepository,
    Repository,
)
from mission_control.quality_software import rubric as _rubric

MAX_FILES = 500
MAX_EXCERPT = 8000
MAX_TOTAL_CHARS = 90_000
MAX_ENTRYPOINTS = 8

#: Windows CreateProcess caps a single command line at ~32k chars and Pi
#: receives the whole prompt via argv. Verified: a 40k prompt fails with
#: FileNotFoundError (WinError 206). Model packages stay well under that.
MAX_PACKAGE_CHARS = 26000

MANIFEST_FILES = {
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "requirements.txt", "setup.py", "setup.cfg", "pom.xml",
    "build.gradle", "Gemfile", "composer.json",
}
TEST_CONFIG_FILES = {
    "pytest.ini", "tox.ini", "jest.config.js", "jest.config.ts",
    "vitest.config.ts", "vitest.config.js", "karma.conf.js",
    "phpunit.xml", "phpunit.xml.dist",
}
CI_PATHS = {
    ".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
    ".circleci/config.yml", "azure-pipelines.yml", "tox.ini",
}
DOC_FILES = {
    "README.md", "readme.md", "AGENTS.md", "DESCRIPTION.md",
    "CHANGELOG.md", "ARCHITECTURE.md", "CONTRIBUTING.md",
}
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", ".next", "coverage", ".coverage", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "target", ".tox", ".eggs",
    "*.egg-info", ".workbench", ".idea", ".vscode", "vendor",
}


def _skip(name: str) -> bool:
    lowered = name.casefold()
    if lowered in SKIP_DIRS:
        return True
    return lowered.endswith(".egg-info")


def _classify_file(rel: str, name: str) -> str:
    """Role of one inventoried file (manifest/config/CI/doc/test/source)."""
    if name in MANIFEST_FILES:
        return "manifest"
    if name in TEST_CONFIG_FILES:
        return "test-config"
    if rel in CI_PATHS or rel.startswith(".github/workflows/"):
        return "ci"
    if name in DOC_FILES:
        return "doc"
    lowered_dir = rel.split("/")[0].lower() if "/" in rel else ""
    if lowered_dir in {"test", "tests", "__tests__"} and Path(name).suffix in {
        ".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java",
    }:
        return "test"
    if Path(name).suffix in {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".md"}:
        lowered = name.lower()
        if "test" in lowered or "spec" in lowered:
            return "test"
    return "source"


def _norm(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return os.path.normcase(os.path.normpath(str(path).strip()))
    except (ValueError, OSError):
        return None


def _excerpt(path: Path, limit: int = MAX_EXCERPT) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""
    redacted, _ = redact_secrets(text)
    return redacted


def _fingerprint(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def collect_evidence(
    session: Session,
    project_id: str,
    *,
    inspect_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Build the evidence manifest. Filesystem reads only; no DB writes."""
    from mission_control.projects.registration import (
        _book_project_ids,  # noqa: SLF001 - shared identity helpers
    )
    from mission_control.quality_software.service import current_charter

    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")
    if project.kind == "book" or project.id in _book_project_ids(session):
        raise ValueError("Book-legacy projects are evaluated by the manuscript system, not here")

    links = session.scalars(
        select(ProjectRepository).where(ProjectRepository.project_id == project_id)
    ).all()
    repos: list[dict[str, Any]] = []
    primary_path: str | None = None
    for link in links:
        repo = session.get(Repository, link.repository_id)
        if repo is None:
            continue
        if link.role == "primary" or primary_path is None:
            primary_path = repo.path
        repos.append(
            {
                "path": repo.path,
                "role": link.role,
                "classification": repo.classification,
                "confidence": repo.confidence,
                "repo_uid": repo.repo_uid or "",
                "is_git": bool(repo.is_git),
                "branch": repo.branch,
                "head": repo.commit_hash,
                "accessible": bool(repo.accessible and Path(repo.path).is_dir()),
            }
        )

    git_info: dict[str, Any] = {"indexed": False}
    commits_30d = 0
    if primary_path:
        key = _norm(primary_path)
        git = next(
            (row for row in session.scalars(select(GitRepository)).all() if _norm(row.path) == key),
            None,
        )
        if git is not None:
            thirty_days_ago = _thirty_days_ago_ts()
            commits_30d = int(
                session.scalar(
                    select(func.count())
                    .select_from(GitCommit)
                    .where(GitCommit.repo_id == git.id, GitCommit.committer_ts >= thirty_days_ago)
                )
                or 0
            )
            recent = session.scalars(
                select(GitCommit.subject)
                .where(GitCommit.repo_id == git.id)
                .order_by(desc(GitCommit.committer_ts))
                .limit(15)
            ).all()
            subjects: list[str] = []
            for subject in recent:
                clean, _ = redact_secrets(str(subject or "")[:160])
                if clean.strip():
                    subjects.append(clean.strip())
            git_info = {
                "indexed": True,
                "repo_id": git.id,
                "repo_uid": git.repo_uid,
                "branch": git.branch,
                "head_sha": git.head_sha,
                "total_commits": git.total_commits,
                "commits_30d": commits_30d,
                "recent_subjects": subjects,
                "backfill_complete": bool(git.backfill_complete),
                "has_agents": bool(git.has_agents),
                "has_description": bool(git.has_description),
                "context_status": git.context_status,
            }

    files: list[dict[str, Any]] = []
    manifests: dict[str, str] = {}
    tests: dict[str, Any] = {"config": [], "dirs": [], "files": 0}
    ci: list[str] = []
    docs: dict[str, Any] = {}
    entrypoints: list[str] = []
    truncated = False
    if primary_path and Path(primary_path).is_dir():
        # os.walk with in-place pruning: never descend into generated,
        # cache, dependency or version-control directories.
        for dirpath, dirnames, filenames in os.walk(primary_path):
            try:
                rel_dir = Path(dirpath).relative_to(primary_path).as_posix()
            except (OSError, ValueError):
                dirnames[:] = []
                continue
            if rel_dir != "." and any(part in SKIP_DIRS or _skip(part) for part in rel_dir.split("/")):
                dirnames[:] = []
                continue
            dirnames[:] = sorted(d for d in dirnames if not _skip(d) and d not in SKIP_DIRS)
            if rel_dir != "." and ".git" in rel_dir.split("/"):
                dirnames[:] = []
                continue
            for name in sorted(filenames):
                if _skip(name):
                    continue
                rel = (rel_dir + "/" + name).lstrip("./") if rel_dir != "." else name
                if len(files) >= MAX_FILES:
                    truncated = True
                    break
                role = _classify_file(rel, name)
                if role == "manifest":
                    manifests[name] = _excerpt(Path(dirpath) / name, MAX_EXCERPT)
                elif role == "test-config":
                    tests["config"].append(rel)
                    manifests[name] = _excerpt(Path(dirpath) / name, MAX_EXCERPT)
                elif role == "ci":
                    ci.append(rel)
                elif role == "doc":
                    if name.lower() == "readme.md":
                        docs["readme"] = _excerpt(Path(dirpath) / name, MAX_EXCERPT)
                    elif name == "AGENTS.md":
                        docs["agents_present"] = True
                    elif name == "DESCRIPTION.md":
                        docs["description_present"] = True
                    elif name == "CHANGELOG.md":
                        docs["changelog_present"] = True
                elif role == "test":
                    tests["files"] += 1
                files.append({"path": rel, "size": _safe_size(Path(dirpath) / name), "role": role})
            if truncated:
                break
        entrypoints = _entrypoints(Path(primary_path), manifests)

    applications = [
        {"id": app.id, "name": app.name}
        for app in session.scalars(select(Application)).all()
        if project_id in (app.related_projects or [])
    ]
    inspect = _inspect_evidence(inspect_dir, primary_path)

    charter = current_charter(session, project_id)
    manifest: dict[str, Any] = {
        "contract": "software-evidence-v1",
        "project": {"id": project.id, "name": project.name, "kind": project.kind},
        "repositories": repos,
        "git": git_info,
        "files": files,
        "file_count": len(files),
        "truncated": truncated,
        "manifests": manifests,
        "dependencies": _declared_dependencies(manifests),
        "tests": tests,
        "ci": sorted(set(ci))[:20],
        "docs": docs,
        "entrypoints": entrypoints[:MAX_ENTRYPOINTS],
        "applications": applications,
        "inspect": inspect,
        "charter": (
            {
                "id": charter["id"],
                "revision": charter["revision"],
                "status": charter["status"],
            }
            if charter
            else None
        ),
        "rubric": {"id": _rubric.RUBRIC_ID, "version": _rubric.RUBRIC_VERSION},
    }
    manifest["evidence"] = _evidence_index(manifest)
    manifest["fingerprint"] = _fingerprint(
        {key: value for key, value in manifest.items() if key != "fingerprint"}
    )
    manifest["size_chars"] = len(json.dumps(manifest))
    if manifest["size_chars"] > MAX_TOTAL_CHARS:
        manifest["truncated_total"] = True
    return manifest


def _split_json_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def build_compact_evidence(
    manifest: dict[str, Any],
    *,
    max_files: int = 100,
    max_caps: int = 40,
    max_opps: int = 20,
    readme_chars: int = 3000,
) -> dict[str, Any]:
    """Bounded evidence summary for model prompts.

    The full manifest stays persisted for audit and freshness; the model
    receives this compact form plus its own evidence index. Validation
    enforces refs against the compact index, so the model can only cite
    evidence it actually saw. Deterministic: every list is sorted and every
    cut is from the tail.
    """
    files = manifest.get("files", []) or []
    by_role: dict[str, int] = {}
    for item in files:
        by_role[str(item.get("role", "source"))] = by_role.get(str(item.get("role", "source")), 0) + 1
    top_dirs: dict[str, int] = {}
    for item in files:
        top = str(item.get("path", "")).split("/")[0]
        if top:
            top_dirs[top] = top_dirs.get(top, 0) + 1
    inspect = manifest.get("inspect", {}) or {}
    caps = (inspect.get("capabilities", []) or [])[:max_caps]
    opps = (inspect.get("opportunities", []) or [])[:max_opps]
    compact = {
        "contract": "software-evidence-compact-v1",
        "project": manifest.get("project", {}),
        "repositories": manifest.get("repositories", []),
        "git": manifest.get("git", {}),
        "manifests": manifest.get("manifests", {}),
        "dependencies": manifest.get("dependencies", []),
        "entrypoints": (manifest.get("entrypoints", []) or [])[:MAX_ENTRYPOINTS],
        "tests": {
            "config": manifest.get("tests", {}).get("config", []),
            "dirs": sorted(manifest.get("tests", {}).get("dirs", [])),
            "test_files": manifest.get("tests", {}).get("files", 0),
        },
        "ci": manifest.get("ci", []),
        "docs": {
            "readme": str((manifest.get("docs", {}) or {}).get("readme", ""))[:readme_chars],
            "agents_present": bool((manifest.get("docs", {}) or {}).get("agents_present", False)),
            "description_present": bool((manifest.get("docs", {}) or {}).get("description_present", False)),
            "changelog_present": bool((manifest.get("docs", {}) or {}).get("changelog_present", False)),
        },
        "structure": {
            "files_total": manifest.get("file_count", len(files)),
            "truncated": True,
            "by_role": by_role,
            "top_dirs": sorted(top_dirs.items(), key=lambda kv: (-kv[1], kv[0]))[:25],
            "sample": [
                {"path": item.get("path"), "role": item.get("role")}
                for item in sorted(files, key=lambda i: str(i.get("path")))[:max_files]
            ],
        },
        "inspect": {
            "available": bool(inspect.get("available", False)),
            "stale_refresh": bool(inspect.get("stale_refresh", False)),
            "capabilities": caps,
            "opportunities": opps,
            "omitted_counts": {
                "capabilities": max(0, len(inspect.get("capabilities", []) or []) - len(caps)),
                "opportunities": max(0, len(inspect.get("opportunities", []) or []) - len(opps)),
            },
            "untested": inspect.get("untested", 0),
            "note": str(inspect.get("note", "")),
        },
        "charter": manifest.get("charter"),
        "rubric": manifest.get("rubric", {}),
        "fingerprint": manifest.get("fingerprint", ""),
    }
    compact["evidence"] = _index_compact(compact)
    return compact


def _index_id(prefix: str, value: str) -> str:
    """Stable, JSON-safe evidence id (no backslashes to survive quoting)."""
    return f"{prefix}:{value.replace(chr(92), '/')}"


def _index_compact(compact: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for repo in compact.get("repositories", []) or []:
        entries.append({"id": _index_id("repo", str(repo.get("path", ""))), "kind": "repository", "ref": str(repo.get("path", ""))})
    git = compact.get("git", {}) or {}
    if git.get("head_sha"):
        entries.append({"id": "git:HEAD", "kind": "git", "ref": str(git["head_sha"])})
    for name in (compact.get("manifests", {}) or {}):
        entries.append({"id": _index_id("manifest", name), "kind": "manifest", "ref": name})
    for path in compact.get("ci", []) or []:
        entries.append({"id": _index_id("ci", path), "kind": "ci", "ref": path})
    for cmd in compact.get("entrypoints", []) or []:
        entries.append({"id": _index_id("entry", str(cmd)), "kind": "entrypoint", "ref": str(cmd)})
    if (compact.get("docs", {}) or {}).get("readme"):
        entries.append({"id": "doc:README.md", "kind": "doc", "ref": "README.md"})
    if (compact.get("docs", {}) or {}).get("agents_present"):
        entries.append({"id": "doc:AGENTS.md", "kind": "doc", "ref": "AGENTS.md"})
    for cap in (compact.get("inspect", {}) or {}).get("capabilities", []) or []:
        entries.append({"id": _index_id("inspect:cap", str(cap.get("id", ""))), "kind": "inspect", "ref": str(cap.get("id"))})
    for opp in (compact.get("inspect", {}) or {}).get("opportunities", []) or []:
        entries.append({"id": _index_id("inspect:opp", str(opp.get("id", ""))), "kind": "inspect", "ref": str(opp.get("id"))})
    charter = compact.get("charter")
    if isinstance(charter, dict) and charter.get("revision") is not None:
        entries.append({"id": _index_id("charter", f"r{charter['revision']}"), "kind": "charter", "ref": str(charter.get("id"))})
    return entries


#: Evidence slice per rubric dimension: focused subsets keep each bounded
#: model call small while the full manifest stays persisted for audit.
DIMENSION_EVIDENCE: dict[str, dict[str, Any]] = {
    "purpose": {"sections": ["project", "repositories", "entrypoints", "docs", "charter", "applications", "inspect_summary"]},
    "correctness": {"sections": ["project", "repositories", "git", "manifests", "entrypoints", "docs", "charter"]},
    "testing": {"sections": ["project", "tests", "ci", "manifests", "entrypoints"]},
    "architecture": {"sections": ["project", "repositories", "manifests", "entrypoints", "dependencies", "structure", "docs"]},
    "maintainability": {"sections": ["project", "structure", "docs", "tests"]},
    "security": {"sections": ["project", "manifests", "dependencies", "entrypoints", "docs", "ci"]},
    "operations": {"sections": ["project", "ci", "manifests", "entrypoints", "docs", "git"]},
    "documentation": {"sections": ["project", "docs", "entrypoints", "repositories"]},
    "usage": {"sections": ["project", "applications", "entrypoints", "inspect_summary", "docs"]},
    "delivery": {"sections": ["project", "git", "ci", "tests", "repositories"]},
}


def slice_for_dimension(compact: dict[str, Any], dim_id: str) -> dict[str, Any]:
    """Project the compact evidence onto one dimension's relevant sections.

    Only present sections are indexed, so validation can only accept
    references the model actually received.
    """
    wanted = set((DIMENSION_EVIDENCE.get(dim_id) or {}).get("sections", []))
    if not wanted:
        wanted = {"project", "repositories", "git"}
    sliced: dict[str, Any] = {"contract": "software-evidence-slice-v1", "dimension": dim_id}
    if "charter" in compact:
        sliced["charter"] = compact["charter"]
    for key in ("project", "repositories", "git", "manifests", "dependencies",
                "entrypoints", "tests", "ci", "docs", "structure", "applications"):
        if key in wanted and key in compact:
            sliced[key] = compact[key]
    if "inspect_summary" in wanted or "inspect" in wanted:
        inspect = compact.get("inspect", {}) or {}
        sliced["inspect"] = {
            "available": bool(inspect.get("available", False)),
            "untested": inspect.get("untested", 0),
            "capabilities": [
                {"id": c.get("id"), "name": c.get("name"), "status": c.get("status")}
                for c in (inspect.get("capabilities", []) or [])[:20]
            ],
            "opportunities": [
                {"id": o.get("id"), "title": o.get("title")}
                for o in (inspect.get("opportunities", []) or [])[:10]
            ],
        }
    sliced["evidence"] = _index_compact(sliced)
    return sliced


def fit_package(package: dict[str, Any], limit: int = MAX_PACKAGE_CHARS) -> dict[str, Any]:
    """Deterministically trim a model package under the Windows argv limit.

    The evidence index is rebuilt after every trim so validation can only
    ever accept references to evidence the model actually received.
    """
    import copy as _copy

    current = _copy.deepcopy(package)
    if _split_json_size(current) <= limit:
        return current
    trimmed = False
    evidence = current.get("evidence", {})
    if isinstance(evidence, dict):
        structure = evidence.get("structure", {})
        if isinstance(structure, dict) and "sample" in structure:
            structure.pop("sample", None)
            trimmed = True
        if _split_json_size(current) > limit:
            inspect = evidence.get("inspect", {})
            if isinstance(inspect, dict):
                inspect["capabilities"] = []
                inspect["opportunities"] = []
                trimmed = True
        if _split_json_size(current) > limit:
            evidence["manifests"] = {}
            trimmed = True
        if _split_json_size(current) > limit:
            docs = evidence.get("docs", {})
            if isinstance(docs, dict):
                docs["readme"] = str(docs.get("readme", ""))[:500]
                trimmed = True
        if _split_json_size(current) > limit:
            evidence["structure"] = {
                "files_total": structure.get("files_total", 0) if isinstance(structure, dict) else 0,
                "truncated": True,
            }
            trimmed = True
        if trimmed:
            evidence["evidence"] = _index_compact(evidence)
            current["truncated_for_model"] = True
    return current


def _declared_dependencies(manifests: dict[str, str]) -> list[str]:
    """Dependency names only (versions are noise for quality judgement)."""
    found: list[str] = []
    package = manifests.get("package.json", "")
    if package:
        try:
            data = json.loads(package)
            if isinstance(data, dict):
                for section in ("dependencies", "devDependencies", "peerDependencies"):
                    deps = data.get(section, {})
                    if isinstance(deps, dict):
                        found.extend(str(name) for name in deps if str(name) not in found)
        except ValueError:
            pass
    pyproject = manifests.get("pyproject.toml", "")
    if pyproject:
        for line in pyproject.splitlines():
            text = line.strip().strip("\"'")
            if text.startswith(("dependencies", "requires-dist")) or (
                text.startswith(("-", "*", ">", "<", "=", "~", "^", " ", "\t")) and len(text) < 80
            ):
                name = re.split(r"[<>=!~\s\[;]+", text.lstrip("- *"), 1)[0].strip("\"' ")
                if name and name not in found and len(name) < 80 and " " not in name:
                    found.append(name)
    return sorted(set(found))[:40]


def _evidence_index(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Stable evidence ids the evaluator must cite (validation enforces)."""
    entries: list[dict[str, str]] = []
    for repo in manifest.get("repositories", []):
        entries.append({"id": _index_id("repo", str(repo["path"])), "kind": "repository", "ref": str(repo["path"])})
    git = manifest.get("git", {})
    if git.get("head_sha"):
        entries.append({"id": "git:HEAD", "kind": "git", "ref": str(git["head_sha"])})
    for name in manifest.get("manifests", {}):
        entries.append({"id": _index_id("manifest", name), "kind": "manifest", "ref": name})
    for path in manifest.get("ci", []):
        entries.append({"id": _index_id("ci", path), "kind": "ci", "ref": path})
    for cmd in manifest.get("entrypoints", []):
        entries.append({"id": _index_id("entry", str(cmd)), "kind": "entrypoint", "ref": str(cmd)})
    if manifest.get("docs", {}).get("readme"):
        entries.append({"id": "doc:README.md", "kind": "doc", "ref": "README.md"})
    if manifest.get("docs", {}).get("agents_present"):
        entries.append({"id": "doc:AGENTS.md", "kind": "doc", "ref": "AGENTS.md"})
    for cap in manifest.get("inspect", {}).get("capabilities", [])[:50]:
        entries.append({"id": _index_id("inspect:cap", str(cap.get("id", ""))), "kind": "inspect", "ref": str(cap.get("id"))})
    for opp in manifest.get("inspect", {}).get("opportunities", [])[:50]:
        entries.append({"id": _index_id("inspect:opp", str(opp.get("id", ""))), "kind": "inspect", "ref": str(opp.get("id"))})
    charter = manifest.get("charter")
    if charter:
        entries.append({"id": _index_id("charter", f"r{charter['revision']}"), "kind": "charter", "ref": str(charter["id"])})
    return entries


def _inspect_evidence(inspect_dir: Path | str | None, repo_path: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "capabilities": [],
        "opportunities": [],
        "untested": 0,
        "note": "No Inspect snapshot published.",
    }
    if not inspect_dir or not repo_path:
        return result
    try:
        from mission_control.inspect_snapshots import get_store, normalize_repository_path

        store = get_store(Path(inspect_dir))
        data, stale = store.view()
    except Exception:
        return result
    if data is None:
        return result
    wanted = normalize_repository_path(repo_path)
    caps = [c for c in data.capabilities if c.get("repository") and normalize_repository_path(_repo_of(c, data)) == wanted]
    opps = [
        o for o in data.opportunities
        if o.get("repository") == wanted or wanted in [normalize_repository_path(p) for p in (o.get("project_ids") or []) if p]
    ]
    untested = sum(1 for c in caps if "test" not in str(c.get("operational_status", "")).lower() and "demonstrat" not in str(c.get("operational_status", "")).lower())
    return {
        "available": True,
        "stale_refresh": stale,
        "matched": True,
        "capabilities": [
            {"id": str(c.get("id")), "name": str(c.get("name", "")), "status": str(c.get("operational_status", ""))}
            for c in caps[:200]
        ],
        "opportunities": [
            {"id": str(o.get("opportunity_id", o.get("title"))), "title": str(o.get("title", ""))}
            for o in opps[:100]
        ],
        "untested": untested,
        "note": "",
    }


def _repo_of(capability: dict[str, Any], data: Any) -> str | None:
    inspect_id = capability.get("repository")
    for project in data.projects:
        if str(project.get("id", "")) == inspect_id:
            return project.get("path")
    return None


def _entrypoints(root: Path, manifests: dict[str, str]) -> list[str]:
    found: list[str] = []
    pyproject = manifests.get("pyproject.toml", "")
    if "[project.scripts]" in pyproject:
        try:
            section = pyproject.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
            found.extend(f"py:{line.split('=')[0].strip()}" for line in section.splitlines() if "=" in line)
        except IndexError:
            pass
    package = manifests.get("package.json", "")
    if package:
        try:
            import json as _json

            data = _json.loads(package)
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            for name in ("start", "dev", "serve", "build", "test"):
                if name in scripts:
                    found.append(f"npm:{name}")
        except ValueError:
            pass
    return found[:MAX_ENTRYPOINTS]


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _thirty_days_ago_ts() -> int:
    import time

    return int(time.time()) - 30 * 86400
