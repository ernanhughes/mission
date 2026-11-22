"""MC-INSPECT-01 Stage 3: read-only Inspect snapshot backend tests.

All snapshots here are tiny fakes under tmp_path -- never the real Inspect
snapshot. New store state is isolated per test via distinct tmp dirs plus a
clear of the module-level store cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from helpers import open_client
from mission_control.config import RuntimeSettings
from mission_control.inspect_snapshots import clear_stores_for_tests

REPO_ROOT = Path(__file__).resolve().parents[2]

_manifest_counter = 0


@pytest.fixture(autouse=True)
def _isolated_stores():
    clear_stores_for_tests()
    yield
    clear_stores_for_tests()


def _write_snapshot(
    root: Path,
    *,
    contract_version: str = "1.0.0",
    projects: list[dict] | None = None,
    capabilities: list[dict] | None = None,
    usages: list[dict] | None = None,
    opportunities: list[dict] | None = None,
    coverages: list[dict] | None = None,
    compositions: list[dict] | None = None,
    corrupt: str | None = None,
) -> Path:
    """Write a fake consumer snapshot with valid checksums (unless corrupt)."""
    global _manifest_counter
    root.mkdir(parents=True, exist_ok=True)
    if projects is None:
        projects = [
            {
                "id": "writer",
                "name": "writer",
                "path": "C:\\Projects\\writer",
                "branch": "main",
                "head_sha": "abc123",
                "inspection_status": "partial",
                "capabilities_count": 1,
                "stale": False,
            },
            {
                "id": "mission",
                "name": "mission",
                "path": "C:\\Projects\\mission",
                "branch": "main",
                "head_sha": "def456",
                "inspection_status": "complete",
                "capabilities_count": 1,
                "stale": False,
            },
        ]
    if capabilities is None:
        capabilities = [
            {
                "id": "writer-plan",
                "name": "Plan chapter",
                "description": "Plans a chapter outline deterministically",
                "repository": "writer",
                "subsystem": "planning",
                "maturity": "implemented",
                "operational_status": "tested-not-demonstrated",
                "accessibility": ["agent-invocable"],
                "risk": "writes-local-files",
            },
            {
                "id": "mission-health",
                "name": "Health check",
                "description": "Reports service health over HTTP",
                "repository": "mission",
                "subsystem": "operations",
                "maturity": "implemented",
                "operational_status": "demonstrated",
                "accessibility": ["public-cli"],
                "risk": "read-only",
            },
        ]
    datasets = {
        "projects.json": {"projects": projects, "generated_at": "2026-11-22T00:00:00Z"},
        "capabilities.json": {"capabilities": capabilities},
        "usage.json": {"usages": usages or []},
        "opportunities.json": {"opportunities": opportunities or []},
        "coverage.json": {"coverages": coverages or []},
        "compositions.json": {"compositions": compositions or []},
    }
    for name, document in datasets.items():
        (root / name).write_text(json.dumps(document), encoding="utf-8")
    if corrupt is not None:
        with (root / corrupt).open("ab") as handle:
            handle.write(b" ")
    checksums = {}
    for name in datasets:
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if name == corrupt:
            digest = "0" * 64  # force a mismatch, like a tampered dataset
        checksums[name] = digest
    manifest = {
        "contract_version": contract_version,
        "generated_at": "2026-11-22T00:00:00Z",
        "inspect_version": {
            "git_sha": "testsha",
            "prompt_version": "1.0",
            "schema_version": "1.0.0",
        },
        "sources": [],
        "counts": {
            "projects": len(projects),
            "capabilities": len(capabilities),
            "usages": len(usages or []),
        },
        "checksums": checksums,
        "validation": {"status": "valid", "errors": []},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # Distinct mtimes per write so refresh-on-mtime is deterministic on disk
    # filesystems with coarse timestamp granularity.
    _manifest_counter += 1
    stamp = time.time() + _manifest_counter
    for name in (*datasets, "manifest.json"):
        os.utime(root / name, (stamp, stamp))
    return root


def _runtime(tmp_path: Path, snapshot_dir: Path) -> RuntimeSettings:
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
        inspect_dir=snapshot_dir,
    )


def test_inspect_default_dir_and_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MISSION_CONTROL_INSPECT_DIR", raising=False)
    assert RuntimeSettings().inspect_dir == Path(
        r"C:\Projects\inspect\output\consumers\mission"
    ).resolve()
    monkeypatch.setenv("MISSION_CONTROL_INSPECT_DIR", str(tmp_path))
    assert RuntimeSettings().inspect_dir == tmp_path.resolve()


def test_valid_snapshot_import(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path / "snapshot")
    with open_client(_runtime(tmp_path, snapshot)) as client:
        manifest = client.get("/api/inspect/manifest")
        assert manifest.status_code == 200, manifest.text
        body = manifest.json()
        assert body["available"] is True
        assert body["stale_refresh"] is False
        assert body["contract_version"] == "1.0.0"
        assert body["counts"]["capabilities"] == 2

        projects = client.get("/api/inspect/projects")
        assert projects.status_code == 200
        assert projects.json()["total"] == 2

        capabilities = client.get("/api/inspect/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["total"] == 2


def test_missing_dir_gives_empty_state_without_startup_failure(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with open_client(_runtime(tmp_path, missing)) as client:
        for path in (
            "/api/inspect/manifest",
            "/api/inspect/projects",
            "/api/inspect/capabilities",
            "/api/inspect/opportunities",
            "/api/inspect/compositions",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json()["available"] is False


def test_invalid_contract_version_keeps_last_valid(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path / "snapshot")
    with open_client(_runtime(tmp_path, snapshot)) as client:
        assert client.get("/api/inspect/manifest").json()["available"] is True
        _write_snapshot(snapshot, contract_version="2.0.0")
        body = client.get("/api/inspect/manifest").json()
        assert body["available"] is True
        assert body["stale_refresh"] is True
        assert body["contract_version"] == "1.0.0"
        assert body["counts"]["capabilities"] == 2
        assert client.get("/api/inspect/projects").json()["total"] == 2


def test_checksum_mismatch_keeps_last_valid(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path / "snapshot")
    with open_client(_runtime(tmp_path, snapshot)) as client:
        assert client.get("/api/inspect/capabilities").json()["total"] == 2
        _write_snapshot(snapshot, corrupt="capabilities.json")
        body = client.get("/api/inspect/capabilities").json()
        assert body["available"] is True
        assert body["stale_refresh"] is True
        assert body["total"] == 2


def test_id_mapping_identity_repository_path_and_passthrough(tmp_path: Path) -> None:
    portal_path = tmp_path / "portal"
    portal_path.mkdir()
    snapshot = _write_snapshot(
        tmp_path / "snapshot",
        projects=[
            {"id": "writer", "name": "writer", "path": "C:\\Projects\\writer"},
            {"id": "portal", "name": "portal", "path": str(portal_path)},
            {"id": "stranger", "name": "stranger", "path": "C:\\Projects\\stranger"},
        ],
    )
    with open_client(_runtime(tmp_path, snapshot)) as client:
        created = client.post(
            "/api/applications",
            json={"id": "portal-app", "name": "Portal", "repository_path": str(portal_path)},
        )
        assert created.status_code == 201, created.text
        body = client.get("/api/inspect/projects").json()
        by_id = {item["id"]: item for item in body["projects"]}
        assert by_id["writer"]["mission_application_id"] == "writer"
        assert by_id["writer"]["mapped"] is True
        assert by_id["portal"]["mission_application_id"] == "portal-app"
        assert by_id["portal"]["mapped"] is True
        assert by_id["stranger"]["mission_application_id"] == "stranger"
        assert by_id["stranger"]["mapped"] is False


def test_search_and_filter_params(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path / "snapshot")
    with open_client(_runtime(tmp_path, snapshot)) as client:
        assert client.get("/api/inspect/capabilities", params={"project": "writer"}).json()[
            "total"
        ] == 1
        assert client.get(
            "/api/inspect/capabilities", params={"subsystem": "operations"}
        ).json()["total"] == 1
        assert client.get(
            "/api/inspect/capabilities", params={"access": "public-cli"}
        ).json()["total"] == 1
        assert client.get(
            "/api/inspect/capabilities",
            params={"verification": "tested-not-demonstrated"},
        ).json()["total"] == 1
        assert client.get(
            "/api/inspect/capabilities", params={"risk": "read-only"}
        ).json()["total"] == 1
        assert client.get("/api/inspect/capabilities", params={"q": "outline"}).json()[
            "total"
        ] == 1
        assert client.get("/api/inspect/capabilities", params={"q": "no-such-thing"}).json()[
            "total"
        ] == 0

        single = client.get("/api/inspect/capabilities/writer-plan")
        assert single.status_code == 200
        assert single.json()["capability"]["id"] == "writer-plan"
        assert client.get("/api/inspect/capabilities/nope").status_code == 404


def test_opportunities_coverage_compositions_and_usage(tmp_path: Path) -> None:
    snapshot = _write_snapshot(
        tmp_path / "snapshot",
        usages=[
            {
                "capability_id": "writer-plan",
                "outcome": "outline",
                "description": "usage",
                "invocations": [],
                "documentation_status": "documented",
                "invocation_status": "plausible-unverified",
                "verification_status": "unverified",
            }
        ],
        opportunities=[
            {
                "opportunity_id": "opp-docs-drift",
                "title": "Drift",
                "description": "docs drift",
                "category": "docs-drift",
                "project_ids": ["writer"],
                "capability_ids": ["writer-plan"],
                "desired_outcome": "x",
                "current_state": "y",
                "gap": "z",
                "suggested_action": "fix",
                "confidence": "high",
                "status": "proposed",
                "repository": "writer",
            }
        ],
        coverages=[{"repository_id": "writer", "inspection_status": "partial"}],
        compositions=[
            {
                "composition_id": "comp-outline",
                "desired_outcome": "book",
                "steps": [],
                "required_capabilities": ["writer-plan"],
                "status": "hypothesized",
                "repository": "writer",
            }
        ],
    )
    with open_client(_runtime(tmp_path, snapshot)) as client:
        usage = client.get("/api/inspect/usage/writer-plan").json()
        assert usage["available"] is True
        assert usage["total"] == 1
        assert client.get("/api/inspect/usage/nothing").json()["total"] == 0

        assert client.get("/api/inspect/opportunities").json()["total"] == 1
        filtered = client.get(
            "/api/inspect/opportunities",
            params={"project": "writer", "category": "docs-drift", "status": "proposed"},
        ).json()
        assert filtered["total"] == 1
        assert client.get(
            "/api/inspect/opportunities", params={"status": "resolved"}
        ).json()["total"] == 0

        coverage = client.get("/api/inspect/coverage/writer")
        assert coverage.status_code == 200
        assert coverage.json()["record"]["inspection_status"] == "partial"
        assert client.get("/api/inspect/coverage/nope").status_code == 404

        assert client.get("/api/inspect/compositions").json()["total"] == 1
        assert client.get(
            "/api/inspect/compositions", params={"project": "writer"}
        ).json()["total"] == 1
        assert client.get(
            "/api/inspect/compositions", params={"project": "mission"}
        ).json()["total"] == 0

        single = client.get("/api/inspect/projects/writer")
        assert single.status_code == 200
        assert single.json()["mapped"] is True
        assert client.get("/api/inspect/projects/nope").status_code == 404


def test_no_path_traversal(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path / "snapshot")
    with open_client(_runtime(tmp_path, snapshot)) as inspect_client:
        assert inspect_client.get("/api/inspect/projects").json()["total"] == 2
        # Encoded traversal sequences are rejected as 404 without touching
        # the filesystem: ids are in-memory lookup keys, never file paths.
        assert inspect_client.get("/api/inspect/projects/%2E%2E").status_code == 404
        assert inspect_client.get("/api/inspect/capabilities/%2E%2E").status_code == 404
        assert inspect_client.get("/api/inspect/usage/%2E%2E").status_code == 404
        assert inspect_client.get("/api/inspect/coverage/%2E%2E").status_code == 404
        body = inspect_client.get("/api/inspect/projects/%2E%2E").json()
        assert body["error"]["code"] == "not_found"
        outside = tmp_path / "outside.json"
        assert not outside.exists()
        # The snapshot still serves normally afterwards.
        assert inspect_client.get("/api/inspect/projects").json()["total"] == 2
