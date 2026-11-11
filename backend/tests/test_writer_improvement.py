"""Read-only chapter-improvement summary: process metrics, never scores."""

from __future__ import annotations

import json
from pathlib import Path

from mission_control.writer.improvement_summary import summarize_improvement


def _report(path: Path, *, run_id: str, status: str, outcomes: dict,
            decisions: int = 0, untouched: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    opportunities = {}
    if decisions:
        opportunities["opp-1"] = {"author_decisions": [
            {"decision": "AUTHOR_ACCEPTED", "rationale": "", "actor": "author"}]}
    path.write_text(json.dumps({
        "report_id": path.stem, "run_id": run_id, "chapter_id": "01-chapter.md",
        "status": status, "outcome_counts": outcomes, "opportunities": opportunities,
        "canonical_untouched": untouched,
    }), encoding="utf-8")


def test_empty_book_root_is_unavailable(tmp_path: Path) -> None:
    summary = summarize_improvement(tmp_path / "books")
    assert summary["available"] is False
    assert summary["totals"]["reports"] == 0


def test_counts_reports_plans_and_outcomes(tmp_path: Path) -> None:
    ci = tmp_path / "books" / "inference" / ".writer" / "chapter-improvement"
    (ci / "snapshots").mkdir(parents=True, exist_ok=True)
    (ci / "plans").mkdir(parents=True, exist_ok=True)
    (ci / "reports").mkdir(parents=True, exist_ok=True)
    (ci / "snapshots" / "snap-1.json").write_text(
        json.dumps({"chapter_id": "01-chapter.md"}), encoding="utf-8")
    (ci / "plans" / "plan-1.json").write_text(
        json.dumps({"chapter_id": "01-chapter.md"}), encoding="utf-8")
    _report(ci / "reports" / "rep-1.json", run_id="ci-1", status="complete",
            outcomes={"VERIFICATION_SUPPORTED": 1, "INCONCLUSIVE": 1}, decisions=1)
    _report(ci / "reports" / "rep-2.json", run_id="ci-2", status="stopped",
            outcomes={"REGRESSION": 1}, untouched=True)
    (ci / "reports" / "bad.json").write_text("{not json", encoding="utf-8")
    summary = summarize_improvement(tmp_path / "books")
    assert summary["available"] is True
    totals = summary["totals"]
    assert totals["reports"] == 2
    assert totals["snapshots"] == 1 and totals["plans"] == 1
    assert totals["verification_supported"] == 1
    assert totals["regressions_prevented"] == 1
    assert totals["inconclusive"] == 1
    assert totals["author_accepted"] == 1
    assert totals["applied"] == 0
    assert totals["canonical_changes"] == 0
    assert summary["unreadable_files"] == 1
    assert "process metrics" in " ".join(summary["limitations"]).lower()


def test_improvement_endpoint_is_read_only(client) -> None:
    response = client.get("/api/writer/improvement")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] in (True, False)
    assert "totals" in body and "limitations" in body
    assert body["totals"]["applied"] == 0


def test_workspace_carries_improvement_summary(client) -> None:
    body = client.get("/api/writer/books").json()
    assert "chapter_improvement" in body
    assert "totals" in body["chapter_improvement"]
