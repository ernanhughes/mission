"""MC-COST-02: AI consumption & model efficiency tests.

Hermetic synthetic SQLite fixtures under tmp_path. The real OpenCode
database is never touched. No model is ever called.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from helpers import open_client
from mission_control.config import RuntimeSettings

REPO_ROOT = Path(__file__).resolve().parents[2]

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


def _msg(session_id: str, seq: int, tc_ms: int, *, model, provider, cost=0.0,
         inp=100, out=10, reasoning=0, cr=0, cw=0) -> tuple:
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
    return (f"m2-{session_id}-{seq}", session_id, "assistant", seq, tc_ms, tc_ms, json.dumps(payload))


def _write_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path.as_posix())
    cur = conn.cursor()
    cur.execute("CREATE TABLE project (id TEXT PRIMARY KEY, worktree TEXT NOT NULL, vcs TEXT, name TEXT, icon_url TEXT, icon_url_override TEXT, icon_color TEXT, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, time_initialized INTEGER, time_active INTEGER DEFAULT 0 NOT NULL, sandboxes TEXT NOT NULL, commands TEXT, time_archived INTEGER)")
    cur.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT, parent_id TEXT, fork_session_id TEXT, fork_boundary TEXT, slug TEXT NOT NULL, directory TEXT NOT NULL, path TEXT, title TEXT, version TEXT NOT NULL, share_url TEXT, summary_additions INTEGER, summary_deletions INTEGER, summary_files INTEGER, summary_diffs TEXT, metadata TEXT, cost REAL DEFAULT 0 NOT NULL, tokens_input INTEGER DEFAULT 0 NOT NULL, tokens_output INTEGER DEFAULT 0 NOT NULL, tokens_reasoning INTEGER DEFAULT 0 NOT NULL, tokens_cache_read INTEGER DEFAULT 0 NOT NULL, tokens_cache_write INTEGER DEFAULT 0 NOT NULL, revert TEXT, permission TEXT, agent TEXT, model TEXT, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, time_idle INTEGER, time_viewed INTEGER, idle_outcome TEXT, time_compacting INTEGER, time_archived INTEGER, time_suspended INTEGER, resume_attempts INTEGER DEFAULT 0 NOT NULL, time_busy INTEGER)")
    cur.execute("CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, type TEXT NOT NULL, seq INTEGER NOT NULL, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, data TEXT NOT NULL)")
    cur.execute("INSERT INTO project (id, worktree, name, time_created, time_updated, sandboxes) VALUES (?,?,?,?,?,?)",
                ("proj-a", "C:/Projects/a", "a", T0, T0, "[]"))
    sessions = [
        ("ses_main", "proj-a", None, "Main task", "C:/Projects/a", T0, T0 + 600_000, 0.04),
        ("ses_child", "proj-a", "ses_main", "Child agent", "C:/Projects/a", T0 + 5_000, T0 + 60_000, 0.0),
        ("ses_free", "proj-a", None, "Free batch", "C:/Projects/a", T0 + 10_000, T0 + 120_000, 0.0),
        ("ses_direct", "proj-missing", None, "Direct route", "C:/elsewhere", T0 + 20_000, T0 + 200_000, 0.55),
        ("ses_big", "proj-a", None, "Big context", "C:/Projects/a", T0 + 30_000, T0 + 90_000, 0.0),
    ]
    for sid, pid, parent, title, directory, tc, tu, cost in sessions:
        cur.execute(
            "INSERT INTO session_v2 (id, project_id, parent_id, slug, directory, title, version, cost, tokens_input, tokens_output, model, agent, time_created, time_updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, pid, parent, "slug", directory, title, "v2", cost, 1000, 100, '{"id":"m"}', "build", tc, tu),
        )
    seq_count: dict[str, int] = {}
    def add(session_id: str, **kwargs) -> None:
        seq_count[session_id] = seq_count.get(session_id, 0) + 1
        row = _msg(session_id, seq_count[session_id], T0 + seq_count[session_id] * 1000, **kwargs)
        cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)", row)
    for _ in range(60):
        add("ses_main", model="deepseek-v4.1-flash", provider="opencode-go", inp=1000, out=50, cr=200)
    for _ in range(2):
        add("ses_main", model="muse-spark-1.3-contributor", provider="meta", cost=0.02, inp=5000, out=200, cr=1000)
    for _ in range(5):
        add("ses_child", model="deepseek-v4.1-flash", provider="opencode-go", inp=1000, out=50, cr=200)
    for _ in range(55):
        add("ses_free", model="beam-free", provider="opencode-go", inp=200, out=20, cr=50)
    for _ in range(55):
        add("ses_direct", model="muse-spark-1.3-contributor", provider="meta", cost=0.01, inp=3000, out=150, cr=500)
    add("ses_big", model="deepseek-v4.1-flash", provider="opencode-go", inp=250_000, out=200, cr=1000)
    conn.commit()
    conn.close()
    return path


WINDOW = "preset=custom&date_from=2026-11-22&date_to=2026-11-22"


def test_throughput_math_and_billing_categories(tmp_path: Path) -> None:
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get(f"/api/cost/summary?{WINDOW}").json()
        assert body["available"] is True
        totals = body["totals"]
        assert totals["requests"] == 60 + 2 + 5 + 55 + 55 + 1
        assert totals["throughput"] == totals["input"] + totals["output"] + totals["cache_read"] + totals["cache_write"]
        by_model = {f"{m['provider']}/{m['model']}": m for m in body["by_model"]}
        go = by_model["opencode-go/deepseek-v4.1-flash"]
        assert go["throughput"] == go["input"] + go["output"] + go["cache_read"] + go["cache_write"]
        assert go["billing_category"] == "go-candidate"
        assert "not retained" in go["billing_reason"]
        assert by_model["meta/muse-spark-1.3-contributor"]["billing_category"] == "direct-candidate"
        assert by_model["opencode-go/beam-free"]["billing_category"] == "free-candidate"
        # Zero cost never claims a billing route on its own: free-candidate
        # comes from the model id, and the reason says the source is missing.
        assert "not retained" in by_model["opencode-go/beam-free"]["billing_reason"]


def test_parent_child_no_double_count_and_mixed_billing(tmp_path: Path) -> None:
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get(f"/api/cost/sessions?{WINDOW}&limit=200").json()
        items = {item["session_id"]: item for item in body["items"]}
        assert body["total"] == 5
        # Parent counts only its own 62 messages, never the child's 5.
        assert items["ses_main"]["requests"] == 62
        assert items["ses_child"]["requests"] == 5
        assert items["ses_main"]["billing_mixed"] is True
        assert items["ses_main"]["billing_category"] == "go-candidate"
        assert sorted(items["ses_main"]["models"]) == [
            "meta/muse-spark-1.3-contributor",
            "opencode-go/deepseek-v4.1-flash",
        ]
        assert items["ses_free"]["billing_category"] == "free-candidate"
        assert items["ses_free"]["billing_mixed"] is False
        # Throughput present per session.
        assert items["ses_big"]["throughput"] == items["ses_big"]["input"] + items["ses_big"]["output"] + items["ses_big"]["cache_read"] + items["ses_big"]["cache_write"]
        assert items["ses_big"]["max_input"] == 250_000
        # Detail still links the tree both ways.
        detail = client.get("/api/cost/sessions/ses_main").json()
        assert detail["children"] == ["ses_child"]
        child = client.get("/api/cost/sessions/ses_child").json()
        assert child["parent_id"] == "ses_main"


def test_session_sort_keys(tmp_path: Path) -> None:
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        by_cost = client.get(f"/api/cost/sessions?{WINDOW}&limit=200&sort=cost").json()["items"]
        assert by_cost[0]["session_id"] == "ses_direct"
        by_thr = client.get(f"/api/cost/sessions?{WINDOW}&limit=200&sort=throughput").json()["items"]
        assert by_thr[0]["session_id"] == "ses_big"
        by_req = client.get(f"/api/cost/sessions?{WINDOW}&limit=200&sort=requests").json()["items"]
        assert by_req[0]["session_id"] == "ses_main"
        bad = client.get(f"/api/cost/sessions?{WINDOW}&sort=price")
        assert bad.status_code == 422


def test_efficiency_is_advisory_only(tmp_path: Path) -> None:
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get(f"/api/cost/efficiency?{WINDOW}").json()
        assert body["available"] is True
        recs = {r["id"]: r for r in body["recommendations"]}
        assert any("verify-free-opencode-go-deepseek" in rid for rid in recs), recs.keys()
        assert any("verify-route-meta-muse-spark" in rid for rid in recs), recs.keys()
        assert any("confirm-free-opencode-go-beam-free" in rid for rid in recs), recs.keys()
        for rec in body["recommendations"]:
            assert rec["action"] == "none (advisory only)"
            assert rec["session_ids"], "every recommendation links evidence"
            lowered = (rec["title"] + rec["detail"]).lower()
            assert "verif" in lowered or "confirm" in lowered or "re-measure" in lowered
        assert "advisory only" in body["provenance"].lower()


def test_efficiency_empty_window_has_no_recommendations(tmp_path: Path) -> None:
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get("/api/cost/efficiency?preset=custom&date_from=2020-01-01&date_to=2020-01-01").json()
        assert body["available"] is True
        assert body["recommendations"] == []


def test_catalogue_degrades_to_unknown(tmp_path: Path, monkeypatch) -> None:
    import mission_control.api.cost as cost_api
    import mission_control.research.pi_backend as pi_backend

    async def _no_go() -> dict:
        return {"available": False, "models": [], "detail": "offline in test"}

    monkeypatch.setattr(cost_api, "_fetch_go_models", _no_go)
    monkeypatch.setattr(pi_backend, "discover_pi_models",
                        lambda timeout=5.0: {"available": False, "models": [], "detail": "no pi in test", "error": "pi_unavailable"})
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get("/api/cost/catalogue").json()
        assert body["available"] is True
        assert body["pi_available"] is False
        assert body["go_available"] is False
        assert "unknown" in body["provenance"].lower()


def test_attribution_counts_unknown(tmp_path: Path) -> None:
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        body = client.get(f"/api/cost/attribution?{WINDOW}").json()
        assert body["available"] is True
        assert body["unknown_sessions"] == 1
        assert body["unknown_requests"] == 55
        assert any("parent" in item for item in body["retained"])
        assert any("billing_source" in item for item in body["missing"])
        assert any("Pi" in item for item in body["instrumentation"])
        assert "unattributed" in body["provenance"].lower()


def test_cost_routes_registered_with_documented_contracts(tmp_path: Path) -> None:
    """Route-contract test: every documented Cost path exists in OpenAPI.

    Guards against the MC-COST-02A failure mode where the frontend calls
    endpoints the running backend does not serve.
    """
    db = _write_db(tmp_path / "opencode.db")
    with open_client(_runtime(tmp_path, db)) as client:
        spec = client.get("/openapi.json").json()
        paths = spec.get("paths", {})
        for route in (
            "/api/cost/status",
            "/api/cost/summary",
            "/api/cost/sessions",
            "/api/cost/sessions/{session_id}",
            "/api/cost/spikes",
            "/api/cost/efficiency",
            "/api/cost/attribution",
            "/api/cost/catalogue",
        ):
            assert route in paths, f"missing route {route}"
            assert "get" in paths[route], f"route {route} is not GET"
        # New MC-COST-02 endpoints answer with their documented envelopes.
        for path in (
            f"/api/cost/efficiency?{WINDOW}",
            f"/api/cost/attribution?{WINDOW}",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json()["available"] is True
        catalogue = client.get("/api/cost/catalogue")
        assert catalogue.status_code == 200
        assert "available" in catalogue.json()
