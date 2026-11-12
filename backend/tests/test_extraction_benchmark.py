"""Deterministic benchmark metrics tests (04A-03C preparation)."""

from __future__ import annotations

import json
from pathlib import Path

from mission_control.technical import benchmark as bench


FIXTURES = Path(__file__).parent / "fixtures" / "pilot_04a03"


def test_manifest_spans_are_computed_and_frozen():
    manifest = bench.load_json(FIXTURES / "manifest.json")
    assert manifest["status"] == "PREPARED_NO_LIVE_CALLS"
    assert set(manifest["chapters"]) == {"12-chapter.md", "44-chapter.md", "25-chapter.md"}
    for chapter_id, entry in manifest["chapters"].items():
        assert entry["frozen"] is True
        assert len(entry["source_hash"]) == 64
        assert entry["region_count"] == len(entry["regions"]) > 0
    passages = bench.load_json(FIXTURES / "passages.json")
    assert passages["count"] == 24
    for passage in passages["passages"]:
        assert passage["label_provenance"] == "ai_draft_awaiting_human_review"
        lo, hi = passage["char_span"]
        assert 0 <= lo < hi
        assert len(passage["text"]) > 100


def _claim(cid, text, excerpt, **kw):
    rec = {"id": cid, "claim_text": text, "source_excerpt": excerpt,
           "anchor_method": "exact", "quote_validated": True,
           "source_char_start": 0, "source_char_end": 10,
           "source_start_line": 1, "source_end_line": 1}
    rec.update(kw)
    return rec


def test_automated_metrics_counts_and_never_guesses():
    claims = [
        _claim("a", "Alpha holds.", "Excerpt one.", source_char_start=0, source_char_end=12),
        _claim("a", "Alpha holds.", "Excerpt two.", source_char_start=50, source_char_end=70),
        _claim("b", "Beta fails.", "Excerpt three.", anchor_method="normalized"),
        _claim("c", "Gamma unknown.", "Excerpt four.", anchor_method="none", quote_validated=False,
               source_char_start=None, source_char_end=None,
               source_start_line=None, source_end_line=None),
    ]
    passages = [{"passage_id": "P1", "char_span": [0, 30], "draft_label": {"n_assertions": 2}},
                {"passage_id": "P2", "char_span": [1000, 2000], "draft_label": {"n_assertions": 1}}]
    metrics = bench.automated_metrics(passages, claims)
    assert metrics["claims_total"] == 4
    assert metrics["anchored"] == 3
    assert metrics["unanchored"] == 1
    assert metrics["quote_validity_rate"] == 0.75
    assert metrics["duplicate_candidate_pairs"] == 1
    assert metrics["passages_touched"] == 1
    assert metrics["anchored_with_lines"] == 3


def test_adjudicated_metrics_excludes_unassessed():
    claims = [_claim("c1", "Alpha holds.", "Q1"), _claim("c2", "Beta fails.", "Q2")]
    passages = [{"passage_id": "P1", "char_span": [0, 30], "draft_label": {"n_assertions": 2}}]
    adjudications = [{"claim_id": "c1", "passage_id": "P1", "verdict": "supports"}]
    metrics = bench.adjudicated_metrics(passages, claims, adjudications)
    assert metrics["claims_assessed"] == 1
    assert metrics["claims_unassessed"] == 1
    assert metrics["precision_supports"] == 1.0
    assert "unassessed" in metrics["recall_note"]
    assert metrics["labelled_assertions"] == 2


def test_bad_verdicts_ignored_not_counted():
    claims = [_claim("c1", "Alpha holds.", "Q1")]
    passages = [{"passage_id": "P1", "char_span": [0, 30], "draft_label": {"n_assertions": 1}}]
    adjudications = [{"claim_id": "c1", "passage_id": "P1", "verdict": "maybe"}]
    metrics = bench.adjudicated_metrics(passages, claims, adjudications)
    assert metrics["claims_assessed"] == 0
    assert metrics["claims_unassessed"] == 1


def test_comparison_report_keeps_nulls():
    report = bench.comparison_report({"a": 1}, {"a": 2, "b": None})
    assert report["metrics"]["a"] == {"A": 1, "B": 2}
    assert report["metrics"]["b"] == {"A": None, "B": None}
