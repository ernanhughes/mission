"""MC-PROJECTS-QUALITY-01 cutover: deterministic auto-registration with owner gates."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.models import (
    GitRepository,
    Project,
    ProjectIdentityDecision,
    ProjectRepository,
    Repository,
)
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import repository_id, seed_defaults
from mission_control.projects import registration


def _database(runtime: RuntimeSettings) -> Database:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    return database


def _repo(
    session,
    path: Path,
    *,
    classification: str = "executable_application",
    confidence: float = 0.85,
    is_git: bool = True,
) -> Repository:
    repo = Repository(
        id=repository_id(str(path)),
        path=str(path),
        name=path.name,
        classification=classification,
        confidence=confidence,
        evidence=["fixture"],
        source_root=str(path.parent),
        is_git=is_git,
        accessible=True,
        candidate=True,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_observed_at="2026-01-02T00:00:00+00:00",
    )
    session.add(repo)
    session.flush()
    return repo


def _git(session, path: Path, uid: str) -> GitRepository:
    import hashlib
    import os as _os

    repo_id = "gitrepo-" + hashlib.sha1(_os.path.normcase(str(path)).encode()).hexdigest()[:16]
    row = GitRepository(
        id=repo_id,
        root_path=str(path.parent),
        path=str(path),
        name=path.name,
        git_dir=str(path / ".git"),
        repo_uid=uid,
        backfill_complete=True,
    )
    session.add(row)
    session.flush()
    return row


def test_preview_splits_eligible_review_and_skipped(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = _database(runtime)
    root = tmp_path / "soft"
    good = root / "good-tool"
    good.mkdir(parents=True)
    (good / "pyproject.toml").write_text("[project]\nname='good-tool'\n", encoding="utf-8")
    vague = root / "vague"
    vague.mkdir()
    missing = root / "gone"
    bookish = root / "manual"
    bookish.mkdir()
    noise = root / "demo-review-pack"
    noise.mkdir()
    try:
        with database.session() as session:
            _repo(session, good)
            _git(session, good, "git-uid-good")
            _repo(session, vague, classification="unknown", confidence=0.3, is_git=False)
            _repo(session, missing, classification="library", confidence=0.7, is_git=False)
            _repo(session, bookish, classification="book", confidence=0.9, is_git=False)
            _repo(session, noise, classification="generated_artifact", confidence=0.9, is_git=False)
        with database.session() as session:
            preview = registration.preview_registration(session, str(root))
        by_path = {item["path"]: item for item in preview["eligible"]}
        assert str(good) in by_path
        assert by_path[str(good)]["repo_uid"] == "git-uid-good"
        review_paths = {item["path"] for item in preview["needs_review"]}
        assert {str(vague), str(missing), str(bookish)} <= review_paths
        skipped = {item["path"]: item for item in preview["skipped"]}
        assert str(noise) in skipped
        assert preview["counts"]["book_legacy_preserved"] >= 3
    finally:
        database.dispose()


def test_apply_requires_confirmation(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            with pytest.raises(Exception):
                registration.apply_registration(session, select_all_eligible=True, confirm=False)
    finally:
        database.dispose()


def test_apply_is_idempotent_and_links_worktrees(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = _database(runtime)
    root = tmp_path / "soft"
    primary = root / "tool"
    primary.mkdir(parents=True)
    worktree = root / "tool-wt"
    worktree.mkdir()
    try:
        with database.session() as session:
            _repo(session, primary)
            _repo(session, worktree)
            _git(session, primary, "git-uid-shared")
            _git(session, worktree, "git-uid-shared")
        with database.session() as session:
            result = registration.apply_registration(
                session, select_all_eligible=True, confirm=True, root=str(root)
            )
        assert result["counts"]["created"] == 1
        project_id = result["created"][0]["project_id"]
        with database.session() as session:
            project = session.get(Project, project_id)
            assert project is not None and project.origin == "auto-discovered"
            links = session.scalars(
                select(ProjectRepository).where(ProjectRepository.project_id == project_id)
            ).all()
            assert {link.role for link in links} == {"primary", "worktree"}
            decisions = session.scalars(select(ProjectIdentityDecision)).all()
            assert len(decisions) == 1
        with database.session() as session:
            again = registration.apply_registration(
                session, select_all_eligible=True, confirm=True, root=str(root)
            )
        assert again["counts"]["created"] == 0
        assert again["counts"]["skipped"] >= 2  # linked primary + worktree companion
    finally:
        database.dispose()


def test_bulk_approval_enables_auto_register(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = _database(runtime)
    root = tmp_path / "soft"
    first = root / "first"
    first.mkdir(parents=True, exist_ok=True)
    try:
        with database.session() as session:
            _repo(session, first)
            registration.apply_registration(
                session,
                select_all_eligible=True,
                confirm=True,
                approve_policy=True,
                root=str(root),
            )
            assert registration.get_policy(session)["auto_register"] is True
        second = root / "second"
        second.mkdir()
        with database.session() as session:
            _repo(session, second)
        with database.session() as session:
            result = registration.auto_register(session, confirm=True)
        assert result["counts"]["created"] == 1
        assert result["created"][0]["path"] == str(second)
    finally:
        database.dispose()


def test_auto_register_refused_without_policy(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            with pytest.raises(Exception):
                registration.auto_register(session, confirm=True)
    finally:
        database.dispose()


def test_rollback_preserves_user_records(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    root = tmp_path / "soft"
    root.mkdir(parents=True, exist_ok=True)
    clean = root / "clean"
    clean.mkdir()
    busy = root / "busy"
    busy.mkdir()
    try:
        with database.session() as session:
            _repo(session, clean)
            _repo(session, busy)
            result = registration.apply_registration(
                session, select_all_eligible=True, confirm=True, root=str(root)
            )
        ids = {item["path"]: item["project_id"] for item in result["created"]}
        with database.session() as session:
            from mission_control.projects.service import create_task
            from mission_control.schemas import TaskCreate

            create_task(session, TaskCreate(project_id=ids[str(busy)], title="Owner task"))
        with database.session() as session:
            report = registration.rollback_cutover(session, confirm=True)
        assert report["counts"] == {"removed": 1, "retained": 1}
        with database.session() as session:
            assert session.get(Project, ids[str(clean)]) is None
            assert session.get(Project, ids[str(busy)]) is not None
    finally:
        database.dispose()


# ------------------------------------------------------------- API wiring


def test_software_inventory_excludes_books(client: TestClient) -> None:
    body = client.get("/api/projects/software").json()
    assert body["total"] == 0
    assert body["items"] == []


def test_identity_endpoints_require_confirmation(client: TestClient) -> None:
    preview = client.get("/api/projects/identity/preview")
    assert preview.status_code == 200
    assert set(preview.json()) >= {"eligible", "needs_review", "skipped", "counts", "policy"}

    denied = client.post("/api/projects/identity/apply", json={"all_eligible": True})
    assert denied.status_code in (400, 422)

    auto = client.post("/api/projects/identity/auto-register", json={"confirm": True})
    assert auto.status_code in (400, 422)

    rollback = client.post("/api/projects/identity/rollback", json={})
    assert rollback.status_code in (400, 422)


def test_cutover_registers_seeded_repository(client: TestClient, tmp_path: Path) -> None:
    repo_dir = tmp_path / "widget"
    repo_dir.mkdir()
    created = client.post(
        "/api/projects",
        json={
            "name": "Widget",
            "description": "Existing curated project.",
            "kind": "supporting",
            "repository_path": str(repo_dir),
        },
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    links = client.get(f"/api/projects/{project_id}/git-links").json()
    assert len(links) == 1
    assert links[0]["path"] == str(repo_dir)
    assert links[0]["git_repo_id"] is None

    import shutil

    shutil.rmtree(repo_dir)
    inventory = client.get("/api/projects/software", params={"missing_only": True}).json()
    assert any(item["id"] == project_id and item["missing"] for item in inventory["items"])
