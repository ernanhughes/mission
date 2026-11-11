"""ARTIFACT-EXPO-01 Stage 08/14: Artifact Load aggregation tests.

Deterministic fixtures only. No model calls.
"""

from types import SimpleNamespace

from mission_control.artifact_load.service import (
    assessment_state,
    cluster_regions,
    compute_load,
)


def _finding(start, end, severity="MED", status="SEMANTICALLY_CONFIRMED"):
    return {
        "family": "EXPOSITORY_OVERLOAD",
        "subtype": "EXPO_COMPRESSION",
        "severity": severity,
        "status": status,
        "start_line": start,
        "end_line": end,
    }


def test_exact_raw_counts_and_severity_weights():
    findings = [
        _finding(10, 14, "HIGH"),
        _finding(30, 32, "MED"),
        _finding(50, 51, "LOW"),
    ]
    out = compute_load(
        findings=findings,
        eligible_words=1000,
        evaluated_units=100,
        coverage_mechanical=1.0,
        coverage_semantic=1.0,
    )
    assert out["confirmed"] == 3
    assert (out["high"], out["medium"], out["low"]) == (1, 1, 1)
    # 3 + 2 + 1 = 6 weight over 1000 words -> 6.0
    assert out["weighted_load"] == 6.0
    assert out["findings_per_1k"] == 3.0
    assert out["affected_regions"] == 3


def test_overlapping_findings_deduplicated_to_regions():
    findings = [
        _finding(10, 16, "HIGH"),
        _finding(12, 18, "MED"),  # same underlying problem, different symptom
        _finding(40, 44, "LOW"),
    ]
    out = compute_load(
        findings=findings,
        eligible_words=1000,
        evaluated_units=50,
        coverage_mechanical=1.0,
        coverage_semantic=1.0,
    )
    assert out["confirmed"] == 3
    assert out["affected_regions"] == 2
    # Region 1 keeps max severity HIGH (3), region 2 LOW (1) -> 4.0
    assert out["weighted_load"] == 4.0


def test_zero_findings_complete_coverage_is_clean():
    out = compute_load(
        findings=[],
        eligible_words=2000,
        evaluated_units=40,
        coverage_mechanical=1.0,
        coverage_semantic=1.0,
    )
    assert out["confirmed"] == 0
    assert out["weighted_load"] == 0.0
    assert out["affected_regions"] == 0


def test_incomplete_coverage_reports_unreviewed_not_clean():
    findings = [
        _finding(10, 12, "MED", status="MECHANICALLY_FLAGGED"),
        _finding(20, 22, "MED", status="SEMANTICALLY_CONFIRMED"),
    ]
    out = compute_load(
        findings=findings,
        eligible_words=1000,
        evaluated_units=20,
        coverage_mechanical=1.0,
        coverage_semantic=0.25,
    )
    # Only confirmed findings drive the burden metric.
    assert out["confirmed"] == 1
    assert out["unreviewed"] == 1
    assert out["weighted_load"] == 2.0


def test_word_count_normalization_and_paragraph_split_guard():
    before = compute_load(
        findings=[_finding(10, 14, "MED")],
        eligible_words=1000,
        evaluated_units=10,
        coverage_mechanical=1.0,
        coverage_semantic=1.0,
    )
    after_same_region_more_words = compute_load(
        findings=[_finding(10, 14, "MED")],
        eligible_words=2000,
        evaluated_units=30,  # paragraph split: 10 -> 30 units, same region
        coverage_mechanical=1.0,
        coverage_semantic=1.0,
    )
    # Normalized load drops because the denominator grew, but the raw region
    # count is unchanged: callers must report both and compare aligned regions.
    assert after_same_region_more_words["affected_regions"] == before["affected_regions"] == 1
    assert after_same_region_more_words["weighted_load"] < before["weighted_load"]
    assert after_same_region_more_words["findings_per_100_units"] < before["findings_per_100_units"]


def test_cluster_regions_max_severity_rule():
    regions = cluster_regions(
        [_finding(5, 9, "LOW"), _finding(7, 12, "HIGH"), _finding(30, 33, "MED")]
    )
    assert len(regions) == 2
    assert regions[0]["max_severity"] == "HIGH"
    assert regions[0]["weight"] == 3
    assert regions[0]["member_count"] == 2


def _mech(start, end, priority="MEDIUM", severity="UNASSESSED"):
    return {
        "family": "EXPOSITORY_OVERLOAD",
        "subtype": "EXPO_COMPRESSION",
        "severity": severity,
        "priority": priority,
        "status": "MECHANICALLY_FLAGGED",
        "start_line": start,
        "end_line": end,
    }


def test_mechanical_pressure_weighted_by_priority_not_severity():
    # EXPO-02 Stage A2: UNASSESSED severity must not be coerced into LOW.
    # Priority HIGH/MEDIUM/LOW drives mechanical pressure 3/2/1.
    findings = [
        _mech(10, 14, priority="HIGH"),
        _mech(30, 32, priority="LOW"),
    ]
    out = compute_load(
        findings=findings,
        eligible_words=1000,
        evaluated_units=10,
        coverage_mechanical=1.0,
        coverage_semantic=0.0,
    )
    assert out["confirmed"] == 0
    assert out["unreviewed"] == 2
    assert out["weighted_load"] == 0.0
    # (3 + 1) / 1.0k words
    assert out["mechanical_pressure"] == 4.0


def test_legacy_severity_only_findings_keep_screening_weight():
    out = compute_load(
        findings=[_finding(10, 12, "MED", status="MECHANICALLY_FLAGGED")],
        eligible_words=1000,
        evaluated_units=10,
        coverage_mechanical=1.0,
        coverage_semantic=0.0,
    )
    assert out["unreviewed"] == 1
    assert out["mechanical_pressure"] == 2.0


def test_priority_regions_do_not_double_count_overlap():
    findings = [
        _mech(10, 16, priority="HIGH"),
        _mech(12, 18, priority="MEDIUM"),
    ]
    out = compute_load(
        findings=findings,
        eligible_words=1000,
        evaluated_units=10,
        coverage_mechanical=1.0,
        coverage_semantic=0.0,
    )
    assert out["mechanical_pressure"] == 3.0


def _record(status="CURRENT", coverage_semantic=1.0, confirmed=0):
    return SimpleNamespace(status=status, coverage_semantic=coverage_semantic, confirmed=confirmed)


def test_assessment_state_not_assessed_without_semantic_coverage():
    assert assessment_state(_record(coverage_semantic=0.0)) == "not_assessed"
    assert assessment_state(_record(status="NOT_RUN")) == "not_assessed"


def test_assessment_state_partial_and_assessed():
    assert assessment_state(_record(coverage_semantic=0.4)) == "partially_assessed"
    assert assessment_state(_record(coverage_semantic=1.0, confirmed=0)) == "assessed_clean"
    assert assessment_state(_record(coverage_semantic=1.0, confirmed=2)) == "assessed_findings"


def test_assessment_state_stale_running_blocked():
    assert assessment_state(_record(status="STALE")) == "stale"
    assert assessment_state(_record(status="RUNNING")) == "running"
    for status in ("BLOCKED", "ERROR", "CANCELLED"):
        assert assessment_state(_record(status=status)) == "blocked_failed"
