"""MC-PRAXIS-07: governed Praxis proposal import, approval and correlation."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

SCHEMA = "mc-praxis-proposal-v1"


def _payload(**overrides: Any) -> dict[str, Any]:
    proposal: dict[str, Any] = {
        "id": "prop-test-1",
        "version": "1",
        "status": "validated",
        "goal": {
            "goal_id": "res-da23de6ba1b27ffe2d54",
            "external_id": "e6316289",
            "title": "[exploit] Reliable AI-Assisted Decisions via Selective Auditing",
            "description": "arxiv reports: selective auditing.",
            "desired_outcome": "Assess a bounded review workflow.",
            "state": "NEW",
            "source": "next_opportunity",
            "provenance": {"source_version": "next-postgres-readonly-v1"},
            "explicit_acceptance": [],
            "inferred_constraints": ["Source snapshot is stale"],
            "evidence": ["Source: 2610.31662v1"],
            "themes": ["verification-evaluation"],
            "stale": True,
        },
        "steps": [
            {
                "capability_id": "writer.audit_registered_books",
                "parameters": {"profile": "technical-nonfiction-v1"},
                "rationale": "bounded local audit",
            }
        ],
        "capability_versions": {"writer.audit_registered_books": "mc09.1"},
        "pi_model": "opencode-go/deepseek-v4.1-flash",
        "protocol": "praxis-compose-v2",
        "evidence_refs": ["prior audit: 32 books, 17 need review"],
        "expected_benefits": ["bounded, inspectable evidence"],
        "risks": ["risk=bounded_local_computation"],
        "assumptions": ["MC remains authoritative"],
        "estimated_cost": {"estimated_usd": None},
        "observed_composition_cost_usd": 0.0007,
        "correlation": {"run_id": "praxis06-test"},
    }
    body = {
        "schema_version": SCHEMA,
        "proposal": proposal,
        "acceptance_criteria": [
            {"id": "ac-1",
             "statement": "An execution record with exit_code 0 and a Writer "
                          "editing summary is produced.",
             "source": "human:ernan"}
        ],
        "acceptance_provenance": "Defined by the human operator for the PRAXIS-07 pilot.",
    }
    body.update(overrides)
    return body


def _import(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/praxis/proposals", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _findings(row: dict[str, Any]) -> dict[str, bool]:
    return {item["check"]: item["ok"] for item in row["validation"]}


def test_import_validates_and_awaits_approval(client: TestClient) -> None:
    row = _import(client, _payload())
    assert row["status"] == "awaiting_approval"
    assert row["proposal_key"] == "prop-test-1@1"
    assert row["correlation_id"].startswith("mcprop-")
    assert row["content_digest"].startswith("sha256:")
    assert row["recipe_digest"].startswith("sha256:")
    assert all(_findings(row).values()), row["validation"]
    assert row["approved_by"] is None
    assert row["execution_id"] is None


def test_import_is_idempotent(client: TestClient) -> None:
    first = _import(client, _payload())
    second = _import(client, _payload())
    assert first["proposal_key"] == second["proposal_key"]
    assert first["correlation_id"] == second["correlation_id"]
    assert first["content_digest"] == second["content_digest"]


def test_same_version_different_content_conflicts(client: TestClient) -> None:
    _import(client, _payload())
    changed = _payload()
    changed["proposal"]["steps"][0]["parameters"] = {"profile": "other-profile"}
    response = client.post("/api/praxis/proposals", json=changed)
    assert response.status_code == 409
    assert "different content" in response.text


def test_unknown_and_disabled_capabilities_rejected(client: TestClient) -> None:
    unknown = _payload()
    unknown["proposal"]["steps"][0]["capability_id"] = "writer.not_a_real_action"
    row = _import(client, unknown)
    assert row["status"] == "rejected"
    assert _findings(row)["action_exists"] is False

    disabled = _payload()
    disabled["proposal"]["id"] = "prop-disabled"
    disabled["proposal"]["steps"][0]["capability_id"] = "next.run_discovery"
    disabled["proposal"]["steps"][0]["parameters"] = {}
    row2 = _import(client, disabled)
    assert row2["status"] == "rejected"
    assert _findings(row2)["action_enabled"] is False


def test_multi_step_and_placeholders_rejected(client: TestClient) -> None:
    multi = _payload()
    multi["proposal"]["id"] = "prop-multi"
    step = copy.deepcopy(multi["proposal"]["steps"][0])
    multi["proposal"]["steps"] = [step, copy.deepcopy(step)]
    row = _import(client, multi)
    assert row["status"] == "rejected"
    assert _findings(row)["single_executable_step"] is False

    placeholder = _payload()
    placeholder["proposal"]["id"] = "prop-placeholder"
    placeholder["proposal"]["steps"][0]["parameters"] = {
        "profile": "<profile from previous step>"}
    row2 = _import(client, placeholder)
    assert row2["status"] == "rejected"
    assert _findings(row2)["no_placeholders"] is False


def test_acceptance_criteria_must_be_human_sourced(client: TestClient) -> None:
    body = _payload()
    body["proposal"]["id"] = "prop-no-ac"
    body["acceptance_criteria"] = []
    row = _import(client, body)
    assert row["status"] == "rejected"
    assert _findings(row)["acceptance_criteria_present"] is False

    body2 = _payload()
    body2["proposal"]["id"] = "prop-pi-ac"
    body2["acceptance_criteria"] = [
        {"id": "ac", "statement": "whatever pi says", "source": "pi:model"}]
    row2 = _import(client, body2)
    assert row2["status"] == "rejected"
    assert _findings(row2)["acceptance_human_sourced"] is False


def test_self_approval_denied_and_confirm_required(client: TestClient) -> None:
    row = _import(client, _payload())
    key = row["proposal_key"]

    no_confirm = client.post(f"/api/praxis/proposals/{key}/approve",
                             json={"approved_by": "ernan", "confirm": False})
    assert no_confirm.status_code == 409

    for who in ("pi", "Praxis", "agent", "system"):
        denied = client.post(f"/api/praxis/proposals/{key}/approve",
                             json={"approved_by": who, "confirm": True})
        assert denied.status_code == 422, who
        assert "cannot approve" in denied.text


def test_approve_then_execute_with_mocked_work(client: TestClient) -> None:
    row = _import(client, _payload())
    key = row["proposal_key"]
    approved = client.post(f"/api/praxis/proposals/{key}/approve",
                           json={"approved_by": "ernan", "confirm": True})
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved_by"] == "ernan"
    assert body["approval_digest"] == body["content_digest"]

    calls: list[dict[str, Any]] = []

    async def fake_start_action(application_id, action_id, parameters, *, confirm):
        calls.append({"application_id": application_id, "action_id": action_id,
                      "parameters": parameters, "confirm": confirm})

        class _Read:
            id = "exec-test-1"

        return _Read()

    client.app.state.integration_service.start_action = fake_start_action  # type: ignore[union-attr]
    executed = client.post(f"/api/praxis/proposals/{key}/execute",
                           json={"requested_by": "ernan", "confirm": True})
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["execution_id"] == "exec-test-1"
    assert body["status"] == "running"
    assert calls == [{
        "application_id": "writer",
        "action_id": "audit_registered_books",
        "parameters": {"profile": "technical-nonfiction-v1"},
        "confirm": True,
    }]

    again = client.post(f"/api/praxis/proposals/{key}/execute",
                        json={"requested_by": "ernan", "confirm": True})
    assert again.status_code == 409
    assert "already been executed" in again.text


def test_execute_requires_approval(client: TestClient) -> None:
    row = _import(client, _payload())
    response = client.post(f"/api/praxis/proposals/{row['proposal_key']}/execute",
                           json={"requested_by": "ernan", "confirm": True})
    assert response.status_code == 409
    assert "approved" in response.text


def test_stale_approval_refused(client: TestClient) -> None:
    row = _import(client, _payload())
    key = row["proposal_key"]
    client.post(f"/api/praxis/proposals/{key}/approve",
                json={"approved_by": "ernan", "confirm": True})
    with client.app.state.database.session() as session:  # type: ignore[union-attr]
        from mission_control.praxis_proposals.models import PraxisProposal

        stored = session.get(PraxisProposal, key)
        assert stored is not None
        stored.approval_digest = "sha256:tampered"
    response = client.post(f"/api/praxis/proposals/{key}/execute",
                           json={"requested_by": "ernan", "confirm": True})
    assert response.status_code == 409
    assert "does not match" in response.text


def test_evidence_reports_correlation_and_evaluation_boundary(client: TestClient) -> None:
    row = _import(client, _payload())
    key = row["proposal_key"]
    client.post(f"/api/praxis/proposals/{key}/approve",
                json={"approved_by": "ernan", "confirm": True})

    async def fake_start_action(application_id, action_id, parameters, *, confirm):
        class _Read:
            id = "exec-evidence-1"

        return _Read()

    client.app.state.integration_service.start_action = fake_start_action  # type: ignore[union-attr]
    client.post(f"/api/praxis/proposals/{key}/execute",
                json={"requested_by": "ernan", "confirm": True})
    response = client.get(f"/api/praxis/proposals/{key}/evidence")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["correlation"]["proposal_key"] == key
    assert body["correlation"]["correlation_id"].startswith("mcprop-")
    assert body["correlation"]["execution_id"] == "exec-evidence-1"
    assert body["correlation"]["approved_by"] == "ernan"
    assert "goal achievement" in " ".join(
        body["evaluation_boundary"]["mc_does_not_assert"])
    # No integration execution row exists for the fake id, so execution stays None.
    assert body["execution"] is None


def test_reject_flow_and_duplicate_listing(client: TestClient) -> None:
    row = _import(client, _payload())
    key = row["proposal_key"]
    rejected = client.post(f"/api/praxis/proposals/{key}/reject",
                           json={"rejected_by": "ernan",
                                 "reason": "pilot scope changed", "confirm": True})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    listing = client.get("/api/praxis/proposals")
    assert listing.status_code == 200
    assert any(item["proposal_key"] == key for item in listing.json())


def test_unknown_proposal_404(client: TestClient) -> None:
    assert client.get("/api/praxis/proposals/nope@1").status_code == 404


def test_praxis_cannot_write_arbitrary_action_endpoint(client: TestClient) -> None:
    """There is no endpoint that executes an action from a raw body."""
    response = client.post("/api/praxis/execute",
                           json={"application_id": "writer",
                                 "action_id": "audit_registered_books"})
    assert response.status_code == 404
