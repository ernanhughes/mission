from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mission_control.adapters.base import ActionContext, AdapterTarget
from mission_control.adapters.writer import WriterAdapter, CLI_SCHEMA, SUMMARY_SCHEMA
from mission_control.integrations.runner import CommandResult


def _dimension(identifier: str, score: float, band: str, code: str | None = None) -> dict:
    return {
        "id": identifier,
        "label": identifier.replace("_", " ").title(),
        "score": score,
        "status_band": band,
        "finding_codes": [code] if code else [],
        "raw_metrics": {"sample": 1},
        "explanation": "Diagnostic only.",
        "limitations": ["Heuristic."],
        "scoring": {"formula": "100 - penalty", "weights": {"penalty": 1}},
    }


def _book(project_id: str, status: str, *, report_id: str | None = "edit-fixture", score: float = 29.3) -> dict:
    finding = {
        "code": "READABILITY.FRAGMENTATION",
        "severity": "high",
        "dimension": "readability",
        "subdimension": "fragmentation",
        "book_id": project_id,
        "chapter_id": "chapter:one",
        "source_path": "C:/book/01.md",
        "locator": {
            "chapter_id": "chapter:one",
            "source_path": "C:/book/01.md",
            "relative_path": "content/books/fixture/01.md",
            "line_start": 12,
            "line_end": 12,
            "paragraph_index": 1,
            "section_title": "One",
            "excerpt": "Short line.",
        },
        "measured": {"short_percent": 80.0},
        "reason": "The chapter is fragmented.",
        "recommendation": "Review whether the short paragraphs do distinct work.",
        "limitations": ["Heuristic."],
    }
    return {
        "project_id": project_id,
        "title": f"Book {project_id}",
        "status": status,
        "profile": "technical-nonfiction-v1",
        "project_root": "C:/book",
        "content_dir": "C:/book/content/books/fixture",
        "repository_path": "C:/book",
        "chapters_available": 2,
        "source_revision": "abc123",
        "source_dirty": False,
        "report_id": report_id,
        "scope": {"kind": "book", "whole_book": True, "chapter_ids": ["chapter:one"]},
        "last_checked": "2026-10-24T23:00:00Z",
        "canonical_fingerprint": "fingerprint",
        "editing": {"status": status, "report_id": report_id},
        "pipeline": {
            "metadata": {"status": "NOT_TRACKED"},
            "mri": {"status": "NOT_TRACKED"},
            "strengthen": {"status": "NOT_TRACKED"},
            "editing": {"status": status},
        },
        "readability": {
            "note": "No composite score.",
            "subdimensions": [
                {
                    "id": "paragraph_load",
                    "label": "Paragraph load",
                    "worst_score": 61.0,
                    "worst_band": "watch",
                    "worst_chapter_id": "chapter:one",
                    "chapters_flagged": 0,
                    "chapter_scores": [],
                },
                {
                    "id": "fragmentation",
                    "label": "Fragmentation",
                    "worst_score": score,
                    "worst_band": "high",
                    "worst_chapter_id": "chapter:one",
                    "chapters_flagged": 1,
                    "chapter_scores": [],
                },
            ],
            "highest_risk": {"subdimension": "fragmentation", "score": score, "status_band": "high"},
        },
        "highest_risk": {
            "kind": "finding",
            "severity": "high",
            "code": "READABILITY.FRAGMENTATION",
            "chapter_id": "chapter:one",
            "subdimension": "fragmentation",
            "score": score,
            "status_band": "high",
        },
        "chapters": [
            {
                "chapter_id": "chapter:one",
                "title": "One",
                "source_path": "C:/book/01.md",
                "relative_path": "content/books/fixture/01.md",
                "source_fingerprint": "abc",
                "order": 0,
                "word_count": 100,
                "paragraph_count": 4,
                "sentence_count": 8,
                "status": "review_required",
                "current": status != "STALE",
                "status_band": "high",
                "highest_risk": {"subdimension": "fragmentation", "score": score},
                "dimensions": [
                    _dimension("paragraph_load", 61.0, "watch", "READABILITY.PARAGRAPH_DENSITY"),
                    _dimension("fragmentation", score, "high", "READABILITY.FRAGMENTATION"),
                ],
                "finding_codes": ["READABILITY.FRAGMENTATION"],
                "finding_count": 1,
                "findings": [finding],
            }
        ],
        "findings_preview": [finding],
        "errors": [] if status == "CURRENT" else ["fixture evidence"],
        "limitations": ["Read-only evidence."],
    }


def _envelope(books: list[dict], *, totals: dict | None = None) -> dict:
    return {
        "ok": True,
        "command": "editing summary",
        "result": {
            "schema_version": SUMMARY_SCHEMA,
            "generated_at": "2026-10-24T23:00:00Z",
            "store_path": "C:/writer/.writer/editing",
            "registry_path": "C:/writer/config/web/projects.yaml",
            "books": books,
            "review_queue": [
                {
                    "project_id": book["project_id"],
                    "title": book["title"],
                    "status": book["status"],
                    "risk_rank": 2,
                    "highest_risk": book.get("highest_risk"),
                    "finding_count": 1,
                    "report_id": book.get("report_id"),
                    "last_checked": book.get("last_checked"),
                }
                for book in books
            ],
            "totals": totals
            or {
                "registered_active": len(books),
                "audited": sum(1 for book in books if book.get("report_id")),
                "needs_review": sum(1 for book in books if book["status"] == "NEEDS_REVIEW"),
                "stale": sum(1 for book in books if book["status"] == "STALE"),
                "not_run": sum(1 for book in books if book["status"] == "NOT_RUN"),
            },
            "limitations": ["No manuscript edited."],
        },
        "warnings": [],
        "errors": [],
        "meta": {"schema_version": CLI_SCHEMA, "generated_at": "2026-10-24T23:00:00Z"},
    }


def _result(stdout: dict) -> CommandResult:
    return CommandResult(
        exit_code=0,
        stdout=json.dumps(stdout),
        stderr="",
        duration_seconds=0.1,
        executable="writer.exe",
    )


def test_writer_adapter_parses_contract_and_preserves_subdimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "writer"
    repo.mkdir()
    payload = _envelope([_book("language", "NEEDS_REVIEW"), _book("quiet", "NOT_RUN", report_id=None)])
    import mission_control.adapters.writer as writer_adapter

    async def fake_run_tool(*_args, **_kwargs):
        return _result(payload)

    monkeypatch.setattr(writer_adapter, "run_tool", fake_run_tool)
    target = AdapterTarget(
        name="Writer",
        application_id="writer",
        repository_paths=[(str(repo), "primary")],
        config={"executable": "C:/writer/venv/Scripts/writer.exe"},
    )
    result = asyncio.run(WriterAdapter().refresh(target))
    assert result.available is True
    assert len(result.resources) == 2
    book = next(item for item in result.resources if item.external_id == "language")
    assert book.resource_type == "writer_editing_book"
    assert book.state == "NEEDS_REVIEW"
    assert book.data["readability"]["subdimensions"][1]["worst_score"] == 29.3
    assert book.data["chapters"][0]["findings"][0]["locator"]["line_start"] == 12
    assert "Writer remains the source" in result.detail


def test_writer_adapter_rejects_unversioned_or_malformed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "writer"
    repo.mkdir()
    import mission_control.adapters.writer as writer_adapter

    async def fake_run_tool(*_args, **_kwargs):
        return _result({"ok": True, "result": {"books": []}})

    monkeypatch.setattr(writer_adapter, "run_tool", fake_run_tool)
    result = asyncio.run(
        WriterAdapter().refresh(
            AdapterTarget(name="Writer", repository_paths=[(str(repo), "primary")])
        )
    )
    assert result.available is False
    assert "versioned editing contract" in result.detail


def test_writer_adapter_unavailable_repository() -> None:
    result = asyncio.run(
        WriterAdapter().refresh(AdapterTarget(name="Writer", repository_paths=[]))
    )
    assert result.available is False
    assert "unavailable" in result.detail


def test_writer_audit_action_validates_profile_and_returns_totals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "writer"
    repo.mkdir()
    payload = _envelope([_book("language", "NEEDS_REVIEW")])
    import mission_control.adapters.writer as writer_adapter

    async def fake_run_tool(*_args, **_kwargs):
        return _result(payload)

    monkeypatch.setattr(writer_adapter, "run_tool", fake_run_tool)
    adapter = WriterAdapter()
    context = ActionContext(
        application_id="writer",
        data_dir=tmp_path,
        application_repository_path=str(repo),
        config={"executable": "C:/writer/venv/Scripts/writer.exe"},
    )
    with pytest.raises(ValueError, match="Unsupported Writer editing profile"):
        adapter.validate_action(
            "audit_registered_books", {"profile": "fiction-v1"}, context
        )
    result = asyncio.run(
        adapter.execute_action(
            "audit_registered_books", {"profile": "technical-nonfiction-v1"}, context
        )
    )
    assert result.status == "succeeded"
    assert result.result["totals"]["needs_review"] == 1
    assert result.artifact_ref.endswith(".writer/editing")
