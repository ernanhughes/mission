"""MC-QUALITY-04A-03B: strategy runs, budget, quarantine, reconciliation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mission_control.persistence.db import Database
from mission_control.technical import service as tech


def _regions():
    return [
        {"id": "r1", "char_start": 0, "char_end": 2000},
        {"id": "r2", "char_start": 2000, "char_end": 5000},
        {"id": "r3", "char_start": 5000, "char_end": 6000},
    ]


def test_planner_whole_continuation_has_two_bounded_passes():
    specs = tech.plan_extraction_requests(
        chapter_id="12-chapter.md", chapter_chars=30000, regions=_regions(),
        strategy="whole_continuation", requested_limit=40)
    assert len(specs) == 2
    assert specs[0]["role"] == "initial" and specs[1]["role"] == "continuation"
    assert specs[1]["excludes_claims_from_pass"] == 1
    assert all(s["requested_limit"] == 40 for s in specs)
    assert all(s["estimated_input_tokens"] > 0 and s["estimated_output_tokens"] > 0
               for s in specs)
    # Deterministic: same inputs, same plan.
    again = tech.plan_extraction_requests(
        chapter_id="12-chapter.md", chapter_chars=30000, regions=_regions(),
        strategy="whole_continuation", requested_limit=40)
    assert specs == again


def test_planner_single_splits_per_region_and_grouped_merges():
    singles = tech.plan_extraction_requests(
        chapter_id="c.md", chapter_chars=6000, regions=_regions(),
        strategy="region_single", requested_limit=10)
    assert len(singles) == 3
    assert [s["char_span"] for s in singles] == [[0, 2000], [2000, 5000], [5000, 6000]]
    grouped = tech.plan_extraction_requests(
        chapter_id="c.md", chapter_chars=6000, regions=_regions(),
        strategy="region_grouped", requested_limit=10, target_request_chars=9000)
    assert len(grouped) == 1 and grouped[0]["role"] == "grouped"
    assert grouped[0]["region_ids"] == ["r1", "r2", "r3"]
    tight = tech.plan_extraction_requests(
        chapter_id="c.md", chapter_chars=6000, regions=_regions(),
        strategy="region_grouped", requested_limit=10, target_request_chars=2500)
    assert len(tight) == 3


def test_planner_rejects_unknown_strategy_and_limit():
    with pytest.raises(Exception):
        tech.plan_extraction_requests(
            chapter_id="c", chapter_chars=10, regions=[], strategy="nope")
    with pytest.raises(Exception):
        tech.plan_extraction_requests(
            chapter_id="c", chapter_chars=10, regions=[], strategy="whole_continuation",
            requested_limit=500)


def test_budget_gate_stops_before_exceeding():
    tech.check_budget(used_input=100, used_output=50, used_calls=1,
                      max_input=1000000, max_output=500000, max_calls=10)
    with pytest.raises(Exception, match="call budget exhausted"):
        tech.check_budget(used_input=100, used_output=50, used_calls=10,
                          max_input=1000000, max_output=500000, max_calls=10)
    with pytest.raises(Exception, match="input token budget exhausted"):
        tech.check_budget(used_input=1000000, used_output=50, used_calls=1,
                          max_input=1000000, max_output=500000, max_calls=10)
    with pytest.raises(Exception, match="output token budget exhausted"):
        tech.check_budget(used_input=100, used_output=500000, used_calls=1,
                          max_input=1000000, max_output=500000, max_calls=10)


def test_quarantined_output_persists_nothing_and_fails_unit(
    client: TestClient, tmp_path, runtime
) -> None:
    from mission_control.technical.service import run_technical_campaign

    root = tmp_path / "book"
    root.mkdir()
    (root / "01-chapter.md").write_text("Alpha claim here.\n", encoding="utf-8")
    database = Database(runtime)

    quarantined = {"status": "OUTPUT_LIMIT_EXCEEDED", "returned_count": 41,
                   "accepted_count": 0,
                   "claims": [{"claim_text": "x", "source_quote": "y",
                               "claim_type": "FACTUAL", "epistemic_role": "OBSERVED"}],
                   "input_tokens": 100, "output_tokens": 9000}
    decision = tech.classify_cli_output(quarantined)
    assert decision["action"] == "quarantine"
    assert decision["run_status"] == "OUTPUT_LIMIT_EXCEEDED"

    def mapped_fn(chapter_id: str) -> dict:
        # What the API evaluate_fn returns after quarantine mapping.
        action = tech.classify_cli_output(quarantined)
        assert action["action"] == "quarantine"
        return {"status": "ERROR", "error": action["error"]}

    with database.session() as session:
        from mission_control.quality.service import create_campaign
        from mission_control.schemas import QualityCampaignCreate

        campaign = create_campaign(session, QualityCampaignCreate(
            project_id="inference", book_id="book-inference", book_root=str(root),
            mode="selected", chapters=["01-chapter.md"],
            model="m", assessment_type="technical"))
        session.commit()
        campaign_id = campaign.id
    record = run_technical_campaign(database.session, campaign_id, mapped_fn)
    assert record.status == "partial" and record.failed == 1
    with database.session() as session:
        from mission_control.models import TechnicalClaim
        assert session.query(TechnicalClaim).filter_by(campaign_id=campaign_id).count() == 0


def test_classifier_maps_all_cli_outcomes() -> None:
    assert tech.classify_cli_output({"status": "BLOCKED"})["action"] == "fail"
    assert tech.classify_cli_output(
        {"status": "TRUNCATED", "input_tokens": 5, "output_tokens": 6})["action"] == "quarantine"
    assert tech.classify_cli_output(
        {"status": "EMPTY"})["action"] == "quarantine"
    persist = tech.classify_cli_output({"status": "CURRENT", "claims": []})
    assert persist["action"] == "persist"
    assert persist["run_status"] == "COMPLETED_WITHIN_BUDGET"
    limited = tech.classify_cli_output({"status": "LIMIT_REACHED", "claims": []})
    assert limited["action"] == "persist" and limited["run_status"] == "LIMIT_REACHED"


def test_run_is_recorded_with_strategy_and_usage(
    client: TestClient, tmp_path, runtime
) -> None:
    from mission_control.schemas import TechnicalExtractionRunCreate

    database = Database(runtime)
    with database.session() as session:
        run = tech.record_extraction_run(session, TechnicalExtractionRunCreate(
            campaign_id=None, strategy="region_grouped", chapter_id="12-chapter.md",
            region_ids=["treg:a", "treg:b"], requested_limit=10,
            returned_count=10, accepted_count=9, status="LIMIT_REACHED",
            input_tokens=4200, output_tokens=900, model_id="m",
            prompt_version="2", source_revision="r" * 64))
        session.commit()
        run_id = run.id
    with database.session() as session:
        listed = tech.list_extraction_runs(session, chapter_id="12-chapter.md")
        assert [r.id for r in listed] == [run_id]
        assert listed[0].strategy == "region_grouped"
        assert listed[0].accepted_count == 9
    bad = dict(campaign_id=None, strategy="nope", chapter_id="c.md")
    with database.session() as session:
        with pytest.raises(Exception):
            tech.record_extraction_run(session, TechnicalExtractionRunCreate(**bad))
            session.flush()


def test_anchor_fields_persisted_on_claim(client: TestClient, tmp_path) -> None:
    from mission_control.schemas import TechnicalClaimCreate
    from mission_control.persistence.db import Database as _DB  # noqa: F401 (surface)

    path = tmp_path / "a.md"
    path.write_text("The value holds here.\n", encoding="utf-8")
    created = client.post("/api/technical/claims", json={
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": str(path), "source_revision": "r" * 64,
        "source_start_line": 1, "source_end_line": 1,
        "source_excerpt": "The value holds here.",
        "claim_text": "The value holds here.",
        "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
        "anchor_method": "exact", "source_char_start": 0, "source_char_end": 20}).json()
    assert created["anchor_method"] == "exact"
    assert created["source_start_line"] == 1
    fetched = client.get(f"/api/technical/claims/{created['id']}").json()
    assert fetched["source_char_start"] == 0 and fetched["source_char_end"] == 20
    bad = client.post("/api/technical/claims", json={
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": str(path), "source_revision": "r" * 64,
        "source_excerpt": "x", "claim_text": "y",
        "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
        "anchor_method": "fuzzy"})
    assert bad.status_code in (400, 422)


def test_duplicate_candidates_flag_shared_text_or_excerpt() -> None:
    class Row:
        def __init__(self, id, text, excerpt):
            self.id = id
            self.claim_text = text
            self.source_excerpt = excerpt

    pairs = tech.find_duplicate_candidates([
        Row("a", "Same assertion", "Quote one."),
        Row("b", "Same assertion", "Quote two."),
        Row("c", "Different point", "Quote three."),
    ])
    assert len(pairs) == 1
    assert pairs[0]["reasons"] == ["same-normalized-claim-text"]
    assert {pairs[0]["first_id"], pairs[0]["second_id"]} == {"a", "b"}


def test_new_coverage_statuses_accepted(client: TestClient, tmp_path, runtime) -> None:
    from mission_control.persistence.db import Database as _DB  # noqa: F401 (surface)

    database = Database(runtime)
    with database.session() as session:
        region = tech.sync_regions(
            session, project_id="inference", book_id="book-inference",
            chapter_id="01-chapter.md", source_path="p", source_hash="h",
            units=[{"title": "S", "char_span": [0, 10], "byte_span": [0, 10],
                    "id": "u1", "editable": True, "bounded": True}])[0]
        session.commit()
        rid = region.id
    with database.session() as session:
        for status in ("OUTPUT_LIMIT_EXCEEDED", "TRUNCATED", "EMPTY"):
            cov = tech.record_coverage(session, region_id=rid, source_hash="h",
                                       requested_limit=40, returned_count=41,
                                       status=status)
            session.flush()
            assert cov.status == status
        session.commit()
