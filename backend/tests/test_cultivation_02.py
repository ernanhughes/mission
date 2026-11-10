"""MC-CULTIVATION-02 qualification: skills, blog source, cycles, HUD."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def hugo_site(tmp_path: Path) -> Path:
    root = tmp_path / "site" / "content" / "post"
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text(
        '+++\ntitle = "Alpha"\ndate = "2024-01-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    (root / "b.md").write_text(
        '+++\ntitle = "Beta"\ndraft = true\ndate = "2024-02-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    (root / "c.md").write_text("# No front matter here.\n", encoding="utf-8")
    (root / "d.md").write_text('+++\ntitle = "Broken"\ndate = [unclosed\n+++\n\nBody.\n', encoding="utf-8")
    (root / "e.md").write_text(
        '+++\ntitle = "Future"\ndate = "2099-01-01T00:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    bundle = root / "sub" / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "index.md").write_text(
        '+++\ntitle = "Bundle"\ndate = "2024-03-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    (root / "sub" / "_index.md").write_text('+++\ntitle = "Section"\n+++\n', encoding="utf-8")
    (root / "sub" / "f.md").write_text(
        '+++\ntitle = "Foxtrot"\ndate = "2024-04-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    (root / "sub" / "g.md").write_text(
        '---\ntitle: Golf\ndate: 2024-05-10\n---\n\nBody.\n', encoding="utf-8")
    (root / "notes.txt").write_text("not a post", encoding="utf-8")
    (root / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return root


def _goal(client: TestClient, **overrides) -> dict:
    payload = {"name": "T", "target_value": 100, "measurement_type": "count"}
    payload.update(overrides)
    response = client.post("/api/cultivation/goals", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _skill(client: TestClient, **overrides) -> dict:
    payload = {"name": "S"}
    payload.update(overrides)
    response = client.post("/api/cultivation/skills", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_skills_crud_pin_reorder_archive(client: TestClient) -> None:
    first = _skill(client, name="Blog Posts", icon="rss", pinned=True, pin_order=0)
    second = _skill(client, name="Books", pinned=True, pin_order=1)
    skills = {row["id"]: row for row in client.get("/api/cultivation/skills").json()}
    assert first["id"] in skills and second["id"] in skills
    client.post("/api/cultivation/skills/reorder", json={"ids": [second["id"], first["id"]]})
    ordered = client.get("/api/cultivation/skills").json()
    ids = [row["id"] for row in ordered]
    assert ids.index(second["id"]) < ids.index(first["id"])
    patched = client.patch(f"/api/cultivation/skills/{first['id']}", json={"name": "Blog"}).json()
    assert patched["name"] == "Blog"
    client.patch(f"/api/cultivation/skills/{first['id']}", json={"state": "archived"})
    visible = {row["id"] for row in client.get("/api/cultivation/skills").json()}
    assert first["id"] not in visible
    all_skills = {row["id"] for row in client.get("/api/cultivation/skills", params={"include_archived": True}).json()}
    assert first["id"] in all_skills


def test_goal_skill_assignment_preserves_goals(client: TestClient) -> None:
    skill = _skill(client, name="Writing")
    goal = _goal(client, name="Novel")
    assert goal["skill_id"] is None
    assigned = client.patch(f"/api/cultivation/goals/{goal['id']}", json={"skill_id": skill["id"]}).json()
    assert assigned["skill_id"] == skill["id"]
    assert assigned["skill_name"] == "Writing"
    assert assigned["progress"]["current"] == 0
    filtered = client.get("/api/cultivation/goals", params={"skill_id": skill["id"]}).json()
    assert {row["id"] for row in filtered} == {goal["id"]}
    detail = client.get(f"/api/cultivation/skills/{skill['id']}").json()
    assert detail["goals_total"] == 1
    assert [row["id"] for row in detail["goals"]] == [goal["id"]]


def test_hugo_source_counts_states(client: TestClient, hugo_site: Path) -> None:
    goal = _goal(client, name="Blog", baseline_value=100, baseline_provenance="user_assertion")
    skill = _skill(client, name="Blog Posts")
    source = client.post("/api/cultivation/sources", json={
        "name": "site", "kind": "hugo_blog", "skill_id": skill["id"],
        "goal_id": goal["id"], "path": str(hugo_site)}).json()
    assert source["last_status"] == "never_synced"
    result = client.post(f"/api/cultivation/sources/{source['id']}/sync").json()
    assert result["status"] == "ok", result
    observed = result["observed"]
    assert observed["published"] == 4, observed
    assert observed["drafts"] == 2, observed
    assert observed["unknown"] == 2, observed
    assert observed["excluded"] == 3, observed
    # Same title, different files stay distinct; nothing is double counted.
    items = client.get(f"/api/cultivation/goals/{goal['id']}/items").json()
    assert len(items) == 8
    assert len({item["id"] for item in items}) == 8
    by_title = {item["title"]: item for item in items}
    assert by_title["Bundle"]["source_ref"].endswith("sub/bundle/index.md")
    # Live count drives current; user-attested milestone is preserved, not erased.
    tracked = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert tracked["progress"]["current"] == 4.0
    assert tracked["progress"]["live_sync_at"] is not None
    assert "user-attested" in (tracked["progress"]["estimate_label"] or "")
    assert tracked["progress"]["disagreement"] is not None
    assert "100" in tracked["progress"]["disagreement"]
    # Milestones for what was actually observed; historical achievement kept.
    assert set(tracked["progress"]["milestones_reached"]) == {1.0}
    events = client.get(f"/api/cultivation/goals/{goal['id']}/events").json()
    assert any(event["event_type"] == "synced" for event in events)


def test_hugo_incremental_and_removal(client: TestClient, hugo_site: Path) -> None:
    goal = _goal(client, name="Blog")
    source = client.post("/api/cultivation/sources", json={
        "name": "site", "kind": "hugo_blog", "goal_id": goal["id"], "path": str(hugo_site)}).json()
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    before = {item["id"]: item for item in client.get(f"/api/cultivation/goals/{goal['id']}/items").json()}
    # No-op resync: no duplicate items, no new stage events for unchanged posts.
    events_before = len(client.get(f"/api/cultivation/goals/{goal['id']}/events").json())
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    after = {item["id"]: item for item in client.get(f"/api/cultivation/goals/{goal['id']}/items").json()}
    assert set(after) == set(before)
    events_after = client.get(f"/api/cultivation/goals/{goal['id']}/events").json()
    stage_events = [event for event in events_after[:50]
                    if event["event_type"] in ("stage_changed", "completed") and
                    "Observed by source" in (event["note"] or "")]
    assert not stage_events or len(events_after) - events_before <= 2  # only the sync record(s)
    # Edit one file: stage follows the file.
    target = next(item for item in after.values() if item["title"] == "Alpha")
    (hugo_site / "a.md").write_text(
        '+++\ntitle = "Alpha"\ndraft = true\ndate = "2024-01-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    moved = next(item for item in client.get(f"/api/cultivation/items/{target['id']}").json()["memberships"]
                 if item["goal_id"] == goal["id"])
    assert moved["stage"] != "published"
    # Delete a file: item leaves the qualifying set but history is kept.
    doomed = next(item for item in after.values() if item["title"] == "Foxtrot")
    (hugo_site / "sub" / "f.md").unlink()
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    gone = next(item for item in client.get(f"/api/cultivation/items/{doomed['id']}").json()["memberships"]
                if item["goal_id"] == goal["id"])
    assert gone["stage"] != "published"
    history = client.get(f"/api/cultivation/items/{doomed['id']}/events").json()
    assert any(event["event_type"] == "source_removed" for event in history)


def test_hugo_manual_hold_not_overwritten(client: TestClient, hugo_site: Path) -> None:
    goal = _goal(client, name="Blog")
    source = client.post("/api/cultivation/sources", json={
        "name": "site", "kind": "hugo_blog", "goal_id": goal["id"], "path": str(hugo_site)}).json()
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    item = next(item for item in client.get(f"/api/cultivation/goals/{goal['id']}/items").json()
                if item["title"] == "Alpha")
    membership = next(m for m in item["memberships"] if m["goal_id"] == goal["id"])
    assert membership["stage"] == "published"
    # Owner moves it back explicitly: the next sync must not overwrite the manual record.
    client.patch(f"/api/cultivation/items/{item['id']}/goals/{goal['id']}/stage",
                 json={"stage": "editing", "note": "Needs another pass"})
    (hugo_site / "a.md").write_text(
        (hugo_site / "a.md").read_text(encoding="utf-8") + "\nMore.\n", encoding="utf-8")
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    held = next(m for m in client.get(f"/api/cultivation/items/{item['id']}").json()["memberships"]
                if m["goal_id"] == goal["id"])
    assert held["stage"] == "editing"


def test_hugo_stale_source_preserves_observation(client: TestClient, hugo_site: Path) -> None:
    goal = _goal(client, name="Blog", baseline_value=100, baseline_provenance="user_assertion")
    source = client.post("/api/cultivation/sources", json={
        "name": "site", "kind": "hugo_blog", "goal_id": goal["id"], "path": str(hugo_site)}).json()
    client.post(f"/api/cultivation/sources/{source['id']}/sync")
    assert client.get(f"/api/cultivation/goals/{goal['id']}").json()["progress"]["current"] == 4.0
    import shutil
    shutil.rmtree(hugo_site)
    result = client.post(f"/api/cultivation/sources/{source['id']}/sync").json()
    assert result["status"] == "stale"
    assert result["observed"]["published"] == 4
    kept = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert kept["progress"]["current"] == 4.0  # last known kept, never zeroed
    assert kept["progress"]["live_stale"] is True


def test_cycles_snapshot_and_rollover(client: TestClient) -> None:
    cycles = {row["number"]: row for row in client.get("/api/cultivation/cycles").json()}
    assert 5 in cycles  # seeded snapshot, no invented start date
    first = cycles[5]
    assert first["day"]["mode"] == "snapshot"
    assert first["day"]["day"] == 50
    assert "Day 50 / 100" in first["day"]["label"]
    assert first["start_date"] is None
    # Snapshot does not advance on its own.
    again = client.get(f"/api/cultivation/cycles/{first['id']}").json()
    assert again["day"]["day"] == 50 and again["day"]["mode"] == "snapshot"
    # Setting a start date enables Dublin-day calculation.
    ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
    dated = client.patch(f"/api/cultivation/cycles/{first['id']}",
                         json={"start_date": ten_days_ago}).json()
    expected = (date.today() - date.fromisoformat(ten_days_ago)).days + 1
    assert dated["day"]["mode"] == "calculated"
    assert dated["day"]["day"] == expected
    # Focus goals + completions attributed by event dates, not scan time.
    goal = _goal(client, name="Cycle Book")
    item = client.post("/api/cultivation/items", json={
        "title": "Done", "goal_ids": [goal["id"]], "stage": "published"}).json()
    assert item
    client.put(f"/api/cultivation/cycles/{first['id']}/focus", json={"goal_ids": [goal["id"]]})
    progress = client.get(f"/api/cultivation/cycles/{first['id']}").json()["progress"]
    assert progress["window"] is not None
    focus = next(entry for entry in progress["focus"] if entry["goal_id"] == goal["id"])
    assert focus["completions_in_window"] == 1
    # Explicit rollover: old completes, next opens with focus copied, goals intact.
    # Roll over a fresh cycle so the seeded Cycle 5 snapshot stays untouched.
    mine = client.post("/api/cultivation/cycles", json={"focus_goal_ids": [goal["id"]]}).json()
    mine_number = mine["number"]
    nxt = client.post(f"/api/cultivation/cycles/{mine['id']}/rollover").json()
    assert nxt["number"] == mine_number + 1
    assert nxt["state"] == "active"
    assert goal["id"] in nxt["focus_goal_ids"]
    assert client.get(f"/api/cultivation/cycles/{mine['id']}").json()["state"] == "completed"
    assert client.get(f"/api/cultivation/goals/{goal['id']}").json()["progress"]["current"] == 1
    # Rollover of a completed cycle is rejected: no silent double-roll.
    assert client.post(f"/api/cultivation/cycles/{mine['id']}/rollover").status_code == 409


def test_cycle_restart_persistence(client: TestClient, runtime) -> None:
    from helpers import open_client

    cycle = client.post("/api/cultivation/cycles", json={"number": 7, "snapshot_day": 12}).json()
    with open_client(runtime) as reopened:
        fetched = reopened.get(f"/api/cultivation/cycles/{cycle['id']}").json()
        assert fetched["day"]["day"] == 12
        assert fetched["day"]["mode"] == "snapshot"


def test_seed_adds_skills_source_and_cycle(client: TestClient) -> None:
    from mission_control.config import RuntimeSettings  # noqa: F401 (documents seed path)
    from mission_control.persistence.db import Database
    from mission_control.persistence.seed import seed_defaults

    database = Database(client.app.state.settings)
    with database.session() as session:
        seed_defaults(session, client.app.state.settings)
    skills = {row["id"]: row for row in client.get("/api/cultivation/skills").json()}
    assert "blog-posts" in skills and "books" in skills
    assert skills["blog-posts"]["pinned"] is True
    goals = {row["id"]: row for row in client.get("/api/cultivation/goals").json()}
    assert goals["published_books"]["skill_id"] == "books"
    assert goals["blog_posts"]["skill_id"] == "blog-posts"
    cycles = client.get("/api/cultivation/cycles").json()
    assert any(row["number"] == 5 and row["day"]["mode"] == "snapshot"
               and row["day"]["day"] == 50 for row in cycles)
    # Seeded cycle 5 keeps its focus goals and does not invent a start date.
    five = next(row for row in cycles if row["number"] == 5)
    assert five["start_date"] is None
    assert set(five["focus_goal_ids"]) >= {"published_books", "blog_posts"}


def test_no_model_calls_in_cultivation_stack() -> None:
    import pathlib
    backend = pathlib.Path(__file__).resolve().parents[1] / "mission_control" / "cultivation"
    for relative in ("service.py", "sources.py"):
        source = (backend / relative).read_text(encoding="utf-8").casefold()
        assert "inference" not in source, relative
        assert "httpx" not in source, relative
        assert "chat/completions" not in source, relative
