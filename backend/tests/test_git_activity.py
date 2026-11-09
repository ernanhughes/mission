"""MC-ACTIVITY-01 qualification: fixture-repo tests for the Git activity index."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, shell=False, check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr[:500]}"
    return (result.stdout or "").strip()


def _make_repo(base: Path, name: str) -> Path:
    repo = base / name
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Fixture Author")
    _git(repo, "config", "user.email", "fixture@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit(repo: Path, filename: str, content: str, message: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message, "--no-gpg-sign")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    root.mkdir(parents=True, exist_ok=True)
    repo = _make_repo(root, "demo")
    _commit(repo, "app.py", "print('hello')\n", "feat: initial commit")
    _commit(repo, "app.py", "print('hello world')\n", "fix: greet the world")
    (repo / "AGENTS.md").write_text("# Agents\n- Run pytest\n", encoding="utf-8")
    (repo / "DESCRIPTION.md").write_text("# Demo\nA fixture project.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "docs: add project context", "--no-gpg-sign")
    return root


def _isolate_roots(client: TestClient, git_root: Path) -> None:
    for existing in client.get("/api/git-activity/roots").json():
        client.delete(f"/api/git-activity/roots?path={existing['path']}&retain_history=false")
    response = client.post("/api/git-activity/roots", json={"path": str(git_root), "name": "Fixtures", "category": "software"})
    assert response.status_code == 201, response.text


def test_roots_add_and_validation(client: TestClient, tmp_path: Path, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    body = client.get("/api/git-activity/roots").json()
    assert any(row["path"] == str(git_root) for row in body)
    found = next(row for row in body if row["path"] == str(git_root))
    assert found["name"] == "Fixtures"
    assert found["git_enabled"] is True

    bad = client.post("/api/git-activity/roots", json={"path": str(tmp_path / "missing")})
    assert bad.status_code in (400, 422)

    roots = client.get("/api/git-activity/roots").json()
    assert any(row["path"] == str(git_root) for row in roots)


def test_scan_indexes_commits_and_timeline(client: TestClient, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    response = client.post("/api/git-activity/scan")
    assert response.status_code == 202, response.text
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        status = client.get("/api/git-activity/scan").json()
        if not status["running"]:
            break
        time.sleep(0.5)
    assert status["status"] == "complete", status

    repos = client.get("/api/git-activity/repos").json()
    assert len(repos) == 1, repos
    assert repos[0]["total_commits"] >= 3
    assert repos[0]["has_agents"] is True
    assert repos[0]["has_description"] is True

    timeline = client.get("/api/git-activity/timeline", params={"preset": "30d", "limit": 50}).json()
    assert timeline["total"] >= 3, timeline
    assert timeline["items"][0]["committer_ts"] >= timeline["items"][-1]["committer_ts"]
    sha = timeline["items"][0]["sha"]
    repo_id = timeline["items"][0]["repo_id"]

    detail = client.get(f"/api/git-activity/commits/{repo_id}/{sha}").json()
    assert detail["commit"]["sha"] == sha

    diff = client.get(f"/api/git-activity/commits/{repo_id}/{sha}/diff").json()
    assert "patch" in diff and "fingerprint" in diff

    prompt = client.get(f"/api/git-activity/commits/{repo_id}/{sha}/prompt").json()
    assert "Markdown" in prompt["markdown"] or "Review objective" in prompt["markdown"]
    assert prompt["size_chars"] > 500
    assert "diff_hash" in prompt

    # Timezone offsets must be preserved from Git; placeholders are never stored.
    assert timeline["items"], timeline
    import re as _re
    for item in timeline["items"]:
        assert _re.match(r"^([+-]\d{2}:\d{2})?$", item["committer_tz"] or ""), item["committer_tz"]

    summary = client.get("/api/git-activity/summary").json()
    assert summary["commits_indexed"] >= 3
    assert summary["repos_indexed"] >= 1


def test_incremental_noop_and_new_commit(client: TestClient, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    import time

    def _wait() -> dict:
        deadline = time.time() + 60
        while time.time() < deadline:
            status = client.get("/api/git-activity/scan").json()
            if not status["running"]:
                return status
            time.sleep(0.5)
        raise AssertionError("scan did not finish")

    first = _wait()
    assert first["status"] == "complete"
    before = client.get("/api/git-activity/timeline", params={"preset": "30d"}).json()["total"]

    # Second scan without changes: index is stable (no-op refresh path exercised).
    client.post("/api/git-activity/scan")
    second = _wait()
    assert second["status"] == "complete"
    assert client.get("/api/git-activity/timeline", params={"preset": "30d"}).json()["total"] == before

    # A new commit appears on the next refresh.
    repo = git_root / "demo"
    _commit(repo, "app.py", "print('hello world!')\nprint('again')\n", "feat: exclaim")
    client.post("/api/git-activity/scan")
    third = _wait()
    assert third["status"] == "complete"
    after = client.get("/api/git-activity/timeline", params={"preset": "30d"}).json()["total"]
    assert after == before + 1


def test_secret_redaction_in_prompt(client: TestClient, git_root: Path) -> None:
    repo = git_root / "demo"
    _commit(repo, "config.env", "API_KEY=supersecret12345\n", "chore: add config")
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        if not client.get("/api/git-activity/scan").json()["running"]:
            break
        time.sleep(0.5)
    timeline = client.get("/api/git-activity/timeline", params={"preset": "30d", "search": "add config"}).json()
    assert timeline["total"] >= 1
    item = timeline["items"][0]
    prompt = client.get(f"/api/git-activity/commits/{item['repo_id']}/{item['sha']}/prompt").json()
    assert "supersecret12345" not in prompt["markdown"]
    assert prompt["redaction_count"] >= 1


def test_review_request_requires_model_config(client: TestClient, git_root: Path) -> None:
    """With no AI endpoint configured, the review must fail closed, not invent output."""
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        if not client.get("/api/git-activity/scan").json()["running"]:
            break
        time.sleep(0.5)
    item = client.get("/api/git-activity/timeline", params={"preset": "30d"}).json()["items"][0]
    response = client.post("/api/git-activity/reviews", json={"repo_id": item["repo_id"], "sha": item["sha"], "model": "test-model"})
    assert response.status_code == 201, response.text
    review_id = response.json()["id"]
    deadline = time.time() + 30
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/git-activity/reviews/{review_id}").json()
        if final["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)
    assert final is not None and final["status"] == "failed"
    assert "error" in final and final["error"]


def test_generated_dirs_are_not_registered_as_projects(client: TestClient, git_root: Path) -> None:
    noisy = git_root / "workbench" / ".workbench" / "run-1" / "book"
    noisy.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["git", "-C", str(noisy), "init"], capture_output=True, timeout=30)
    assert result.returncode == 0
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        if not client.get("/api/git-activity/scan").json()["running"]:
            break
        time.sleep(0.5)
    names = {repo["name"] for repo in client.get("/api/git-activity/repos").json()}
    assert "demo" in names
    assert "book" not in names


def test_no_repository_mutation(client: TestClient, git_root: Path) -> None:
    repo = git_root / "demo"
    head_before = _git(repo, "rev-parse", "HEAD")
    status_before = _git(repo, "status", "--porcelain")
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        if not client.get("/api/git-activity/scan").json()["running"]:
            break
        time.sleep(0.5)
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert _git(repo, "status", "--porcelain") == status_before


def test_context_inventory_and_proposal(client: TestClient, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        if not client.get("/api/git-activity/scan").json()["running"]:
            break
        time.sleep(0.5)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    inventory = client.get(f"/api/git-activity/context/{repo_id}").json()
    assert inventory["has_agents"] is True and inventory["has_description"] is True
    proposal = client.post(f"/api/git-activity/context/{repo_id}/propose", json={"kind": "description"}).json()
    assert "proposal" in proposal and len(proposal["proposal"]) > 50
    # Proposal must not write without explicit approval.
    assert (git_root / "demo" / "DESCRIPTION.md").read_text(encoding="utf-8").startswith("# Demo")
