"""Artifact Load measurement (ARTIFACT-EXPO-01, Stage 08).

Independent from the six-dimension prose-quality scores in
quality_evaluations. Three layers stay separate:

- Layer A (mechanical pressure): reproducible counts/rates from deterministic
  detectors. Signals, not confirmed defects.
- Layer B (confirmed load): distinct source-linked confirmed findings. This is
  the primary metric (weighted_load).
- Layer C (reader benefit): independent evaluation evidence that a revision
  improved comprehension. Never inferred from count reduction alone.

Higher weighted_load means more confirmed burden. It is never a percentage
and never a 0-100 health score.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import ArtifactLoadObservation, Project

AGGREGATION_VERSION = "artifact-load-v1"

SEVERITY_WEIGHTS = {"LOW": 1, "MED": 2, "HIGH": 3}
PRIORITY_WEIGHTS = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
SEVERITIES = ("LOW", "MED", "HIGH")
PRIORITIES = ("LOW", "MEDIUM", "HIGH")

# Declared assessment policy (ARTIFACT-EXPO-02 Stage A1): a chapter load is
# only reported as assessed when semantic review covered every eligible unit.
# Anything less is partial; 0% semantic coverage is not assessed at all.
# History is never rewritten to fit this presentation: the state is derived
# at read time from stored coverage and counts.
ASSESSMENT_POLICY_VERSION = "assessment-policy-v1"
FULL_SEMANTIC_COVERAGE = 1.0

CONFIRMED_STATES = ("CURRENT", "PARTIAL", "STALE")
UNSCORABLE_STATES = ("NOT_RUN", "RUNNING", "BLOCKED", "ERROR", "CANCELLED")
ALL_STATES = CONFIRMED_STATES + UNSCORABLE_STATES

# Finding review states produced by the Writer detector pipeline.
CONFIRMED_FINDING = "SEMANTICALLY_CONFIRMED"
UNREVIEWED_FINDINGS = {"MECHANICALLY_FLAGGED", "PENDING_SEMANTIC_REVIEW", "CANDIDATE"}
INVALID_FINDINGS = {"INVALID_EVIDENCE", "BLOCKED", "FAILED"}
RESOLVED_FINDINGS = {"RESOLVED", "REJECTED_INTENTIONAL", "REJECTED", "FALSE_POSITIVE"}


def _severity_weight(severity: str) -> int:
    return SEVERITY_WEIGHTS.get(str(severity or "").upper(), 0)


def _finding_priority(finding: dict[str, Any]) -> str:
    """Review priority for mechanical screening weight.

    Reads the explicit ``priority`` left by the detector (EXPO-02 Stage A2).
    Legacy severity-only findings fall back to their severity; unknown or
    missing values fall back to LOW so a recorded candidate still counts as
    one unit of screening pressure (mechanical pressure is a signal, and the
    candidate count itself is always reported separately).
    """
    priority = str(finding.get("priority") or "").upper()
    if priority in PRIORITY_WEIGHTS:
        return priority
    severity = str(finding.get("severity") or "").upper()
    return {"LOW": "LOW", "MED": "MEDIUM", "MEDIUM": "MEDIUM", "HIGH": "HIGH"}.get(severity, "LOW")


def _priority_weight(priority: str) -> int:
    return PRIORITY_WEIGHTS.get(str(priority or "").upper(), 0)


def _rank_label(label: str) -> int:
    return {"LOW": 0, "MED": 1, "MEDIUM": 1, "HIGH": 2}.get(str(label or "").upper(), -1)


def cluster_regions(
    findings: list[dict[str, Any]], *, weight_field: str = "severity"
) -> list[dict[str, Any]]:
    """Cluster overlapping findings into affected regions.

    A shared span must not receive multiple independent penalties when several
    detectors recognise different symptoms of one underlying problem. Within a
    region the documented aggregation rule is the maximum validated severity
    (``weight_field="severity"``) or the maximum review priority
    (``weight_field="priority"``) for mechanical screening. Findings without
    usable line spans form singleton regions.

    Severity UNASSESSED (mechanical flags, EXPO-02 Stage A2) is never coerced
    into LOW: the region records it as-is with weight 0 under severity mode.
    """
    spans: list[tuple[int, int, str, int]] = []
    for idx, finding in enumerate(findings):
        try:
            start = int(finding.get("start_line") or 0)
            end = int(finding.get("end_line") or start)
        except (TypeError, ValueError):
            start, end = 0, 0
        if weight_field == "priority":
            label = _finding_priority(finding)
            weight = _priority_weight(label)
        else:
            raw = str(finding.get("severity") or "").upper()
            label = raw if raw in SEVERITIES else "UNASSESSED"
            weight = _severity_weight(label)
        if start <= 0 or end < start:
            # No usable span: singleton region so raw counts stay exact.
            spans.append((-(idx + 1), -(idx + 1), label, weight, idx))
        else:
            spans.append((start, end, label, weight, idx))
    ordered = sorted(spans, key=lambda item: (item[0], item[1]))
    regions: list[dict[str, Any]] = []
    for start, end, label, weight, idx in ordered:
        if start < 0:
            regions.append(
                {
                    "start_line": 0,
                    "end_line": 0,
                    "max_severity": label if weight_field == "severity" else "UNASSESSED",
                    "max_priority": label if weight_field == "priority" else None,
                    "weight": weight,
                    "member_count": 1,
                    "member_ids": [idx],
                }
            )
            continue
        if regions and regions[-1]["end_line"] > 0 and start <= regions[-1]["end_line"]:
            region = regions[-1]
            region["end_line"] = max(region["end_line"], end)
            key = "max_severity" if weight_field == "severity" else "max_priority"
            if _rank_label(label) > _rank_label(region.get(key)):
                region[key] = label
                region["weight"] = weight
            region["member_count"] += 1
            region["member_ids"].append(idx)
        else:
            regions.append(
                {
                    "start_line": start,
                    "end_line": end,
                    "max_severity": label if weight_field == "severity" else "UNASSESSED",
                    "max_priority": label if weight_field == "priority" else None,
                    "weight": weight,
                    "member_count": 1,
                    "member_ids": [idx],
                }
            )
    return regions


def compute_load(
    *,
    findings: list[dict[str, Any]],
    eligible_words: int,
    evaluated_units: int,
    coverage_mechanical: float,
    coverage_semantic: float,
) -> dict[str, Any]:
    """Compute Artifact Load from findings with explicit coverage.

    Only SEMANTICALLY_CONFIRMED findings contribute to the primary burden
    metric (weighted_load). Mechanical candidates contribute to
    mechanical_pressure only. Unreviewed and invalid-evidence counts are
    reported so unevaluated text is never treated as defect-free.
    """
    if eligible_words < 0 or evaluated_units < 0:
        raise ValidationProblem("eligible_words and evaluated_units must be >= 0")
    for coverage in (coverage_mechanical, coverage_semantic):
        if not 0.0 <= coverage <= 1.0:
            raise ValidationProblem("coverage values must be within 0.0-1.0")

    confirmed = [f for f in findings if str(f.get("status") or "") == CONFIRMED_FINDING]
    unreviewed = [f for f in findings if str(f.get("status") or "") in UNREVIEWED_FINDINGS]
    invalid = [f for f in findings if str(f.get("status") or "") in INVALID_FINDINGS]

    high = sum(1 for f in confirmed if str(f.get("severity") or "").upper() == "HIGH")
    medium = sum(1 for f in confirmed if str(f.get("severity") or "").upper() == "MED")
    low = sum(1 for f in confirmed if str(f.get("severity") or "").upper() == "LOW")

    regions = cluster_regions(confirmed)
    region_weight = sum(r["weight"] for r in regions)

    if eligible_words > 0:
        per_1k = round(len(confirmed) / (eligible_words / 1000.0), 3)
        weighted = round(region_weight / (eligible_words / 1000.0), 3)
    else:
        per_1k = None
        weighted = None
    if evaluated_units > 0:
        per_100 = round(len(confirmed) / (evaluated_units / 100.0), 3)
        region_rate = round(len(regions) / (evaluated_units / 100.0), 3)
    else:
        per_100 = None
        region_rate = None

    # Mechanical pressure uses the same region rule over candidates so one
    # underlying problem is not penalised once per detector symptom. Weight
    # comes from review priority (EXPO-02 Stage A2), never from UNASSESSED
    # severity, with a legacy severity fallback for older findings.
    candidate_regions = cluster_regions(
        [
            f
            for f in findings
            if str(f.get("status") or "") in UNREVIEWED_FINDINGS | {CONFIRMED_FINDING}
        ],
        weight_field="priority",
    )
    candidate_weight = sum(r["weight"] for r in candidate_regions)
    mechanical = (
        round(candidate_weight / (eligible_words / 1000.0), 3) if eligible_words > 0 else None
    )

    return {
        "total_candidates": len(findings),
        "confirmed": len(confirmed),
        "high": high,
        "medium": medium,
        "low": low,
        "unreviewed": len(unreviewed),
        "invalid_evidence": len(invalid),
        "affected_regions": len(regions),
        "findings_per_1k": per_1k,
        "findings_per_100_units": per_100,
        "region_rate": region_rate,
        "weighted_load": weighted,
        "mechanical_pressure": mechanical,
        "regions": regions,
    }


def record_observation(
    session: Session,
    *,
    project_id: str | None,
    book_id: str,
    chapter_id: str,
    source_path: str,
    chapter_revision: str,
    status: str,
    eligible_words: int,
    evaluated_units: int,
    coverage_mechanical: float,
    coverage_semantic: float,
    findings: list[dict[str, Any]],
    detector_version: str = "expo-v1",
    limitations: list[str] | None = None,
    execution: dict[str, Any] | None = None,
    previous_observation_id: str | None = None,
    supersedes: str | None = None,
    workbench_url: str | None = None,
    baseline_eligible_words: int = 0,
    revised_eligible_words: int = 0,
) -> ArtifactLoadObservation:
    if not chapter_id:
        raise ValidationProblem("chapter_id is required")
    if not chapter_revision:
        raise ValidationProblem("chapter_revision is required")
    if status not in ALL_STATES:
        raise ValidationProblem(f"status must be one of {', '.join(ALL_STATES)}; got {status!r}")
    if project_id and session.get(Project, project_id) is None:
        raise ValidationProblem("Project does not exist")
    if (
        previous_observation_id
        and session.get(ArtifactLoadObservation, previous_observation_id) is None
    ):
        raise ValidationProblem("Previous observation does not exist")
    if status in UNSCORABLE_STATES and findings:
        raise ValidationProblem(f"status {status} must not carry findings; unknown is not zero")

    summary = (
        compute_load(
            findings=list(findings),
            eligible_words=eligible_words,
            evaluated_units=evaluated_units,
            coverage_mechanical=coverage_mechanical,
            coverage_semantic=coverage_semantic,
        )
        if status in CONFIRMED_STATES
        else {
            "total_candidates": 0,
            "confirmed": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "unreviewed": 0,
            "invalid_evidence": 0,
            "affected_regions": 0,
            "findings_per_1k": None,
            "findings_per_100_units": None,
            "region_rate": None,
            "weighted_load": None,
            "mechanical_pressure": None,
            "regions": [],
        }
    )
    record = ArtifactLoadObservation(
        id=f"aload:{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        book_id=book_id or "",
        chapter_id=chapter_id,
        source_path=source_path or "",
        chapter_revision=chapter_revision,
        aggregation_version=AGGREGATION_VERSION,
        detector_version=detector_version or "expo-v1",
        status=status,
        eligible_words=eligible_words,
        evaluated_units=evaluated_units,
        total_candidates=summary["total_candidates"],
        confirmed=summary["confirmed"],
        high=summary["high"],
        medium=summary["medium"],
        low=summary["low"],
        unreviewed=summary["unreviewed"],
        invalid_evidence=summary["invalid_evidence"],
        affected_regions=summary["affected_regions"],
        findings_per_1k=summary["findings_per_1k"],
        findings_per_100_units=summary["findings_per_100_units"],
        region_rate=summary["region_rate"],
        coverage_mechanical=coverage_mechanical,
        coverage_semantic=coverage_semantic,
        weighted_load=summary["weighted_load"],
        mechanical_pressure=summary["mechanical_pressure"],
        baseline_eligible_words=baseline_eligible_words or eligible_words,
        revised_eligible_words=revised_eligible_words or eligible_words,
        findings=list(findings),
        regions=summary["regions"],
        limitations=list(limitations or []),
        execution=dict(execution or {}),
        previous_observation_id=previous_observation_id,
        supersedes=supersedes,
        workbench_url=workbench_url,
    )
    session.add(record)
    session.flush()
    return record


def assessment_state(record: ArtifactLoadObservation) -> str:
    """Derived assessment state for display (EXPO-02 Stage A1).

    One of: not_assessed | partially_assessed | assessed_clean |
    assessed_findings | stale | running | blocked_failed.

    ``weighted_load == 0.0`` is a legitimate accumulator, never a display
    verdict on its own: a chapter with 0% semantic coverage reports
    ``not_assessed`` however many mechanical candidates exist. No historical
    record is rewritten; this is derived at read time from stored coverage,
    counts and status.
    """
    status = str(record.status or "").upper()
    if status == "NOT_RUN":
        return "not_assessed"
    if status == "RUNNING":
        return "running"
    if status in ("BLOCKED", "ERROR", "CANCELLED", "FAILED"):
        return "blocked_failed"
    if status == "STALE":
        return "stale"
    try:
        semantic = float(record.coverage_semantic or 0.0)
    except (TypeError, ValueError):
        semantic = 0.0
    if semantic <= 0.0:
        return "not_assessed"
    if semantic < FULL_SEMANTIC_COVERAGE:
        return "partially_assessed"
    if (record.confirmed or 0) > 0:
        return "assessed_findings"
    return "assessed_clean"


def list_observations(
    session: Session,
    *,
    project_id: str | None = None,
    chapter_id: str | None = None,
    limit: int = 200,
) -> list[ArtifactLoadObservation]:
    stmt = select(ArtifactLoadObservation).order_by(desc(ArtifactLoadObservation.created_at))
    if project_id:
        stmt = stmt.where(ArtifactLoadObservation.project_id == project_id)
    if chapter_id:
        stmt = stmt.where(ArtifactLoadObservation.chapter_id == chapter_id)
    return list(session.scalars(stmt.limit(limit)).all())


def get_observation(session: Session, observation_id: str) -> ArtifactLoadObservation:
    record = session.get(ArtifactLoadObservation, observation_id)
    if record is None:
        raise NotFound("Artifact Load observation does not exist")
    return record


def compare_observations(session: Session, first_id: str, second_id: str) -> dict[str, Any]:
    first = get_observation(session, first_id)
    second = get_observation(session, second_id)
    if first.aggregation_version != second.aggregation_version:
        compatible = False
    else:
        compatible = True
    delta_regions = (second.affected_regions or 0) - (first.affected_regions or 0)
    delta_confirmed = (second.confirmed or 0) - (first.confirmed or 0)
    load_before = first.weighted_load
    load_after = second.weighted_load
    delta_load = (
        round(load_after - load_before, 3)
        if load_before is not None and load_after is not None
        else None
    )
    # Denominator stability: splitting one paragraph into three must not read
    # as improvement. Report raw counts alongside normalized rates and flag
    # word-count growth without region reduction.
    denominator_grew = (second.eligible_words or 0) > (first.eligible_words or 0) * 1.2
    pseudo_improvement = (
        denominator_grew
        and delta_regions >= 0
        and (load_after is not None and load_before is not None and load_after < load_before)
    )
    return {
        "first_id": first.id,
        "second_id": second.id,
        "compatible_basis": "artifact-load-v1" if compatible else "incompatible",
        "chapter_id": second.chapter_id,
        "chapter_revision_before": first.chapter_revision,
        "chapter_revision_after": second.chapter_revision,
        "detector_before": first.detector_version,
        "detector_after": second.detector_version,
        "delta_confirmed": delta_confirmed,
        "delta_regions": delta_regions,
        "load_before": load_before,
        "load_after": load_after,
        "delta_load": delta_load,
        "words_before": first.eligible_words,
        "words_after": second.eligible_words,
        "denominator_grew": denominator_grew,
        "pseudo_improvement_warning": pseudo_improvement,
        "coverage_before": {
            "mechanical": first.coverage_mechanical,
            "semantic": first.coverage_semantic,
        },
        "coverage_after": {
            "mechanical": second.coverage_mechanical,
            "semantic": second.coverage_semantic,
        },
    }
