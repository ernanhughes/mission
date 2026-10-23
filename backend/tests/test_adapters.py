from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.adapters.base import (
    Adapter,
    AdapterResult,
    AdapterTarget,
    Observation,
    RecommendationSeed,
)
from mission_control.adapters.book_adapters import MathBookAdapter
from mission_control.adapters.cocoder import CoCoderAdapter
from mission_control.adapters.next import NextAdapter
from mission_control.adapters.service import AdapterService
from mission_control.adapters.work import WorkAdapter


def test_math_adapter_reads_evidence_and_derives_obligation_recommendations(tmp_path: Path) -> None:
    repo = tmp_path / "math"
    artifacts = repo / "artifacts" / "math01"
    artifacts.mkdir(parents=True)
    report = {
        "schema_version": "math-investigation-report-v1",
        "generated_at": "2026-10-23T07:34:47Z",
        "assessments": [
            {
                "claim_id": "claim-alpha",
                "overall_status": "formally_verified",
                "rationale": "Kernel accepted the claim.",
                "unresolved_obligations": ["Compose the bridge with the theorem."],
            }
        ],
        "capabilities": [{"system": "lean4", "available": True}],
    }
    (artifacts / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (repo / "book").mkdir()
    (repo / "book" / "outline.md").write_text("# Outline", encoding="utf-8")
    target = AdapterTarget(
        name="Math",
        project_id="math",
        repository_paths=[(str(repo), "manuscript")],
    )
    result = asyncio.run(MathBookAdapter().refresh(target))
    assert result.available is True
    assert any("claim-alpha" in item.title for item in result.observations)
    assert len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert "Compose the bridge" in recommendation.title
    assert recommendation.provenance == "derived_observation"
    assert recommendation.project_id == "math"
    assert any("report.json" in reference for reference in recommendation.evidence)


def test_math_adapter_rejects_malformed_report_without_raising(tmp_path: Path) -> None:
    repo = tmp_path / "math"
    (repo / "artifacts" / "math01").mkdir(parents=True)
    (repo / "artifacts" / "math01" / "report.json").write_text("{not-json", encoding="utf-8")
    target = AdapterTarget(name="Math", project_id="math", repository_paths=[(str(repo), "manuscript")])
    result = asyncio.run(MathBookAdapter().refresh(target))
    assert result.available is False
    assert result.error


def test_next_adapter_reads_local_snapshot_without_creating_recommendations(tmp_path: Path) -> None:
    repo = tmp_path / "next"
    data = repo / "data"
    data.mkdir(parents=True)
    db_path = data / "next.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE opportunities (id TEXT, title TEXT, status TEXT, queue_type TEXT, "
        "score REAL, created_at TEXT, evaluation_basis TEXT, evidence TEXT)"
    )
    con.execute(
        "INSERT INTO opportunities VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "opp-1",
            "A research candidate",
            "NEW",
            "validated",
            12.5,
            "2026-10-20T09:24:20Z",
            "provisional",
            "Source: example",
        ),
    )
    con.commit()
    con.close()
    target = AdapterTarget(
        name="Next",
        application_id="next",
        repository_paths=[(str(repo), "primary")],
        config={"database_path": str(db_path), "limit": 5},
    )
    result = asyncio.run(NextAdapter().refresh(target))
    assert result.available is True
    assert len(result.observations) == 1
    assert result.observations[0].provenance == "external_claim"
    assert result.recommendations == []
    assert "local SQLite snapshot" in result.detail


def test_next_adapter_reports_unsafe_or_missing_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "next"
    repo.mkdir()
    outside = tmp_path / "elsewhere.db"
    sqlite3.connect(outside).close()
    target = AdapterTarget(
        name="Next",
        repository_paths=[(str(repo), "primary")],
        config={"database_path": str(outside)},
    )
    result = asyncio.run(NextAdapter().refresh(target))
    assert result.available is False
    assert "inside the Next repository" in result.detail


def test_cocoder_adapter_reads_review_and_surfaces_high_findings(tmp_path: Path) -> None:
    repo = tmp_path / "cocoder"
    repo.mkdir()
    artifact = repo / "review.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "changed_files": ["a.py"],
                "findings": [
                    {
                        "finding_id": "F-1",
                        "title": "Removed guard",
                        "statement": "A boundary check was deleted.",
                        "severity": "high",
                        "claim_type": "fact",
                        "confidence": "high",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    target = AdapterTarget(
        name="CoCoder",
        application_id="cocoder",
        repository_paths=[(str(repo), "primary")],
        config={"review_json_path": str(artifact)},
    )
    result = asyncio.run(CoCoderAdapter().refresh(target))
    assert result.available is True
    assert any("Removed guard" in item.title for item in result.observations)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].provenance == "derived_observation"


def test_cocoder_adapter_requires_configuration(tmp_path: Path) -> None:
    repo = tmp_path / "cocoder"
    repo.mkdir()
    target = AdapterTarget(name="CoCoder", repository_paths=[(str(repo), "primary")], config={})
    result = asyncio.run(CoCoderAdapter().refresh(target))
    assert result.available is False
    assert "no review artifact" in result.detail.lower()


def test_work_adapter_does_not_fabricate_opportunities(tmp_path: Path) -> None:
    result = asyncio.run(WorkAdapter().refresh(AdapterTarget(name="Work", repository_paths=[])))
    assert result.available is False
    assert result.observations == []
    assert "no verified read-only export" in result.detail.lower() or "not present" in result.detail.lower()


class ExplodingAdapter(Adapter):
    name = "exploding"
    capabilities = ["failure"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        raise RuntimeError("detonated")


def test_adapter_failure_is_isolated(client: TestClient) -> None:
    service = AdapterService(client.app.state.database)
    target = AdapterTarget(name="Math", project_id="math", repository_paths=[])
    result = asyncio.run(service._execute("exploding", ExplodingAdapter(), target, {}))
    assert result.available is False
    assert "failed" in result.detail.lower()
    # The API itself is unaffected.
    assert client.get("/api/health").status_code == 200
    statuses = client.get("/api/adapters").json()
    assert any(status["adapter"] == "math" for status in statuses)


def test_adapter_ingestion_deduplicates_observations_and_recommendations(client: TestClient) -> None:
    service = AdapterService(client.app.state.database)
    result = AdapterResult(
        available=True,
        detail="fixture",
        observations=[
            Observation(
                title="Observed fact",
                detail="One bounded observation.",
                external_id="fact-1",
                provenance="verified_observation",
            )
        ],
        recommendations=[
            RecommendationSeed(
                title="Review fact",
                rationale="Derived from the observed fact.",
                external_id="rec-seed-1",
                project_id="math",
                provenance="derived_observation",
            )
        ],
    )
    with client.app.state.database.session() as session:
        service._ingest(session, "fixture", None, "math", result)
        service._ingest(session, "fixture", None, "math", result)
    with client.app.state.database.session() as session:
        from sqlalchemy import func, select

        from mission_control.models import ActivityEvent, Recommendation

        recommendation_count = session.scalar(
            select(func.count()).select_from(Recommendation).where(
                Recommendation.external_id == "rec-seed-1"
            )
        )
        observation_count = session.scalar(
            select(func.count()).select_from(ActivityEvent).where(
                ActivityEvent.source_id == "fact-1"
            )
        )
    assert recommendation_count == 1
    assert observation_count == 1
