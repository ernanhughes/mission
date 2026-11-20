"""MC-PRAXIS-10: governed single-book Writer audit ActionSpec."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mission_control.adapters.base import ActionContext
from mission_control.adapters.writer import WriterAdapter
from mission_control.integrations.runner import CommandResult


def _envelope(findings: list[dict], partial: bool = False) -> str:
    return json.dumps({
        "ok": True, "command": "editing audit", "project_id": "distillation",
        "exit_code": 0,
        "result": {
            "schema_version": "writer-editing-report-v1",
            "book": {"project_id": "distillation", "title": "distillation"},
            "report_id": "edit-test-1",
            "partial": partial,
            "findings": findings,
            "limitations": ["Audit is read-only."],
            "generated_at": "2026-11-20T00:00:00Z",
        },
        "artifacts": ["C:\\Projects\\writer\\.writer\\editing\\edit-test-1.json"],
        "meta": {"schema_version": "writer.editing.cli.v1"},
    })


def _context() -> ActionContext:
    return ActionContext(
        application_id="writer",
        data_dir=Path("C:/Projects/mission/data"),
        application_repository_path="C:/Projects/writer",
        config={"executable": "C:/Projects/writer/venv/Scripts/writer.exe",
                "working_directory": "C:/Projects/writer",
                "env_names": ["WRITER_PROJECTS_CONFIG"],
                "timeout_seconds": 180},
    )


def test_scoped_audit_action_is_exposed(client: TestClient) -> None:
    response = client.get("/api/integrations/writer")
    assert response.status_code == 200
    actions = {a["id"]: a for a in response.json()["actions"]}
    assert "audit_registered_book" in actions
    spec = actions["audit_registered_book"]
    assert spec["approval_required"] is True
    assert spec["enabled"] is True
    assert spec["side_effect"] == "local_generated_artifacts"
    assert spec["parameters_schema"]["required"] == ["book_id"]


def test_scoped_audit_parses_typed_report(monkeypatch) -> None:
    calls: dict = {}

    async def fake_run_tool(executable, arguments, *, working_directory,
                            env_names=None, timeout_seconds=60.0):
        calls["arguments"] = arguments
        return CommandResult(
            exit_code=0,
            stdout=_envelope([{"severity": "high"}, {"severity": "low"},
                              {"severity": "high"}]),
            stderr="", duration_seconds=5.9, executable=executable)

    monkeypatch.setattr("mission_control.adapters.writer.run_tool", fake_run_tool)
    result = asyncio.run(WriterAdapter().execute_action(
        "audit_registered_book", {"book_id": "distillation"}, _context()))
    assert result.status == "succeeded"
    assert calls["arguments"] == ["editing", "audit", "distillation",
                                  "--profile", "technical-nonfiction-v1", "--json"]
    assert result.result["book_id"] == "distillation"
    assert result.result["report_id"] == "edit-test-1"
    assert result.result["finding_counts"] == {"high": 2, "low": 1}
    assert result.result["partial"] is False
    assert result.artifact_ref.endswith("edit-test-1.json")


def test_scoped_audit_rejects_bad_identifiers() -> None:
    adapter = WriterAdapter()
    for bad in ("", "../etc", "C:\\books\\x", "UPPER", "a" * 200):
        with pytest.raises(ValueError):
            adapter.validate_action("audit_registered_book",
                                    {"book_id": bad}, _context())
    adapter.validate_action("audit_registered_book",
                            {"book_id": "distillation"}, _context())


def test_scoped_audit_failure_is_typed(monkeypatch) -> None:
    async def fake_run_tool(*args, **kwargs):
        return CommandResult(exit_code=1, stdout="boom", stderr="registry error",
                             duration_seconds=1.0, executable="writer")

    monkeypatch.setattr("mission_control.adapters.writer.run_tool", fake_run_tool)
    result = asyncio.run(WriterAdapter().execute_action(
        "audit_registered_book", {"book_id": "distillation"}, _context()))
    assert result.status == "failed"
    assert "registry error" in (result.error or "")


def test_execution_rejects_unregistered_book_before_running(client: TestClient) -> None:
    response = client.post(
        "/api/integrations/writer/actions/audit_registered_book/execute",
        json={"parameters": {"book_id": "not-a-registered-book"}, "confirm": True})
    assert response.status_code == 422
    assert "not a registered Writer book" in response.text


def test_proposal_validation_resolves_scoped_book(client: TestClient) -> None:
    from mission_control.models import IntegrationRecord
    from mission_control.persistence.db import now_iso

    with client.app.state.database.session() as session:  # type: ignore[union-attr]
        session.add(IntegrationRecord(
            id="res-scoped-book", application_id="writer",
            resource_type="writer_editing_book", external_id="distillation",
            title="distillation", summary="", state="NEEDS_REVIEW",
            evidence=[], data={"project_root": "C:\\books\\distillation"},
            source_version="writer-editing-summary-v1",
            observed_at=now_iso(), created_at=now_iso()))

    body = {
        "schema_version": "mc-praxis-proposal-v1",
        "proposal": {
            "id": "prop-scoped-audit", "version": "1", "status": "validated",
            "goal": {"goal_id": "res-1", "title": "scoped audit",
                     "source": "next_opportunity", "provenance": {},
                     "stale": None},
            "steps": [{"capability_id": "writer.audit_registered_book",
                       "parameters": {"book_id": "distillation"},
                       "rationale": "audit one book"}],
            "capability_versions": {"writer.audit_registered_book": "mc09.1"},
            "pi_model": "test", "protocol": "praxis-compose-v2",
            "evidence_refs": [], "expected_benefits": [], "risks": [],
            "assumptions": [], "estimated_cost": {},
            "observed_composition_cost_usd": None,
            "correlation": {"run_id": "scoped"},
        },
        "acceptance_criteria": [{"id": "ac", "statement": "report produced",
                                 "source": "human:ernan"}],
        "acceptance_provenance": "test",
    }
    response = client.post("/api/praxis/proposals", json=body)
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["status"] == "awaiting_approval"
    checks = {item["check"]: item["ok"] for item in row["validation"]}
    assert checks["book_registered"] is True
    assert checks["book_root_known"] is True
    assert any(f["id"].endswith("book_resolved") for f in row["preflight"])
