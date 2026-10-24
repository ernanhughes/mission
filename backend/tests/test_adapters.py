from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
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
from mission_control.integrations.runner import CommandResult


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


def _next_fixture_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE opportunities (id TEXT PRIMARY KEY, run_id TEXT, title TEXT, description TEXT, "
        "mode TEXT, themes TEXT, sources TEXT, item_ids TEXT, what_discovered TEXT, evidence TEXT, "
        "what_is_new TEXT, capability_unlocked TEXT, relation_to_existing TEXT, combinable_with TEXT, "
        "simplest_experiment TEXT, falsification TEXT, cost_estimate TEXT, why_not TEXT, "
        "capability_gain REAL, feasibility REAL, cost_efficiency REAL, evidence_strength REAL, "
        "novelty REAL, score REAL, uncertainty REAL, evaluation_basis TEXT, rank INTEGER, status TEXT, "
        "decision_reason TEXT, decided_at TEXT, decided_by TEXT, created_at TEXT, queue_type TEXT, "
        "research_status TEXT, overall_confidence REAL)"
    )
    con.execute(
        "INSERT INTO opportunities (id, run_id, title, description, mode, themes, sources, item_ids, "
        "what_discovered, evidence, what_is_new, status, score, evaluation_basis, created_at, queue_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "opp-1",
            "run-1",
            "A research candidate",
            "A candidate description",
            "explore",
            '["research"]',
            '["fixture"]',
            '["item-1"]',
            "A mechanism was discovered.",
            "Source: fixture",
            "The candidate is new.",
            "NEW",
            12.5,
            "provisional",
            "2026-10-20T09:24:20Z",
            "validated",
        ),
    )
    con.execute(
        "CREATE TABLE discovery_runs (id TEXT PRIMARY KEY, started_at TEXT, completed_at TEXT, "
        "status TEXT, items_retrieved INTEGER, items_new INTEGER, candidates INTEGER, "
        "recommendations INTEGER, sources_queried INTEGER, sources_failed INTEGER)"
    )
    con.execute(
        "INSERT INTO discovery_runs VALUES ('run-1','2026-10-20T09:00:00Z','2026-10-20T09:10:00Z',"
        "'completed',10,5,1,1,2,1)"
    )
    con.execute(
        "CREATE TABLE evidence_gaps (opportunity_id TEXT, opportunity_title TEXT, "
        "current_verdict TEXT, gaps_json TEXT, analyzed_at TEXT)"
    )
    con.execute(
        "INSERT INTO evidence_gaps VALUES ('opp-1','A research candidate','insufficient',"
        "'[{\"question\":\"Does it reproduce?\"}]','2026-10-20T09:11:00Z')"
    )
    con.execute(
        "CREATE TABLE experiments (id TEXT, opportunity_id TEXT, hypothesis TEXT, baseline_metric TEXT, "
        "expected_improvement TEXT, actual_result TEXT, status TEXT, cost_usd REAL, created_at TEXT)"
    )
    con.execute(
        "CREATE TABLE decisions (id INTEGER PRIMARY KEY, opportunity_id TEXT, status TEXT, reason TEXT, "
        "decided_by TEXT, decided_at TEXT)"
    )
    con.execute(
        "CREATE TABLE items (id TEXT PRIMARY KEY, title TEXT, url TEXT, source TEXT, published_at TEXT)"
    )
    con.execute(
        "INSERT INTO items VALUES ('item-1','Fixture paper','https://example.invalid/paper','fixture',"
        "'2026-10-20T00:00:00Z')"
    )
    con.commit()
    con.close()


def test_next_adapter_reads_structured_resources_from_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "next"
    repo.mkdir()
    db_path = repo / "next.db"
    _next_fixture_db(db_path)
    target = AdapterTarget(
        name="Next",
        application_id="next",
        repository_paths=[(str(repo), "primary")],
        config={"sqlite_path": str(db_path), "limit": 5, "dsn_env": "MC_TEST_MISSING_DSN"},
    )
    result = asyncio.run(NextAdapter().refresh(target))
    assert result.available is True
    assert result.recommendations == []
    types = {resource.resource_type for resource in result.resources}
    assert {"next_opportunity", "next_run", "next_evidence_gap"} <= types
    opportunity = next(item for item in result.resources if item.resource_type == "next_opportunity")
    assert opportunity.external_id == "opp-1"
    assert opportunity.state == "NEW"
    assert opportunity.data["items"][0]["url"] == "https://example.invalid/paper"
    assert "read-only" in result.detail.lower() or "snapshot" in result.detail.lower()


def test_next_adapter_reports_missing_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "next"
    repo.mkdir()
    target = AdapterTarget(
        name="Next",
        repository_paths=[(str(repo), "primary")],
        config={"sqlite_path": str(tmp_path / "missing.db"), "dsn_env": "MC_TEST_MISSING_DSN"},
    )
    result = asyncio.run(NextAdapter().refresh(target))
    assert result.available is False
    assert result.error
    assert result.resources == []


def test_cocoder_adapter_reads_review_and_findings(tmp_path: Path) -> None:
    artifact = tmp_path / "review.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "base": "HEAD~1",
                "head": "HEAD",
                "changed_files": ["a.py"],
                "evidence": [
                    {
                        "fact_id": "EXC-1",
                        "kind": "exception_boundary_widened",
                        "description": "The handler catches Exception.",
                        "path": "a.py",
                        "symbol": "run",
                    }
                ],
                "findings": [
                    {
                        "finding_id": "F-1",
                        "title": "Removed guard",
                        "statement": "A boundary check was deleted.",
                        "severity": "high",
                        "claim_type": "fact",
                        "confidence": "high",
                        "evidence_ids": ["EXC-1"],
                        "unknowns": ["Why the guard was removed."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    target = AdapterTarget(
        name="CoCoder",
        application_id="cocoder",
        repository_paths=[(str(tmp_path / "cocoder"), "primary")],
        config={"artifact_paths": [str(artifact)]},
        data_dir=str(tmp_path),
    )
    result = asyncio.run(CoCoderAdapter().refresh(target))
    assert result.available is True
    assert {item.resource_type for item in result.resources} == {
        "cocoder_review",
        "cocoder_finding",
    }
    finding = next(item for item in result.resources if item.resource_type == "cocoder_finding")
    assert "Removed guard" in finding.title
    assert finding.data["severity"] == "high"
    assert finding.data["affected_paths"] == ["a.py"]


def test_cocoder_adapter_requires_artifacts_and_validates_action_repo(tmp_path: Path) -> None:
    repo = tmp_path / "cocoder"
    repo.mkdir()
    target = AdapterTarget(
        name="CoCoder",
        repository_paths=[(str(repo), "primary")],
        config={},
        data_dir=str(tmp_path),
    )
    result = asyncio.run(CoCoderAdapter().refresh(target))
    assert result.available is False
    assert "no cocoder review artifact" in result.detail.lower()

    from mission_control.adapters.base import ActionContext

    context = ActionContext(
        application_id="cocoder",
        data_dir=tmp_path,
        allowed_repository_paths=[str(tmp_path)],
    )
    try:
        asyncio.run(
            CoCoderAdapter().execute_action(
                "run_review", {"repo_path": str(tmp_path / "not-allowed")}, context
            )
        )
    except ValueError as exc:
        assert "not a registered repository" in str(exc)
    else:
        raise AssertionError("Unregistered repository was accepted")


def test_cocoder_action_redirects_state_outside_repository(
    tmp_path: Path, monkeypatch
) -> None:
    import mission_control.adapters.cocoder as cocoder_module
    from mission_control.adapters.base import ActionContext

    repo = tmp_path / "repo"
    repo.mkdir()
    data_dir = tmp_path / "mission-data"
    captured: dict = {}

    async def fake_run_tool(executable, arguments, **kwargs):
        captured["arguments"] = arguments
        captured["kwargs"] = kwargs
        output = Path(arguments[arguments.index("--output") + 1])
        output.write_text(
            json.dumps(
                {
                    "schema_version": "0.2",
                    "base": "HEAD~1",
                    "head": "HEAD",
                    "changed_files": [],
                    "findings": [],
                    "evidence": [],
                }
            ),
            encoding="utf-8",
        )
        return CommandResult(
            exit_code=0,
            stdout="wrote artifact",
            stderr="",
            duration_seconds=0.1,
            executable=executable,
        )

    monkeypatch.setattr(cocoder_module, "run_tool", fake_run_tool)
    context = ActionContext(
        application_id="cocoder",
        data_dir=data_dir,
        allowed_repository_paths=[str(repo)],
        application_repository_path=str(repo),
    )
    result = asyncio.run(
        CoCoderAdapter().execute_action("run_review", {"repo_path": str(repo)}, context)
    )
    assert result.status == "succeeded"
    arguments = captured["arguments"]
    config_path = Path(arguments[arguments.index("--config") + 1])
    assert config_path.exists()
    config_text = config_path.read_text(encoding="utf-8")
    assert (data_dir / "integrations" / "cocoder").as_posix() in config_text
    assert not (repo / ".cocoder").exists()
    assert captured["kwargs"]["working_directory"] == str(
        data_dir / "integrations" / "cocoder"
    )


def test_work_adapter_uses_json_cli_contract(tmp_path: Path) -> None:
    executable = sys.executable
    fixture = Path(__file__).parent / "fixtures" / "work_cli_fixture.py"
    target = AdapterTarget(
        name="Work",
        application_id="work",
        repository_paths=[(str(tmp_path / "work"), "primary")],
        config={
            "executable": executable,
            "arguments": [str(fixture)],
            "working_directory": str(tmp_path),
            "env_names": [],
            "limit": 10,
        },
    )
    result = asyncio.run(WorkAdapter().refresh(target))
    assert result.available is True
    assert len(result.resources) == 2
    qualified = next(item for item in result.resources if item.external_id == "work-fixture-1")
    assert qualified.data["qualification"]["qualified"] is True
    assert qualified.data["buyer"] == "Fixture Buyer"
    assert result.recommendations == []


def test_work_adapter_reports_unavailable_cli_without_fabricating(tmp_path: Path) -> None:
    target = AdapterTarget(
        name="Work",
        application_id="work",
        repository_paths=[(str(tmp_path / "work"), "primary")],
        config={"executable": "definitely-not-installed-work-cli"},
    )
    result = asyncio.run(WorkAdapter().refresh(target))
    assert result.available is False
    assert result.resources == []
    assert "no opportunity data" in result.detail.lower()


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
