"""Read-only projection of Workbench's editorial decisions.

Workbench owns these decisions and writes them as an append-only JSONL log.
Mission Control reads that log to remember what the author already decided; it
never writes, edits or infers a decision. Scope precedence matches Workbench:
a passage decision is more specific than a chapter pattern, which is more
specific than a book pattern.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCOPES = ("passage", "chapter", "book")


def read_records(path: str | Path | None) -> list[dict[str, Any]]:
    """Every readable decision record. A missing log is an empty log, not an error."""
    if not path:
        return []
    file = Path(path)
    if not file.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=lambda row: str(row.get("created_at") or ""))


def resolve(
    records: list[dict[str, Any]],
    *,
    project_id: str,
    chapter_id: str | None,
    finding_id: str | None,
    code: str | None,
) -> dict[str, Any] | None:
    """The decision that applies to one finding, using Workbench's scope order."""
    rows = [
        row
        for row in records
        if str(row.get("project_id") or "") == str(project_id or "")
    ]
    exact = _latest(
        [
            row
            for row in rows
            if finding_id
            and row.get("scope") == "passage"
            and str(row.get("finding_id") or "") == str(finding_id)
        ]
    )
    chapter = _latest(
        [
            row
            for row in rows
            if chapter_id
            and code
            and row.get("scope") == "chapter"
            and str(row.get("chapter_id") or "") == str(chapter_id)
            and str(row.get("code") or "") == str(code)
        ]
    )
    book = _latest(
        [
            row
            for row in rows
            if code
            and row.get("scope") == "book"
            and str(row.get("code") or "") == str(code)
        ]
    )
    chosen = exact or chapter or book
    if chosen is None:
        return None
    return {
        "decision": chosen.get("decision"),
        "scope": chosen.get("scope"),
        "reason": chosen.get("reason") or "",
        "created_at": chosen.get("created_at"),
        "decision_id": chosen.get("decision_id"),
    }


def summary(records: list[dict[str, Any]], *, project_id: str | None = None) -> dict[str, int]:
    counts = {"confirmed": 0, "dismissed": 0, "deferred": 0}
    for row in records:
        if project_id and str(row.get("project_id") or "") != str(project_id):
            continue
        key = str(row.get("decision") or "")
        if key in counts:
            counts[key] += 1
    return counts


def read_workbench_book(path: str | Path | None) -> dict[str, Any] | None:
    """The book Workbench currently has selected, from its saved preferences."""
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    book = data.get("book") if isinstance(data, dict) else None
    return book if isinstance(book, dict) else None


__all__ = ["SCOPES", "read_records", "resolve", "summary", "read_workbench_book"]
