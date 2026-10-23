from __future__ import annotations


from fastapi.testclient import TestClient

from helpers import open_client
from mission_control.config import RuntimeSettings


def test_briefing_is_grounded_and_ai_offline_does_not_break_it(client: TestClient) -> None:
    checkpoint = client.post(
        "/api/checkpoints",
        json={
            "project_id": "math",
            "summary": "Reviewed the Lorentz report.",
            "next_action": "Inspect additional proof obligations.",
            "last_completed": "Read report.json",
            "blockers": "",
            "milestone": "MATH01-R1",
            "evidence_refs": ["artifacts/math01/report.json"],
        },
    )
    assert checkpoint.status_code == 201
    task = client.post(
        "/api/tasks", json={"project_id": "math", "title": "Check the open proof obligation"}
    )
    assert task.status_code == 201

    response = client.post("/api/briefing/generate", json={"use_ai": False})
    assert response.status_code == 200, response.text
    briefing = response.json()
    assert briefing["mode"] == "deterministic"
    assert briefing["status"] == "complete"
    items = briefing["items"]
    assert items
    math_items = [item for item in items if item["project_id"] == "math"]
    assert any(item["provenance"] == "recorded_checkpoint" for item in math_items)
    assert any(item["provenance"] == "user_task" for item in math_items)
    assert "Reviewed the Lorentz report." in briefing["content"]
    # AI is not consulted without configuration.
    assert "AI interpretation" not in briefing["content"]

    # Explicitly request AI with no configured provider: deterministic fallback.
    offline = client.post("/api/briefing/generate", json={"use_ai": True})
    assert offline.status_code == 200
    fallback = offline.json()
    assert fallback["mode"] == "deterministic"
    assert fallback["status"] in {"ai_not_configured", "ai_unavailable"}
    assert fallback["items"]
    assert "AI interpretation unavailable" in fallback["content"] or fallback["error"]


def test_activity_filters_notes_and_project_scope(client: TestClient) -> None:
    note = client.post(
        "/api/activity/notes",
        json={
            "project_id": "math",
            "title": "Note on verification",
            "detail": "Physical claim remains separate.",
            "evidence_ref": "artifacts/math01/report.json",
        },
    )
    assert note.status_code == 201
    assert note.json()["provenance"] == "user"

    activity = client.get("/api/activity?project_id=math&type=user_note").json()
    assert len(activity) == 1
    assert activity[0]["title"] == "Note on verification"
    other = client.get("/api/activity?project_id=language&type=user_note").json()
    assert not other
    since = client.get("/api/activity?since=2030-01-01T00:00:00%2B00:00").json()
    assert not since


def test_resume_uses_persisted_focus_and_checkpoint(runtime: RuntimeSettings) -> None:
    with open_client(runtime) as client:
        client.post(
            "/api/checkpoints",
            json={
                "project_id": "math",
                "summary": "Stopped at the proof obligation review.",
                "next_action": "Continue the obligation review.",
                "last_completed": "Validated MATH01 output.",
                "blockers": "Cross-kernel equivalence remains open.",
                "milestone": "MATH01-R1",
                "evidence_refs": ["artifacts/math01/report.json"],
            },
        )
        client.post("/api/projects/inference/focus")

    with open_client(runtime) as client:
        resume = client.get("/api/resume").json()
        assert resume["project"]["id"] == "inference"
        # The checkpoint itself remains on Math and is recoverable.
        math = client.get("/api/projects/math").json()
        assert math["latest_checkpoint"]["summary"] == "Stopped at the proof obligation review."
        assert math["latest_checkpoint"]["next_action"] == "Continue the obligation review."
        client.post("/api/projects/math/focus")
        resumed = client.get("/api/resume").json()
        assert resumed["project"]["id"] == "math"
        assert resumed["checkpoint"]["blockers"] == "Cross-kernel equivalence remains open."
