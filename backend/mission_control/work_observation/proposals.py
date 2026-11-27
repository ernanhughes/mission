"""WORK-OUTCOME-01 W7: corrective proposal service.

Patterns mirrored from praxis_proposals/workflows (confirm-gated
transitions, scope-hash approval pinning, human-only approval,
append-only event history) — but a separate domain: these are
work-evaluation corrective commissions bound to findings/requirements/
episodes, not governance proposals. Ownership boundary documented in
W7-EXISTING-EXECUTION-INFRASTRUCTURE.md.

Status machine:
  draft -> ready_for_review -> approved -> queued -> running
    -> reported_complete -> verification_pending -> verified_resolved
  rejected | deferred | cancelled | failed at the documented gates.
Approval binds (version, scope_hash); editing scope after
ready_for_review bumps version and voids approval (re-review required).
No auto-execution: queued/running/report transitions are recorded
handoff states, never performed by this service.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from mission_control import models as orm
from mission_control.persistence.db import Database, now_iso

# finding kind -> corrective action category (§6 taxonomy; gaps first,
# code changes never the default for missing evidence)
ACTION_FOR_KIND = {
    "verification_gap": "RECOVER_EXISTING_EVIDENCE",
    "unsupported_claim": "RECOVER_EXISTING_EVIDENCE",
    "missing_requirement": "RECOVER_OR_CONFIRM_REQUIREMENTS",
    "defect": "INVESTIGATE_SUSPECTED_DEFECT",
}

# gap class refines the category for test/push/provenance gaps
ACTION_FOR_GAP = {
    "missing_test_evidence": "REPRODUCE_VERIFICATION",
    "merge_corroborated_push_unproven": "RECOVER_EXISTING_EVIDENCE",
    "missing_merge_provenance": "RECOVER_EXISTING_EVIDENCE",
    "missing_push_proof": "RECOVER_EXISTING_EVIDENCE",
    "unresolved_review": "INDEPENDENT_REVIEW",
    "missing_requirement": "RECOVER_OR_CONFIRM_REQUIREMENTS",
    "confirmed_defect": "INVESTIGATE_SUSPECTED_DEFECT",
}

VALID_ACTIONS = {
    "RECOVER_EXISTING_EVIDENCE", "RECOVER_OR_CONFIRM_REQUIREMENTS",
    "REPRODUCE_VERIFICATION", "INDEPENDENT_REVIEW",
    "INVESTIGATE_SUSPECTED_DEFECT", "CORRECT_CONFIRMED_DEFECT",
    "IMPLEMENT_MISSING_REQUIREMENT", "COMPLETE_INTEGRATION",
    "REEVALUATE_STALE_ASSESSMENT", "REQUEST_USER_DECISION",
    "DEFER_WITH_AUTHORIZATION", "NO_ACTION_REQUIRED",
}

TRANSITIONS = {
    "draft": {"ready_for_review", "cancelled"},
    "ready_for_review": {"approved", "rejected", "deferred", "draft",
                         "cancelled"},
    "approved": {"queued", "deferred", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"reported_complete", "failed", "cancelled"},
    "reported_complete": {"verification_pending", "failed"},
    "verification_pending": {"verified_resolved", "failed"},
    "verified_resolved": set(),
    "rejected": {"draft"},
    "deferred": {"draft", "cancelled"},
    "failed": {"draft", "cancelled"},
    "cancelled": set(),
}


APPROVAL_GATES = {"approved", "queued", "running", "reported_complete",
                  "verification_pending", "verified_resolved"}


def scope_hash_of(action_category: str, scope: str, exclusions: str,
                  acceptance_criteria: str, version: int) -> str:
    return hashlib.sha1(
        f"{action_category}|{scope}|{exclusions}|{acceptance_criteria}|{version}"
        .encode()).hexdigest()[:24]


def action_for_finding(kind: str, gap_class: str = "") -> str:
    if gap_class and gap_class in ACTION_FOR_GAP:
        return ACTION_FOR_GAP[gap_class]
    return ACTION_FOR_KIND.get(kind, "REQUEST_USER_DECISION")


class ProposalService:
    def __init__(self, database: Database) -> None:
        self._database = database

    # -- creation ---------------------------------------------------------
    def create_proposal(self, *, episode_id: str, finding_ids: list[str],
                        action_category: str = "",
                        objective: str = "", scope: str = "",
                        exclusions: str = "", acceptance_criteria: str = "",
                        required_verification: str = "",
                        suggested_route: str = "manual",
                        cost_constraints: str = "",
                        risk: str = "unknown",
                        group_id: str | None = None) -> dict[str, Any]:
        from mission_control.work_observation import grouping as gp
        episode_id = (episode_id or "")[:160]
        finding_ids = [f[:64] for f in finding_ids or []][:50]
        if not episode_id or not finding_ids:
            return {"status": "rejected",
                    "error": "episode_id and finding_ids are required"}
        if action_category and action_category not in VALID_ACTIONS:
            return {"status": "rejected", "error": "unknown action_category"}
        with self._database.session() as session:
            if session.get(orm.WoEpisode, episode_id) is None:
                return {"status": "unknown_episode"}
            rows = session.query(orm.WoFinding).filter(
                orm.WoFinding.id.in_(finding_ids)).all()
            if len(rows) != len(set(finding_ids)):
                return {"status": "rejected",
                        "error": "unknown finding id in finding_ids"}
            if any(r.episode_id != episode_id for r in rows):
                return {"status": "rejected",
                        "error": "all findings must belong to the episode"}
            if not action_category:
                first = rows[0]
                gap = ""
                try:
                    gap = gp.gap_class_for(first.kind, first.title or "")
                except Exception:
                    gap = ""
                action_category = action_for_finding(first.kind, gap)
            # Duplicate prevention: same open proposal for same findings.
            for p in session.query(orm.WoProposal).filter(
                    orm.WoProposal.episode_id == episode_id,
                    orm.WoProposal.status.notin_(
                        ("rejected", "cancelled", "verified_resolved"))).all():
                have = {m.finding_id for m in session.query(
                    orm.WoProposalFinding).filter(
                    orm.WoProposalFinding.proposal_id == p.id).all()}
                if have == set(finding_ids):
                    return {"status": "duplicate",
                            "proposal_id": p.id,
                            "error": "open proposal already covers findings"}
            pid = "wp:" + uuid.uuid4().hex[:16]
            now = now_iso()
            session.add(orm.WoProposal(
                id=pid, episode_id=episode_id, group_id=group_id,
                project_key="", action_category=action_category,
                objective=objective[:2000], scope=scope[:2000],
                exclusions=exclusions[:2000],
                acceptance_criteria=acceptance_criteria[:2000],
                required_verification=required_verification[:2000],
                suggested_route=suggested_route[:80],
                cost_constraints=cost_constraints[:500],
                risk=risk[:32], status="draft", version=1,
                scope_hash=scope_hash_of(action_category, scope, exclusions,
                                         acceptance_criteria, 1),
                closure_status="open", observed_at=now, created_at=now))
            for fid in set(finding_ids):
                session.add(orm.WoProposalFinding(
                    proposal_id=pid, finding_id=fid))
            session.add(orm.WoProposalEvent(
                id=uuid.uuid4().hex[:16], proposal_id=pid,
                from_status="", to_status="draft", actor="system",
                reason="proposal created", created_at=now))
        return {"status": "completed", "proposal_id": pid,
                "action_category": action_category}

    # -- assembly ----------------------------------------------------------
    def assemble_commission(self, proposal_id: str) -> dict[str, Any]:
        """Deterministic 13-section commission (§9) from stored facts.
        No model calls. Returns the previewable/copyable text + sections."""
        with self._database.session() as session:
            p = session.get(orm.WoProposal, proposal_id)
            if p is None:
                return {"status": "unknown_proposal"}
            fids = [m.finding_id for m in session.query(
                orm.WoProposalFinding).filter(
                orm.WoProposalFinding.proposal_id == p.id).all()]
            findings = session.query(orm.WoFinding).filter(
                orm.WoFinding.id.in_(fids)).all() if fids else []
            req_ids = sorted({f.requirement_id for f in findings
                              if f.requirement_id})
            reqs = session.query(orm.WoRequirement).filter(
                orm.WoRequirement.id.in_(req_ids)).all() if req_ids else []
            ep = session.get(orm.WoEpisode, p.episode_id)
            revs = session.query(orm.WoRequirementConfirmation).filter(
                orm.WoRequirementConfirmation.requirement_id.in_(
                    req_ids)).all() if req_ids else []
            decisions = {}
            for c in revs:
                decisions.setdefault(c.requirement_id, []).append(
                    f"{c.decision} by {c.reviewer}")
        lines = [
            f"1. Original objective: {(ep.title if ep else p.episode_id)}",
            "2. Authorized requirements:",
        ]
        for r in reqs:
            dec = "; ".join(decisions.get(r.id, []))
            lines.append(f"   - [{r.authority}] {r.text[:200]} (v{r.version})"
                         + (f" [human: {dec}]" if dec else ""))
        if not reqs:
            lines.append("   - (none recovered yet — see §7 recovery first)")
        lines += [
            f"3. Current observed implementation: episode {p.episode_id} "
            f"(see Work Episodes → Changes).",
            "4. Specific problem or evidence gap:",
        ]
        for f in findings:
            lines.append(f"   - [{f.kind}/{f.severity}] {f.title[:160]}")
            if f.next_action:
                lines.append(f"     Next: {f.next_action[:160]}")
        lines += [
            "5. Supporting evidence and source references:",
        ]
        for f in findings:
            if f.rationale:
                lines.append(f"   - {f.rationale[:200]}")
        lines += [
            "6. Relevant previous work: linked episode commits and reviews "
            "(see Work Episodes → Changes/Evidence).",
            f"7. Exact requested action [{p.action_category}]: {p.objective[:300]}",
            f"8. Permitted scope: {p.scope[:500] or '(as narrow as the findings above)'}",
            f"9. Explicit exclusions: {p.exclusions[:500] or 'no repository changes beyond scope; no push/deploy'}",
            f"10. Acceptance criteria: {p.acceptance_criteria[:500] or 'evidence class in §12 supplied for each finding'}",
            f"11. Required verification: {p.required_verification[:500] or 'independent check of the new evidence; no self-verification'}",
            f"12. Cost and execution constraints: {p.cost_constraints[:300] or 'deterministic first; paid inference $0 without separate authorization'}",
            "13. Stop conditions: stop and report if scope must widen, "
            "evidence contradicts the proposal, or any authorization is missing.",
        ]
        return {"status": "completed", "proposal_id": p.id,
                "version": p.version, "sections": lines,
                "text": "\n".join(lines)}

    # -- transitions -------------------------------------------------------
    def transition(self, proposal_id: str, to_status: str, *,
                   actor: str = "", reason: str = "",
                   confirm: bool = False) -> dict[str, Any]:
        to_status = (to_status or "")[:32]
        with self._database.session() as session:
            p = session.query(orm.WoProposal).filter_by(id=proposal_id).with_for_update().first()
            if p is None:
                return {"status": "unknown_proposal"}
            active_sc4 = session.query(orm.WoExecutionLink).filter_by(
                proposal_id=p.id, route="stephanie-sc3", status="running").first()
            if active_sc4 is not None:
                return {"status": "rejected", "error": "an SC4 execution claim is running; reconcile it before changing proposal state"}
            allowed = TRANSITIONS.get(p.status, set())
            if to_status not in allowed:
                return {"status": "rejected",
                        "error": f"transition {p.status} -> {to_status} "
                               f"not allowed"}
            if to_status in APPROVAL_GATES and not confirm:
                return {"status": "rejected",
                        "error": "confirm=True required (no self-authorizing "
                               "transitions)"}
            if to_status == "approved":
                # F1/F3 (W7 review): actor names are self-asserted
                # (convention-enforced, like the rest of the API), but a
                # literal system/model signature is refused outright.
                if (not actor.strip()
                        or actor.strip().lower() in ("system", "model")):
                    return {"status": "rejected",
                            "error": "approval requires a human actor"}
                if p.scope_hash != scope_hash_of(
                        p.action_category, p.scope, p.exclusions,
                        p.acceptance_criteria, p.version):
                    return {"status": "rejected",
                            "error": "scope changed since review: re-review "
                                     "required (edit bumps version first)"}
            frm = p.status
            p.status = to_status
            session.add(orm.WoProposalEvent(
                id=uuid.uuid4().hex[:16], proposal_id=p.id,
                from_status=frm, to_status=to_status,
                actor=actor[:80], reason=reason[:500],
                created_at=now_iso()))
        return {"status": "completed", "proposal_id": proposal_id,
                "from": frm, "to": to_status}

    def record_sc4_outcome_decision(self, proposal_id: str, *, actor: str,
                                    decision: str, evidence: dict[str, Any],
                                    rationale: str = "") -> dict[str, Any]:
        """Append a distinct human candidate decision without changing proposal lifecycle state."""
        actor = (actor or "").strip()
        decision = (decision or "").strip().lower()
        if not actor or actor.lower() in {"system", "model"}:
            return {"status": "rejected", "error": "a human actor is required"}
        if decision not in {"accepted", "rejected"}:
            return {"status": "rejected", "error": "decision must be accepted or rejected"}
        if not isinstance(evidence, dict) or evidence.get("schema_version") != "mission.sc4-outcome-decision.v1":
            return {"status": "rejected", "error": "invalid SC4 decision evidence"}
        if not evidence.get("investigation_id") or not evidence.get("experiment_id") or not evidence.get("result_digest"):
            return {"status": "rejected", "error": "SC4 decision evidence is incomplete"}
        import json
        marker = "MISSION_SC4_OUTCOME_DECISION_V1:"
        with self._database.session() as session:
            p = session.query(orm.WoProposal).filter_by(id=proposal_id).with_for_update().first()
            if p is None:
                return {"status": "unknown_proposal"}
            events = session.query(orm.WoProposalEvent).filter_by(proposal_id=proposal_id).all()
            for event in events:
                if event.reason.startswith(marker):
                    try:
                        prior = json.loads(event.reason[len(marker):])
                    except json.JSONDecodeError:
                        continue
                    if prior.get("evidence", {}).get("experiment_id") == evidence["experiment_id"]:
                        return ({"status": "duplicate", "decision": prior,
                                 "proposal_id": proposal_id} if prior.get("decision") == decision
                                else {"status": "conflict", "error": "a different human decision is already recorded for this experiment"})
            payload = {"schema_version": "mission.sc4-outcome-decision.v1",
                       "decision": decision, "actor": actor[:80],
                       "rationale": (rationale or "").strip()[:500],
                       "evidence": evidence}
            session.add(orm.WoProposalEvent(
                id=uuid.uuid4().hex[:16], proposal_id=p.id,
                from_status=p.status, to_status=p.status, actor=actor[:80],
                reason=marker + json.dumps(payload, sort_keys=True, separators=(",", ":")),
                created_at=now_iso()))
        return {"status": "completed", "proposal_id": proposal_id,
                "decision": payload}

    def edit_scope(self, proposal_id: str, *,
                   scope: str | None = None,
                   exclusions: str | None = None,
                   acceptance_criteria: str | None = None,
                   objective: str | None = None) -> dict[str, Any]:
        """Scope edits bump version + recompute hash and return the
        proposal to draft (voiding any prior approval)."""
        with self._database.session() as session:
            p = session.query(orm.WoProposal).filter_by(id=proposal_id).with_for_update().first()
            if p is None:
                return {"status": "unknown_proposal"}
            if p.status in ("verified_resolved", "cancelled"):
                return {"status": "rejected",
                        "error": "closed proposals are immutable"}
            active_sc4 = session.query(orm.WoExecutionLink).filter_by(
                proposal_id=p.id, route="stephanie-sc3", status="running").first()
            if active_sc4 is not None:
                return {"status": "rejected", "error": "an SC4 execution claim is running; scope edits are blocked until reconciliation"}
            changed = False
            for field, val in (("scope", scope), ("exclusions", exclusions),
                               ("acceptance_criteria", acceptance_criteria),
                               ("objective", objective)):
                if val is not None and getattr(p, field) != val[:2000]:
                    setattr(p, field, val[:2000])
                    changed = True
            if not changed:
                return {"status": "no_change", "proposal_id": proposal_id,
                        "version": p.version}
            frm = p.status
            p.version += 1
            p.scope_hash = scope_hash_of(
                p.action_category, p.scope, p.exclusions,
                p.acceptance_criteria, p.version)
            if frm != "draft":
                p.status = "draft"
            session.add(orm.WoProposalEvent(
                id=uuid.uuid4().hex[:16], proposal_id=p.id,
                from_status=frm, to_status=p.status,
                actor="editor", reason="scope edited: version bumped, "
                                       "prior approval void",
                created_at=now_iso()))
        return {"status": "completed", "proposal_id": proposal_id,
                "version": p.version, "from": frm, "to": p.status}

    # -- handoff + routes ----------------------------------------------------
    def describe_routes(self) -> dict[str, Any]:
        """Available execution routes. Manual copy is always available.
        Worker dispatch is reported with its precise limitation: no
        configured route in this environment, so only manual handoff is
        offered (no competing executor is created to fill the gap)."""
        return {"routes": [
            {"route": "manual", "available": True,
             "note": "copyable commission; execution happens outside "
                     "Mission Control and is linked back by hand"},
            {"route": "worker", "available": False,
             "note": "no configured worker route in this environment; "
                     "POST /v1/work integration is designed, not demonstrated"}
        ], "default": "manual"}

    def record_handoff(self, proposal_id: str, route: str,
                       external_ref: str = "", model: str = "",
                       actor: str = "", confirm: bool = False) -> dict[str, Any]:
        """Record an execution handoff (manual copy by default). Recording
        is not execution: the link traces the proposal to an external
        run that Mission Control did not start. F4 (W7 review): the
        approved -> queued move is an approval-gate transition, so it
        requires confirm=True like every other gate."""
        route = (route or "manual")[:32]
        if route != "manual":
            return {"status": "rejected",
                    "error": f"route '{route}' unavailable: only manual "
                             "handoff is offered in this environment"}
        if not confirm:
            return {"status": "rejected",
                    "error": "confirm=True required (no self-advancing "
                             "handoff)"}
        with self._database.session() as session:
            p = session.get(orm.WoProposal, proposal_id)
            if p is None:
                return {"status": "unknown_proposal"}
            if p.status not in ("approved", "queued"):
                return {"status": "rejected",
                        "error": "handoff requires an approved proposal "
                               "(approve first, then hand off)"}
            lid = "wx:" + uuid.uuid4().hex[:16]
            now = now_iso()
            session.add(orm.WoExecutionLink(
                id=lid, proposal_id=proposal_id, route="manual",
                external_ref=external_ref[:300], model=model[:120],
                status="handed_off", started_at=now, finished_at="",
                cost_usd=0.0, created_at=now))
            if p.status == "approved":
                p.status = "queued"
                session.add(orm.WoProposalEvent(
                    id=uuid.uuid4().hex[:16], proposal_id=proposal_id,
                    from_status="approved", to_status="queued",
                    actor=actor[:80] or "operator",
                    reason="manual handoff recorded" +
                           (f": {external_ref[:200]}" if external_ref else ""),
                    created_at=now))
        return {"status": "completed", "execution_id": lid,
                "proposal_id": proposal_id, "route": "manual"}

    # -- reads --------------------------------------------------------------
    def list_proposals(self, *,
                       episode_id: str | None = None,
                       status: str | None = None,
                       limit: int = 100) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoProposal).order_by(
                orm.WoProposal.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoProposal.episode_id == episode_id)
            if status:
                q = q.filter(orm.WoProposal.status == status)
            out = []
            for p in q.limit(max(1, min(limit, 500))).all():
                fids = [m.finding_id for m in session.query(
                    orm.WoProposalFinding).filter(
                    orm.WoProposalFinding.proposal_id == p.id).all()]
                out.append({"id": p.id, "episode_id": p.episode_id,
                            "group_id": p.group_id,
                            "action_category": p.action_category,
                            "objective": p.objective, "scope": p.scope,
                            "exclusions": p.exclusions,
                            "acceptance_criteria": p.acceptance_criteria,
                            "required_verification": p.required_verification,
                            "suggested_route": p.suggested_route,
                            "cost_constraints": p.cost_constraints,
                            "risk": p.risk, "status": p.status,
                            "version": p.version,
                            "scope_hash": p.scope_hash,
                            "closure_status": p.closure_status,
                            "finding_ids": fids})
            return out

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        rows = self.list_proposals(limit=500)
        for r in rows:
            if r["id"] == proposal_id:
                with self._database.session() as session:
                    evts = session.query(orm.WoProposalEvent).filter(
                        orm.WoProposalEvent.proposal_id == proposal_id
                    ).order_by(
                        orm.WoProposalEvent.created_at).all()
                    links = session.query(orm.WoExecutionLink).filter(
                        orm.WoExecutionLink.proposal_id == proposal_id).all()
                r["events"] = [
                    {"from": e.from_status, "to": e.to_status,
                     "actor": e.actor, "reason": e.reason,
                     "at": e.created_at} for e in evts]
                r["executions"] = [
                    {"id": li.id, "route": li.route,
                     "external_ref": li.external_ref, "model": li.model,
                     "status": li.status,
                     "cost_usd": li.cost_usd} for li in links]
                return r
        return None
