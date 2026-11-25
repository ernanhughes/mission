"""WORK-OUTCOME-01 W4: work outcome evaluation service.

Deterministic first: mechanical claim verification, rule-based requirement
assessment, completion rollup, findings synthesis. Semantic layer (gated
loopback model, budgeted, cached, strictly validated) only for requirements
where evidence exists but judgement is required. Three perspectives stay
independent; no composite scores.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from mission_control import models as orm
from mission_control.persistence.db import Database, now_iso
from mission_control.work_observation.extract_schemas import is_vacuous
from mission_control.work_observation.verify import (
    RUBRIC_VERSION,
    ClaimVerification,
    EvidenceItem,
    RequirementAssessment,
    assess_requirement_deterministic,
    rollup_completion,
    verify_claim_deterministic,
)

PROMPT_VERSION = "w4-eval-v1"
MAX_CALLS_DEFAULT = 30
BUDGET_USD_DEFAULT = 2.0

EVAL_VERDICTS = {
    "satisfied_verified", "satisfied_reported", "partially_satisfied",
    "not_satisfied", "contradicted", "insufficient_evidence", "blocked",
    "authorized_deferral", "superseded", "not_applicable",
}


class EvaluationService:
    def __init__(self, database: Database, *, model_enabled: bool = False,
                 model_backend: Any | None = None,
                 max_model_calls: int = MAX_CALLS_DEFAULT,
                 budget_usd: float = BUDGET_USD_DEFAULT) -> None:
        self._database = database
        self._model_enabled = bool(model_enabled)
        self._backend = model_backend
        self._max_calls = max_model_calls
        self._budget = budget_usd

    # -- main entry ----------------------------------------------------------
    def evaluate_episode(self, episode_id: str, *,
                         semantic: bool = True) -> dict[str, Any]:
        started = time.monotonic()
        run_id = uuid.uuid4().hex[:16]
        with self._database.session() as session:
            session.add(orm.WoEvalRun(id=run_id, status="running",
                                      scope={"episode_id": episode_id},
                                      started_at=now_iso(), created_at=now_iso()))
        try:
            return self._execute(run_id, episode_id, semantic, started)
        except Exception as exc:
            with self._database.session() as session:
                run = session.get(orm.WoEvalRun, run_id)
                if run is not None and run.status == "running":
                    run.status = "failed"
                    run.error = f"{type(exc).__name__}: {exc}"[:500]
                    run.finished_at = now_iso()
            raise

    def _execute(self, run_id: str, episode_id: str, semantic: bool,
                 started: float) -> dict[str, Any]:
        with self._database.session() as session:
            ep = session.get(orm.WoEpisode, episode_id)
            if ep is None:
                return self._finish(run_id, "unknown_episode",
                                    error="no such episode", started=started)
            reqs = session.query(orm.WoRequirement).filter(
                orm.WoRequirement.episode_id == episode_id).all()
            claims = session.query(orm.WoClaim).filter(
                orm.WoClaim.episode_id == episode_id).all()
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.valid == 1).all()
        commits = sorted({a.target_ref.split(":", 1)[1] for a in assocs
                          if a.assoc_type == "commit" and ":" in a.target_ref})
        reviews = self._reviews_for_commits(commits)
        # Deterministic auto-linking before assessment (mechanical only).
        with self._database.session() as session:
            req_rows = session.query(orm.WoRequirement).filter(
                orm.WoRequirement.episode_id == episode_id).all()
            self._auto_link(session, episode_id, req_rows, commits)
        # Deterministic claim verification.
        from mission_control.work_observation.verify import claim_identity

        claim_rows = []
        with self._database.session() as session:
            for cl in claims:
                v = verify_claim_deterministic(
                    {"id": cl.id, "text": cl.text},
                    commits, [r["ref"] for r in reviews])
                claim_rows.append(self._store_claim_verification(
                    session, cl.id, episode_id, v, evaluator="deterministic",
                    digest=claim_identity(cl.text or "", cl.scope or "",
                                          cl.source_ref or "")))
        # Deterministic requirement assessment.
        links = self._evidence_for_requirements(episode_id, [r.id for r in reqs])
        det: dict[str, RequirementAssessment] = {}
        with self._database.session() as session:
            for r in reqs:
                ev_items = links.get(r.id, [])
                # F1: only *resolved* sibling evidence counts as corroboration.
                siblings = any(e.resolved for o in reqs if o.id != r.id
                               for e in links.get(o.id, []))
                a = assess_requirement_deterministic(
                    {"id": r.id, "authority": r.authority,
                     "mandatory": bool(r.mandatory), "kind": r.kind,
                     "text": r.text}, ev_items, siblings)
                det[r.id] = a
                self._store_req_assessment(session, episode_id, r.id, a,
                                           evaluator="deterministic",
                                           source_text=r.text or "")
        # Semantic layer for eligible requirements (one batched call).
        # F2: ambiguous-authority requirements are excluded — a model must
        # never upgrade an requirement whose authority is unestablished.
        sem_calls = 0
        sem_cost = 0.0
        eligible = [r for r in reqs if det[r.id].verdict in (
            "satisfied_reported", "insufficient_evidence",
            "partially_satisfied") and links.get(r.id)
            and r.authority not in ("ambiguous",)]
        if semantic and eligible and self._model_enabled and self._backend is not None:
            out = self._assess_requirements_model(episode_id, eligible, links,
                                                  commits, reviews)
            sem_calls = out.get("model_calls", 0)
            sem_cost = out.get("model_cost", 0.0)
        # Rollups + findings.
        with self._database.session() as session:
            final = self._latest_assessments(session, episode_id,
                                             [r.id for r in reqs])
        completion, completion_why = rollup_completion(
            list(final.values()),
            {r.id for r in reqs if r.mandatory})
        execution, exec_why = self._execution_view(episode_id, list(final.values()),
                                                   claim_rows)
        outcome, out_why = self._outcome_view(list(final.values()), reviews)
        merged_ok: set[str] = set()
        checked = 0
        for c in claim_rows:
            if checked >= 25:
                break
            for assoc in assocs:
                if assoc.assoc_type != "commit" or ":" not in assoc.target_ref:
                    continue
                repo_uid, sha = assoc.target_ref.split(":", 1)
                checked += 1
                if checked > 25:
                    break
                if self._merged_into_main(repo_uid, sha):
                    merged_ok.add(c["claim_id"])
                    break
        findings = self._synthesize_findings(
            episode_id, reqs, final, claim_rows,
            {c.id: (c.text or "") for c in claims},
            merged_claim_ids=merged_ok)
        with self._database.session() as session:
            assessment_id = uuid.uuid4().hex[:16]
            session.add(orm.WoEpisodeAssessment(
                id=assessment_id, episode_id=episode_id,
                execution_verdict=execution, execution_rationale=exec_why[:2000],
                outcome_verdict=outcome, outcome_rationale=out_why[:2000],
                completion_verdict=completion, completion_rationale=completion_why[:2000],
                evaluator="deterministic+model" if sem_calls else "deterministic",
                rubric_version=RUBRIC_VERSION, observed_at=now_iso(),
                created_at=now_iso()))
            # W6C: a fresh assessment clears staleness for this episode.
            from mission_control.work_observation import staleness as st
            st.refresh_after_eval(session, episode_id, assessment_id, now_iso())
            made = 0
            for f in findings:
                # Identical wording in one episode = one finding (keyed by
                # normalized claim text, not occurrence id); distinct wordings
                # keep distinct findings.
                scope = f["requirement_id"] or ""
                if not scope and f.get("claim_text"):
                    scope = "t:" + hashlib.sha1(
                        " ".join(f["claim_text"].lower().split()).encode()
                    ).hexdigest()[:16]
                fid = hashlib.sha1(
                    f"{episode_id}|{scope}|{f['kind']}".encode()
                ).hexdigest()[:24]
                if session.get(orm.WoFinding, fid) is None:
                    session.add(orm.WoFinding(
                        id=fid, episode_id=episode_id,
                        requirement_id=f["requirement_id"], kind=f["kind"],
                        severity=f["severity"], status=f["status"],
                        title=f["title"][:500], rationale=f["rationale"][:2000],
                        evidence_refs=f["evidence_refs"][:20],
                        next_action=f["next_action"][:500],
                        closure_evidence="", observed_at=now_iso(),
                        created_at=now_iso()))
                    made += 1
        with self._database.session() as session:
            run = session.get(orm.WoEvalRun, run_id)
            status, req_n, cl_n = "completed", len(final), len(claim_rows)
            if run is not None:
                run.status, run.episodes_evaluated, run.requirements_assessed = \
                    status, 1, req_n
                run.claims_verified, run.findings_raised = cl_n, made
                run.finished_at = now_iso()
        return {"run_id": run_id, "status": status, "episode_id": episode_id,
                "requirements_assessed": len(final),
                "claims_verified": len(claim_rows), "findings_raised": made,
                "completion": completion, "execution": execution,
                "outcome": outcome,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "model_calls": sem_calls, "model_cost": sem_cost}

    def _finish(self, run_id: str, status: str, *, started: float,
                error: str = "") -> dict[str, Any]:
        now = now_iso()
        with self._database.session() as session:
            run = session.get(orm.WoEvalRun, run_id)
            if run is not None:
                run.status = status
                run.error = error[:500]
                run.finished_at = now
        return {"run_id": run_id, "status": status, "error": error,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "model_calls": 0, "model_cost": 0.0}

    # -- evidence -------------------------------------------------------------
    def _commit_files(self, repo_path: str | None, sha: str) -> list[str]:
        if not repo_path or not sha or len(sha) < 7 or any(
                c not in "0123456789abcdef" for c in sha.lower()):
            return []
        from mission_control.git.history import run_git

        proc = run_git(repo_path, ["diff-tree", "--no-commit-id", "--name-only",
                                   "-r", sha, "--"], timeout=15.0)
        if proc is None or proc.returncode != 0:
            return []
        return [ln for ln in (proc.stdout or "").splitlines() if ln][:2000]

    def _auto_link(self, session: Any, episode_id: str,
                   reqs: list[Any], commits: list[str]) -> int:
        """Mechanical candidate links: SHA mentions resolving in episode
        commits, or file basenames matching commit diffs. Deterministic,
        confidence-capped, never a verdict by itself."""
        import re as _re

        made = 0
        repo_of = {c.split(":", 1)[0]: c.split(":", 1)[1] for c in commits
                   if ":" in c}
        repos = {r.repo_uid: r.path for r in session.query(
            orm.GitRepository).all()} if repo_of else {}
        # W6A fix: _evidence_for_requirements resolves git_commit links
        # against full association target_refs ("uid:sha"). Storing the bare
        # sha made every mechanical link unresolvable (silent
        # insufficient_evidence). Map suffix hits back to full refs.
        full_of: dict[str, str] = {}
        for a in session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.assoc_type == "commit",
                orm.WoEpisodeAssociation.valid == 1).all():
            full_of[a.target_ref.split(":", 1)[-1].lower()] = a.target_ref
        # File matching needs uid->sha even when `commits` are bare SHAs.
        for _full in full_of.values():
            if ":" in _full:
                _u, _s = _full.split(":", 1)
                repo_of.setdefault(_u, _s)
        repos = {r.repo_uid: r.path for r in session.query(
            orm.GitRepository).all()} if repo_of else {}
        file_cache: dict[str, list[str]] = {}
        existing = {(link.requirement_id, link.evidence_kind, link.evidence_ref)
                    for link in session.query(orm.WoEvidenceLink).filter(
                    orm.WoEvidenceLink.requirement_id.in_(
                        [r.id for r in reqs]) if reqs else False).all()} \
            if reqs else set()
        for r in reqs:
            text = r.text or ""
            for m in _re.findall(r"\b[0-9a-f]{7,40}\b", text.lower()):
                hit = next((c for c in commits
                            if c.lower().endswith(m) or m in c.lower()), None)
                full = full_of.get((hit or m).lower(), hit or m)
                if hit and (r.id, "git_commit", full) not in existing:
                    session.add(orm.WoEvidenceLink(
                        id=hashlib.sha1(f"{r.id}|git|{full}".encode()).hexdigest()[:24],
                        requirement_id=r.id, evidence_kind="git_commit",
                        evidence_ref=full, source_digest="auto-link",
                        method="deterministic", confidence="moderate",
                        observed_at=now_iso(), created_at=now_iso()))
                    existing.add((r.id, "git_commit", full))
                    made += 1
            for repo_uid, sha in repo_of.items():
                if sha not in file_cache:
                    file_cache[sha] = self._commit_files(
                        repos.get(repo_uid), sha)
                for f in file_cache[sha]:
                    base = f.rsplit("/", 1)[-1].lower()
                    if len(base) > 4 and base in text.lower():
                        ref = f"file:{f.rsplit('/', 1)[-1]}"
                        if (r.id, "file", ref) not in existing:
                            session.add(orm.WoEvidenceLink(
                                id=hashlib.sha1(
                                    f"{r.id}|file|{ref}".encode()).hexdigest()[:24],
                                requirement_id=r.id, evidence_kind="file",
                                evidence_ref=ref, source_digest="auto-link",
                                method="deterministic", confidence="weak",
                                observed_at=now_iso(), created_at=now_iso()))
                            existing.add((r.id, "file", ref))
                            made += 1
                            break
        return made
    def _reviews_for_commits(self, commits: list[str]) -> list[dict[str, str]]:
        if not commits:
            return []
        out: list[dict[str, str]] = []
        with self._database.session() as session:
            rows = session.query(orm.GitReview).limit(5000).all()
            for r in rows:
                shas = set()
                for attr in ("commit_sha", "base_sha", "target_sha"):
                    v = getattr(r, attr, None)
                    if v:
                        shas.add(str(v).lower())
                for s in (r.commit_shas or []):
                    shas.add(str(s).lower())
                hit = [c for c in commits if c.lower() in shas or
                       any(h.startswith(c.lower()) or c.lower().startswith(h)
                           for h in shas)]
                if hit:
                    out.append({"ref": f"review:{r.id}",
                                "verdict": str(r.verdict or ""),
                                "status": str(r.status or "")})
        return out

    def _evidence_for_requirements(self, episode_id: str,
                                   req_ids: list[str]) -> dict[str, list[Any]]:
        out: dict[str, list[Any]] = {i: [] for i in req_ids}
        with self._database.session() as session:
            links = session.query(orm.WoEvidenceLink).all()
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.assoc_type == "commit",
                orm.WoEpisodeAssociation.valid == 1).all()
            commit_refs = {a.target_ref for a in assocs}
        for link in links:
            if link.requirement_id in out:
                resolved = False
                if link.evidence_kind == "git_commit":
                    resolved = link.evidence_ref in commit_refs
                elif link.evidence_kind in ("file", "manifest", "test_report",
                                            "review", "remote_ref"):
                    # W8D: cited-but-unverified classes (remote containment,
                    # test reports, reviews) resolve by citation; verdicts
                    # stay reported, never verified, by assessment rule.
                    resolved = bool(link.evidence_ref)
                out[link.requirement_id].append(EvidenceItem(
                    link.evidence_kind, link.evidence_ref, resolved))
        # No blanket fallback: unlinked requirements stay link-less
        # (→ insufficient/not_satisfied). Attaching every commit to every
        # requirement would mark genuinely missing work as reported-satisfied.
        # Binding is W3's job (explicit links) or the semantic layer's.
        return out

    # -- persistence helpers ----------------------------------------------------
    def _store_claim_verification(self, session: Any, claim_id: str,
                                  episode_id: str, v: ClaimVerification,
                                  evaluator: str, digest: str = "") -> dict[str, Any]:
        row = session.query(orm.WoClaimVerification).filter(
            orm.WoClaimVerification.claim_id == claim_id,
            orm.WoClaimVerification.method == v.method,
            orm.WoClaimVerification.evaluator == evaluator).one_or_none()
        if row is not None:
            return {"claim_id": claim_id, "verdict": row.verdict,
                    "rationale": row.rationale,
                    "evidence": list(row.evidence_refs or []),
                    "cached": True}
        if digest:
            # F5: identical (text, scope, revision) verified before under a
            # different occurrence id → reuse the verdict, new occurrence row.
            prior = session.query(orm.WoClaimVerification).filter(
                orm.WoClaimVerification.source_digest == digest,
                orm.WoClaimVerification.method == v.method,
                orm.WoClaimVerification.evaluator == evaluator).first()
            if prior is not None:
                row = orm.WoClaimVerification(
                    id=uuid.uuid4().hex[:16], claim_id=claim_id,
                    episode_id=episode_id, verdict=prior.verdict,
                    rationale=prior.rationale,
                    evidence_refs=list(prior.evidence_refs or []),
                    source_digest=digest, method=v.method,
                    evaluator=evaluator, observed_at=now_iso(),
                    created_at=now_iso())
                session.add(row)
                return {"claim_id": claim_id, "verdict": row.verdict,
                        "rationale": row.rationale,
                        "evidence": list(row.evidence_refs or []),
                        "cached": True}
        row = orm.WoClaimVerification(
            id=uuid.uuid4().hex[:16], claim_id=claim_id,
            episode_id=episode_id, verdict=v.verdict,
            rationale=v.rationale[:2000],
            evidence_refs=list(v.evidence_refs)[:20], source_digest=digest,
            method=v.method,
            evaluator=evaluator, observed_at=now_iso(), created_at=now_iso())
        session.add(row)
        return {"claim_id": claim_id, "verdict": row.verdict,
                "rationale": row.rationale, "evidence": list(row.evidence_refs)}

    def _store_req_assessment(self, session: Any, episode_id: str, req_id: str,
                              a: RequirementAssessment, evaluator: str,
                              source_text: str = "") -> None:
        digest = hashlib.sha1(source_text.encode(errors="replace")).hexdigest()[:24] \
            if source_text else ""
        session.add(orm.WoRequirementAssessment(
            id=uuid.uuid4().hex[:16], requirement_id=req_id,
            episode_id=episode_id, verdict=a.verdict,
            rationale=a.rationale[:2000],
            evidence_refs=list(a.evidence_refs)[:20], method=a.method,
            evaluator=evaluator, rubric_version=RUBRIC_VERSION,
            confidence=a.confidence, limitations="",
            missing_evidence=a.missing[:500], source_digest=digest,
            observed_at=now_iso(), created_at=now_iso()))

    def _latest_assessments(self, session: Any, episode_id: str,
                            req_ids: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for rid in req_ids:
            row = session.query(orm.WoRequirementAssessment).filter(
                orm.WoRequirementAssessment.requirement_id == rid).order_by(
                orm.WoRequirementAssessment.created_at.desc()).first()
            if row is not None:
                out[rid] = row
        return out

    # -- semantic layer (gated) ---------------------------------------------------
    def _assess_requirements_model(self, episode_id: str, reqs: list[Any],
                                   links: dict[str, list[Any]],
                                   commits: list[str],
                                   reviews: list[dict[str, str]]) -> dict[str, Any]:
        import json as _json
        import re as _re

        def _sanitize(text: str) -> str:
            # F6: strip absolute host paths to bare tokens before submission.
            return _re.sub(r"[A-Za-z]:\\[^\s\"']*",
                           lambda m: m.group(0).replace("\\", "/").rsplit("/", 1)[-1],
                           text or "")

        blocked = self._budget_error()
        if blocked:
            return {**blocked, "model_cost": 0.0}
        packet = {"episode": episode_id, "requirements": [
            {"index": i, "id": r.id, "text": _sanitize(r.text)[:800],
             "authority": r.authority, "kind": r.kind,
             "evidence": [_sanitize(f"{e.kind}:{e.ref}") for e in links.get(r.id, [])][:10]}
            for i, r in enumerate(reqs)],
            "commits": commits[:20],
            "reviews": reviews[:10]}
        digest = hashlib.sha1(_json.dumps(packet, sort_keys=True).encode()).hexdigest()
        with self._database.session() as session:
            hit = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.input_digest == digest,
                orm.WoExtractionRun.schema_version == "w4-eval-v1",
                orm.WoExtractionRun.prompt_version == PROMPT_VERSION,
                orm.WoExtractionRun.extractor == self._backend.name).one_or_none()
            if hit is not None:
                return {"status": "cached", "model_calls": 0, "model_cost": 0.0}
        from mission_control.work_observation.ollama_backend import EVAL_INSTRUCTION
        try:
            result = self._backend.complete(
                EVAL_INSTRUCTION + "\n" + _json.dumps(packet))
        except Exception as exc:
            return {"status": "provider_failed", "error": str(exc)[:300],
                    "model_calls": 1, "model_cost": 0.0}
        data = result.get("data") if isinstance(result.get("data"), dict) else None
        verdicts = (data or {}).get("assessments")
        problems = self._validate_eval(verdicts, reqs, links)
        if problems:
            self._record_eval_run(episode_id, digest, "rejected", "; ".join(problems),
                                  result, 0, 0, 0)
            return {"status": "rejected", "error": "; ".join(problems)[:500],
                    "model_calls": 1, "model_cost": 0.0}
        with self._database.session() as session:
            by_index = {i: r for i, r in enumerate(reqs)}
            for v in verdicts:
                r = by_index[v["requirement_index"]]
                self._store_req_assessment(session, episode_id, r.id,
                                           RequirementAssessment(
                                               requirement_id=r.id,
                                               verdict=v["verdict"],
                                               rationale=v.get("rationale", "")[:2000],
                                               evidence_refs=v.get("evidence_refs", [])[:20],
                                               confidence=v.get("confidence", "moderate"),
                                               missing=v.get("missing", "")[:500],
                                               method="model"),
                                           evaluator=self._backend.name,
                                           source_text=r.text or '')
            self._record_eval_run(episode_id, digest, "accepted", "", result,
                                  len(verdicts), 0, 0)
        return {"status": "completed", "model_calls": 1,
                "model_cost": float(result.get("cost_usd", 0.0))}

    def _budget_error(self) -> dict[str, Any] | None:
        with self._database.session() as session:
            spent_calls = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.schema_version == "w4-eval-v1").count()
            spent_usd = sum(r.cost_usd for r in session.query(
                orm.WoExtractionRun.cost_usd).filter(
                orm.WoExtractionRun.schema_version == "w4-eval-v1").all())
        if spent_calls >= self._max_calls:
            return {"status": "budget_exhausted", "error": "cap reached"}
        if spent_usd >= self._budget:
            return {"status": "budget_exhausted", "error": "ceiling reached"}
        return None

    def _validate_eval(self, verdicts: Any, reqs: list[Any],
                       links: dict[str, list[Any]]) -> list[str]:
        from mission_control.work_observation.extract_schemas import (
            is_eval_vacuous as _is_eval_vacuous,
        )

        problems: list[str] = []
        if not isinstance(verdicts, list) or not verdicts:
            return ["assessments must be a non-empty list"]
        if len(verdicts) > 100:
            return ["too many assessments"]
        by_index = {i: r for i, r in enumerate(reqs)}
        known_refs = {f"{e.kind}:{e.ref}" for evs in links.values() for e in evs}
        known_resolved = {f"{e.kind}:{e.ref}" for evs in links.values() for e in evs
                          if e.resolved and e.kind in ("git_commit", "review", "test_report")}
        # W4-v2: remote_ref is resolved-by-citation for assessment, but it may
        # corroborate ONLY a relational requirement together with a bound
        # git_commit. It never verifies a non-relational requirement alone.
        known_resolved_relational = {
            f"{e.kind}:{e.ref}" for evs in links.values() for e in evs
            if e.resolved and e.kind in ("git_commit", "remote_ref")}
        for v in verdicts:
            if not isinstance(v, dict):
                problems.append("assessment must be an object")
                continue
            idx = v.get("requirement_index")
            if idx not in by_index:
                problems.append(f"unknown requirement index: {idx}")
                continue
            if v.get("verdict") not in EVAL_VERDICTS:
                problems.append(f"invalid verdict: {v.get('verdict')}")
            # F2: ambiguous-authority requirements can never be upgraded.
            if getattr(by_index[idx], "authority", "") == "ambiguous" and v.get(
                    "verdict") not in ("insufficient_evidence",):
                problems.append("ambiguous requirement must not be upgraded")
            # F4: satisfied_verified needs resolved corroborating evidence.
            # W4-v2: relational requirements need bound git_commit + remote_ref;
            # all other kinds keep the pre-v2 rule (remote_ref alone never verifies).
            if v.get("verdict") == "satisfied_verified":
                from mission_control.work_observation.verify import (
                    _is_relational_requirement as _is_rel,
                )
                _req = by_index[idx]
                _is_rel_req = (getattr(_req, "kind", "") == "relational"
                               or _is_rel(str(getattr(_req, "text", "") or "")))
                _refs = set(v.get("evidence_refs", []) or [])
                if _is_rel_req:
                    _has_git = bool(_refs & {r for r in known_resolved_relational
                                             if r.startswith("git_commit:")})
                    _has_remote = bool(_refs & {r for r in known_resolved_relational
                                                if r.startswith("remote_ref:")})
                    if not (_has_git and _has_remote):
                        problems.append("satisfied_verified relational requires "
                                        "bound git_commit + remote_ref")
                elif not (_refs & known_resolved):
                    problems.append("satisfied_verified requires resolved evidence")
            for ref in v.get("evidence_refs", []) or []:
                if ref not in known_refs:
                    problems.append(f"unknown evidence ref: {str(ref)[:80]}")
            rationale = str(v.get("rationale", ""))
            if len(rationale.strip()) < 20:
                problems.append("rationale too thin")
            if is_vacuous(rationale) or is_vacuous(str(v.get("missing", ""))):
                problems.append("vacuous instruction echo")
            if _is_eval_vacuous(rationale) or _is_eval_vacuous(str(v.get("missing", ""))):
                problems.append("vacuous eval instruction echo")
        return problems

    def _record_eval_run(self, episode_id: str, digest: str, status: str,
                         error: str, result: dict[str, Any],
                         n_req: int, n_cl: int, n_f: int) -> None:
        with self._database.session() as session:
            session.add(orm.WoExtractionRun(
                id=uuid.uuid4().hex[:16], episode_id=episode_id,
                schema_version="w4-eval-v1", prompt_version=PROMPT_VERSION,
                extractor=getattr(self._backend, "name", "model"),
                input_digest=digest, status=status, error=error[:500],
                cost_usd=float(result.get("cost_usd", 0.0)),
                tokens_input=int(result.get("tokens_in", 0)),
                tokens_output=int(result.get("tokens_out", 0)),
                latency_ms=int(result.get("latency_ms", 0)),
                observed_at=now_iso(), created_at=now_iso()))

    # -- perspectives + findings --------------------------------------------------
    def _execution_view(self, episode_id: str, assessments: list[Any],
                        claim_rows: list[dict[str, Any]]) -> tuple[str, str]:
        unsupported = [c for c in claim_rows
                       if c["verdict"] in ("reported_only", "unverified")
                       and any(w in (c.get("rationale", "") or "").lower()
                               for w in ("complet", "merg", "push", "deploy"))]
        if unsupported:
            return ("concerns", f"{len(unsupported)} completion-type claims lack "
                                f"independent evidence")
        if assessments and all(getattr(a, "verdict", "") in (
                "satisfied_verified", "authorized_deferral", "superseded",
                "not_applicable") for a in assessments):
            return ("sound", "all assessed requirements verified or legitimately closed")
        return ("unknown", "insufficient evidence to judge execution")

    def _outcome_view(self, assessments: list[Any],
                      reviews: list[dict[str, str]]) -> tuple[str, str]:
        verdicts = [getattr(a, "verdict", "insufficient_evidence") for a in assessments]
        if not verdicts:
            return ("unknown", "no requirements assessed")
        if any(v == "contradicted" for v in verdicts):
            return ("poor", "evidence contradicts assessed requirements")
        if any(v == "not_satisfied" for v in verdicts):
            return ("poor", "mandatory requirements unsatisfied")
        if all(v == "satisfied_verified" for v in verdicts):
            return ("good", "all assessed requirements verified")
        if any("request changes" in r.get("verdict", "").lower() for r in reviews):
            return ("mixed", "review requested changes")
        if any(v in ("satisfied_reported", "partially_satisfied") for v in verdicts):
            return ("mixed", "reported but not independently verified")
        return ("unknown", "evidence does not support an outcome judgement")

    def _merged_into_main(self, repo_uid, sha):
        """Deterministic merge corroboration: is sha an ancestor of the repo's
        main line? Read-only git plumbing, bounded. A merged commit does not
        prove a push/deployment happened - it only corroborates the merge."""
        if not repo_uid or not sha or len(sha) < 7:
            return False
        with self._database.session() as session:
            repo = session.query(orm.GitRepository).filter(
                orm.GitRepository.repo_uid == repo_uid).one_or_none()
            workdir = repo.path if repo else None
        if not workdir:
            return False
        from mission_control.git.history import run_git as _run_git
        for ref in ("main", "master", "origin/main", "HEAD"):
            try:
                proc = _run_git(workdir, ["merge-base", "--is-ancestor", sha, ref],
                                 timeout=15.0)
            except Exception:
                return False
            if proc is not None and proc.returncode == 0:
                return True
        return False

    def _synthesize_findings(self, episode_id: str, reqs: list[Any],
                             final: dict[str, Any],
                             claim_rows: list[dict[str, Any]],
                             claim_texts: dict[str, str] | None = None,
                             merged_claim_ids: set[str] | frozenset = frozenset()) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in reqs:
            a = final.get(r.id)
            if a is None:
                continue
            v = getattr(a, "verdict", "")
            if v == "not_satisfied" and r.mandatory:
                out.append({"requirement_id": r.id, "kind": "missing_requirement",
                            "severity": "major", "status": "suspected",
                            "title": f"Missing requirement: {r.text[:120]}",
                            "rationale": getattr(a, "rationale", ""),
                            "evidence_refs": [], "next_action": "implement or explicitly defer"})
            elif v == "satisfied_reported" and r.mandatory:
                out.append({"requirement_id": r.id, "kind": "verification_gap",
                            "severity": "minor", "status": "suspected",
                            "title": f"Reported but unverified: {r.text[:120]}",
                            "rationale": getattr(a, "rationale", ""),
                            "evidence_refs": [], "next_action": "supply independent verification"})
            elif v == "contradicted":
                out.append({"requirement_id": r.id, "kind": "defect",
                            "severity": "major", "status": "suspected",
                            "title": f"Contradicted requirement: {r.text[:120]}",
                            "rationale": getattr(a, "rationale", ""),
                            "evidence_refs": [], "next_action": "correct and re-verify"})
            elif v == "insufficient_evidence" and r.mandatory:
                out.append({"requirement_id": r.id, "kind": "verification_gap",
                            "severity": "minor", "status": "suspected",
                            "title": f"Unverified requirement: {r.text[:120]}",
                            "rationale": getattr(a, "rationale", ""),
                            "evidence_refs": [], "next_action": "supply verification evidence"})
        for c in claim_rows:
            if c["verdict"] not in ("reported_only", "unverified"):
                continue
            text = (claim_texts or {}).get(c["claim_id"], "").lower()
            is_completion = any(w in text for w in
                                ("complet", "merg", "push", "deploy"))
            is_test_report = (not is_completion) and any(
                w in text for w in ("all tests passed", "tests passed",
                                    "tests passed", "test passed"))
            if not (is_completion or is_test_report):
                continue
            if is_test_report:
                out.append({"requirement_id": None,
                            "claim_id": c.get("claim_id"),
                            "claim_text": (claim_texts or {}).get(c["claim_id"], "")[:200],
                            "kind": "verification_gap",
                            "severity": "minor", "status": "suspected",
                            "title": f"Unverified test report: {(claim_texts or {}).get(c['claim_id'], '')[:80]}",
                            "rationale": c.get("rationale", ""),
                            "evidence_refs": [],
                            "next_action": "supply execution record"})
            else:
                if c.get("claim_id") in (merged_claim_ids or frozenset()):
                    out.append({"requirement_id": None,
                                "claim_id": c.get("claim_id"),
                                "claim_text": (claim_texts or {}).get(c["claim_id"], "")[:200],
                                "kind": "verification_gap",
                                "severity": "minor", "status": "suspected",
                                "title": f"Merge corroborated, push unproven: {(claim_texts or {}).get(c['claim_id'], '')[:80]}",
                                "rationale": (c.get("rationale", "") + " Episode commits are merged into the main line; the push/deployment itself is unproven.")[:500],
                                "evidence_refs": [],
                                "next_action": "supply push/deployment evidence"})
                else:
                    # W6B severity policy w6b-v1: an uncorroborated historical
                    # completion claim with no counter-evidence is an evidence
                    # limitation (minor), not a confirmed defect (major).
                    # Major is reserved for contradicted claims (handled above
                    # as defect) and missing mandatory requirements. The kind
                    # stays unsupported_claim so no record disappears; only
                    # the consequence-based severity changes, and the rationale
                    # says why.
                    out.append({"requirement_id": None,
                                "claim_id": c.get("claim_id"),
                                "claim_text": (claim_texts or {}).get(c["claim_id"], "")[:200],
                                "kind": "unsupported_claim",
                                "severity": "minor", "status": "suspected",
                                "title": f"Unverified completion claim: {(claim_texts or {}).get(c['claim_id'], '')[:80]}",
                                "rationale": (c.get("rationale", "") + " [w6b-v1] Historical evidence limitation: no counter-evidence; severity reflects missing provenance, not a confirmed defect.")[:500],
                                "evidence_refs": [],
                                "next_action": "supply merge SHA / push record / execution record"})
        return out

    # -- queries --------------------------------------------------------------------
    def overview(self, *, project_key: str | None = None,
                 limit: int = 100) -> dict[str, Any]:
        """Compact per-episode rows for the W5 overview (one bounded call,
        no N+1). Read-only; never triggers evaluation or model calls."""
        with self._database.session() as session:
            q = session.query(orm.WoEpisode).order_by(
                orm.WoEpisode.updated_at.desc())
            if project_key:
                q = q.filter(orm.WoEpisode.project_key == project_key)
            eps = q.limit(max(1, min(limit, 200))).all()
            ids = [e.id for e in eps]
            latest: dict[str, Any] = {}
            if ids:
                for a in session.query(orm.WoEpisodeAssessment).filter(
                        orm.WoEpisodeAssessment.episode_id.in_(ids)).all():
                    prev = latest.get(a.episode_id)
                    if prev is None or a.created_at > prev.created_at:
                        latest[a.episode_id] = a
            open_findings: dict[str, int] = {}
            mand_open: dict[str, int] = {}
            if ids:
                for f in session.query(orm.WoFinding).filter(
                        orm.WoFinding.episode_id.in_(ids),
                        orm.WoFinding.status != "closed").all():
                    open_findings[f.episode_id] = open_findings.get(f.episode_id, 0) + 1
                    if f.requirement_id:
                        mand_open[f.episode_id] = mand_open.get(f.episode_id, 0) + 1
            # W6C: real freshness from wo_eval_state (one batched read).
            state_of: dict[str, Any] = {}
            if ids:
                for s in session.query(orm.WoEvalState).filter(
                        orm.WoEvalState.episode_id.in_(ids)).all():
                    state_of[s.episode_id] = s
            rows = []
            for e in eps:
                a = latest.get(e.id)
                es = state_of.get(e.id)
                rows.append({"id": e.id, "project_key": e.project_key,
                             "title": e.title, "kind": e.kind, "status": e.status,
                             "parent_id": e.parent_id,
                             "first_seen_ms": e.first_seen_ms,
                             "last_seen_ms": e.last_seen_ms,
                             "source_digest": e.source_digest,
                             "version": e.version,
                             "completion": a.completion_verdict if a else None,
                             "execution": a.execution_verdict if a else None,
                             "outcome": a.outcome_verdict if a else None,
                             "evaluated": a is not None,
                             "stale": bool(es.stale) if es is not None else False,
                             "stale_reason": es.stale_reason if es is not None else "",
                             "queue_status": es.queue_status if es is not None
                             else ("current" if a is not None else "unevaluated"),
                             "open_findings": open_findings.get(e.id, 0),
                             "mandatory_open": mand_open.get(e.id, 0)})
            return {"episodes": rows, "total": len(rows),
                    "project_key": project_key}

    def list_req_assessments(self, episode_id: str) -> list[dict[str, Any]]:
        with self._database.session() as session:
            rows = session.query(orm.WoRequirementAssessment).filter(
                orm.WoRequirementAssessment.episode_id == episode_id).all()
            return [{"id": r.id, "requirement_id": r.requirement_id,
                     "verdict": r.verdict, "rationale": r.rationale,
                     "evidence_refs": r.evidence_refs, "method": r.method,
                     "evaluator": r.evaluator, "confidence": r.confidence,
                     "missing_evidence": r.missing_evidence}
                    for r in rows]

    def list_claim_verifications(self, episode_id: str) -> list[dict[str, Any]]:
        with self._database.session() as session:
            rows = session.query(orm.WoClaimVerification).filter(
                orm.WoClaimVerification.episode_id == episode_id).all()
            return [{"id": r.id, "claim_id": r.claim_id, "verdict": r.verdict,
                     "rationale": r.rationale, "evidence_refs": r.evidence_refs,
                     "method": r.method} for r in rows]

    def get_episode_assessment(self, episode_id: str) -> dict[str, Any] | None:
        with self._database.session() as session:
            r = session.query(orm.WoEpisodeAssessment).filter(
                orm.WoEpisodeAssessment.episode_id == episode_id).order_by(
                orm.WoEpisodeAssessment.created_at.desc()).first()
            if r is None:
                return None
            return {"id": r.id, "episode_id": r.episode_id,
                    "execution": {"verdict": r.execution_verdict,
                                  "rationale": r.execution_rationale},
                    "outcome": {"verdict": r.outcome_verdict,
                                "rationale": r.outcome_rationale},
                    "completion": {"verdict": r.completion_verdict,
                                   "rationale": r.completion_rationale},
                    "evaluator": r.evaluator, "rubric_version": r.rubric_version}

    def list_findings(self, *, episode_id: str | None = None,
                      status: str | None = None,
                      limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoFinding).order_by(orm.WoFinding.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoFinding.episode_id == episode_id)
            if status:
                q = q.filter(orm.WoFinding.status == status)
            return [{"id": r.id, "episode_id": r.episode_id,
                     "requirement_id": r.requirement_id, "kind": r.kind,
                     "severity": r.severity, "status": r.status,
                     "title": r.title, "rationale": r.rationale,
                     "evidence_refs": r.evidence_refs,
                     "next_action": r.next_action}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    # -- W6B groups + W6C eval state ------------------------------------------
    def finding_groups(self) -> list[dict[str, Any]]:
        """Computed groups over open findings (no persistence; use
        persist_groups for the recorded pass). Presentation layer only."""
        from mission_control.work_observation import grouping as gp
        with self._database.session() as session:
            rows = session.query(orm.WoFinding).filter(
                orm.WoFinding.status != "resolved").limit(5000).all()
            eps = {r.episode_id for r in rows}
            proj_of = {}
            if eps:
                for e in session.query(orm.WoEpisode).filter(
                        orm.WoEpisode.id.in_(list(eps))).all():
                    proj_of[e.id] = e.project_key or ""
            findings = [{"id": r.id, "episode_id": r.episode_id,
                         "project_key": proj_of.get(r.episode_id, ""),
                         "kind": r.kind, "severity": r.severity,
                         "status": r.status, "title": r.title,
                         # Stored finding rows carry no claim linkage (W4
                         # schema); grouping derives the subject from the
                         # title, which embeds the claim's first 80 chars.
                         # Identical assertions group; distinct wordings stay
                         # distinct. Documented limitation in W6B report.
                         "claim_text": ""}
                        for r in rows]
            return gp.build_groups(findings)

    def persist_groups(self) -> dict[str, Any]:
        """Recorded grouping pass: upserts groups + membership. Members and
        history preserved; re-runnable (idempotent on group id)."""
        from mission_control.persistence.db import now_iso as _now
        groups = self.finding_groups()
        made = members = 0
        with self._database.session() as session:
            for g in groups:
                row = session.get(orm.WoFindingGroup, g["id"])
                if row is None:
                    session.add(orm.WoFindingGroup(
                        id=g["id"], project_key=g["project_key"],
                        subject=g["subject"], gap_class=g["gap_class"],
                        title=(g["title"] + " — "
                               + g.get("sample_title", ""))[:500],
                        severity=g["severity"],
                        status=g["status"], member_count=g["member_count"],
                        observed_at=_now(), created_at=_now()))
                    made += 1
                else:
                    row.title = (g["title"] + " — "
                                 + g.get("sample_title", ""))[:500]
                    row.severity = g["severity"]
                    row.status = g["status"]
                    row.member_count = g["member_count"]
                for fid in g["member_ids"]:
                    if session.get(orm.WoFindingGroupMember,
                                   {"group_id": g["id"],
                                    "finding_id": fid}) is None:
                        session.add(orm.WoFindingGroupMember(
                            group_id=g["id"], finding_id=fid))
                        members += 1
        return {"status": "completed", "groups": len(groups),
                "groups_created": made, "memberships_added": members}

    def reconcile_severity(self) -> dict[str, Any]:
        """Recorded w6b-v1 severity pass over stored findings."""
        from mission_control.work_observation import grouping as gp
        with self._database.session() as session:
            changed = gp.reconcile_severity_policy(session)
        return {"status": "completed", "policy": gp.SEVERITY_POLICY,
                "changed": len(changed), "changes": changed[:100]}

    def reconcile_resolved(self, actor: str = "",
                         reason: str = "") -> dict[str, Any]:
        """W6D §21 obligation reconciliation: close missing_requirement
        findings whose requirement now carries a satisfied assessment.
        W9A cross-family review: closure is system-attributed, so a human
        actor + reason are REQUIRED (same bar as resolve_finding) even
        though the evidence match itself is mechanical. Closure evidence
        cites the satisfying assessment; the finding row and its history
        are preserved (status change only, never deletion)."""
        actor = (actor or "").strip()
        if not actor or actor.lower() in ("system", "model"):
            return {"status": "rejected",
                    "error": "reconciliation requires a human actor"}
        if not reason.strip():
            return {"status": "rejected",
                    "error": "reconciliation requires a reason"}
        from mission_control.persistence.db import now_iso as _now
        resolved = []
        with self._database.session() as session:
            rows = session.query(orm.WoFinding).filter(
                orm.WoFinding.kind == "missing_requirement",
                orm.WoFinding.status != "resolved").all()
            for f in rows:
                if not f.requirement_id:
                    continue
                latest = session.query(orm.WoRequirementAssessment).filter(
                    orm.WoRequirementAssessment.requirement_id ==
                    f.requirement_id).order_by(
                    orm.WoRequirementAssessment.created_at.desc()).first()
                if latest is not None and latest.verdict in (
                        "satisfied_verified", "satisfied_reported"):
                    f.status = "resolved"
                    f.closure_evidence = (
                        f"[{actor.strip()[:40]}: {reason.strip()[:200]}] "
                        f"requirement {f.requirement_id} now {latest.verdict} "
                        f"(assessment {latest.id}, {latest.created_at}); "
                        f"recorded {_now()}")[:500]
                    resolved.append({"finding_id": f.id,
                                     "requirement_id": f.requirement_id,
                                     "verdict": latest.verdict})
        return {"status": "completed", "resolved": len(resolved),
                "items": resolved[:100]}

    def resolve_finding(self, finding_id: str, *,
                        closure_evidence: str,
                        actor: str = "") -> dict[str, Any]:
        """W7 §15 evidence-bound closure. The actor must be human; the
        evidence must cite verifiable records (never 'later work exists').
        History preserved; reopen via status change with new rationale
        (reopen_finding). Never called automatically."""
        closure_evidence = (closure_evidence or "").strip()
        if not closure_evidence or len(closure_evidence) < 20:
            return {"status": "rejected",
                    "error": "closure requires cited evidence (>=20 chars)"}
        if not actor.strip() or actor.strip().lower() in ("system", "model"):
            return {"status": "rejected",
                    "error": "closure requires a human actor"}
        with self._database.session() as session:
            f = session.get(orm.WoFinding, finding_id)
            if f is None:
                return {"status": "unknown_finding"}
            if f.status == "resolved":
                return {"status": "no_change", "finding_id": finding_id}
            f.status = "resolved"
            f.closure_evidence = (f"[{actor.strip()[:40]}] "
                                  + closure_evidence)[:500]
        return {"status": "completed", "finding_id": finding_id}

    def reopen_finding(self, finding_id: str, *,
                       reason: str, actor: str = "") -> dict[str, Any]:
        """Reopen when later evidence invalidates a closure. History kept."""
        from mission_control.persistence.db import now_iso as _now  # noqa: F401
        if not reason.strip() or not actor.strip():
            return {"status": "rejected",
                    "error": "reopen requires actor and reason"}
        with self._database.session() as session:
            f = session.get(orm.WoFinding, finding_id)
            if f is None:
                return {"status": "unknown_finding"}
            if f.status != "resolved":
                return {"status": "no_change", "finding_id": finding_id}
            f.status = "suspected"
            # F7 (W7 review): annotate, never erase — the refuted closure
            # evidence stays readable as history alongside the reopening.
            f.closure_evidence = ((f.closure_evidence or "")
                                  + f" [REOPENED by {actor.strip()[:40]}: "
                                  + reason.strip()[:200] + "]")[:500]
            f.rationale = ((f.rationale or "") + f" [reopened by "
                           f"{actor.strip()[:40]}: {reason.strip()[:200]}]")[:2000]
        return {"status": "completed", "finding_id": finding_id}

    def eval_state(self, *,
                   episode_id: str | None = None) -> list[dict[str, Any]]:
        from mission_control.work_observation import staleness as st
        with self._database.session() as session:
            if episode_id:
                return [st.get_state(session, episode_id)]
            rows = session.query(orm.WoEvalState).limit(500).all()
            return [{"episode_id": r.episode_id, "stale": r.stale,
                     "stale_reason": r.stale_reason,
                     "queue_status": r.queue_status,
                     "last_assessment_id": r.last_assessment_id}
                    for r in rows]

    def mark_stale(self, episode_id: str, reason: str) -> dict[str, Any]:
        from mission_control.work_observation import staleness as st
        from mission_control.persistence.db import now_iso as _now
        with self._database.session() as session:
            return st.mark_stale(session, episode_id, reason, _now())

    def eval_queue(self, limit: int = 20) -> list[dict[str, Any]]:
        from mission_control.work_observation import staleness as st
        with self._database.session() as session:
            return st.select_queue(session, limit=limit)

    # -- W6D governed operation -----------------------------------------------
    def get_auto(self) -> dict[str, Any]:
        """Scheduled semantic evaluation flag. Default OFF; deterministic
        observation never depends on it."""
        with self._database.session() as session:
            row = session.get(orm.Setting, "wo_auto_enabled")
            enabled = bool(row.value) if row is not None else False
            row2 = session.get(orm.Setting, "wo_auto_last_run")
            return {"auto_enabled": enabled,
                    "last_run": row2.value if row2 is not None else None,
                    "paid_budget_usd": 0.0,
                    "note": "automatic paid inference is never enabled; "
                            "semantic auto-eval requires a governed free route "
                            "and explicit enablement"}

    def set_auto(self, enabled: bool) -> dict[str, Any]:
        from mission_control.persistence.db import now_iso as _now
        with self._database.session() as session:
            row = session.get(orm.Setting, "wo_auto_enabled")
            if row is None:
                session.add(orm.Setting(key="wo_auto_enabled", value=bool(enabled),
                                        updated_at=_now()))
            else:
                row.value = bool(enabled)
                row.updated_at = _now()
        return self.get_auto()

    def coverage(self, project_key: str | None = None) -> dict[str, Any]:
        with self._database.session() as session:
            comp: dict[str, int] = {}
            for r in session.query(orm.WoEpisodeAssessment).all():
                comp[r.completion_verdict] = comp.get(r.completion_verdict, 0) + 1
            return {"episode_assessments": sum(comp.values()),
                    "completion_mix": comp,
                    "requirements_assessed": session.query(
                        orm.WoRequirementAssessment).count(),
                    "claims_verified": session.query(
                        orm.WoClaimVerification).count(),
                    "findings": session.query(orm.WoFinding).count(),
                    "project_key": project_key or "all", "model_calls": 0}

    def get_cost(self) -> dict[str, Any]:
        with self._database.session() as session:
            runs = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.schema_version == "w4-eval-v1").all()
        return {"model_calls": len(runs),
                "model_cost_usd": round(sum(r.cost_usd for r in runs), 6),
                "tokens_in": sum(r.tokens_input for r in runs),
                "tokens_out": sum(r.tokens_output for r in runs),
                "call_cap": self._max_calls, "budget_usd": self._budget,
                "model_enabled": self._model_enabled}
