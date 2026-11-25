"""WORK-OUTCOME-01 W2 episode service: deterministic reconstruction + queries.

Reads W1 signals, OpenCode sessions and the existing git index; writes only
W2 episode tables. Zero model calls. No completion judgements — episode
``status`` is reconstruction status (candidate/established/superseded).
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from mission_control import models as orm
from mission_control.git.history import run_git
from mission_control.persistence.db import Database, now_iso
from mission_control.work_observation import opencode_adapter, reconstruct
from mission_control.work_observation.reconstruct import (
    EPISODE_VERSION,
    CommitRec,
    SessionRec,
    check_cycle,
)

SOURCE_KIND = "opencode"
RECON_VERSION = 1
MAX_COMMIT_FILES = 200


def _norm(p: str | None) -> str:
    return (p or "").replace("\\", "/").rstrip("/").lower()


class EpisodeService:
    def __init__(self, database: Database, opencode_db_path) -> None:
        from pathlib import Path

        self._database = database
        self._opencode_db_path = Path(opencode_db_path)

    # -- reconstruction --------------------------------------------------
    def run_reconstruction(self, *, project_contains: str | None = None,
                           limit_sessions: int = 500,
                           limit_signals: int = 20000) -> dict[str, Any]:
        started = time.monotonic()
        run_id = uuid.uuid4().hex[:16]
        scope = {"project_contains": project_contains or "",
                 "limit_sessions": limit_sessions, "limit_signals": limit_signals}
        project_key = (project_contains or "").strip() or "all"
        with self._database.session() as session:
            session.add(orm.WoReconRun(id=run_id, status="running",
                                       scope=scope, started_at=now_iso(),
                                       created_at=now_iso()))
        try:
            return self._execute(run_id, scope, project_key, started)
        except Exception as exc:
            with self._database.session() as session:
                run = session.get(orm.WoReconRun, run_id)
                if run is not None and run.status == "running":
                    run.status = "failed"
                    run.error = f"{type(exc).__name__}: {exc}"[:500]
                    run.finished_at = now_iso()
            raise

    def _execute(self, run_id: str, scope: dict[str, Any], project_key: str,
                 started: float) -> dict[str, Any]:
        st = opencode_adapter.status(self._opencode_db_path)
        if not st.available:
            return self._finish(run_id, "locked" if st.error == "locked"
                                else "source_unavailable",
                                error=f"{st.error}: {st.reason}", started=started)
        needle = scope["project_contains"].strip()
        conn = opencode_adapter._connect_ro(self._opencode_db_path)
        try:
            projects = {r["id"]: dict(r) for r in
                        opencode_adapter.fetch_projects(conn)}
            if needle:
                sessions = opencode_adapter.fetch_sessions_matching(
                    conn, needle, 0, scope["limit_sessions"])
            else:
                sessions = opencode_adapter.fetch_sessions_updated_since(
                    conn, 0, scope["limit_sessions"])
        finally:
            conn.close()

        with self._database.session() as session:
            repo_rows = session.query(orm.GitRepository).all()
            repos = [{"id": r.id, "path": r.path or "", "repo_uid": r.repo_uid or "",
                      "branch": r.branch or ""} for r in repo_rows]
            sig_rows = (session.query(orm.WoSignal)
                        .order_by(orm.WoSignal.observed_at.desc())
                        .limit(scope["limit_signals"]).all())
        session_ids = {s["id"] for s in sessions}
        signals_by_session: dict[str, dict[str, list[str]]] = {}
        for row in sig_rows:
            ref = row.source_ref or ""
            if not ref.startswith("opencode:"):
                continue
            sid = ref.split(":")[1] if ":" in ref else ""
            if sid not in session_ids:
                continue
            bucket = signals_by_session.setdefault(sid, {})
            vals = bucket.setdefault(row.signal_type, [])
            if len(vals) < 200:
                vals.append(row.value)

        def _repo_uid_for(directory: str, worktree: str) -> str | None:
            best: str | None = None
            best_len = -1
            for target in (directory, worktree):
                norm = _norm(target)
                if not norm:
                    continue
                for r in repos:
                    rp = _norm(r["path"])
                    if rp and (norm == rp or norm.startswith(rp + "/")) \
                            and len(rp) > best_len:
                        best, best_len = r["repo_uid"], len(rp)
            return best

        sess_recs: list[SessionRec] = []
        involved_repos: set[str] = set()
        for s in sessions:
            proj = projects.get(s["project_id"]) or {}
            ruid = _repo_uid_for(str(s["directory"] or ""),
                                 str(proj.get("worktree") or ""))
            if ruid:
                involved_repos.add(ruid)
            sess_recs.append(SessionRec(
                id=s["id"], parent_id=s["parent_id"],
                directory=str(s["directory"] or ""),
                worktree=str(proj.get("worktree") or ""), repo_uid=ruid,
                title=str(s["title"] or ""), first_ms=int(s["time_created"] or 0),
                last_ms=int(s["time_updated"] or 0)))

        with self._database.session() as session:
            commit_rows = []
            if involved_repos:
                wanted = [r["id"] for r in repos if r["repo_uid"] in involved_repos]
                if wanted:
                    commit_rows = (session.query(orm.GitCommit)
                                   .filter(orm.GitCommit.repo_id.in_(wanted))
                                   .order_by(orm.GitCommit.committer_ts.desc())
                                   .limit(2000).all())
        repo_path = {r["repo_uid"]: self._repo_workdir(repos, r["repo_uid"])
                     for r in repos}
        commit_recs: list[CommitRec] = []
        file_listed = 0
        for c in commit_rows:
            files: list[str] = []
            workdir = repo_path.get(self._ruid_of(repos, c.repo_id))
            if workdir and file_listed < MAX_COMMIT_FILES:
                files = self._commit_files(workdir, c.sha)
                file_listed += 1
            try:
                ts = int(c.committer_ts or 0)
            except (TypeError, ValueError):
                ts = 0
            commit_recs.append(CommitRec(
                repo_uid=self._ruid_of(repos, c.repo_id), sha=c.sha,
                message=str(c.subject or ""), time_ms=ts, files=files))

        result = reconstruct.reconstruct(sess_recs, signals_by_session,
                                         commit_recs, project_key=project_key)
        persisted = self._persist(run_id, project_key, result, sess_recs)
        envelope = self._finish(run_id, "completed", started=started,
                                episodes_found=len(result.episodes),
                                associations_made=persisted,
                                unresolved_observations=len(
                                    result.unresolved_session_ids),
                                truncated=len(sessions) >= scope["limit_sessions"])
        envelope["rejected_count"] = sum(
            1 for a in result.associations if a.method == "rejected")
        envelope["rules_fired"] = int(result.stats.get("rules_fired", 0))
        return envelope

    @staticmethod
    def _ruid_of(repos: list[dict[str, Any]], repo_id: str) -> str | None:
        for r in repos:
            if r["id"] == repo_id:
                return r["repo_uid"] or None
        return None

    @staticmethod
    def _repo_workdir(repos: list[dict[str, Any]], repo_uid: str | None) -> str | None:
        for r in repos:
            if r["repo_uid"] == (repo_uid or ""):
                return r["path"] or None
        return None

    @staticmethod
    def _commit_files(workdir: str, sha: str) -> list[str]:
        if not workdir or len(sha) < 7 or any(
                c not in "0123456789abcdef" for c in sha.lower()):
            return []
        proc = run_git(workdir, ["diff-tree", "--no-commit-id", "--name-only",
                                 "-r", sha, "--"], timeout=15.0)
        if proc is None or proc.returncode != 0:
            return []
        return [ln for ln in (proc.stdout or "").splitlines() if ln][:2000]

    def _persist(self, run_id: str, project_key: str,
                 result: Any, sess_recs: list[SessionRec]) -> int:
        made = 0
        with self._database.session() as session:
            existing = {e.id: e for e in session.query(orm.WoEpisode).filter(
                orm.WoEpisode.project_key == project_key).all()}
            # W6C fix: episode ids are globally unique (ep:task:…), but the
            # upsert scope above is project_key-bound. A re-run under a
            # different scope string ('ai' vs 'Projects/ai') found an empty
            # scoped map and bulk-INSERTed colliding ids (UniqueViolation on
            # re-run). Check global identity first; scope stays a query
            # convenience, never the identity.
            ids = [ep.id for ep in result.episodes]
            global_rows = {e.id: e for e in session.query(orm.WoEpisode).filter(
                orm.WoEpisode.id.in_(ids)).all()} if ids else {}
            parents = {eid: (e.parent_id or "") for eid, e in existing.items()}
            for ep in result.episodes:
                parents[ep.id] = ep.parent_id or parents.get(ep.id, "")
            for ep in result.episodes:
                row = existing.get(ep.id) or global_rows.get(ep.id)
                if row is None:
                    row = orm.WoEpisode(
                        id=ep.id, project_key=project_key, title=ep.title[:500],
                        kind=ep.kind, status=ep.status,
                        parent_id=None, first_seen_ms=ep.first_ms,
                        last_seen_ms=ep.last_ms, source_digest=ep.source_digest,
                        version=EPISODE_VERSION, created_at=now_iso(),
                        updated_at=now_iso())
                    session.add(row)
                    existing[ep.id] = row
                else:
                    # Review M9: version is a change counter, not a clock —
                    # bump only when material fields actually changed.
                    changed = (row.title != ep.title[:500] or row.kind != ep.kind
                               or row.status != ep.status
                               or row.first_seen_ms != ep.first_ms
                               or row.last_seen_ms != ep.last_ms
                               or row.source_digest != ep.source_digest)
                    row.title = ep.title[:500]
                    row.kind = ep.kind
                    row.status = ep.status
                    row.first_seen_ms = ep.first_ms
                    row.last_seen_ms = ep.last_ms
                    row.source_digest = ep.source_digest
                    if changed:
                        row.version = (row.version or 1) + 1
                        row.updated_at = now_iso()
                    # Keep the scoped map current (includes globally-found
                    # rows, which are in `current` so never retired below).
                    existing[ep.id] = row
                if ep.parent_id and not check_cycle(
                        {k: _P(v) for k, v in parents.items()}, ep.id, ep.parent_id):
                    row.parent_id = ep.parent_id
                    parents[ep.id] = ep.parent_id
            session.flush()
            pairs = {(a.episode_id, a.assoc_type, a.target_ref, a.method)
                     for a in result.associations if a.episode_id}
            have: dict[tuple, str] = {}
            if pairs:
                eps = list({p[0] for p in pairs})
                for i in range(0, len(eps), 500):
                    chunk = eps[i:i + 500]
                    rows = session.query(
                        orm.WoEpisodeAssociation.episode_id,
                        orm.WoEpisodeAssociation.assoc_type,
                        orm.WoEpisodeAssociation.target_ref,
                        orm.WoEpisodeAssociation.method,
                        orm.WoEpisodeAssociation.reason).filter(
                        orm.WoEpisodeAssociation.episode_id.in_(chunk)).all()
                    for r in rows:
                        have[(r[0], r[1], r[2], r[3])] = r[4] or ""
            for a in result.associations:
                if not a.episode_id:
                    continue  # rejected/unresolved markers live in run stats
                key = (a.episode_id, a.assoc_type, a.target_ref, a.method)
                if key in have:
                    # Re-review minor 1: distinct refusal reasons must not be
                    # silently collapsed — append unseen reasons to the row.
                    if a.reason and a.reason not in have[key]:
                        row = session.query(orm.WoEpisodeAssociation).filter(
                            orm.WoEpisodeAssociation.episode_id == a.episode_id,
                            orm.WoEpisodeAssociation.assoc_type == a.assoc_type,
                            orm.WoEpisodeAssociation.target_ref == a.target_ref,
                            orm.WoEpisodeAssociation.method == a.method).one_or_none()
                        if row is not None:
                            row.reason = (have[key] + "; " + a.reason)[:500]
                            have[key] = row.reason
                    continue
                have[key] = a.reason
                aid = hashlib.sha1(
                    f"{a.episode_id}|{a.assoc_type}|{a.target_ref}|{a.method}"
                    .encode()).hexdigest()[:24]
                session.add(orm.WoEpisodeAssociation(
                    id=aid, episode_id=a.episode_id, assoc_type=a.assoc_type,
                    target_ref=a.target_ref[:500], method=a.method,
                    confidence=a.confidence, reason=a.reason[:300],
                    signals=list(a.signals)[:20], recon_version=RECON_VERSION,
                    valid=1, created_at=now_iso()))
                made += 1
            # Supersession: same-scope episodes absent from this result retire
            # (review M4): status flips AND their links retire (valid=0) so
            # dropped evidence never lingers as current.
            current = {ep.id for ep in result.episodes}
            for eid, row in existing.items():
                if eid not in current and row.status != "superseded":
                    row.status = "superseded"
                    row.updated_at = now_iso()
                    session.query(orm.WoEpisodeAssociation).filter(
                        orm.WoEpisodeAssociation.episode_id == eid,
                        orm.WoEpisodeAssociation.valid == 1).update(
                        {"valid": 0})
        return made

    def _finish(self, run_id: str, status: str, *, started: float,
                error: str = "", episodes_found: int = 0,
                associations_made: int = 0, unresolved_observations: int = 0,
                truncated: bool = False) -> dict[str, Any]:
        now = now_iso()
        with self._database.session() as session:
            run = session.get(orm.WoReconRun, run_id)
            if run is not None:
                run.status = status
                run.error = error[:500]
                run.episodes_found = episodes_found
                run.associations_made = associations_made
                run.unresolved_observations = unresolved_observations
                run.finished_at = now
        return {"run_id": run_id, "status": status, "error": error,
                "episodes_found": episodes_found,
                "associations_made": associations_made,
                "unresolved_observations": unresolved_observations,
                "truncated": truncated,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "model_calls": 0, "model_cost": 0}

    # -- queries -----------------------------------------------------------
    def list_episodes(self, *, project_key: str | None = None,
                      kind: str | None = None, status: str | None = None,
                      limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoEpisode).order_by(orm.WoEpisode.updated_at.desc())
            if project_key:
                q = q.filter(orm.WoEpisode.project_key == project_key)
            if kind:
                q = q.filter(orm.WoEpisode.kind == kind)
            if status:
                q = q.filter(orm.WoEpisode.status == status)
            return [self._ep_read(r) for r in
                    q.limit(max(1, min(limit, 200))).offset(max(0, offset)).all()]

    def get_episode(self, episode_id: str) -> dict[str, Any] | None:
        with self._database.session() as session:
            row = session.get(orm.WoEpisode, episode_id)
            if row is None:
                return None
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.valid == 1).all()
            out = self._ep_read(row)
            out["associations"] = [self._assoc_read(a) for a in assocs]
            children = session.query(orm.WoEpisode).filter(
                orm.WoEpisode.parent_id == episode_id).all()
            out["children"] = [c.id for c in children]
            return out

    @staticmethod
    def _ep_read(r: Any) -> dict[str, Any]:
        return {"id": r.id, "project_key": r.project_key, "title": r.title,
                "kind": r.kind, "status": r.status, "parent_id": r.parent_id,
                "first_seen_ms": r.first_seen_ms, "last_seen_ms": r.last_seen_ms,
                "source_digest": r.source_digest, "version": r.version,
                "created_at": r.created_at, "updated_at": r.updated_at}

    @staticmethod
    def _assoc_read(a: Any) -> dict[str, Any]:
        return {"id": a.id, "episode_id": a.episode_id, "assoc_type": a.assoc_type,
                "target_ref": a.target_ref, "method": a.method,
                "confidence": a.confidence, "reason": a.reason,
                "signals": a.signals, "recon_version": a.recon_version,
                "valid": a.valid, "created_at": a.created_at}

    def list_unresolved(self, project_key: str) -> list[dict[str, Any]]:
        with self._database.session() as session:
            rows = session.query(orm.WoEpisode).filter(
                orm.WoEpisode.project_key == project_key,
                orm.WoEpisode.kind == "unresolved").all()
            out = []
            for r in rows:
                item = self._ep_read(r)
                assocs = session.query(orm.WoEpisodeAssociation).filter(
                    orm.WoEpisodeAssociation.episode_id == r.id,
                    orm.WoEpisodeAssociation.valid == 1).all()
                item["session_refs"] = [a.target_ref for a in assocs
                                        if a.assoc_type == "session"]
                out.append(item)
            return out

    def query_associations(self, *, episode_id: str | None = None,
                           assoc_type: str | None = None, valid: int = 1,
                           limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoEpisodeAssociation).order_by(
                orm.WoEpisodeAssociation.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoEpisodeAssociation.episode_id == episode_id)
            if assoc_type:
                q = q.filter(orm.WoEpisodeAssociation.assoc_type == assoc_type)
            q = q.filter(orm.WoEpisodeAssociation.valid == valid)
            return [self._assoc_read(a) for a in
                    q.limit(max(1, min(limit, 500))).all()]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._database.session() as session:
            rows = (session.query(orm.WoReconRun)
                    .order_by(orm.WoReconRun.created_at.desc())
                    .limit(max(1, min(limit, 200))).all())
            return [{"run_id": r.id, "status": r.status, "scope": r.scope,
                     "episodes_found": r.episodes_found,
                     "associations_made": r.associations_made,
                     "unresolved_observations": r.unresolved_observations,
                     "error": r.error, "started_at": r.started_at,
                     "finished_at": r.finished_at} for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._database.session() as session:
            r = session.get(orm.WoReconRun, run_id)
            if r is None:
                return None
            return {"run_id": r.id, "status": r.status, "scope": r.scope,
                    "episodes_found": r.episodes_found,
                    "associations_made": r.associations_made,
                    "unresolved_observations": r.unresolved_observations,
                    "error": r.error, "started_at": r.started_at,
                    "finished_at": r.finished_at}

    def coverage(self, project_key: str | None = None) -> dict[str, Any]:
        with self._database.session() as session:
            q = session.query(orm.WoEpisode)
            if project_key:
                q = q.filter(orm.WoEpisode.project_key == project_key)
            eps = q.all()
            kinds: dict[str, int] = {}
            statuses: dict[str, int] = {}
            for e in eps:
                kinds[e.kind] = kinds.get(e.kind, 0) + 1
                statuses[e.status] = statuses.get(e.status, 0) + 1
            assoc_total = session.query(orm.WoEpisodeAssociation).count()
            run_total = session.query(orm.WoReconRun).count()
        return {"episodes": len(eps), "kinds": kinds, "statuses": statuses,
                "stored_associations": assoc_total, "stored_runs": run_total,
                "model_calls": 0}


class _P:
    """Minimal parent-pointer adapter for check_cycle."""

    def __init__(self, parent_id: str | None) -> None:
        self.parent_id = parent_id or None
