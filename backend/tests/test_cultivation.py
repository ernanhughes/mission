"""MC-CULTIVATION-01 qualification: goals, items, lifecycle, ranks, HUD."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _goal(client: TestClient, **overrides) -> dict:
    payload = {"name": "Test Goal", "target_value": 10, "measurement_type": "count"}
    payload.update(overrides)
    response = client.post("/api/cultivation/goals", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_goal_creation_and_editing(client: TestClient) -> None:
    goal = _goal(client, name="Write Books", description="All books", category="books")
    assert goal["progress"]["current"] == 0
    assert goal["progress"]["achieved"] is False
    assert goal["progress"]["unknown_reason"] is None

    patched = client.patch(f"/api/cultivation/goals/{goal['id']}",
                           json={"name": "Write Books!", "target_value": 50}).json()
    assert patched["name"] == "Write Books!"
    assert patched["target_value"] == 50
    assert patched["progress"]["target"] == 50


def test_multiple_simultaneous_goals(client: TestClient) -> None:
    first = _goal(client, name="Alpha")
    second = _goal(client, name="Beta", measurement_type="threshold_up", unit="reps", target_value=100)
    goals = client.get("/api/cultivation/goals").json()
    assert {first["id"], second["id"]} <= {goal["id"] for goal in goals}


def _unpin_seeded(client: TestClient) -> None:
    """Seeded catalogue pins published_books/blog_posts; tests needing pin
    control start from a clean slate without touching user data."""
    for goal_id in ("published_books", "blog_posts"):
        response = client.patch(f"/api/cultivation/goals/{goal_id}", json={"pinned": False})
        assert response.status_code == 200, response.text


def test_pin_persistence_and_reorder(client: TestClient) -> None:
    _unpin_seeded(client)
    first = _goal(client, name="Pinned One", pinned=True, pin_order=0)
    second = _goal(client, name="Pinned Two", pinned=True, pin_order=1)
    hud = client.get("/api/cultivation/hud").json()
    assert hud["primary"]["id"] == first["id"]
    assert [goal["id"] for goal in hud["pinned"]] == [first["id"], second["id"]]
    client.post("/api/cultivation/goals/reorder", json={"ids": [second["id"], first["id"]]})
    hud = client.get("/api/cultivation/hud").json()
    assert hud["primary"]["id"] == second["id"]
    assert [goal["id"] for goal in hud["pinned"]] == [second["id"], first["id"]]


def test_count_goal_and_item_lifecycle(client: TestClient) -> None:
    goal = _goal(client, name="Books", qualifying_stage="published")
    item = client.post("/api/cultivation/items", json={
        "title": "Techno-Prophet", "goal_ids": [goal["id"]], "stage": "editing"}).json()
    assert item["memberships"][0]["stage"] == "editing"

    goal_now = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert goal_now["progress"]["current"] == 0
    assert goal_now["progress"]["pipeline"] == {"editing": 1}

    client.patch(f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/stage",
                 json={"stage": "published", "note": "Released"})
    goal_done = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert goal_done["progress"]["current"] == 1
    assert goal_done["progress"]["pipeline"] == {"published": 1}

    events = client.get(f"/api/cultivation/goals/{goal['id']}/events").json()
    types = [event["event_type"] for event in events]
    assert "stage_changed" in types and "completed" in types

    # Reversal removes the count but keeps the history.
    client.patch(f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/stage",
                 json={"stage": "editing", "note": "Recalled"})
    reopened = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert reopened["progress"]["current"] == 0
    events = client.get(f"/api/cultivation/goals/{goal['id']}/events").json()
    assert "reopened" in [event["event_type"] for event in events]

    # Historical completion date can be recorded.
    client.patch(f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/stage",
                 json={"stage": "published"},
                 params={})
    response = client.patch(
        f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/stage?completed_at=2024-05-01T00:00:00Z",
        json={"stage": "published"})
    assert response.status_code == 200
    detail = client.get(f"/api/cultivation/items/{item['id']}").json()
    membership = next(m for m in detail["memberships"] if m["goal_id"] == goal["id"])
    assert membership["completed_at"] == "2024-05-01T00:00:00Z"


def test_threshold_up_goal(client: TestClient) -> None:
    goal = _goal(client, name="Press-ups", measurement_type="threshold_up",
                 unit="press-ups", target_value=100)
    assert goal["progress"]["current"] is None
    assert "No measurements" in (goal["progress"]["unknown_reason"] or "")
    client.post(f"/api/cultivation/goals/{goal['id']}/measurements",
                json={"value": 60, "observed_at": "2026-11-01T00:00:00Z"})
    mid = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert mid["progress"]["current"] == 60
    assert mid["progress"]["achieved"] is False
    client.post(f"/api/cultivation/goals/{goal['id']}/measurements",
                json={"value": 100, "observed_at": "2026-11-09T00:00:00Z"})
    done = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert done["progress"]["achieved"] is True
    assert done["progress"]["percent"] == 100.0


def test_threshold_down_requires_baseline(client: TestClient) -> None:
    goal = _goal(client, name="Weight", measurement_type="threshold_down",
                 unit="lb", target_value=150, privacy="private")
    assert goal["progress"]["current"] is None
    assert "baseline" in (goal["progress"]["unknown_reason"] or "")
    client.patch(f"/api/cultivation/goals/{goal['id']}",
                 json={"baseline_value": 180, "baseline_provenance": "user_assertion",
                       "baseline_note": "Weighed Monday"})
    client.post(f"/api/cultivation/goals/{goal['id']}/measurements",
                json={"value": 165, "observed_at": "2026-11-09T00:00:00Z"})
    weighed = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert weighed["progress"]["current"] == 165
    assert weighed["progress"]["percent"] == pytest.approx(50.0)
    assert weighed["progress"]["achieved"] is False


def test_recurring_goal(client: TestClient) -> None:
    goal = _goal(client, name="Daily Habit", measurement_type="recurring",
                 target_value=100, window_days=3)
    assert "window" in (goal["progress"]["unknown_reason"] or "") or goal["progress"]["current"] == 0.0
    # Two of the last three days met: not yet achieved.
    client.post(f"/api/cultivation/goals/{goal['id']}/measurements",
                json={"value": 100, "observed_at": "2026-11-09T08:00:00Z"})
    client.post(f"/api/cultivation/goals/{goal['id']}/measurements",
                json={"value": 100, "observed_at": "2026-11-08T08:00:00Z"})
    partial = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert partial["progress"]["achieved"] is False
    client.post(f"/api/cultivation/goals/{goal['id']}/measurements",
                json={"value": 120, "observed_at": "2026-11-07T08:00:00Z"})
    full = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert full["progress"]["current"] == 3.0
    assert full["progress"]["achieved"] is True


def test_historical_baseline_entry_and_correction(client: TestClient) -> None:
    goal = _goal(client, name="Books", baseline_value=30, baseline_provenance="estimate",
                 baseline_note="Owner estimate")
    assert goal["progress"]["current"] == 30
    assert goal["progress"]["estimate_label"] is not None
    assert "estimate" in (goal["progress"]["estimate_label"] or "")
    item = client.post("/api/cultivation/items", json={
        "title": "New Book", "goal_ids": [goal["id"]], "stage": "published"}).json()
    assert item["memberships"][0]["completed_at"] is not None
    tracked = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert tracked["progress"]["current"] == 31
    client.patch(f"/api/cultivation/goals/{goal['id']}",
                 json={"baseline_value": 29, "baseline_note": "One title moved to tracked items"})
    corrected = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert corrected["progress"]["current"] == 30
    events = client.get(f"/api/cultivation/goals/{goal['id']}/events").json()
    assert "correction" in [event["event_type"] for event in events]


def test_multi_goal_membership_and_dedup(client: TestClient) -> None:
    all_books = _goal(client, name="All Books")
    fiction = _goal(client, name="Fiction")
    item = client.post("/api/cultivation/items", json={
        "title": "A Novel", "goal_ids": [all_books["id"], fiction["id"]],
        "stage": "published"}).json()
    assert len(item["memberships"]) == 2
    assert client.get(f"/api/cultivation/goals/{all_books['id']}").json()["progress"]["current"] == 1
    assert client.get(f"/api/cultivation/goals/{fiction['id']}").json()["progress"]["current"] == 1
    # Same item twice in one goal is rejected, not double counted.
    duplicate = client.post(f"/api/cultivation/items/{item['id']}/goals/{all_books['id']}")
    assert duplicate.status_code == 409
    assert client.get(f"/api/cultivation/goals/{all_books['id']}").json()["progress"]["current"] == 1
    # A distinct edition is a distinct item.
    edition = client.post("/api/cultivation/items", json={
        "title": "A Novel (Illustrated Edition)", "goal_ids": [all_books["id"]],
        "stage": "published"}).json()
    assert edition["id"] != item["id"]
    assert client.get(f"/api/cultivation/goals/{all_books['id']}").json()["progress"]["current"] == 2


def test_qualified_count_goal(client: TestClient) -> None:
    goal = _goal(client, name="Perfect Repos", measurement_type="qualified_count")
    item = client.post("/api/cultivation/items", json={
        "title": "mission", "goal_ids": [goal["id"]], "stage": "published"}).json()
    assert client.get(f"/api/cultivation/goals/{goal['id']}").json()["progress"]["current"] == 0
    client.patch(f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/qualify",
                 json={"qualified": True,
                       "quality_evidence": {"tests": "passing", "review": "accepted"},
                       "note": "Meets the standard"})
    qualified = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert qualified["progress"]["current"] == 1
    detail = client.get(f"/api/cultivation/items/{item['id']}").json()
    membership = next(m for m in detail["memberships"] if m["goal_id"] == goal["id"])
    assert membership["qualified"] is True
    assert membership["quality_evidence"] == {"tests": "passing", "review": "accepted"}
    # A review verdict alone is not qualification evidence: unqualifying drops it.
    client.patch(f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/qualify",
                 json={"qualified": False, "note": "Standard revised"})
    assert client.get(f"/api/cultivation/goals/{goal['id']}").json()["progress"]["current"] == 0


def test_milestones_and_ranks(client: TestClient) -> None:
    goal = _goal(client, name="Books", milestones=[1.0, 10.0])
    assert goal["progress"]["milestones_reached"] == []
    assert goal["progress"]["next_milestone"] == 1.0
    item = client.post("/api/cultivation/items", json={
        "title": "First", "goal_ids": [goal["id"]], "stage": "published"}).json()
    progressed = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert progressed["progress"]["milestones_reached"] == [1.0]
    events = client.get(f"/api/cultivation/goals/{goal['id']}/events").json()
    assert any(event["event_type"] == "milestone" and event["to_value"] == "1.0" for event in events)
    ranks = client.get("/api/cultivation/ranks").json()
    assert any(rank["id"] == "initiate" for rank in ranks)
    initiate = next(rank for rank in ranks if rank["id"] == "initiate")
    assert initiate["qualified"] is True
    _ = item


def test_manual_vs_verified_evidence(client: TestClient) -> None:
    goal = _goal(client, name="Books")
    item = client.post("/api/cultivation/items", json={
        "title": "Claimed", "goal_ids": [goal["id"]], "stage": "published"}).json()
    claimed = client.post(f"/api/cultivation/goals/{goal['id']}/evidence", json={
        "item_id": item["id"], "kind": "release_reference",
        "reference": "publisher page", "note": "Owner claims release"}).json()
    assert claimed["verified"] is False
    detail = client.get(f"/api/cultivation/items/{item['id']}").json()
    assert detail["memberships"][0]["evidence_status"] == "claimed"
    verified = client.post(f"/api/cultivation/goals/{goal['id']}/evidence", json={
        "item_id": item["id"], "kind": "release_reference",
        "reference": "ISBN registry", "verified": True}).json()
    assert verified["verified"] is True
    detail = client.get(f"/api/cultivation/items/{item['id']}").json()
    assert detail["memberships"][0]["evidence_status"] == "verified"


def test_archived_goals_excluded(client: TestClient) -> None:
    _unpin_seeded(client)
    goal = _goal(client, name="Old Hobby", pinned=True)
    assert client.get("/api/cultivation/hud").json()["primary"]["id"] == goal["id"]
    client.patch(f"/api/cultivation/goals/{goal['id']}", json={"state": "archived"})
    hud = client.get("/api/cultivation/hud").json()
    assert all(item["id"] != goal["id"] for item in hud["pinned"])
    visible = client.get("/api/cultivation/goals").json()
    assert all(item["id"] != goal["id"] for item in visible)
    all_goals = client.get("/api/cultivation/goals", params={"include_archived": True}).json()
    assert any(item["id"] == goal["id"] for item in all_goals)


def test_privacy_filter(client: TestClient) -> None:
    private = _goal(client, name="Secret Target", privacy="private")
    assert private["privacy"] == "private"
    standard = client.get("/api/cultivation/goals", params={"privacy": "standard"}).json()
    assert all(goal["id"] != private["id"] for goal in standard)
    assert any(goal["privacy"] == "private" for goal in client.get("/api/cultivation/goals").json())


def test_restart_persistence(client: TestClient, runtime) -> None:
    from helpers import open_client

    goal = _goal(client, name="Persistent", baseline_value=5, baseline_provenance="user_assertion")
    item = client.post("/api/cultivation/items", json={
        "title": "Kept", "goal_ids": [goal["id"]], "stage": "published"}).json()
    with open_client(runtime) as reopened:
        fetched = reopened.get(f"/api/cultivation/goals/{goal['id']}").json()
        assert fetched["progress"]["current"] == 6
        detail = reopened.get(f"/api/cultivation/items/{item['id']}").json()
        assert detail["title"] == "Kept"
        history = reopened.get(f"/api/cultivation/goals/{goal['id']}/events").json()
        assert len(history) >= 3
    _ = item


def test_starter_catalogue_seeded(client: TestClient) -> None:
    goals = {goal["id"]: goal for goal in client.get("/api/cultivation/goals").json()}
    for expected in ("published_books", "fiction_books", "technical_books", "blog_posts",
                     "movies", "songs", "research_papers", "applications", "repositories",
                     "perfect_repositories", "body_weight", "press_ups"):
        assert expected in goals, f"missing starter goal {expected}"
    books = goals["published_books"]
    assert books["pinned"] is True
    assert books["progress"]["current"] == 30
    assert books["progress"]["estimate_label"] is not None
    assert "inventory verification" in books["baseline_note"]
    blog = goals["blog_posts"]
    assert blog["state"] == "achieved"
    assert blog["progress"]["current"] == 100
    assert blog["progress"]["estimate_label"] is not None
    assert blog["baseline_provenance"] == "user_assertion"
    weight = goals["body_weight"]
    assert weight["privacy"] == "private"
    assert weight["progress"]["current"] is None  # no invented baseline
    perfect = goals["perfect_repositories"]
    assert perfect["measurement_type"] == "qualified_count"
    assert "renewal" in perfect["completion_criteria"]
    repos = goals["repositories"]
    assert repos["target_value"] == 1000
    assert 1000.0 in repos["milestones"]
    ranks = {rank["id"] for rank in client.get("/api/cultivation/ranks").json()}
    assert {"initiate", "qi_refinement", "foundation", "core_formation",
            "nascent_soul", "higher_realms"} <= ranks
    config = client.get("/api/cultivation/config").json()
    assert [stage["id"] for stage in config["stages"]] == [
        "idea", "development", "editing", "ready", "published"]


def test_seed_never_overwrites_user_goals(client: TestClient) -> None:
    from mission_control.config import RuntimeSettings  # noqa: F401 (documents seed path)
    goal = _goal(client, name="Custom")
    client.patch(f"/api/cultivation/goals/{goal['id']}", json={"name": "Custom Renamed"})
    # Re-running the seed must keep the user's edit and the starter catalogue.
    from mission_control.persistence.seed import seed_defaults
    from mission_control.persistence.db import Database
    database = Database(client.app.state.settings)
    with database.session() as session:
        seed_defaults(session, client.app.state.settings)
    renamed = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert renamed["name"] == "Custom Renamed"
    assert "published_books" in {item["id"] for item in client.get("/api/cultivation/goals").json()}


def test_no_model_calls_in_cultivation_stack() -> None:
    import pathlib
    backend = pathlib.Path(__file__).resolve().parents[1] / "mission_control"
    for relative in ("cultivation/service.py", "api/cultivation.py"):
        source = (backend / relative).read_text(encoding="utf-8").casefold()
        assert "inference" not in source, relative
        assert "httpx" not in source, relative
        assert "chat/completions" not in source, relative
