"""MC-INSPECT-04 B: Inspect opportunity -> Praxis proposal bridge tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _snapshot(client: TestClient, tmp_path, monkeypatch):
    from mission_control import inspect_snapshots as snaps

    root = tmp_path / "inspect-snap"
    root.mkdir()
    manifest = {
        "contract_version": "1.0.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "inspect_version": {},
        "sources": [],
        "checksums": {
            "projects.json": "",
            "capabilities.json": "",
            "usage.json": "",
            "opportunities.json": "",
            "coverage.json": "",
            "compositions.json": "",
        },
    }
    import hashlib
    import json

    datasets = {
        "projects.json": {"projects": [{"id": "mission", "path": "C:\\Projects\\mission"}]},
        "capabilities.json": {"capabilities": []},
        "usage.json": {"usages": []},
        "opportunities.json": {
            "opportunities": [
                {
                    "opportunity_id": "opp-test-001",
                    "repository": "mission",
                    "title": "Test improvement",
                    "description": "desc",
                    "status": "proposed",
                    "desired_outcome": "better",
                    "suggested_action": "do X",
                    "evidence_refs": ["src/a.py"],
                }
            ]
        },
        "coverage.json": {"coverages": []},
        "compositions.json": {"compositions": []},
    }
    for name, doc in datasets.items():
        raw = json.dumps(doc, sort_keys=True).encode()
        (root / name).write_bytes(raw)
        manifest["checksums"][name] = hashlib.sha256(raw).hexdigest()
    (root / "manifest.json").write_bytes(json.dumps(manifest).encode())
    monkeypatch.setattr(client.app.state.settings, "inspect_dir", str(root))
    snaps.clear_stores_for_tests()
    return root


def test_draft_and_import_link_opportunity(client: TestClient, tmp_path, monkeypatch):
    _snapshot(client, tmp_path, monkeypatch)
    draft = client.post(
        "/api/inspect/opportunities/opp-test-001/proposal-draft",
        json={
            "capability_id": "",
            "parameters": {},
            "acceptance_criteria": [
                {"id": "a1", "statement": "human verifies", "source": "human:tester"}
            ],
            "acceptance_provenance": "test",
            "expected_benefits": ["demo"],
            "owner": "",
        },
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert "inspect:opportunity:opp-test-001" in body["draft"]["proposal"]["evidence_refs"]

    imported = client.post(
        "/api/inspect/opportunities/opp-test-001/proposals",
        json={
            "capability_id": "",
            "parameters": {},
            "acceptance_criteria": [
                {"id": "a1", "statement": "human verifies", "source": "human:tester"}
            ],
            "acceptance_provenance": "test",
            "expected_benefits": [],
            "owner": "",
        },
    )
    # Advisory (no executable step) is rejected by validation, but linkage is kept:
    # status rejected, never approved, never executable.
    assert imported.status_code == 200, imported.text
    assert imported.json()["status"] == "rejected"


def test_resolved_opportunity_cannot_seed(client: TestClient, tmp_path, monkeypatch):
    _snapshot(client, tmp_path, monkeypatch)
    # Patch snapshot to resolved
    from mission_control import inspect_snapshots as snaps

    store = snaps.get_store(client.app.state.settings.inspect_dir)
    data, _ = store.view()
    assert data is not None
    data.opportunities[0]["status"] = "resolved"
    resp = client.post(
        "/api/inspect/opportunities/opp-test-001/proposals",
        json={
            "capability_id": "",
            "parameters": {},
            "acceptance_criteria": [
                {"id": "a1", "statement": "x", "source": "human:tester"}
            ],
            "acceptance_provenance": "test",
        },
    )
    assert resp.status_code in (400, 409, 422)
