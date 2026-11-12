"""Calibration runs, review packets and statistics (MC-QUALITY-04A-02).

Deterministic. No model calls. Provenance convention (stored in the
existing publication_calibration_reviews table, sample_version=2 for
run CAL04A02-20261112):

- reviewer: "human:<id>" | "ai_assisted" | "ai_assisted:secondary" |
  "ai_assisted:adjudicator" | "deterministic"
- sample_reason: "run:<RUN_ID>|A" for probability cases,
  "run:<RUN_ID>|B:<reason>" for diagnostic cases
- verdict prefix "DEFERRED:" / "ABSTAINED:" / "DRAFT:" marks workflow
  states; completed reviews carry R1..R10 codes in `correction`.
- correction lines "Rk:VALUE[:note]" record the ten rubric answers:
  R1 claim fidelity (VALID|PARTIAL|INVALID|ABSTAIN)
  R2 applicability (APPLICABLE|NOT_APPLICABLE|UNDETERMINED)
  R3 necessity (REQUIRED|OPTIONAL|REDUNDANT|UNJUSTIFIED|UNDETERMINED)
  R4 epistemic fit (OK|MISMATCH)
  R5 evidence relevance (direct|partial|contextual|unrelated|none)
  R6 evidence independence (independent|restates|shared|circular|none)
  R7 satisfaction (yes|no|partial|unknown|waived)
  R8 gap class (justified|misclassified:<correct-type>)
  R9 priority (proportionate|inflated|deflated)
  R10 blocking (blocker-candidate|policy-decision|advisory|na|undetermined)

Only HUMAN_REVIEW rows count as independent ground truth. AI-assisted
rows are provisional analysis. Deterministic rows cover exact-match
checks only. AWAITING_REVIEW is the absence of a row.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

RUN_ID = "CAL04A02-20261112"
SAMPLE_VERSION = 2

DATA_DIR = Path(__file__).parent / "data"

REVIEWER_HUMAN_PREFIX = "human:"
REVIEWER_AI = "ai_assisted"
REVIEWER_AI_SECONDARY = "ai_assisted:secondary"
REVIEWER_AI_ADJUDICATOR = "ai_assisted:adjudicator"
REVIEWER_DETERMINISTIC = "deterministic"

STATE_PREFIXES = ("DEFERRED:", "ABSTAINED:", "DRAFT:")


def reviewer_provenance(reviewer: str) -> str:
    if reviewer == REVIEWER_DETERMINISTIC:
        return "DETERMINISTIC_VALIDATION"
    if reviewer in (REVIEWER_AI, REVIEWER_AI_SECONDARY, REVIEWER_AI_ADJUDICATOR):
        return "AI_ASSISTED_REVIEW"
    if reviewer.startswith(REVIEWER_HUMAN_PREFIX):
        return "HUMAN_REVIEW"
    return "AWAITING_REVIEW"


def review_state(verdict: str) -> str:
    for prefix in ("DEFERRED", "ABSTAINED", "DRAFT"):
        if (verdict or "").startswith(prefix + ":"):
            return prefix.lower()
    return "completed" if (verdict or "").strip() else "awaiting"


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> dict:
    """Wilson score interval for a binomial proportion. No approximations
    hidden: returns nulls (not zero) when trials == 0."""
    if trials <= 0:
        return {"rate": None, "low": None, "high": None, "trials": 0}
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return {"rate": p, "low": max(0.0, center - half), "high": min(1.0, center + half),
            "trials": trials}


def summarize_human_sample(reviews: list[dict]) -> dict:
    """Estimates over HUMAN_REVIEW completed rows only. AI-assisted and
    deterministic rows are counted separately and never merged in."""
    human = [r for r in reviews
             if reviewer_provenance(r.get("reviewer", "")) == "HUMAN_REVIEW"
             and review_state(r.get("verdict", "")) == "completed"]
    ai = [r for r in reviews
          if reviewer_provenance(r.get("reviewer", "")) == "AI_ASSISTED_REVIEW"]
    det = [r for r in reviews
           if reviewer_provenance(r.get("reviewer", "")) == "DETERMINISTIC_VALIDATION"]
    n = len(human)

    def rate(pred):
        hits = sum(1 for r in human if pred(r))
        return {"hits": hits, **wilson_interval(hits, n)}

    return {
        "human_completed": n,
        "ai_assisted_completed": len(ai),
        "deterministic_completed": len(det),
        "applicability": rate(lambda r: r.get("requirement_applicable") == "APPLICABLE"),
        "false_positive_obligations": rate(
            lambda r: r.get("requirement_applicable") == "NOT_APPLICABLE"),
        "gap_justified": rate(lambda r: bool(r.get("gap_justified"))),
        "priority_proportionate": rate(lambda r: bool(r.get("priority_proportionate"))),
        "would_block": rate(lambda r: bool(r.get("would_block"))),
        "note": ("Intervals are Wilson 95% over completed human reviews only. "
                 "AI-assisted rows are provisional analysis, not population estimates."),
    }


def build_packet(requirement: dict, claim: dict, chapter_text: str,
                  chapter_revision: str, evidence: list[dict],
                  verifications: list[dict], gaps: list[dict],
                  case_id: str, arm: str, reason: str, run_id: str = RUN_ID) -> dict:
    """Assemble one source-grounded review packet from plain dicts.

    Never paraphrases the manuscript; context is sliced, not generated.
    """
    excerpt = (claim.get("source_excerpt") or "").replace("\r\n", "\n")
    at = chapter_text.find(excerpt) if excerpt else -1
    integrity = {
        "chapter_fingerprint_match": claim.get("source_revision") == chapter_revision,
        "excerpt_anchored": at >= 0,
        "excerpt_multiple_occurrences": chapter_text.count(excerpt) > 1 if at >= 0 else False,
        "stale_or_missing": None,
    }
    if claim.get("source_revision") != chapter_revision:
        integrity["stale_or_missing"] = "chapter revision differs from claim source_revision"
    elif at < 0:
        integrity["stale_or_missing"] = "excerpt not found in current chapter text"
    if at >= 0:
        lo = max(0, at - 800)
        hi = min(len(chapter_text), at + len(excerpt) + 800)
        plo = chapter_text.rfind("\n\n", 0, lo)
        plo = 0 if plo < 0 else plo + 2
        phi = chapter_text.find("\n\n", hi)
        phi = len(chapter_text) if phi < 0 else phi
        context = {"text": chapter_text[plo:phi], "char_span": [plo, phi],
                   "excerpt_offset_in_context": [at - plo, at + len(excerpt) - plo]}
    else:
        context = {"text": "", "char_span": [0, 0], "excerpt_offset_in_context": [0, 0]}
    return {
        "calibration_case_id": case_id,
        "sampling_arm": arm,
        "sample_reason": reason,
        "run_id": run_id,
        "requirement_id": requirement["id"],
        "claim_id": claim["id"],
        "book_id": claim.get("book_id", ""),
        "chapter_id": claim["chapter_id"],
        "source_revision": claim.get("source_revision", ""),
        "live_chapter_revision": chapter_revision,
        "claim_type": claim["claim_type"],
        "epistemic_role": claim["epistemic_role"],
        "claim_text": claim["claim_text"],
        "qualifications": list(claim.get("qualifications") or []),
        "exact_manuscript_excerpt": excerpt,
        "surrounding_source_context": context,
        "requirement_template": requirement["requirement_key"],
        "requirement_type": requirement.get("requirement_type", ""),
        "requirement_description": requirement.get("label", ""),
        "requirement_acceptance_rule": requirement.get("acceptance_rule", ""),
        "current_applicability": requirement["applicability"],
        "applicability_reason": requirement.get("applicability_reason", ""),
        "current_satisfaction": requirement["satisfaction"],
        "satisfaction_detail": requirement.get("satisfaction_detail", ""),
        "existing_evidence": [{
            "id": e.get("id"), "evidence_type": e.get("evidence_type"),
            "source_location": e.get("source_location"),
            "source_span": e.get("source_span") or "",
            "evidence_excerpt": (e.get("evidence_excerpt") or "")[:400],
            "verification_status": e.get("verification_status")} for e in evidence],
        "existing_verification_results": [{
            "method": v.get("method"), "status": v.get("status"),
            "detail": (v.get("detail") or "")[:300],
            "spec_id": v.get("spec_id") or "", "model_id": v.get("model_id") or ""}
            for v in verifications],
        "existing_gap": [{
            "id": g.get("id"), "gap_type": g.get("gap_type"), "status": g.get("status"),
            "title": g.get("title"), "searched_scope": g.get("searched_scope") or "",
            "priority_rationale": g.get("priority_rationale") or ""} for g in gaps],
        "current_priority": (gaps[0].get("priority_rationale") if gaps else ""),
        "integrity": integrity,
        "review_state": "AWAITING_REVIEW",
    }


def fixture_path(data_dir: str, name: str) -> Path:
    return Path(data_dir) / "calibration_04a02" / name
