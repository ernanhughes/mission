"""MC-ACTIVITY-02 qualification: daily project AI review."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient


def _git(repo: Path, *args: str, env_extra: dict[str, str] | None = None) -> str:
    import os

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, shell=False, check=False, env=env,
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


def _commit_on(repo: Path, filename: str, content: str, message: str, when_iso: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message, "--no-gpg-sign",
         env_extra={"GIT_AUTHOR_DATE": when_iso, "GIT_COMMITTER_DATE": when_iso})
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    root.mkdir(parents=True, exist_ok=True)
    # Two repos with the SAME display name in different dirs to prove IDs stay separate.
    for dirname in ("writer-a", "writer-b"):
        repo = _make_repo(root, dirname)
        _commit_on(repo, "notes.txt", f"hello {dirname}\n", "feat: initial",
                   "2026-11-10T09:00:00+00:00")
        _commit_on(repo, "notes.txt", f"hello {dirname} v2\n", "fix: second",
                   "2026-11-10T14:00:00+00:00")
        (repo / "AGENTS.md").write_text("# Agents\n- Run pytest\n", encoding="utf-8")
        (repo / "DESCRIPTION.md").write_text("# Demo\nA fixture project.\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "docs: context", "--no-gpg-sign",
             env_extra={"GIT_AUTHOR_DATE": "2026-11-10T15:00:00+00:00",
                        "GIT_COMMITTER_DATE": "2026-11-10T15:00:00+00:00"})
    return root


def _isolate_roots(client: TestClient, git_root: Path) -> None:
    for existing in client.get("/api/git-activity/roots").json():
        client.delete(f"/api/git-activity/roots?path={existing['path']}&retain_history=false")
    response = client.post("/api/git-activity/roots", json={"path": str(git_root), "name": "Fixtures", "category": "software"})
    assert response.status_code == 201, response.text


def _wait_for_scan(client: TestClient, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get("/api/git-activity/scan").json()
        if not status["running"]:
            return status
        time.sleep(0.5)
    raise AssertionError("scan did not finish")


def test_day_bounds_dst() -> None:
    from mission_control.activity_git.service import _day_bounds_exclusive

    spring_start, spring_end = _day_bounds_exclusive("2026-03-29", "Europe/Dublin")
    assert spring_end - spring_start == 23 * 3600, (spring_start, spring_end)
    autumn_start, autumn_end = _day_bounds_exclusive("2026-10-25", "Europe/Dublin")
    assert autumn_end - autumn_start == 25 * 3600, (autumn_start, autumn_end)
    normal_start, normal_end = _day_bounds_exclusive("2026-11-10", "Europe/Dublin")
    assert normal_end - normal_start == 24 * 3600
    # Start-inclusive / end-exclusive: a commit exactly at end belongs to next day.
    assert spring_start < spring_end
    dublin = ZoneInfo("Europe/Dublin")
    assert datetime.fromtimestamp(normal_start, tz=dublin).hour == 0
    assert datetime.fromtimestamp(normal_end, tz=dublin).hour == 0


def test_daily_projects_two_repos_and_same_name_separate(client: TestClient, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    assert _wait_for_scan(client)["status"] == "complete"
    # Force identical display names: IDs must still stay separate.
    with client.app.state.database.session() as session:
        from mission_control.models import GitRepository
        for row in session.scalars(__import__("sqlalchemy", fromlist=["select"]).select(GitRepository)).all():
            row.name = "Writer"
    body = client.get("/api/git-activity/daily/projects",
                      params={"date": "2026-11-10", "timezone": "Europe/Dublin"}).json()
    assert body["date"] == "2026-11-10" and body["timezone"] == "Europe/Dublin"
    assert body["total_repos"] == 2, body
    assert body["total_commits"] == 6, body
    assert len(body["projects"]) == 2
    ids = {p["repo_id"] for p in body["projects"]}
    assert len(ids) == 2
    assert {p["repo_name"] for p in body["projects"]} == {"Writer"}
    for project in body["projects"]:
        assert project["commit_count"] == 3, project
        assert len(project["commit_shas"]) == 3
        assert project["snapshot_fingerprint"]
        assert project["review_status"] == "not_reviewed"


def test_daily_manifest_includes_all_commits_over_100(client: TestClient, git_root: Path) -> None:
    from mission_control.models import GitCommit
    from mission_control.persistence.db import now_iso

    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    # Synthetic burst of 150 commits on one day proves pagination independence.
    from mission_control.activity_git.service import _day_bounds_exclusive
    start, _ = _day_bounds_exclusive("2026-11-10", "Europe/Dublin")
    with client.app.state.database.session() as session:
        for i in range(150):
            sha = f"{i:040x}"
            session.add(GitCommit(
                repo_id=repo_id, sha=sha, short_sha=sha[:8], subject=f"synthetic {i}",
                body="", author_name="Test", author_email="t@example.com",
                author_ts=start + i, author_tz="+00:00",
                committer_ts=start + i, committer_tz="+00:00",
                parents=[], branches=["main"], files_changed=1, insertions=1,
                deletions=0, is_merge=False, is_root=False, reachable=True,
                first_seen_at=now_iso(), observed_at=now_iso()))
    body = client.get("/api/git-activity/daily/projects",
                      params={"date": "2026-11-10", "timezone": "Europe/Dublin"}).json()
    entry = next(p for p in body["projects"] if p["repo_id"] == repo_id)
    assert entry["commit_count"] >= 153, entry
    assert len(entry["commit_shas"]) == entry["commit_count"]
    # Timeline paginates at 100; the daily manifest must not.
    timeline = client.get("/api/git-activity/timeline",
                          params={"preset": "30d", "limit": 100}).json()
    assert timeline["total"] >= 153
    assert len(timeline["items"]) == 100


def test_daily_prompt_includes_more_than_50_and_reports_coverage(client: TestClient, git_root: Path) -> None:
    from mission_control.models import GitCommit
    from mission_control.persistence.db import now_iso

    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    from mission_control.activity_git.service import _day_bounds_exclusive
    start, _ = _day_bounds_exclusive("2026-11-10", "Europe/Dublin")
    with client.app.state.database.session() as session:
        for i in range(60):
            sha = f"b{i:039x}"
            session.add(GitCommit(
                repo_id=repo_id, sha=sha, short_sha=sha[:8], subject=f"burst {i}",
                body="", author_name="Test", author_email="t@example.com",
                author_ts=start + 100 + i, author_tz="+00:00",
                committer_ts=start + 100 + i, committer_tz="+00:00",
                parents=[], branches=["main"], files_changed=1, insertions=1,
                deletions=0, is_merge=False, is_root=False, reachable=True,
                first_seen_at=now_iso(), observed_at=now_iso()))
    before = len(client.get("/api/git-activity/reviews").json())
    prompt = client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code"}).json()
    assert len(prompt["commit_shas"]) > 50, len(prompt["commit_shas"])
    assert prompt["coverage"]["total_commits"] == len(prompt["commit_shas"])
    assert "snapshot_fingerprint" in prompt
    # Prompt creation must not start a model call or persist a review.
    assert len(client.get("/api/git-activity/reviews").json()) == before


def test_explain_and_review_modes_differ(client: TestClient, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    explain = client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "explain", "profile": "code"}).json()
    review = client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code"}).json()
    assert explain["mode"] == "explain" and review["mode"] == "review"
    assert "what the developer should know" in explain["markdown"].lower() or "workstream" in explain["markdown"].lower()
    assert "Critically review" in review["markdown"]
    assert "Verdict" in review["markdown"]
    assert explain["markdown"] != review["markdown"]


def test_multibranch_warning_and_no_cumulative_claim(client: TestClient, git_root: Path) -> None:
    from mission_control.models import GitCommit
    from mission_control.persistence.db import now_iso

    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    from mission_control.activity_git.service import _day_bounds_exclusive
    start, _ = _day_bounds_exclusive("2026-11-10", "Europe/Dublin")
    with client.app.state.database.session() as session:
        for i, branch in enumerate(("feature-a", "feature-b")):
            sha = f"c{i:039x}"
            session.add(GitCommit(
                repo_id=repo_id, sha=sha, short_sha=sha[:8], subject=f"branch work {branch}",
                body="", author_name="Test", author_email="t@example.com",
                author_ts=start + 5000 + i, author_tz="+00:00",
                committer_ts=start + 5000 + i, committer_tz="+00:00",
                parents=[], branches=[branch], files_changed=1, insertions=2,
                deletions=0, is_merge=False, is_root=False, reachable=True,
                first_seen_at=now_iso(), observed_at=now_iso()))
    prompt = client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code"}).json()
    assert prompt["coverage"]["multi_branch"] is True
    assert "do NOT assume one linear cumulative diff" in prompt["markdown"]


def test_snapshot_stale_after_new_commit(client: TestClient, git_root: Path) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    first = client.get("/api/git-activity/daily/projects",
                       params={"date": "2026-11-10", "timezone": "Europe/Dublin"}).json()
    snapshot_before = next(p for p in first["projects"] if p["repo_id"] == repo_id)["snapshot_fingerprint"]
    review = client.post("/api/git-activity/daily/reviews", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code", "model": "test-model"}).json()
    assert review["review_type"] == "daily"
    assert review["evidence_coverage"]["snapshot_fingerprint"] == snapshot_before
    # A new commit on the same day changes the snapshot and stales the review.
    repo = git_root / "writer-a"
    _commit_on(repo, "notes.txt", "late change\n", "feat: late",
               "2026-11-10T20:00:00+00:00")
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    after = client.get("/api/git-activity/daily/projects",
                       params={"date": "2026-11-10", "timezone": "Europe/Dublin"}).json()
    entry = next(p for p in after["projects"] if p["repo_id"] == repo_id)
    assert entry["snapshot_fingerprint"] != snapshot_before
    assert entry["review_stale"] is True


def test_secret_redaction_and_no_absolute_paths(client: TestClient, git_root: Path) -> None:
    repo = git_root / "writer-a"
    _commit_on(repo, "config.env", "API_KEY=supersecret12345\n", "chore: add config",
               "2026-11-10T16:00:00+00:00")
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = next(r["id"] for r in client.get("/api/git-activity/repos").json()
                   if r["name"] == "writer-a")
    prompt = client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code"}).json()
    assert "supersecret12345" not in prompt["markdown"]
    assert prompt["redaction_count"] >= 1
    assert str(git_root) not in prompt["markdown"]


def test_oversized_day_reports_partial_coverage(client: TestClient, git_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    # Force a tiny budget so the day cannot fit: coverage must say so explicitly.
    with client.app.state.database.session() as session:
        from mission_control.activity_git.service import GitActivityService  # noqa: F401
        setting = session.get(__import__("mission_control.models", fromlist=["Setting"]).Setting, "activity_git")
        if setting is None:
            from mission_control.models import Setting
            from mission_control.persistence.db import now_iso
            session.add(Setting(key="activity_git",
                                value={"recent_days": 30, "max_depth": 4, "max_repos_per_scan": 2000,
                                       "diff_max_bytes": 120_000, "backfill_page": 500,
                                       "prompt_max_chars": 4000, "concurrency": 8},
                                updated_at=now_iso()))
        else:
            value = dict(setting.value)
            value["prompt_max_chars"] = 4000
            setting.value = value
    prompt = client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code"}).json()
    assert prompt["coverage"]["commit_count"] == len(prompt["commit_shas"])
    assert prompt["truncated"] is True
    assert "PARTIAL" in prompt["markdown"]


def test_review_execution_fail_closed_and_persists_scope(client: TestClient, git_root: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = client.get("/api/git-activity/repos").json()[0]["id"]
    review = client.post("/api/git-activity/daily/reviews", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "explain", "profile": "code", "model": "test-model"}).json()
    deadline = time.time() + 30
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/git-activity/reviews/{review['id']}").json()
        if final["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)
    assert final is not None and final["status"] == "failed"
    assert final["error"]
    assert final["review_type"] == "daily"
    assert final["evidence_coverage"]["daily_date"] == "2026-11-10"

    # With a stubbed model the exact result persists with the full scope.
    async def _fake_chat(session, *, model, messages, route=None):
        assert messages and "2026-11-10" in messages[-1]["content"][:200000]
        if "workstream" in messages[-1]["content"].lower() or "expl accomplished" in messages[-1]["content"].lower() or "Explain" in messages[-1]["content"]:
            return {"content": "Day summary:\n- Workstream A shipped\n", "model": model, "route": route or "configured-local-openai", "usage": {}}
        return {"content": "Verdict: Accept\nFindings:\n- none\n", "model": model, "route": route or "configured-local-openai", "usage": {}}

    import mission_control.research.inference as inference
    monkeypatch.setattr(inference, "complete_chat", _fake_chat)
    review2_resp = client.post("/api/git-activity/daily/reviews", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code", "model": "stub-model"})
    assert review2_resp.status_code == 201, review2_resp.text
    review2 = review2_resp.json()
    deadline = time.time() + 30
    final2 = None
    while time.time() < deadline:
        final2 = client.get(f"/api/git-activity/reviews/{review2['id']}").json()
        if final2["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)
    assert final2 is not None and final2["status"] == "completed", final2
    assert final2["verdict"] == "Accept"
    assert final2["evidence_coverage"]["daily_date"] == "2026-11-10"
    assert final2["evidence_coverage"]["daily_mode"] == "review"
    assert len(final2["commit_shas"]) >= 3
    listed = client.get("/api/git-activity/daily/reviews",
                        params={"repo_id": repo_id, "date": "2026-11-10",
                                "timezone": "Europe/Dublin"}).json()
    assert any(r["id"] == review2["id"] for r in listed)


def test_no_repository_mutation(client: TestClient, git_root: Path) -> None:
    repo = git_root / "writer-a"
    head_before = _git(repo, "rev-parse", "HEAD")
    status_before = _git(repo, "status", "--porcelain")
    _isolate_roots(client, git_root)
    client.post("/api/git-activity/scan")
    _wait_for_scan(client)
    repo_id = next(r["id"] for r in client.get("/api/git-activity/repos").json() if r["name"] == "writer-a")
    client.post("/api/git-activity/daily/prompt", json={
        "repo_id": repo_id, "date": "2026-11-10", "timezone": "Europe/Dublin",
        "mode": "review", "profile": "code"})
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert _git(repo, "status", "--porcelain") == status_before
