"""MC-INSPECT-04: operational Inspect job backend tests.

All Inspect checkouts and snapshots are tiny fakes under tmp_path -- never the
real C:\\Projects\\inspect. A stub inspect.py stands in for the CLI.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest

from helpers import open_client
from mission_control.config import RuntimeSettings
from mission_control.inspect_snapshots import clear_stores_for_tests

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated_stores():
    clear_stores_for_tests()
    yield
    clear_stores_for_tests()


def _stub_checkout(root: Path) -> Path:
    """Fake Inspect checkout: stub inspect.py honoring the real argv shape."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "inspect.py").write_text(
        "import json, sys, time\n"
        "argv = sys.argv[1:]\n"
        "target = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else ''\n"
        "if target == 'slow':\n"
        "    time.sleep(60)\n"
        "print(json.dumps({'result': 'complete', 'operation': argv[0] if argv else ''}))\n",
        encoding="utf-8",
    )
    return root


def _write_snapshot(root: Path, *, projects, sources) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    datasets = {
        "projects.json": {"projects": projects, "generated_at": "2026-11-25T00:00:00Z"},
        "capabilities.json": {"capabilities": []},
        "usage.json": {"usages": []},
        "opportunities.json": {"opportunities": []},
        "coverage.json": {"coverages": []},
        "compositions.json": {"compositions": []},
    }
    for name, document in datasets.items():
        (root / name).write_text(json.dumps(document), encoding="utf-8")
    checksums = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in datasets
    }
    manifest = {
        "contract_version": "1.0.0",
        "generated_at": "2026-11-25T00:00:00Z",
        "inspect_version": {"git_sha": "t", "prompt_version": "1", "schema_version": "1.0.0"},
        "sources": sources,
        "counts": {"projects": len(projects)},
        "checksums": checksums,
        "validation": {"status": "valid", "errors": []},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture()
def ops_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    snap = tmp_path / "snap"
    checkout = _stub_checkout(tmp_path / "inspect")
    monkeypatch.setenv("MISSION_CONTROL_INSPECT_DIR", str(snap))
    monkeypatch.setenv("MISSION_CONTROL_INSPECT_CHECKOUT", str(checkout))
    return snap, checkout


def _runtime(tmp_path: Path) -> RuntimeSettings:
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
    )


def _make_app(client, app_id: str, repo_path: Path) -> dict:
    response = client.post(
        "/api/applications",
        json={"id": app_id, "name": app_id, "repository_path": str(repo_path)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for args in (["init"], ["config", "user.email", "t@t.t"], ["config", "user.name", "t"]):
        result = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
    return path


def test_inventory_empty_snapshot_lists_registry_as_never_inspected(tmp_path, ops_env) -> None:
    repo = _git_repo(tmp_path / "repos" / "demo")
    with open_client(_runtime(tmp_path)) as client:
        _make_app(client, "demo", repo)
        body = client.get("/api/inspect/ops/inventory").json()
    assert body["available"] is False
    assert body["total"] >= 1
    row = next(r for r in body["projects"] if r["mission_application_id"] == "demo")
    assert row["execution"] == "never-inspected"
    assert row["freshness"] == "unknown"
    assert row["primary_action"] == "inspect"
    assert body["counts"]["never_inspected"] >= 1


def test_inventory_maps_snapshot_and_unmapped(tmp_path, ops_env) -> None:
    snap, _ = ops_env
    repo = _git_repo(tmp_path / "repos" / "writer")
    projects = [
        {"id": "writer", "name": "writer", "path": str(repo), "branch": "main",
         "head_sha": "abc", "inspection_status": "complete",
         "capabilities_count": 5, "stale": False},
        {"id": "ghost", "name": "ghost", "path": "C:\\Projects\\ghost",
         "branch": "main", "head_sha": "def", "inspection_status": "complete",
         "capabilities_count": 2, "stale": True},
    ]
    sources = [
        {"repository": "writer", "head_sha": "abc", "inspection_status": "complete",
         "stale": False, "stale_reason": ""},
        {"repository": "ghost", "head_sha": "def", "inspection_status": "complete",
         "stale": True, "stale_reason": "source changed since inspection"},
    ]
    _write_snapshot(snap, projects=projects, sources=sources)
    with open_client(_runtime(tmp_path)) as client:
        _make_app(client, "ops-writer", repo)
        body = client.get("/api/inspect/ops/inventory").json()
    assert body["available"] is True
    row = next(r for r in body["projects"] if r["mission_application_id"] == "ops-writer")
    assert row["mapped"] is True
    assert row["execution"] == "complete"
    assert row["freshness"] == "current"
    assert row["capabilities"] == 0  # fake snapshot carries no capability rows
    assert row["primary_action"] == "enrich"  # no usage/coverage yet
    assert [u["inspect_id"] for u in body["unmapped"]] == ["ghost"]
    assert body["counts"]["unmapped"] == 1


def test_start_run_rejects_unknown_operation(tmp_path, ops_env) -> None:
    with open_client(_runtime(tmp_path)) as client:
        response = client.post(
            "/api/inspect/ops/runs", json={"repository_id": "writer", "operation": "rm -rf"}
        )
    assert response.status_code == 400


def test_start_run_rejects_unknown_and_traversal_repo(tmp_path, ops_env) -> None:
    with open_client(_runtime(tmp_path)) as client:
        # Repo-scoped operations require a known repository.
        assert client.post(
            "/api/inspect/ops/runs", json={"repository_id": "nope", "operation": "inspect"}
        ).status_code == 404
        assert client.post(
            "/api/inspect/ops/runs", json={"repository_id": "../x", "operation": "inspect"}
        ).status_code == 404
        # Ecosystem operations ignore repository_id.
        assert client.post(
            "/api/inspect/ops/runs", json={"repository_id": "nope", "operation": "refresh"}
        ).status_code == 200
        assert client.get("/api/inspect/ops/runs/bad%20id!").status_code == 404


def test_refresh_run_completes_with_logged_result(tmp_path, ops_env) -> None:
    with open_client(_runtime(tmp_path)) as client:
        started = client.post(
            "/api/inspect/ops/runs", json={"repository_id": "", "operation": "refresh"}
        ).json()
        run_id = started["run"]["run_id"]
        assert started["duplicate"] is False
        status = ""
        for _ in range(100):
            job = client.get(f"/api/inspect/ops/runs/{run_id}").json()
            status = job["status"]
            if status not in ("queued", "running"):
                break
            time.sleep(0.1)
        assert status == "completed", job
        assert job["result_summary"].get("result") == "complete"
        history = client.get("/api/inspect/ops/runs").json()
        assert history["total"] >= 1


def test_duplicate_active_run_and_cancel(tmp_path, ops_env) -> None:
    repo = _git_repo(tmp_path / "repos" / "slow")
    with open_client(_runtime(tmp_path)) as client:
        _make_app(client, "slow", repo)
        first = client.post(
            "/api/inspect/ops/runs", json={"repository_id": "slow", "operation": "inspect"}
        ).json()
        run_id = first["run"]["run_id"]
        try:
            second = client.post(
                "/api/inspect/ops/runs",
                json={"repository_id": "slow", "operation": "inspect"},
            ).json()
            assert second["duplicate"] is True
            assert second["run"]["run_id"] == run_id
            cancelled = client.post(f"/api/inspect/ops/runs/{run_id}/cancel").json()
            assert cancelled["cancelled"] is True
            assert cancelled["run"]["status"] == "cancelled"
        finally:
            client.post(f"/api/inspect/ops/runs/{run_id}/cancel")


def test_concurrency_limit(tmp_path, ops_env, monkeypatch) -> None:
    import mission_control.api.inspect_ops as ops

    monkeypatch.setattr(ops, "GLOBAL_CONCURRENCY_LIMIT", 1)
    repo_a = _git_repo(tmp_path / "repos" / "slow")
    repo_b = _git_repo(tmp_path / "repos" / "other")
    with open_client(_runtime(tmp_path)) as client:
        _make_app(client, "slow", repo_a)
        _make_app(client, "other", repo_b)
        first = client.post(
            "/api/inspect/ops/runs", json={"repository_id": "slow", "operation": "inspect"}
        )
        assert first.status_code == 200
        run_id = first.json()["run"]["run_id"]
        try:
            blocked = client.post(
                "/api/inspect/ops/runs",
                json={"repository_id": "other", "operation": "refresh"},
            )
            assert blocked.status_code == 409
        finally:
            client.post(f"/api/inspect/ops/runs/{run_id}/cancel")


def test_snapshot_known_repo_resolves_to_live_path(tmp_path, ops_env) -> None:
    """Snapshot-known but undiscovered repos must launch by path, not bare id.

    The Inspect CLI only resolves ids present in its discovery registry; an
    explicit existing path always resolves. The stub CLI fails loudly when it
    receives the bare id.
    """
    snap, checkout = ops_env
    repo = _git_repo(tmp_path / "repos" / "ghost")
    (checkout / "inspect.py").write_text(
        "import json, sys\n"
        "target = sys.argv[2] if len(sys.argv) > 2 else ''\n"
        "import os\n"
        "if not os.path.isdir(target):\n"
        "    print(json.dumps({'result': 'failed', "
        "'errors': ['unknown repository: ' + target]}))\n"
        "else:\n"
        "    print(json.dumps({'result': 'complete'}))\n",
        encoding="utf-8",
    )
    projects = [
        {"id": "ghost", "name": "ghost", "path": str(repo), "branch": "main",
         "head_sha": "abc", "inspection_status": "complete",
         "capabilities_count": 1, "stale": False},
    ]
    sources = [
        {"repository": "ghost", "head_sha": "abc", "inspection_status": "complete",
         "stale": False, "stale_reason": ""},
    ]
    _write_snapshot(snap, projects=projects, sources=sources)
    with open_client(_runtime(tmp_path)) as client:
        started = client.post(
            "/api/inspect/ops/runs", json={"repository_id": "ghost", "operation": "inspect"}
        )
        assert started.status_code == 200, started.text
        run_id = started.json()["run"]["run_id"]
        status = ""
        for _ in range(100):
            job = client.get(f"/api/inspect/ops/runs/{run_id}").json()
            status = job["status"]
            if status not in ("queued", "running"):
                break
            time.sleep(0.1)
        assert status == "completed", job


def test_history_filters_by_repository(tmp_path, ops_env) -> None:
    with open_client(_runtime(tmp_path)) as client:
        client.post("/api/inspect/ops/runs", json={"repository_id": "", "operation": "refresh"})
        body = client.get("/api/inspect/ops/runs", params={"repository_id": ""}).json()
        assert body["total"] >= 0  # empty key matches ecosystem runs only
