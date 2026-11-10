"""MC-CULTIVATION scripts: numbered self-hypnosis files as a live-counted goal.

Only ``ScriptNNN.md`` files count (variants like ``Script052s.md`` or names
with spaces count too); Morning files, themed notes, audio and dot-dirs are
context, never counted. A weekly-rhythm goal is fed one unit per new script.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DAY = 86400


@pytest.fixture
def script_dir(tmp_path: Path) -> Path:
    root = tmp_path / "script"
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    recent = now - DAY
    old = now - 30 * DAY
    files = {
        "Script001.md": ("# Script 001.\n", old),
        "Script002.md": ("# Script 002.\n", recent),
        "Script052s.md": ("# Variant.\n", recent),
        "Script036_not your money.md": ("# Spaced name.\n", recent),
        "sub/Script057a.md": ("# Nested.\n", recent),
        "Morning001.md": ("# Morning.\n", recent),
        "OceanOfEnergy.md": ("# Themed.\n", recent),
        "perfect belief.md": ("# Lowercase.\n", recent),
        "gpt-hypnosis.txt": ("notes\n", recent),
    }
    (root / "sub").mkdir(exist_ok=True)
    (root / "audio").mkdir(exist_ok=True)
    (root / "audio" / "take.mp3").write_bytes(b"\x00" * 16)
    (root / ".git").mkdir(exist_ok=True)
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "Script099_bad.md").write_bytes(b"\xff\xfe\x00not-utf8")
    for rel, (text, stamp) in files.items():
        target = root / rel
        target.write_text(text, encoding="utf-8")
        os.utime(target, (stamp, stamp))
    os.utime(root / "Script099_bad.md", (recent, recent))
    return root


def _goal(client: TestClient, **overrides) -> dict:
    payload = {"name": "T", "target_value": 100, "measurement_type": "count"}
    payload.update(overrides)
    response = client.post("/api/cultivation/goals", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _sync(client: TestClient, source_id: str) -> dict:
    response = client.post(f"/api/cultivation/sources/{source_id}/sync")
    assert response.status_code == 200, response.text
    return response.json()


def _measurements(client: TestClient, goal_id: str) -> list[dict]:
    return client.get(f"/api/cultivation/goals/{goal_id}/measurements").json()


def test_scan_counts_only_numbered_scripts(script_dir: Path) -> None:
    from mission_control.cultivation.sources import scan_numbered_files

    scan = scan_numbered_files(script_dir)
    assert scan.published == 5, sorted(post.identity for post in scan.posts)
    assert scan.unknown == 1
    assert scan.drafts == 0
    # Morning/themed/notes/audio/hidden-tooling files are excluded, not errors.
    assert scan.excluded == 5, scan.candidates
    assert scan.candidates == 11
    assert not scan.errors
    by_id = {post.identity: post for post in scan.posts}
    assert set(by_id) >= {"Script001.md", "Script052s.md",
                          "Script036_not your money.md", "sub/Script057a.md"}
    assert by_id["Script036_not your money.md"].title == "Script036 not your money"
    assert by_id["Script099_bad.md"].state == "unknown"
    assert "unreadable" in by_id["Script099_bad.md"].reason
    assert "Morning001.md" not in by_id
    # Item dates follow file mtimes (portable; no commit history consulted).
    stamp = (by_id["Script001.md"].date or datetime.now(timezone.utc)).timestamp()
    assert abs(stamp - (time.time() - 30 * DAY)) < 5 * DAY


def test_sync_live_count_idempotent_and_feeds_weekly(client: TestClient, script_dir: Path) -> None:
    count = _goal(client, name="Scripts")
    weekly = _goal(client, name="Weekly Script", measurement_type="recurring",
                   recurring_mode="period", window_days=7, target_value=1)
    assert weekly["recurring_mode"] == "period"
    source = client.post("/api/cultivation/sources", json={
        "name": "scripts", "kind": "numbered_files", "goal_id": count["id"],
        "path": str(script_dir), "config": {"period_goal_id": weekly["id"]}}).json()
    result = _sync(client, source["id"])
    assert result["status"] == "ok", result
    assert result["observed"]["published"] == 5
    assert result["observed"]["unknown"] == 1
    tracked = client.get(f"/api/cultivation/goals/{count['id']}").json()
    assert tracked["evidence_source"] == "numbered_files"
    assert tracked["progress"]["current"] == 5.0
    assert tracked["progress"]["live_sync_at"] is not None
    items = client.get(f"/api/cultivation/goals/{count['id']}/items").json()
    assert len(items) == 6  # 5 published scripts + 1 unreadable, tracked but not counted
    assert len({item["id"] for item in items}) == 6
    assert all(item["id"].startswith("script-") for item in items)
    # The weekly goal is fed one unit per new published script, dated at the file.
    fed = _measurements(client, weekly["id"])
    assert len(fed) == 5
    assert all(row["value"] == 1.0 and row["source"] == f"sync:{source['id']}" for row in fed)
    # Idempotent resync: no duplicate items, no duplicate weekly units.
    seen_event_ids = {event["id"] for event in client.get(f"/api/cultivation/goals/{count['id']}/events").json()}
    _sync(client, source["id"])
    again = {item["id"] for item in client.get(f"/api/cultivation/goals/{count['id']}/items").json()}
    assert len(again) == 6
    assert len(_measurements(client, weekly["id"])) == 5
    new_events = [event for event in client.get(f"/api/cultivation/goals/{count['id']}/events").json()
                  if event["id"] not in seen_event_ids]
    assert {event["event_type"] for event in new_events} <= {"synced", "milestone"}


def test_weekly_window_counts_only_recent_scripts(client: TestClient, script_dir: Path) -> None:
    count = _goal(client, name="Scripts")
    weekly = _goal(client, name="Weekly Script", measurement_type="recurring",
                   recurring_mode="period", window_days=7, target_value=1)
    source = client.post("/api/cultivation/sources", json={
        "name": "scripts", "kind": "numbered_files", "goal_id": count["id"],
        "path": str(script_dir), "config": {"period_goal_id": weekly["id"]}}).json()
    _sync(client, source["id"])
    assert client.get(f"/api/cultivation/goals/{count['id']}").json()["progress"]["current"] == 5.0
    rhythm = client.get(f"/api/cultivation/goals/{weekly['id']}").json()
    # Four scripts dated this week; the 30-day-old Script001 stays history.
    assert rhythm["progress"]["current"] == 4.0
    assert rhythm["progress"]["achieved"] is True
    # Cycle attribution uses file dates: the 30-day-old script does not
    # count as started in a fresh window; recently observed files do.
    # (The unreadable file has no date, so its start falls back to sync time.)
    start = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()
    cycle = client.post("/api/cultivation/cycles",
                        json={"start_date": start, "length_days": 100}).json()
    client.put(f"/api/cultivation/cycles/{cycle['id']}/focus", json={"goal_ids": [count["id"]]})
    items = client.get(f"/api/cultivation/goals/{count['id']}/items").json()
    focus = next(entry for entry in client.get(f"/api/cultivation/cycles/{cycle['id']}").json()["progress"]["focus"]
                 if entry["goal_id"] == count["id"])
    assert focus["started_in_window"] == 5
    old = next(item for item in items if item["title"] == "Script001")
    old_membership = next(m for m in old["memberships"] if m["goal_id"] == count["id"])
    assert old_membership["quality_evidence"]["first_evidence_ts"][:10] < start


def test_removal_hold_and_stale(client: TestClient, script_dir: Path) -> None:
    count = _goal(client, name="Scripts")
    source = client.post("/api/cultivation/sources", json={
        "name": "scripts", "kind": "numbered_files", "goal_id": count["id"],
        "path": str(script_dir)}).json()
    _sync(client, source["id"])
    assert client.get(f"/api/cultivation/goals/{count['id']}").json()["progress"]["current"] == 5.0
    # Owner moves a script back explicitly: the next sync must not overwrite it.
    first = next(item for item in client.get(f"/api/cultivation/goals/{count['id']}/items").json()
                 if item["title"] == "Script001")
    client.patch(f"/api/cultivation/items/{first['id']}/goals/{count['id']}/stage",
                 json={"stage": "editing", "note": "Needs another pass"})
    (script_dir / "Script001.md").write_text("# Script 001.\n\nMore.\n", encoding="utf-8")
    _sync(client, source["id"])
    held = next(m for m in client.get(f"/api/cultivation/items/{first['id']}").json()["memberships"]
                if m["goal_id"] == count["id"])
    assert held["stage"] == "editing"
    # Delete a file: the item leaves the qualifying set but history is kept.
    doomed = next(item for item in client.get(f"/api/cultivation/goals/{count['id']}/items").json()
                  if item["title"] == "Script002")
    (script_dir / "Script002.md").unlink()
    _sync(client, source["id"])
    gone = next(m for m in client.get(f"/api/cultivation/items/{doomed['id']}").json()["memberships"]
                if m["goal_id"] == count["id"])
    assert gone["stage"] != "published"
    assert client.get(f"/api/cultivation/goals/{count['id']}").json()["progress"]["current"] == 4.0
    history = client.get(f"/api/cultivation/items/{doomed['id']}/events").json()
    assert any(event["event_type"] == "source_removed" for event in history)
    # Missing directory: stale keeps the last observation, never zeroes it.
    import shutil
    shutil.rmtree(script_dir)
    result = _sync(client, source["id"])
    assert result["status"] == "stale"
    assert result["observed"]["published"] == 4
    kept = client.get(f"/api/cultivation/goals/{count['id']}").json()
    assert kept["progress"]["current"] == 4.0
    assert kept["progress"]["live_stale"] is True


def test_recurring_period_progress_and_validation(client: TestClient) -> None:
    # Unknown mode is rejected; the default stays per-day.
    bad = client.post("/api/cultivation/goals", json={
        "name": "Bad", "measurement_type": "recurring", "recurring_mode": "weekly",
        "window_days": 7, "target_value": 1})
    assert bad.status_code == 422, bad.text
    plain = _goal(client, name="Daily", measurement_type="recurring", window_days=7, target_value=1)
    assert plain["recurring_mode"] == "daily"
    patched = client.patch(f"/api/cultivation/goals/{plain['id']}",
                           json={"recurring_mode": "period"}).json()
    assert patched["recurring_mode"] == "period"
    # Period mode sums output inside the window against the target.
    goal = _goal(client, name="Rhythm", measurement_type="recurring",
                 recurring_mode="period", window_days=7, target_value=2)
    assert goal["progress"]["current"] == 0
    assert goal["progress"]["achieved"] is False
    today = datetime.now(timezone.utc)
    for stamp, value in ((today, 1.0), (today - timedelta(days=3), 1.0),
                         (today - timedelta(days=30), 1.0)):
        response = client.post(f"/api/cultivation/goals/{goal['id']}/measurements", json={
            "value": value, "observed_at": stamp.isoformat()})
        assert response.status_code == 201, response.text
    rhythm = client.get(f"/api/cultivation/goals/{goal['id']}").json()
    assert rhythm["progress"]["current"] == 2.0
    assert rhythm["progress"]["achieved"] is True
    assert rhythm["progress"]["percent"] == 100.0


@pytest.mark.skipif(shutil.which("git") is None, reason="git binary required for commit-date dating")
def test_git_add_dates_preferred_over_mtime(client: TestClient, tmp_path: Path) -> None:
    import subprocess

    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)

    def run_git(*args: str, env: dict | None = None) -> None:
        full = dict(os.environ)
        full.update(env or {})
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=60, env=full)
        assert completed.returncode == 0, completed.stderr

    run_git("init")
    (root / "Script001.md").write_text("# Old.\n", encoding="utf-8")
    run_git("-c", "user.email=t@t", "-c", "user.name=t", "add", "Script001.md")
    run_git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "first",
            "--date=2020-01-05T00:00:00+00:00")
    (root / "Script002.md").write_text("# New.\n", encoding="utf-8")
    run_git("-c", "user.email=t@t", "-c", "user.name=t", "add", "Script002.md")
    run_git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "second",
            "--date=2026-11-08T00:00:00+00:00")
    # All mtimes are now: mtime dating alone would put both scripts in-window.
    now = time.time()
    os.utime(root / "Script001.md", (now, now))
    os.utime(root / "Script002.md", (now, now))
    head_before = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=60).stdout.strip()

    count = _goal(client, name="Scripts")
    weekly = _goal(client, name="Weekly Script", measurement_type="recurring",
                   recurring_mode="period", window_days=7, target_value=1)
    source = client.post("/api/cultivation/sources", json={
        "name": "scripts", "kind": "numbered_files", "goal_id": count["id"],
        "path": str(root), "config": {"period_goal_id": weekly["id"]}}).json()
    result = _sync(client, source["id"])
    assert result["status"] == "ok", result
    assert result["observed"]["published"] == 2
    # The sync never writes to the repository.
    assert subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=60).stdout.strip() == head_before
    assert subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, timeout=60).stdout.strip() == ""
    # Commit dates win: the 2020 script keeps its date, stays out of the week.
    items = {item["title"]: item for item in client.get(f"/api/cultivation/goals/{count['id']}/items").json()}
    old_membership = next(m for m in items["Script001"]["memberships"] if m["goal_id"] == count["id"])
    assert (old_membership["completed_at"] or "").startswith("2020-01-05")
    assert old_membership["quality_evidence"]["first_evidence_ts"].startswith("2020-01-05")
    rhythm = client.get(f"/api/cultivation/goals/{weekly['id']}").json()
    assert rhythm["progress"]["current"] == 1.0
    assert rhythm["progress"]["achieved"] is True


def test_unsupported_source_kind_rejected(client: TestClient, script_dir: Path) -> None:
    response = client.post("/api/cultivation/sources", json={
        "name": "nope", "kind": "git_log", "path": str(script_dir)})
    assert response.status_code == 422, response.text


@pytest.mark.skipif(not Path(r"C:\script").is_dir(), reason="seed scripts source is path-gated")
def test_seed_adds_scripts_skill_goals_and_source(client: TestClient) -> None:
    skills = {row["id"]: row for row in client.get("/api/cultivation/skills").json()}
    assert skills["scripts"]["pinned"] is True
    goals = {row["id"]: row for row in client.get("/api/cultivation/goals").json()}
    assert goals["scripts_published"]["skill_id"] == "scripts"
    assert goals["weekly_script"]["skill_id"] == "scripts"
    assert goals["weekly_script"]["recurring_mode"] == "period"
    assert goals["weekly_script"]["window_days"] == 7
    sources = client.get("/api/cultivation/sources").json()
    seeded = next(row for row in sources if row["id"] == "src-scripts")
    assert seeded["kind"] == "numbered_files"
    assert seeded["goal_id"] == "scripts_published"
    assert seeded["config"].get("period_goal_id") == "weekly_script"


def test_scripts_sync_makes_no_model_calls(client: TestClient, script_dir: Path) -> None:
    count = _goal(client, name="Scripts")
    source = client.post("/api/cultivation/sources", json={
        "name": "scripts", "kind": "numbered_files", "goal_id": count["id"],
        "path": str(script_dir)}).json()
    before = set(sys.modules)
    _sync(client, source["id"])
    leaked = {name for name in set(sys.modules) - before
              if name.split(".")[0] in {"openai", "anthropic", "transformers", "torch"}}
    assert not leaked
