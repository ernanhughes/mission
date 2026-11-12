"""MC-QUALITY-04A-02: calibration sampling, packets, stats, workflow."""

from __future__ import annotations

import json
import random

from fastapi.testclient import TestClient

from mission_control.publication import calibration as cal


def _row(**kw):
    base = {"requirement_applicable": "APPLICABLE", "gap_justified": True,
            "priority_proportionate": True, "would_block": False,
            "verdict": "R1:VALID", "reviewer": "human:author",
            "satisfied_by_evidence": "unknown"}
    base.update(kw)
    return base


def test_provenance_and_state_helpers():
    assert cal.reviewer_provenance("human:author") == "HUMAN_REVIEW"
    assert cal.reviewer_provenance("ai_assisted") == "AI_ASSISTED_REVIEW"
    assert cal.reviewer_provenance("ai_assisted:secondary") == "AI_ASSISTED_REVIEW"
    assert cal.reviewer_provenance("deterministic") == "DETERMINISTIC_VALIDATION"
    assert cal.reviewer_provenance("operator") == "AWAITING_REVIEW"
    assert cal.review_state("DEFERRED: waiting on chapter") == "deferred"
    assert cal.review_state("ABSTAINED: unclear scope") == "abstained"
    assert cal.review_state("DRAFT: partial notes") == "draft"
    assert cal.review_state("R1:VALID R2:APPLICABLE") == "completed"
    assert cal.review_state("") == "awaiting"


def test_wilson_interval_known_values():
    empty = cal.wilson_interval(0, 0)
    assert empty == {"rate": None, "low": None, "high": None, "trials": 0}
    full = cal.wilson_interval(10, 10)
    assert full["rate"] == 1.0 and full["low"] < 1.0 and full["high"] == 1.0
    half = cal.wilson_interval(5, 10)
    assert half["low"] < 0.5 < half["high"]
    assert half["low"] >= 0.0 and half["high"] <= 1.0


def test_summary_counts_human_only():
    rows = [_row(), _row(requirement_applicable="NOT_APPLICABLE"),
            _row(reviewer="ai_assisted", requirement_applicable="NOT_APPLICABLE"),
            _row(reviewer="deterministic", gap_justified=False),
            _row(reviewer="human:second", verdict="DEFERRED: later")]
    summary = cal.summarize_human_sample(rows)
    assert summary["human_completed"] == 2
    assert summary["ai_assisted_completed"] == 1
    assert summary["deterministic_completed"] == 1
    assert summary["applicability"]["hits"] == 1
    assert summary["applicability"]["trials"] == 2
    assert summary["false_positive_obligations"]["trials"] == 2


def test_build_packet_anchors_and_flags_stale():
    chapter = "Alpha line.\nBeta line two.\nGamma line.\n"
    req = {"id": "treq:x", "requirement_key": "metrics", "requirement_type": "m",
           "label": "L", "acceptance_rule": "A", "applicability": "APPLICABLE",
           "applicability_reason": "r", "satisfaction": "UNRESOLVED", "satisfaction_detail": "d"}
    claim = {"id": "tclaim:y", "book_id": "b", "chapter_id": "01-chapter.md",
             "source_revision": "rev1", "source_excerpt": "Beta line two.",
             "claim_text": "Beta.", "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
             "qualifications": []}
    packet = cal.build_packet(req, claim, chapter, "rev1", [], [], [],
                              "CAL04A02-001", "A", "probability-sample")
    assert packet["integrity"]["excerpt_anchored"] is True
    assert packet["surrounding_source_context"]["text"].startswith("Alpha line.")
    assert packet["review_state"] == "AWAITING_REVIEW"
    stale = cal.build_packet(req, claim, chapter, "rev2", [], [], [],
                             "CAL04A02-001", "A", "probability-sample")
    assert stale["integrity"]["stale_or_missing"] is not None
    missing = cal.build_packet(req, {**claim, "source_excerpt": "Nope absent."},
                               chapter, "rev1", [], [], [],
                               "CAL04A02-001", "A", "probability-sample")
    assert missing["integrity"]["excerpt_anchored"] is False


def test_frozen_sample_is_reproducible_and_audited():
    data = json.loads((cal.DATA_DIR / "sample.json").read_text(encoding="utf-8"))
    population = json.loads((cal.DATA_DIR / "population.json").read_text(encoding="utf-8"))
    assert data["seed"] == 20261112
    assert len(data["sample_A"]) == 110 and len(data["sample_B"]) == 30
    assert len(set(data["sample_A"])) == 110
    b_ids = [s["requirement_id"] for s in data["sample_B"]]
    assert not (set(data["sample_A"]) & set(b_ids))
    candidate = sorted(i["requirement_id"] for i in population["items"] if not i["historical_review"])
    assert len(candidate) == 441
    assert sorted(random.Random(20261112).sample(candidate, 110)) == data["sample_A"]
    pop_ids = set(i["requirement_id"] for i in population["items"])
    assert set(data["sample_A"]) <= pop_ids and set(b_ids) <= pop_ids
    historical = set(i["requirement_id"] for i in population["items"] if i["historical_review"])
    assert not ((set(data["sample_A"]) | set(b_ids)) & historical)


def test_frozen_population_matches_contract():
    population = json.loads((cal.DATA_DIR / "population.json").read_text(encoding="utf-8"))
    assert population["population_size"] == 475
    assert population["contract"] == "evidence-requirements-v1"
    templates = set(i["requirement_template"] for i in population["items"])
    assert len(templates) == 22  # instantiated subset of the 25 declared templates


def test_calibration_api_endpoints(client: TestClient) -> None:
    runs = client.get("/api/publication/calibration/runs").json()
    assert isinstance(runs, list) and len(runs) == 2
    by_id = {r["run_id"]: r for r in runs}
    assert by_id["CAL04A02-20261112"]["arm_A_target"] == 110
    assert by_id["CAL04A02-20261112"]["awaiting"] == 140
    sample = client.get("/api/publication/calibration/sample").json()
    assert sample["new_distinct"] == 140 and sample["new_model_calls"] == 0
    page = client.get("/api/publication/calibration/packets?arm=B&limit=5").json()
    assert page["count"] == 30 and len(page["packets"]) == 5
    one = client.get("/api/publication/calibration/packets/CAL04A02-001").json()
    assert one["calibration_case_id"] == "CAL04A02-001"
    assert one["review_state"] == "AWAITING_REVIEW"
    missing = client.get("/api/publication/calibration/packets/CAL04A02-999")
    assert missing.status_code == 404
    stats = client.get("/api/publication/calibration/stats").json()
    assert stats["human_completed"] == 0
    assert stats["ai_assisted_completed"] == 0


def test_calibration_review_does_not_touch_history(client: TestClient) -> None:
    before = client.get("/api/technical/claims?project_id=inference").json()
    created = client.post("/api/publication/calibration", json={
        "requirement_id": "treq:fake", "sample_version": 2,
        "sample_reason": "run:CAL04A02-20261112|A",
        "requirement_applicable": "APPLICABLE", "reviewer": "ai_assisted",
        "verdict": "ABSTAINED: fixture has no matching requirement"})
    assert created.status_code == 404  # unknown requirement rejected, nothing written
    after = client.get("/api/technical/claims?project_id=inference").json()
    assert len(before) == len(after)
