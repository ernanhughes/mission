"""WORK-OUTCOME-01 W4: deterministic verification (no model calls).

Mechanical checks first: existence, reachability, linkage. Anything requiring
judgement returns explicitly-judgement-shaped outputs (reported_only,
insufficient_evidence, suspected gaps) for the semantic layer or W4 pilot to
resolve. Never invents evidence; never upgrades a claim by rewording it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

RUBRIC_VERSION = "w4-v1"

_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")

# Requirement verdicts (§7).
V_SATISFIED_VERIFIED = "satisfied_verified"
V_SATISFIED_REPORTED = "satisfied_reported"
V_PARTIAL = "partially_satisfied"
V_NOT_SATISFIED = "not_satisfied"
V_CONTRADICTED = "contradicted"
V_INSUFFICIENT = "insufficient_evidence"
V_BLOCKED = "blocked"
V_DEFERRED = "authorized_deferral"
V_SUPERSEDED = "superseded"
V_NA = "not_applicable"

# Claim verdicts.
C_COMMIT_EXISTS = "verified_commit_exists"
C_REVIEW_EXISTS = "verified_review_exists"
C_REPORTED = "reported_only"
C_CONTRADICTED = "contradicted"
C_UNVERIFIED = "unverified"


@dataclass
class EvidenceItem:
    kind: str  # git_commit | file | review | test_report | manifest | other
    ref: str
    resolved: bool = False
    detail: str = ""


@dataclass
class RequirementAssessment:
    requirement_id: str
    verdict: str
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)
    confidence: str = "weak"
    missing: str = ""
    method: str = "deterministic"


@dataclass
class ClaimVerification:
    claim_id: str
    verdict: str
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)
    method: str = "deterministic"


def _norm_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def assess_requirement_deterministic(requirement: dict, evidence: list[EvidenceItem],
                                     sibling_has_evidence: bool) -> RequirementAssessment:
    """Mechanical requirement assessment. Judgement-shaped gaps are returned
    as gaps, never resolved by assumption."""
    rid = str(requirement.get("id", ""))
    authority = str(requirement.get("authority", "ambiguous"))
    mandatory = bool(requirement.get("mandatory", True))
    kind = str(requirement.get("kind", "functional"))
    if authority == "deferred":
        return RequirementAssessment(rid, V_DEFERRED, "explicitly deferred", [], "strong")
    if authority == "superseded":
        return RequirementAssessment(rid, V_SUPERSEDED, "replaced by later amendment", [], "strong")
    if authority in ("excluded",):
        return RequirementAssessment(rid, V_NA, "explicitly out of scope", [], "strong")
    if authority == "suggested" and not mandatory:
        return RequirementAssessment(rid, V_NA, "optional improvement, non-blocking", [], "moderate")
    if authority == "ambiguous":
        return RequirementAssessment(rid, V_INSUFFICIENT, "intent not reliably established",
                                     [], "moderate", missing="requirement authority")
    resolved = [e for e in evidence if e.resolved]
    if not resolved:
        if mandatory and sibling_has_evidence:
            return RequirementAssessment(
                rid, V_NOT_SATISFIED,
                "mandatory requirement with no linked evidence while sibling "
                "requirements have evidence", [], "moderate",
                missing="any corroborating evidence")
        return RequirementAssessment(rid, V_INSUFFICIENT, "no linked evidence",
                                     [], "moderate", missing="corroborating evidence")
    refs = [f"{e.kind}:{e.ref}" for e in resolved]
    # Existence-type requirements can be verified mechanically against
    # re-read repository state (diff file lists, manifests).
    if kind in ("existence",) or _is_existence_requirement(requirement.get("text", "")):
        files = [e for e in resolved if e.kind in ("file", "git_commit") and e.resolved]
        if files:
            return RequirementAssessment(rid, V_SATISFIED_VERIFIED,
                                         "existence evidenced in resolved source state",
                                         refs, "strong")
    return RequirementAssessment(rid, V_SATISFIED_REPORTED,
                                 "evidence linked but correctness not "
                                 "independently judged", refs, "moderate",
                                 missing="independent correctness judgement")


_EXISTENCE_HINTS = ("file exists", "add file", "create file", "manifest",
                    "endpoint exists", "page exists")


def _is_existence_requirement(text: str) -> bool:
    t = _norm_text(text)
    return any(h in t for h in _EXISTENCE_HINTS)


def verify_claim_deterministic(claim: dict, episode_commits: list[str],
                               review_refs: list[str]) -> ClaimVerification:
    """Mechanical claim verification. Returns reported_only wherever the
    evidence does not independently establish the assertion."""
    cid = str(claim.get("id", ""))
    text = claim.get("text", "") or ""
    t = _norm_text(text)
    shas = [m for m in _SHA_RE.findall(t) if len(set(m)) >= 4]
    resolved = [s for s in shas if s.lower() in {c.lower() for c in episode_commits}
                or any(c.lower().startswith(s.lower()) for c in episode_commits)]
    if any(w in t for w in ("commit", "merg", "push")):
        if resolved:
            return ClaimVerification(cid, C_COMMIT_EXISTS,
                                     "referenced commit resolves in episode history",
                                     [f"git_commit:{r}" for r in resolved])
        return ClaimVerification(cid, C_REPORTED, "commit assertion without resolvable reference", [])
    if "test" in t and ("pass" in t or "fail" in t or "run" in t):
        return ClaimVerification(cid, C_REPORTED,
                                 "test outcome asserted; no execution record linked", [])
    if "review" in t:
        if review_refs:
            return ClaimVerification(cid, C_REVIEW_EXISTS, "review record linked",
                                     review_refs[:5])
        return ClaimVerification(cid, C_REPORTED, "review asserted; no review record linked", [])
    if any(w in t for w in ("integrat", "deploy", "available", "live")):
        return ClaimVerification(cid, C_UNVERIFIED, "operational assertion needs demonstration evidence", [])
    if any(w in t for w in ("fix", "correct", "resolv", "patch")):
        return ClaimVerification(cid, C_REPORTED, "correction asserted; re-verification not evidenced", [])
    return ClaimVerification(cid, C_REPORTED, "no mechanical verification rule applies", [])


def claim_identity(text: str, scope: str, revision: str) -> str:
    """Claim identity = statement + subject scope + source revision.
    Identical wording across revisions/scopes yields distinct identities
    (the W3 1248-vs-1202 lesson: categories overlap; identity must not)."""
    return hashlib.sha1(f"{_norm_text(text)}|{scope}|{revision}".encode()).hexdigest()[:24]


def rollup_completion(assessments: list[RequirementAssessment],
                      mandatory_ids: set[str]) -> tuple[str, str]:
    """Completion is governed by mandatory requirements (§9). Strict: complete
    requires every mandatory requirement satisfied_verified. Reported-only
    satisfaction is never completion."""
    if not mandatory_ids:
        return ("unknown", "no mandatory requirements recorded")
    by_id = {a.requirement_id: a for a in assessments}
    missing = [i for i in mandatory_ids if i not in by_id]
    if missing:
        return ("unknown", f"unassessed mandatory requirements: {len(missing)}")
    verdicts = [by_id[i].verdict for i in mandatory_ids]
    if all(v == V_SATISFIED_VERIFIED for v in verdicts):
        return ("complete", "all mandatory requirements verified")
    if any(v in (V_NOT_SATISFIED, V_CONTRADICTED) for v in verdicts):
        return ("incomplete", "mandatory requirements unsatisfied/contradicted")
    if any(v == V_BLOCKED for v in verdicts):
        return ("blocked", "mandatory requirement blocked")
    if any(v in (V_SATISFIED_REPORTED, V_PARTIAL) for v in verdicts):
        return ("partial", "requirements reported/partial but not all verified")
    return ("unknown", "mandatory requirements lack assessable evidence")
