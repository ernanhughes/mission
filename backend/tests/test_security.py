from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from helpers import FIXTURES

ALLOWED_ORIGIN = "http://127.0.0.1:5173"
LOCAL_HEADERS = {"Origin": ALLOWED_ORIGIN, "X-Mission-Control-Request": "1"}


def test_browser_origin_guard_blocks_cross_site_execution(client: TestClient) -> None:
    task = {"title": "Origin test"}
    rejected = client.post("/api/tasks", json=task, headers={"Origin": ALLOWED_ORIGIN})
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "origin_rejected"

    hostile = client.post(
        "/api/tasks",
        json=task,
        headers={"Origin": "https://evil.example", "X-Mission-Control-Request": "1"},
    )
    assert hostile.status_code == 403

    accepted = client.post("/api/tasks", json=task, headers=LOCAL_HEADERS)
    assert accepted.status_code == 201, accepted.text

    # Local CLI clients without an Origin remain supported.
    cli = client.post("/api/tasks", json={"title": "CLI task"})
    assert cli.status_code == 201


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "Mission Control"


def test_external_browser_mode_opens_the_system_browser(
    client: TestClient, monkeypatch
) -> None:
    opened: list[str] = []

    def fake_open(url: str, new: int = 0) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", fake_open)
    configured = client.patch(
        "/api/settings", json={"browser": {"open_mode": "external"}}
    )
    assert configured.status_code == 200
    response = client.post("/api/applications/work/open-url")
    assert response.status_code == 200, response.text
    assert response.json()["opened_externally"] is True
    assert opened and opened[0] == "http://127.0.0.1:8765/"


def test_launch_requests_cannot_inject_an_executable_or_working_directory(
    client: TestClient,
) -> None:
    injected = client.post(
        "/api/applications/next/launch",
        json={"executable": "C:\\Windows\\System32\\cmd.exe", "arguments": ["/c", "whoami"]},
        headers=LOCAL_HEADERS,
    )
    assert injected.status_code == 422
    assert "Extra inputs are not permitted" in injected.text or "extra_forbidden" in injected.text

    missing = client.post("/api/processes/not-a-real-process/stop", headers=LOCAL_HEADERS)
    assert missing.status_code == 404


def test_unsafe_application_configuration_is_rejected(client: TestClient) -> None:
    base = {
        "id": "unsafe-app",
        "name": "Unsafe",
        "category": "supporting",
        "repository_path": str(FIXTURES),
    }
    shell_executable = client.post(
        "/api/applications",
        json={
            **base,
            "launch_definitions": [
                {
                    "name": "Bad",
                    "launch_type": "command",
                    "executable": "cmd.exe & whoami",
                    "arguments": [],
                    "enabled": True,
                }
            ],
        },
        headers=LOCAL_HEADERS,
    )
    assert shell_executable.status_code == 422

    cmd_script = client.post(
        "/api/applications",
        json={
            **base,
            "id": "cmd-app",
            "launch_definitions": [
                {
                    "name": "Bad",
                    "launch_type": "command",
                    "executable": "C:\\Projects\\thing.cmd",
                    "arguments": [],
                    "enabled": True,
                }
            ],
        },
        headers=LOCAL_HEADERS,
    )
    assert cmd_script.status_code == 422
    assert "native executable" in cmd_script.text

    traversal = client.post(
        "/api/applications",
        json={**base, "id": "traversal-app", "repository_path": "C:\\Projects\\..\\Windows"},
        headers=LOCAL_HEADERS,
    )
    assert traversal.status_code == 422

    relative = client.post(
        "/api/applications",
        json={**base, "id": "relative-app", "repository_path": "relative\\path"},
        headers=LOCAL_HEADERS,
    )
    assert relative.status_code == 422

    relative_cwd = client.post(
        "/api/applications",
        json={
            **base,
            "id": "relative-cwd",
            "launch_definitions": [
                {
                    "name": "Run",
                    "launch_type": "command",
                    "executable": sys.executable,
                    "arguments": [],
                    "working_directory": "relative",
                    "enabled": True,
                }
            ],
        },
        headers=LOCAL_HEADERS,
    )
    assert relative_cwd.status_code == 422


def test_discovery_roots_reject_relative_and_traversal_paths(client: TestClient) -> None:
    relative = client.post(
        "/api/discovery/roots", json={"path": "C:\\Projects\\..\\Windows"}, headers=LOCAL_HEADERS
    )
    assert relative.status_code == 422
    missing = client.post(
        "/api/discovery/roots", json={"path": "C:\\does-not-exist-mc"}, headers=LOCAL_HEADERS
    )
    assert missing.status_code == 422


def test_ai_secrets_are_never_stored_or_returned(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-testSECRET1234567890")
    rejected = client.patch(
        "/api/settings",
        json={"ai": {"enabled": True, "consent": True, "api_key": "sk-should-not-store"}},
        headers=LOCAL_HEADERS,
    )
    assert rejected.status_code == 422
    assert "sk-should-not-store" not in rejected.text

    configured = client.patch(
        "/api/settings",
        json={
            "ai": {
                "enabled": True,
                "consent": True,
                "base_url": "http://127.0.0.1:1/v1",
                "model": "test-model",
                "api_key_env": "OPENAI_API_KEY",
            }
        },
        headers=LOCAL_HEADERS,
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["ai_key_present"] is True
    assert "sk-testSECRET1234567890" not in configured.text

    fetched = client.get("/api/settings")
    assert fetched.status_code == 200
    assert fetched.json()["ai_key_present"] is True
    assert "sk-testSECRET1234567890" not in fetched.text
    assert "api_key" not in fetched.json()["ai"]
