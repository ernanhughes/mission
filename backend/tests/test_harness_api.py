from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mission_control import models as orm
from mission_control.api import harness


def make_client(monkeypatch, *, model_policy="local_only", duplicate=False):
    app = FastAPI()
    app.include_router(harness.router)
    app.state.settings = SimpleNamespace(worker_base_url="http://127.0.0.1:7317")
    app.state.episode_service = SimpleNamespace(
        get_episode=lambda episode_id: {"id": episode_id, "project_key": "project-1", "status": "established"}
    )
    app.state.intent_service = SimpleNamespace(
        list_objectives=lambda **_: [{"id": "objective-1", "text": "Return the answer as JSON.", "status": "current"}]
    )
    registrations = []

    class Envelopes:
        def register_envelope(self, **kwargs):
            registrations.append(kwargs)
            if duplicate:
                return {"status": "duplicate", "envelope_id": "we:prior"}
            return {"status": "completed", "envelope_id": "we:new", "commission_digest": "abc"}

    app.state.envelope_service = Envelopes()
    strategies = [{"key": key, "id": key.split(".")[0], "version": "1", "maximum_model_invocations": 2,
                   "supported_backends": ["model"], "behavior": "authoritative Worker description"}
                  for key in sorted(harness.STRATEGY_IDS)]
    models = [{"id": "local-free", "model": "fixture-model", "economic_tier": "free", "data_policy": model_policy}]
    policies = {"local-policy": {"routes": ["local-free"], "required_data_policy": "local_only", "attempts_per_route": 1}}

    async def fake_get(client, base, path):
        if path == "/health":
            return {"status": "ok", "version": "test"}
        if path == "/v1/strategies":
            return {"schema_version": "worker.execution-strategies.v1", "strategies": strategies}
        if path == "/v1/models/catalogue":
            return {"approved": models, "policies": policies}
        if path == "/v1/executions":
            return {"executions": [], "more_in_read_window": False}
        raise AssertionError(path)

    class Response:
        status_code = 200

        def json(self):
            return {"request_id": "wrq_1234567890abcdef", "status": "AWAITING_ACCEPTANCE",
                    "output": "{\"answer\":42}", "execution": {"backend": "model"}}

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(harness, "_get", fake_get)
    monkeypatch.setattr(harness.httpx, "AsyncClient", AsyncClient)
    return TestClient(app), registrations


def test_catalogue_projects_worker_metadata_without_claiming_qualification(monkeypatch):
    client, _ = make_client(monkeypatch)
    response = client.get("/api/harness/catalogue")
    assert response.status_code == 200
    payload = response.json()
    assert {row["key"] for row in payload["strategies"]} == harness.STRATEGY_IDS
    assert all(row["qualification"] == "not_asserted_by_catalogue" for row in payload["strategies"])
    assert payload["worker"]["reachable"] is True


def test_launch_uses_verified_work_outcome_identity_and_requires_explicit_authority(monkeypatch):
    client, registrations = make_client(monkeypatch)
    response = client.post("/api/harness/executions", json={
        "episode_id": "episode-1", "objective_id": "objective-1", "strategy_id": "adaptive.v1",
        "model_route": "local-free", "policy": "local-policy", "normalization_policy": "json-fence.v1",
        "timeout_ms": 30_000, "max_output_tokens": 256, "actor": "owner",
        "authorization_note": "Confirmed in Harness UI", "submission_id": "submission-0001",
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["worker_result"]["status"] == "AWAITING_ACCEPTANCE"
    assert payload["correlation"]["linkage"] == "mission-work-envelope-correlated; Worker episode fields remain caller-supplied"
    assert registrations[0]["actor"] == "owner"
    assert registrations[0]["episode_id"] == "episode-1"


def test_launch_rejects_external_route_before_authorizing_or_dispatching(monkeypatch):
    client, registrations = make_client(monkeypatch, model_policy="private")
    response = client.post("/api/harness/executions", json={
        "episode_id": "episode-1", "objective_id": "objective-1", "strategy_id": "direct.v1",
        "model_route": "local-free", "policy": "local-policy", "actor": "owner",
        "authorization_note": "Confirmed in Harness UI", "submission_id": "submission-0002",
    })
    assert response.status_code == 422
    assert registrations == []


def test_project_scoped_launch_rejects_episode_from_another_project(monkeypatch):
    client, registrations = make_client(monkeypatch)
    response = client.post("/api/harness/executions", json={
        "episode_id": "episode-1", "objective_id": "objective-1", "strategy_id": "direct.v1",
        "model_route": "local-free", "policy": "local-policy", "actor": "owner",
        "authorization_note": "Confirmed in Harness UI", "submission_id": "submission-project-1",
        "project_key": "project-2",
    })
    assert response.status_code == 422
    assert "outside the requested project scope" in response.text
    assert registrations == []


def test_worker_episode_link_is_verified_only_against_matching_mission_envelope():
    envelope = SimpleNamespace(id="we:fixture", episode_id="episode-1", objective_ref="objective-1")
    episode = SimpleNamespace(id="episode-1", project_key="project-1")

    class Query:
        def __init__(self, rows): self.rows = rows
        def filter(self, *_): return self
        def all(self): return self.rows

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def query(self, model): return Query([envelope] if model is orm.WoWorkEnvelope else [episode])

    app = SimpleNamespace(state=SimpleNamespace(database=SimpleNamespace(session=lambda: Session())))
    request = SimpleNamespace(app=app)
    row = {"operation_id": "we:fixture", "episode_id": "episode-1", "task_id": "objective-1",
           "episode_link": "caller_supplied_unverified"}
    correlated = harness._correlate_rows(request, [row])[0]
    assert correlated["mission_correlation"]["status"] == "verified"
    assert correlated["mission_correlation"]["project_key"] == "project-1"
    tampered = harness._correlate_rows(request, [{**row, "task_id": "other-objective"}])[0]
    assert tampered["mission_correlation"]["status"] == "unmatched"
    assert "episode_id" not in tampered["mission_correlation"]


def test_launch_duplicate_submission_is_not_redispatched(monkeypatch):
    client, registrations = make_client(monkeypatch, duplicate=True)
    response = client.post("/api/harness/executions", json={
        "episode_id": "episode-1", "objective_id": "objective-1", "strategy_id": "direct.v1",
        "model_route": "local-free", "policy": "local-policy", "actor": "owner",
        "authorization_note": "Confirmed in Harness UI", "submission_id": "submission-0003",
    })
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DUPLICATE_SUBMISSION"
    assert len(registrations) == 1


def test_adaptive_policy_and_budgets_are_validated_by_schema(monkeypatch):
    client, registrations = make_client(monkeypatch)
    response = client.post("/api/harness/executions", json={
        "episode_id": "episode-1", "objective_id": "objective-1", "strategy_id": "adaptive.v1",
        "model_route": "local-free", "policy": "local-policy", "actor": "owner",
        "authorization_note": "Confirmed in Harness UI", "submission_id": "submission-0004",
        "timeout_ms": 60_001,
    })
    assert response.status_code == 422
    assert registrations == []


def test_job_status_projection_redacts_prompts_and_results(monkeypatch):
    client, _ = make_client(monkeypatch)

    async def get_with_job(_client, _base, path):
        if path == "/v1/jobs":
            return {"jobs": [{"job_id": "job-1", "operation_id": "op-1", "stage_id": "stage-1",
                              "status": "complete", "started_at": "t1", "completed_at": "t2",
                              "request": {"prompt": "private prompt", "workspace": {"root": "C:/secret"}},
                              "result": {"output": "private result"},
                              "events": [{"type": "MODEL_OUTPUT", "timestamp": "t2", "prompt": "secret"}]}]}
        raise AssertionError(path)

    monkeypatch.setattr(harness, "_get", get_with_job)
    response = client.get("/api/harness/jobs")
    assert response.status_code == 200
    text = response.text
    assert "private prompt" not in text and "private result" not in text and "C:/secret" not in text
    assert "MODEL_OUTPUT" in text


def test_raw_artifact_projection_is_request_scoped_and_strips_unrelated_job_fields(monkeypatch):
    client, _ = make_client(monkeypatch)

    async def get_with_artifact(_client, _base, path):
        if path == "/v1/executions/wrq_abcdef1234567890":
            return {"request_id": "wrq_abcdef1234567890", "output_digest": "digest"}
        if path == "/v1/jobs":
            return {"jobs": [{"request": {"prompt": "private"}, "result": {
                "request_id": "wrq_abcdef1234567890", "output": "raw output",
                "strategy_execution": {"invocations": [{"output": "raw child", "output_digest": "digest", "private_field": "secret"}],
                                        "normalized_artifact": {"text": "normalized"}}}}]}
        raise AssertionError(path)

    monkeypatch.setattr(harness, "_get", get_with_artifact)
    response = client.get("/api/harness/executions/wrq_abcdef1234567890/artifacts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["output"] == "raw output"
    assert payload["strategy_execution"]["invocations"][0]["output"] == "raw child"
    assert "private_field" not in response.text and "private" not in response.text


def test_remote_worker_url_is_rejected_before_network_access(monkeypatch):
    client, _ = make_client(monkeypatch)
    client.app.state.settings.worker_base_url = "https://worker.example.com"
    response = client.get("/api/harness/catalogue")
    assert response.status_code == 503


# -- MC-HARNESS-FIX-01: empty vs unavailable vs unknown ------------------------

from fastapi import HTTPException as _HTTPException


def _ledger_client(monkeypatch, get_impl, project_ids=("jev", "ai")):
    client, _ = make_client(monkeypatch)
    monkeypatch.setattr(harness, "_get", get_impl)

    class Query:
        def __init__(self, rows): self.rows = rows
        def filter(self, *_): return self
        def all(self): return self.rows

    projects = [SimpleNamespace(id=pid) for pid in project_ids]

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def query(self, model): return Query(projects if model is orm.Project else [])

    client.app.state.database = SimpleNamespace(session=lambda: Session())
    return client


async def _raise_404(_client, _base, _path):
    raise _HTTPException(status_code=404, detail="Worker execution or retained artifact was not found")


async def _raise_503(_client, _base, _path):
    raise _HTTPException(status_code=503, detail="Worker is unavailable (ConnectError)")


async def _empty_ledger(_client, _base, path):
    assert path == "/v1/executions"
    return {"executions": [], "more_in_read_window": False}


def test_ledger_without_read_window_is_empty_not_error(monkeypatch):
    client = _ledger_client(monkeypatch, _raise_404)
    response = client.get("/api/harness/executions?project_key=jev&limit=100")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["executions"] == []
    assert payload["coverage"]["ledger"]["available"] is False
    assert payload["coverage"]["unavailable_is_not_zero"] is True
    assert payload["worker"]["reachable"] is True


def test_valid_project_with_zero_executions_is_successful_empty_collection(monkeypatch):
    client = _ledger_client(monkeypatch, _empty_ledger)
    response = client.get("/api/harness/executions?project_key=jev&limit=100")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["executions"] == []
    assert payload["coverage"]["ledger"]["available"] is True


def test_unknown_project_is_not_an_empty_history(monkeypatch):
    client = _ledger_client(monkeypatch, _empty_ledger)
    response = client.get("/api/harness/executions?project_key=nope&limit=100")
    assert response.status_code == 404
    assert "Unknown project" in response.text


def test_worker_unavailable_is_not_converted_to_empty_history(monkeypatch):
    client = _ledger_client(monkeypatch, _raise_503)
    response = client.get("/api/harness/executions?project_key=jev&limit=100")
    assert response.status_code == 503


def test_project_filter_uses_canonical_identity(monkeypatch):
    envelope = SimpleNamespace(id="we:fixture", episode_id="episode-1", objective_ref="objective-1")
    episode = SimpleNamespace(id="episode-1", project_key="Projects/ai")

    class Query:
        def __init__(self, rows): self.rows = rows
        def filter(self, *_): return self
        def all(self): return self.rows

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def query(self, model):
            if model is orm.Project:
                return Query([SimpleNamespace(id="ai")])
            if model is orm.WoWorkEnvelope:
                return Query([envelope])
            return Query([episode])

    async def get_with_row(_client, _base, path):
        assert path == "/v1/executions"
        return {"executions": [{"operation_id": "we:fixture", "episode_id": "episode-1",
                                "task_id": "objective-1", "request_id": "wrq_abcdef1234567890"}],
                "more_in_read_window": False}

    client, _ = make_client(monkeypatch)
    monkeypatch.setattr(harness, "_get", get_with_row)
    client.app.state.database = SimpleNamespace(session=lambda: Session())
    response = client.get("/api/harness/executions?project_key=ai&limit=100")
    assert response.status_code == 200, response.text
    assert len(response.json()["executions"]) == 1
    other = client.get("/api/harness/executions?project_key=writer&limit=100")
    assert other.status_code == 404
    assert "Unknown project" in other.text
