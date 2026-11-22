"""MC-PROJECTS-QUALITY-01 Phase 1: read-only discovery reconciliation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, shell=False, check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr[:300]}"
    return (result.stdout or "").strip()


def _make_repo(root: Path, name: str, *, readme: str = "# Demo\n") -> Path:
    repo = root / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text(readme, encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = \"demo\"\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.name", "Fixture Author")
    _git(repo, "config", "user.email", "fixture@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat: initial commit", "--no-gpg-sign")
    return repo


def test_reconciliation_is_read_only_and_flags_book_legacy(client: TestClient) -> None:
    before = client.get("/api/projects").json()
    before_ids = {item["id"] for item in before}

    response = client.get("/api/projects/reconciliation", params={"live": False})
    assert response.status_code == 200, response.text
    body = response.json()

    assert set(body) >= {
        "software_root", "root_exists", "discovery_roots", "counts",
        "software_projects", "book_legacy_projects", "unlinked_candidates",
        "missing_paths", "basename_collisions", "shared_repo_uids",
        "applications", "notes",
    }
    # Seeded book manuscripts are preserved as book-legacy, never software.
    legacy_ids = {item["id"] for item in body["book_legacy_projects"]}
    assert {"language", "inference", "math"} <= legacy_ids
    assert all(item["has_book"] for item in body["book_legacy_projects"])
    for item in body["software_projects"]:
        assert not item["has_book"] and item["kind"] != "book"

    # Read-only: no project created, none deleted.
    after = client.get("/api/projects").json()
    assert {item["id"] for item in after} == before_ids

    counts = body["counts"]
    assert counts["projects_total"] == counts["software_projects"] + counts["book_legacy_projects"]
    assert counts["book_legacy_projects"] >= 3


def test_reconciliation_detects_unlinked_live_candidates(
    client: TestClient, tmp_path: Path
) -> None:
    root = tmp_path / "softwareroot"
    root.mkdir(parents=True, exist_ok=True)
    _make_repo(root, "demo-tool")

    response = client.get(
        "/api/projects/reconciliation", params={"root": str(root), "live": True}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["software_root"] == str(root)
    assert body["root_exists"] is True
    assert body["live_scan"] is not None
    assert body["live_scan"]["candidate_count"] >= 1

    paths = [item["path"] for item in body["unlinked_candidates"]]
    assert any(Path(item).name == "demo-tool" for item in paths)

    # Still read-only.
    assert client.get("/api/projects/reconciliation", params={"live": False}).status_code == 200


def test_reconciliation_reports_missing_paths(client: TestClient, tmp_path: Path) -> None:
    present = tmp_path / "transient-repo"
    present.mkdir(parents=True, exist_ok=True)
    created = client.post(
        "/api/projects",
        json={
            "name": "Transient Repo Project",
            "description": "Linked repo is deleted after creation.",
            "kind": "project",
            "repository_path": str(present),
        },
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    import shutil

    shutil.rmtree(present)

    body = client.get("/api/projects/reconciliation", params={"live": False}).json()
    entry = next(p for p in body["software_projects"] if p["id"] == project_id)
    assert entry["missing_paths"], entry
    assert any(
        item["path"] == entry["missing_paths"][0] for item in body["missing_paths"]
    )
