"""Versioned software-quality rubric (MC-PROJECTS-QUALITY-02).

A beautifully structured application that does not solve its intended purpose
must not score highly: purpose alignment and correctness carry the largest
weights, and missing evidence is never scored as success.
"""

from __future__ import annotations

from typing import Any

RUBRIC_ID = "software-quality-v1"
RUBRIC_VERSION = 1
PROMPT_VERSION = "1"

DIMENSIONS: list[dict[str, Any]] = [
    {"id": "purpose", "label": "Purpose and goal alignment", "weight": 150},
    {"id": "correctness", "label": "Correctness and reliability", "weight": 170},
    {"id": "testing", "label": "Testing and validation", "weight": 130},
    {"id": "architecture", "label": "Architecture and boundaries", "weight": 130},
    {"id": "maintainability", "label": "Maintainability", "weight": 100},
    {"id": "security", "label": "Security and safety", "weight": 100},
    {"id": "operations", "label": "Operational readiness", "weight": 70},
    {"id": "documentation", "label": "Documentation and agent readiness", "weight": 50},
    {"id": "usage", "label": "Actual use and ecosystem integration", "weight": 50},
    {"id": "delivery", "label": "Delivery evidence", "weight": 50},
]

BY_ID = {dim["id"]: dim for dim in DIMENSIONS}
TOTAL_WEIGHT = sum(dim["weight"] for dim in DIMENSIONS)
assert TOTAL_WEIGHT == 1000

#: Minimum bar for publishing an overall score out of the attainable total.
MIN_ASSESSED_DIMENSIONS = 8
REQUIRED_DIMENSIONS = ("purpose", "correctness")

DIMENSION_STATES = ("assessed", "abstained", "na")
SEVERITIES = ("critical", "high", "medium", "low")
FINDING_DECISIONS = ("ACCEPT", "REJECT", "DEFER", "INVESTIGATE")
FINDING_STATUSES = (
    "proposed",
    "accepted",
    "rejected",
    "in_progress",
    "needs_verification",
    "resolved",
    "reopened",
)
EVAL_STATUSES = ("queued", "running", "completed", "partial", "failed", "blocked")
REVIEW_VERDICTS = ("agree", "disagree", "partial")


class RubricProblem(ValueError):
    """Raised when model output violates the evaluation contract."""


def validate_dimension(dim_id: str, raw: Any, evidence_ids: set[str]) -> dict[str, Any]:
    """Validate one dimension assessment. Raises RubricProblem on violation."""
    if dim_id not in BY_ID:
        raise RubricProblem(f"unknown dimension {dim_id!r}")
    return _validate_one(BY_ID[dim_id], dim_id, raw if isinstance(raw, dict) else {}, evidence_ids)


def validate_dimensions(dimensions: dict[str, Any], evidence_ids: set[str]) -> dict[str, Any]:
    """Validate one evaluation's per-dimension assessments.

    Returns the normalized mapping. Raises RubricProblem on any contract
    violation: unknown/missing dimension, bad state, out-of-range score,
    missing rationale, or evidence references outside the manifest.
    """
    if not isinstance(dimensions, dict):
        raise RubricProblem("dimensions must be an object keyed by dimension id")
    missing = [dim["id"] for dim in DIMENSIONS if dim["id"] not in dimensions]
    if missing:
        raise RubricProblem(f"missing dimensions: {', '.join(missing)}")
    unknown = [key for key in dimensions if key not in BY_ID]
    if unknown:
        raise RubricProblem(f"unknown dimensions: {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    for dim in DIMENSIONS:
        dim_id = dim["id"]
        raw = dimensions[dim_id]
        if not isinstance(raw, dict):
            raise RubricProblem(f"dimension {dim_id} must be an object")
        normalized[dim_id] = _validate_one(dim, dim_id, raw, evidence_ids)
    return normalized


def _validate_one(
    dim: dict[str, Any], dim_id: str, raw: dict[str, Any], evidence_ids: set[str]
) -> dict[str, Any]:
    state = raw.get("state", "abstained")
    if state not in DIMENSION_STATES:
        raise RubricProblem(f"dimension {dim_id}: unknown state {state!r}")
    entry: dict[str, Any] = {
        "state": state,
        "max": dim["weight"],
        "score": None,
        "confidence": _confidence(raw.get("confidence")),
        "rationale": _text(raw.get("rationale"), dim_id, "rationale"),
        "positives": _strings(raw.get("positives"), dim_id, "positives"),
        "assumptions": _strings(raw.get("assumptions"), dim_id, "assumptions"),
        "unknowns": _strings(raw.get("unknowns"), dim_id, "unknowns"),
        "na_reason": "",
        "evidence_refs": [],
        "findings": [],
    }
    refs = raw.get("evidence_refs", [])
    if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
        raise RubricProblem(f"dimension {dim_id}: evidence_refs must be a string list")
    for ref in refs:
        if ref not in evidence_ids:
            raise RubricProblem(f"dimension {dim_id}: unknown evidence reference {ref!r}")
    entry["evidence_refs"] = list(refs)
    if state == "assessed":
        score = raw.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise RubricProblem(f"dimension {dim_id}: assessed requires a numeric score")
        if not 0 <= score <= dim["weight"]:
            raise RubricProblem(
                f"dimension {dim_id}: score {score} outside 0..{dim['weight']}"
            )
        entry["score"] = int(score)
        if not refs:
            raise RubricProblem(f"dimension {dim_id}: assessed requires evidence references")
    elif state == "na":
        reason = _text(raw.get("na_reason"), dim_id, "na_reason", allow_empty=False)
        entry["na_reason"] = reason
    for finding in raw.get("findings", []) or []:
        entry["findings"].append(validate_finding(finding, evidence_ids))
    return entry


def validate_finding(finding: Any, evidence_ids: set[str]) -> dict[str, Any]:
    """Validate one inline model finding. Raises RubricProblem on violation."""
    if not isinstance(finding, dict):
        raise RubricProblem("finding must be an object")
    severity = finding.get("severity", "medium")
    if severity not in SEVERITIES:
        raise RubricProblem(f"unknown severity {severity!r}")
    for field in ("title", "component"):
        if not str(finding.get(field) or "").strip():
            raise RubricProblem(f"finding is missing {field}")
    refs = finding.get("evidence_refs", [])
    if not isinstance(refs, list) or not refs or any(not isinstance(item, str) for item in refs):
        raise RubricProblem("finding requires at least one evidence reference")
    for ref in refs:
        if ref not in evidence_ids:
            raise RubricProblem(f"finding references unknown evidence {ref!r}")
    return {
        "severity": severity,
        "component": str(finding.get("component") or "")[:300],
        "title": str(finding.get("title") or "")[:300],
        "expected": str(finding.get("expected") or "")[:2000],
        "observed": str(finding.get("observed") or "")[:2000],
        "impact": str(finding.get("impact") or "")[:2000],
        "proposal": str(finding.get("proposal") or "")[:2000],
        "verification": str(finding.get("verification") or "")[:2000],
        "evidence_refs": list(refs)[:20],
    }


def aggregate(normalized: dict[str, Any]) -> dict[str, Any]:
    """Apply the aggregation policy.

    An overall score is published only when at least MIN_ASSESSED_DIMENSIONS
    dimensions are assessed including every REQUIRED dimension. Not-applicable
    dimensions leave the denominator via max_attainable; abstentions stay in
    the denominator as unscored. Below the bar the overall is NULL.
    """
    assessed = [dim for dim, entry in normalized.items() if entry["state"] == "assessed"]
    na_weights = sum(BY_ID[dim]["weight"] for dim, entry in normalized.items() if entry["state"] == "na")
    max_attainable = TOTAL_WEIGHT - na_weights
    coverage = round(len(assessed) / len(DIMENSIONS) * 100, 1)
    valid = len(assessed) >= MIN_ASSESSED_DIMENSIONS and all(
        normalized[dim]["state"] == "assessed" for dim in REQUIRED_DIMENSIONS
    )
    overall = sum(normalized[dim]["score"] for dim in assessed) if valid else None
    return {
        "overall": overall,
        "max_attainable": max_attainable,
        "coverage_percent": coverage,
        "assessed_count": len(assessed),
        "valid": valid,
    }


def _confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def _text(value: Any, dim_id: str, field: str, allow_empty: bool = True) -> str:
    text = str(value or "").strip()
    if not text and not allow_empty:
        raise RubricProblem(f"dimension {dim_id}: {field} is required")
    if field == "rationale" and not text:
        raise RubricProblem(f"dimension {dim_id}: rationale is required")
    return text[:4000]


def _strings(value: Any, dim_id: str, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RubricProblem(f"dimension {dim_id}: {field} must be a string list")
    return [item[:1000] for item in value][:20]
