"""Prioritised editorial decision queue.

Writer supplies findings, severity, locators and stable finding ids. Mission
Control groups repeated findings of the same kind so the author reviews a
representative, consequential case rather than every detected instance. It
joins Workbench's decision log for state only; it never scores prose or creates
an editorial decision.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from mission_control.writer.decisions import resolve

_SEVERITY = {"high": 0, "medium": 1, "low": 2, "info": 3}
_STATUS = {
    "NEEDS_REVIEW": 0,
    "CURRENT": 1,
    "PARTIAL": 2,
    "STALE": 3,
    "ERROR": 4,
    "NOT_RUN": 5,
    "NO_MANUSCRIPT": 6,
    "BLOCKED": 7,
}
_DECIDED = 2
_PARTIAL = 1
_UNDECIDED = 0
_STALE_EVIDENCE = {"STALE", "ERROR"}


def _chapter_name(finding: dict[str, Any], chapter: dict[str, Any]) -> str:
    locator = finding.get("locator") or {}
    raw = locator.get("relative_path") or chapter.get("relative_path") or ""
    return Path(str(raw)).name


def _workbench_link(
    *,
    base_url: str,
    finding_id: str,
    chapter_name: str,
) -> str:
    if not base_url:
        return ""
    return (
        f"{base_url.rstrip('/')}/#chapter={quote(chapter_name)}"
        f"&menu=edt&drawer=editing&finding={quote(finding_id)}"
    )


def _finding_rows(book: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for chapter in book.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for finding in chapter.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            rows.append((chapter, finding))
    return rows


def build_decision_queue(
    books: list[dict[str, Any]],
    records: list[dict[str, Any]],
    *,
    workbench_url: str = "",
    workbench_book: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    """Group findings by book/code/severity and attach the author's decision state."""
    workbench_project = str((workbench_book or {}).get("project_id") or "")
    missing_identity = 0
    groups: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for book in books:
        project_id = str(book.get("project_id") or "")
        if not project_id:
            continue
        if str(book.get("status") or "").upper() in {"NOT_RUN", "NO_MANUSCRIPT", "BLOCKED"}:
            continue
        for chapter, finding in _finding_rows(book):
            if not finding.get("finding_id"):
                missing_identity += 1
                continue
            group = (
                project_id,
                str(finding.get("code") or ""),
                str(finding.get("severity") or "info"),
            )
            groups[group].append((chapter, finding))

    queue: list[dict[str, Any]] = []
    for (project_id, code, severity), rows in groups.items():
        book = next(item for item in books if str(item.get("project_id") or "") == project_id)
        book_status = str(book.get("status") or "UNKNOWN").upper()
        stale = book_status in _STALE_EVIDENCE

        # A representative is the earliest chapter and locator in the group.
        rows.sort(
            key=lambda pair: (
                int(pair[0].get("order") or 0),
                int(((pair[1].get("locator") or {}).get("line_start") or 0)),
                str(pair[1].get("finding_id") or ""),
            )
        )
        chapter, finding = rows[0]
        chapter_id = str(chapter.get("chapter_id") or finding.get("chapter_id") or "")
        chapter_name = _chapter_name(finding, chapter)
        locator = finding.get("locator") or {}

        decisions = [
            resolve(
                records,
                project_id=project_id,
                chapter_id=str(pair[0].get("chapter_id") or pair[1].get("chapter_id") or ""),
                finding_id=str(pair[1].get("finding_id") or ""),
                code=str(pair[1].get("code") or ""),
            )
            for pair in rows
        ]
        decided = [item for item in decisions if item]
        representative_decision = decisions[0]
        if stale:
            state = "stale"
        elif len(decided) == len(rows):
            state = "decided"
        elif decided:
            state = "partial"
        else:
            state = "undecided"
        queue.append(
            {
                "id": f"writer-decision:{project_id}:{code}:{severity}",
                "project_id": project_id,
                "book_title": book.get("title") or project_id,
                "book_status": book_status,
                "stale": stale,
                "code": code,
                "subdimension": finding.get("subdimension") or "",
                "severity": severity,
                "dimension": finding.get("dimension") or "readability",
                "chapter_id": chapter_id,
                "chapter_title": chapter.get("title") or "",
                "chapter_order": int(chapter.get("order") or 0),
                "chapter_name": chapter_name,
                "finding_id": str(finding.get("finding_id") or ""),
                "reason": finding.get("reason") or "",
                "recommendation": finding.get("recommendation") or "",
                "locator": locator,
                "measured": finding.get("measured") or {},
                "limitations": list(finding.get("limitations") or []),
                "count": len(rows),
                "chapter_count": len({str(pair[0].get("chapter_id") or "") for pair in rows}),
                "decided_count": len(decided),
                "undecided_count": len(rows) - len(decided),
                "state": state,
                "decision": representative_decision,
                "workbench_link": _workbench_link(
                    base_url=workbench_url,
                    finding_id=str(finding.get("finding_id") or ""),
                    chapter_name=chapter_name,
                )
                if not stale
                else "",
                "workbench_book_ready": bool(
                    workbench_project and workbench_project == project_id and not stale
                ),
            }
        )

    queue.sort(
        key=lambda item: (
            # Undecided work comes before partial and decided work. Within the
            # undecided set, the book already open in Workbench is the one the
            # author can act on without switching context.
            _UNDECIDED if item["state"] == "undecided" else _PARTIAL if item["state"] == "partial" else _DECIDED,
            0 if item["workbench_book_ready"] else 1,
            _SEVERITY.get(str(item["severity"]), 9),
            -int(item["undecided_count"]),
            -int(item["count"]),
            _STATUS.get(str(item["book_status"]), 9),
            str(item["book_title"]).casefold(),
            str(item["code"]),
        )
    )
    totals = {
        "groups": len(queue),
        "findings": sum(item["count"] for item in queue),
        "undecided": sum(item["undecided_count"] for item in queue),
        "decided": sum(item["decided_count"] for item in queue),
        "stale_groups": sum(1 for item in queue if item["stale"]),
        "missing_identity": missing_identity,
    }
    workbench = {
        "url": workbench_url,
        "book": workbench_project or None,
        "ready": bool(workbench_project),
        "note": (
            ""
            if workbench_project
            else "Workbench's saved book is unavailable; open a book there before following a link."
        ),
    }
    return queue, totals, workbench


__all__ = ["build_decision_queue"]
