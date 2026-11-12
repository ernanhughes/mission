"""Versioned release policy for MC-QUALITY-03D.

``publication-readiness-v1`` declares the gates, their groups, verification
methods, acceptance rules, failure severity and waiver policy. The gate
evaluator in ``service.py`` is deterministic given the same verified inputs
and this policy version. Nothing here calls a model; nothing here edits a
manuscript.
"""

from __future__ import annotations

POLICY_VERSION = "publication-readiness-v1"
POLICY_KIND = "technical-nonfiction"

# Gate result states.
PASS = "PASS"
FAIL = "FAIL"
WARNING = "WARNING"
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_RUN = "NOT_RUN"
UNKNOWN = "UNKNOWN"
STALE = "STALE"
ERROR = "ERROR"

# Overall readiness states.
READY = "READY"
READY_WITH_LIMITATIONS = "READY_WITH_ACCEPTED_LIMITATIONS"
BLOCKED = "BLOCKED"
NOT_YET_ASSESSED = "NOT_YET_ASSESSED"

GATES: list[dict] = [
    {
        "gate_id": "manuscript_identity",
        "gate_version": 1,
        "gate_group": "identity",
        "description": "The release candidate binds to an exact manuscript snapshot.",
        "applicability": "always",
        "required_inputs": ["chapter_manifest", "manuscript_fingerprint"],
        "verification_method": "deterministic",
        "acceptance_rule": "Chapter manifest is non-empty and every chapter hashes to the recorded revision.",
        "failure_severity": "blocker",
        "waiver_policy": "nonwaivable",
    },
    {
        "gate_id": "chapter_structure",
        "gate_version": 1,
        "gate_group": "structure",
        "description": "Chapter numbering and index claims are consistent with the manuscript on disk.",
        "applicability": "always",
        "required_inputs": ["preflight_findings"],
        "verification_method": "deterministic",
        "acceptance_rule": "No duplicate chapter numbers and no index chapter-count mismatch. Gaps and undeclared parts warn only.",
        "failure_severity": "blocker",
        "waiver_policy": "nonwaivable",
    },
    {
        "gate_id": "publication_build",
        "gate_version": 1,
        "gate_group": "build",
        "description": "The production Hugo build succeeds for the frozen snapshot.",
        "applicability": "always",
        "required_inputs": ["hugo_build_record"],
        "verification_method": "deterministic",
        "acceptance_rule": "An allowlisted production build exits 0 with output outside the book root. A passing development build is not equivalent.",
        "failure_severity": "blocker",
        "waiver_policy": "nonwaivable",
    },
    {
        "gate_id": "assets_references",
        "gate_version": 1,
        "gate_group": "assets",
        "description": "Required publication assets and references resolve.",
        "applicability": "always",
        "required_inputs": ["preflight_findings"],
        "verification_method": "deterministic",
        "acceptance_rule": "No missing assets, unresolved link targets or malformed SVGs. Medium/low illustration findings warn only.",
        "failure_severity": "blocker",
        "waiver_policy": "waivable",
    },
    {
        "gate_id": "prose_review",
        "gate_version": 1,
        "gate_group": "prose",
        "description": "Editorial review coverage is complete under the declared prose policy.",
        "applicability": "always",
        "required_inputs": ["prose_workspace"],
        "verification_method": "deterministic",
        "acceptance_rule": "Every discovered chapter has a current prose evaluation. No score threshold is imposed; scores never gate publication.",
        "failure_severity": "advisory",
        "waiver_policy": "waivable",
    },
    {
        "gate_id": "technical_verification",
        "gate_version": 1,
        "gate_group": "technical",
        "description": "Technical claims in scope are verified; contradictions are adjudicated or reviewed.",
        "applicability": "technical_scope",
        "required_inputs": ["technical_overview", "technical_assessments", "quality_reviews"],
        "verification_method": "deterministic",
        "acceptance_rule": "No claim whose latest verification contradicts the evidence without an author ACCEPT/DEFER review. "
        "Policy v1 requires full-book technical coverage for a READY verdict; a pilot scope leaves this gate NOT_YET_ASSESSED.",
        "failure_severity": "blocker",
        "waiver_policy": "nonwaivable",
        "require_full_coverage": True,
    },
    {
        "gate_id": "evidence_completeness",
        "gate_version": 1,
        "gate_group": "completeness",
        "description": "Evidence obligations in scope are assessed under calibrated requirement contracts.",
        "applicability": "technical_scope",
        "required_inputs": ["completeness_reports", "calibration_reviews"],
        "verification_method": "deterministic",
        "acceptance_rule": "Unconfirmed requirement priorities are advisory only and can never block. "
        "Only human-reviewed requirements with would_block=true may block, and only when unresolved and unwaived. "
        "Policy v1 requires full assessment coverage for a READY verdict.",
        "failure_severity": "blocker",
        "waiver_policy": "nonwaivable",
        "require_full_coverage": True,
    },
    {
        "gate_id": "author_approval",
        "gate_version": 1,
        "gate_group": "approval",
        "description": "The author approved this exact release snapshot under this policy version.",
        "applicability": "always",
        "required_inputs": ["publication_approvals"],
        "verification_method": "deterministic",
        "acceptance_rule": "A fresh (non-stale) APPROVE_RELEASE_CANDIDATE decision exists for this assessment id, snapshot and policy version.",
        "failure_severity": "advisory",
        "waiver_policy": "nonwaivable",
    },
]

GATE_IDS = [g["gate_id"] for g in GATES]


def get_gate(gate_id: str) -> dict:
    for gate in GATES:
        if gate["gate_id"] == gate_id:
            return gate
    raise KeyError(f"unknown gate {gate_id!r}")


def derive_readiness(results: dict[str, str], approval_present: bool) -> tuple[str, str]:
    """Overall readiness from per-gate results. Pure and deterministic.

    FAIL on a nonwaivable blocker gates BLOCKED. Anything mandatory and
    unknown/not-run/stale keeps NOT_YET_ASSESSED — including when blockers
    coexist with unknowns (both are reported, neither hidden). Approval is a
    separate recorded action and never inferred.
    """
    blocking_fail = [g["gate_id"] for g in GATES
                     if g["failure_severity"] == "blocker"
                     and g["waiver_policy"] == "nonwaivable"
                     and results.get(g["gate_id"]) == FAIL]
    if blocking_fail:
        return BLOCKED, f"nonwaivable blocking failure: {', '.join(sorted(blocking_fail))}"
    # Waivable blockers without an accepted limitation also block.
    waivable_fail = [g["gate_id"] for g in GATES
                     if g["failure_severity"] == "blocker"
                     and g["waiver_policy"] == "waivable"
                     and results.get(g["gate_id"]) == FAIL]
    if waivable_fail:
        return BLOCKED, f"unwaived blocking failure: {', '.join(sorted(waivable_fail))}"
    incomplete = [g["gate_id"] for g in GATES
                  if results.get(g["gate_id"]) in (NOT_RUN, UNKNOWN, STALE, ERROR, None)]
    if incomplete:
        return NOT_YET_ASSESSED, f"mandatory evidence missing: {', '.join(sorted(incomplete))}"
    if not approval_present:
        return NOT_YET_ASSESSED, "all gates resolved but author approval is absent"
    limited = [g["gate_id"] for g in GATES if results.get(g["gate_id"]) == WARNING]
    if limited:
        return READY_WITH_LIMITATIONS, f"approved with accepted limitations in: {', '.join(sorted(limited))}"
    return READY, "all mandatory gates pass and the author approved this snapshot"
