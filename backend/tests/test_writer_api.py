from __future__ import annotations

import json

from fastapi.testclient import TestClient

from mission_control.adapters.base import ResourceSeed
from mission_control.integrations.store import upsert_resources
from mission_control.models import AdapterStatus
from mission_control.persistence.db import now_iso


def _chapter(title: str, *, status: str, fragmentation: float, paragraph: float) -> dict:
    finding = {
        "finding_id": "edfinding:" + title.lower().replace(" ", "-"),
        "code": "READABILITY.FRAGMENTATION",
        "severity": "high",
        "dimension": "readability",
        "subdimension": "fragmentation",
        "book_id": "language",
        "chapter_id": f"chapter:{title.lower().replace(' ', '-')}",
        "source_path": "C:/language/03.md",
        "locator": {
            "chapter_id": f"chapter:{title.lower().replace(' ', '-')}",
            "source_path": "C:/language/03.md",
            "relative_path": "content/books/language/03.md",
            "line_start": 22,
            "line_end": 22,
            "paragraph_index": 4,
            "section_title": title,
            "excerpt": "Short line.",
        },
        "measured": {"short_percent": 80.0},
        "reason": "The chapter is fragmented.",
        "recommendation": "Review whether short paragraphs do distinct work.",
        "limitations": ["Heuristic."],
    }
    return {
        "chapter_id": f"chapter:{title.lower().replace(' ', '-')}",
        "title": title,
        "source_path": "C:/language/03.md",
        "relative_path": "content/books/language/03.md",
        "source_fingerprint": "abc",
        "order": 0,
        "word_count": 1200,
        "paragraph_count": 40,
        "sentence_count": 100,
        "status": status,
        "current": True,
        "status_band": "high",
        "highest_risk": {"subdimension": "fragmentation", "score": fragmentation},
        "dimensions": [
            {
                "id": "paragraph_load",
                "label": "Paragraph load",
                "score": paragraph,
                "status_band": "watch",
                "finding_codes": ["READABILITY.PARAGRAPH_DENSITY"],
                "raw_metrics": {"p90_paragraph_words": 124},
                "explanation": "Density signal.",
                "limitations": ["Heuristic."],
                "scoring": {"formula": "100 - penalty", "weights": {"density": 55}},
            },
            {
                "id": "fragmentation",
                "label": "Fragmentation",
                "score": fragmentation,
                "status_band": "high",
                "finding_codes": ["READABILITY.FRAGMENTATION"],
                "raw_metrics": {"short_percent": 80.0},
                "explanation": "Fragmentation signal.",
                "limitations": ["Heuristic."],
                "scoring": {"formula": "100 - penalty", "weights": {"short": 70}},
            },
        ],
        "finding_codes": ["READABILITY.FRAGMENTATION"],
        "finding_count": 1,
        "findings": [finding],
    }


def _book(project_id: str, title: str, status: str, *, chapter: bool = True) -> dict:
    chapters = [_chapter("Memory", status="review_required", fragmentation=29.3, paragraph=61.0)] if chapter else []
    return {
        "project_id": project_id,
        "title": title,
        "status": status,
        "profile": "technical-nonfiction-v1",
        "project_root": "C:/language",
        "content_dir": "C:/language/content/books/language",
        "repository_path": "C:/language",
        "chapters_available": 1 if chapter else 0,
        "source_revision": "abc123",
        "source_dirty": True,
        "report_id": f"edit-{project_id}" if status != "NOT_RUN" else None,
        "scope": {"kind": "book", "whole_book": True, "chapter_ids": []},
        "last_checked": "2026-10-24T23:00:00Z" if status != "NOT_RUN" else None,
        "canonical_fingerprint": "fingerprint" if status != "NOT_RUN" else None,
        "editing": {"status": status},
        "pipeline": {
            "metadata": {"status": "NOT_TRACKED"},
            "mri": {"status": "NOT_TRACKED"},
            "strengthen": {"status": "NOT_TRACKED"},
            "editing": {"status": status},
        },
        "readability": (
            {
                "note": "Subdimensions are independent.",
                "subdimensions": [
                    {
                        "id": "paragraph_load",
                        "label": "Paragraph load",
                        "worst_score": 61.0,
                        "worst_band": "watch",
                        "worst_chapter_id": "chapter:memory",
                        "chapters_flagged": 0,
                        "chapter_scores": [],
                    },
                    {
                        "id": "fragmentation",
                        "label": "Fragmentation",
                        "worst_score": 29.3,
                        "worst_band": "high",
                        "worst_chapter_id": "chapter:memory",
                        "chapters_flagged": 1,
                        "chapter_scores": [],
                    },
                ],
                "highest_risk": {"subdimension": "fragmentation", "score": 29.3, "status_band": "high"},
            }
            if status != "NOT_RUN"
            else None
        ),
        "highest_risk": (
            {"severity": "high", "code": "READABILITY.FRAGMENTATION", "score": 29.3}
            if status != "NOT_RUN"
            else None
        ),
        "chapters": chapters,
        "findings_preview": chapters[0]["findings"] if chapters else [],
        "errors": ["Source unavailable"] if status == "ERROR" else [],
        "limitations": ["Read-only evidence."],
    }


def _seed_writer(client: TestClient) -> None:
    with client.app.state.database.session() as session:
        status = session.get(AdapterStatus, "adapter-app-writer")
        assert status is not None
        status.available = True
        status.detail = "Read 4 Writer book summaries."
        status.last_checked_at = now_iso()
        upsert_resources(
            session,
            "writer",
            [
                ResourceSeed(
                    resource_type="writer_editing_book",
                    external_id="language",
                    title="Language",
                    summary="Needs review",
                    state="NEEDS_REVIEW",
                    data=_book("language", "Language", "NEEDS_REVIEW"),
                    source_version="writer-editing-summary-v1",
                    source_timestamp="2026-10-24T23:00:00Z",
                ),
                ResourceSeed(
                    resource_type="writer_editing_book",
                    external_id="stale-book",
                    title="Stale Book",
                    summary="Stale",
                    state="STALE",
                    data=_book("stale-book", "Stale Book", "STALE"),
                    source_version="writer-editing-summary-v1",
                    source_timestamp="2026-10-24T23:00:00Z",
                ),
                ResourceSeed(
                    resource_type="writer_editing_book",
                    external_id="partial-book",
                    title="Partial Book",
                    summary="Partial",
                    state="PARTIAL",
                    data=_book("partial-book", "Partial Book", "PARTIAL"),
                    source_version="writer-editing-summary-v1",
                    source_timestamp="2026-10-24T23:00:00Z",
                ),
                ResourceSeed(
                    resource_type="writer_editing_book",
                    external_id="not-run",
                    title="Not Run",
                    summary="No evidence",
                    state="NOT_RUN",
                    data=_book("not-run", "Not Run", "NOT_RUN", chapter=False),
                    source_version="writer-editing-summary-v1",
                    source_timestamp="2026-10-24T23:00:00Z",
                ),
                ResourceSeed(
                    resource_type="writer_editing_book",
                    external_id="error-book",
                    title="Error Book",
                    summary="Error",
                    state="ERROR",
                    data=_book("error-book", "Error Book", "ERROR"),
                    source_version="writer-editing-summary-v1",
                    source_timestamp="2026-10-24T23:00:00Z",
                ),
            ],
        )


def test_writer_workspace_preserves_subdimensions_and_orders_review_queue(
    client: TestClient,
) -> None:
    _seed_writer(client)
    response = client.get("/api/writer/books")
    assert response.status_code == 200, response.text
    workspace = response.json()
    assert workspace["available"] is True
    assert [book["project_id"] for book in workspace["books"]] == [
        "error-book",
        "stale-book",
        "language",
        "partial-book",
        "not-run",
    ]
    assert [item["project_id"] for item in workspace["review_queue"]] == [
        "error-book",
        "stale-book",
        "language",
        "partial-book",
        "not-run",
    ]
    assert workspace["totals"]["not_run"] == 1
    assert workspace["totals"]["partial"] == 1
    language = next(book for book in workspace["books"] if book["project_id"] == "language")
    assert language["status"] == "NEEDS_REVIEW"
    assert language["readability"]["subdimensions"][0]["worst_score"] == 61.0
    assert language["readability"]["subdimensions"][1]["worst_score"] == 29.3
    chapter = language["chapters"][0]
    assert chapter["findings"][0]["locator"]["relative_path"] == "content/books/language/03.md"
    assert chapter["dimensions"][0]["scoring"]["weights"]["density"] == 55
    not_run = next(book for book in workspace["books"] if book["project_id"] == "not-run")
    assert not_run["report_id"] is None
    assert not_run["readability"] is None

def test_decision_queue_groups_findings_and_links_to_the_current_workbench_book(
    client: TestClient,
) -> None:
    _seed_writer(client)
    client.app.state.settings.workbench_preferences_path.write_text(
        json.dumps({"book": {"project_id": "language", "book_root": "C:/language"}}),
        encoding="utf-8",
    )
    workspace = client.get("/api/writer/books").json()
    assert workspace["decision_totals"]["groups"] >= 1
    language = next(
        item for item in workspace["decision_queue"] if item["project_id"] == "language"
    )
    assert language["code"] == "READABILITY.FRAGMENTATION"
    assert language["count"] == 1 and language["chapter_count"] == 1
    assert language["state"] == "undecided"
    assert language["finding_id"].startswith("edfinding:")
    assert language["workbench_book_ready"] is True
    assert "chapter=03.md" in language["workbench_link"]
    assert "finding=edfinding%3A" in language["workbench_link"] or "finding=edfinding:" in language["workbench_link"]
    stale = next(
        item for item in workspace["decision_queue"] if item["project_id"] == "stale-book"
    )
    assert stale["state"] == "stale" and stale["workbench_link"] == ""
    assert stale["workbench_book_ready"] is False


def test_a_book_scope_workbench_decision_is_remembered_without_writing_it(
    client: TestClient,
) -> None:
    _seed_writer(client)
    log = client.app.state.settings.workbench_decisions_path
    log.write_text(
        json.dumps(
            {
                "decision_id": "eddecision:test",
                "created_at": "2026-10-25T12:00:00Z",
                "project_id": "language",
                "chapter_id": "chapter:memory",
                "finding_id": "edfinding:memory",
                "code": "READABILITY.FRAGMENTATION",
                "decision": "dismissed",
                "scope": "book",
                "reason": "Intentional style.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    workspace = client.get("/api/writer/books").json()
    language = next(
        item for item in workspace["decision_queue"] if item["project_id"] == "language"
    )
    assert language["state"] == "decided"
    assert language["undecided_count"] == 0 and language["decided_count"] == 1
    assert language["decision"]["decision"] == "dismissed"
    assert language["decision"]["reason"] == "Intentional style."
    assert workspace["decision_totals"]["dismissed"] == 1
    assert log.read_text(encoding="utf-8").count("eddecision:test") == 1
