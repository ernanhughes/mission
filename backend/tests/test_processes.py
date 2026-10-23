from __future__ import annotations

import sys
import time
from pathlib import Path

import psutil
import pytest
from fastapi.testclient import TestClient

from helpers import FIXTURES, make_fixture_application, open_client, stop_all
from mission_control.config import RuntimeSettings
from mission_control.models import ProcessInstance
from mission_control.persistence.db import now_iso


def wait_for_status(client: TestClient, process_id: str, expected: set[str], timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = client.get(f"/api/processes/{process_id}").json()
        if last.get("status") in expected:
            return last
        time.sleep(0.1)
    raise AssertionError(f"Process {process_id} did not reach {expected}; last={last}")


def wait_for_log(client: TestClient, process_id: str, needle: str, timeout: float = 8.0) -> str:
    deadline = time.time() + timeout
    text = ""
    while time.time() < deadline:
        text = "\n".join(client.get(f"/api/processes/{process_id}/logs").json()["lines"])
        if needle in text:
            return text
        time.sleep(0.15)
    raise AssertionError(f"Log did not contain {needle!r}. Last log:\n{text}")


@pytest.mark.integration
def test_real_process_launch_logs_and_stop(client: TestClient) -> None:
    make_fixture_application(client, app_id="real-process", name="Real Process", arguments=["hello"])
    response = client.post("/api/applications/real-process/launch", json={})
    assert response.status_code == 201, response.text
    process = response.json()
    assert process["pid"]
    running = wait_for_status(client, process["id"], {"running"})
    assert running["owned"] is True
    text = wait_for_log(client, process["id"], "fixture-start")
    assert "fixture-arg=hello" in text
    assert "Environment: allowlisted" in text
    assert "api_key" not in text.lower()

    app = client.get("/api/applications/real-process").json()
    assert app["status"]["state"] == "running"
    assert app["actions"]["stop"]["enabled"] is True
    assert app["actions"]["launch"]["enabled"] is False

    stopped = client.post(f"/api/processes/{process['id']}/stop")
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "stopped"
    time.sleep(0.3)
    assert not psutil.pid_exists(process["pid"])
    assert client.get("/api/applications/real-process").json()["status"]["state"] == "stopped"


@pytest.mark.integration
def test_duplicate_launch_and_process_limit(client: TestClient) -> None:
    make_fixture_application(client, app_id="first-process", name="First")
    first = client.post("/api/applications/first-process/launch", json={})
    assert first.status_code == 201
    try:
        duplicate = client.post("/api/applications/first-process/launch", json={})
        assert duplicate.status_code == 409
        assert "already has a managed process" in duplicate.text

        assert client.patch("/api/settings", json={"processes": {"max_managed": 1}}).status_code == 200
        make_fixture_application(client, app_id="second-process", name="Second")
        blocked = client.post("/api/applications/second-process/launch", json={})
        assert blocked.status_code == 409
        assert "limit" in blocked.text.lower()
    finally:
        stop_all(client)


@pytest.mark.integration
def test_failed_launch_is_reported_and_isolated(client: TestClient) -> None:
    bad = {
        "id": "bad-launch",
        "name": "Bad Launch",
        "category": "supporting",
        "repository_path": str(FIXTURES),
        "launch_definitions": [
            {
                "id": "bad-run",
                "name": "Bad",
                "launch_type": "command",
                "executable": "definitely-not-a-real-executable-xyz",
                "arguments": [],
                "working_directory": str(FIXTURES),
                "enabled": True,
                "is_primary": True,
                "health_type": "none",
            }
        ],
    }
    assert client.post("/api/applications", json=bad).status_code == 201
    response = client.post("/api/applications/bad-launch/launch", json={})
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "launch_failed"
    assert "not found" in payload["error"]["message"].lower()

    app = client.get("/api/applications/bad-launch").json()
    assert app["status"]["state"] == "launch_failed"
    assert "not found" in app["last_failure_detail"].lower()
    # Other applications and the API remain available.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/applications/next").status_code == 200

    processes = client.get("/api/processes?application_id=bad-launch").json()
    assert len(processes) == 1
    assert processes[0]["status"] == "failed"
    assert processes[0]["error"]


def test_process_with_missing_working_directory_fails_cleanly(client: TestClient) -> None:
    payload = {
        "id": "missing-cwd",
        "name": "Missing CWD",
        "category": "supporting",
        "launch_definitions": [
            {
                "id": "missing-cwd-run",
                "name": "Run",
                "launch_type": "command",
                "executable": sys.executable,
                "arguments": ["-c", "print(1)"],
                "working_directory": "C:\\definitely-missing-directory-mc-test",
                "enabled": True,
                "is_primary": True,
            }
        ],
    }
    assert client.post("/api/applications", json=payload).status_code == 201
    response = client.post("/api/applications/missing-cwd/launch", json={})
    assert response.status_code == 422
    assert "does not exist" in response.text.lower()
    app = client.get("/api/applications/missing-cwd").json()
    assert app["status"]["state"] in {"launch_failed", "misconfigured"}
    assert "does not exist" in (app["last_failure_detail"] or "").lower()


@pytest.mark.integration
def test_managed_process_survives_backend_restart_and_reattaches(runtime: RuntimeSettings) -> None:
    with open_client(runtime) as client:
        make_fixture_application(client, app_id="survivor", name="Survivor")
        launched = client.post("/api/applications/survivor/launch", json={})
        assert launched.status_code == 201
        process = launched.json()
        wait_for_log(client, process["id"], "fixture-start")

    with open_client(runtime) as client:
        reattached = client.get(f"/api/processes/{process['id']}").json()
        assert reattached["status"] == "running"
        assert reattached["reattached"] is True
        stopped = client.post(f"/api/processes/{process['id']}/stop")
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["status"] == "stopped"


@pytest.mark.integration
def test_configured_editor_opens_the_registered_repository(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe_log = tmp_path / "editor-probe.txt"
    monkeypatch.setenv("EDITOR_PROBE_LOG", str(probe_log))
    response = client.patch(
        "/api/settings",
        json={
            "editor": {
                "command": sys.executable,
                "arguments": [str(FIXTURES / "editor_probe.py")],
                "append_path": True,
            }
        },
    )
    assert response.status_code == 200, response.text
    make_fixture_application(client, app_id="editor-app", name="Editor App")
    project = client.get("/api/projects/math").json()
    assert project["repository_action"]["enabled"] is True
    opened = client.post("/api/applications/editor-app/open-repository")
    assert opened.status_code == 200, opened.text
    deadline = time.time() + 8
    while time.time() < deadline and not probe_log.exists():
        time.sleep(0.1)
    assert probe_log.exists()
    assert probe_log.read_text(encoding="utf-8") == str(FIXTURES.resolve())

    documentation = FIXTURES / "editor_probe.py"
    patched = client.patch(
        "/api/applications/editor-app",
        json={"documentation_paths": [str(documentation)]},
    )
    assert patched.status_code == 200
    assert patched.json()["actions"]["open_documentation"]["enabled"] is True
    docs_opened = client.post("/api/applications/editor-app/open-documentation")
    assert docs_opened.status_code == 200, docs_opened.text
    deadline = time.time() + 8
    while time.time() < deadline:
        if probe_log.read_text(encoding="utf-8") == str(documentation.resolve()):
            break
        time.sleep(0.1)
    assert probe_log.read_text(encoding="utf-8") == str(documentation.resolve())


def test_health_probe_reports_unavailable_without_inventing_health(client: TestClient) -> None:
    make_fixture_application(
        client,
        app_id="health-app",
        name="Health App",
        health_type="http",
        health_url="http://127.0.0.1:1/health",
    )
    response = client.post("/api/applications/health-app/check-health")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "unavailable"
    assert "failed" in response.json()["detail"].lower() or "timed out" in response.json()["detail"].lower()


def test_external_process_record_cannot_be_stopped(client: TestClient) -> None:
    with client.app.state.database.session() as session:
        session.add(
            ProcessInstance(
                id="external-process",
                application_id="next",
                status="running",
                started_at=now_iso(),
                owned=False,
                pid=None,
            )
        )
    response = client.post("/api/processes/external-process/stop")
    assert response.status_code == 409
    assert "does not own" in response.json()["error"]["message"].lower()

    with client.app.state.database.session() as session:
        record = session.get(ProcessInstance, "external-process")
        assert record is not None
        assert record.status == "running"


@pytest.mark.integration
def test_startup_profile_activation_is_explicit_and_bounded(client: TestClient) -> None:
    make_fixture_application(client, app_id="profile-app", name="Profile App")
    disabled = client.post("/api/startup/activate")
    assert disabled.status_code == 409

    configured = client.patch(
        "/api/settings",
        json={
            "startup": {
                "profile_enabled": True,
                "profile_applications": ["profile-app"],
            }
        },
    )
    assert configured.status_code == 200, configured.text
    activated = client.post("/api/startup/activate")
    assert activated.status_code == 200, activated.text
    body = activated.json()
    assert len(body["activated"]) == 1
    assert body["activated"][0]["application_id"] == "profile-app"
    try:
        running = client.get("/api/processes?application_id=profile-app").json()
        assert running[0]["status"] == "running"
    finally:
        stop_all(client)


def test_editor_shell_script_is_rejected(client: TestClient) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "editor": {
                "command": r"C:\Projects\some-editor.cmd",
                "arguments": [],
                "append_path": True,
            }
        },
    )
    assert response.status_code == 422
    assert "native executable" in response.text.lower() or "shell script" in response.text.lower()


@pytest.mark.integration
def test_logs_redact_secrets(client: TestClient) -> None:
    make_fixture_application(
        client,
        app_id="secret-app",
        name="Secret App",
        script="secret_process.py",
    )
    launched = client.post("/api/applications/secret-app/launch", json={})
    assert launched.status_code == 201
    process_id = launched.json()["id"]
    try:
        text = wait_for_log(client, process_id, "starting diagnostic")
        assert "sk-testSECRET1234567890" not in text
        assert "super-secret-token" not in text
        assert "[REDACTED" in text
    finally:
        client.post(f"/api/processes/{process_id}/stop")
