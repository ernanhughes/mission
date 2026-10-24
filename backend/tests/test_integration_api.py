from __future__ import annotations

import time

from fastapi.testclient import TestClient

from helpers import open_client
from mission_control.adapters.base import (
    ActionContext,
    ActionSpec,
    ActionResult,
    Adapter,
    AdapterResult,
    AdapterTarget,
    ResourceSeed,
)
from mission_control.config import RuntimeSettings
from mission_control.integrations.store import upsert_resources
from mission_control.models import IntegrationDecision, IntegrationRecord


def _seed_resources(client: TestClient) -> None:
    with client.app.state.database.session() as session:
        upsert_resources(
            session,
            "next",
            [
                ResourceSeed(
                    resource_type="next_opportunity",
                    external_id="next-fixture-1",
                    title="Fixture Next recommendation",
                    summary="A grounded Next fixture.",
                    state="NEW",
                    data={
                        "queue_type": "validated",
                        "scores": {"score": 42.0},
                        "source_decision_history": [],
                    },
                    evidence=["next:fixture"],
                )
            ],
        )
        upsert_resources(
            session,
            "work",
            [
                ResourceSeed(
                    resource_type="work_opportunity",
                    external_id="work-fixture-1",
                    title="Fixture qualified opportunity",
                    summary="Review the fixture opportunity.",
                    state="DISCOVERED / qualified",
                    data={
                        "qualification": {"qualified": True, "score": 72},
                        "buyer": "Fixture Buyer",
                    },
                    evidence=["work:fixture"],
                )
            ],
        )
        upsert_resources(
            session,
            "cocoder",
            [
                ResourceSeed(
                    resource_type="cocoder_finding",
                    external_id="review-fixture:F-1",
                    title="HIGH: Fixture finding",
                    summary="A fixture code finding.",
                    state="high / confirmed",
                    data={"severity": "high", "repository_path": r"C:\Projects\mission"},
                    evidence=["cocoder:fixture"],
                )
            ],
        )


def test_integration_inbox_search_decisions_and_project_association(client: TestClient) -> None:
    _seed_resources(client)
    inbox = client.get("/api/inbox?limit=50").json()
    assert {"next", "work", "cocoder"} <= {item["source_application"] for item in inbox}
    next_item = next(item for item in inbox if item["source_application"] == "next")
    assert next_item["target_path"].startswith("/next?record=")
    assert next_item["actions"]

    search = client.get("/api/search?q=fixture").json()
    assert {"Next", "Work", "CoCoder"} <= {item["source"] for item in search}

    record = client.get("/api/integrations/next/resources?limit=10").json()[0]
    assert record["data"]["queue_type"] == "validated"
    decision = client.post(
        f"/api/integrations/next/resources/{record['id']}/decision",
        json={"decision": "shortlist", "reason": "Worth a bounded review."},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["sync_state"] == "local_only"

    detail = client.get(f"/api/integrations/next/resources/{record['id']}").json()
    assert detail["local_decision"]["decision"] == "shortlist"
    assert detail["local_decision"]["sync_state"] == "local_only"
    # Source data is unchanged; only Mission Control's local decision exists.
    assert detail["state"] == "NEW"

    invalid = client.post(
        f"/api/integrations/work/resources/{client.get('/api/integrations/work/resources?limit=1').json()[0]['id']}/decision",
        json={"decision": "accept", "reason": "Unsupported Work decision"},
    )
    assert invalid.status_code == 422

    work = client.get("/api/integrations/work/resources?limit=1").json()[0]
    associated = client.patch(
        f"/api/integrations/work/resources/{work['id']}",
        json={"project_id": "math"},
    )
    assert associated.status_code == 200
    assert associated.json()["project_id"] == "math"
    context = client.get("/api/projects/math/integration-context").json()
    assert any(item["id"] == work["id"] for item in context)


class FixtureActionAdapter(Adapter):
    name = "cocoder"
    capabilities = ["execute_action", "list_actions"]
    actions = [
        ActionSpec(
            id="fixture_action",
            title="Fixture action",
            description="A safe fixture action.",
            risk="read_only",
            approval_required=True,
            parameters_schema={
                "type": "object",
                "required": ["repo_path"],
                "properties": {
                    "repo_path": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "additionalProperties": False,
            },
        )
    ]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        return AdapterResult(available=True, detail="fixture adapter", capabilities=self.capabilities, actions=self.actions)

    async def execute_action(
        self, action_id: str, parameters: dict, context: ActionContext
    ) -> ActionResult:
        return ActionResult(
            status="succeeded",
            output="fixture action completed",
            result={"repo_path": parameters["repo_path"], "count": parameters.get("count", 1)},
            exit_code=0,
        )


def test_registered_action_lifecycle_and_parameter_validation(
    client: TestClient, monkeypatch
) -> None:
    import mission_control.integrations.service as integration_service_module

    fixture = FixtureActionAdapter()
    monkeypatch.setattr(
        integration_service_module,
        "get_app_adapter",
        lambda name: fixture if name == "cocoder" else None,
    )
    missing_confirmation = client.post(
        "/api/integrations/cocoder/actions/fixture_action/execute",
        json={"parameters": {"repo_path": r"C:\Projects\mission"}, "confirm": False},
    )
    assert missing_confirmation.status_code == 409

    extra_parameter = client.post(
        "/api/integrations/cocoder/actions/fixture_action/execute",
        json={"parameters": {"repo_path": r"C:\Projects\mission", "command": "anything"}, "confirm": True},
    )
    assert extra_parameter.status_code == 422

    started = client.post(
        "/api/integrations/cocoder/actions/fixture_action/execute",
        json={"parameters": {"repo_path": r"C:\Projects\mission", "count": 3}, "confirm": True},
    )
    assert started.status_code == 200, started.text
    execution_id = started.json()["id"]
    deadline = time.time() + 10
    execution = started.json()
    while time.time() < deadline:
        execution = client.get(f"/api/integrations/executions/{execution_id}").json()
        if execution["status"] not in {"queued", "running"}:
            break
        time.sleep(0.1)
    assert execution["status"] == "succeeded"
    assert execution["approved_at"]
    assert execution["result"]["count"] == 3
    assert execution["output"] == "fixture action completed"


def test_cocoder_action_rejects_unregistered_repository_before_queue(
    client: TestClient, tmp_path
) -> None:
    outside = tmp_path / "outside-repository"
    outside.mkdir()
    response = client.post(
        "/api/integrations/cocoder/actions/run_review/execute",
        json={
            "parameters": {"repo_path": str(outside), "base": "HEAD~1", "head": "HEAD"},
            "confirm": True,
        },
    )
    assert response.status_code == 422
    assert "registered repository" in response.text
    assert client.get("/api/integrations/executions").json() == []

    invalid_ref = client.post(
        "/api/integrations/cocoder/actions/run_review/execute",
        json={
            "parameters": {
                "repo_path": str(client.app.state.settings.repo_root),
                "base": "HEAD;rm",
                "head": "HEAD",
            },
            "confirm": True,
        },
    )
    assert invalid_ref.status_code == 422
    assert "Invalid base ref" in invalid_ref.text
    assert client.get("/api/integrations/executions").json() == []


def test_integration_decisions_survive_restart(runtime: RuntimeSettings) -> None:
    with open_client(runtime) as client:
        _seed_resources(client)
        record = client.get("/api/integrations/next/resources?limit=1").json()[0]
        response = client.post(
            f"/api/integrations/next/resources/{record['id']}/decision",
            json={"decision": "investigate", "reason": "Persist this."},
        )
        assert response.status_code == 200
    with open_client(runtime) as client:
        detail = client.get(f"/api/integrations/next/resources/{record['id']}").json()
        assert detail["local_decision"]["decision"] == "investigate"
        assert detail["local_decision"]["sync_state"] == "local_only"
    with open_client(runtime) as client:
        with client.app.state.database.session() as session:
            assert session.query(IntegrationDecision).count() >= 1
            assert session.query(IntegrationRecord).count() >= 3


def test_failed_source_refresh_does_not_break_other_workspaces(client: TestClient) -> None:
    _seed_resources(client)
    # Force one integration to an unavailable path/executable, then refresh.
    configured = client.patch(
        "/api/integrations/work",
        json={
            "adapter_config": {"executable": "not-installed-work-cli"},
            "adapter_enabled": True,
        },
    )
    assert configured.status_code == 200
    refreshed = client.post("/api/integrations/work/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["available"] is False
    assert client.get("/api/integrations/next/resources?limit=1").status_code == 200
    assert client.get("/api/inbox?limit=20").status_code == 200
    assert client.get("/api/health").status_code == 200
