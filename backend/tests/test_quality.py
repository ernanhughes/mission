"""MC-QUALITY-02: quality evaluation history contracts and API."""

from __future__ import annotations

from fastapi.testclient import TestClient

REV = "a" * 64
DIM_NAMES = ["clarity", "argument", "precision", "economy", "voice", "structure"]


def _dims(**overrides):
    base = {"clarity": 4, "argument": 4, "precision": 5, "economy": 3, "voice": 4, "structure": 4}
    base.update(overrides)
    return {
        name: {"dimension": name, "score": score, "evidence": "e", "evidence_validated": False}
        for name, score in base.items()
    }


def _payload(**overrides):
    body = {
        "project_id": "inference",
        "book_id": "book-inference",
        "chapter_id": "01-chapter.md",
        "source_path": "C:/books/inference/content/books/inference/01-chapter.md",
        "chapter_revision": REV,
        "status": "CURRENT",
        "overall": 4.0,
        "dimensions": _dims(),
        "execution": {"actual_model": "m", "status": "succeeded", "token_usage": "unknown"},
    }
    body.update(overrides)
    return body


def test_record_and_read_evaluation(client: TestClient):
    created = client.post("/api/quality/evaluations", json=_payload())
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["derived_state"] in ("current", "CURRENT")
    fetched = client.get(f"/api/quality/evaluations/{record['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["overall"] == 4.0


def test_unknown_project_rejected(client: TestClient):
    response = client.post("/api/quality/evaluations", json=_payload(project_id="nope"))
    assert response.status_code in (400, 404, 422)


def test_seventh_dimension_rejected(client: TestClient):
    dims = _dims()
    dims["novelty"] = {"dimension": "novelty", "score": 5, "evidence": "e", "evidence_validated": False}
    response = client.post("/api/quality/evaluations", json=_payload(dimensions=dims))
    assert response.status_code == 422


def test_out_of_range_score_rejected(client: TestClient):
    response = client.post("/api/quality/evaluations", json=_payload(dimensions=_dims(precision=6), overall=4.17))
    assert response.status_code == 422


def test_hand_set_overall_rejected(client: TestClient):
    response = client.post("/api/quality/evaluations", json=_payload(overall=5.0))
    assert response.status_code == 422


def test_unknown_status_rejected(client: TestClient):
    response = client.post("/api/quality/evaluations", json=_payload(status="SCORED"))
    assert response.status_code == 422


def test_blocked_without_scores_accepted(client: TestClient):
    body = _payload(status="BLOCKED", overall=None, dimensions={})
    created = client.post("/api/quality/evaluations", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["overall"] is None


def test_blocked_with_scores_rejected(client: TestClient):
    body = _payload(status="BLOCKED")
    response = client.post("/api/quality/evaluations", json=body)
    assert response.status_code == 422


def test_history_preserved_and_compared(client: TestClient):
    first = client.post("/api/quality/evaluations", json=_payload()).json()
    second = client.post(
        "/api/quality/evaluations",
        json=_payload(dimensions=_dims(economy=4), overall=4.17, previous_evaluation_id=first["id"]),
    ).json()
    assert second["previous_evaluation_id"] == first["id"]
    compared = client.get(
        f"/api/quality/compare?first_id={first['id']}&second_id={second['id']}"
    ).json()
    assert compared["per_dimension_difference"]["economy"] == 1
    assert compared["mean_absolute_difference"] == 0.17
    assert compared["max_variation"] == 1
    assert compared["overall_range"] == 0.17
    assert "same-revision" in compared["compatible_basis"]


def test_incompatible_rubric_flagged(client: TestClient):
    first = client.post("/api/quality/evaluations", json=_payload()).json()
    other = _payload(rubric_id="other-rubric", rubric_version=9)
    second = client.post("/api/quality/evaluations", json=other).json()
    compared = client.get(
        f"/api/quality/compare?first_id={first['id']}&second_id={second['id']}"
    ).json()
    assert "incompatible" in compared["compatible_basis"]


def test_compare_with_unscored_terminal_state(client: TestClient):
    scored = client.post("/api/quality/evaluations", json=_payload()).json()
    blocked = client.post(
        "/api/quality/evaluations", json=_payload(status="BLOCKED", overall=None, dimensions={})
    ).json()
    compared = client.get(
        f"/api/quality/compare?first_id={scored['id']}&second_id={blocked['id']}"
    ).json()
    assert compared["overall_range"] is None
    assert compared["per_dimension_difference"] == {}


def test_workspace_groups_and_states(client: TestClient):
    client.post("/api/quality/evaluations", json=_payload()).json()
    workspace = client.get("/api/quality/workspace?project_id=inference").json()
    assert workspace["project_id"] == "inference"
    assert workspace["chapters_evaluated"] >= 1
    assert workspace["chapters_current"] >= 1
    chapter = next(c for c in workspace["chapters"] if c["chapter_id"] == "01-chapter.md")
    assert chapter["current"] is not None
    assert chapter["current"]["overall"] == 4.0
    assert any("coverage is explicit" in limitation for limitation in workspace["limitations"])
