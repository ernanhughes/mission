"""AITEST-03: quality evidence ingestion and read models."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_quality_sync_and_project_read(client: TestClient) -> None:
    doc = {
        "project": {
            "project_id": "proj_quality_demo",
            "name": "quality-demo",
            "root": "C:/quality-demo",
            "integration_state": "observation",
            "policy": "standard",
        },
        "tests": [],
        "quality": {
            "mode": "structural",
            "snapshot": "snap2:demo",
            "tests_evaluated": 17,
            "findings": {"ASSERTS_ON_MOCK": 2},
            "recommendations": {"KEEP": 14, "STRENGTHEN_VERIFICATION_CANDIDATE": 3},
            "verification_gaps": 4,
            "redundancy_candidates": 1,
            "coverage_percent": 42.5,
            "cost_ms": 120.0,
        },
    }
    r = client.post("/api/tests/sync", json=doc)
    assert r.status_code == 200, r.text

    rows = client.get("/api/tests/quality/projects").json()
    row = next(item for item in rows if item["project_id"] == "proj_quality_demo")
    assert row["tests_evaluated"] == 17
    assert row["findings"]["ASSERTS_ON_MOCK"] == 2
    assert row["recommendations"]["KEEP"] == 14
    assert row["verification_gaps"] == 4
    assert row["coverage_percent"] == 42.5

    read = client.get("/api/tests/projects/proj_quality_demo/quality")
    assert read.status_code == 200, read.text
    assert read.json()["redundancy_candidates"] == 1

    missing = client.get("/api/tests/projects/proj_missing/quality")
    assert missing.status_code == 404
