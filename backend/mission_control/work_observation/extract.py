"""WORK-OUTCOME-01 W3 extraction service: deterministic + gated model paths.

Deterministic extraction (claims from CLAIMED signals, evidence candidates
from W2 associations, task objectives, session triage) runs without any model.
Model-backed requirement/objective drafting requires explicit enablement,
loopback-only endpoints, digest cache hits to be missed first, and remaining
budget (≤20 calls / $1 default). Every model output is post-validated before
anything is persisted.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from mission_control import models as orm
from mission_control.persistence.db import Database, now_iso
from mission_control.work_observation import evidence as ev
from mission_control.work_observation import opencode_adapter
from mission_control.work_observation.extract_schemas import (
    SCHEMA_VERSION,
    VALID_AUTHORITIES,
    VALID_TRIAGE,
    ClaimProposal,
    ExtractionPacket,
    ObjectiveProposal,
    is_tool_paraphrase,
    is_vacuous,
)
from mission_control.work_observation.triage import SessionSummary, triage

PROMPT_VERSION = "w3-v1"
MAX_CALLS_DEFAULT = 20
BUDGET_USD_DEFAULT = 1.0


def _sanitize_signal(signal_type: str, value: str) -> str:
    """Strip absolute host paths to bare file names before model submission
    (W4 pilot: absolute Temp paths leaked into stored requirements)."""
    if signal_type != "file_path":
        return value
    norm = (value or "").replace("\\", "/")
    return norm.rsplit("/", 1)[-1][:200]

_CODE_EXTS = (".py", ".ts", ".tsx", ".js", ".jsx", ".sql", ".rs", ".go",
              ".java", ".cs", ".sh", ".ps1")
_RESEARCH_HINTS = ("research", "plan", "notes", "design", "docs/")


def _is_code(path: str) -> bool:
    return path.replace("\\", "/").lower().endswith(_CODE_EXTS)


def _is_research(path: str) -> bool:
    low = path.replace("\\", "/").lower()
    return any(h in low for h in _RESEARCH_HINTS)


class ExtractionService:
    def __init__(self, database: Database, opencode_db_path,
                 *, model_enabled: bool = False,
                 model_backend: Any | None = None,
                 max_model_calls: int = MAX_CALLS_DEFAULT,
                 budget_usd: float = BUDGET_USD_DEFAULT) -> None:
        from pathlib import Path

        self._database = database
        self._opencode_db_path = Path(opencode_db_path)
        self._model_enabled = bool(model_enabled)
        self._backend = model_backend
        self._max_calls = max_model_calls
        self._budget = budget_usd

    # -- deterministic triage -------------------------------------------------
    def triage_scope(self, *, project_contains: str | None = None,
                     limit_sessions: int = 500) -> dict[str, Any]:
        started = time.monotonic()
        needle = (project_contains or "").strip()
        st = opencode_adapter.status(self._opencode_db_path)
        if not st.available:
            return {"status": st.error or "source_unavailable", "error": st.reason,
                    "triaged": 0, "model_calls": 0}
        conn = opencode_adapter._connect_ro(self._opencode_db_path)
        try:
            if needle:
                sessions = opencode_adapter.fetch_sessions_matching(
                    conn, needle, 0, limit_sessions)
            else:
                sessions = opencode_adapter.fetch_sessions_updated_since(
                    conn, 0, limit_sessions)
            sids = [s["id"] for s in sessions]
            by_type: dict[str, dict[str, int]] = {}
            first_user: dict[str, str] = {}
            for m in opencode_adapter.fetch_messages_for_sessions(conn, sids, 0, 20000):
                d = by_type.setdefault(m["session_id"], {})
                d[m["type"]] = d.get(m["type"], 0) + 1
                if m["type"] == "user" and m["session_id"] not in first_user:
                    parsed = opencode_adapter.parse_message("user", m["data"])
                    first_user[m["session_id"]] = parsed.get("excerpt", "")[:300]
        finally:
            conn.close()
        with self._database.session() as session:
            sig_rows = session.query(orm.WoSignal).all()
        sigs: dict[str, dict[str, list[str]]] = {}
        for r in sig_rows:
            if r.source_ref.startswith("opencode:"):
                sid = r.source_ref.split(":")[1]
                sigs.setdefault(sid, {}).setdefault(r.signal_type, []).append(r.value)
        with self._database.session() as session:
            rows = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.assoc_type == "session",
                orm.WoEpisodeAssociation.valid == 1).all()
            bucket_ids = {e.id for e in session.query(orm.WoEpisode.id).filter(
                orm.WoEpisode.kind == "unresolved").all()}
            # Rows are (id,) tuples under SQLite; normalize defensively.
            bucket_ids = {b[0] if isinstance(b, (tuple, list)) else b
                          for b in bucket_ids}
            ep_sessions = {a.target_ref for a in rows
                           if a.episode_id not in bucket_ids}
        run_id = uuid.uuid4().hex[:16]
        made = queued = 0
        with self._database.session() as session:
            for s in sessions:
                b = sigs.get(s["id"], {})
                counts = by_type.get(s["id"], {})
                files = list(b.get("file_path", []))
                code_files = [f for f in files if _is_code(f)]
                research_files = [f for f in files if _is_research(f)]
                summary = SessionSummary(
                    session_id=s["id"],
                    message_count=sum(counts.values()),
                    has_task=bool(b.get("task_id_candidate")),
                    has_sha=bool(b.get("commit_sha_candidate")),
                    has_files=bool(files),
                    has_claims=bool(b.get("test_claim") or b.get("completion_claim")),
                    has_tools=bool(b.get("tool_invocation")),
                    has_chain=bool(s["parent_id"]),
                    user_first=first_user.get(s["id"], ""),
                    code_files=code_files,
                    research_files=research_files,
                    in_episode=(f"opencode:{s['id']}" in ep_sessions),
                    review_tools=any("review" in t.lower() or "cocoder" in t.lower()
                                     for t in b.get("tool_invocation", [])))
                verdict = triage(summary)
                row = session.query(orm.WoTriageResult).filter(
                    orm.WoTriageResult.session_id == s["id"],
                    orm.WoTriageResult.run_id == run_id).one_or_none()
                if row is None:
                    session.add(orm.WoTriageResult(
                        id=uuid.uuid4().hex[:16], session_id=s["id"],
                        classification=verdict.classification, method="deterministic",
                        reason=verdict.reason,
                        queued_for_model=1 if verdict.queued_for_model else 0,
                        run_id=run_id, observed_at=now_iso(), created_at=now_iso()))
                    made += 1
                if verdict.queued_for_model:
                    queued += 1
        return {"status": "completed", "run_id": run_id, "triaged": made,
                "queued_for_model": queued,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "model_calls": 0, "model_cost": 0.0}

    # -- deterministic extraction ----------------------------------------------
    def extract_episode_deterministic(self, episode_id: str) -> dict[str, Any]:
        """Claims from CLAIMED signals, evidence candidates from W2 links,
        inferred objective for task episodes. Requirements need judgement and
        are explicitly abstained here (recorded, not invented)."""
        started = time.monotonic()
        with self._database.session() as session:
            ep = session.get(orm.WoEpisode, episode_id)
            if ep is None:
                return {"status": "unknown_episode", "written": {}}
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.valid == 1).all()
            sess_ids = [a.target_ref.split(":", 1)[1] for a in assocs
                        if a.assoc_type == "session" and ":" in a.target_ref]
            sig_rows = session.query(orm.WoSignal).filter(
                orm.WoSignal.source_kind == "opencode").all() if sess_ids else []
        by_sess: dict[str, list[Any]] = {}
        for r in sig_rows:
            parts = r.source_ref.split(":")
            if len(parts) >= 3 and parts[1] in sess_ids:
                by_sess.setdefault(parts[1], []).append(r)
        packet = self._deterministic_packet(episode_id, ep, by_sess)
        written = self._persist_packet(episode_id, packet, extractor="deterministic",
                                      input_digest=self._packet_digest(packet))
        return {"status": "completed", "episode_id": episode_id,
                "packet": packet.model_dump(), "written": written,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "model_calls": 0, "model_cost": 0.0}

    def _deterministic_packet(self, episode_id: str, ep: Any,
                              by_sess: dict[str, list[Any]]) -> ExtractionPacket:
        objectives: list[ObjectiveProposal] = []
        if ep.kind == "task":
            objectives.append(ObjectiveProposal(
                text=f"Achieve {ep.title}", authority="inferred",
                sources=[{"kind": "episode", "ref": episode_id}]))
        claims: list[ClaimProposal] = []
        for sid, rows in by_sess.items():
            for r in rows:
                if r.signal_type in ("test_claim", "completion_claim"):
                    claims.append(ClaimProposal(
                        claimant="assistant",
                        text=r.value[:500],
                        scope=f"session {sid[:12]}",
                        source={"kind": "signal", "ref": r.source_ref},
                        qualified=False))
        return ExtractionPacket(episode_id=episode_id, objectives=objectives,
                                claims=claims[:50])

    def _packet_digest(self, packet: ExtractionPacket) -> str:
        return hashlib.sha1(packet.model_dump_json().encode()).hexdigest()

    def _persist_packet(self, episode_id: str, packet: ExtractionPacket, *,
                        extractor: str, input_digest: str,
                        cost_usd: float = 0.0, tokens_in: int = 0,
                        tokens_out: int = 0, latency_ms: int = 0) -> dict[str, int]:
        counts = {"objectives": 0, "requirements": 0, "claims": 0, "evidence": 0}
        with self._database.session() as session:
            run = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.input_digest == input_digest,
                orm.WoExtractionRun.schema_version == SCHEMA_VERSION,
                orm.WoExtractionRun.prompt_version == PROMPT_VERSION,
                orm.WoExtractionRun.extractor == extractor).one_or_none()
            if run is not None:
                return {**counts, "cached": 1}
            run_id = uuid.uuid4().hex[:16]
            session.add(orm.WoExtractionRun(
                id=run_id, episode_id=episode_id, schema_version=SCHEMA_VERSION,
                prompt_version=PROMPT_VERSION, extractor=extractor,
                input_digest=input_digest, status="accepted",
                cost_usd=cost_usd, tokens_input=tokens_in,
                tokens_output=tokens_out, latency_ms=latency_ms,
                observed_at=now_iso(), created_at=now_iso()))
            for o in packet.objectives:
                session.add(orm.WoObjective(
                    id=uuid.uuid4().hex[:16], episode_id=episode_id,
                    text=o.text[:2000], authority=o.authority, status="current",
                    version=1, source_digest=input_digest, extractor=extractor,
                    observed_at=now_iso(), created_at=now_iso()))
                counts["objectives"] += 1
            req_ids_by_index: dict[int, str] = {}
            for i, q in enumerate(packet.requirements):
                rid = uuid.uuid4().hex[:16]
                req_ids_by_index[i] = rid
                session.add(orm.WoRequirement(
                    id=rid, episode_id=episode_id,
                    text=q.text[:2000], authority=q.authority,
                    mandatory=1 if q.mandatory else 0, kind=q.kind,
                    state="proposed", version=1, source_digest=input_digest,
                    extractor=extractor, observed_at=now_iso(),
                    created_at=now_iso()))
                counts["requirements"] += 1
            for cl in packet.claims:
                session.add(orm.WoClaim(
                    id=uuid.uuid4().hex[:16], episode_id=episode_id,
                    claimant=cl.claimant[:120], text=cl.text[:2000],
                    scope=cl.scope[:500],
                    source_ref=(cl.source.ref if cl.source else "")[:300],
                    qualified=1 if cl.qualified else 0,
                    evidence_available=0, observed_at=now_iso(),
                    created_at=now_iso()))
                counts["claims"] += 1
            for i, link in enumerate(packet.evidence_links):
                req_id = req_ids_by_index.get(link.requirement_index) \
                    if link.requirement_index is not None else None
                ref = link.evidence_ref[:500]
                if link.evidence_kind == "file":
                    # F6: persist basenames, never absolute host paths.
                    ref = ref.replace("\\", "/").rsplit("/", 1)[-1]
                    ref = f"file:{ref}" if not ref.startswith("file:") else ref
                session.add(orm.WoEvidenceLink(
                    id=uuid.uuid4().hex[:16],
                    requirement_id=req_id, claim_id=None,
                    evidence_kind=link.evidence_kind[:64],
                    evidence_ref=ref,
                    source_digest=input_digest, method="candidate",
                    confidence="weak", observed_at=now_iso(),
                    created_at=now_iso()))
                counts["evidence"] += 1
            # Deterministic W2-backed evidence candidates for this episode.
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.assoc_type == "commit",
                orm.WoEpisodeAssociation.valid == 1).all()
            for a in assocs:
                session.add(orm.WoEvidenceLink(
                    id=uuid.uuid4().hex[:16],
                    requirement_id=None, claim_id=None,
                    evidence_kind="git_commit", evidence_ref=a.target_ref[:500],
                    source_digest=a.id, method="candidate",
                    confidence=a.confidence, observed_at=now_iso(),
                    created_at=now_iso()))
                counts["evidence"] += 1
        return counts

    # -- model-backed session triage (gated) --------------------------------------
    def _budget_error(self) -> dict[str, Any] | None:
        with self._database.session() as session:
            spent_calls = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.extractor != "deterministic").count()
            spent_usd = sum(r.cost_usd for r in session.query(
                orm.WoExtractionRun.cost_usd).all())
        if spent_calls >= self._max_calls:
            return {"status": "budget_exhausted",
                    "error": "invocation cap reached", "model_calls": 0}
        if spent_usd >= self._budget:
            return {"status": "budget_exhausted",
                    "error": "spend ceiling reached", "model_calls": 0}
        return None

    def triage_session_model(self, session_id: str) -> dict[str, Any]:
        """One bounded model triage call for a queued session."""
        if not self._model_enabled or self._backend is None:
            return {"status": "model_not_enabled",
                    "error": "Model triage is gated.", "model_calls": 0}
        blocked = self._budget_error()
        if blocked:
            return blocked
        from mission_control.work_observation.ollama_backend import (
            TRIAGE_INSTRUCTION,
        )

        packet_input = self._session_packet(session_id)
        if packet_input is None:
            return {"status": "unknown_session", "model_calls": 0}
        digest = hashlib.sha1(packet_input.encode()).hexdigest()
        with self._database.session() as session:
            hit = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.input_digest == digest,
                orm.WoExtractionRun.schema_version == SCHEMA_VERSION,
                orm.WoExtractionRun.prompt_version == PROMPT_VERSION,
                orm.WoExtractionRun.extractor == self._backend.name).one_or_none()
            if hit is not None:
                return {"status": "cached", "session_id": session_id,
                        "model_calls": 0, "model_cost": 0.0}
        try:
            result = self._backend.complete(TRIAGE_INSTRUCTION + "\n" + packet_input)
        except Exception as exc:
            self._record_rejection(None, digest, f"{type(exc).__name__}: {exc}")
            return {"status": "provider_failed", "error": str(exc)[:300],
                    "model_calls": 1, "model_cost": 0.0}
        data = result.get("data")
        proposal = (data or {}).get("triage") if isinstance(data, dict) else None
        if not isinstance(proposal, dict) or proposal.get("classification") \
                not in VALID_TRIAGE:
            self._record_rejection(None, digest, "invalid triage proposal")
            return {"status": "rejected",
                    "error": "triage proposal failed validation",
                    "model_calls": 1, "model_cost": 0.0}
        run_id = uuid.uuid4().hex[:16]
        with self._database.session() as session:
            session.add(orm.WoTriageResult(
                id=uuid.uuid4().hex[:16], session_id=session_id,
                classification=proposal["classification"], method="model",
                reason=str(proposal.get("reason", ""))[:300],
                queued_for_model=0, run_id=run_id,
                observed_at=now_iso(), created_at=now_iso()))
            session.add(orm.WoExtractionRun(
                id=run_id, episode_id=None, schema_version=SCHEMA_VERSION,
                prompt_version=PROMPT_VERSION, extractor=self._backend.name,
                input_digest=digest, status="accepted",
                cost_usd=float(result.get("cost_usd", 0.0)),
                tokens_input=int(result.get("tokens_in", 0)),
                tokens_output=int(result.get("tokens_out", 0)),
                latency_ms=int(result.get("latency_ms", 0)),
                observed_at=now_iso(), created_at=now_iso()))
        return {"status": "completed", "session_id": session_id,
                "classification": proposal["classification"],
                "model_calls": 1, "model_cost": 0.0}

    def _session_packet(self, session_id: str) -> str | None:
        import json as _json

        st = opencode_adapter.status(self._opencode_db_path)
        if not st.available:
            return None
        conn = opencode_adapter._connect_ro(self._opencode_db_path)
        try:
            rows = conn.execute(
                "SELECT type, seq, data FROM session_message WHERE session_id=? "
                "ORDER BY seq ASC LIMIT 6", (session_id,)).fetchall()
            if not rows:
                return None
            excerpts = []
            for m in rows:
                parsed = opencode_adapter.parse_message(m["type"], m["data"])
                excerpts.append({"seq": m["seq"], "type": m["type"],
                                 "excerpt": parsed.get("excerpt", "")[:800]})
        finally:
            conn.close()
        with self._database.session() as session:
            sigs = [f"{r.signal_type}: {r.value[:200]}" for r in session.query(
                orm.WoSignal).filter(
                orm.WoSignal.source_ref.like(f"opencode:{session_id}:%")).limit(40)]
        return _json.dumps({"session": session_id, "messages": excerpts,
                            "signals": sigs})

    # -- model-backed extraction (gated) ----------------------------------------
    def extract_episode_model(self, episode_id: str) -> dict[str, Any]:
        if not self._model_enabled or self._backend is None:
            return {"status": "model_not_enabled",
                    "error": "Model extraction is gated: no governed route enabled.",
                    "model_calls": 0}
        with self._database.session() as session:
            spent_calls = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.extractor != "deterministic").count()
            spent_usd = sum(r.cost_usd for r in session.query(
                orm.WoExtractionRun.cost_usd).all())
        if spent_calls >= self._max_calls:
            return {"status": "budget_exhausted", "error": "invocation cap reached",
                    "model_calls": 0}
        if spent_usd >= self._budget:
            return {"status": "budget_exhausted", "error": "spend ceiling reached",
                    "model_calls": 0}
        packet_input = self._evidence_packet(episode_id)
        if packet_input is None:
            return {"status": "unknown_episode", "model_calls": 0}
        digest = hashlib.sha1(packet_input.encode()).hexdigest()
        with self._database.session() as session:
            hit = session.query(orm.WoExtractionRun).filter(
                orm.WoExtractionRun.input_digest == digest,
                orm.WoExtractionRun.schema_version == SCHEMA_VERSION,
                orm.WoExtractionRun.prompt_version == PROMPT_VERSION,
                orm.WoExtractionRun.extractor == self._backend.name).one_or_none()
            if hit is not None:
                return {"status": "cached", "episode_id": episode_id,
                        "model_calls": 0, "model_cost": 0.0}
        try:
            from mission_control.work_observation.ollama_backend import (
                EXTRACT_INSTRUCTION,
            )

            result = self._backend.complete(EXTRACT_INSTRUCTION + "\n" + packet_input)
        except Exception as exc:
            self._record_rejection(episode_id, digest, f"{type(exc).__name__}: {exc}")
            return {"status": "provider_failed", "error": str(exc)[:300],
                    "model_calls": 1, "model_cost": 0.0}
        packet, problems = self._validate_model_output(episode_id, result.get("data"))
        if problems:
            self._record_rejection(episode_id, digest, "; ".join(problems)[:500])
            return {"status": "rejected", "error": "; ".join(problems)[:500],
                    "model_calls": 1, "model_cost": float(result.get("cost_usd", 0.0))}
        written = self._persist_packet(
            episode_id, packet, extractor=self._backend.name, input_digest=digest,
            cost_usd=float(result.get("cost_usd", 0.0)),
            tokens_in=int(result.get("tokens_in", 0)),
            tokens_out=int(result.get("tokens_out", 0)),
            latency_ms=int(result.get("latency_ms", 0)))
        return {"status": "completed", "episode_id": episode_id, "written": written,
                "model_calls": 1, "model_cost": float(result.get("cost_usd", 0.0))}

    def _evidence_packet(self, episode_id: str) -> str | None:
        import json as _json

        with self._database.session() as session:
            ep = session.get(orm.WoEpisode, episode_id)
            if ep is None:
                return None
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.valid == 1).limit(200).all()
            sess_ids = [a.target_ref.split(":", 1)[1] for a in assocs
                        if a.assoc_type == "session" and ":" in a.target_ref][:12]
            sig_rows = session.query(orm.WoSignal).limit(10000).all() if sess_ids else []
        by_sess: dict[str, list[str]] = {}
        for r in sig_rows:
            parts = r.source_ref.split(":")
            if len(parts) >= 3 and parts[1] in sess_ids:
                redacted, _ = ev.excerpt_redacted(
                    _sanitize_signal(r.signal_type, r.value), 200)
                by_sess.setdefault(parts[1], []).append(
                    f"{r.signal_type}: {redacted}")
        return _json.dumps({"episode": {"id": ep.id, "kind": ep.kind,
                                        "title": ep.title[:300]},
                            "sessions": {sid: vals[:20]
                                         for sid, vals in by_sess.items()}})

    def _validate_model_output(self, episode_id: str,
                               data: Any) -> tuple[ExtractionPacket | None, list[str]]:
        problems: list[str] = []
        if not isinstance(data, dict):
            return None, ["output is not a JSON object"]
        try:
            packet = ExtractionPacket.model_validate(data)
        except Exception as exc:
            return None, [f"schema violation: {exc}"[:500]]
        with self._database.session() as session:
            assocs = session.query(
                orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.valid == 1).all()
            known_sessions = {a.target_ref for a in assocs}
            known_evidence = set()
            for a in assocs:
                if a.assoc_type == "commit":
                    known_evidence.add(f"git_commit:{a.target_ref}")
            sig_rows = session.query(orm.WoSignal).limit(20000).all()
        sess_ids = {t.split(":", 1)[1] for t in known_sessions
                    if t.startswith("opencode:") and ":" in t}
        for r in sig_rows:
            parts = r.source_ref.split(":")
            if len(parts) >= 3 and parts[1] in sess_ids:
                if r.signal_type == "file_path":
                    known_evidence.add(f"file:{_sanitize_signal('file_path', r.value)}")
                elif r.signal_type in ("test_claim", "completion_claim"):
                    known_evidence.add(f"claim:{r.value_digest}")
        for q in packet.requirements:
            if q.authority not in VALID_AUTHORITIES:
                problems.append(f"unknown authority: {q.authority}")
            if is_vacuous(q.text):
                problems.append("vacuous instruction echo in requirement")
            if is_tool_paraphrase(q.text):
                problems.append("tool-call paraphrase is not a user requirement")
            for s in q.sources:
                if s.kind == "session" and s.ref not in known_sessions:
                    problems.append(f"unknown source session: {s.ref[:80]}")
        known_commits: set[str] = set()
        for r in known_evidence:
            if r.startswith("git_commit:"):
                full = r.split(":", 1)[1]
                known_commits.add(full)
                known_commits.add(full.split(":", 1)[-1])
        for i, link in enumerate(packet.evidence_links):
            if link.evidence_kind == "git_commit":
                if link.evidence_ref not in known_commits:
                    problems.append(
                        f"unresolvable evidence ref: {link.evidence_ref[:80]}")
            elif link.evidence_kind == "file":
                base = link.evidence_ref.replace("\\", "/").rsplit("/", 1)[-1]
                if not any(r == f"file:{base}" or r.endswith("/" + base)
                           for r in known_evidence if r.startswith("file:")):
                    problems.append(f"unresolvable evidence ref: {link.evidence_ref[:80]}")
        for o in packet.objectives:
            if is_vacuous(o.text):
                problems.append("vacuous instruction echo in objective")
            for s in o.sources:
                if s.kind == "session" and s.ref not in known_sessions:
                    problems.append(f"unknown source session: {s.ref[:80]}")
            # W6A calibration: explicit_user must be grounded in a cited
            # session message. An episode-title echo with only an episode ref
            # is inference, not a user commission (observed mistral-small
            # over-claim on probe input, W6A benchmark 2026-11-24).
            if o.authority == "explicit_user" and not any(
                    s.kind == "session" for s in o.sources):
                problems.append("explicit_user objective without session source")
        if any(t not in ("explicit_user", "accepted_proposal", "inferred", "unknown")
               for t in [o.authority for o in packet.objectives]):
            problems.append("invalid objective authority")
        return (None, problems) if problems else (packet, [])

    def _record_rejection(self, episode_id: str, digest: str, error: str) -> None:
        with self._database.session() as session:
            session.add(orm.WoExtractionRun(
                id=uuid.uuid4().hex[:16], episode_id=episode_id,
                schema_version=SCHEMA_VERSION, prompt_version=PROMPT_VERSION,
                extractor=getattr(self._backend, "name", "model"),
                input_digest=digest, status="rejected", error=error[:500],
                observed_at=now_iso(), created_at=now_iso()))

    # -- queries ------------------------------------------------------------------
    def list_objectives(self, *, episode_id: str | None = None,
                        limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoObjective).order_by(
                orm.WoObjective.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoObjective.episode_id == episode_id)
            return [{"id": r.id, "episode_id": r.episode_id, "text": r.text,
                     "authority": r.authority, "status": r.status,
                     "version": r.version, "supersedes": r.supersedes,
                     "extractor": r.extractor}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def list_requirements(self, *, episode_id: str | None = None,
                          authority: str | None = None,
                          limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoRequirement).order_by(
                orm.WoRequirement.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoRequirement.episode_id == episode_id)
            if authority:
                q = q.filter(orm.WoRequirement.authority == authority)
            return [{"id": r.id, "episode_id": r.episode_id,
                     "objective_id": r.objective_id, "text": r.text,
                     "authority": r.authority, "mandatory": r.mandatory,
                     "kind": r.kind, "state": r.state, "version": r.version,
                     "extractor": r.extractor}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    # -- W6A human-reviewed requirement recovery -----------------------------
    def record_requirement_manual(self, *, episode_id: str, text: str,
                                  authority: str, mandatory: bool = True,
                                  kind: str = "functional",
                                  source_kind: str = "repo_doc",
                                  source_path: str = "",
                                  source_revision: str = "",
                                  source_digest: str = "",
                                  authority_basis: str = "",
                                  reviewer: str = "") -> dict[str, Any]:
        """Human-reviewed requirement insertion with mandatory provenance.

        Authority must be explicit_user or accepted_proposal; inferred and
        ambiguous are rejected here (use model extraction for drafts).
        source_digest + authority_basis are required: no provenance, no row.
        Vacuous/tool-paraphrase texts are rejected like model output.
        """
        text = (text or "").strip()
        if authority not in ("explicit_user", "accepted_proposal"):
            return {"status": "rejected",
                    "error": "manual recovery requires explicit_user or "
                             "accepted_proposal authority"}
        if not text or len(text) < 12:
            return {"status": "rejected", "error": "requirement text too short"}
        if not source_digest or not authority_basis.strip():
            return {"status": "rejected",
                    "error": "provenance required: source_digest and "
                             "authority_basis"}
        if is_vacuous(text) or is_tool_paraphrase(text):
            return {"status": "rejected",
                    "error": "vacuous or tool-paraphrase text rejected"}
        if kind not in ("functional", "constraint", "acceptance", "exclusion"):
            return {"status": "rejected", "error": "unknown requirement kind"}
        if source_kind not in ("repo_doc", "git_commit", "session_message",
                               "human_attestation"):
            return {"status": "rejected", "error": "unknown source_kind"}
        with self._database.session() as session:
            if session.get(orm.WoEpisode, episode_id) is None:
                return {"status": "unknown_episode"}
            rid = uuid.uuid4().hex[:16]
            session.add(orm.WoRequirement(
                id=rid, episode_id=episode_id, text=text[:2000],
                authority=authority, mandatory=1 if mandatory else 0,
                kind=kind, state="accepted", version=1,
                source_digest=source_digest[:64],
                extractor=f"human-reviewed:{reviewer[:40]}" if reviewer else "human-reviewed",
                observed_at=now_iso(), created_at=now_iso()))
            session.add(orm.WoRequirementSource(
                id=uuid.uuid4().hex[:16], requirement_id=rid,
                episode_id=episode_id, source_kind=source_kind,
                path=source_path[:500], revision=source_revision[:80],
                digest=source_digest[:64], authority_basis=authority_basis[:500],
                observed_at=now_iso(), created_at=now_iso()))
        return {"status": "completed", "requirement_id": rid,
                "episode_id": episode_id, "authority": authority}

    # -- W7 requirement confirmation ---------------------------------------------
    def record_confirmation(self, *, requirement_id: str, decision: str,
                            reviewer: str = "",
                            rationale: str = "",
                            amended_text: str = "") -> dict[str, Any]:
        """Human requirement decision (confirm/amend/reject/defer/
        insufficient). Amend spawns a new requirement version (supersedes
        old); the old row and this decision are preserved. No auto-confirm:
        reviewer is mandatory and decisions are explicit."""
        decision = (decision or "").strip()
        if decision not in ("confirm", "amend", "reject", "defer",
                            "insufficient"):
            return {"status": "rejected", "error": "unknown decision"}
        reviewer = (reviewer or "").strip()
        # F2 (W7 independent review): reviewer must be a human identity.
        # Self-asserted like the rest of the API (no auth layer), but a
        # literal system/model signature is refused outright.
        if not reviewer or reviewer.lower() in ("system", "model"):
            return {"status": "rejected",
                    "error": "reviewer is required (no auto-confirm, "
                             "no system/model signature)"}
        amended_text = (amended_text or "").strip()
        if decision == "amend":
            if len(amended_text) < 12:
                return {"status": "rejected",
                        "error": "amend requires amended_text"}
            if is_vacuous(amended_text) or is_tool_paraphrase(amended_text):
                return {"status": "rejected",
                        "error": "amended text fails validation gates"}
        with self._database.session() as session:
            r = session.get(orm.WoRequirement, requirement_id)
            if r is None:
                return {"status": "unknown_requirement"}
            cid = uuid.uuid4().hex[:16]
            session.add(orm.WoRequirementConfirmation(
                id=cid, requirement_id=requirement_id,
                episode_id=r.episode_id, decision=decision,
                reviewer=reviewer[:80], rationale=rationale[:500],
                amended_text=amended_text[:2000],
                created_at=now_iso()))
            new_id = None
            if decision == "amend":
                new_id = uuid.uuid4().hex[:16]
                session.add(orm.WoRequirement(
                    id=new_id, episode_id=r.episode_id,
                    objective_id=r.objective_id, text=amended_text[:2000],
                    authority=r.authority, mandatory=r.mandatory,
                    kind=r.kind, state="accepted", version=r.version + 1,
                    supersedes=requirement_id,
                    source_digest=r.source_digest,
                    extractor=f"human-amend:{reviewer[:40]}",
                    observed_at=now_iso(), created_at=now_iso()))
                r.state = "superseded"
        return {"status": "completed", "confirmation_id": cid,
                "decision": decision, "new_requirement_id": new_id}

    def list_confirmations(self, *,
                           requirement_id: str | None = None,
                           episode_id: str | None = None,
                           limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoRequirementConfirmation).order_by(
                orm.WoRequirementConfirmation.created_at.desc())
            if requirement_id:
                q = q.filter(orm.WoRequirementConfirmation.requirement_id
                             == requirement_id)
            if episode_id:
                q = q.filter(orm.WoRequirementConfirmation.episode_id
                             == episode_id)
            return [{"id": r.id, "requirement_id": r.requirement_id,
                     "episode_id": r.episode_id, "decision": r.decision,
                     "reviewer": r.reviewer, "rationale": r.rationale,
                     "amended_text": r.amended_text}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def list_requirement_sources(self, *,
                                 episode_id: str | None = None,
                                 limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoRequirementSource).order_by(
                orm.WoRequirementSource.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoRequirementSource.episode_id == episode_id)
            return [{"id": r.id, "requirement_id": r.requirement_id,
                     "episode_id": r.episode_id, "source_kind": r.source_kind,
                     "path": r.path, "revision": r.revision, "digest": r.digest,
                     "authority_basis": r.authority_basis}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def source_candidates(self, episode_id: str) -> dict[str, Any]:
        """Deterministic repo-artifact candidates for an episode (read-only).
        Resolves repo paths via linked commit associations; never assigns
        authority. Candidates with review siblings are flagged for human
        confirmation, never auto-accepted."""
        from mission_control.work_observation import req_sources as rs
        with self._database.session() as session:
            ep = session.get(orm.WoEpisode, episode_id)
            if ep is None:
                return {"status": "unknown_episode", "candidates": []}
            title = ep.title or ""
            assocs = session.query(orm.WoEpisodeAssociation).filter(
                orm.WoEpisodeAssociation.episode_id == episode_id,
                orm.WoEpisodeAssociation.assoc_type == "commit",
                orm.WoEpisodeAssociation.valid == 1).limit(50).all()
            repo_uids = {a.target_ref.split(":", 1)[0] for a in assocs
                         if ":" in a.target_ref}
            repos = session.query(orm.GitRepository).filter(
                orm.GitRepository.repo_uid.in_(list(repo_uids))).all() \
                if repo_uids else []
            paths = [r.path for r in repos if r.path]
        if not paths:
            # Fallback: match the episode's project_key tail to a known repo
            # path (episodes without linked commits, e.g. AI-CORE-05, still
            # belong to a project directory). Never guesses: basename match.
            tail = (ep.project_key or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            if tail:
                for r in session.query(orm.GitRepository).limit(500).all():
                    rp = (r.path or "").replace("\\", "/").rstrip("/")
                    if rp == tail or rp.endswith("/" + tail):
                        paths.append(r.path)
                        if len(paths) >= 3:
                            break
        if not paths:
            return {"status": "no_linked_repos", "candidates": [],
                    "episode_id": episode_id}
        out: list[dict[str, Any]] = []
        for p in paths[:3]:
            for c in rs.resolve_candidates(p, episode_id, title):
                out.append({"repo": p, "path": c.path,
                            "revision": c.revision, "digest": c.digest,
                            "has_review_sibling": c.has_review_sibling,
                            "review_path": c.review_path,
                            "suggested_authority": c.suggested_authority,
                            "basis": c.basis})
        return {"status": "completed", "episode_id": episode_id,
                "candidates": out[:25]}

    def list_claims(self, *, episode_id: str | None = None,
                    limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoClaim).order_by(orm.WoClaim.created_at.desc())
            if episode_id:
                q = q.filter(orm.WoClaim.episode_id == episode_id)
            return [{"id": r.id, "episode_id": r.episode_id,
                     "claimant": r.claimant, "text": r.text, "scope": r.scope,
                     "source_ref": r.source_ref, "qualified": r.qualified,
                     "evidence_available": r.evidence_available}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def list_evidence(self, *, requirement_id: str | None = None,
                      limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoEvidenceLink).order_by(
                orm.WoEvidenceLink.created_at.desc())
            if requirement_id:
                q = q.filter(orm.WoEvidenceLink.requirement_id == requirement_id)
            return [{"id": r.id, "requirement_id": r.requirement_id,
                     "claim_id": r.claim_id, "evidence_kind": r.evidence_kind,
                     "evidence_ref": r.evidence_ref, "method": r.method,
                     "confidence": r.confidence}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def list_triage(self, *, classification: str | None = None,
                    queued: int | None = None,
                    limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoTriageResult).order_by(
                orm.WoTriageResult.created_at.desc())
            if classification:
                q = q.filter(orm.WoTriageResult.classification == classification)
            if queued is not None:
                q = q.filter(orm.WoTriageResult.queued_for_model == queued)
            return [{"session_id": r.session_id,
                     "classification": r.classification, "method": r.method,
                     "reason": r.reason,
                     "queued_for_model": r.queued_for_model, "run_id": r.run_id}
                    for r in q.limit(max(1, min(limit, 500))).all()]

    def coverage(self, project_key: str | None = None) -> dict[str, Any]:
        with self._database.session() as session:
            q = session.query(orm.WoTriageResult)
            total = q.count()
            by_class: dict[str, int] = {}
            for r in q.all():
                by_class[r.classification] = by_class.get(r.classification, 0) + 1
            queued = sum(1 for r in q.all() if r.queued_for_model)
            return {"triaged_sessions": total, "by_classification": by_class,
                    "queued_for_model": queued,
                    "objectives": session.query(orm.WoObjective).count(),
                    "requirements": session.query(orm.WoRequirement).count(),
                    "claims": session.query(orm.WoClaim).count(),
                    "evidence_links": session.query(orm.WoEvidenceLink).count(),
                    "project_key": project_key or "all", "model_calls": 0}

    def get_cost(self) -> dict[str, Any]:
        with self._database.session() as session:
            runs = session.query(orm.WoExtractionRun).all()
        calls = sum(1 for r in runs if r.extractor != "deterministic"
                    and r.status != "cached")
        return {"model_calls": calls,
                "model_cost_usd": round(sum(r.cost_usd for r in runs), 6),
                "tokens_in": sum(r.tokens_input for r in runs),
                "tokens_out": sum(r.tokens_output for r in runs),
                "rejected": sum(1 for r in runs if r.status == "rejected"),
                "call_cap": self._max_calls, "budget_usd": self._budget,
                "model_enabled": self._model_enabled}
