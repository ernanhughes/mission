"""MC-QUALITY-04A-04-00 Workstream F: benchmark reference-review workflow tests."""

import pytest

from mission_control.technical import benchmark as bench


def _passage(**over):
    packet = {"passage_id": "P12-1", "chapter_id": "12-chapter.md",
              "char_span": [4, 9], "text": "quick",
              "label_provenance": "ai_draft_awaiting_human_review",
              "draft_label": {"n_assertions": 2}}
    packet.update(over)
    return packet


def test_packet_slices_without_paraphrase():
    chapter = "The quick brown fox.\n\nAnother paragraph here.\n"
    packet = bench.build_review_packet(_passage(), chapter, live_revision="rev")
    assert packet["frozen_text"] == "quick"
    assert packet["integrity"]["text_matches_frozen_span"] is True
    assert packet["integrity"]["excerpt_anchored"] is True
    assert packet["status"] == "AWAITING_REVIEW"
    assert packet["reviews"] == []
    assert "quick" in packet["surrounding_source_context"]["text"]


def test_packet_flags_stale_or_mismatched_passage():
    chapter = "Entirely different words here.\n"
    packet = bench.build_review_packet(_passage(), chapter, live_revision="rev")
    assert packet["integrity"]["text_matches_frozen_span"] is False
    assert packet["integrity"]["excerpt_anchored"] is False
    assert packet["surrounding_source_context"]["text"] == ""


def test_packet_flags_out_of_range_span():
    chapter = "short\n"
    packet = bench.build_review_packet(_passage(char_span=[0, 5000]), chapter,
                                       live_revision="rev")
    assert packet["integrity"]["span_in_range"] is False


def test_verdict_vocabulary_enforced():
    packet = bench.build_review_packet(_passage(), "The quick brown fox.\n", live_revision="r")
    with pytest.raises(ValueError):
        bench.record_review_verdict(packet, verdict="LOOKS_GOOD", reviewer="human:ann")
    with pytest.raises(ValueError):
        bench.record_review_verdict(packet, verdict="ACCEPT_LABEL", reviewer="  ")


def test_human_provenance_requires_human_reviewer():
    packet = bench.build_review_packet(_passage(), "The quick brown fox.\n", live_revision="r")
    human = bench.record_review_verdict(packet, verdict="ACCEPT_LABEL",
                                        reviewer="human:ann", rationale="exact")
    assert human["reviews"][0]["reviewer_provenance"] == "HUMAN_REVIEW"
    assert human["status"] == "HUMAN_REVIEWED"
    agent = bench.record_review_verdict(packet, verdict="ACCEPT_LABEL",
                                        reviewer="ai_assisted:pi")
    assert agent["reviews"][0]["reviewer_provenance"] == "AI_ASSISTED_REVIEW"
    assert agent["status"] == "AI_ASSISTED_REVIEW"


def test_disagreement_preserved_not_merged():
    packet = bench.build_review_packet(_passage(), "The quick brown fox.\n", live_revision="r")
    once = bench.record_review_verdict(packet, verdict="ACCEPT_LABEL", reviewer="human:ann")
    twice = bench.record_review_verdict(once, verdict="REJECT_LABEL", reviewer="human:bob")
    assert [r["verdict"] for r in twice["reviews"]] == ["ACCEPT_LABEL", "REJECT_LABEL"]
    assert twice["status"] == "HUMAN_REVIEWED"


def test_status_counts_and_not_measured_without_humans():
    packets = [bench.build_review_packet(_passage(passage_id="P%d" % i),
                                         "The quick brown fox.\n", live_revision="r")
               for i in range(3)]
    status = bench.review_status(packets)
    assert status == {"packets_total": 3, "by_status": {"AWAITING_REVIEW": 3},
                      "precision": "NOT_MEASURED", "recall": "NOT_MEASURED",
                      "note": status["note"]}
    judged = bench.adjudicated_metrics([], [], [])
    assert judged["precision_supports"] is None
