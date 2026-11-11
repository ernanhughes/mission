"""Read-only projection of chapter-improvement progress (ARTIFACT-EXPO-03B, Stage 09).

Mission Control never scores manuscripts and never writes anything. It reads
the Writer-owned chapter-improvement reports (``<book>/.writer/
chapter-improvement/reports/``) plus snapshot/plan counts, and reports
process metrics only: how many chapters were snapshotted, planned, attempted,
and what the independent verification and the authors decided.

These are process metrics, not manuscript-quality scores. More attempts does
not mean higher productivity, and a verification-supported candidate is never
counted as a successful improvement. Verification-supported is not
author-approved, author-approved (IMPROVED) is not applied, and
model-assessed readability is supporting evidence, never proof.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IMPROVEMENT_DIRNAME = ".writer/chapter-improvement"

LIMITATIONS = [
    "Process metrics only. They describe improvement activity, not manuscript quality.",
    "More repair attempts is not higher productivity. A verification-supported candidate is not a successful improvement.",
    "Verification-supported means eligible for author review. It is not author approval.",
    "IMPROVED means the author accepted the candidate. It is not application to the manuscript.",
    "Application to the manuscript is Workbench-owned; Mission Control counts 0 applied.",
    "Missing providers are evidence gaps, not zeros. Stale evidence is labeled, never compared.",
    "Prose-quality scores, artifact load and self-repair metrics stay independent; no composite is computed.",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _empty_totals() -> dict[str, int]:
    return {
        "reports": 0,
        "snapshots": 0,
        "plans": 0,
        "runs": 0,
        "opportunities": 0,
        "verification_supported": 0,
        "improved": 0,
        "regressions_prevented": 0,
        "inconclusive": 0,
        "author_accepted": 0,
        "applied": 0,
        "canonical_changes": 0,
    }


def summarize_improvement(book_root: str | Path | None) -> dict[str, Any]:
    """Summarize Writer chapter-improvement reports under ``book_root``. Read-only."""
    totals = _empty_totals()
    books: list[dict[str, Any]] = []
    unreadable = 0

    root = Path(book_root) if book_root else None
    if root is None or not root.is_dir():
        return {
            "available": False,
            "detail": "Book root is unavailable; no improvement evidence was read.",
            "error": "book root unavailable",
            "totals": totals,
            "books": books,
            "limitations": list(LIMITATIONS),
            "unreadable_files": 0,
        }

    for book_dir in sorted(root.iterdir(), key=lambda p: p.name):
        if not book_dir.is_dir():
            continue
        ci_root = book_dir / ".writer" / "chapter-improvement"
        if not ci_root.is_dir():
            continue
        book_totals = _empty_totals()
        chapters: dict[str, dict[str, Any]] = {}

        def chapter_entry(chapter_id: str) -> dict[str, Any]:
            return chapters.setdefault(
                chapter_id,
                {"chapter_id": chapter_id, "snapshots": 0, "plans": 0, "runs": 0,
                 "opportunities": 0, "verification_supported": 0, "improved": 0,
                 "author_accepted": 0, "canonical_changes": 0,
                 "latest_status": "unknown", "latest_report": None},
            )

        for path in sorted((ci_root / "snapshots").glob("*.json")) if (ci_root / "snapshots").is_dir() else []:
            data = _load_json(path)
            if data is None:
                unreadable += 1
                continue
            totals["snapshots"] += 1
            book_totals["snapshots"] += 1
            chapter_entry(str(data.get("chapter_id") or "unknown"))["snapshots"] += 1
        for path in sorted((ci_root / "plans").glob("*.json")) if (ci_root / "plans").is_dir() else []:
            data = _load_json(path)
            if data is None:
                unreadable += 1
                continue
            totals["plans"] += 1
            book_totals["plans"] += 1
            chapter_entry(str(data.get("chapter_id") or "unknown"))["plans"] += 1
        for path in sorted((ci_root / "reports").glob("*.json")) if (ci_root / "reports").is_dir() else []:
            data = _load_json(path)
            if data is None:
                unreadable += 1
                continue
            totals["reports"] += 1
            book_totals["reports"] += 1
            chapter_id = str(data.get("chapter_id") or "unknown")
            entry = chapter_entry(chapter_id)
            totals["runs"] += 1
            book_totals["runs"] += 1
            entry["runs"] += 1
            entry["latest_status"] = str(data.get("status") or "unknown")
            entry["latest_report"] = str(data.get("report_id") or path.stem)
            for outcome, count in (data.get("outcome_counts") or {}).items():
                try:
                    count = int(count)
                except (TypeError, ValueError):
                    continue
                totals["opportunities"] += count
                book_totals["opportunities"] += count
                entry["opportunities"] += count
                if outcome == "VERIFICATION_SUPPORTED":
                    totals["verification_supported"] += count
                    book_totals["verification_supported"] += count
                    entry["verification_supported"] += count
                elif outcome == "IMPROVED":
                    totals["improved"] += count
                    book_totals["improved"] += count
                    entry["improved"] += count
                elif outcome == "REGRESSION":
                    totals["regressions_prevented"] += count
                    book_totals["regressions_prevented"] += count
                elif outcome in ("INCONCLUSIVE", "REVISION_REQUIRED"):
                    totals["inconclusive"] += count
                    book_totals["inconclusive"] += count
            for opp in (data.get("opportunities") or {}).values():
                if not isinstance(opp, dict):
                    continue
                for decision in opp.get("author_decisions") or []:
                    if isinstance(decision, dict) and decision.get("decision") == "AUTHOR_ACCEPTED":
                        totals["author_accepted"] += 1
                        book_totals["author_accepted"] += 1
                        entry["author_accepted"] += 1
            if data.get("canonical_untouched") is False:
                totals["canonical_changes"] += 1
                book_totals["canonical_changes"] += 1
                entry["canonical_changes"] += 1

        books.append({
            "book_id": book_dir.name,
            "improvement_root": ci_root.as_posix(),
            "totals": book_totals,
            "chapters": sorted(chapters.values(), key=lambda c: str(c["chapter_id"])),
        })

    detail = (
        f"Read {totals['reports']} report(s) ({totals['snapshots']} snapshots, "
        f"{totals['plans']} plans) across {len(books)} book(s) with improvement evidence. "
        f"{totals['verification_supported']} verification-supported candidate(s), "
        f"{totals['improved']} author-accepted (IMPROVED), "
        f"{totals['regressions_prevented']} regression(s) prevented, "
        f"{totals['canonical_changes']} canonical change(s)."
    )
    return {
        "available": True,
        "detail": detail,
        "error": None,
        "totals": totals,
        "books": books,
        "limitations": list(LIMITATIONS),
        "unreadable_files": unreadable,
    }


__all__ = ["summarize_improvement", "LIMITATIONS"]
