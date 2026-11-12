"""Book campaign summary (read-only) + adapter action contracts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mission_control.adapters.base import ActionContext, AdapterTarget
from mission_control.adapters.writer import WriterAdapter
from mission_control.integrations.runner import CommandResult
from mission_control.writer.campaign_summary import summarize_campaigns


def _campaign(path: Path, *, state: str = "READY", chapters: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "campaign_id": path.stem, "mode": "PLAN", "state": state,
        "chapters": [f"{i:02d}-chapter.md" for i in range(1, chapters + 1)],
    }), encoding="utf-8")


def _report(path: Path, *, status: str = "COMPLETE", outcomes: dict | None = None,
            untouched: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "report_id": path.stem, "run_id": "run-1", "status": status,
        "outcome_counts": outcomes or {"VERIFICATION_SUPPORTED": 1},
        "chapters_done": 1, "candidates_made": 1,
        "chapter_work": {"01-chapter.md": {
            "chapter_id": "01-chapter.md", "status": "done",
            "outcome_counts": outcomes or {"VERIFICATION_SUPPORTED": 1},
            "candidates_made": 1, "model_calls": 2, "note": ""}},
        "canonical_untouched": untouched,
    }), encoding="utf-8")


def test_empty_book_root_is_unavailable(tmp_path: Path) -> None:
    summary = summarize_campaigns(tmp_path / "books")
    assert summary["available"] is False
    assert summary["totals"]["campaigns"] == 0


def test_counts_campaigns_and_outcomes(tmp_path: Path) -> None:
    ci = tmp_path / "books" / "inference" / ".writer" / "book-campaigns"
    (ci / "campaigns").mkdir(parents=True)
    (ci / "reports").mkdir(parents=True)
    _campaign(ci / "campaigns" / "camp-1.json")
    _campaign(ci / "campaigns" / "camp-2.json", state="PAUSED", chapters=1)
    _report(ci / "reports" / "rep-run-1.json")
    _report(ci / "reports" / "rep-run-2.json", status="COMPLETE_WITH_FAILURES",
            outcomes={"REGRESSION": 1, "INCONCLUSIVE": 1})
    (ci / "reports" / "bad.json").write_text("{not json", encoding="utf-8")
    summary = summarize_campaigns(tmp_path / "books")
    assert summary["available"] is True
    totals = summary["totals"]
    assert totals["reports"] == 2
    assert totals["verification_supported"] == 1
    assert totals["regressions_prevented"] == 1
    assert totals["inconclusive"] == 1
    assert totals["applied"] == 0
    assert totals["canonical_changes"] == 0
    assert summary["unreadable_files"] == 1
    assert "process metrics" in " ".join(summary["limitations"]).lower()
    inference = next(b for b in summary["books"] if b["book_id"] == "inference")
    assert len(inference["campaigns"]) == 2
    assert inference["chapters"][0]["chapter_id"] == "01-chapter.md"


def test_campaign_endpoints_are_read_only(client) -> None:
    response = client.get("/api/writer/campaigns")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] in (True, False)
    assert "totals" in body and "limitations" in body
    assert body["totals"]["applied"] == 0


def test_campaign_create_validates_input_without_executing(client) -> None:
    response = client.post("/api/writer/campaigns", json={"book_root": "", "mode": "PLAN"})
    assert response.status_code == 422, response.text
    response = client.post("/api/writer/campaigns/runs/chunk",
                           json={"run_id": "camp-1", "book_root": ""})
    assert response.status_code == 422, response.text


def test_workspace_carries_campaigns(client) -> None:
    body = client.get("/api/writer/books").json()
    assert "campaigns" in body
    assert "totals" in body["campaigns"]


def _ctx(tmp_path: Path) -> ActionContext:
    return ActionContext(
        application_id="writer",
        data_dir=tmp_path,
        application_repository_path=str(tmp_path / "writer"),
        config={"executable": "C:/writer/venv/Scripts/writer.exe"},
    )


def test_campaign_actions_validate_without_executing(tmp_path: Path) -> None:
    (tmp_path / "writer").mkdir()
    adapter = WriterAdapter()
    context = _ctx(tmp_path)
    adapter.validate_action("book_campaign_create", {"book_root": "C:/books/x"}, context)
    adapter.validate_action("book_campaign_run_chunk",
                            {"run_id": "camp-1", "book_root": "C:/books/x"}, context)
    with pytest.raises(ValueError, match="run_id"):
        adapter.validate_action("book_campaign_run_chunk", {"book_root": "C:/books/x"}, context)
    with pytest.raises(ValueError, match="Unsupported Writer action"):
        adapter.validate_action("book_campaign_destroy", {}, context)


def test_campaign_action_shells_writer_cli_with_json_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "writer").mkdir()
    import mission_control.adapters.writer as writer_adapter

    seen: dict = {}

    async def fake_run_tool(executable, arguments, **kwargs):
        seen["executable"] = executable
        seen["arguments"] = arguments
        return CommandResult(
            exit_code=0,
            stdout=json.dumps({"ok": True, "result": {"campaign": {"campaign_id": "camp-9"}}}),
            stderr="",
            duration_seconds=0.1,
            executable=executable,
        )

    monkeypatch.setattr(writer_adapter, "run_tool", fake_run_tool)
    adapter = WriterAdapter()
    result = asyncio.run(adapter.execute_action(
        "book_campaign_create",
        {"book_root": "C:/books/inference", "book_id": "inference", "mode": "PLAN"},
        _ctx(tmp_path),
    ))
    assert result.status == "succeeded"
    assert result.result["campaign"]["campaign_id"] == "camp-9"
    assert seen["arguments"][:2] == ["book-campaign", "create"]
    assert "--book-root" in seen["arguments"]
