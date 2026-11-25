"""WORK-OUTCOME-01 W6C: stale evaluation detection + queue state.

An assessment goes stale only when one of its tracked dependencies changes:
requirement versions, source revisions (new linked commits), new evidence,
changed evidence availability, review corrections, changed associations,
or rubric/policy changes. A new commit anywhere in the repo does NOT mark
every evaluation stale — only episodes linked to the changed revision.

queue_status lifecycle: current -> stale -> queued -> running ->
current | blocked | failed. History (assessments, findings, runs) is never
rewritten; staleness only marks the pointer row in wo_eval_state.
"""

from __future__ import annotations

from typing import Any

from mission_control import models as orm
from mission_control.work_observation.grouping import SEVERITY_POLICY

STALE_REASONS = {
    "requirement_changed",
    "new_commit",
    "new_evidence",
    "association_changed",
    "rubric_changed",
    "review_correction",
}

QUEUE_ORDER = ("blocked", "failed", "stale_consequential", "new_substantive",
               "stale", "unevaluated")


def get_state(session: Any, episode_id: str) -> dict[str, Any]:
    row = session.get(orm.WoEvalState, episode_id)
    if row is None:
        return {"episode_id": episode_id, "stale": 0, "stale_reason": "",
                "queue_status": "unevaluated", "last_assessment_id": ""}
    return {"episode_id": row.episode_id, "stale": row.stale,
            "stale_reason": row.stale_reason,
            "queue_status": row.queue_status,
            "last_assessment_id": row.last_assessment_id}


def mark_stale(session: Any, episode_id: str, reason: str,
               updated_at: str) -> dict[str, Any]:
    """Mark one episode stale for a tracked reason. Unknown reasons are
    rejected (never silently widen invalidation)."""
    if reason not in STALE_REASONS:
        return {"status": "rejected", "error": f"unknown stale reason: {reason}"}
    row = session.get(orm.WoEvalState, episode_id)
    if row is None:
        session.add(orm.WoEvalState(
            episode_id=episode_id, stale=1, stale_reason=reason,
            queue_status="stale", updated_at=updated_at))
    else:
        row.stale = 1
        row.stale_reason = reason
        if row.queue_status in ("current", "failed"):
            row.queue_status = "stale"
        row.updated_at = updated_at
    return {"status": "marked_stale", "episode_id": episode_id, "reason": reason}


def refresh_after_eval(session: Any, episode_id: str, assessment_id: str,
                       updated_at: str) -> None:
    row = session.get(orm.WoEvalState, episode_id)
    if row is None:
        session.add(orm.WoEvalState(
            episode_id=episode_id, last_assessment_id=assessment_id,
            stale=0, stale_reason="", queue_status="current",
            updated_at=updated_at))
    else:
        row.last_assessment_id = assessment_id
        row.stale = 0
        row.stale_reason = ""
        row.queue_status = "current"
        row.updated_at = updated_at


def select_queue(session: Any, limit: int = 20) -> list[dict[str, Any]]:
    """Manual/automatic queue selection. Priority: consequential stale work
    first; probe pings and machine-generated scoring batches are never
    auto-queued as development work (triage classification gates this:
    only substantive/insufficient-evidence episodes qualify)."""
    rows = session.query(orm.WoEvalState).filter(
        orm.WoEvalState.queue_status.in_(("stale", "queued", "failed", "blocked"))
    ).limit(max(1, min(limit, 100))).all()
    out = [{"episode_id": r.episode_id, "queue_status": r.queue_status,
            "stale_reason": r.stale_reason} for r in rows]
    order = {"blocked": 0, "failed": 1, "stale": 2, "queued": 3}
    out.sort(key=lambda d: order.get(d["queue_status"], 9))
    return out


RUBRIC_VERSION = "w4-v1"
POLICY_VERSION = SEVERITY_POLICY
