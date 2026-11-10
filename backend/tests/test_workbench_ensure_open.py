"""Tests for the one-click Workbench start-or-open orchestration (MC-WORKBENCH-01)."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from helpers import FIXTURES, PYTHON_EXECUTABLE, open_client, stop_all
from mission_control.config import RuntimeSettings
from mission_control.models import LaunchDefinition
from mission_control.persistence.seed import ensure_workbench_launch_definition
from mission_control.processes.manager import verify_workbench_identity


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def workbench_definition(port: int, mode: str = "workbench") -> dict:
    url = f"http://127.0.0.1:{port}/"
    return {
        "id": "workbench-server",
        "name": "Workbench server",
        "launch_type": "server",
        "executable": PYTHON_EXECUTABLE,
        "arguments": ["workbench_probe.py", str(port), mode],
        "working_directory": str(FIXTURES),
        "env_names": [],
        "browser_url": url,
        "health_type": "http",
        "health_url": url,
        "expected_port": port,
        "is_primary": True,
        "enabled": True,
        "verified": True,
        "verification_note": "test fixture",
        "shutdown_behavior": "terminate",
    }


def patch_workbench_launch(client: TestClient, port: int, mode: str = "workbench") -> dict:
    response = client.patch(
        "/api/applications/workbench", json={"launch_definitions": [workbench_definition(port, mode)]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"Port {port} did not open in time")


def test_ensure_open_starts_stopped_app_and_reuses_it(client: TestClient) -> None:
    port = free_port()
    patch_workbench_launch(client, port)
    try:
        first = client.post("/api/applications/workbench/ensure-open")
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["url"] == f"http://127.0.0.1:{port}/"
        assert body["state"] == "started"
        assert body["ownership"] == "managed"
        assert body["process_id"]

        second = client.post("/api/applications/workbench/ensure-open")
        assert second.status_code == 200, second.text
        assert second.json()["state"] == "running"
        assert second.json()["process_id"] == body["process_id"]

        running = [
            process
            for process in client.get("/api/processes?application_id=workbench").json()
            if process["status"] == "running"
        ]
        assert len(running) == 1
    finally:
        stop_all(client)


def test_ensure_open_concurrent_calls_share_one_process(client: TestClient) -> None:
    port = free_port()
    patch_workbench_launch(client, port)
    try:
        results: list[tuple[int, dict]] = []

        def call() -> None:
            # Both clicks share the backend (and its serialised launcher),
            # exactly like two rapid clicks in the Mission Control tab.
            response = client.post("/api/applications/workbench/ensure-open")
            results.append((response.status_code, response.json()))

        threads = [threading.Thread(target=call) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        assert len(results) == 2
        assert all(status == 200 for status, _ in results)
        assert results[0][1]["process_id"] == results[1][1]["process_id"]
        running = [
            process
            for process in client.get("/api/processes?application_id=workbench").json()
            if process["status"] == "running"
        ]
        assert len(running) == 1
    finally:
        stop_all(client)


def test_ensure_open_refuses_port_occupied_by_something_else(client: TestClient) -> None:
    port = free_port()
    patch_workbench_launch(client, port, mode="other")
    intruder = subprocess.Popen(
        [PYTHON_EXECUTABLE, "workbench_probe.py", str(port), "other"],
        cwd=str(FIXTURES),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port(port)
        response = client.post("/api/applications/workbench/ensure-open")
        assert response.status_code == 409, response.text
        assert "already in use" in response.json()["error"]["message"].lower()
        running = [
            process
            for process in client.get("/api/processes?application_id=workbench").json()
            if process["status"] == "running"
        ]
        assert running == []
    finally:
        intruder.terminate()
        try:
            intruder.wait(timeout=5)
        except subprocess.TimeoutExpired:
            intruder.kill()
        stop_all(client)


def test_ensure_open_adopts_external_workbench_without_claiming(client: TestClient) -> None:
    port = free_port()
    patch_workbench_launch(client, port, mode="workbench")
    external = subprocess.Popen(
        [PYTHON_EXECUTABLE, "workbench_probe.py", str(port), "workbench"],
        cwd=str(FIXTURES),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port(port)
        response = client.post("/api/applications/workbench/ensure-open")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["state"] == "running_external"
        assert body["ownership"] == "external"
        assert body["process_id"] is None
        # Mission Control must not claim or stop what it did not launch.
        running = [
            process
            for process in client.get("/api/processes?application_id=workbench").json()
            if process["status"] == "running"
        ]
        assert running == []
    finally:
        external.terminate()
        try:
            external.wait(timeout=5)
        except subprocess.TimeoutExpired:
            external.kill()
        stop_all(client)


def test_ensure_open_reports_missing_environment(client: TestClient) -> None:
    payload = {
        "id": "missing-env",
        "name": "Missing Env",
        "category": "supporting",
        "repository_path": str(FIXTURES),
        "launch_definitions": [
            {
                "id": "missing-env-run",
                "name": "Run",
                "launch_type": "server",
                "executable": "definitely-not-a-real-executable-xyz",
                "arguments": [],
                "working_directory": str(FIXTURES),
                "enabled": True,
                "is_primary": True,
                "browser_url": f"http://127.0.0.1:{free_port()}/",
                "health_type": "none",
            }
        ],
    }
    assert client.post("/api/applications", json=payload).status_code == 201
    response = client.post("/api/applications/missing-env/ensure-open")
    assert response.status_code == 422, response.text
    assert "not found" in response.json()["error"]["message"].lower()
    app = client.get("/api/applications/missing-env").json()
    assert app["status"]["state"] == "launch_failed"


def test_ensure_open_requires_a_stored_browser_url(client: TestClient) -> None:
    payload = {
        "id": "no-url",
        "name": "No URL",
        "category": "supporting",
        "repository_path": str(FIXTURES),
        "launch_definitions": [
            {
                "id": "no-url-run",
                "name": "Run",
                "launch_type": "command",
                "executable": sys.executable,
                "arguments": ["-c", "print(1)"],
                "working_directory": str(FIXTURES),
                "enabled": True,
                "is_primary": True,
                "health_type": "none",
            }
        ],
    }
    assert client.post("/api/applications", json=payload).status_code == 201
    response = client.post("/api/applications/no-url/ensure-open")
    assert response.status_code == 409, response.text
    assert "browser url" in response.text.lower()


def test_workbench_backfill_inserts_once_without_overwriting(client: TestClient) -> None:
    database = client.app.state.database
    with database.session() as session:
        deleted = (
            session.scalars(
                select(LaunchDefinition).where(LaunchDefinition.application_id == "workbench")
            ).all()
        )
        for definition in deleted:
            session.delete(definition)
        session.flush()
        assert ensure_workbench_launch_definition(session) is True
    with database.session() as session:
        assert ensure_workbench_launch_definition(session) is False
        definitions = (
            session.scalars(
                select(LaunchDefinition).where(LaunchDefinition.application_id == "workbench")
            ).all()
        )
        assert len(definitions) == 1
        assert definitions[0].browser_url == "http://127.0.0.1:7420/"
        assert definitions[0].expected_port == 7420


def test_verify_workbench_identity_rejects_non_loopback() -> None:
    matches, detail = asyncio.run(verify_workbench_identity("http://example.com/"))
    assert matches is False
    assert "loopback" in detail


def test_verify_workbench_identity_rejects_non_http() -> None:
    matches, detail = asyncio.run(verify_workbench_identity("file:///C:/Projects/workbench"))
    assert matches is False
    assert "http" in detail.lower()


@pytest.mark.integration
def test_managed_process_still_reattaches_after_restart(runtime: RuntimeSettings) -> None:
    with open_client(runtime) as first:
        port = free_port()
        assert first.patch("/api/applications/workbench", json={"launch_definitions": [workbench_definition(port)]}).status_code == 200
        launched = first.post("/api/applications/workbench/ensure-open")
        assert launched.status_code == 200, launched.text
        process_id = launched.json()["process_id"]
        try:
            with open_client(runtime) as second:
                reattached = second.get(f"/api/processes/{process_id}").json()
                assert reattached["status"] == "running"
                assert reattached["reattached"] is True
                reopened = second.post("/api/applications/workbench/ensure-open")
                assert reopened.status_code == 200, reopened.text
                assert reopened.json()["process_id"] == process_id
                stopped = second.post(f"/api/processes/{process_id}/stop")
                assert stopped.status_code == 200, stopped.text
        finally:
            with open_client(runtime) as cleanup:
                stop_all(cleanup)
