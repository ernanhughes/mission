from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from mission_control.config import RuntimeSettings
from mission_control.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
# The uv virtual-environment python.exe is a launcher that immediately exits
# after spawning the base interpreter. For a restart-reattachment test we need
# the actual long-lived process, so use the base executable when available.
PYTHON_EXECUTABLE = getattr(sys, "_base_executable", sys.executable)


@contextmanager
def open_client(settings: RuntimeSettings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


def make_fixture_application(
    client: TestClient,
    *,
    app_id: str = "fixture-app",
    name: str = "Fixture Application",
    script: str = "managed_process.py",
    arguments: list[str] | None = None,
    health_type: str = "none",
    health_url: str | None = None,
    expected_port: int | None = None,
    repository_path: str | None = None,
) -> dict:
    payload = {
        "id": app_id,
        "name": name,
        "category": "supporting",
        "repository_path": repository_path or str(FIXTURES),
        "enabled": True,
        "pinned": False,
        "launch_definitions": [
            {
                "id": f"{app_id}-run",
                "name": "Run fixture",
                "launch_type": "server",
                "executable": PYTHON_EXECUTABLE,
                "arguments": [script, *(arguments or [])],
                "working_directory": str(FIXTURES),
                "enabled": True,
                "verified": True,
                "is_primary": True,
                "health_type": health_type,
                "health_url": health_url,
                "expected_port": expected_port,
            }
        ],
    }
    response = client.post("/api/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def stop_all(client: TestClient) -> None:
    processes = client.get("/api/processes?limit=100").json()
    for process in processes:
        if process["status"] == "running":
            client.post(f"/api/processes/{process['id']}/stop")
