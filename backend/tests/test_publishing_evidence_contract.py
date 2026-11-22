"""Contract tests: unknown stays unknown, invalid verdicts rejected."""

import pytest

from mission_control.publication.evidence import (
    EvidenceItem,
    unknown_evidence,
)


def test_unknown_is_neither_pass_nor_fail() -> None:
    item = unknown_evidence("book-math", "manuscript_integrity", "writer")
    assert item.result == "unknown"
    assert item.freshness == "unknown"
    assert item.result not in {"passed", "failed"}
    assert item.to_dict()["evidence_type"] == "manuscript_integrity"


def test_invalid_result_rejected() -> None:
    with pytest.raises(ValueError):
        EvidenceItem(
            book_id="book-math",
            evidence_type="qc",
            source_system="writer",
            result="ready",  # type: ignore[arg-type]
        )


def test_invalid_freshness_rejected() -> None:
    with pytest.raises(ValueError):
        EvidenceItem(
            book_id="book-math",
            evidence_type="qc",
            source_system="writer",
            freshness="fresh",  # type: ignore[arg-type]
        )


def test_stale_does_not_rewrite_verdict() -> None:
    item = EvidenceItem(
        book_id="book-math",
        evidence_type="qc",
        source_system="writer",
        result="passed",
        freshness="stale",
    )
    assert item.result == "passed"
    assert item.freshness == "stale"
