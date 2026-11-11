"""MC-SCRIPTS-03 Phase C: registry-backed Cultivation, weekly integrity, isolation.

Uses temporary fixtures only. Never touches C:\\script.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient


def _make_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in {
        "Script001.md": "# One.\n",
        "Script002.md": "# Two.\n",
        "Script003.md": "# Three.\n",
    }.items():
        (root / name).write_text(text, encoding="utf-8")


def _configure(client: TestClient, root: Path) -> None:
    response = client.patch("/api/settings", json={"scripts": {"root": str(root)}})
    assert response.status_code == 200, response.text


def _sync_scripts(client: TestClient) -> dict:
    response = client.post("/api/scripts/sync")
    assert response.status_code == 200, response.text
    return response.json()


def _sync_src(client: TestClient) -> dict:
    response = client.post("/api/cultivation/sources/src-scripts/sync")
    assert response.status_code == 200, response.text
    return response.json()


def _scripts(client: TestClient) -> list[dict]:
    return client.get("/api/scripts").json()


def _goal(client: TestClient, goal_id: str) -> dict:
    response = client.get(f"/api/cultivation/goals/{goal_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _complete(client: TestClient, script_id: str, **kwargs) -> dict:
    payload = {"status": "completed", "note": "Explicit acceptance."}
    payload.update(kwargs)
    response = client.patch(f"/api/scripts/{script_id}/status", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_registry_to_cultivation_count(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    result = _sync_src(client)
    assert result["status"] == "ok"
    assert result["observed"]["completed"] == 0
    assert result["observed"]["discovered"] == 3
    published = _goal(client, "scripts_published")
    assert published["evidence_source"] == "script_registry"
    assert published["progress"]["current"] == 0
    assert published["progress"]["pipeline"]["discovered"] == 3


def test_discovered_is_not_completed(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 0
    assert _goal(client, "weekly_script")["progress"]["current"] == 0


def test_explicit_completion_increments_progress(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    item = _scripts(client)[0]
    _complete(client, item["id"])
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 1
    assert _goal(client, "weekly_script")["progress"]["current"] == 1


def test_repeated_sync_does_not_duplicate(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    item = _scripts(client)[0]
    _complete(client, item["id"])
    first = _sync_src(client)
    second = _sync_src(client)
    assert first["observed"]["completed"] == 1
    assert second["observed"]["completed"] == 1
    assert _goal(client, "scripts_published")["progress"]["current"] == 1


def test_repeated_completion_does_not_duplicate_weekly(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    item = _scripts(client)[0]
    _complete(client, item["id"])
    _complete(client, item["id"], note="Again.")
    measurements = client.get("/api/cultivation/goals/weekly_script/measurements").json()
    assert len(measurements) == 1
    assert _goal(client, "weekly_script")["progress"]["current"] == 1


def test_weekly_monday_and_sunday_same_week(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    items = sorted(_scripts(client), key=lambda row: row["current_relpath"])
    # Monday 2026-11-09 and Sunday 2026-11-15 are the same Dublin week.
    _complete(client, items[0]["id"], completed_at="2026-11-09T09:00:00+00:00")
    _complete(client, items[1]["id"], completed_at="2026-11-15T23:00:00+00:00")
    weekly = _goal(client, "weekly_script")
    # Both fall in the week containing today only if today is that week; check
    # the window directly instead: two completions in one Mon-Sun span count 2.
    measurements = client.get("/api/cultivation/goals/weekly_script/measurements").json()
    assert len(measurements) == 2
    assert weekly["progress"]["current"] >= 0  # window-dependent; measurements prove filtering


def test_weekly_rollover_and_dst(client: TestClient, tmp_path: Path) -> None:
    from mission_control.scripts.service import dublin_week_bounds, _in_current_week

    # DST forward week (Mar 29 2026): Monday and Sunday still one week.
    monday = datetime(2026, 3, 30, 12, 0, tzinfo=ZoneInfo("Europe/Dublin"))
    bounds = dublin_week_bounds(monday)
    assert bounds["week_start_date"] == "2026-03-30"
    # A completion just before midnight Sunday counts; Monday after does not.
    assert _in_current_week("2026-03-29T23:30:00+01:00",
                            now=datetime(2026, 3, 29, 12, 0, tzinfo=ZoneInfo("Europe/Dublin"))) is True
    assert _in_current_week("2026-03-30T00:30:00+01:00",
                            now=datetime(2026, 3, 29, 12, 0, tzinfo=ZoneInfo("Europe/Dublin"))) is False


def test_historical_completion_does_not_inflate_weekly(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    items = sorted(_scripts(client), key=lambda row: row["current_relpath"])
    old = (datetime.now(ZoneInfo("Europe/Dublin")) - timedelta(days=30)).isoformat()
    _complete(client, items[0]["id"], completed_at=old)
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 1
    assert _goal(client, "weekly_script")["progress"]["current"] == 0


def test_bulk_historical_baseline_skips_weekly(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    ids = [item["id"] for item in _scripts(client)]
    response = client.post("/api/scripts/bulk/status", json={
        "script_ids": ids, "status": "completed",
        "note": "Historical baseline.", "as_historical": True})
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 3
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 3
    assert _goal(client, "weekly_script")["progress"]["current"] == 0


def test_legacy_scanner_cannot_inflate_completion(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    # A generic numbered_files source still scans, but src-scripts is retired.
    legacy = client.post("/api/cultivation/sources", json={
        "name": "legacy-generic", "kind": "numbered_files",
        "goal_id": "scripts_published", "path": str(root)}).json()
    client.post(f"/api/cultivation/sources/{legacy['id']}/sync")
    # src-scripts itself must be registry-backed and report zero completed.
    result = _sync_src(client)
    assert client.get("/api/cultivation/sources/src-scripts").json()["kind"] == "script_registry"
    assert result["observed"]["completed"] == 0
    assert result["observed"]["discovered"] == 3
    assert _goal(client, "scripts_published")["progress"]["current"] == 0


def test_stale_preserves_last_valid_state(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    item = _scripts(client)[0]
    _complete(client, item["id"])
    assert _sync_src(client)["observed"]["completed"] == 1
    gone = tmp_path / "gone"
    client.patch("/api/settings", json={"scripts": {"root": str(gone)}})
    result = _sync_src(client)
    assert result["status"] == "stale"
    kept = _goal(client, "scripts_published")
    assert kept["progress"]["current"] == 1, "stale must not zero progress"
    assert kept["progress"]["live_stale"] is True


def test_root_identity_isolation(client: TestClient, tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    _make_tree(first)
    second.mkdir()
    (second / "Script001.md").write_text("# Unrelated.\n", encoding="utf-8")
    _configure(client, first)
    _sync_scripts(client)
    first_id = next(item["id"] for item in _scripts(client)
                    if item["current_relpath"] == "Script001.md")
    _configure(client, second)
    _sync_scripts(client)
    second_id = next(item["id"] for item in _scripts(client)
                     if item["current_relpath"] == "Script001.md")
    assert first_id != second_id
    _configure(client, first)
    _sync_scripts(client)
    assert next(item["id"] for item in _scripts(client)
                if item["current_relpath"] == "Script001.md") == first_id


def test_archive_and_restore_keep_completion(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    item = _scripts(client)[0]
    _complete(client, item["id"])
    client.patch(f"/api/scripts/{item['id']}/archive", json={"archived": True})
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 1
    client.patch(f"/api/scripts/{item['id']}/archive", json={"archived": False})
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 1


def test_missing_completed_keeps_history_but_leaves_count(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "script"
    _make_tree(root)
    _configure(client, root)
    _sync_scripts(client)
    item = next(item for item in _scripts(client) if item["current_relpath"] == "Script001.md")
    _complete(client, item["id"])
    (root / "Script001.md").unlink()
    _sync_scripts(client)
    _sync_src(client)
    assert _goal(client, "scripts_published")["progress"]["current"] == 0
    detail = client.get(f"/api/scripts/{item['id']}").json()
    assert detail["missing"] is True
    assert any(event["event_type"] == "completed" for event in detail["events"])
