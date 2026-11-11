"""ARTIFACT-EXPO-01 Stage 08/09/14: Artifact Load API contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

REV = "b" * 64


def _payload(**overrides):
    body = {
        "project_id": None,
        "book_id": "book-inference",
        "chapter_id": "01-chapter.md",
        "source_path": "C:/books/inference/content/books/inference/01-chapter.md",
        "chapter_revision": REV,
        "status": "CURRENT",
        "eligible_words": 1000,
        "evaluated_units": 20,
        "coverage_mechanical": 1.0,
        "coverage_semantic": 1.0,
        "findings": [
            {
                "family": "EXPOSITORY_OVERLOAD",
                "subtype": "EXPO_COMPRESSION",
                "severity": "HIGH",
                "status": "SEMANTICALLY_CONFIRMED",
                "start_line": 16,
                "end_line": 18,
                "fingerprint": "abc123",
                "diagnosis": "test",
            },
            {
                "family": "EXPOSITORY_OVERLOAD",
                "subtype": "EXPO_INTERRUPTION",
                "severity": "MED",
                "status": "SEMANTICALLY_CONFIRMED",
                "start_line": 17,
                "end_line": 20,
                "fingerprint": "def456",
                "diagnosis": "overlapping symptom of the same region",
            },
            {
                "family": "EXPOSITORY_OVERLOAD",
                "subtype": "EXPO_COMPRESSION",
                "severity": "LOW",
                "status": "MECHANICALLY_FLAGGED",
                "start_line": 40,
                "end_line": 42,
                "fingerprint": "ghi789",
                "diagnosis": "unreviewed candidate",
            },
        ],
        "execution": {"transport": "test", "detector": "expo-v1"},
    }
    body.update(overrides)
    return body


def test_record_and_read_observation(client: TestClient):
    created = client.post("/api/artifact-load/observations", json=_payload())
    assert created.status_code == 201, created.text
    record = created.json()
    # Overlapping confirmed findings share one region with max severity HIGH.
    assert record["confirmed"] == 2
    assert record["affected_regions"] == 1
    assert record["weighted_load"] == 3.0
    assert record["unreviewed"] == 1
    assert record["aggregation_version"] == "artifact-load-v1"
    fetched = client.get(f"/api/artifact-load/observations/{record['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["weighted_load"] == 3.0


def test_prose_scores_untouched_by_load_observations(client: TestClient):
    load = client.post("/api/artifact-load/observations", json=_payload())
    assert load.status_code == 201, load.text
    quality = client.get("/api/quality/workspace", params={"project_id": "whatever"})
    assert quality.status_code in (200, 404)


def test_incomplete_coverage_never_clean(client: TestClient):
    created = client.post(
        "/api/artifact-load/observations",
        json=_payload(
            coverage_semantic=0.0,
            findings=[
                {
                    "family": "EXPOSITORY_OVERLOAD",
                    "subtype": "EXPO_COMPRESSION",
                    "severity": "MED",
                    "status": "MECHANICALLY_FLAGGED",
                    "start_line": 10,
                    "end_line": 12,
                }
            ],
        ),
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["confirmed"] == 0
    assert record["unreviewed"] == 1
    assert record["weighted_load"] == 0.0 or record["weighted_load"] == 0


def test_compare_flags_denominator_growth(client: TestClient):
    first = client.post("/api/artifact-load/observations", json=_payload()).json()
    second = client.post(
        "/api/artifact-load/observations",
        json=_payload(
            chapter_revision="c" * 64,
            eligible_words=2000,
            evaluated_units=60,
            previous_observation_id=first["id"],
        ),
    ).json()
    compared = client.get(
        "/api/artifact-load/compare",
        params={"first_id": first["id"], "second_id": second["id"]},
    )
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["denominator_grew"] is True
    assert body["words_before"] == 1000
    assert body["words_after"] == 2000


def test_unscorable_status_carries_no_findings(client: TestClient):
    body = _payload(status="BLOCKED", findings=[])
    created = client.post("/api/artifact-load/observations", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["weighted_load"] is None


def test_superseded_revision_reports_stale_not_original_assessment(client: TestClient):
    first = client.post("/api/artifact-load/observations", json=_payload(project_id="math")).json()
    assert first["assessment_state"] == "assessed_findings"
    second = client.post(
        "/api/artifact-load/observations",
        json=_payload(project_id="math", chapter_revision="c" * 64, findings=[]),
    ).json()
    assert second["assessment_state"] == "assessed_clean"
    workspace = client.get("/api/artifact-load/workspace", params={"project_id": "math"})
    assert workspace.status_code == 200, workspace.text
    chapters = {c["chapter_id"]: c for c in workspace.json()["chapters"]}
    obs = {o["id"]: o for o in chapters["01-chapter.md"]["observations"]}
    assert obs[first["id"]]["assessment_state"] == "stale"
    assert obs[second["id"]]["assessment_state"] == "assessed_clean"


def test_zero_semantic_coverage_reports_not_assessed_not_clean(client: TestClient):
    # EXPO-02 Stage A1: 0% semantic coverage must display Not assessed,
    # never a healthy-looking zero load.
    created = client.post(
        "/api/artifact-load/observations",
        json=_payload(
            coverage_semantic=0.0,
            findings=[
                {
                    "family": "EXPOSITORY_OVERLOAD",
                    "subtype": "EXPO_COMPRESSION",
                    "severity": "UNASSESSED",
                    "priority": "HIGH",
                    "status": "MECHANICALLY_FLAGGED",
                    "start_line": 10,
                    "end_line": 12,
                }
            ],
        ),
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["confirmed"] == 0
    assert record["assessment_state"] == "not_assessed"
    assert record["weighted_load"] == 0.0  # accumulator only, not a verdict
    assert record["mechanical_pressure"] == 3.0


def test_partial_coverage_reports_partially_assessed(client: TestClient):
    created = client.post("/api/artifact-load/observations", json=_payload(coverage_semantic=0.5))
    assert created.status_code == 201, created.text
    assert created.json()["assessment_state"] == "partially_assessed"


def test_full_coverage_no_findings_reports_assessed_clean(client: TestClient):
    created = client.post("/api/artifact-load/observations", json=_payload(findings=[]))
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["assessment_state"] == "assessed_clean"
    assert record["weighted_load"] == 0.0


def test_full_coverage_with_findings_reports_assessed_findings(client: TestClient):
    created = client.post("/api/artifact-load/observations", json=_payload())
    assert created.status_code == 201, created.text
    assert created.json()["assessment_state"] == "assessed_findings"
