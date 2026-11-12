"""Read-only strategy-evolution projection (ARTIFACT-EXPO-03E, Stage 14).

Reads Writer's strategy registry, proposals, experiments, reports and
decisions. No model calls, no writes. Process metrics only: versions and
verdicts are reported with their evidence state, never ranked into a
single evolution score. Test and production populations are never mixed
(the index below reads only versioned comparison records, not ad-hoc runs).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LIMITATIONS = [
    "Process metrics only. They describe experimental activity, not manuscript quality.",
    "Experiment verdicts are evidence, not promotion: NEEDS_MORE_EVIDENCE and INCONCLUSIVE are valid terminal states.",
    "Small samples dominate; agreement rates are descriptive, never proof of superiority.",
    "No composite evolution score exists; native quality metrics stay independent.",
    "Test and production strategy use are never mixed in these counts.",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _empty_totals() -> dict[str, int]:
    return {
        "versions": 0,
        "experiments": 0,
        "proposals": 0,
        "decisions": 0,
        "paired_cases": 0,
        "candidate_favored": 0,
        "safety_regressions": 0,
    }


def _iter_evo_roots(book_root: Path) -> list[tuple[str, Path]]:
    """Yield (book_id, strategy-evolution dir) pairs."""
    found: list[tuple[str, Path]] = []
    if not book_root.is_dir():
        return found
    for book_dir in sorted(book_root.iterdir()):
        if not book_dir.is_dir():
            continue
        cands = [book_dir / ".writer" / "strategy-evolution"]
        content = book_dir / "content" / "books"
        if content.is_dir():
            cands.extend(b / ".writer" / "strategy-evolution"
                         for b in sorted(content.iterdir()) if b.is_dir())
        for cand in cands:
            if cand.is_dir() and (book_dir.name, cand) not in found:
                found.append((book_dir.name, cand))
    return found


def summarize_strategy_evolution(book_root: str | Path | None) -> dict[str, Any]:
    """Summarize versioned strategies, experiments and decisions. Read-only."""
    totals = _empty_totals()
    books: list[dict[str, Any]] = []
    unreadable = 0

    root = Path(book_root) if book_root else None
    if root is None or not root.is_dir():
        return {
            "available": False,
            "detail": "Book root is unavailable; no strategy-evolution evidence was read.",
            "error": "book root unavailable",
            "totals": totals,
            "versions": [],
            "proposals": [],
            "experiments": [],
            "decisions": [],
            "books": books,
            "limitations": list(LIMITATIONS),
            "unreadable_files": 0,
        }

    versions: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    experiments: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for book_id, evo_root in _iter_evo_roots(root):
        book_versions: list[dict[str, Any]] = []
        for path in sorted((evo_root / "strategies").glob("*.json")) if (evo_root / "strategies").is_dir() else []:
            data = _load_json(path)
            if data is None:
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    unreadable += 1
                continue
            data["book_id"] = book_id
            versions.append(data)
            book_versions.append(data)
            totals["versions"] += 1
        for path in sorted((evo_root / "proposals").glob("*.json")) if (evo_root / "proposals").is_dir() else []:
            if path.stem.endswith("--validation"):
                continue
            data = _load_json(path)
            if data is None:
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    unreadable += 1
                continue
            data["book_id"] = book_id
            proposals.append({"proposal_id": path.stem, **data})
            totals["proposals"] += 1
        for path in sorted((evo_root / "experiments").glob("*.json")) if (evo_root / "experiments").is_dir() else []:
            data = _load_json(path)
            if data is None:
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    unreadable += 1
                continue
            data["book_id"] = book_id
            experiments.append(data)
            totals["experiments"] += 1
        for path in sorted((evo_root / "decisions").glob("*.json")) if (evo_root / "decisions").is_dir() else []:
            data = _load_json(path)
            if data is None:
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    unreadable += 1
                continue
            data["book_id"] = book_id
            decisions.append(data)
            totals["decisions"] += 1
        for path in sorted((evo_root / "reports").glob("*.json")) if (evo_root / "reports").is_dir() else []:
            data = _load_json(path)
            if data is None:
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    unreadable += 1
                continue
            agg = data.get("aggregate", {}) or {}
            totals["paired_cases"] += int(agg.get("cases", 0) or 0)
            totals["candidate_favored"] += int(agg.get("by_verdict", {}).get("CANDIDATE_FAVORED", 0) or 0)
            totals["safety_regressions"] += int(agg.get("safety_regressions", 0) or 0)
        books.append({"book_id": book_id, "versions": len(book_versions)})

    detail = (
        f"Read {totals['versions']} strategy version(s), {totals['experiments']} "
        f"experiment(s), {totals['proposals']} proposal(s) and {totals['decisions']} "
        f"decision(s) across {len(books)} book(s). "
        f"{totals['paired_cases']} paired case(s), "
        f"{totals['safety_regressions']} safety regression(s)."
    )
    return {
        "available": True,
        "detail": detail,
        "error": None,
        "totals": totals,
        "versions": versions,
        "proposals": proposals,
        "experiments": experiments,
        "decisions": decisions,
        "books": books,
        "limitations": list(LIMITATIONS),
        "unreadable_files": unreadable,
    }


__all__ = ["summarize_strategy_evolution", "LIMITATIONS"]
