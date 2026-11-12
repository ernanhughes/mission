"""Read-only improvement-intelligence projection (ARTIFACT-EXPO-03D, Stage 10).

Reads Writer's analytical outputs without executing models or writing
anything. Two sources, both file-local:

1. The evidence index is rebuilt from Writer's authoritative run/report
   stores on every call (history is small; no caching, no duplication).
2. Oversized-region rows come from the same chapter-plan records the index
   already reads.

Process metrics only. Scorecard rates carry denominators; small samples are
reported as INSUFFICIENT_EVIDENCE, never ranked. No composite intelligence
score exists anywhere in this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVIDENCE_LEVELS = (
    "INSUFFICIENT_EVIDENCE",
    "EARLY_SIGNAL",
    "COMPARABLE_EVIDENCE",
    "SUBSTANTIAL_EVIDENCE",
)

LIMITATIONS = [
    "Process metrics only. They describe past campaign activity, not manuscript quality.",
    "Scorecard rates carry explicit denominators; a supported candidate is not an author approval.",
    "INSUFFICIENT_EVIDENCE is the honest answer for most segments; it is not a ranking.",
    "Comparisons are observational (roles/chapters were not randomly assigned), never controlled A/B.",
    "Re-evaluation eligibility is advisory; it never schedules work or mutates contracts.",
    "No composite intelligence score exists; native metrics stay independent.",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _empty_totals() -> dict[str, int]:
    return {
        "attempts": 0,
        "evaluated": 0,
        "verification_supported": 0,
        "preservation_failed": 0,
        "contract_failures": 0,
        "skipped_oversized": 0,
        "eligible_reevaluations": 0,
    }


def _iter_book_writers(book_root: Path) -> list[tuple[str, Path]]:
    """Yield (book_id, <book>/.writer) dirs.

    Mission's book_root contains book dirs directly (C:/books/inference,
    C:/books/jev, ...); each book may keep its .writer at top level and/or
    under content/books/<book>/.writer (Inference layout).
    """
    found: list[tuple[str, Path]] = []
    if not book_root.is_dir():
        return found
    for book_dir in sorted(book_root.iterdir()):
        if not book_dir.is_dir():
            continue
        cands = [book_dir / ".writer"]
        content = book_dir / "content" / "books"
        if content.is_dir():
            cands.extend(sorted(b / ".writer" for b in content.iterdir() if b.is_dir()))
        for cand in cands:
            if (cand / "chapter-improvement").is_dir() and (book_dir.name, cand) not in found:
                found.append((book_dir.name, cand))
    return found


def _read_book_reports(writer_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted((writer_root / "book-campaigns" / "reports").glob("*.json")):
        data = _load_json(path)
        if data is not None:
            out.append(data)
    return out


def _read_chapter_runs(writer_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    base = writer_root / "chapter-improvement"
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*.json")):
        if path.name == "model_calls.json":
            continue
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        opps = data.get("opportunities")
        if isinstance(opps, dict) and isinstance(data.get("run_id"), str):
            data["_source"] = str(path)
            out.append(data)
    return out


def _rows(chapter_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten run records to attempt rows (mirror of Writer's index, dependency-free).

    Mission must not import Writer code; this re-derives the same analytical
    classes with a fraction of the detail. Full rows live behind the Writer
    intel API; this summary carries only what the dashboard renders.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in chapter_runs:
        run_id = str(record.get("run_id", ""))
        chapter_id = str(record.get("chapter_id", ""))
        for opp_id, opp in (record.get("opportunities") or {}).items():
            if not isinstance(opp, dict):
                continue
            strategy = str(opp.get("strategy", ""))
            attempts = opp.get("attempts") or []
            if attempts:
                for index, attempt in enumerate(attempts):
                    if not isinstance(attempt, dict):
                        continue
                    key = "|".join((run_id, str(opp.get("opportunity_id") or opp_id), str(index)))
                    if key in seen:
                        continue
                    seen.add(key)
                    disposition = str(attempt.get("disposition", ""))
                    rows.append({
                        "row_id": key,
                        "chapter_id": chapter_id,
                        "strategy": strategy,
                        "outcome": disposition,
                        "class": _classify(disposition, bool(opp.get("outcome") == "IMPROVED")),
                        "model": _attempt_model(attempt),
                        "model_calls": int(attempt.get("model_calls", 0) or 0),
                        "failed_gates": sorted(str(g.get("gate", "")) for g in
                                               ((attempt.get("verification") or {}).get("gates", []) or [])
                                               if isinstance(g, dict) and g.get("status") in ("fail", "blocked", "error")),
                        "note": str(attempt.get("note", "") or "")[:200],
                    })
            else:
                outcome = str(opp.get("outcome") or opp.get("status") or "")
                key = "|".join((run_id, str(opp.get("opportunity_id") or opp_id), "no-attempt"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "row_id": key,
                    "chapter_id": chapter_id,
                    "strategy": strategy,
                    "outcome": outcome,
                    "class": _classify(outcome, False),
                    "model": "",
                    "model_calls": 0,
                    "failed_gates": [],
                    "note": str(opp.get("note", "") or "")[:200],
                })
    return rows


def _classify(disposition: str, improved: bool) -> str:
    upper = (disposition or "").strip().upper()
    mapping = {
        "VERIFICATION_SUPPORTED": "VERIFICATION_SUPPORTED",
        "REGRESSION": "PRESERVATION_FAILED",
        "NO_MEANINGFUL_IMPROVEMENT": "NO_MEANINGFUL_IMPROVEMENT",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "REVISION_REQUIRED": "REVISION_REQUIRED",
        "BLOCKED": "BLOCKED",
    }
    if improved or upper == "IMPROVED":
        return "AUTHOR_ACCEPTED"
    return mapping.get(upper, "UNKNOWN")


def _attempt_model(attempt: dict[str, Any]) -> str:
    verification = attempt.get("verification") if isinstance(attempt.get("verification"), dict) else {}
    provenance = attempt.get("provenance") if isinstance(attempt.get("provenance"), dict) else {}
    run_dirs = [verification.get("run_dir"), provenance.get("engine_run_dir")]
    for path in run_dirs:
        if not isinstance(path, str) or not path:
            continue
        data = _load_json(Path(path) / "run.json")
        if isinstance(data, dict):
            for section in ("candidate", "plan"):
                part = data.get(section)
                if isinstance(part, dict) and part.get("model"):
                    return str(part["model"])
        summary = _load_json(Path(path) / "summary.json")
        if isinstance(summary, dict) and summary.get("model"):
            return str(summary["model"])
    return ""


def summarize_intel(book_root: str | Path | None) -> dict[str, Any]:
    """Summarize improvement intelligence across book .writer dirs. Read-only."""
    totals = _empty_totals()
    books: list[dict[str, Any]] = []
    unreadable = 0
    failures: dict[str, int] = {}

    root = Path(book_root) if book_root else None
    if root is None or not root.is_dir():
        return {
            "available": False,
            "detail": "Book root is unavailable; no intelligence evidence was read.",
            "error": "book root unavailable",
            "totals": totals,
            "strategies": [],
            "models": [],
            "failures": [],
            "reevaluations": [],
            "oversized": [],
            "books": books,
            "limitations": list(LIMITATIONS),
            "unreadable_files": 0,
        }

    for book_id, writer_root in _iter_book_writers(root):
        runs = _read_chapter_runs(writer_root)
        rows = _rows(runs)
        strategies: dict[str, dict[str, int]] = {}
        for row in rows:
            totals["attempts"] += 1
            totals["evaluated"] += 1 if row["class"] in (
                "VERIFICATION_SUPPORTED", "PRESERVATION_FAILED",
                "NO_MEANINGFUL_IMPROVEMENT", "INCONCLUSIVE", "REVISION_REQUIRED") else 0
            card = strategies.setdefault(row["strategy"] or "unknown",
                                         {"attempts": 0, "evaluated": 0, "supported": 0,
                                          "preservation_failed": 0, "no_improvement": 0,
                                          "inconclusive": 0})
            card["attempts"] += 1
            if row["class"] in ("VERIFICATION_SUPPORTED", "PRESERVATION_FAILED",
                                "NO_MEANINGFUL_IMPROVEMENT", "INCONCLUSIVE", "REVISION_REQUIRED"):
                card["evaluated"] += 1
            if row["class"] == "VERIFICATION_SUPPORTED":
                card["supported"] += 1
                totals["verification_supported"] += 1
            elif row["class"] == "PRESERVATION_FAILED":
                card["preservation_failed"] += 1
                totals["preservation_failed"] += 1
                failures["technical_preservation"] = failures.get("technical_preservation", 0) + 1
            elif row["class"] == "NO_MEANINGFUL_IMPROVEMENT":
                card["no_improvement"] += 1
                failures["explanation_quality"] = failures.get("explanation_quality", 0) + 1
            elif row["class"] == "INCONCLUSIVE":
                card["inconclusive"] += 1
                failures["evaluation"] = failures.get("evaluation", 0) + 1
            elif row["class"] == "BLOCKED":
                failures["contract_or_execution"] = failures.get("contract_or_execution", 0) + 1
                if "contract" in row["note"].lower():
                    totals["contract_failures"] += 1
            role = "candidate_generation"
            key = (row["model"] or "unknown", role)
        oversized: list[dict[str, Any]] = []
        plans_base = writer_root / "chapter-improvement" / "plans"
        if plans_base.is_dir():
            for path in sorted(plans_base.glob("*.json")):
                data = _load_json(path)
                if data is None:
                    try:
                        json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        unreadable += 1
                    continue
                if not isinstance(data.get("items"), list):
                    continue
                for entry in data.get("skipped") or []:
                    if not isinstance(entry, dict):
                        continue
                    reason = str(entry.get("reason", ""))
                    if "region spans" in reason and "budget max" in reason:
                        totals["skipped_oversized"] += 1
                        oversized.append({
                            "chapter_id": str(data.get("chapter_id", "")),
                            "opportunity_id": str(entry.get("opportunity_id", "")),
                            "reason": reason[:200],
                            "plan_id": str(data.get("plan_id", path.stem)),
                        })
        books.append({
            "book_id": book_id,
            "attempts": len(rows),
            "strategies": [{"strategy": name, **counts} for name, counts in sorted(strategies.items())],
            "oversized": oversized,
        })

    strategy_cards = []
    for book in books:
        for card in book.pop("strategies"):
            card["book_id"] = book["book_id"]
            evaluated = card["evaluated"]
            card["support_rate"] = round(card["supported"] / evaluated, 3) if evaluated else None
            card["evidence_level"] = ("INSUFFICIENT_EVIDENCE" if evaluated <= 1
                                      else "EARLY_SIGNAL" if evaluated <= 4
                                      else "COMPARABLE_EVIDENCE" if evaluated <= 11
                                      else "SUBSTANTIAL_EVIDENCE")
            card["denominator"] = "supported / evaluated attempts"
            strategy_cards.append(card)
    model_cards = _global_models(root)

    detail = (
        f"Read {totals['attempts']} attempt row(s) across {len(books)} book(s). "
        f"{totals['verification_supported']} verification-supported, "
        f"{totals['preservation_failed']} preservation failure(s), "
        f"{totals['skipped_oversized']} oversized skip(s)."
    )
    return {
        "available": True,
        "detail": detail,
        "error": None,
        "totals": totals,
        "strategies": strategy_cards,
        "models": model_cards,
        "failures": [{"family": name, "attempts": count,
                      "sample_limitation": "descriptive, not causal"}
                     for name, count in sorted(failures.items())],
        "reevaluations": [],
        "oversized": [o for b in books for o in b.get("oversized", [])],
        "books": [{"book_id": b["book_id"], "attempts": b["attempts"],
                   "oversized": len(b.get("oversized", []))} for b in books],
        "limitations": list(LIMITATIONS),
        "unreadable_files": unreadable,
    }


def _global_models(book_root: Path) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str], dict[str, int]] = {}
    for _book_id, writer_root in _iter_book_writers(book_root):
        for row in _rows(_read_chapter_runs(writer_root)):
            key = (row["model"] or "unknown", "candidate_generation")
            entry = totals.setdefault(key, {"attempts": 0, "evaluated": 0, "supported": 0})
            entry["attempts"] += 1
            if row["class"] in ("VERIFICATION_SUPPORTED", "PRESERVATION_FAILED",
                                "NO_MEANINGFUL_IMPROVEMENT", "INCONCLUSIVE", "REVISION_REQUIRED"):
                entry["evaluated"] += 1
            if row["class"] == "VERIFICATION_SUPPORTED":
                entry["supported"] += 1
    return [{"model": model, "role": role, "attempts": c["attempts"],
             "evaluated": c["evaluated"], "supported": c["supported"],
             "denominator": "observational; roles/chapters not randomly assigned",
             "evidence_level": ("INSUFFICIENT_EVIDENCE" if c["evaluated"] <= 1
                                else "EARLY_SIGNAL" if c["evaluated"] <= 4
                                else "COMPARABLE_EVIDENCE" if c["evaluated"] <= 11
                                else "SUBSTANTIAL_EVIDENCE")}
            for (model, role), c in sorted(totals.items())]


__all__ = ["summarize_intel", "LIMITATIONS"]
