"""MC-CULTIVATION-APPS-01: GitHub repository inventory and application progress.

Fixtures pass fake fetchers directly (no network, no ``gh`` subprocess):
the adapter under test must be read-only toward GitHub and must never
overwrite owner judgement.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mission_control.cultivation import github as github_module
from mission_control.cultivation import service
from mission_control.models import (
    CultivationEvent,
    CultivationGitHubRepo,
    CultivationGoal,
    CultivationMembership,
    CultivationRepoState,
    Repository,
)


def _repo(node: str, name: str, **overrides):
    repo = {
        "node_id": node,
        "numeric_id": None,
        "owner": "ernanhughes",
        "name": name,
        "full_name": f"ernanhughes/{name}",
        "url": f"https://github.com/ernanhughes/{name}",
        "description": f"{name} project",
        "visibility": "PUBLIC",
        "is_private": False,
        "is_fork": False,
        "is_archived": False,
        "language": "Python",
        "languages": ["Python"],
        "topics": [],
        "default_branch": "main",
        "pushed_at": "2026-11-01T00:00:00Z",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2026-11-01T00:00:00Z",
    }
    repo.update(overrides)
    return repo


def _source(client: TestClient, **overrides) -> dict:
    payload = {"name": "GitHub repositories", "kind": "github_repos",
               "goal_id": "repositories",
               "config": {"account": "ernanhughes", "auth": "gh_cli"}}
    payload.update(overrides)
    response = client.post("/api/cultivation/sources", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _sync_db(client: TestClient, source_id: str, fetcher) -> dict:
    with client.app.state.database.session() as session:
        return service.sync_github_repos(session, source_id, fetcher=fetcher)


def test_sync_imports_inventory_without_pagination_limit(client: TestClient) -> None:
    source = _source(client)
    # 250 repositories: more than any single 100-row page.
    repos = [_repo(f"R_node{i:04d}", f"tool-{i:03d}") for i in range(250)]
    result = _sync_db(client, source["id"], fetcher=lambda: repos)
    assert result["status"] == "ok"
    assert result["observed"]["repos_total"] == 250
    assert result["new_items"] == 250
    states = client.get("/api/cultivation/repo-states", params={"limit": 500}).json()
    assert states["total"] == 250
    items = client.get("/api/cultivation/items", params={"limit": 500}).json()
    gh_items = [item for item in items if item["id"].startswith("repo-github:")]
    assert len(gh_items) == 250
    # Idempotent resync: no new items, no duplicate rows.
    again = _sync_db(client, source["id"], fetcher=lambda: repos)
    assert again["fingerprint_changed"] is False
    assert again["new_items"] == 0
    with client.app.state.database.session() as session:
        count = session.scalar(select(func.count()).select_from(CultivationGitHubRepo))
        assert count == 250


def test_private_repositories_stored_with_visibility_filter(client: TestClient) -> None:
    source = _source(client)
    repos = [_repo("R_priv1", "secret-tool", visibility="PRIVATE", is_private=True),
             _repo("R_pub1", "open-tool")]
    result = _sync_db(client, source["id"], fetcher=lambda: repos)
    assert result["observed"]["public"] == 1
    assert result["observed"]["private"] == 1
    private = client.get("/api/cultivation/repo-states",
                         params={"origin": "github", "visibility": "private"}).json()
    assert private["total"] == 1
    assert private["items"][0]["name"] == "secret-tool"
    assert private["items"][0]["private"] is True
    assert private["items"][0]["visibility"] == "PRIVATE"
    assert private["items"][0]["origin"] == "github"
    public = client.get("/api/cultivation/repo-states",
                        params={"origin": "github", "visibility": "public"}).json()
    assert public["total"] == 1


def test_stable_identity_across_rename(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_keep", "writer")])
    result = _sync_db(client, source["id"],
                      fetcher=lambda: [_repo("R_keep", "writer-v2")])
    assert result["observed"]["repos_total"] == 1
    states = client.get("/api/cultivation/repo-states",
                        params={"origin": "github"}).json()
    assert states["total"] == 1
    assert states["items"][0]["repo_id"] == "gh-R_keep"
    assert states["items"][0]["name"] == "writer-v2"
    with client.app.state.database.session() as session:
        events = session.scalars(select(CultivationEvent).where(
            CultivationEvent.event_type == "renamed")).all()
        assert len(events) == 1


def test_sync_failure_preserves_cached_inventory(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_a", "alpha")])

    def _failing():
        raise github_module.GitHubAuthError("GitHub CLI is not authenticated.")

    result = _sync_db(client, source["id"], fetcher=_failing)
    assert result["status"] == "auth_error"
    assert result["stale"] is True
    states = client.get("/api/cultivation/repo-states",
                        params={"origin": "github"}).json()
    assert states["total"] == 1
    assert states["items"][0]["name"] == "alpha"
    detail = client.get(f"/api/cultivation/sources/{source['id']}").json()
    assert detail["last_status"] == "auth_error"
    assert detail["last_error"]
    assert detail["observed"]["repos_total"] == 1


def test_owner_overrides_survive_resync(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_own", "mystery")])
    states = client.get("/api/cultivation/repo-states",
                        params={"origin": "github"}).json()
    repo_id = states["items"][0]["repo_id"]
    response = client.patch(f"/api/cultivation/repo-states/{repo_id}", json={
        "classification": "book", "lifecycle_stage": "working",
        "qualification": "pending", "rationale": "Owner review: book manuscript repo."})
    assert response.status_code == 200, response.text
    assert response.json()["decided_by"] == "owner"
    # Remote facts change; owner judgement must not.
    updated = _repo("R_own", "mystery", description="New remote description",
                    pushed_at="2026-12-01T00:00:00Z")
    _sync_db(client, source["id"], fetcher=lambda: [updated])
    kept = client.get("/api/cultivation/repo-states",
                      params={"origin": "github"}).json()["items"][0]
    assert kept["classification"] == "book"
    assert kept["lifecycle_stage"] == "working"
    assert kept["qualification"] == "pending"
    assert kept["decided_by"] == "owner"
    assert kept["evidence"]["github"]["description"] == "New remote description"


def test_book_repos_stay_visible_without_inflating_applications(client: TestClient) -> None:
    book_source = _source(client)
    _sync_db(client, book_source["id"],
             fetcher=lambda: [_repo("R_book", "language", language=None)])
    states = client.get("/api/cultivation/repo-states",
                        params={"origin": "github"}).json()
    assert states["items"][0]["classification"] == "book"
    repo_id = states["items"][0]["repo_id"]
    response = client.patch(f"/api/cultivation/repo-states/{repo_id}", json={
        "qualification": "qualified",
        "rationale": "Substantive book-associated repository.",
        "goal_id": "repositories"})
    assert response.status_code == 200, response.text
    repos_progress = client.get("/api/cultivation/goals/repositories").json()["progress"]
    assert repos_progress["current"] == 1
    apps_progress = client.get("/api/cultivation/goals/applications").json()["progress"]
    assert apps_progress["current"] == 0
    summary = client.get("/api/cultivation/github/summary").json()
    assert summary["discovered"] == 1
    assert summary["books_identified"] == 1
    assert summary["completed_applications"] == 0
    assert summary["goals"]["applications"]["current"] == 0


def test_completed_application_counts_once(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_app", "writer")])
    repo_id = client.get("/api/cultivation/repo-states",
                         params={"origin": "github"}).json()["items"][0]["repo_id"]
    app = client.post("/api/cultivation/applications",
                      json={"name": "Writer", "description": "AI authoring"}).json()
    link = client.post(f"/api/cultivation/applications/{app['id']}/repos",
                       json={"repo_id": repo_id})
    assert link.status_code == 200, link.text
    release = client.post(f"/api/cultivation/applications/{app['id']}/release", json={
        "lifecycle": "released",
        "evidence": {"kind": "owner_confirmed", "note": "Shipped and in use."},
        "goal_id": "applications"})
    assert release.status_code == 200, release.text
    summary = client.get("/api/cultivation/github/summary").json()
    assert summary["completed_applications"] == 1
    assert summary["published_applications"] == 1
    assert summary["goals"]["applications"]["current"] == 1


def test_lifecycle_transitions_and_archived_not_counted(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [
        _repo("R_live", "writer"),
        _repo("R_old", "retired-tool", is_archived=True)])
    rows = {item["name"]: item for item in client.get(
        "/api/cultivation/repo-states", params={"origin": "github", "limit": 100}).json()["items"]}
    assert rows["retired-tool"]["qualification"] == "archived"
    assert rows["retired-tool"]["lifecycle_stage"] == "archived"
    live_id = rows["writer"]["repo_id"]
    for stage in ("concept", "prototype", "working", "completed", "published"):
        response = client.patch(f"/api/cultivation/repo-states/{live_id}",
                                json={"lifecycle_stage": stage})
        assert response.status_code == 200, response.text
        assert response.json()["lifecycle_stage"] == stage
    # Archived lifecycle alone never counts toward applications.
    archived_id = rows["retired-tool"]["repo_id"]
    assert client.get("/api/cultivation/goals/applications").json()["progress"]["current"] == 0
    assert archived_id.startswith("gh-")


def test_local_workspace_matching_recorded(client: TestClient) -> None:
    # Seed registers C:\Projects\writer for the writer application.
    with client.app.state.database.session() as session:
        existing = session.scalar(select(Repository).where(
            Repository.path == r"C:\Projects\writer"))
        assert existing is not None
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_w", "writer")])
    item = client.get("/api/cultivation/repo-states",
                      params={"origin": "github"}).json()["items"][0]
    matches = item["evidence"].get("local_matches", [])
    assert any(match["path"] == r"C:\Projects\writer" for match in matches)


def test_missing_repos_tracked_without_deleting_history(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [
        _repo("R_stay", "stayer"), _repo("R_gone", "leaver")])
    gone_id = [item for item in client.get(
        "/api/cultivation/repo-states",
        params={"origin": "github", "limit": 100}).json()["items"]
        if item["name"] == "leaver"][0]["repo_id"]
    client.patch(f"/api/cultivation/repo-states/{gone_id}", json={
        "qualification": "qualified", "rationale": "Substantive repo.",
        "goal_id": "repositories"})
    result = _sync_db(client, source["id"], fetcher=lambda: [_repo("R_stay", "stayer")])
    assert result["observed"]["missing"] == 1
    with client.app.state.database.session() as session:
        missing = session.get(CultivationGitHubRepo, "R_gone")
        assert missing is not None and missing.missing is True
        state = session.get(CultivationRepoState, gone_id)
        assert state is not None and state.accessible is False
        assert state.qualification == "qualified"
        membership = session.get(
            CultivationMembership, (f"repo-github:{'R_gone'}", "repositories"))
        assert membership is not None
        goal = session.get(CultivationGoal, "repositories")
        assert goal is not None
        assert membership.stage == goal.qualifying_stage


def test_inferred_classification_never_counts_by_itself(client: TestClient) -> None:
    source = _source(client)
    result = _sync_db(client, source["id"], fetcher=lambda: [
        _repo("R_a1", "writer"), _repo("R_e1", "notes-analysis", language="Jupyter Notebook"),
        _repo("R_u1", "zzz-no-signal", language=None, languages=[])])
    kinds = {item["name"]: item["classification"] for item in client.get(
        "/api/cultivation/repo-states",
        params={"origin": "github", "limit": 100}).json()["items"]}
    assert kinds["writer"] == "application"
    assert kinds["notes-analysis"] == "experiment"
    assert kinds["zzz-no-signal"] == "unclassified"
    assert result["observed"]["by_qualification"] == {"discovered": 3}
    assert client.get("/api/cultivation/goals/applications").json()["progress"]["current"] == 0


def test_sync_endpoint_reports_auth_failure_without_destroying_cache(client: TestClient,
                                                                     monkeypatch) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_k", "kept")])

    def _auth_failure():
        raise github_module.GitHubAuthError("GitHub CLI is not authenticated.")

    monkeypatch.setattr(github_module, "resolve_fetcher", lambda config: _auth_failure)
    response = client.post(f"/api/cultivation/sources/{source['id']}/sync")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "auth_error"
    assert body["stale"] is True
    states = client.get("/api/cultivation/repo-states",
                        params={"origin": "github"}).json()
    assert states["total"] == 1


def test_token_config_names_env_without_storing_secret(client: TestClient, monkeypatch) -> None:
    source = _source(client, config={"account": "ernanhughes", "auth": "token",
                                     "token_env": "MISSION_CONTROL_TEST_GH_TOKEN"})
    monkeypatch.delenv("MISSION_CONTROL_TEST_GH_TOKEN", raising=False)
    response = client.post(f"/api/cultivation/sources/{source['id']}/sync")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "auth_error"
    stored = client.get(f"/api/cultivation/sources/{source['id']}").json()
    assert stored["config"].get("token_env") == "MISSION_CONTROL_TEST_GH_TOKEN"
    assert "token" not in {key.lower() for key in stored["config"]}
    assert stored["last_error"] and "MISSION_CONTROL_TEST_GH_TOKEN" in stored["last_error"]


def test_rest_pagination_beyond_one_hundred(monkeypatch) -> None:
    import httpx as _httpx

    first = [{"node_id": f"R_page{i}", "nameWithOwner": f"o/r{i}", "name": f"r{i}",
              "visibility": "PUBLIC"} for i in range(100)]
    second = [{"node_id": f"R_page{100 + i}", "nameWithOwner": f"o/r{100 + i}",
               "name": f"r{100 + i}", "visibility": "PUBLIC"} for i in range(30)]

    class _Response:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.headers = {}

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None, params=None):
            assert url == "https://api.github.com/user/repos"
            page = int(params["page"])
            if page == 1:
                return _Response(first)
            if page == 2:
                return _Response(second)
            return _Response([])

    monkeypatch.setattr(_httpx, "Client", _Client)
    repos = github_module.fetch_via_rest(token="redacted", account="o")
    assert len(repos) == 130
    assert repos[0]["node_id"] == "R_page0"
    assert repos[-1]["node_id"] == "R_page129"
    # No silent truncation: the second page was required.
    assert all(repo["name"] for repo in repos)


def test_classification_heuristics_cover_inventory_kinds() -> None:
    cases = {
        "language": "book",
        "programmer.ie": "website",
        "hugo-bookkit": "library",
        "deep-example": "tutorial",
        "zotero-arxiv-daily": "dataset",
        "zeromodel": "research",
        "agent-runtimes": "infrastructure",
    }
    for name, expected in cases.items():
        repo = _repo("R_x", name)
        classification, rationale = github_module.infer_classification(repo)
        assert classification == expected, (name, classification, rationale)
    uncertain, _ = github_module.infer_classification(_repo("R_u", "zzz", language=None,
                                                             languages=[], description=""))
    assert uncertain == "unclassified"
    lifecycle, _ = github_module.infer_lifecycle(_repo("R_a", "old", is_archived=True))
    assert lifecycle == "archived"


def test_github_source_kind_accepted_without_path(client: TestClient) -> None:
    source = _source(client)
    assert source["kind"] == "github_repos"
    assert source["path"] == ""


def test_github_summary_shape(client: TestClient) -> None:
    source = _source(client)
    _sync_db(client, source["id"], fetcher=lambda: [_repo("R_s", "writer")])
    summary = client.get("/api/cultivation/github/summary").json()
    assert set(summary) >= {"discovered", "private", "applications_identified",
                            "books_identified", "completed_applications",
                            "published_applications", "goals"}
    assert summary["discovered"] == 1
    assert summary["applications_identified"] == 1


@pytest.mark.integration
def test_live_github_inventory_read_only(client: TestClient) -> None:
    """One real authenticated read-only check (gh CLI, no writes)."""
    import shutil

    if shutil.which("gh") is None:
        pytest.skip("gh CLI not available")
    source = _source(client)
    with client.app.state.database.session() as session:
        result = service.sync_github_repos(session, source["id"])
    assert result["status"] == "ok", result
    assert result["observed"]["repos_total"] >= 306
    assert result["observed"]["public"] + result["observed"]["private"] == result["observed"]["repos_total"]
