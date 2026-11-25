"""WORK-OUTCOME-01 W6B: finding aggregation and severity policy.

Groups are a presentation/reconciliation layer: every finding row is
preserved, members are never deleted, and closing a group requires
per-member closure evidence. Grouping key is (gap_class, subject digest)
where subject comes from the claim text — identical wording in one class
aggregates; distinct wordings stay distinct. No finding disappears without
an auditable explanation (member rows + group report).

Severity policy w6b-v1 (consequence, not mere absence of history):
- contradicted material claim with counter-evidence -> major defect
- missing mandatory requirement               -> major missing_requirement
- unsupported completion claim, no counter-evidence,
  historical evidence only (missing SHA/push proof/test record) -> minor
  (kind preserved as unsupported_claim; epistemic status suspected)
- merge corroborated, push unproven            -> minor verification_gap
- unverified test report, no execution record  -> minor verification_gap
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

SEVERITY_POLICY = "w6b-v1"

SEVERITY_ORDER = {"minor": 0, "major": 1, "critical": 2}


def gap_class_for(kind: str, title: str) -> str:
    t = (title or "").lower()
    if "test" in t and ("pass" in t or "report" in t):
        return "missing_test_evidence"
    if "merge" in t and "corroborat" in t:
        return "merge_corroborated_push_unproven"
    if "merge" in t:
        return "missing_merge_provenance"
    if "push" in t or "deploy" in t:
        return "missing_push_proof"
    if "review" in t:
        return "unresolved_review"
    if kind == "missing_requirement":
        return "missing_requirement"
    if kind == "defect":
        return "confirmed_defect"
    if kind == "verification_gap":
        return "verification_gap"
    return "other_evidence_limitation"


def subject_key(claim_text: str, title: str) -> str:
    base = (claim_text or "").strip().lower()
    if not base:
        base = (title or "").strip().lower()
    norm = " ".join(base.split())
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


def group_key(project_key: str, kind: str, claim_text: str,
              title: str) -> tuple[str, str, str]:
    gap = gap_class_for(kind, title)
    return (project_key or "", gap, subject_key(claim_text, title))


def group_title(gap: str, n: int) -> str:
    labels = {
        "missing_test_evidence": "Unverified test report",
        "merge_corroborated_push_unproven": "Merge corroborated, push unproven",
        "missing_merge_provenance": "Missing merge provenance",
        "missing_push_proof": "Missing push/deployment proof",
        "unresolved_review": "Unresolved independent review",
        "missing_requirement": "Missing mandatory requirement",
        "confirmed_defect": "Confirmed defect",
        "verification_gap": "Verification gap",
        "other_evidence_limitation": "Historical evidence limitation",
    }
    return f"{labels.get(gap, gap)} × {n}"


def max_severity(members: list[dict]) -> str:
    best = "minor"
    for m in members:
        sev = (m.get("severity") or "minor").lower()
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(best, 0):
            best = sev
    return best


def build_groups(findings: list[dict]) -> list[dict]:
    """Pure function: finding dicts (id, episode_id, project_key, kind,
    severity, status, title, claim_text) -> group dicts with members."""
    buckets: dict[tuple[str, str, str], list[dict]] = {}
    for f in findings:
        key = group_key(f.get("project_key", ""), f.get("kind", ""),
                        f.get("claim_text", ""), f.get("title", ""))
        buckets.setdefault(key, []).append(f)
    groups = []
    for (project_key, gap, subject), members in sorted(buckets.items()):
        gid = "wg:" + hashlib.sha1(
            f"{project_key}|{gap}|{subject}".encode()).hexdigest()[:16]
        open_members = [m for m in members if m.get("status") != "resolved"]
        sample = next((m.get("title", "") for m in members
                       if m.get("title")), "")
        groups.append({
            "id": gid,
            "project_key": project_key,
            "subject": subject,
            "gap_class": gap,
            "title": group_title(gap, len(members)),
            "sample_title": sample[:200],
            "sample_episodes": sorted({m.get("episode_id", "") for m in members
                                       if m.get("title") == sample})[:5],
            "members": [{"id": m.get("id", ""),
                         "episode_id": m.get("episode_id", "")}
                        for m in members],
            "severity": max_severity(members),
            "status": "open" if open_members else "resolved",
            "member_count": len(members),
            "member_ids": [m["id"] for m in members],
            "episode_ids": sorted({m.get("episode_id", "") for m in members}),
        })
    return groups


def new_group_id() -> str:
    return "wg:" + uuid.uuid4().hex[:16]


def reconcile_severity_policy(session: Any,
                              policy: str = SEVERITY_POLICY) -> list[dict]:
    """One recorded pass applying w6b-v1 to stored open findings.

    Only downgrades `unsupported_claim/major` rows that carry no
    counter-evidence (kind != defect, no contradiction language) to minor.
    Kind and title are kept stable (stored rows are history); severity,
    rationale suffix and next_action are updated. Returns one record per
    changed row for the audit report. Idempotent.
    """
    changed: list[dict] = []
    rows = session.query(_orm().WoFinding).filter(
        _orm().WoFinding.kind == "unsupported_claim",
        _orm().WoFinding.severity == "major").all()
    for r in rows:
        text = f"{r.title} {r.rationale}".lower()
        if "contradict" in text or r.kind == "defect":
            continue
        r.severity = "minor"
        note = f" [{policy}] Historical evidence limitation: severity reflects missing provenance, not a confirmed defect."
        if policy not in (r.rationale or ""):
            r.rationale = ((r.rationale or "") + note)[:2000]
        r.next_action = "supply merge SHA / push record / execution record"
        changed.append({"finding_id": r.id, "episode_id": r.episode_id,
                        "from": "major", "to": "minor"})
    return changed


def _orm():  # lazy to keep grouping import-light for pure use
    from mission_control import models as orm
    return orm

