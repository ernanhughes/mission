"""Read model for Writer Editing evidence in Mission Control.

Mission Control never re-scores a book. It reads the Writer-created summary and
resource payloads, preserves independent subdimensions, and presents source
status (current/stale/not-run/partial/error).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from mission_control.config import RuntimeSettings
from mission_control.models import Application, AdapterStatus, IntegrationRecord
from mission_control.persistence.db import Database
from mission_control.writer.decisions import (
    read_records,
    read_workbench_book,
    summary as decision_summary,
)
from mission_control.writer.queue import build_decision_queue

_STATUS_RANK = {
    "ERROR": 0,
    "STALE": 1,
    "NEEDS_REVIEW": 2,
    "PARTIAL": 3,
    "NOT_RUN": 4,
    "CURRENT": 5,
    "NO_MANUSCRIPT": 6,
    "BLOCKED": 7,
    "RUNNING": 8,
}


class WriterService:
    def __init__(self, database: Database, settings: RuntimeSettings | None = None) -> None:
        self.database = database
        self.settings = settings or RuntimeSettings()

    def workspace(self) -> dict[str, Any]:
        with self.database.session() as session:
            application = session.get(Application, "writer")
            status = session.get(AdapterStatus, "adapter-app-writer")
            rows = session.scalars(
                select(IntegrationRecord)
                .where(
                    IntegrationRecord.application_id == "writer",
                    IntegrationRecord.resource_type == "writer_editing_book",
                    IntegrationRecord.current.is_(True),
                )
                .order_by(desc(IntegrationRecord.source_timestamp), desc(IntegrationRecord.observed_at))
            ).all()
            books = [dict(row.data) for row in rows if isinstance(row.data, dict)]
            books.sort(
                key=lambda book: (
                    _STATUS_RANK.get(str(book.get("status")), 9),
                    (book.get("highest_risk") or {}).get("score", 101),
                    str(book.get("title") or "").casefold(),
                )
            )
            totals = self._totals(books)
            queue = [
                {
                    "project_id": book.get("project_id"),
                    "title": book.get("title"),
                    "status": book.get("status"),
                    "risk_rank": _STATUS_RANK.get(str(book.get("status")), 9),
                    "highest_risk": book.get("highest_risk"),
                    "finding_count": len(book.get("findings_preview") or []),
                    "report_id": book.get("report_id"),
                    "last_checked": book.get("last_checked"),
                }
                for book in books
                if book.get("status") not in {"NO_MANUSCRIPT", "BLOCKED"}
            ]
            generated_at = max(
                (str(book.get("last_checked") or "") for book in books if book.get("last_checked")),
                default=None,
            )
            records = read_records(self.settings.workbench_decisions_path)
            workbench_book = read_workbench_book(self.settings.workbench_preferences_path)
            decision_queue, decision_totals, workbench = build_decision_queue(
                books,
                records,
                workbench_url=self.settings.workbench_url,
                workbench_book=workbench_book,
            )
            decision_counts = decision_summary(records)
            limitations = [
                "Mission Control displays Writer's report; it does not recalculate readability or findings.",
                "NOT_RUN is not zero and not a pass. STALE means the source fingerprint changed after the report.",
                "Metadata, MRI and Strengthen status are shown as not tracked because Editing v1 does not infer them.",
                "The cross-book queue orders presentation only. It does not create an editorial decision.",
                "The decision queue groups Writer findings by code and severity. It is a reading order, not a new score.",
                "Workbench owns Confirm, Dismiss and Defer; Mission Control reads that log and never writes it.",
            ]
            if decision_totals["missing_identity"]:
                limitations.append(
                    "Some Writer findings have no stable identity yet; refresh Writer evidence to include them."
                )
            return {
                "available": bool(status and status.available and application and application.adapter_enabled),
                "detail": status.detail if status else "Writer integration has not been refreshed yet.",
                "error": status.error if status else None,
                "last_checked_at": status.last_checked_at if status else None,
                "generated_at": generated_at,
                "totals": totals,
                "review_queue": queue,
                "decision_queue": decision_queue,
                "decision_totals": {
                    **decision_totals,
                    "confirmed": decision_counts.get("confirmed", 0),
                    "dismissed": decision_counts.get("dismissed", 0),
                    "deferred": decision_counts.get("deferred", 0),
                },
                "workbench": workbench,
                "books": books,
                "limitations": limitations,
            }

    @staticmethod
    def _totals(books: list[dict[str, Any]]) -> dict[str, int]:
        totals = {
            "books": len(books),
            "with_manuscript": 0,
            "audited": 0,
            "current": 0,
            "needs_review": 0,
            "stale": 0,
            "partial": 0,
            "not_run": 0,
            "blocked": 0,
            "no_manuscript": 0,
            "error": 0,
        }
        for book in books:
            status = str(book.get("status") or "").upper()
            if int(book.get("chapters_available") or 0) > 0:
                totals["with_manuscript"] += 1
            if book.get("report_id"):
                totals["audited"] += 1
            key = status.casefold()
            if key in totals:
                totals[key] += 1
        return totals
