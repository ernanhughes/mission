from __future__ import annotations

from mission_control.writer.decisions import resolve
from mission_control.writer.queue import build_decision_queue


def _finding(
    finding_id: str,
    *,
    code: str = "READABILITY.LONG_SENTENCE",
    severity: str = "high",
    chapter_id: str = "chapter:book:01-chapter",
    line: int = 10,
) -> dict:
    return {
        "finding_id": finding_id,
        "code": code,
        "severity": severity,
        "dimension": "readability",
        "subdimension": "sentence_load",
        "chapter_id": chapter_id,
        "reason": "The sentence carries several claims.",
        "recommendation": "Read it in context.",
        "locator": {
            "chapter_id": chapter_id,
            "relative_path": f"{chapter_id.rsplit(':', 1)[-1]}.md",
            "line_start": line,
            "line_end": line,
            "paragraph_index": 1,
            "section_title": "Opening",
            "excerpt": "A long sentence.",
        },
        "measured": {"sentence_words": 54},
        "limitations": ["A diagnostic, not a verdict."],
    }


def _chapter(chapter_id: str, order: int, findings: list[dict]) -> dict:
    return {
        "chapter_id": chapter_id,
        "title": f"Chapter {order + 1}",
        "relative_path": f"{chapter_id.rsplit(':', 1)[-1]}.md",
        "order": order,
        "findings": findings,
    }


def _book(project_id: str, status: str, chapters: list[dict]) -> dict:
    return {
        "project_id": project_id,
        "title": project_id.title(),
        "status": status,
        "chapters": chapters,
    }


def _decision(**over) -> dict:
    row = {
        "decision_id": "eddecision:test",
        "created_at": "2026-10-25T12:00:00Z",
        "project_id": "book",
        "chapter_id": "chapter:book:01-chapter",
        "finding_id": "edfinding:a",
        "code": "READABILITY.LONG_SENTENCE",
        "decision": "confirmed",
        "scope": "passage",
        "reason": "",
    }
    row.update(over)
    return row


def test_repeated_findings_are_grouped_with_an_earliest_representative() -> None:
    first = _finding("edfinding:a", chapter_id="chapter:book:01-chapter", line=10)
    second = _finding("edfinding:b", chapter_id="chapter:book:02-chapter", line=20)
    books = [
        _book(
            "book",
            "NEEDS_REVIEW",
            [
                _chapter("chapter:book:02-chapter", 1, [second]),
                _chapter("chapter:book:01-chapter", 0, [first]),
            ],
        )
    ]
    queue, totals, workbench = build_decision_queue(
        books,
        [],
        workbench_url="http://workbench.test",
        workbench_book={"project_id": "book"},
    )
    assert len(queue) == 1
    item = queue[0]
    assert item["count"] == 2 and item["chapter_count"] == 2
    assert item["finding_id"] == "edfinding:a"
    assert item["chapter_title"] == "Chapter 1"
    assert item["state"] == "undecided" and item["undecided_count"] == 2
    assert item["workbench_book_ready"] is True
    assert "finding=edfinding%3Aa" in item["workbench_link"]
    assert totals == {
        "groups": 1,
        "findings": 2,
        "undecided": 2,
        "decided": 0,
        "stale_groups": 0,
        "missing_identity": 0,
    }
    assert workbench["book"] == "book"


def test_chapter_scope_is_partial_and_book_scope_is_remembered_as_decided() -> None:
    first = _finding("edfinding:a", chapter_id="chapter:book:01-chapter")
    second = _finding("edfinding:b", chapter_id="chapter:book:02-chapter")
    books = [
        _book(
            "book",
            "NEEDS_REVIEW",
            [
                _chapter("chapter:book:01-chapter", 0, [first]),
                _chapter("chapter:book:02-chapter", 1, [second]),
            ],
        )
    ]
    chapter_record = _decision(scope="chapter", finding_id="edfinding:a")
    queue, totals, _ = build_decision_queue(books, [chapter_record])
    item = queue[0]
    assert item["state"] == "partial"
    assert item["decided_count"] == 1 and item["undecided_count"] == 1
    assert item["decision"]["scope"] == "chapter"

    book_record = _decision(scope="book", finding_id="edfinding:other")
    queue, totals, _ = build_decision_queue(books, [chapter_record, book_record])
    item = queue[0]
    assert item["state"] == "decided"
    assert item["decided_count"] == 2 and item["undecided_count"] == 0
    assert totals["decided"] == 2


def test_a_more_specific_passage_decision_wins_and_latest_wins_within_scope() -> None:
    records = [
        _decision(scope="book", decision="dismissed", created_at="2026-10-25T10:00:00Z"),
        _decision(
            scope="chapter",
            decision="deferred",
            finding_id="edfinding:other",
            created_at="2026-10-25T11:00:00Z",
        ),
        _decision(scope="passage", decision="confirmed", created_at="2026-10-25T12:00:00Z"),
    ]
    chosen = resolve(
        records,
        project_id="book",
        chapter_id="chapter:book:01-chapter",
        finding_id="edfinding:a",
        code="READABILITY.LONG_SENTENCE",
    )
    assert chosen is not None
    assert chosen["decision"] == "confirmed" and chosen["scope"] == "passage"

    chosen = resolve(
        records,
        project_id="book",
        chapter_id="chapter:book:01-chapter",
        finding_id="edfinding:not-in-log",
        code="READABILITY.LONG_SENTENCE",
    )
    assert chosen is not None and chosen["decision"] == "deferred"

    chosen = resolve(
        records,
        project_id="book",
        chapter_id="chapter:book:99-chapter",
        finding_id="edfinding:not-in-log",
        code="READABILITY.LONG_SENTENCE",
    )
    assert chosen is not None and chosen["decision"] == "dismissed"


def test_stale_evidence_has_no_workbench_link_and_is_not_presented_as_decidable() -> None:
    books = [
        _book(
            "book",
            "STALE",
            [_chapter("chapter:book:01-chapter", 0, [_finding("edfinding:a")])],
        )
    ]
    queue, totals, _ = build_decision_queue(
        books,
        [],
        workbench_url="http://workbench.test",
        workbench_book={"project_id": "book"},
    )
    assert queue[0]["state"] == "stale"
    assert queue[0]["workbench_link"] == ""
    assert queue[0]["workbench_book_ready"] is False
    assert totals["stale_groups"] == 1

def test_the_book_open_in_workbench_is_queued_first_so_the_link_is_actionable() -> None:
    other = _book(
        "other",
        "NEEDS_REVIEW",
        [_chapter("chapter:other:01-chapter", 0, [_finding(f"edfinding:o{i}") for i in range(10)])],
    )
    current = _book(
        "book",
        "NEEDS_REVIEW",
        [_chapter("chapter:book:01-chapter", 0, [_finding("edfinding:a", severity="medium")])],
    )
    queue, _, _ = build_decision_queue(
        [other, current],
        [],
        workbench_url="http://workbench.test",
        workbench_book={"project_id": "book"},
    )
    assert queue[0]["project_id"] == "book"
    assert queue[0]["workbench_book_ready"] is True
    assert queue[1]["project_id"] == "other"
    assert queue[1]["workbench_book_ready"] is False

def test_a_later_book_decision_does_not_override_an_earlier_passage_decision() -> None:
    records = [
        _decision(scope="passage", decision="confirmed", created_at="2026-10-25T10:00:00Z"),
        _decision(scope="book", decision="dismissed", created_at="2026-10-25T11:00:00Z"),
    ]
    chosen = resolve(
        records,
        project_id="book",
        chapter_id="chapter:book:01-chapter",
        finding_id="edfinding:a",
        code="READABILITY.LONG_SENTENCE",
    )
    assert chosen is not None
    assert chosen["decision"] == "confirmed" and chosen["scope"] == "passage"

def test_a_decided_current_book_group_does_not_outrank_undecided_work_elsewhere() -> None:
    current = _book(
        "book",
        "NEEDS_REVIEW",
        [_chapter("chapter:book:01-chapter", 0, [_finding("edfinding:a")])],
    )
    other = _book(
        "other",
        "NEEDS_REVIEW",
        [_chapter("chapter:other:01-chapter", 0, [_finding("edfinding:b")])],
    )
    decided = _decision(scope="book", decision="dismissed")
    queue, _, _ = build_decision_queue(
        [current, other],
        [decided],
        workbench_url="http://workbench.test",
        workbench_book={"project_id": "book"},
    )
    assert queue[0]["project_id"] == "other"
    assert queue[0]["state"] == "undecided"
    assert queue[1]["project_id"] == "book"
    assert queue[1]["state"] == "decided"

