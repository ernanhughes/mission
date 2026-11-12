"""Improvement-intelligence summary (read-only) + selective plan passthrough."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_control.writer.intel_summary import summarize_intel


def _chapter_run(path: Path, *, outcome="VERIFICATION_SUPPORTED", strategy="artifact_pattern",
                 run_id="r-1"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "run_id": run_id, "chapter_id": "01-chapter.md", "source_revision": "a" * 64,
        "status": "complete",
        "opportunities": {
            "opp-1": {"opportunity_id": "opp-1", "strategy": strategy,
                      "status": "done", "outcome": outcome,
                      "attempts": [{"strategy": strategy, "disposition": outcome,
                                    "note": "engine accepted", "model_calls": 1,
                                    "verification": {"run_dir": "",
                                                     "gates": []},
                                    "provenance": {}}]},
        },
    }), encoding="utf-8")


def _plan(path: Path, *, span=200):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "plan_id": path.stem, "chapter_id": "02-chapter.md",
        "source_revision": "b" * 64, "snapshot_id": "s", "items": [],
        "skipped": [{"opportunity_id": "opp-big",
                     "reason": f"region spans {span} lines (budget max 60); split the region"}],
    }), encoding="utf-8")


def test_empty_book_root_is_unavailable(tmp_path: Path) -> None:
    summary = summarize_intel(tmp_path / "books")
    assert summary["available"] is False
    assert summary["totals"]["attempts"] == 0


def test_index_counts_attempts_strategies_and_oversized(tmp_path: Path) -> None:
    w = tmp_path / "books" / "inference" / ".writer" / "chapter-improvement"
    _chapter_run(w / "runs" / "r-1.json", run_id="r-1")
    _chapter_run(w / "runs" / "r-2.json", outcome="REGRESSION", run_id="r-2")
    _plan(w / "plans" / "p-1.json")
    (w / "plans" / "bad.json").write_text("{not json", encoding="utf-8")
    summary = summarize_intel(tmp_path / "books")
    assert summary["available"] is True
    assert summary["totals"]["attempts"] == 2
    assert summary["totals"]["verification_supported"] == 1
    assert summary["totals"]["preservation_failed"] == 1
    assert summary["totals"]["skipped_oversized"] == 1
    assert summary["unreadable_files"] == 1
    by_strategy = {c["strategy"]: c for c in summary["strategies"]}
    assert by_strategy["artifact_pattern"]["evaluated"] == 2
    assert by_strategy["artifact_pattern"]["evidence_level"] == "EARLY_SIGNAL"
    assert by_strategy["artifact_pattern"]["denominator"].startswith("supported / evaluated")
    assert summary["models"], "model cards must exist even when models are unknown"
    assert any(f["family"] == "technical_preservation" for f in summary["failures"])
    assert len(summary["oversized"]) == 1
    assert "process metrics" in " ".join(summary["limitations"]).lower()


def test_intel_is_read_only_and_in_workspace(client) -> None:
    response = client.get("/api/writer/intel")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] in (True, False)
    assert "strategies" in body and "models" in body and "oversized" in body
    workspace = client.get("/api/writer/books").json()
    assert "intel" in workspace
    assert workspace["intel"]["totals"]["attempts"] >= 0


def test_plan_action_accepts_selective_modes(tmp_path: Path) -> None:
    (tmp_path / "writer").mkdir()
    from mission_control.adapters.base import ActionContext
    from mission_control.adapters.writer import WriterAdapter

    adapter = WriterAdapter()
    context = ActionContext(
        application_id="writer",
        data_dir=tmp_path,
        application_repository_path=str(tmp_path / "writer"),
        config={"executable": "C:/writer/venv/Scripts/writer.exe"},
    )
    adapter.validate_action("book_campaign_plan",
                            {"campaign_id": "c", "book_root": "b", "selective": "eligible"},
                            context)
    args = adapter._campaign_args("book_campaign_plan",
                                  {"campaign_id": "c", "book_root": "b", "selective": "eligible"})
    assert args == ["book-campaign", "plan", "c", "--book-root", "b",
                    "--selective", "eligible"]
    args_all = adapter._campaign_args("book_campaign_plan",
                                      {"campaign_id": "c", "book_root": "b"})
    assert "--selective" not in args_all
    with pytest.raises(ValueError, match="selective"):
        adapter._campaign_args("book_campaign_plan",
                               {"campaign_id": "c", "book_root": "b", "selective": "bogus"})
