"""MC-CULTIVATION-03 qualification: project adapter, lifecycle, applications.

Fixtures insert Activity index rows directly (no git processes, no scanner):
the adapter under test must only read them.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mission_control.models import (
    DiscoveryRoot,
    GitCommit,
    GitRepository,
    Project,
    ProjectRepository,
    Repository,
)
from mission_control.persistence.db import now_iso


def _repo(session, *, repo_id: str, uid: str, path: str, root: str, name: str,
          accessible: bool = True, backfill: bool = True,
          commits: list[tuple[int, str]] | None = None) -> GitRepository:
    row = GitRepository(
        id=repo_id, root_path=root, path=path, name=name, git_dir=path + "/.git",
        repo_uid=uid, branch="main", head_sha="f" * 40 if commits else None,
        accessible=accessible, is_bare=False, is_shallow=False,
        last_indexed_at=now_iso(), backfill_complete=backfill, refs_snapshot="x",
        total_commits=len(commits or []), has_agents=False, has_description=False,
        context_status="missing", updated_at=now_iso())
    session.add(row)
    session.flush()  # parents before children: one flush per level
    for index, (ts, subject) in enumerate(commits or []):
        session.add(GitCommit(
            repo_id=repo_id, sha=f"{index:040d}", short_sha=f"{index:08d}",
            subject=subject, body="", author_name="T", author_email="t@e.com",
            author_ts=ts, author_tz="+00:00", committer_ts=ts, committer_tz="+00:00",
            parents=[], branches=["main"], files_changed=1, insertions=10, deletions=2,
            is_merge=False, is_root=index == 0, reachable=True,
            first_seen_at=now_iso(), observed_at=now_iso()))
    session.flush()
    return row


@pytest.fixture
def activity_index(client: TestClient):
    database = client.app.state.database
    with database.session() as session:
        for path, name, category in (
            (r"C:\Projects", "Projects", "software"),
            (r"C:\books", "Books", "books"),
        ):
            if session.get(DiscoveryRoot, path) is None:
                session.add(DiscoveryRoot(path=path, enabled=True, added_at=now_iso(),
                                          display_name=name, category=category, git_enabled=True))
        proj = Project(id="proj-web", name="Web App", description="", kind="project",
                       status="active", priority=100, pinned=False, archived=False,
                       display_order=100, created_at=now_iso(), updated_at=now_iso())
        session.add(proj)
        repo = Repository(id="repo-web", path=r"C:\Projects\web", name="web",
                          classification="web_application", confidence=0.9, evidence=[],
                          source_root=r"C:\Projects", is_git=True, accessible=True,
                          candidate=False, first_seen_at=now_iso())
        session.add(repo)
        session.flush()
        session.add(ProjectRepository(project_id="proj-web", repository_id="repo-web", role="primary"))
    yield client


def _source(client: TestClient, **overrides) -> dict:
    payload = {"name": "Activity", "kind": "activity_projects",
               "goal_id": "repositories",
               "config": {"included_roots": [r"C:\Projects"]}}
    payload.update(overrides)
    response = client.post("/api/cultivation/sources", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _sync(client: TestClient, source_id: str) -> dict:
    response = client.post(f"/api/cultivation/sources/{source_id}/sync")
    assert response.status_code == 200, response.text
    return response.json()


def test_uses_activity_registry_without_rescan(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-a", uid="git-aaa", path=r"C:\Projects\web",
              root=r"C:\Projects", name="web", commits=[(1700000000, "init"), (1790000000, "feat")])
        _repo(session, repo_id="gitrepo-b", uid="git-bbb", path=r"C:\Projects\tool",
              root=r"C:\Projects", name="tool", commits=[(1790000000, "only")])
    source = _source(client)
    result = _sync(client, source["id"])
    assert result["status"] == "ok"
    assert result["observed"]["repos_total"] == 2
    assert result["observed"]["by_qualification"] == {"eligible": 1, "pending": 1}
    # Same repo names must not duplicate: one state row per Activity row.
    states = client.get("/api/cultivation/repo-states").json()
    assert states["total"] == 2
    # Idempotent: a second unchanged sync creates no new items or stage events.
    before_items = len(client.get("/api/cultivation/items").json())
    events_before = client.get("/api/cultivation/goals/repositories/events", params={"limit": 200}).json()
    result2 = _sync(client, source["id"])
    assert result2["fingerprint_changed"] is False
    assert len(client.get("/api/cultivation/items").json()) == before_items
    events_after = client.get("/api/cultivation/goals/repositories/events", params={"limit": 200}).json()
    assert len(events_after) == len(events_before)


def test_no_second_scanner_in_adapter() -> None:
    import inspect

    from mission_control.cultivation import service as cultivation_service

    # The Activity adapter must read indexed rows only: no filesystem walk,
    # no subprocess, no git binary. (File observation lives in sources.py, a
    # different layer: the Hugo blog source walks its own content tree and the
    # numbered-file source dates files with read-only git.)
    for name in ("sync_activity_projects", "_scope_roots", "_project_map",
                 "_commit_aggregates", "_auto_qualification", "list_repo_states",
                 "repo_read", "_resolve_git_row"):
        source = inspect.getsource(getattr(cultivation_service, name)).casefold()
        assert "os.walk" not in source, name
        assert "os.scandir" not in source, name
        assert "subprocess" not in source, name
        assert "popen" not in source, name
    adapter = inspect.getsource(cultivation_service.sync_activity_projects)
    assert "run_git" not in adapter
    assert "build_prompt" not in adapter
    assert "file_diff" not in adapter


def test_service_syncs_do_not_shell_out() -> None:
    import inspect

    from mission_control.cultivation import service as cultivation_service

    # Filesystem and git access live in cultivation/sources.py (read-only
    # observation). The service layer orchestrates rows and events only: no
    # shell, no directory walk of its own.
    for name in ("sync_source", "_sync_hugo_blog", "_sync_numbered_files",
                 "_reconcile_observed_items", "_feed_period_goal",
                 "_store_scan_observation", "_mark_source_stale",
                 "_attach_live_source"):
        source = inspect.getsource(getattr(cultivation_service, name)).casefold()
        assert "subprocess" not in source, name
        assert "popen" not in source, name
        assert "os.walk" not in source, name
        assert "os.scandir" not in source, name


def test_worktrees_and_moves_share_stable_identity(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-main", uid="git-shared", path=r"C:\Projects\app",
              root=r"C:\Projects", name="app",
              commits=[(1790000000, "a"), (1790000100, "b"), (1790000200, "c")])
        _repo(session, repo_id="gitrepo-wt", uid="git-shared", path=r"C:\Projects\app-wt",
              root=r"C:\Projects", name="app-wt",
              commits=[(1790000000, "a"), (1790000100, "b"), (1790000200, "c")])
    source = _source(client)
    _sync(client, source["id"])
    items = client.get("/api/cultivation/items", params={"search": "app"}).json()
    repo_items = [item for item in items if item["id"].startswith("repo-")]
    assert len(repo_items) == 1  # one stable identity, not two checkouts
    # Move: Activity issues a new row id for the new path, same uid.
    with client.app.state.database.session() as session:
        session.delete(session.get(GitRepository, "gitrepo-main"))
        session.delete(session.get(GitRepository, "gitrepo-wt"))
        _repo(session, repo_id="gitrepo-moved", uid="git-shared", path=r"C:\Projects\renamed-app",
              root=r"C:\Projects", name="renamed-app",
              commits=[(1790000000, "a"), (1790000100, "b"), (1790000200, "c")])
    result = _sync(client, source["id"])
    assert result["status"] == "ok"
    states = client.get("/api/cultivation/repo-states").json()["items"]
    assert len(states) == 1
    assert states[0]["repo_id"] == "gitrepo-moved"
    history = client.get(f"/api/cultivation/items/{repo_items[0]['id']}/events").json()
    assert any(event["event_type"] == "renamed" for event in history)


def test_nested_and_inaccessible_repos(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-outer", uid="git-outer", path=r"C:\Projects\mono",
              root=r"C:\Projects", name="mono", commits=[(1790000000, "a"), (1790000001, "b")])
        _repo(session, repo_id="gitrepo-inner", uid="git-inner", path=r"C:\Projects\mono\inner",
              root=r"C:\Projects", name="inner", commits=[(1790000000, "a")])
        _repo(session, repo_id="gitrepo-dead", uid="git-dead", path=r"C:\Projects\gone",
              root=r"C:\Projects", name="gone", accessible=False, commits=[(1790000000, "a")])
    source = _source(client)
    result = _sync(client, source["id"])
    assert result["observed"]["repos_total"] == 3
    states = {row["repo_id"]: row for row in client.get("/api/cultivation/repo-states").json()["items"]}
    assert states["gitrepo-outer"]["qualification"] == "eligible"
    assert states["gitrepo-inner"]["qualification"] == "pending"  # single commit
    assert states["gitrepo-dead"]["qualification"] == "discovered"  # inaccessible: never pending-counted
    assert states["gitrepo-dead"]["accessible"] is False


def test_archived_repo_activity_is_observation_not_transition(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-old", uid="git-old", path=r"C:\Projects\old",
              root=r"C:\Projects", name="old",
              commits=[(1790000000, "a"), (1790000001, "b")])
    source = _source(client)
    _sync(client, source["id"])
    client.patch("/api/cultivation/repo-states/gitrepo-old",
                 json={"lifecycle_stage": "archived", "rationale": "Retired"})
    with client.app.state.database.session() as session:
        session.add(GitCommit(
            repo_id="gitrepo-old", sha="9" * 40, short_sha="99999999", subject="stray fix",
            body="", author_name="T", author_email="t@e.com", author_ts=1790000100,
            author_tz="+00:00", committer_ts=1790000100, committer_tz="+00:00",
            parents=[], branches=["main"], files_changed=1, insertions=1, deletions=0,
            is_merge=False, is_root=False, reachable=True,
            first_seen_at=now_iso(), observed_at=now_iso()))
    _sync(client, source["id"])
    state = next(row for row in client.get("/api/cultivation/repo-states").json()["items"]
                 if row["repo_id"] == "gitrepo-old")
    assert state["lifecycle_stage"] == "archived"  # unchanged by new commits
    item = next(item for item in client.get("/api/cultivation/items").json()
                if item["id"] == "repo-git-old")
    history = client.get(f"/api/cultivation/items/{item['id']}/events").json()
    assert any(event["event_type"] == "activity_observed" for event in history)


def test_projects_linked_and_books_excluded(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-web", uid="git-web", path=r"C:\Projects\web",
              root=r"C:\Projects", name="web",
              commits=[(1790000000, "a"), (1790000001, "b"), (1790000002, "c")])
        _repo(session, repo_id="gitrepo-book", uid="git-book", path=r"C:\books\novel",
              root=r"C:\books", name="novel",
              commits=[(1790000000, "a"), (1790000001, "b"), (1790000002, "c")])
    source = _source(client)
    result = _sync(client, source["id"])
    assert result["observed"]["repos_total"] == 1  # books root excluded by default scope
    states = client.get("/api/cultivation/repo-states").json()["items"]
    assert [row["repo_id"] for row in states] == ["gitrepo-web"]
    assert states[0]["projects"] == [{"id": "proj-web", "name": "Web App"}]
    assert result["observed"]["projects_linked"] == 1


def test_discovered_vs_qualifying_and_owner_confirm(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-a", uid="git-a", path=r"C:\Projects\a",
              root=r"C:\Projects", name="a", commits=[(1790000000, "a")] * 3)
    source = _source(client)
    _sync(client, source["id"])
    goal = client.get("/api/cultivation/goals/repositories").json()
    assert goal["progress"]["current"] == 0  # nothing auto-counts
    # Qualifying without a rationale is rejected.
    bad = client.patch("/api/cultivation/repo-states/gitrepo-a", json={"qualification": "qualified"})
    assert bad.status_code == 422
    good = client.patch("/api/cultivation/repo-states/gitrepo-a",
                        json={"qualification": "qualified", "rationale": "Real tool, used daily",
                              "goal_id": "repositories"}).json()
    assert good["qualification"] == "qualified"
    assert good["decided_by"] == "owner"
    goal = client.get("/api/cultivation/goals/repositories").json()
    assert goal["progress"]["current"] == 1
    # Excluding removes the count but keeps the item and its history.
    client.patch("/api/cultivation/repo-states/gitrepo-a",
                 json={"qualification": "excluded", "rationale": "Vendored copy", "goal_id": "repositories"})
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 0
    item = next(item for item in client.get("/api/cultivation/items").json() if item["id"] == "repo-git-a")
    assert item is not None
    history = client.get(f"/api/cultivation/items/{item['id']}/events").json()
    assert {"completed", "reopened", "unqualified"} & {event["event_type"] for event in history}


def test_perfect_repos_need_explicit_evidence(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-p", uid="git-p", path=r"C:\Projects\p",
              root=r"C:\Projects", name="p", commits=[(1790000000, "a")] * 5)
    source = _source(client)
    _sync(client, source["id"])
    assert client.get("/api/cultivation/goals/perfect_repositories").json()["progress"]["current"] == 0
    client.patch("/api/cultivation/repo-states/gitrepo-p",
                 json={"qualification": "qualified", "rationale": "Meets team bar",
                       "goal_id": "perfect_repositories"})
    # A qualified repo is not automatically a *perfect* repo: quality evidence
    # is a separate, explicit step.
    still = client.get("/api/cultivation/goals/perfect_repositories").json()
    assert still["progress"]["current"] == 0
    assert still["progress"]["unknown_reason"] is None  # known zero, not unknown
    item = next(item for item in client.get("/api/cultivation/items").json() if item["id"] == "repo-git-p")
    client.patch(f"/api/cultivation/items/{item['id']}/goals/perfect_repositories/qualify", json={
        "qualified": True,
        "quality_evidence": {"tests": "passing", "review": "accepted", "reviewed_by": "owner"},
        "note": "Independent check passed"})
    perfect = client.get("/api/cultivation/goals/perfect_repositories").json()
    assert perfect["progress"]["current"] == 1
    assert perfect["progress"]["estimate_label"] is None  # no blanket AI verdict involved
    # The plain repositories goal is unaffected by perfect-qualification here
    # (this repo was never counted there).
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 0


def test_bulk_confirm_and_filters(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        for index in range(3):
            subjects = ["a", "b"] if index < 2 else ["a"]
            _repo(session, repo_id=f"gitrepo-{index}", uid=f"git-{index}",
                  path=rf"C:\Projects\r{index}", root=r"C:\Projects", name=f"r{index}",
                  commits=[(1790000000 + i, subject) for i, subject in enumerate(subjects)])
    source = _source(client)
    _sync(client, source["id"])
    result = client.post("/api/cultivation/repo-states/bulk", json={
        "repo_ids": ["gitrepo-0", "gitrepo-1"], "qualification": "qualified",
        "rationale": "Reviewed batch", "goal_id": "repositories"}).json()
    assert result == {"updated": 2}
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 2
    qualified = client.get("/api/cultivation/repo-states",
                           params={"qualification": "qualified"}).json()
    assert qualified["total"] == 2
    pending = client.get("/api/cultivation/repo-states", params={"qualification": "pending"}).json()
    assert pending["total"] == 1
    excluded = client.post("/api/cultivation/repo-states/bulk", json={
        "repo_ids": ["gitrepo-2"], "qualification": "excluded", "rationale": "Fork"}).json()
    assert excluded == {"updated": 1}


def test_applications_count_once_across_repos(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-fe", uid="git-fe", path=r"C:\Projects\fe",
              root=r"C:\Projects", name="fe", commits=[(1790000000, "a")] * 2)
        _repo(session, repo_id="gitrepo-be", uid="git-be", path=r"C:\Projects\be",
              root=r"C:\Projects", name="be", commits=[(1790000000, "a")] * 2)
    source = _source(client)
    _sync(client, source["id"])
    app = client.post("/api/cultivation/applications", json={
        "name": "Portal", "repo_ids": ["gitrepo-fe", "gitrepo-be"]}).json()
    assert app["lifecycle_stage"] == "idea"
    assert len(app["repos"]) == 2
    # Release without evidence is rejected: commits alone never qualify.
    bad = client.post(f"/api/cultivation/applications/{app['id']}/release",
                      json={"lifecycle": "released", "evidence": {}, "goal_id": "applications"})
    assert bad.status_code == 422
    good = client.post(f"/api/cultivation/applications/{app['id']}/release", json={
        "lifecycle": "released",
        "evidence": {"kind": "owner_confirmed", "note": "Used daily; accepted as complete",
                     "completed_at": "2026-11-05T00:00:00Z"},
        "goal_id": "applications"}).json()
    assert good["lifecycle_stage"] == "released"
    assert good["completed_at"] == "2026-11-05T00:00:00Z"
    shipped = client.get("/api/cultivation/goals/applications").json()
    assert shipped["progress"]["current"] == 1  # one app, not two repos
    # Withdrawing the release removes the count but keeps the evidence.
    client.post(f"/api/cultivation/applications/{app['id']}/unrelease", json={"note": "Rewriting"})
    assert client.get("/api/cultivation/goals/applications").json()["progress"]["current"] == 0
    detail = client.get(f"/api/cultivation/applications/{app['id']}").json()
    assert detail["release_evidence"]["kind"] == "owner_confirmed"


def test_one_repo_can_support_two_applications(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-mono", uid="git-mono", path=r"C:\Projects\mono",
              root=r"C:\Projects", name="mono", commits=[(1790000000, "a")] * 2)
    source = _source(client)
    _sync(client, source["id"])
    for name in ("Alpha", "Beta"):
        app = client.post("/api/cultivation/applications",
                          json={"name": name, "repo_ids": ["gitrepo-mono"]}).json()
        client.post(f"/api/cultivation/applications/{app['id']}/release", json={
            "lifecycle": "released",
            "evidence": {"kind": "owner_confirmed", "note": f"{name} shipped"},
            "goal_id": "applications"})
    assert client.get("/api/cultivation/goals/applications").json()["progress"]["current"] == 2


def test_manual_hold_blocks_sync_changes(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-h", uid="git-h", path=r"C:\Projects\h",
              root=r"C:\Projects", name="h", commits=[(1790000000, "a")] * 3)
    source = _source(client)
    _sync(client, source["id"])
    # Owner moves the repo out of the qualified count in the repos goal.
    client.patch("/api/cultivation/repo-states/gitrepo-h",
                 json={"qualification": "qualified", "rationale": "Counts", "goal_id": "repositories"})
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 1
    item = next(item for item in client.get("/api/cultivation/items").json() if item["id"] == "repo-git-h")
    membership = next(m for m in item["memberships"] if m["goal_id"] == "repositories")
    assert membership["stage"] == "published"
    client.patch(f"/api/cultivation/items/{item['id']}/goals/repositories/stage",
                 json={"stage": "editing", "note": "Owner review: not yet"})
    _sync(client, source["id"])
    held = next(m for m in client.get(f"/api/cultivation/items/{item['id']}").json()["memberships"]
                if m["goal_id"] == "repositories")
    assert held["stage"] == "editing"  # sync did not silently overwrite


def test_unavailable_repo_keeps_history_and_count(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-temp", uid="git-temp", path=r"C:\Projects\temp",
              root=r"C:\Projects", name="temp", commits=[(1790000000, "a")] * 2)
    source = _source(client)
    _sync(client, source["id"])
    client.patch("/api/cultivation/repo-states/gitrepo-temp",
                 json={"qualification": "qualified", "rationale": "Counts", "goal_id": "repositories"})
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 1
    with client.app.state.database.session() as session:
        row = session.get(GitRepository, "gitrepo-temp")
        session.delete(row)
    result = _sync(client, source["id"])
    assert result["status"] == "ok"
    states = client.get("/api/cultivation/repo-states",
                        params={"include_unavailable": True}).json()["items"]
    temp = next(row for row in states if row["repo_id"] == "gitrepo-temp")
    assert temp["indexed"] is False
    assert temp["accessible"] is False
    assert temp["qualification"] == "qualified"  # history and count kept
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 1
    history = client.get("/api/cultivation/items/repo-git-temp/events").json()
    assert any(event["event_type"] == "source_removed" for event in history)


def test_cycle_window_uses_dates_not_scan_time(client: TestClient, activity_index: TestClient) -> None:
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-old", uid="git-old", path=r"C:\Projects\old",
              root=r"C:\Projects", name="old",
              commits=[(1700000000, "ancient"), (1700000001, "older")])
        _repo(session, repo_id="gitrepo-fresh", uid="git-fresh", path=r"C:\Projects\fresh",
              root=r"C:\Projects", name="fresh",
              commits=[(1790000000, "new"), (1790000100, "newer")])
    source = _source(client)
    _sync(client, source["id"])
    # An old repository discovered today must not count as established this cycle.
    today = date.today().isoformat()
    cycle = client.post("/api/cultivation/cycles", json={
        "start_date": today, "focus_goal_ids": ["repositories"]}).json()
    progress = client.get(f"/api/cultivation/cycles/{cycle['id']}").json()["progress"]
    focus = next(entry for entry in progress["focus"] if entry["goal_id"] == "repositories")
    assert focus["started_in_window"] == 0
    assert focus["completions_in_window"] == 0
    # Qualifying the fresh repo now attributes the completion to this cycle.
    client.patch("/api/cultivation/repo-states/gitrepo-fresh",
                 json={"qualification": "qualified", "rationale": "Real work",
                       "goal_id": "repositories"})
    progress = client.get(f"/api/cultivation/cycles/{cycle['id']}").json()["progress"]
    focus = next(entry for entry in progress["focus"] if entry["goal_id"] == "repositories")
    assert focus["completions_in_window"] == 1
    assert focus["started_in_window"] == 1
    # Lifetime totals are independent of the cycle window.
    assert client.get("/api/cultivation/goals/repositories").json()["progress"]["item_count"] == 1


def test_app_release_attributed_to_correct_cycle(client: TestClient, activity_index: TestClient) -> None:
    today = date.today()
    in_window = client.post("/api/cultivation/cycles", json={
        "start_date": (today - timedelta(days=10)).isoformat(),
        "focus_goal_ids": ["applications"]}).json()
    out_window = client.post("/api/cultivation/cycles", json={
        "start_date": (today - timedelta(days=200)).isoformat(), "length_days": 30,
        "focus_goal_ids": ["applications"]}).json()
    app = client.post("/api/cultivation/applications", json={"name": "Old Tool"}).json()
    client.post(f"/api/cultivation/applications/{app['id']}/release", json={
        "lifecycle": "maintained",
        "evidence": {"kind": "completion_decision", "note": "Accepted Q3",
                     "completed_at": (today - timedelta(days=3)).isoformat()},
        "goal_id": "applications"})
    current = client.get(f"/api/cultivation/cycles/{in_window['id']}").json()["progress"]
    assert next(e for e in current["focus"] if e["goal_id"] == "applications")["completions_in_window"] == 1
    old = client.get(f"/api/cultivation/cycles/{out_window['id']}").json()["progress"]
    assert next(e for e in old["focus"] if e["goal_id"] == "applications")["completions_in_window"] == 0
    # Lifetime count is independent of any window.
    assert client.get("/api/cultivation/goals/applications").json()["progress"]["current"] == 1


def test_rollover_preserves_lifetime_and_snapshot(client: TestClient) -> None:
    cycles = client.get("/api/cultivation/cycles").json()
    five = next(c for c in cycles if c["number"] == 5)
    assert five["day"]["mode"] == "snapshot" and five["day"]["day"] == 50
    nxt = client.post(f"/api/cultivation/cycles/{five['id']}/rollover").json()
    assert nxt["number"] == 6
    assert set(nxt["focus_goal_ids"]) >= {"published_books", "blog_posts"}
    assert client.get(f"/api/cultivation/cycles/{five['id']}").json()["state"] == "completed"
    assert client.get("/api/cultivation/goals/published_books").json()["progress"]["current"] == 30


def test_no_model_calls_and_no_git_mutation(client: TestClient, activity_index: TestClient) -> None:
    import pathlib
    # The adapter path must not infer or touch repositories. Shelling out is
    # banned in the service layer; the file scanners (sources.py) may use
    # read-only git for observation (numbered-file dating) — the Activity
    # adapter stays shell-free per test_no_second_scanner_in_adapter, and the
    # no-mutation half below guards behavior.
    backend = pathlib.Path(__file__).resolve().parents[1] / "mission_control" / "cultivation"
    for relative in ("service.py", "sources.py"):
        lowered = (backend / relative).read_text(encoding="utf-8").casefold()
        assert "inference" not in lowered, relative
        assert "httpx" not in lowered, relative
    assert "subprocess" not in (backend / "service.py").read_text(encoding="utf-8").casefold()
    assert "chat/completions" not in (backend / "service.py").read_text(encoding="utf-8")
    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-m", uid="git-m", path=r"C:\Projects\m",
              root=r"C:\Projects", name="m", commits=[(1790000000, "a")] * 2)
    source = _source(client)
    with client.app.state.database.session() as session:
        before_commits = session.scalar(select(func.count()).select_from(GitCommit))
        before_heads = {row.id: row.head_sha for row in session.scalars(select(GitRepository)).all()}
    _sync(client, source["id"])
    with client.app.state.database.session() as session:
        assert session.scalar(select(func.count()).select_from(GitCommit)) == before_commits
        for row in session.scalars(select(GitRepository)).all():
            assert before_heads[row.id] == row.head_sha


def test_seed_software_skill_and_source(client: TestClient) -> None:
    goals = {row["id"]: row for row in client.get("/api/cultivation/goals").json()}
    skills = {row["id"]: row for row in client.get("/api/cultivation/skills").json()}
    assert "software-development" in skills
    assert goals["repositories"]["skill_id"] == "software-development"
    assert goals["perfect_repositories"]["skill_id"] == "software-development"
    assert goals["applications"]["skill_id"] == "software-development"
    sources = client.get("/api/cultivation/sources").json()
    assert any(row["kind"] == "activity_projects" for row in sources)
    # Goals keep their configured milestones and types.
    assert goals["repositories"]["target_value"] == 1000
    assert goals["perfect_repositories"]["measurement_type"] == "qualified_count"


def test_restart_persistence_for_projects(client: TestClient, runtime) -> None:
    from helpers import open_client

    with client.app.state.database.session() as session:
        _repo(session, repo_id="gitrepo-keep", uid="git-keep", path=r"C:\Projects\keep",
              root=r"C:\Projects", name="keep", commits=[(1790000000, "a")] * 2)
    source = _source(client)
    _sync(client, source["id"])
    client.patch("/api/cultivation/repo-states/gitrepo-keep",
                 json={"qualification": "qualified", "rationale": "Keep",
                       "goal_id": "repositories"})
    app = client.post("/api/cultivation/applications", json={"name": "Keeper"}).json()
    with open_client(runtime) as reopened:
        states = reopened.get("/api/cultivation/repo-states").json()["items"]
        assert any(row["repo_id"] == "gitrepo-keep" and row["qualification"] == "qualified" for row in states)
        assert reopened.get(f"/api/cultivation/applications/{app['id']}").json()["name"] == "Keeper"
        assert reopened.get("/api/cultivation/goals/repositories").json()["progress"]["current"] == 1
