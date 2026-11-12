"""Strategy-evolution summary (read-only) + experiment action contracts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mission_control.adapters.base import ActionContext
from mission_control.adapters.writer import WriterAdapter
from mission_control.integrations.runner import CommandResult
from mission_control.writer.evolution_summary import summarize_strategy_evolution


def _version(path: Path, *, version: str = "v1", status: str = "ACTIVE_VERSION") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "strategy_id": "explanation_reorder", "version": version, "status": status,
        "content_hash": "sth-x", "prompt_overrides": []}), encoding="utf-8")


def _proposal(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "proposal_id": "prop-1", "baseline_strategy": "s",
        "baseline_version": "v1", "candidate_version": "v2"}), encoding="utf-8")


def _experiment(path: Path, *, status: str = "COMPLETE") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "experiment_id": "exp-1", "status": status,
        "baseline_strategy": "s", "baseline_version": "v1",
        "candidate_strategy": "s", "candidate_version": "v2",
        "verification_policy": "g"}), encoding="utf-8")


def _report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "experiment_id": "exp-1", "overall_verdict": "INCONCLUSIVE",
        "aggregate": {"cases": 2, "by_verdict": {"NO_MEANINGFUL_DIFFERENCE": 2},
                      "safety_regressions": 0}}), encoding="utf-8")


def test_empty_book_root_is_unavailable(tmp_path: Path) -> None:
    summary = summarize_strategy_evolution(tmp_path / "books")
    assert summary["available"] is False
    assert summary["totals"]["versions"] == 0


def test_counts_versions_experiments_and_decisions(tmp_path: Path) -> None:
    evo = tmp_path / "books" / "inference" / ".writer" / "strategy-evolution"
    (evo / "strategies").mkdir(parents=True)
    (evo / "proposals").mkdir(parents=True)
    (evo / "experiments").mkdir(parents=True)
    (evo / "reports").mkdir(parents=True)
    (evo / "decisions").mkdir(parents=True)
    _version(evo / "strategies" / "s--v1.json")
    _version(evo / "strategies" / "s--v2.json", version="v2", status="EXPERIMENTAL")
    _proposal(evo / "proposals" / "prop-1.json")
    (evo / "proposals" / "prop-1--validation.json").write_text("{}", encoding="utf-8")
    _experiment(evo / "experiments" / "exp-1.json")
    (evo / "decisions" / "dec-1.json").write_text(json.dumps({
        "decision_id": "dec-1", "decision": "NEEDS_MORE_EVIDENCE"}), encoding="utf-8")
    _report(evo / "reports" / "rep-exp-1.json")
    (evo / "reports" / "bad.json").write_text("{not json", encoding="utf-8")
    summary = summarize_strategy_evolution(tmp_path / "books")
    assert summary["available"] is True
    assert summary["totals"]["versions"] == 2
    assert summary["totals"]["experiments"] == 1
    assert summary["totals"]["proposals"] == 1  # validation sidecar excluded
    assert summary["totals"]["decisions"] == 1
    assert summary["totals"]["paired_cases"] == 2
    assert summary["unreadable_files"] == 1
    assert any(v["status"] == "EXPERIMENTAL" for v in summary["versions"])
    assert "no composite" in " ".join(summary["limitations"]).lower()


def test_evolution_endpoints_are_read_only(client) -> None:
    response = client.get("/api/writer/evolution")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] in (True, False)
    assert "versions" in body and "experiments" in body and "decisions" in body


def test_workspace_carries_evolution(client) -> None:
    body = client.get("/api/writer/books").json()
    assert "strategy_evolution" in body
    assert "totals" in body["strategy_evolution"]


def _ctx(tmp_path: Path) -> ActionContext:
    return ActionContext(
        application_id="writer",
        data_dir=tmp_path,
        application_repository_path=str(tmp_path / "writer"),
        config={"executable": "C:/writer/venv/Scripts/writer.exe"},
    )


def test_experiment_action_validates_and_shells_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "writer").mkdir()
    import mission_control.adapters.writer as writer_adapter

    seen: dict = {}

    async def fake_run_tool(executable, arguments, **kwargs):
        seen["arguments"] = arguments
        return CommandResult(
            exit_code=0,
            stdout=json.dumps({"ok": True, "result": {"arm": "baseline", "results": []}}),
            stderr="",
            duration_seconds=0.1,
            executable=executable,
        )

    monkeypatch.setattr(writer_adapter, "run_tool", fake_run_tool)
    adapter = WriterAdapter()
    context = _ctx(tmp_path)
    adapter.validate_action("book_strategy_experiment_run",
                            {"experiment_id": "exp-1", "arm": "baseline",
                             "book_root": "C:/books/inference"}, context)
    with pytest.raises(ValueError, match="arm"):
        adapter.validate_action("book_strategy_experiment_run",
                                {"experiment_id": "exp-1", "arm": "bogus",
                                 "book_root": "C:/books/inference"}, context)
    result = asyncio.run(adapter.execute_action(
        "book_strategy_experiment_run",
        {"experiment_id": "exp-1", "arm": "baseline", "book_root": "C:/books/inference",
         "max_wall_seconds": 60},
        context,
    ))
    assert result.status == "succeeded"
    assert seen["arguments"][:2] == ["strategy-evolution", "run-experiment"]
    assert "--arm" in seen["arguments"]


def test_experiment_run_route_validates_arm(client) -> None:
    response = client.post("/api/writer/evolution/experiments/run",
                           json={"experiment_id": "exp-1", "arm": "bogus",
                                 "book_root": "C:/books/inference"})
    assert response.status_code == 422, response.text
