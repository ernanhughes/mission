"""Read-only projection of contract-gated self-repair progress (ARTIFACT-EXPO-03A, Stage 08).

Mission Control never scores manuscripts here and never writes anything. It
reads the Writer-owned self-repair evidence (``<book>/.writer/self-repair/``)
and reports process metrics only: how many contracts exist, how many runs
were attempted, what the independent gates said, and what the author decided.

These are process metrics, not manuscript-quality scores. More attempts does
not mean higher productivity, and a generated candidate is never counted as
a successful improvement. Verification-supported is not author-approved,
author-approved is not applied, and model-assessed readability is supporting
evidence, never proof.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SELF_REPAIR_DIRNAME = ".writer/self-repair"
CONTRACTS_SUBDIR = "contracts"
RUNS_SUBDIR = "runs"

APPROVED_STATUSES = {"APPROVED"}
AWAITING_STATUSES = {"DRAFT", "REVIEW_REQUIRED"}

LIMITATIONS = [
    "Process metrics only. They describe repair activity, not manuscript quality.",
    "More repair attempts is not higher productivity. A generated candidate is not a successful improvement.",
    "Verification-supported means eligible for author review. It is not author approval.",
    "Author-approved means the author accepted the candidate. It is not application to the manuscript.",
    "Application to the manuscript is Workbench-owned; Mission Control counts 0 applied until Workbench exposes apply receipts.",
    "Model-assessed readability is supporting evidence, never proof of human-reader benefit.",
]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _contract_chapter(contract: dict[str, Any]) -> str:
    versions = contract.get("versions") or []
    current = contract.get("current_version", 1)
    chosen = next((v for v in versions if v.get("version") == current), None)
    if not isinstance(chosen, dict) and versions:
        chosen = versions[-1]
    payload = (chosen or {}).get("payload") if isinstance(chosen, dict) else None
    if isinstance(payload, dict):
        chapter = str(payload.get("chapter_id") or "")
        if chapter:
            return chapter
    return "unknown"


def _contract_status(contract: dict[str, Any]) -> str:
    versions = contract.get("versions") or []
    current = contract.get("current_version", 1)
    chosen = next((v for v in versions if v.get("version") == current), None)
    if not isinstance(chosen, dict) and versions:
        chosen = versions[-1]
    if isinstance(chosen, dict):
        return str(chosen.get("status") or "unknown")
    return "unknown"


def _empty_totals() -> dict[str, int]:
    return {
        "contracts": 0,
        "contracts_awaiting_approval": 0,
        "contracts_approved": 0,
        "runs": 0,
        "attempts": 0,
        "verification_supported": 0,
        "failed_preservation_gates": 0,
        "inconclusive_comparisons": 0,
        "author_accepted": 0,
        "applied": 0,
        "canonical_changes": 0,
    }


def summarize_self_repair(book_root: str | Path | None) -> dict[str, Any]:
    """Summarize Writer self-repair evidence under ``book_root``. Read-only.

    Every book directory directly under ``book_root`` is scanned for
    ``.writer/self-repair/contracts/*.json`` and ``runs/*/run.json``.
    Unreadable files are skipped and counted as ``unreadable_files``; they
    never fail the summary.
    """
    totals = _empty_totals()
    books: list[dict[str, Any]] = []
    unreadable = 0

    root = Path(book_root) if book_root else None
    if root is None or not root.is_dir():
        return {
            "available": False,
            "detail": "Book root is unavailable; no self-repair evidence was read.",
            "error": "book root unavailable",
            "totals": totals,
            "books": books,
            "limitations": list(LIMITATIONS),
            "unreadable_files": 0,
        }

    for book_dir in sorted(root.iterdir(), key=lambda p: p.name):
        if not book_dir.is_dir():
            continue
        sr_root = book_dir / ".writer" / "self-repair"
        if not sr_root.is_dir():
            continue
        contracts_dir = sr_root / CONTRACTS_SUBDIR
        runs_dir = sr_root / RUNS_SUBDIR

        contracts: dict[str, dict[str, Any]] = {}
        if contracts_dir.is_dir():
            for path in sorted(contracts_dir.glob("*.json")):
                data = _load_json(path)
                if data is None or not data.get("contract_id"):
                    unreadable += 1
                    continue
                contracts[str(data["contract_id"])] = data
                totals["contracts"] += 1
                status = _contract_status(data)
                if status in AWAITING_STATUSES:
                    totals["contracts_awaiting_approval"] += 1
                elif status in APPROVED_STATUSES:
                    totals["contracts_approved"] += 1

        book_totals = _empty_totals()
        book_totals["contracts"] = sum(1 for _ in contracts)
        chapters: dict[str, dict[str, Any]] = {}
        for contract in contracts.values():
            chapter = _contract_chapter(contract)
            entry = chapters.setdefault(
                chapter,
                {"chapter_id": chapter, "contracts": 0, "runs": 0, "attempts": 0,
                 "verification_supported": 0, "author_accepted": 0,
                 "canonical_changes": 0},
            )
            entry["contracts"] += 1
            status = _contract_status(contract)
            if status in AWAITING_STATUSES:
                book_totals["contracts_awaiting_approval"] += 1
            elif status in APPROVED_STATUSES:
                book_totals["contracts_approved"] += 1
        book_totals["contracts"] = len(contracts)

        runs_seen = 0
        if runs_dir.is_dir():
            for run_file in sorted(runs_dir.glob("*/run.json")):
                data = _load_json(run_file)
                if data is None:
                    unreadable += 1
                    continue
                runs_seen += 1
                totals["runs"] += 1
                book_totals["runs"] += 1
                attempts = data.get("attempts") or []
                chapter = "unknown"
                contract_id = str(data.get("contract_id") or "")
                if contract_id in contracts:
                    chapter = _contract_chapter(contracts[contract_id])
                entry = chapters.setdefault(
                    chapter,
                    {"chapter_id": chapter, "contracts": 0, "runs": 0, "attempts": 0,
                     "verification_supported": 0, "author_accepted": 0,
                     "canonical_changes": 0},
                )
                entry["runs"] += 1
                totals["attempts"] += len(attempts)
                book_totals["attempts"] += len(attempts)
                entry["attempts"] += len(attempts)
                for attempt in attempts:
                    if not isinstance(attempt, dict):
                        continue
                    if attempt.get("status") == "VERIFICATION_SUPPORTED":
                        totals["verification_supported"] += 1
                        book_totals["verification_supported"] += 1
                        entry["verification_supported"] += 1
                    gates = attempt.get("gates") or []
                    gate_map = {g.get("gate"): g.get("status") for g in gates
                                if isinstance(g, dict)}
                    if gate_map.get("B_preservation") == "fail":
                        totals["failed_preservation_gates"] += 1
                        book_totals["failed_preservation_gates"] += 1
                    if gate_map.get("E_readability") == "inconclusive":
                        totals["inconclusive_comparisons"] += 1
                        book_totals["inconclusive_comparisons"] += 1
                for decision in data.get("author_decisions") or []:
                    if isinstance(decision, dict) and decision.get("decision") == "AUTHOR_ACCEPTED":
                        totals["author_accepted"] += 1
                        book_totals["author_accepted"] += 1
                        entry["author_accepted"] += 1
                # Application happens only through the explicit Workbench Apply
                # flow; the run record has no applied state, so applied stays 0.
                # Canonical edits would be a safety violation: count any run
                # that does not assert candidate-only operation.
                if data.get("canonical_untouched") is False:
                    totals["canonical_changes"] += 1
                    book_totals["canonical_changes"] += 1
                    entry["canonical_changes"] += 1

        books.append({
            "book_id": book_dir.name,
            "self_repair_root": sr_root.as_posix(),
            "totals": book_totals,
            "chapters": sorted(chapters.values(), key=lambda c: str(c["chapter_id"])),
        })

    detail = (
        f"Read {totals['contracts']} contract(s) "
        f"({totals['contracts_awaiting_approval']} awaiting approval) and "
        f"{totals['runs']} run(s) with {totals['attempts']} attempt(s) "
        f"across {len(books)} book(s) with self-repair evidence. "
        f"{totals['verification_supported']} verification-supported candidate(s), "
        f"{totals['author_accepted']} author-accepted, "
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


__all__ = ["summarize_self_repair", "LIMITATIONS"]
