"""LIVING-WORK-BOOKS-01 W2: Writer evaluation ingestion + chapter read-model.

Uses real W1 pilot envelopes (fixtures/writer_envelopes/*.json) produced by
Writer-owned code against the Inference snapshot. No scores invented, no
prose/technical/publication state touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mission_control.models import IntegrationRecord, QualityEvaluation

FIXTURES = Path(__file__).parent / "fixtures" / "writer_envelopes"

pytestmark = pytest.mark.fast


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _quality_row_count(client: TestClient) -> int:
    with client.app.state.database.session() as session:
        return session.scalar(select(func.count()).select_from(QualityEvaluation))


def test_ingest_qc_and_artifact_for_chapter_39(client: TestClient) -> None:
    before = _quality_row_count(client)
    qc = _load("qc-39-chapter.json")
    art = _load("artifact-39-chapter.json")
    for envelope in (qc, art):
        response = client.post(
            "/api/writer/evaluations/ingest",
            json={"project_id": "inference", "envelope": envelope},
        )
        assert response.status_code == 200, response.text
        assert response.json()["created"] is True
    # Gate D: existing prose/quality state untouched by Writer ingest.
    assert _quality_row_count(client) == before


def test_chapter_39_current_with_matching_hash(client: TestClient) -> None:
    qc = _load("qc-39-chapter.json")
    art = _load("artifact-39-chapter.json")
    for envelope in (qc, art):
        client.post(
            "/api/writer/evaluations/ingest",
            json={"project_id": "inference", "envelope": envelope},
        )
    source_hash = qc["work_object"]["source_hash"]
    response = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter",
            "source_hash": source_hash,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall"] == "CURRENT"
    assert len(body["evaluations"]) == 2
    providers = {item["envelope"]["producer"]["runtime_name"] for item in body["evaluations"]}
    assert providers == {"artifact", "qc"}

    # Native scales preserved, no composite invented: no score-averaging
    # keys anywhere in the stored envelope.
    def _keys(node: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(node, dict):
            for key, value in node.items():
                found.add(key)
                found |= _keys(value)
        elif isinstance(node, list):
            for value in node:
                found |= _keys(value)
        return found

    forbidden = {"composite_score", "overall_score", "quality_score", "verdict_score"}
    for item in body["evaluations"]:
        assert not (forbidden & _keys(item["envelope"]))


def test_chapter_01_artifact_independent_evidence(client: TestClient) -> None:
    art = _load("artifact-01-chapter.json")
    response = client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    )
    assert response.status_code == 200
    body = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "01-chapter",
            "source_hash": art["work_object"]["source_hash"],
        },
    ).json()
    assert body["overall"] == "CURRENT"
    assert len(body["evaluations"]) == 1
    assert body["evaluations"][0]["envelope"]["producer"]["runtime_name"] == "artifact"


def test_replay_same_id_creates_nothing(client: TestClient) -> None:
    art = _load("artifact-39-chapter.json")
    first = client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    ).json()
    second = client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    ).json()
    assert first["created"] is True
    assert second["created"] is False
    assert first["record_id"] == second["record_id"]
    with client.app.state.database.session() as session:
        count = session.scalar(
            select(func.count())
            .select_from(IntegrationRecord)
            .where(
                IntegrationRecord.application_id == "writer",
                IntegrationRecord.resource_type == "writer_evaluation",
                IntegrationRecord.external_id == art["evaluation_id"],
            )
        )
    assert count == 1


def test_new_evaluation_supersedes_preserves_history(client: TestClient) -> None:
    art = _load("artifact-39-chapter.json")
    client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    )
    changed = dict(art)
    changed["evaluation_id"] = art["evaluation_id"] + "-rerun"
    changed["provenance"] = {**art["provenance"], "operation_id": "op-rerun"}
    response = client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": changed},
    )
    assert response.json()["created"] is True
    body = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter",
            "source_hash": art["work_object"]["source_hash"],
        },
    ).json()
    assert len(body["evaluations"]) == 2
    current = [item for item in body["evaluations"] if item["current"]]
    historical = [item for item in body["evaluations"] if not item["current"]]
    assert len(current) == 1 and len(historical) == 1
    assert historical[0]["evaluation_id"] == art["evaluation_id"]
    # QC evidence (other provider) unaffected by artifact supersession.
    qc = _load("qc-39-chapter.json")
    client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": qc},
    )
    body = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter",
            "source_hash": art["work_object"]["source_hash"],
        },
    ).json()
    assert len(body["evaluations"]) == 3


def test_changed_source_marks_stale(client: TestClient) -> None:
    art = _load("artifact-39-chapter.json")
    client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    )
    body = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter",
            "source_hash": "0" * 64,
        },
    ).json()
    assert body["overall"] == "STALE"
    assert body["evaluations"][0]["derived"] == "STALE"


def test_unknown_chapter_is_not_run(client: TestClient) -> None:
    body = client.get(
        "/api/writer/evaluations/chapter",
        params={"project_id": "inference", "chapter_id": "99-chapter"},
    ).json()
    assert body["overall"] == "NOT_RUN"
    assert body["evaluations"] == []


def test_unavailable_provider_preserved(client: TestClient) -> None:
    envelope = {
        "schema_version": "writer.evaluation-envelope.v1",
        "evaluation_id": "qc-eval-unavailable-1",
        "observed_at": "2026-11-22T12:00:00+00:00",
        "work_object": {
            "kind": "chapter",
            "target_id": "39-chapter",
            "source_hash": "a" * 64,
        },
        "producer": {"runtime_name": "qc", "method": "none"},
        "rubric": {},
        "status": "unavailable",
        "dimensions": [],
        "findings": [],
        "coverage": None,
        "limitations": ["store unreachable"],
        "provenance": {},
    }
    response = client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": envelope},
    )
    assert response.status_code == 200
    body = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter",
            "source_hash": "a" * 64,
        },
    ).json()
    assert body["overall"] == "UNAVAILABLE"


def test_invalid_envelopes_rejected(client: TestClient) -> None:
    bad_schema = dict(_load("artifact-39-chapter.json"), schema_version="v0")
    assert (
        client.post(
            "/api/writer/evaluations/ingest",
            json={"project_id": "inference", "envelope": bad_schema},
        ).status_code
        == 422
    )
    unknown_provider = dict(_load("artifact-39-chapter.json"))
    unknown_provider["producer"] = {"runtime_name": "scoring", "method": "x"}
    assert (
        client.post(
            "/api/writer/evaluations/ingest",
            json={"project_id": "inference", "envelope": unknown_provider},
        ).status_code
        == 422
    )
    not_object = {"project_id": "inference", "envelope": [1, 2, 3]}
    assert client.post("/api/writer/evaluations/ingest", json=not_object).status_code == 422


def test_findings_keep_native_family_no_tech_verdict(client: TestClient) -> None:
    qc = _load("qc-39-chapter.json")
    client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": qc},
    )
    body = client.get(
        "/api/writer/evaluations/evaluation_id-missing",
    )
    assert body.status_code == 404
    record = client.get(
        f"/api/writer/evaluations/{qc['evaluation_id']}",
    ).json()
    envelope = record["envelope"]
    assert envelope["evaluation_id"] == qc["evaluation_id"]
    assert {finding["family"] for finding in envelope["findings"]} == {"qc"}
    # No technical-verification claim is manufactured from QC findings.
    assert "VERIFIED" not in json.dumps(envelope["findings"])


def test_adapter_refresh_does_not_demote_evaluations(client: TestClient) -> None:
    """W3-found regression: a writer adapter refresh (other resource types)
    must not mark current evaluations historical."""
    from mission_control.adapters.base import ResourceSeed
    from mission_control.integrations.store import upsert_resources
    from mission_control.models import IntegrationRecord

    art = _load("artifact-39-chapter.json")
    client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    )
    with client.app.state.database.session() as session:
        upsert_resources(
            session,
            "writer",
            [
                ResourceSeed(
                    resource_type="writer_editing_book",
                    external_id="inference",
                    title="Inference",
                    summary="summary",
                    state="CURRENT",
                    data={},
                )
            ],
        )
        session.commit()
        rows = session.scalars(
            select(IntegrationRecord).where(
                IntegrationRecord.application_id == "writer",
                IntegrationRecord.resource_type == "writer_evaluation",
                IntegrationRecord.current.is_(True),
            )
        ).all()
    assert len(rows) == 1
    assert rows[0].external_id == art["evaluation_id"]


def test_chapter_id_filename_form_matches_stem(client: TestClient) -> None:
    """W3 closure: stem and filename chapter ids resolve identically."""
    art = _load("artifact-39-chapter.json")
    client.post(
        "/api/writer/evaluations/ingest",
        json={"project_id": "inference", "envelope": art},
    )
    stem = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter",
            "source_hash": art["work_object"]["source_hash"],
        },
    ).json()
    dotted = client.get(
        "/api/writer/evaluations/chapter",
        params={
            "project_id": "inference",
            "chapter_id": "39-chapter.md",
            "source_hash": art["work_object"]["source_hash"],
        },
    ).json()
    assert stem["overall"] == "CURRENT"
    assert dotted["overall"] == "CURRENT"
    assert [e["evaluation_id"] for e in stem["evaluations"]] == [
        e["evaluation_id"] for e in dotted["evaluations"]
    ]
