"""Read-only projection of book improvement campaigns (ARTIFACT-EXPO-03C, Stage 10).

Mission Control never scores manuscripts and never writes anything. It reads
the Writer-owned campaign records (``<book>/.writer/book-campaigns/``) and
reports process metrics only: campaign lifecycle states, chapter progress,
verification outcomes and author decisions.

These are process metrics, not manuscript-quality scores. No composite is
computed; prose-quality scores, artifact load, self-repair and chapter
improvement stay in their own panels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CAMPAIGN_DIRNAME = ".writer/book-campaigns"

LIMITATIONS = [
    "Process metrics only. They describe campaign activity, not manuscript quality.",
    "More repair attempts is not higher productivity. A generated candidate is not a successful improvement.",
    "Verification-supported means eligible for author review. It is not author approval.",
    "IMPROVED means the author accepted the candidate. It is not application to the manuscript.",
    "No bulk application exists: every manuscript change still needs the explicit per-chapter Apply flow.",
    "Missing providers are evidence gaps, not zeros. Stale chapters are skipped, never silently compared.",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _empty_totals() -> dict[str, int]:
    return {
        "campaigns": 0,
        "reports": 0,
        "runs": 0,
        "chapters_planned": 0,
        "chapters_done": 0,
        "opportunities": 0,
        "verification_supported": 0,
        "improved": 0,
        "regressions_prevented": 0,
        "inconclusive": 0,
        "author_accepted": 0,
        "applied": 0,
        "canonical_changes": 0,
    }


def summarize_campaigns(book_root: str | Path | None) -> dict[str, Any]:
    """Summarize Writer book campaigns under ``book_root``. Read-only."""
    totals = _empty_totals()
    books: list[dict[str, Any]] = []
    unreadable = 0

    root = Path(book_root) if book_root else None
    if root is None or not root.is_dir():
        return {
            "available": False,
            "detail": "Book root is unavailable; no campaign evidence was read.",
            "error": "book root unavailable",
            "totals": totals,
            "books": books,
            "limitations": list(LIMITATIONS),
            "unreadable_files": 0,
        }

    for book_dir in sorted(root.iterdir(), key=lambda p: p.name):
        if not book_dir.is_dir():
            continue
        camp_root = book_dir / ".writer" / "book-campaigns"
        if not camp_root.is_dir():
            continue
        book_totals = _empty_totals()
        campaigns: list[dict[str, Any]] = []
        for path in sorted((camp_root / "campaigns").glob("*.json")) if (camp_root / "campaigns").is_dir() else []:
            data = _load_json(path)
            if data is None:
                unreadable += 1
                continue
            totals["campaigns"] += 1
            book_totals["campaigns"] += 1
            campaigns.append({
                "campaign_id": data.get("campaign_id", path.stem),
                "mode": data.get("mode", "PLAN"),
                "state": data.get("state", "unknown"),
                "chapters": data.get("chapters", []),
                "created_at": data.get("created_at"),
            })
        chapters: dict[str, dict[str, Any]] = {}
        active_runs: list[dict[str, Any]] = []
        for path in sorted((camp_root / "runs").glob("*.json")) if (camp_root / "runs").is_dir() else []:
            data = _load_json(path)
            if data is None:
                unreadable += 1
                continue
            if data.get("state") not in ("COMPLETE", "COMPLETE_WITH_FAILURES", "BLOCKED",
                                         "CANCELLED", "FAILED"):
                active_runs.append({
                    "run_id": data.get("run_id", path.stem),
                    "campaign_id": data.get("campaign_id", ""),
                    "state": data.get("state", "unknown"),
                    "stop_reason": data.get("stop_reason", ""),
                })
        for path in sorted((camp_root / "reports").glob("*.json")) if (camp_root / "reports").is_dir() else []:
            data = _load_json(path)
            if data is None:
                unreadable += 1
                continue
            totals["reports"] += 1
            book_totals["reports"] += 1
            totals["runs"] += 1
            book_totals["runs"] += 1
            for chapter_id, work in (data.get("chapter_work") or {}).items():
                if not isinstance(work, dict):
                    continue
                entry = chapters.setdefault(str(chapter_id), {
                    "chapter_id": str(chapter_id), "status": "unknown",
                    "outcomes": {}, "candidates_made": 0, "model_calls": 0,
                    "report_id": data.get("report_id")})
                if work.get("status") in ("done", "skipped", "blocked"):
                    entry["status"] = work["status"]
                entry["candidates_made"] += int(work.get("candidates_made", 0) or 0)
                entry["model_calls"] += int(work.get("model_calls", 0) or 0)
                for outcome, count in (work.get("outcome_counts") or {}).items():
                    entry["outcomes"][outcome] = int(entry["outcomes"].get(outcome, 0)) + int(count or 0)
            for outcome, count in (data.get("outcome_counts") or {}).items():
                try:
                    count = int(count)
                except (TypeError, ValueError):
                    continue
                totals["opportunities"] += count
                book_totals["opportunities"] += count
                if outcome == "VERIFICATION_SUPPORTED":
                    totals["verification_supported"] += count
                    book_totals["verification_supported"] += count
                elif outcome == "IMPROVED":
                    totals["improved"] += count
                    book_totals["improved"] += count
                elif outcome == "REGRESSION":
                    totals["regressions_prevented"] += count
                    book_totals["regressions_prevented"] += count
                elif outcome in ("INCONCLUSIVE", "REVISION_REQUIRED", "BLOCKED"):
                    totals["inconclusive"] += count
                    book_totals["inconclusive"] += count
            totals["chapters_done"] += int(data.get("chapters_done", 0) or 0)
            book_totals["chapters_done"] += int(data.get("chapters_done", 0) or 0)
            for opp in (data.get("opportunities") or {}).values() if isinstance(data.get("opportunities"), dict) else []:
                for decision in (opp or {}).get("author_decisions", []) if isinstance(opp, dict) else []:
                    if isinstance(decision, dict) and decision.get("decision") == "AUTHOR_ACCEPTED":
                        totals["author_accepted"] += 1
                        book_totals["author_accepted"] += 1
            if data.get("canonical_untouched") is False:
                totals["canonical_changes"] += 1
                book_totals["canonical_changes"] += 1
        books.append({
            "book_id": book_dir.name,
            "campaign_root": camp_root.as_posix(),
            "totals": book_totals,
            "campaigns": campaigns,
            "chapters": sorted(chapters.values(), key=lambda c: str(c["chapter_id"])),
            "active_runs": active_runs,
        })

    detail = (
        f"Read {totals['campaigns']} campaign(s) with {totals['runs']} run report(s) "
        f"across {len(books)} book(s) with campaign evidence. "
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


__all__ = ["summarize_campaigns", "LIMITATIONS"]
