"""Read-only self-repair summary: process metrics, never scores."""

from __future__ import annotations

import json
from pathlib import Path

from mission_control.writer.self_repair import summarize_self_repair


def _contract(path: Path, *, status: str = "APPROVED", chapter: str = "01-chapter.md") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "contract_id": path.stem,
        "schema_version": "exp-contract-v1",
        "current_version": 1,
        "versions": [{
            "version": 1,
            "status": status,
            "content_hash": "ab" * 32 if status == "APPROVED" else None,
            "payload": {"chapter_id": chapter, "region": {}},
            "reviews": [],
        }],
    }), encoding="utf-8")


def _run(path: Path, *, contract_id: str, attempts: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "run_id": path.parent.name,
        "contract_id": contract_id,
        "disposition": "REVISION_REQUIRED",
        "canonical_untouched": True,
        "attempts": attempts,
        "author_decisions": [],
    }), encoding="utf-8")


def test_empty_book_root_is_available_with_zero_counts(tmp_path: Path) -> None:
    summary = summarize_self_repair(tmp_path / "books")
    assert summary["available"] is False
    assert summary["totals"]["contracts"] == 0


def test_counts_contracts_runs_and_gate_outcomes(tmp_path: Path) -> None:
    book = tmp_path / "books" / "inference"
    _contract(book / ".writer" / "self-repair" / "contracts" / "exp-aaa.json",
              status="APPROVED")
    _contract(book / ".writer" / "self-repair" / "contracts" / "exp-bbb.json",
              status="REVIEW_REQUIRED")
    _run(book / ".writer" / "self-repair" / "runs" / "r1" / "run.json",
         contract_id="exp-aaa", attempts=[
             {"attempt": 1, "status": "FAILED_VERIFICATION", "gates": [
                 {"gate": "A_source", "status": "fail"},
                 {"gate": "B_preservation", "status": "fail"},
                 {"gate": "E_readability", "status": "inconclusive"},
             ]},
             {"attempt": 2, "status": "VERIFICATION_SUPPORTED", "gates": [
                 {"gate": "B_preservation", "status": "pass"},
                 {"gate": "E_readability", "status": "pass"},
             ]},
         ])
    summary = summarize_self_repair(tmp_path / "books")
    assert summary["available"] is True
    totals = summary["totals"]
    assert totals["contracts"] == 2
    assert totals["contracts_awaiting_approval"] == 1
    assert totals["contracts_approved"] == 1
    assert totals["runs"] == 1
    assert totals["attempts"] == 2
    assert totals["verification_supported"] == 1
    assert totals["failed_preservation_gates"] == 1
    assert totals["inconclusive_comparisons"] == 1
    assert totals["author_accepted"] == 0
    assert totals["applied"] == 0
    assert totals["canonical_changes"] == 0
    assert "not manuscript quality" in " ".join(summary["limitations"]).lower() \
        or "process metrics" in " ".join(summary["limitations"]).lower()


def test_malformed_files_are_skipped_not_fatal(tmp_path: Path) -> None:
    book = tmp_path / "books" / "inference"
    bad = book / ".writer" / "self-repair" / "contracts" / "exp-bad.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json", encoding="utf-8")
    summary = summarize_self_repair(tmp_path / "books")
    assert summary["available"] is True
    assert summary["unreadable_files"] == 1
    assert summary["totals"]["contracts"] == 0


def test_self_repair_endpoint_is_read_only(client) -> None:
    response = client.get("/api/writer/self-repair")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] in (True, False)
    assert "totals" in body and "limitations" in body
    assert body["totals"]["applied"] == 0


def test_workspace_carries_self_repair_summary(client) -> None:
    body = client.get("/api/writer/books").json()
    assert "self_repair" in body
    assert "totals" in body["self_repair"]
