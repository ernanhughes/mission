"""AITEST-02 R12/R17: central testing API on an isolated database.

Uses the repo's own ``client`` fixture (tmp SQLite, operational MC_DSN
stripped by conftest). Never touches the live database.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_tests_summary_empty(client: TestClient) -> None:
    r = client.get("/api/tests/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["projects"] == 0
    assert body["total_tests"] == 0


def test_ingest_event_idempotent_and_visible(client: TestClient) -> None:
    evt = {
        "schema_version": "aitest.event.v1",
        "event_id": "evt_test_001",
        "event_type": "project.registered",
        "project_id": "proj_demo",
        "source_snapshot_id": "",
        "occurred_at": 0,
        "producer_version": "0.1.0",
        "policy_version": "standard/1",
        "payload": {"name": "demo", "root": "C:/x", "integration_state": "observation"},
    }
    r = client.post("/api/tests/events", json=evt)
    assert r.status_code == 200, r.text
    assert r.json()["duplicate"] is False
    r2 = client.post("/api/tests/events", json=evt)
    assert r2.json()["duplicate"] is True

    projects = client.get("/api/tests/projects").json()
    assert any(p["project_id"] == "proj_demo" for p in projects)

    sync = {
        "project": {"project_id": "proj_demo", "name": "demo"},
        "tests": [{
            "logical_id": "t_abc", "relpath": "test_x.py", "func_name": "test_ok",
            "duration_ms": 12.0, "band": "INSTANT",
            "lifecycle": "ACTIVE", "last_outcome": "passed",
        }],
        "receipt": {
            "execution_id": "exe_1", "snapshot_id": "s", "status": "FULL_PASS",
            "discovered": 1, "executed": 1, "passed": 1, "failed": 0,
            "skipped": 0, "quarantined": 0, "deferred": 0,
            "timed_out": 0, "unobserved": 0, "duration_ms": 12.0,
        },
        "issues": [{
            "test_logical_id": "t_xyz", "kind": "HUNG_UNRESOLVED",
            "title": "test_hang exceeds deadline", "detail": {},
        }],
    }
    r3 = client.post("/api/tests/sync", json=sync)
    assert r3.status_code == 200, r3.text

    summary = client.get("/api/tests/summary").json()
    assert summary["projects"] == 1
    assert summary["total_tests"] == 1
    assert summary["healthy"] == 1
    assert summary["repair_needed"] == 1

    inv = client.get("/api/tests/projects/proj_demo/inventory").json()
    assert len(inv) == 1 and inv[0]["band"] == "INSTANT"

    receipts = client.get("/api/tests/projects/proj_demo/receipts").json()
    assert receipts and receipts[0]["status"] == "FULL_PASS"

    issues = client.get("/api/tests/projects/proj_demo/issues").json()
    assert issues and issues[0]["kind"] == "HUNG_UNRESOLVED"


def test_unsupported_envelope_rejected(client: TestClient) -> None:
    r = client.post("/api/tests/events", json={
        "schema_version": "nope", "event_id": "e2",
        "event_type": "x", "project_id": "p"})
    assert r.status_code == 400
