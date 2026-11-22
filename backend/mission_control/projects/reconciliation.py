"""Read-only software-project discovery reconciliation (MC-PROJECTS-QUALITY-01 Phase 1).

Compares the desired software-project inventory under a discovery root
(default ``C:\\Projects``) against Mission Control's persisted state:

- ``Project`` / ``Book`` / ``ProjectRepository`` / ``Repository``
- ``GitRepository`` / ``GitCommit`` (worktree-aware ``repo_uid`` identity)
- ``Application`` registry (``repository_path`` links)

The report never writes to the database, never creates projects and never
starts model calls. An optional bounded live scan reuses
``discovery.scanner.scan_roots`` (read-only, symlink-protected) to surface
filesystem candidates that are not yet indexed. Identity cutover is
explicitly out of scope: this report is the evidence reviewed *before* any
cutover is applied.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mission_control.models import (
    Application,
    Book,
    DiscoveryRoot,
    GitRepository,
    Project,
    ProjectRepository,
    Repository,
    Setting,
)

DEFAULT_SOFTWARE_ROOT = r"C:\Projects"


def _norm(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return os.path.normcase(os.path.normpath(path.strip()))
    except (ValueError, OSError):
        return None


def _basename(path: str) -> str:
    return Path(path).name.casefold()


def _default_root(session: Session) -> str | None:
    if Path(DEFAULT_SOFTWARE_ROOT).is_dir():
        return DEFAULT_SOFTWARE_ROOT
    row = session.scalar(
        select(DiscoveryRoot)
        .where(DiscoveryRoot.enabled.is_(True))
        .order_by(DiscoveryRoot.path)
    )
    return row.path if row else None


def _discovery_exclusions(session: Session) -> list[str]:
    setting = session.get(Setting, "discovery")
    if setting and isinstance(setting.value, dict):
        exclusions = setting.value.get("exclusions", [])
        if isinstance(exclusions, list):
            return [str(item) for item in exclusions if str(item).strip()]
    return []


def _live_candidates(root: str, exclusions: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bounded read-only filesystem scan. Never writes to the database."""
    from mission_control.discovery.scanner import scan_roots

    result = scan_roots(
        [root],
        exclusion_patterns=exclusions,
        max_depth=1,
        max_candidates=500,
        timeout_seconds=60.0,
        git_timeout_seconds=2.0,
    )
    candidates = [
        {
            "path": item.path,
            "name": item.name,
            "classification": item.classification,
            "confidence": item.confidence,
            "evidence": list(item.evidence[:10]),
            "is_git": item.is_git,
            "accessible": item.accessible,
            "source_root": item.source_root,
        }
        for item in result.candidates
    ]
    scan = {
        "candidate_count": len(candidates),
        "scanned_directories": result.scanned_directories,
        "elapsed_seconds": result.elapsed_seconds,
        "truncated": result.truncated,
        "cancelled": result.cancelled,
        "excluded_count": result.excluded_count,
        "errors": result.errors[:20],
    }
    return candidates, scan


def build_reconciliation(
    session: Session,
    *,
    software_root: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    """Build the read-only reconciliation report. No database writes."""
    root = software_root or _default_root(session)
    root_norm = _norm(root) if root else None
    root_exists = bool(root and Path(root).is_dir())
    root_row = session.get(DiscoveryRoot, root) if root else None

    roots = [
        {
            "path": row.path,
            "enabled": bool(row.enabled),
            "git_enabled": bool(row.git_enabled),
            "category": row.category or "",
            "display_name": row.display_name or "",
        }
        for row in session.scalars(select(DiscoveryRoot).order_by(DiscoveryRoot.path)).all()
    ]

    projects = session.scalars(select(Project).order_by(Project.id)).all()
    book_project_ids = set(
        session.scalars(select(Book.project_id)).all()
    )

    project_entries: list[dict[str, Any]] = []
    software_projects: list[dict[str, Any]] = []
    book_legacy_projects: list[dict[str, Any]] = []
    for project in projects:
        links = session.scalars(
            select(ProjectRepository).where(ProjectRepository.project_id == project.id)
        ).all()
        repo_paths: list[str] = []
        missing: list[str] = []
        for link in links:
            repo = session.get(Repository, link.repository_id)
            if repo is None:
                missing.append(f"<dangling repository id {link.repository_id}>")
                continue
            repo_paths.append(repo.path)
            if not Path(repo.path).is_dir():
                missing.append(repo.path)
        entry = {
            "id": project.id,
            "name": project.name,
            "kind": project.kind,
            "status": project.status,
            "archived": bool(project.archived),
            "has_book": project.id in book_project_ids,
            "repository_paths": sorted(repo_paths),
            "missing_paths": sorted(missing),
        }
        project_entries.append(entry)
        if project.kind == "book" or project.id in book_project_ids:
            book_legacy_projects.append(entry)
        else:
            software_projects.append(entry)

    repositories = session.scalars(select(Repository).order_by(Repository.path)).all()
    repo_by_norm: dict[str, Any] = {}
    for repo in repositories:
        key = _norm(repo.path)
        if key:
            repo_by_norm[key] = repo

    git_repos = session.scalars(select(GitRepository).order_by(GitRepository.path)).all()

    applications = session.scalars(select(Application).order_by(Application.id)).all()
    app_entries = [
        {
            "id": app.id,
            "name": app.name,
            "repository_path": app.repository_path,
            "enabled": bool(app.enabled),
            "related_projects": list(app.related_projects or []),
        }
        for app in applications
    ]
    app_path_norms = {_norm(app.repository_path) for app in applications if _norm(app.repository_path)}

    # Basename collisions: same directory name, different normalized paths.
    # Identity must never rely on basename alone; collisions are reported.
    by_basename: dict[str, set[str]] = {}
    for path in [repo.path for repo in repositories] + [row.path for row in git_repos]:
        by_basename.setdefault(_basename(path), set()).add(_norm(path) or path)
    basename_collisions = [
        {"basename": name, "paths": sorted(paths)}
        for name, paths in sorted(by_basename.items())
        if len(paths) > 1
    ]

    # Shared repo_uid groups: worktrees / nested checkouts of one repository.
    by_uid: dict[str, set[str]] = {}
    for row in git_repos:
        if row.repo_uid:
            by_uid.setdefault(row.repo_uid, set()).add(row.path)
    shared_repo_uids = [
        {"repo_uid": uid, "paths": sorted(paths)}
        for uid, paths in sorted(by_uid.items())
        if len(paths) > 1
    ]

    missing_paths: list[dict[str, str]] = []
    for entry in project_entries:
        for path in entry["missing_paths"]:
            missing_paths.append({"path": path, "reason": "project-linked repository path is unavailable"})
    for row in git_repos:
        if not row.accessible or not Path(row.path).is_dir():
            missing_paths.append(
                {"path": row.path, "reason": "git-indexed repository is inaccessible or missing"}
            )

    under_root_repos = [
        repo
        for repo in repositories
        if root_norm and (_norm(repo.path) == root_norm or (_norm(repo.path) or "").startswith(root_norm + os.sep))
    ]
    git_uid_by_norm = {_norm(row.path): row.repo_uid for row in git_repos if row.repo_uid}
    linked_repo_norms = {
        _norm(session.get(Repository, link.repository_id).path)
        for link in session.scalars(select(ProjectRepository)).all()
        if session.get(Repository, link.repository_id) is not None
    }
    linked_repo_norms.discard(None)

    unlinked = [
        {
            "path": repo.path,
            "name": repo.name,
            "classification": repo.classification,
            "confidence": repo.confidence,
            "source": "indexed",
            "repo_uid": git_uid_by_norm.get(_norm(repo.path) or "") or "",
            "git_indexed": any(
                (_norm(row.path) == _norm(repo.path)) for row in git_repos
            ),
            "application_linked": _norm(repo.path) in app_path_norms,
        }
        for repo in under_root_repos
        if _norm(repo.path) not in linked_repo_norms and _norm(repo.path) not in app_path_norms
    ]

    live_scan: dict[str, Any] | None = None
    if live and root_exists and root:
        candidates, scan = _live_candidates(root, _discovery_exclusions(session))
        live_scan = {"root": root, **scan}
        indexed_norms = {_norm(repo.path) for repo in repositories}
        for candidate in candidates:
            key = _norm(candidate["path"])
            if key in indexed_norms or key in linked_repo_norms or key in app_path_norms:
                candidate["linked"] = True
                continue
            candidate["linked"] = False
            unlinked.append(
                {
                    "path": candidate["path"],
                    "name": candidate["name"],
                    "classification": candidate["classification"],
                    "confidence": candidate["confidence"],
                    "source": "live-scan",
                    "git_indexed": False,
                    "application_linked": False,
                }
            )
        live_scan["unindexed_candidates"] = sum(
            1 for item in candidates if not item.get("linked")
        )

    backfill_pending = int(
        session.scalar(
            select(func.count(GitRepository.id)).where(GitRepository.backfill_complete.is_(False))
        )
        or 0
    )
    never_observed = int(
        session.scalar(
            select(func.count(Repository.id)).where(Repository.last_observed_at.is_(None))
        )
        or 0
    )

    notes = [
        "Book-legacy projects keep their records and foreign keys; they are listed separately and excluded from the software-project presentation.",
        "Projects are keyed by Mission Control id; repositories by normalized path and Git repo_uid. Directory basenames are reported only to surface collisions, never as identity.",
        "Unindexed live-scan candidates require an explicit cutover step; this report creates nothing.",
        "Application launch definitions are never created by discovery.",
    ]
    if live_scan and live_scan.get("truncated"):
        notes.append("Live scan hit its bound (time or candidate cap); counts are partial.")
    if backfill_pending:
        notes.append(f"Git backfill pending for {backfill_pending} repositories; commit counts may grow.")

    return {
        "software_root": root,
        "root_exists": root_exists,
        "root_enabled": bool(root_row.enabled) if root_row else None,
        "discovery_roots": roots,
        "counts": {
            "projects_total": len(project_entries),
            "software_projects": len(software_projects),
            "book_legacy_projects": len(book_legacy_projects),
            "repositories_total": len(repositories),
            "repositories_under_root": len(under_root_repos),
            "git_repositories_total": len(git_repos),
            "applications_total": len(app_entries),
            "unlinked_candidates": len(unlinked),
            "missing_paths": len(missing_paths),
            "basename_collisions": len(basename_collisions),
            "shared_repo_uids": len(shared_repo_uids),
            "git_backfill_pending": backfill_pending,
            "repositories_never_observed": never_observed,
        },
        "software_projects": software_projects,
        "book_legacy_projects": book_legacy_projects,
        "unlinked_candidates": sorted(unlinked, key=lambda item: item["path"].casefold()),
        "missing_paths": sorted(missing_paths, key=lambda item: item["path"].casefold()),
        "basename_collisions": basename_collisions,
        "shared_repo_uids": shared_repo_uids,
        "applications": app_entries,
        "live_scan": live_scan,
        "notes": notes,
    }
