from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.config import RuntimeSettings
from helpers import FIXTURES, open_client


def test_dashboard_has_three_pinned_books_and_core_applications(client: TestClient) -> None:
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert [book["project_id"] for book in body["books"]] == ["language", "inference", "math"]
    app_ids = {app["id"] for app in body["applications"]}
    assert {"next", "cocoder", "work"} <= app_ids
    assert body["stats"]["priority_books"] == 3


def test_application_crud_and_launch_configuration(client: TestClient) -> None:
    payload = {
        "id": "example-tool",
        "name": "Example Tool",
        "description": "A test application",
        "category": "supporting",
        "repository_path": str(FIXTURES),
        "tags": ["test"],
        "launch_definitions": [
            {
                "name": "Run",
                "launch_type": "command",
                "executable": sys.executable,
                "arguments": ["-c", "print('hello')"],
                "working_directory": str(FIXTURES),
                "enabled": True,
                "verified": True,
                "is_primary": True,
            }
        ],
    }
    created = client.post("/api/applications", json=payload)
    assert created.status_code == 201, created.text
    app = created.json()
    assert app["source"] == "user"
    assert len(app["launch_definitions"]) == 1
    assert app["actions"]["launch"]["enabled"] is True

    patched = client.patch(
        "/api/applications/example-tool",
        json={"name": "Example Tool Renamed", "pinned": True},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Example Tool Renamed"
    assert patched.json()["pinned"] is True

    replaced = client.patch(
        "/api/applications/example-tool",
        json={
            "launch_definitions": [
                {
                    "id": "second-definition",
                    "name": "Disabled",
                    "launch_type": "none",
                    "arguments": [],
                    "enabled": False,
                }
            ]
        },
    )
    assert replaced.status_code == 200
    assert [item["id"] for item in replaced.json()["launch_definitions"]] == ["second-definition"]
    assert replaced.json()["actions"]["launch"]["enabled"] is False

    url_only = client.patch(
        "/api/applications/example-tool",
        json={
            "launch_definitions": [
                {
                    "id": "url-definition",
                    "name": "Web interface",
                    "launch_type": "url",
                    "browser_url": "http://127.0.0.1:9999/",
                    "arguments": [],
                    "enabled": True,
                }
            ]
        },
    )
    assert url_only.status_code == 200, url_only.text
    assert url_only.json()["actions"]["launch"]["enabled"] is False
    assert url_only.json()["actions"]["open_url"]["enabled"] is True

    # Disabled definitions remain visible to the editor.
    work = client.get("/api/applications/work").json()
    assert any(definition["enabled"] is False for definition in work["launch_definitions"])

    duplicate = client.post("/api/applications", json={**payload, "name": "Duplicate"})
    assert duplicate.status_code == 409


def test_application_relationship_validation(client: TestClient) -> None:
    response = client.post(
        "/api/applications",
        json={
            "id": "bad-relationship",
            "name": "Bad relationship",
            "related_projects": ["does-not-exist"],
        },
    )
    assert response.status_code == 422
    assert "Related project does not exist" in response.text


def test_create_project_with_repository_and_book(client: TestClient, tmp_path: Path) -> None:
    repo = tmp_path / "book-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Book\n\nA manuscript with chapters.", encoding="utf-8")
    response = client.post(
        "/api/projects",
        json={
            "name": "New Book",
            "kind": "book",
            "repository_path": str(repo),
            "book_title": "New Book Title",
            "next_action": "Write chapter one",
        },
    )
    assert response.status_code == 201, response.text
    project = response.json()
    assert project["id"] == "new-book"
    assert project["book"]["title"] == "New Book Title"
    assert project["repositories"][0]["path"] == str(repo.resolve())


def test_checkpoint_resume_and_priority_survive_restart(
    runtime: RuntimeSettings,
) -> None:
    with open_client(runtime) as client:
        math = client.get("/api/projects/math").json()
        assert math["status"] == "active"
        checkpoint = client.post(
            "/api/checkpoints",
            json={
                "project_id": "math",
                "summary": "Lorentz proof validation reviewed.",
                "last_completed": "Read the MATH01 report.",
                "next_action": "Inspect additional proof obligations.",
                "blockers": "",
                "milestone": "MATH01-R1",
                "evidence_refs": ["artifacts/math01/report.json"],
            },
        )
        assert checkpoint.status_code == 201, checkpoint.text
        assert client.post("/api/projects/language/focus").status_code == 200
        order = client.get("/api/books").json()
        ids = [book["id"] for book in order]
        moved = [ids[1], ids[2], ids[0]]
        assert client.post("/api/books/reorder", json={"ids": moved}).status_code == 200
        assert client.get("/api/projects/math").json()["next_action"] == (
            "Inspect additional proof obligations."
        )

    with open_client(runtime) as client:
        books = client.get("/api/books").json()
        assert [book["id"] for book in books] == moved
        assert [book["priority"] for book in books] == [1, 2, 3]
        detail = client.get("/api/projects/math").json()
        assert detail["next_action"] == "Inspect additional proof obligations."
        assert detail["latest_checkpoint"]["summary"] == "Lorentz proof validation reviewed."
        # Language remains the explicit focus, while Math's checkpoint is intact.
        resume = client.get("/api/resume").json()
        assert resume["project"]["id"] == "language"
        assert client.post("/api/projects/math/focus").status_code == 200
        resume = client.get("/api/resume").json()
        assert resume["project"]["id"] == "math"
        assert resume["checkpoint"]["next_action"] == "Inspect additional proof obligations."
        assert resume["recent_projects"]


def test_tasks_decisions_and_recommendation_review(client: TestClient) -> None:
    task = client.post(
        "/api/tasks",
        json={"project_id": "math", "title": "Check proof obligation", "priority": 1},
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    done = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert done.status_code == 200
    assert done.json()["status"] == "done"

    decision = client.post(
        "/api/decisions",
        json={
            "project_id": "math",
            "title": "Keep physical claim separate",
            "rationale": "Kernel evidence does not establish physical adequacy.",
            "status": "accepted",
        },
    )
    assert decision.status_code == 201
    assert decision.json()["status"] == "accepted"

    # Insert a pending recommendation directly; adapters are tested separately.
    from mission_control.models import Recommendation
    from mission_control.persistence.db import now_iso

    with client.app.state.database.session() as session:
        session.add(
            Recommendation(
                id="rec-test",
                project_id="math",
                title="Review open obligation",
                rationale="Recorded obligation.",
                evidence=["report.json"],
                source_application="math",
                provenance="derived_observation",
                review_state="pending",
                created_at=now_iso(),
                updated_at=now_iso(),
                dedupe_key="rec-test",
            )
        )
    reviewed = client.patch(
        "/api/recommendations/rec-test",
        json={"review_state": "accepted", "note": "Person reviewed the evidence."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_state"] == "accepted"
    decisions = client.get("/api/decisions?project_id=math").json()
    assert any("Recommendation accepted" in item["title"] for item in decisions)
    activity = client.get("/api/activity?project_id=math&limit=100").json()
    assert any(event["type"] == "recommendation_reviewed" for event in activity)
    assert any(event["provenance"] == "user" for event in activity)


def test_user_application_configuration_survives_restart(runtime: RuntimeSettings) -> None:
    with open_client(runtime) as client:
        response = client.patch(
            "/api/applications/next",
            json={"pinned": False, "name": "Next (user name)"},
        )
        assert response.status_code == 200
    with open_client(runtime) as client:
        app = client.get("/api/applications/next").json()
        assert app["pinned"] is False
        assert app["name"] == "Next (user name)"
