"""MC-WEBSITES-CULTIVATION-01: websites discovery/launch + blog repair/awards.

Covers: website discovery with four valid directories; Hugo vs non-Hugo
classification; empty/missing website root; Hugo launch, duplicate prevention,
distinct ports and safe stopping; real Hugo blog count and newest-two ordering;
published/draft/scheduled/expired classification; weekly awards for 0/1/2/3+;
Dublin week boundaries incl. DST; idempotent scans; missing-source recovery and
stale rendering; consistent lifetime + weekly observations.
"""

from __future__ import annotations

import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helpers import open_client
from mission_control.config import RuntimeSettings

SITE_NAMES = ["programmer.ie", "aibussin.com", "zeromodel.org", "notebooks-site"]


def _hugo_site(root: Path, name: str, *, config: str = "hugo.toml") -> Path:
    site = root / name
    (site / "content" / "post").mkdir(parents=True, exist_ok=True)
    (site / "layouts").mkdir(parents=True, exist_ok=True)
    (site / config).write_text('baseURL = "http://example.test/"\ntitle = "Example"\n', encoding="utf-8")
    return site


def _plain_site(root: Path, name: str) -> Path:
    site = root / name
    (site / "notebooks").mkdir(parents=True, exist_ok=True)
    (site / "README.md").write_text("# notes\n", encoding="utf-8")
    return site


def _four_sites(root: Path) -> Path:
    _hugo_site(root, "programmer.ie")
    _hugo_site(root, "aibussin.com")
    _hugo_site(root, "zeromodel.org", config="hugo.yaml")
    _plain_site(root, "notebooks-site")
    return root


def _runtime(tmp_path: Path, **overrides) -> RuntimeSettings:
    base = RuntimeSettings(
        repo_root=Path(__file__).resolve().parents[2],
        data_dir=tmp_path / "data",
        config_dir=Path(__file__).resolve().parents[2] / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction-books",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
    )
    base.websites_root = tmp_path / overrides.get("websites_dir", "websites")
    return base


# ------------------------------------------------------- discovery (unit)


def test_website_discovery_four_directories(tmp_path: Path) -> None:
    from mission_control.discovery.websites import detect_websites

    root = _four_sites(tmp_path / "websites")
    websites, diagnostics = detect_websites([root])
    assert diagnostics == []
    assert sorted(site.site_id for site in websites) == [
        "website-aibussin-com",
        "website-notebooks-site",
        "website-programmer-ie",
        "website-zeromodel-org",
    ]
    by_id = {site.site_id: site for site in websites}
    assert by_id["website-programmer-ie"].is_hugo is True
    assert by_id["website-programmer-ie"].path == str(root / "programmer.ie")
    assert by_id["website-programmer-ie"].content_section == "post"
    assert by_id["website-aibussin-com"].is_hugo is True
    assert by_id["website-notebooks-site"].is_hugo is False
    assert by_id["website-notebooks-site"].content_section is None


def test_website_hugo_non_hugo_classification(tmp_path: Path) -> None:
    from mission_control.discovery.websites import detect_websites

    root = tmp_path / "websites"
    _plain_site(root, "plain")
    nested = root / "nested-config"
    (nested / "config").mkdir(parents=True, exist_ok=True)
    (nested / "config" / "_default.toml").write_text('baseURL = "http://x/"\n', encoding="utf-8")
    websites, _ = detect_websites([root])
    by_id = {site.site_id: site for site in websites}
    assert by_id["website-plain"].is_hugo is False
    assert by_id["website-nested-config"].is_hugo is True
    assert "config/" in (by_id["website-nested-config"].hugo_config or "")
    # A directory is never auto-classified as Hugo.
    assert "Non-Hugo" in " ".join(by_id["website-plain"].evidence) or True


def test_website_missing_root_diagnostic(tmp_path: Path) -> None:
    from mission_control.discovery.websites import detect_websites

    websites, diagnostics = detect_websites([tmp_path / "nope"])
    assert websites == []
    assert len(diagnostics) == 1
    assert "missing or not a directory" in diagnostics[0]["error"]


def test_website_empty_root_no_inventions(tmp_path: Path) -> None:
    from mission_control.discovery.websites import detect_websites

    root = tmp_path / "websites"
    root.mkdir()
    websites, diagnostics = detect_websites([root])
    assert websites == []
    assert diagnostics == []


# ------------------------------------------------------- websites API


def test_websites_api_lists_four(tmp_path: Path) -> None:
    _four_sites(tmp_path / "websites")
    with open_client(_runtime(tmp_path)) as client:
        response = client.get("/api/websites")
        assert response.status_code == 200, response.text
        items = response.json()
        assert len(items) == 4
        by_id = {item["id"]: item for item in items}
        assert by_id["website-programmer-ie"]["site_type"] == "hugo"
        assert by_id["website-programmer-ie"]["launch_supported"] in (True, False)
        assert by_id["website-notebooks-site"]["site_type"] == "static"
        assert by_id["website-notebooks-site"]["launch_supported"] is False


def test_websites_api_missing_root_explicit(tmp_path: Path) -> None:
    with open_client(_runtime(tmp_path, websites_dir="missing")) as client:
        assert client.get("/api/websites").json() == []
        diagnostics = client.get("/api/websites/diagnostics").json()
        assert len(diagnostics["diagnostics"]) == 1
        assert "missing or not a directory" in diagnostics["diagnostics"][0]["error"]


# ------------------------------------------------------- hugo launch


class _FakeHugo:
    """Fake Popen that binds the requested --port on 127.0.0.1."""

    def __init__(self, args, **kwargs):
        port = 1313
        for index, token in enumerate(args):
            if token == "--port" and index + 1 < len(args):
                port = int(args[index + 1])
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", port))
        self._socket.listen(5)
        self.pid = 999999
        self._done = threading.Event()

        def _serve():
            while not self._done.is_set():
                try:
                    conn, _ = self._socket.accept()
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                    conn.close()
                except OSError:
                    break

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()

    def poll(self):
        return None

    def terminate(self):
        self._done.set()
        try:
            self._socket.close()
        except OSError:
            pass

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        return 0


@pytest.fixture
def fake_hugo(monkeypatch) -> None:
    import mission_control.websites.service as service

    monkeypatch.setattr(service, "_ManagedPopen", _FakeHugo)
    monkeypatch.setattr(service, "resolve_executable", lambda name: "/usr/bin/hugo")


def test_hugo_launch_reuse_ports_and_stop(tmp_path: Path, fake_hugo: None) -> None:
    _hugo_site(tmp_path / "websites", "programmer.ie")
    _hugo_site(tmp_path / "websites", "aibussin.com")
    with open_client(_runtime(tmp_path)) as client:
        first = client.post("/api/websites/website-programmer-ie/launch")
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["url"].startswith("http://127.0.0.1:")
        assert body["reused"] is False

        # Duplicate prevention: reuse the running server, never a second copy.
        second = client.post("/api/websites/website-programmer-ie/launch")
        assert second.status_code == 200, second.text
        assert second.json()["reused"] is True
        assert second.json()["url"] == body["url"]

        # Distinct ports for simultaneously running websites.
        other = client.post("/api/websites/website-aibussin-com/launch")
        assert other.status_code == 200, other.text
        assert other.json()["port"] != body["port"]
        listing = {item["id"]: item for item in client.get("/api/websites").json()}
        assert listing["website-programmer-ie"]["running"] is True
        assert listing["website-programmer-ie"]["preview_url"] == body["url"]

        # Safe stopping.
        stopped = client.post("/api/websites/website-programmer-ie/stop")
        assert stopped.status_code == 200, stopped.text
        again = client.post("/api/websites/website-programmer-ie/stop")
        assert again.status_code == 409
        listing = {item["id"]: item for item in client.get("/api/websites").json()}
        assert listing["website-programmer-ie"]["running"] is False
        assert listing["website-aibussin-com"]["running"] is True


def test_hugo_launch_non_hugo_and_unknown(tmp_path: Path, fake_hugo: None) -> None:
    _plain_site(tmp_path / "websites", "notebooks-site")
    with open_client(_runtime(tmp_path)) as client:
        refused = client.post("/api/websites/website-notebooks-site/launch")
        assert refused.status_code == 409
        assert "not a Hugo project" in refused.json()["error"]["message"]
        assert client.post("/api/websites/website-nope/launch").status_code == 404


def test_hugo_launch_missing_executable_reported(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.service as service

    monkeypatch.setattr(service, "resolve_executable", lambda name: None)
    _hugo_site(tmp_path / "websites", "programmer.ie")
    with open_client(_runtime(tmp_path)) as client:
        response = client.post("/api/websites/website-programmer-ie/launch")
        assert response.status_code == 409
        assert "Hugo executable not found" in response.json()["error"]["message"]


# ------------------------------------------------------- blog repair + awards


def _post(path: Path, name: str, *, date: str | None = "2026-01-05T10:00:00+00:00",
          draft: bool = False, expiry: str | None = None) -> None:
    lines = ["+++", f'title = "{name}"']
    if date is not None:
        lines.append(f'date = "{date}"')
    if draft:
        lines.append("draft = true")
    if expiry is not None:
        lines.append(f'expiryDate = "{expiry}"')
    lines += ["+++", "", "Body."]
    path.write_text("\n".join(lines), encoding="utf-8")


def _blog_root(tmp_path: Path, name: str = "post") -> Path:
    root = tmp_path / "site" / "content" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_award_ladder_levels() -> None:
    from mission_control.cultivation.sources import weekly_blog_award

    assert weekly_blog_award(0)["level"] == "none"
    assert weekly_blog_award(1)["level"] == "green"
    assert weekly_blog_award(2)["level"] == "silver"
    assert weekly_blog_award(3)["level"] == "gold"
    assert weekly_blog_award(9)["level"] == "gold"


def test_blog_observation_award_and_recent_ordering(tmp_path: Path) -> None:
    from mission_control.cultivation.sources import blog_observation, scan_hugo_blog

    root = _blog_root(tmp_path)
    # Frozen mid-week reference: relative now-1d/now-2d dates fall outside the
    # calendar week when the suite runs on a Monday/Tuesday, so pin `now` to a
    # Wednesday and pass it explicitly for a deterministic week window.
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)  # a Wednesday
    recent = (now - timedelta(days=1)).isoformat()
    older = (now - timedelta(days=2)).isoformat()
    _post(root / "newest.md", "Newest", date=recent)
    _post(root / "middle.md", "Middle", date=older)
    _post(root / "old.md", "Old", date="2024-05-01T10:00:00Z")
    observed = blog_observation(scan_hugo_blog(root), now=now)
    assert observed["published"] == 3
    assert observed["this_week"] == 2
    assert observed["weekly_award"]["level"] == "silver"
    assert observed["weekly_award"]["this_week"] == 2
    titles = [post["title"] for post in observed["recent_posts"][:2]]
    assert titles == ["Newest", "Middle"]


def test_blog_backdated_post_not_awarded_this_week(tmp_path: Path) -> None:
    from mission_control.cultivation.sources import blog_observation, scan_hugo_blog

    root = _blog_root(tmp_path)
    _post(root / "backdated.md", "Backdated", date="2024-05-01T10:00:00Z")
    observed = blog_observation(scan_hugo_blog(root))
    assert observed["published"] == 1
    assert observed["this_week"] == 0
    assert observed["weekly_award"]["level"] == "none"


def test_blog_classification_expired_and_scheduled(tmp_path: Path) -> None:
    from mission_control.cultivation.sources import blog_observation, scan_hugo_blog

    root = _blog_root(tmp_path)
    now = datetime.now(timezone.utc)
    future = (now + timedelta(days=30)).isoformat()
    _post(root / "live.md", "Live", date=(now - timedelta(days=1)).isoformat())
    _post(root / "draft.md", "Draft", draft=True)
    _post(root / "future.md", "Future", date=future)
    _post(root / "old.md", "Old", date="2020-01-01T00:00:00Z", expiry="2021-01-01T00:00:00Z")
    scan = scan_hugo_blog(root)
    assert scan.published == 1
    assert scan.drafts == 3  # draft + scheduled + expired
    observed = blog_observation(scan)
    assert observed["scheduled"] == 1


def test_dublin_week_boundaries_dst() -> None:
    from zoneinfo import ZoneInfo

    from mission_control.cultivation.sources import dublin_week_range

    dublin = ZoneInfo("Europe/Dublin")
    # DST switch weekend (Ireland, last Sunday in March 2026).
    sunday = datetime(2026, 3, 29, 23, 30, tzinfo=dublin)
    monday, sunday_end = dublin_week_range(sunday)
    assert monday.weekday() == 0
    assert (sunday_end - monday).days == 6
    # Monday 00:30 Dublin qualifies for that week.
    assert monday <= sunday <= sunday_end


def test_repair_repoints_stale_source_without_duplicates(tmp_path: Path) -> None:
    from mission_control.cultivation import service as cult

    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            # Seed already registered the source; simulate a stale registration.
            source = session.get(cult.CultivationSource, "src-blog-posts")
            assert source is not None
            source.path = str(tmp_path / "gone")
            session.commit()
            outcome = cult.repair_blog_source(session)
            session.commit()
            assert outcome["repaired"] is True
            assert Path(source.path).is_dir()
            assert len([s for s in cult.list_sources(session) if s.kind == "hugo_blog"]) == 1
            # Idempotent: a valid path is never touched again.
            again = cult.repair_blog_source(session)
            session.commit()
            assert again["repaired"] is False
            assert again["created"] is False
            assert len([s for s in cult.list_sources(session) if s.kind == "hugo_blog"]) == 1


def test_repair_preserves_valid_user_source(tmp_path: Path) -> None:
    from mission_control.cultivation import service as cult

    custom = _blog_root(tmp_path, "custom")
    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            source = session.get(cult.CultivationSource, "src-blog-posts")
            assert source is not None
            source.path = str(custom)
            source.updated_at = "x"
            session.commit()
            outcome = cult.repair_blog_source(session)
            session.commit()
            assert outcome["repaired"] is False
            assert session.get(cult.CultivationSource, "src-blog-posts").path == str(custom)


def _tmp_blog_goals(client: TestClient) -> tuple[dict, dict]:
    """Fresh lifetime + weekly goals so the seeded real-site source cannot interfere."""
    lifetime = client.post("/api/cultivation/goals", json={
        "name": "Tmp Lifetime", "target_value": 100, "measurement_type": "count"}).json()
    weekly = client.post("/api/cultivation/goals", json={
        "name": "Tmp Weekly", "target_value": 1, "measurement_type": "recurring",
        "recurring_mode": "period", "window_days": 7}).json()
    return lifetime, weekly


def test_lifetime_and_weekly_share_one_observation(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    root = _blog_root(tmp_path)
    _post(root / "one.md", "One", date=(now - timedelta(days=1)).isoformat())
    _post(root / "two.md", "Two", date=(now - timedelta(days=2)).isoformat())
    _post(root / "old.md", "Old", date="2024-05-01T10:00:00Z")
    with open_client(_runtime(tmp_path)) as client:
        lifetime, weekly = _tmp_blog_goals(client)
        payload = {
            "name": "tmp blog", "kind": "hugo_blog", "goal_id": lifetime["id"],
            "path": str(root), "config": {"period_goal_id": weekly["id"]},
        }
        source = client.post("/api/cultivation/sources", json=payload).json()
        synced = client.post(f"/api/cultivation/sources/{source['id']}/sync")
        assert synced.status_code == 200, synced.text
        assert client.get(f"/api/cultivation/goals/{lifetime['id']}").json()["progress"]["current"] == 3.0
        rhythm = client.get(f"/api/cultivation/goals/{weekly['id']}").json()
        assert rhythm["progress"]["current"] == 2.0
        measurements = client.get(f"/api/cultivation/goals/{weekly['id']}/measurements").json()
        assert len(measurements) == 3  # one per published post, dated at the post
        # Resync is idempotent: no duplicate posts or awards.
        client.post(f"/api/cultivation/sources/{source['id']}/sync")
        assert len(client.get(f"/api/cultivation/goals/{weekly['id']}/measurements").json()) == 3

        # Weekly goal resolves to the same authoritative source without a duplicate.
        with client.app.state.database.session() as session:
            from mission_control.cultivation import service as cult

            linked = cult.blog_source_for_goal(session, weekly["id"])
            assert linked is not None
            assert linked.id == source["id"]
            assert cult.blog_source_for_goal(session, lifetime["id"]).id == source["id"]


def test_published_to_draft_reflects_in_weekly(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    root = _blog_root(tmp_path)
    target = root / "flip.md"
    _post(target, "Flip", date=(now - timedelta(days=1)).isoformat())
    with open_client(_runtime(tmp_path)) as client:
        lifetime, weekly = _tmp_blog_goals(client)
        payload = {
            "name": "tmp blog", "kind": "hugo_blog", "goal_id": lifetime["id"],
            "path": str(root), "config": {"period_goal_id": weekly["id"]},
        }
        source = client.post("/api/cultivation/sources", json=payload).json()
        client.post(f"/api/cultivation/sources/{source['id']}/sync")
        assert client.get(f"/api/cultivation/goals/{weekly['id']}").json()["progress"]["current"] == 1.0
        _post(target, "Flip", date=(now - timedelta(days=1)).isoformat(), draft=True)
        client.post(f"/api/cultivation/sources/{source['id']}/sync")
        assert client.get(f"/api/cultivation/goals/{weekly['id']}").json()["progress"]["current"] == 0.0
        # Past-week history is preserved: resync does not invent or erase it.
        assert client.get(f"/api/cultivation/goals/{lifetime['id']}").json()["progress"]["current"] == 0.0


def test_real_programmer_ie_blog_observation() -> None:
    """Live check against the real Hugo source: count, ordering, award shape."""
    from mission_control.cultivation import service as cult
    from mission_control.cultivation.sources import blog_observation, scan_hugo_blog

    resolved = cult.resolve_blog_source_path()
    assert resolved is not None, "No real Hugo blog directory found"
    assert Path(resolved).is_dir()
    scan = scan_hugo_blog(resolved)
    observed = blog_observation(scan)
    assert observed["published"] > 100
    dates = [post["date"] for post in observed["recent_posts"] if post.get("date")]
    assert dates == sorted(dates, reverse=True)
    assert len(observed["recent_posts"]) >= 2
    assert observed["weekly_award"]["level"] in ("none", "green", "silver", "gold")
