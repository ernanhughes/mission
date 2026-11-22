"""Deterministic software-project registration (MC-PROJECTS-QUALITY-01 cutover).

Automatic registration scales to hundreds of repositories: unambiguous software
repositories register through the approved discovery workflow without per-repo
hand-holding, while ambiguous identities, legacy conflicts and destructive
changes always require explicit owner approval.

Identity rules (no display names, no bare basenames as identity):

- Git repositories identify by ``repo_uid`` (worktree-aware, shared dir).
- Non-Git source projects identify by normalized absolute path.
- Repeated scans and repeated approvals are idempotent via
  ``project_identity_decisions.path_norm`` (unique) plus live link checks.

Every decision is recorded in ``project_identity_decisions`` for audit and
rollback. Missing or inaccessible repositories are reported as unavailable,
never deleted.
"""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import (
    ActivityEvent,
    Application,
    Book,
    Decision,
    GitRepository,
    Project,
    ProjectIdentityDecision,
    ProjectRepository,
    Recommendation,
    Repository,
    Setting,
    Task,
    WorkCheckpoint,
)
from mission_control.persistence.db import now_iso

POLICY_KEY = "project_identity"
SOFTWARE_ROOT_DEFAULT = r"C:\Projects"

#: Classifications that may auto-register. Anything else needs owner review
#: (book/publishing_site/unknown) or is skipped as noise (generated_artifact).
AUTO_CLASSIFICATIONS = {
    "executable_application",
    "background_service",
    "research_project",
    "experiment",
    "library",
    "supporting_repository",
}
REVIEW_CLASSIFICATIONS = {"book", "publishing_site", "unknown"}
SKIP_CLASSIFICATIONS = {"generated_artifact"}

KIND_BY_CLASSIFICATION = {
    "executable_application": "application",
    "background_service": "application",
    "research_project": "research",
    "experiment": "research",
    "library": "supporting",
    "supporting_repository": "supporting",
}

SLUG = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    return SLUG.sub("-", value.strip().lower()).strip("-")[:64] or f"project-{uuid.uuid4().hex[:6]}"


def _norm(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return os.path.normcase(os.path.normpath(str(path).strip()))
    except (ValueError, OSError):
        return None


def _under(path: str, root_norm: str) -> bool:
    key = _norm(path)
    return bool(key) and (key == root_norm or key.startswith(root_norm + os.sep))


def get_policy(session: Session) -> dict[str, Any]:
    setting = session.get(Setting, POLICY_KEY)
    if setting and isinstance(setting.value, dict):
        value = dict(setting.value)
    else:
        value = {}
    return {
        "auto_register": bool(value.get("auto_register", False)),
        "approved_at": value.get("approved_at"),
        "approved_root": value.get("approved_root"),
    }


def set_policy(session: Session, *, auto_register: bool, root: str | None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "auto_register": bool(auto_register),
        "approved_at": now_iso() if auto_register else None,
        "approved_root": root,
    }
    setting = session.get(Setting, POLICY_KEY)
    if setting is None:
        session.add(Setting(key=POLICY_KEY, value=value, updated_at=now_iso()))
    else:
        setting.value = value
        setting.updated_at = now_iso()
    session.flush()
    return get_policy(session)


def _git_uid_by_norm(session: Session) -> dict[str, GitRepository]:
    mapping: dict[str, GitRepository] = {}
    for row in session.scalars(select(GitRepository)).all():
        key = _norm(row.path)
        if key and key not in mapping:
            mapping[key] = row
    return mapping


def _book_project_ids(session: Session) -> set[str]:
    return set(session.scalars(select(Book.project_id)).all())


def _project_id_for(session: Session, name: str, uid: str, taken: set[str]) -> str:
    base = _slugify(name)
    if base and base not in taken and session.get(Project, base) is None:
        taken.add(base)
        return base
    suffix = (uid or uuid.uuid4().hex)[:6].lower() if uid else uuid.uuid4().hex[:6]
    candidate = f"{base}-{suffix}" if base else f"sw-{suffix}"
    index = 2
    while candidate in taken or session.get(Project, candidate) is not None:
        candidate = f"{base}-{suffix}-{index}"
        index += 1
    taken.add(candidate)
    return candidate


def _linked_norms(session: Session) -> set[str]:
    norms: set[str] = set()
    for link in session.scalars(select(ProjectRepository)).all():
        repo = session.get(Repository, link.repository_id)
        if repo is not None:
            key = _norm(repo.path)
            if key:
                norms.add(key)
    return norms


def _decisions_by_norm(session: Session) -> dict[str, ProjectIdentityDecision]:
    return {
        row.path_norm: row
        for row in session.scalars(select(ProjectIdentityDecision)).all()
        if row.path_norm
    }


def preview_registration(session: Session, root: str | None = None) -> dict[str, Any]:
    """Read-only cutover preview. No database writes."""
    root = root or SOFTWARE_ROOT_DEFAULT
    root_norm = _norm(root) or root
    git_by_norm = _git_uid_by_norm(session)
    linked = _linked_norms(session)
    decisions = _decisions_by_norm(session)
    book_ids = _book_project_ids(session)

    repos = [
        repo
        for repo in session.scalars(select(Repository).order_by(Repository.path)).all()
        if _under(repo.path, root_norm)
    ]
    # Group Git-indexed paths by repo_uid to keep worktrees as one identity.
    uid_groups: dict[str, list[Repository]] = {}
    for repo in repos:
        git = git_by_norm.get(_norm(repo.path) or "")
        uid = (git.repo_uid if git else "") or ""
        if uid:
            uid_groups.setdefault(uid, []).append(repo)

    linked_uids = {
        (git_by_norm[key].repo_uid if key in git_by_norm else "")
        for key in linked
    } - {""}

    eligible: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    taken = {row.id for row in session.scalars(select(Project)).all()}
    taken.update(dec.project_id for dec in decisions.values() if dec.project_id)

    # One eligible entry per shared repo_uid: the shortest path is the primary
    # and the rest attach as worktree links. Identity stays uid-based.
    primary_by_uid: dict[str, str] = {}
    for uid, members in uid_groups.items():
        normals = sorted((_norm(item.path) or item.path) for item in members)
        if normals:
            primary_by_uid[uid] = normals[0]

    for repo in repos:
        key = _norm(repo.path) or repo.path
        git = git_by_norm.get(key)
        uid = (git.repo_uid if git else "") or repo.repo_uid or ""
        record = {
            "path": repo.path,
            "name": repo.name,
            "classification": repo.classification,
            "confidence": repo.confidence,
            "evidence": list(repo.evidence or [])[:10],
            "repo_uid": uid,
            "is_git": bool(repo.is_git or git is not None),
        }
        if key in linked or uid in linked_uids:
            skipped.append({**record, "reason": "already linked to a project workspace"})
            continue
        if uid and uid in primary_by_uid and key != primary_by_uid[uid]:
            skipped.append(
                {**record, "reason": f"worktree of {primary_by_uid[uid]}; registers with the primary"}
            )
            continue
        existing = decisions.get(key)
        if existing is not None and existing.decision in {"auto_registered", "approved"}:
            live = session.get(Project, existing.project_id) if existing.project_id else None
            if live is not None and key in linked:
                skipped.append({**record, "reason": "already registered by a prior decision"})
                continue
        if repo.classification in SKIP_CLASSIFICATIONS:
            skipped.append({**record, "reason": f"generated noise ({repo.classification}); never registered"})
            continue
        if not Path(repo.path).is_dir():
            needs_review.append({**record, "reason": "repository path is missing; preserved as unavailable, never auto-registered"})
            continue
        if repo.classification in REVIEW_CLASSIFICATIONS or repo.confidence < 0.4:
            book_hint = (
                "book-legacy domain owns manuscript identity; owner decides"
                if repo.classification == "book"
                else "uncertain classification; owner review required"
            )
            needs_review.append({**record, "reason": book_hint})
            continue
        companions = [item for item in uid_groups.get(uid, []) if _norm(item.path) != key] if uid else []
        links = [{"path": repo.path, "role": "primary"}]
        for other in companions:
            other_key = _norm(other.path) or other.path
            if other_key not in linked and Path(other.path).is_dir():
                links.append({"path": other.path, "role": "worktree"})
        kind = KIND_BY_CLASSIFICATION.get(repo.classification, "project")
        app_match = next(
            (
                app.id
                for app in session.scalars(select(Application)).all()
                if _norm(app.repository_path) == key
            ),
            None,
        )
        eligible.append(
            {
                **record,
                "kind": kind,
                "project_id": _project_id_for(session, repo.name, uid, taken),
                "links": links,
                "application_id": app_match,
            }
        )

    return {
        "root": root,
        "policy": get_policy(session),
        "counts": {
            "eligible": len(eligible),
            "needs_review": len(needs_review),
            "skipped": len(skipped),
            "repositories": len(repos),
            "book_legacy_preserved": sum(
                1 for row in session.scalars(select(Project)).all()
                if row.kind == "book" or row.id in book_ids
            ),
        },
        "eligible": sorted(eligible, key=lambda item: item["path"].casefold()),
        "needs_review": sorted(needs_review, key=lambda item: item["path"].casefold()),
        "skipped": sorted(skipped, key=lambda item: item["path"].casefold()),
        "notes": [
            "Identity is repo_uid for Git checkouts, normalized path otherwise; basenames are never identity.",
            "Worktrees sharing one repo_uid register as a single project with linked worktree repositories.",
            "Book-legacy projects are preserved and excluded; manuscript identity stays with Books.",
            "Missing paths are held for review and reported as unavailable, never deleted.",
        ],
    }


def backup_database(db_path: Path, backup_dir: Path) -> Path | None:
    """Online SQLite backup before the first production cutover. Returns the backup path."""
    try:
        source = Path(db_path)
        if not source.is_file():
            return None
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = backup_dir / f"pre-cutover-{stamp}.db"
        with sqlite3.connect(str(source)) as src, sqlite3.connect(str(dest)) as dst:
            src.backup(dst)
        return dest
    except OSError:
        return None


def apply_registration(
    session: Session,
    *,
    paths: list[str] | None = None,
    select_all_eligible: bool = False,
    confirm: bool = False,
    approve_policy: bool = False,
    root: str | None = None,
    backup_path: Path | None = None,
) -> dict[str, Any]:
    """Register software projects. Requires explicit ``confirm=True``. Idempotent."""
    if not confirm:
        raise ValidationProblem("Cutover requires explicit confirmation (confirm: true).")
    preview = preview_registration(session, root)
    wanted: set[str] = set()
    if select_all_eligible:
        wanted = {_norm(item["path"]) or item["path"] for item in preview["eligible"]}
    for raw in paths or []:
        key = _norm(raw)
        if key:
            wanted.add(key)
    if not wanted:
        if paths:
            raise ValidationProblem("No eligible repositories selected.")
        # Idempotent re-run: nothing left to register; report the skip state.
        already = [
            {"path": item["path"], "reason": item.get("reason", "not eligible")}
            for item in [*preview["skipped"], *preview["needs_review"]]
        ]
        return {
            "root": preview["root"],
            "created": [],
            "skipped": sorted(already, key=lambda item: item["path"].casefold()),
            "counts": {"created": 0, "skipped": len(already)},
            "policy": preview["policy"],
            "backup": str(backup_path) if backup_path else None,
        }

    by_norm = {_norm(item["path"]) or item["path"]: item for item in preview["eligible"]}
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for key in sorted(wanted):
        item = by_norm.get(key)
        if item is None:
            skipped.append({"path": key, "reason": "not eligible (review queue, already linked, or unknown path)"})
            continue
        repo = session.scalar(select(Repository).where(Repository.path == item["path"]))
        if repo is None:
            skipped.append({"path": item["path"], "reason": "repository record vanished; rescan first"})
            continue
        decision = session.scalar(
            select(ProjectIdentityDecision).where(ProjectIdentityDecision.path_norm == key)
        )
        if decision is not None and decision.decision in {"auto_registered", "approved"}:
            live = session.get(Project, decision.project_id) if decision.project_id else None
            if live is not None and key in _linked_norms(session):
                skipped.append({"path": item["path"], "reason": "already registered (idempotent skip)"})
                continue
        project = session.get(Project, item["project_id"])
        if project is None:
            project = Project(
                id=item["project_id"],
                name=item["name"],
                description=f"Software workspace for {item['path']}. Purpose charter pending.",
                kind=item["kind"],
                status="active",
                origin="auto-discovered",
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(project)
            session.flush()
        for link in item["links"]:
            target = session.scalar(select(Repository).where(Repository.path == link["path"]))
            if target is None:
                continue
            if item["repo_uid"]:
                target.repo_uid = item["repo_uid"]
            if session.get(ProjectRepository, (project.id, target.id)) is None:
                session.add(
                    ProjectRepository(
                        project_id=project.id, repository_id=target.id, role=link["role"]
                    )
                )
        if item.get("application_id"):
            app = session.get(Application, item["application_id"])
            if app is not None and project.id not in (app.related_projects or []):
                app.related_projects = [*(app.related_projects or []), project.id]
                app.updated_at = now_iso()
        if decision is None:
            session.add(
                ProjectIdentityDecision(
                    id=f"pid-{uuid.uuid4().hex[:16]}",
                    repo_uid=item.get("repo_uid") or "",
                    path=item["path"],
                    path_norm=key,
                    project_id=project.id,
                    decision="approved" if paths else "auto_registered",
                    reason="; ".join((item.get("classification") or "", "owner bulk approval" if paths else "approved policy")),
                    created_at=now_iso(),
                )
            )
        else:
            decision.project_id = project.id
            decision.decision = "approved" if paths else "auto_registered"
            decision.reason = "re-applied after missing link"
        created.append(
            {"project_id": project.id, "path": item["path"], "kind": item["kind"], "links": item["links"]}
        )
    session.flush()
    policy = get_policy(session)
    if approve_policy and created:
        policy = set_policy(session, auto_register=True, root=preview["root"])
    if created:
        record_activity(
            session,
            event_type="system",
            title=f"Registered {len(created)} software project workspaces",
            detail="Deterministic cutover registration; ambiguous identities held for review.",
            source="mission-control",
            provenance="user",
            metadata={"projects": [item["project_id"] for item in created][:50]},
        )
        session.flush()
    return {
        "root": preview["root"],
        "created": created,
        "skipped": skipped,
        "counts": {"created": len(created), "skipped": len(skipped)},
        "policy": policy,
        "backup": str(backup_path) if backup_path else None,
    }


def auto_register(session: Session, *, confirm: bool = False, root: str | None = None) -> dict[str, Any]:
    """Register currently-eligible repositories under the approved policy.

    Explicit endpoint (never hidden inside scans). Requires the policy to be
    enabled and explicit confirmation.
    """
    policy = get_policy(session)
    if not policy.get("auto_register"):
        raise ValidationProblem("Automatic registration is not approved. Approve the bulk inventory first.")
    return apply_registration(
        session, select_all_eligible=True, confirm=confirm, root=root or policy.get("approved_root")
    )


def rollback_cutover(session: Session, *, confirm: bool = False) -> dict[str, Any]:
    """Remove pristine auto-registered projects; never lose user records.

    Projects with checkpoints, tasks, decisions, recommendations or activity
    are retained and reported. Decision rows are marked ``rolled_back``.
    """
    if not confirm:
        raise ValidationProblem("Rollback requires explicit confirmation (confirm: true).")
    removed: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for decision in session.scalars(select(ProjectIdentityDecision)).all():
        if decision.decision not in {"auto_registered", "approved"}:
            continue
        project = session.get(Project, decision.project_id) if decision.project_id else None
        if project is None:
            decision.decision = "rolled_back"
            continue
        if project.origin != "auto-discovered":
            retained.append({"project_id": project.id, "reason": "origin changed by owner; kept"})
            continue
        user_content = (
            session.scalar(select(func.count()).select_from(WorkCheckpoint).where(WorkCheckpoint.project_id == project.id)) or 0
        ) + (
            session.scalar(select(func.count()).select_from(Task).where(Task.project_id == project.id)) or 0
        ) + (
            session.scalar(select(func.count()).select_from(Decision).where(Decision.project_id == project.id)) or 0
        ) + (
            session.scalar(select(func.count()).select_from(Recommendation).where(Recommendation.project_id == project.id)) or 0
        ) + (
            session.scalar(select(func.count()).select_from(ActivityEvent).where(ActivityEvent.project_id == project.id)) or 0
        )
        if user_content:
            retained.append({"project_id": project.id, "reason": f"has {int(user_content)} user records; kept"})
            continue
        # Explicit bulk delete first: deterministic order, no reliance on
        # unit-of-work delete ordering (DB-level ON DELETE CASCADE also holds).
        session.execute(
            sa_delete(ProjectRepository).where(ProjectRepository.project_id == project.id)
        )
        session.delete(project)
        decision.decision = "rolled_back"
        removed.append({"project_id": project.id, "path": decision.path})
    session.flush()
    if removed:
        record_activity(
            session,
            event_type="system",
            title=f"Rolled back {len(removed)} auto-registered projects",
            detail="Pristine cutover projects removed; user records preserved.",
            source="mission-control",
            provenance="user",
        )
        session.flush()
    return {"removed": removed, "retained": retained, "counts": {"removed": len(removed), "retained": len(retained)}}


def project_git_links(session: Session, project_id: str) -> list[dict[str, Any]]:
    """Git-indexed repositories backing one project, matched by normalized path."""
    from mission_control.models import GitReview

    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    links = session.scalars(
        select(ProjectRepository).where(ProjectRepository.project_id == project_id)
    ).all()
    rows: list[dict[str, Any]] = []
    for link in links:
        repo = session.get(Repository, link.repository_id)
        if repo is None:
            continue
        key = _norm(repo.path)
        git = next(
            (
                row
                for row in session.scalars(select(GitRepository)).all()
                if _norm(row.path) == key
            ),
            None,
        )
        latest_review = None
        if git is not None:
            latest_review = session.scalar(
                select(GitReview)
                .where(GitReview.repo_id == git.id)
                .order_by(GitReview.created_at.desc())
            )
        rows.append(
            {
                "repository_id": repo.id,
                "path": repo.path,
                "role": link.role,
                "classification": repo.classification,
                "accessible": bool(repo.accessible and Path(repo.path).is_dir()),
                "git_repo_id": git.id if git else None,
                "repo_uid": (git.repo_uid if git else "") or repo.repo_uid or "",
                "branch": (git.branch if git else None) or repo.branch,
                "head_sha": git.head_sha if git else repo.commit_hash,
                "total_commits": git.total_commits if git else 0,
                "backfill_complete": bool(git.backfill_complete) if git else True,
                "has_agents": bool(git.has_agents) if git else False,
                "has_description": bool(git.has_description) if git else False,
                "context_status": git.context_status if git else "missing",
                "latest_review_status": latest_review.status if latest_review else None,
                "latest_review_verdict": latest_review.verdict if latest_review else None,
            }
        )
    return sorted(rows, key=lambda item: (item["role"] != "primary", item["path"].casefold()))


def software_inventory(
    session: Session,
    *,
    search: str | None = None,
    classification: str | None = None,
    attention_only: bool = False,
    missing_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[dict[str, Any]]]:
    """Paginated software workspace inventory. Book-legacy projects excluded."""
    from mission_control.projects.service import project_read

    book_ids = _book_project_ids(session)
    git_by_norm = _git_uid_by_norm(session)
    rows: list[dict[str, Any]] = []
    for project in session.scalars(select(Project).order_by(Project.name)).all():
        if project.kind == "book" or project.id in book_ids:
            continue
        base = project_read(session, project)
        repos = base.repositories
        primary = next((repo for repo in repos if getattr(repo, "role", "") == "primary"), repos[0] if repos else None)
        missing = [repo for repo in repos if not Path(repo.path).is_dir()]
        git = git_by_norm.get(_norm(primary.path) if primary else None) if primary else None
        row = {
            "id": base.id,
            "name": base.name,
            "description": base.description,
            "kind": base.kind,
            "status": base.status,
            "pinned": base.pinned,
            "archived": base.archived,
            "origin": base.origin,
            "priority": base.priority,
            "classification": primary.classification if primary else "unknown",
            "confidence": primary.confidence if primary else 0.0,
            "path": primary.path if primary else None,
            "repository_count": len(repos),
            "repo_uid": (git.repo_uid if git else "") or (primary.repo_uid if primary else "") or "",
            "branch": (git.branch if git else None) or (primary.branch if primary else None),
            "commit_hash": (git.head_sha if git else None) or (primary.commit_hash if primary else None),
            "last_commit_at": primary.last_commit_at if primary else None,
            "last_observed_at": primary.last_observed_at if primary else None,
            "accessible": all(Path(repo.path).is_dir() and repo.accessible for repo in repos) if repos else False,
            "missing": bool(missing),
            "stale": bool(
                (git is not None and not git.backfill_complete)
                or (primary is not None and not primary.last_observed_at)
            ),
            "applications": base.applications,
            "open_task_count": base.open_task_count,
            "pending_recommendation_count": base.pending_recommendation_count,
            "needs_attention": bool(base.open_task_count or base.pending_recommendation_count),
            "quality_state": "unassessed",
            "current_milestone": base.current_milestone,
            "next_action": base.next_action,
            "updated_at": base.updated_at,
        }
        rows.append(row)
    if search:
        needle = search.casefold()
        rows = [
            row for row in rows
            if needle in (row["name"] or "").casefold()
            or needle in (row["description"] or "").casefold()
            or needle in (row["path"] or "").casefold()
        ]
    if classification:
        rows = [row for row in rows if row["classification"] == classification]
    if attention_only:
        rows = [row for row in rows if row["needs_attention"]]
    if missing_only:
        rows = [row for row in rows if row["missing"]]
    total = len(rows)
    return total, rows[max(offset, 0):max(offset, 0) + min(max(limit, 1), 200)]
