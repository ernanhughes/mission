"""WORK-OUTCOME-01 W8: prospective Work Envelope registration + linkage.

An envelope binds pre-authorized intent (objective + requirement
versions + authorization ref + acceptance policy) to a work identity
BEFORE execution. It is metadata (~700 bytes), never model context:
no conversation history, no evidence packets travel with it.

References are validated, not invented: episode/objective/requirement/
finding/proposal ids must resolve; repositories must be known
GitRepository uids; commit SHAs must resolve to linked episode commits
or existing repo objects; sessions to OpenCode sessions; test receipts
to AITest receipts; reviews to GitReview rows. Unknown refs are
rejected. Execution links carry the envelope id (real parentage, not
an anecdote table).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from mission_control import models as orm
from mission_control.persistence.db import Database, now_iso

SCHEMA = "work-envelope.v1"


def _jl(value: Any) -> list:
    """JSON columns over TEXT DDL come back as strings on PostgreSQL
    (SQLite deserializes them). Normalize to lists at every read so
    PG and SQLite behave identically. Never silently invent content:
    unparseable values become []."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []

LINK_STATUSES = {"handed_off", "running", "reported_complete",
                 "verification_pending", "verified_resolved", "failed"}


def commission_digest_of(objective_text: str, requirements: list[dict],
                         scope: str, acceptance: str,
                         authorization_ref: str = "",
                         repositories: list | None = None,
                         acceptance_policy_ref: str = "") -> str:
    canon = json.dumps({"objective": objective_text,
                        "requirements": requirements,
                        "scope": scope,
                        "acceptance": acceptance,
                        "authorization_ref": authorization_ref,
                        "repositories": sorted(repositories or []),
                        "acceptance_policy_ref": acceptance_policy_ref},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:32]


class EnvelopeService:
    def __init__(self, database: Database,
                 opencode_db_path: Any | None = None) -> None:
        from pathlib import Path

        self._database = database
        self._opencode_db_path = Path(opencode_db_path) \
            if opencode_db_path else None

    # -- registration -----------------------------------------------------
    def register_envelope(self, *, episode_id: str,
                          objective_id: str,
                          requirement_ids: list[str] | None = None,
                          repositories: list[str] | None = None,
                          scope: str = "",
                          acceptance_criteria: str = "",
                          acceptance_policy_ref: str = "w6b-v1",
                          programme_id: str = "WORK-OUTCOME-01",
                          stage_id: str = "W8",
                          parent_work_id: str | None = None,
                          originating_findings: list[str] | None = None,
                          authorization_proposal_id: str | None = None,
                          authorization_note: str = "",
                          actor: str = "") -> dict[str, Any]:
        """Register prospective work. Authorization is an approved
        wo_proposal (pinned to id+version+scope_hash) or an explicit
        human attestation. No auto-authorization."""
        episode_id = (episode_id or "")[:160]
        requirement_ids = [r[:64] for r in requirement_ids or []][:50]
        repositories = [r[:160] for r in repositories or []][:20]
        originating_findings = [f[:64] for f in originating_findings or []][:50]
        if not episode_id or not objective_id:
            return {"status": "rejected",
                    "error": "episode_id and objective_id are required"}
        with self._database.session() as session:
            ep = session.get(orm.WoEpisode, episode_id)
            if ep is None:
                return {"status": "unknown_episode"}
            obj = session.get(orm.WoObjective, objective_id)
            if obj is None or obj.episode_id != episode_id:
                return {"status": "rejected",
                        "error": "objective must belong to the episode"}
            reqs = session.query(orm.WoRequirement).filter(
                orm.WoRequirement.id.in_(requirement_ids)).all() \
                if requirement_ids else []
            if len({r.id for r in reqs}) != len(set(requirement_ids)):
                return {"status": "rejected",
                        "error": "unknown requirement id in requirement_ids"}
            if any(r.episode_id != episode_id for r in reqs):
                return {"status": "rejected",
                        "error": "all requirements must belong to the episode"}
            forRid = {r.id for r in reqs}
            known_repos = {r.repo_uid for r in session.query(
                orm.GitRepository).all()}
            for repo_uid in repositories:
                if repo_uid not in known_repos:
                    return {"status": "rejected",
                            "error": f"unknown repository: {repo_uid[:80]}"}
            for f in originating_findings:
                if session.get(orm.WoFinding, f) is None:
                    return {"status": "rejected",
                            "error": f"unknown originating finding: {f}"}
            auth_ref = ""
            if authorization_proposal_id:
                p = session.get(orm.WoProposal,
                                authorization_proposal_id)
                if p is None:
                    return {"status": "rejected",
                            "error": "unknown authorization proposal"}
                if p.status != "approved":
                    return {"status": "rejected",
                            "error": "authorization proposal is not approved"}
                auth_ref = (f"proposal:{p.id}@v{p.version}:"
                            f"{p.scope_hash}")
            else:
                if not actor.strip() or not authorization_note.strip():
                    return {"status": "rejected",
                            "error": "direct authorization requires human "
                                     "actor + note (no auto-authorization)"}
                if actor.strip().lower() in ("system", "model"):
                    return {"status": "rejected",
                            "error": "authorization requires a human actor"}
                auth_ref = (f"human:{actor.strip()[:80]}:"
                            f"{authorization_note.strip()[:200]}")
            req_entries = [{"id": rid, "v": next(
                r.version for r in reqs if r.id == rid)}
                for rid in sorted(set(requirement_ids))
                if rid in forRid]
            digest = commission_digest_of(
                obj.text or "", req_entries, scope[:2000],
                acceptance_criteria[:2000], auth_ref, repositories,
                acceptance_policy_ref[:64])
            prev = session.query(orm.WoWorkEnvelope).filter(
                orm.WoWorkEnvelope.episode_id == episode_id,
                orm.WoWorkEnvelope.status == "active").order_by(
                orm.WoWorkEnvelope.version.desc()).first()
            if prev is not None and prev.commission_digest == digest:
                return {"status": "duplicate", "envelope_id": prev.id,
                        "version": prev.version}
            version = (prev.version + 1) if prev is not None else 1
            eid = "we:" + uuid.uuid4().hex[:16]
            now = now_iso()
            session.add(orm.WoWorkEnvelope(
                id=eid, episode_id=episode_id, schema_version=SCHEMA,
                programme_id=programme_id[:80], stage_id=stage_id[:32],
                objective_ref=objective_id,
                requirement_refs=req_entries,
                repositories=repositories,
                commission_digest=digest, authorization_ref=auth_ref,
                acceptance_policy_ref=acceptance_policy_ref[:64],
                parent_work_id=parent_work_id,
                originating_findings=originating_findings,
                version=version, status="active",
                supersedes=prev.id if prev is not None else None,
                observed_at=now, created_at=now))
            if prev is not None:
                prev.status = "superseded"
        return {"status": "completed", "envelope_id": eid,
                "version": version, "commission_digest": digest,
                "requirement_versions": req_entries}

    # -- execution linkage --------------------------------------------------
    def link_execution(self, *, envelope_id: str, route: str = "manual",
                       external_ref: str = "", model: str = "",
                       session_id: str = "", commit_sha: str = "",
                       test_receipt_ref: str = "", review_ref: str = "",
                       status: str = "handed_off",
                       proposal_id: str = "") -> dict[str, Any]:
        """Attach execution evidence to an envelope. Every cited ref is
        resolved (sessions, commits, receipts, reviews) or the call is
        rejected — the docstring promise from W7 review F1. Recording
        only; never starts execution."""
        if route != "manual":
            return {"status": "rejected",
                    "error": "only the manual route is offered in this "
                             "environment"}
        if status not in LINK_STATUSES:
            return {"status": "rejected",
                    "error": f"unknown link status: {status[:32]}"}
        with self._database.session() as session:
            env = session.get(orm.WoWorkEnvelope, envelope_id)
            if env is None:
                return {"status": "unknown_envelope"}
            if proposal_id:
                p = session.get(orm.WoProposal, proposal_id)
                if p is None:
                    return {"status": "rejected",
                            "error": "unknown proposal id"}
            commit_refs = {a.target_ref.split(":", 1)[-1].lower()
                           for a in session.query(
                               orm.WoEpisodeAssociation).filter(
                               orm.WoEpisodeAssociation.episode_id ==
                               env.episode_id,
                               orm.WoEpisodeAssociation.assoc_type ==
                               "commit",
                               orm.WoEpisodeAssociation.valid == 1).all()}
            if commit_sha and commit_sha.lower() not in commit_refs:
                if not self._git_object_exists(env, commit_sha):
                    return {"status": "rejected",
                            "error": "commit_sha resolves to neither a "
                                     "linked episode commit nor a known "
                                     "repo object"}
            if session_id and not self._session_exists(session_id):
                return {"status": "rejected",
                        "error": "session_id not found in observations"}
            if test_receipt_ref and session.query(orm.AitestReceipt).filter(
                    orm.AitestReceipt.execution_id ==
                    test_receipt_ref).first() is None:
                return {"status": "rejected",
                        "error": "test receipt not found"}
            if review_ref and session.get(orm.GitReview,
                                          review_ref) is None:
                return {"status": "rejected",
                        "error": "review not found"}
            lid = "wx:" + uuid.uuid4().hex[:16]
            now = now_iso()
            session.add(orm.WoExecutionLink(
                id=lid, proposal_id=proposal_id,
                route="manual", external_ref=external_ref[:300],
                model=model[:120], status=status,
                started_at=now, finished_at="", cost_usd=0.0,
                session_id=session_id[:160], commit_sha=commit_sha[:80],
                test_receipt_ref=test_receipt_ref[:160],
                review_ref=review_ref[:160], envelope_id=envelope_id,
                created_at=now))
        return {"status": "completed", "execution_id": lid,
                "envelope_id": envelope_id}

    def _session_exists(self, session_id: str) -> bool:
        if not self._opencode_db_path:
            return False
        try:
            from mission_control.work_observation import opencode_adapter as oa
            st = oa.status(self._opencode_db_path)
            if not st.available:
                return False
            conn = oa._connect_ro(self._opencode_db_path)
            try:
                row = conn.execute(
                    "SELECT id FROM session_v2 WHERE id=? "
                    "LIMIT 1", (session_id,)).fetchone()
                return row is not None
            finally:
                conn.close()
        except Exception:
            return False

    def _git_object_exists(self, env: Any, sha: str) -> bool:
        if not sha or len(sha) < 7 or any(
                c not in "0123456789abcdef" for c in sha.lower()):
            return False
        with self._database.session() as session:
            repos = {r.repo_uid: r.path for r in session.query(
                orm.GitRepository).all()}
        for uid in _jl(env.repositories):
            path = repos.get(uid)
            if not path:
                continue
            try:
                from mission_control.git.history import run_git as _rg
                proc = _rg(path, ["cat-file", "-e", sha], timeout=15.0)
                if proc is not None and proc.returncode == 0:
                    return True
            except Exception:
                continue
        return False

    # -- reads ------------------------------------------------------------------
    def list_envelopes(self, *,
                       episode_id: str | None = None,
                       limit: int = 100) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoWorkEnvelope).order_by(
                orm.WoWorkEnvelope.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoWorkEnvelope.episode_id == episode_id)
            return [{"id": r.id, "episode_id": r.episode_id,
                     "schema_version": r.schema_version,
                     "programme_id": r.programme_id, "stage_id": r.stage_id,
                     "objective_ref": r.objective_ref,
                     "requirement_refs": _jl(r.requirement_refs),
                     "repositories": _jl(r.repositories),
                     "commission_digest": r.commission_digest,
                     "authorization_ref": r.authorization_ref,
                     "acceptance_policy_ref": r.acceptance_policy_ref,
                     "parent_work_id": r.parent_work_id,
                     "originating_findings": _jl(r.originating_findings),
                     "version": r.version, "status": r.status,
                     "supersedes": r.supersedes}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def envelope_size_bytes(self, envelope_id: str) -> dict[str, Any]:
        """Context-overhead probe (§9/§26): the envelope carries metadata
        only; report its serialized size to prove it."""
        import json as _json
        rows = [r for r in self.list_envelopes(limit=500)
                if r["id"] == envelope_id]
        if not rows:
            return {"status": "unknown_envelope"}
        blob = _json.dumps(rows[0], sort_keys=True)
        return {"status": "completed", "envelope_id": envelope_id,
                "bytes": len(blob.encode()),
                "carries_conversation": False,
                "carries_evidence_packets": False}
