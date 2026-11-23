"""MC-COST-01: hermetic read-only OpenCode cost adapter tests.

All fixtures are tiny synthetic SQLite files under tmp_path. The real
OpenCode database is never touched.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from helpers import open_client
from mission_control.config import RuntimeSettings

REPO_ROOT = Path(__file__).resolve().parents[2]

DAY = "2026-11-22"
# 22 Nov 2026 22:10 UTC in ms
T0 = int(datetime(2026, 11, 22, 22, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)


def _runtime(tmp_path: Path, db_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        repo_root=REPO_ROOT,
        data_dir=tmp_path / "data",
        config_dir=REPO_ROOT / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction-books",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
        workbench_decisions_path=tmp_path / "workbench-decisions.jsonl",
        workbench_preferences_path=tmp_path / "workbench-preferences.json",
        workbench_url="http://workbench.test",
        opencode_db_path=db_path,
    )


def _assistant_msg(session_id: str, seq: int, tc_ms: int, *, model="deepseek-v4.1-flash",
                   provider="opencode-go", cost=0.0, inp=100, out=10,
                   reasoning=0, cr=0, cw=0) -> tuple:
    payload = {
        "time": {"created": tc_ms, "completed": tc_ms + 1000},
        "agent": "build",
        "model": {"id": model, "providerID": provider, "variant": "max"},
        "content": [{"type": "text", "text": "hello"}],
        "finish": "stop",
        "cost": cost,
        "tokens": {"input": inp, "output": out, "reasoning": reasoning,
                   "cache": {"read": cr, "write": cw}},
    }
    return (f"msg-{session_id}-{seq}", session_id, "assistant", seq, tc_ms, tc_ms, json.dumps(payload))


def _write_opencode_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path.as_posix())
    cur = conn.cursor()
    cur.execute("CREATE TABLE project (id TEXT PRIMARY KEY, worktree TEXT NOT NULL, vcs TEXT, name TEXT, icon_url TEXT, icon_url_override TEXT, icon_color TEXT, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, time_initialized INTEGER, time_active INTEGER DEFAULT 0 NOT NULL, sandboxes TEXT NOT NULL, commands TEXT, time_archived INTEGER)")
    cur.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT, parent_id TEXT, fork_session_id TEXT, fork_boundary TEXT, slug TEXT NOT NULL, directory TEXT NOT NULL, path TEXT, title TEXT, version TEXT NOT NULL, share_url TEXT, summary_additions INTEGER, summary_deletions INTEGER, summary_files INTEGER, summary_diffs TEXT, metadata TEXT, cost REAL DEFAULT 0 NOT NULL, tokens_input INTEGER DEFAULT 0 NOT NULL, tokens_output INTEGER DEFAULT 0 NOT NULL, tokens_reasoning INTEGER DEFAULT 0 NOT NULL, tokens_cache_read INTEGER DEFAULT 0 NOT NULL, tokens_cache_write INTEGER DEFAULT 0 NOT NULL, revert TEXT, permission TEXT, agent TEXT, model TEXT, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, time_idle INTEGER, time_viewed INTEGER, idle_outcome TEXT, time_compacting INTEGER, time_archived INTEGER, time_suspended INTEGER, resume_attempts INTEGER DEFAULT 0 NOT NULL, time_busy INTEGER)")
    cur.execute("CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, type TEXT NOT NULL, seq INTEGER NOT NULL, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, data TEXT NOT NULL)")
    cur.execute("CREATE UNIQUE INDEX session_message_session_seq_idx ON session_message (session_id, seq)")
    # Projects: mission + unknown-missing (no row for orphan project)
    cur.execute("INSERT INTO project (id, worktree, name, time_created, time_updated, sandboxes) VALUES (?,?,?, ?, ?, ?)",
                ("proj-mission", "C:/Projects/mission", "mission", T0, T0, "[]"))
    # Sessions: parent + child + orphan (unknown project)
    sessions = [
        ("ses_parent", "proj-mission", None, "Parent research", "C:/Projects/mission", T0, T0 + 600_000, 0.05),
        ("ses_child", "proj-mission", "ses_parent", "Child agent", "C:/Projects/mission", T0 + 10_000, T0 + 300_000, 0.0),
        ("ses_orphan", "proj-missing", None, "Orphan", "C:/elsewhere", T0 + 20_000, T0 + 40_000, 0.01),
    ]
    for sid, pid, parent, title, directory, tc, tu, cost in sessions:
        cur.execute(
            "INSERT INTO session_v2 (id, project_id, parent_id, slug, directory, title, version, cost, tokens_input, tokens_output, time_created, time_updated, model, agent) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, pid, parent, "slug", directory, title, "v2", cost, 1000, 100, tc, tu, '{"id":"m"}', "build"),
        )
    msgs = [
        _assistant_msg("ses_parent", 8, T0 + 1_000, model="deepseek-v4.1-flash", provider="opencode-go",
                       cost=0.0, inp=7000, out=160, cr=1920),
        _assistant_msg("ses_parent", 9, T0 + 2_000, model="muse-spark-1.3-contributor", provider="meta",
                       cost=0.039, inp=346050, out=16278, cr=0),
        _assistant_msg("ses_child", 5, T0 + 10_000, model="deepseek-v4.1-flash", provider="opencode-go",
                       cost=0.0, inp=10133, out=132, cr=5000),
        _assistant_msg("ses_orphan", 3, T0 + 20_000, model="deepseek-v4.1-flash", provider="opencode-go",
                       cost=0.0, inp=500, out=50, cr=100),
        # duplicate seq ignored? use distinct seq; retry simulated as second message same minute
        _assistant_msg("ses_parent", 10, T0 + 61_000, model="muse-spark-1.3-contributor", provider="meta",
                       cost=0.001, inp=253, out=913, cr=370033),
    ]
    for mid, sid, typ, seq, tc, tu, data in msgs:
        cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
                    (mid, sid, typ, seq, tc, tu, data))
    # idle go-limit + user message (non-assistant, must not count as request)
    cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
                ("idle-1", "ses_parent", "idle", 100, T0 + 500_000,
                 T0 + 500_000, json.dumps({"time": {"created": T0}, "outcome": "failed",
                                                   "error": {"type": "provider.go-limit", "message": "limit"}})))
    cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
                ("user-1", "ses_parent", "user", 1, T0,
                 T0, json.dumps({"metadata": {}, "time": {"created": T0}, "text": "hi"})))
    conn.commit()
    conn.close()
    return path


def test_status_available(tmp_path: Path) -> None:
    db = _write_opencode_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get("/api/cost/status").json()
        assert body["available"] is True
        assert body["sessions"] == 3
        assert "source_path" in body


def test_missing_db_is_explicit(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    with open_client(_runtime(tmp_path, missing)) as client:
        for path in ("/api/cost/status", "/api/cost/summary?preset=custom&date_from=2026-11-22&date_to=2026-11-22",
                     "/api/cost/sessions?preset=custom&date_from=2026-11-22&date_to=2026-11-22",
                     "/api/cost/spikes?preset=custom&date_from=2026-11-22&date_to=2026-11-22"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert resp.json()["available"] is False
            assert resp.json()["reason"]


def test_summary_aggregates_without_double_counting(tmp_path: Path) -> None:
    db = _write_opencode_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get("/api/cost/summary?preset=custom&date_from=2026-11-22&date_to=2026-11-22").json()
        assert body["available"] is True
        # 5 assistant messages in window; user/idle excluded; no session rollup added
        assert body["totals"]["requests"] == 5
        assert abs(body["totals"]["recorded_cost"] - 0.04) < 1e-9
        assert body["totals"]["input"] == 7000 + 346050 + 10133 + 500 + 253
        assert body["totals"]["cache_read"] == 1920 + 0 + 5000 + 100 + 370033
        providers = {(m["provider"], m["model"]) for m in body["by_model"]}
        assert ("opencode-go", "deepseek-v4.1-flash") in providers
        assert ("meta", "muse-spark-1.3-contributor") in providers


def test_dublin_day_boundary(tmp_path: Path) -> None:
    db = _write_opencode_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        # Custom single Dublin day containing T0
        body = client.get("/api/cost/summary?preset=custom&date_from=2026-11-22&date_to=2026-11-22&timezone=Europe/Dublin").json()
        assert body["available"] is True
        assert body["totals"]["requests"] == 5
        # A Dublin day with no data returns zeros but stays available
        empty = client.get("/api/cost/summary?preset=custom&date_from=2026-01-01&date_to=2026-01-01&timezone=Europe/Dublin").json()
        assert empty["available"] is True
        assert empty["totals"]["requests"] == 0
        assert empty["totals"]["recorded_cost"] == 0.0


def test_sessions_pagination_and_parent_child(tmp_path: Path) -> None:
    db = _write_opencode_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        first = client.get("/api/cost/sessions?preset=custom&date_from=2026-11-22&date_to=2026-11-22&limit=2&offset=0").json()
        assert first["available"] is True
        assert first["total"] == 3
        assert len(first["items"]) == 2
        second = client.get("/api/cost/sessions?preset=custom&date_from=2026-11-22&date_to=2026-11-22&limit=2&offset=2").json()
        assert len(second["items"]) == 1
        # Unknown project bucket: orphan session has empty worktree fallback to directory
        worktrees = [item["project_worktree"] for item in first["items"] + second["items"]]
        assert "C:/elsewhere" in worktrees


def test_session_detail_shows_failures_and_models(tmp_path: Path) -> None:
    db = _write_opencode_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get("/api/cost/sessions/ses_parent").json()
        assert body["available"] is True
        assert body["session_id"] == "ses_parent"
        assert body["children"] == ["ses_child"]
        # child points to parent
        child = client.get("/api/cost/sessions/ses_child").json()
        assert child["parent_id"] == "ses_parent"
        assert any(f["kind"] == "go-limit" for f in body["failures"])
        assert {m["provider"] for m in body["by_model"]} == {"opencode-go", "meta"}
        assert body["message_counts"].get("assistant") == 3
        missing = client.get("/api/cost/sessions/ses_nope")
        assert missing.status_code == 404


def test_spikes_are_deterministic(tmp_path: Path) -> None:
    db = _write_opencode_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get("/api/cost/spikes?preset=custom&date_from=2026-11-22&date_to=2026-11-22").json()
        assert body["available"] is True
        ids = {f["id"] for f in body["findings"]}
        assert "go-limit" in ids
        assert "zero-cost-volume" in ids
