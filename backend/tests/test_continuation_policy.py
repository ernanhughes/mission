"""MC-QUALITY-04A-04-00 Workstream E: saturation and continuation policy tests."""

from mission_control.technical import service as tech


def _decision(**over):
    base = {"chapter_id": "12-chapter.md", "run_status": "LIMIT_REACHED",
            "requested_limit": 40, "returned_count": 40,
            "all_region_ids": ["r0", "r1", "r2"], "covered_region_ids": ["r0"]}
    base.update(over)
    return tech.continuation_decision(**base)


def test_saturated_with_remaining_regions_is_eligible():
    decision = _decision()
    assert decision["eligible"] is True
    assert decision["remaining_region_ids"] == ["r1", "r2"]
    assert decision["excludes_claim_texts"] == []


def test_saturated_with_full_coverage_is_not_completeness():
    decision = _decision(covered_region_ids=["r0", "r1", "r2"])
    assert decision["eligible"] is False
    assert "not complete" in decision["reason"]
    assert decision["remaining_region_ids"] == []


def test_unsaturated_result_never_triggers_continuation():
    assert _decision(run_status="COMPLETED_WITHIN_BUDGET")["eligible"] is False
    assert _decision(run_status="LIMIT_REACHED", returned_count=12)["eligible"] is False
    assert _decision(run_status="PARTIAL")["eligible"] is False
    assert _decision(run_status="FAILED")["eligible"] is False


def test_continuation_budget_terminates_bounded():
    assert _decision(prior_continuations=1)["eligible"] is False
    assert "budget exhausted" in _decision(prior_continuations=1)["reason"]
    assert _decision(prior_continuations=0, max_continuations=2)["eligible"] is True


def test_exclusion_list_passes_through_for_dedup():
    decision = _decision(exclude_claim_texts=["claim one", "claim two"])
    assert decision["eligible"] is True
    assert decision["excludes_claim_texts"] == ["claim one", "claim two"]


def test_zero_new_claims_ends_line_without_completeness_claim():
    # A continuation that returns nothing new ends the line; the record
    # stays "saturated, not complete" rather than becoming "complete".
    first = _decision()
    assert first["eligible"] is True
    second = _decision(prior_continuations=1, covered_region_ids=["r0", "r1", "r2"])
    assert second["eligible"] is False
