"""MC-CULTIVATION Blog Posts live integration: filesystem-backed weekly discipline.

Covers: recursive discovery (.md/.markdown, bundles, duplicates),
published/draft/scheduled/unknown classification, Hugo front matter (TOML/YAML/JSON),
weekly requirement (Mon-Sun Europe/Dublin), idempotent sync, stale preservation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient


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


def _blog_site(tmp_path: Path) -> Path:
    root = tmp_path / "blog" / "content" / "post"
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    this_week = now - timedelta(days=1)
    last_week = now - timedelta(days=9)
    # Published tech post this week (qualifies for weekly).
    (root / "tech.md").write_text(
        '+++\ntitle = "Tech Post"\ndate = "%s"\ncategories = ["AI"]\n+++\n\nBody.\n' % this_week.isoformat(),
        encoding="utf-8")
    # Published finance post last week.
    (root / "money.markdown").write_text(
        '---\ntitle: Money Post\ndate: %s\ncategories: [Finance]\n---\n\nBody.\n' % last_week.date().isoformat(),
        encoding="utf-8")
    # Draft.
    (root / "draft.md").write_text(
        '+++\ntitle = "Draft"\ndraft = true\ndate = "2024-01-01T00:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    # Scheduled future.
    (root / "future.md").write_text(
        '+++\ntitle = "Future"\ndate = "2099-01-01T00:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    # Bundle + duplicate identity prevention.
    bundle = root / "bundle"
    bundle.mkdir(exist_ok=True)
    (bundle / "index.md").write_text(
        '+++\ntitle = "Bundle"\ndate = "2024-03-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    (bundle / "index.markdown").write_text(
        '+++\ntitle = "Bundle Dup"\ndate = "2024-03-10T10:00:00Z"\n+++\n\nBody.\n', encoding="utf-8")
    (root / "_index.md").write_text('+++\ntitle = "Section"\n+++\n', encoding="utf-8")
    (root / "_index.markdown").write_text('+++\ntitle = "Section2"\n+++\n', encoding="utf-8")
    (root / "notes.txt").write_text("not a post", encoding="utf-8")
    # JSON front matter.
    (root / "json.md").write_text(
        '{"title": "JSON Post", "date": "2024-06-01T00:00:00Z", "categories": ["Technology"]}\n\nBody.\n',
        encoding="utf-8")
    # Expired.
    (root / "old.md").write_text(
        '+++\ntitle = "Old"\ndate = "2020-01-01T00:00:00Z"\nexpiryDate = "2021-01-01T00:00:00Z"\n+++\n\nBody.\n',
        encoding="utf-8")
    # Unknown: no front matter.
    (root / "mystery.md").write_text("# No front matter.\n", encoding="utf-8")
    return root


def test_blog_scanner_supports_markdown_bundles_duplicates(tmp_path: Path) -> None:
    from mission_control.cultivation.sources import scan_hugo_blog, blog_observation

    root = _blog_site(tmp_path)
    scan = scan_hugo_blog(root)
    # tech, money, bundle, json = 4 published; draft+future+old = 3 drafts; mystery = 1 unknown.
    assert scan.published == 4, [p.identity for p in scan.posts]
    assert scan.drafts == 3
    assert scan.unknown == 1
    # Duplicate bundle index.markdown is excluded, not double-counted; section indexes + txt excluded.
    # candidates = all files walked: tech, money, draft, future, bundle/index.md, bundle/index.markdown,
    # _index.md, _index.markdown, notes.txt, json, old, mystery = 12
    assert scan.candidates == 12
    assert scan.excluded == 4  # dup + 2 section indexes + txt
    assert any("Duplicate post identity" in e["error"] for e in scan.errors)
    obs = blog_observation(scan)
    assert obs["scheduled"] == 1
    assert obs["tech_published"] >= 2  # tech.md (AI) + json (Technology)
    assert obs["finance_published"] >= 1  # money.markdown
    assert obs["this_week"] == 1
    assert obs["timezone"] == "Europe/Dublin"
    assert len(obs["recent_posts"]) >= 4
    assert obs["latest_published_at"] is not None


def test_blog_sync_feeds_weekly_and_idempotent(client: TestClient, tmp_path: Path) -> None:
    root = _blog_site(tmp_path)
    count = _goal(client, name="Blog Lifetime")
    weekly = _goal(client, name="Weekly Blog", measurement_type="recurring",
                   recurring_mode="period", window_days=7, target_value=1)
    source = client.post("/api/cultivation/sources", json={
        "name": "blog", "kind": "hugo_blog", "goal_id": count["id"],
        "path": str(root), "config": {"period_goal_id": weekly["id"]}}).json()
    result = _sync(client, source["id"])
    assert result["status"] == "ok"
    assert result["observed"]["published"] == 4
    assert result["observed"]["scheduled"] == 1
    assert result["observed"]["tech_published"] >= 2
    tracked = client.get(f"/api/cultivation/goals/{count['id']}").json()
    assert tracked["evidence_source"] == "hugo_blog"
    assert tracked["progress"]["current"] == 4.0
    # Weekly fed by file dates: only this-week post counts.
    rhythm = client.get(f"/api/cultivation/goals/{weekly['id']}").json()
    assert rhythm["progress"]["current"] == 1.0
    assert rhythm["progress"]["achieved"] is True
    measurements = client.get(f"/api/cultivation/goals/{weekly['id']}/measurements").json()
    assert len(measurements) == 4  # one per new published post, dated at post
    # Idempotent resync: no duplicates.
    _sync(client, source["id"])
    assert len(client.get(f"/api/cultivation/goals/{weekly['id']}/measurements").json()) == 4
    items = client.get(f"/api/cultivation/goals/{count['id']}/items").json()
    assert len({i["id"] for i in items}) == len(items)


def test_blog_weekly_dublin_boundaries(tmp_path: Path) -> None:
    from mission_control.cultivation.sources import dublin_week_range, scan_hugo_blog, blog_observation
    from zoneinfo import ZoneInfo

    # DST transition week (Ireland: last Sunday in March/October). Use a known Sunday.
    dublin = ZoneInfo("Europe/Dublin")
    sunday = datetime(2026, 3, 29, 23, 30, tzinfo=dublin)  # DST switch day
    monday, sunday_end = dublin_week_range(sunday)
    assert monday.weekday() == 0
    assert (sunday_end - monday).days == 6
    assert monday.tzinfo is not None
    root = tmp_path / "post"
    root.mkdir(parents=True, exist_ok=True)
    # Post dated Monday 00:30 Dublin qualifies for that week.
    monday_post = (monday + timedelta(minutes=30)).astimezone(timezone.utc)
    (root / "m.md").write_text(
        '+++\ntitle = "M"\ndate = "%s"\n+++\n\nBody.\n' % monday_post.isoformat(), encoding="utf-8")
    obs = blog_observation(scan_hugo_blog(root, now=sunday), now=sunday)
    assert obs["this_week"] == 1


def test_blog_missing_dir_stale_preserves_last(client: TestClient, tmp_path: Path) -> None:
    import shutil

    root = _blog_site(tmp_path)
    count = _goal(client, name="Blog")
    source = client.post("/api/cultivation/sources", json={
        "name": "blog", "kind": "hugo_blog", "goal_id": count["id"], "path": str(root)}).json()
    _sync(client, source["id"])
    assert client.get(f"/api/cultivation/goals/{count['id']}").json()["progress"]["current"] == 4.0
    shutil.rmtree(root)
    result = _sync(client, source["id"])
    assert result["status"] == "stale"
    assert result["observed"]["published"] == 4
    kept = client.get(f"/api/cultivation/goals/{count['id']}").json()
    assert kept["progress"]["live_stale"] is True


def test_seed_weekly_blog_exists_and_linked(client: TestClient) -> None:
    goals = {g["id"]: g for g in client.get("/api/cultivation/goals").json()}
    assert "weekly_blog" in goals
    assert goals["weekly_blog"]["skill_id"] == "blog-posts"
    sources = client.get("/api/cultivation/sources").json()
    # Path-gated: only present when the real repo exists.
    by_id = {s["id"]: s for s in sources}
    if "src-blog-posts" in by_id:
        assert by_id["src-blog-posts"]["goal_id"] == "blog_posts"
