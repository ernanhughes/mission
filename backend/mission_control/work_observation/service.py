"""WORK-OUTCOME-01 W1 observation service: incremental, idempotent, read-only.

Checkpoints advance only on completed runs. A timestamp-only watermark is
insufficient (ties, late arrivals, in-place updates), so every cursor is a
``(time_ms, tiebreak_id)`` pair plus an overlap window; stable signal ids make
re-delivery idempotent. Model calls: zero — this module never imports the
research/inference or Worker execution paths.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from mission_control import models as orm
from mission_control.git.history import resolve_identity
from mission_control.persistence.db import Database, now_iso
from mission_control.work_observation import opencode_adapter

SOURCE_KIND = "opencode"
OVERLAP_MS = 5 * 60 * 1000
DEFAULT_LIMIT_MESSAGES = 2000
DEFAULT_LIMIT_SESSIONS = 500

SESSION_CURSOR = "session_updated"
MESSAGE_CURSOR = "message_created"


def _signal_id(source_ref: str, signal_type: str, value_digest: str) -> str:
    return hashlib.sha1(
        f"{source_ref}|{signal_type}|{value_digest}".encode("utf-8")).hexdigest()[:24]


class WorkObservationService:
    def __init__(self, database: Database, opencode_db_path: Path,
                 overlap_ms: int = OVERLAP_MS) -> None:
        self._database = database
        self._opencode_db_path = Path(opencode_db_path)
        self._overlap_ms = max(0, int(overlap_ms))

    # -- health / coverage -------------------------------------------------
    def health(self) -> dict[str, Any]:
        """Source reachability + PG table presence + checkpoint state."""
        st = opencode_adapter.status(self._opencode_db_path)
        with self._database.session() as session:
            tables = self._table_names(session)
            checkpoints = self._read_checkpoints(session)
        return {
            "source": {"available": st.available, "source_path": st.source_path,
                       "reason": st.reason, "error": st.error,
                       "sessions": st.sessions, "messages": st.messages,
                       "parts": st.parts, "has_parts_table": st.has_parts_table},
            "store": {"has_tables": all(
                t in tables for t in ("wo_observation_runs", "wo_checkpoints",
                                      "wo_signals", "wo_observation_sources"))},
            "checkpoints": checkpoints,
            "model_calls": 0,
        }

    @staticmethod
    def _table_names(session: Any) -> set[str]:
        from sqlalchemy import inspect as _inspect

        try:
            return set(_inspect(session.get_bind()).get_table_names())
        except Exception:
            return set()

    def _read_checkpoints(self, session: Any) -> dict[str, dict[str, Any]]:
        try:
            rows = session.query(orm.WoCheckpoint).filter(
                orm.WoCheckpoint.source_kind == SOURCE_KIND).all()
        except Exception:
            return {}
        return {r.cursor_key: {"cursor_value_ms": r.cursor_value_ms,
                              "tiebreak_id": r.tiebreak_id,
                              "observed_at": r.observed_at} for r in rows}

    # -- observation runs --------------------------------------------------
    def run_observation(self, *, since_ms: int | None = None,
                        limit_messages: int = DEFAULT_LIMIT_MESSAGES,
                        limit_sessions: int = DEFAULT_LIMIT_SESSIONS,
                        project_contains: str | None = None) -> dict[str, Any]:
        """One bounded incremental pass. Returns a stats envelope."""
        started = time.monotonic()
        run_id = uuid.uuid4().hex[:16]
        now = now_iso()
        with self._database.session() as session:
            session.add(orm.WoObservationRun(
                id=run_id, source_kind=SOURCE_KIND, status="running",
                window_from_ms=int(since_ms or 0), started_at=now, created_at=now))
        try:
            return self._execute_run(run_id, since_ms=since_ms,
                                     limit_messages=limit_messages,
                                     limit_sessions=limit_sessions,
                                     project_contains=project_contains,
                                     started=started)
        except Exception as exc:  # never leak an open 'running' row
            with self._database.session() as session:
                run = session.get(orm.WoObservationRun, run_id)
                if run is not None and run.status == "running":
                    run.status = "failed"
                    run.error = f"{type(exc).__name__}: {exc}"[:500]
                    run.finished_at = now_iso()
            raise

    def _execute_run(self, run_id: str, *, since_ms: int | None,
                     limit_messages: int, limit_sessions: int,
                     project_contains: str | None, started: float) -> dict[str, Any]:
        st = opencode_adapter.status(self._opencode_db_path)
        if not st.available:
            status = "locked" if st.error == "locked" else "source_unavailable"
            return self._finish_run(run_id, status, error=f"{st.error}: {st.reason}",
                                    started=started)
        with self._database.session() as session:
            checkpoints = self._read_checkpoints(session)
        sess_hwm = checkpoints.get(SESSION_CURSOR, {}).get("cursor_value_ms", 0)
        msg_hwm = checkpoints.get(MESSAGE_CURSOR, {}).get("cursor_value_ms", 0)
        base = int(since_ms) if since_ms else 0
        if base:
            session_since = message_since = max(0, base)
        else:
            session_since = max(0, sess_hwm - self._overlap_ms)
            message_since = max(0, msg_hwm - self._overlap_ms)

        needle = (project_contains or "").strip()
        try:
            conn = opencode_adapter._connect_ro(self._opencode_db_path)
        except sqlite3.OperationalError as exc:
            if opencode_adapter._is_locked_error(exc):
                return self._finish_run(run_id, "locked", error=str(exc)[:300],
                                        started=started)
            return self._finish_run(run_id, "source_unavailable",
                                    error=str(exc)[:300], started=started)
        try:
            projects = {r["id"]: dict(r) for r in
                        opencode_adapter.fetch_projects(conn)}
            if needle:
                sessions = opencode_adapter.fetch_sessions_matching(
                    conn, needle, session_since, limit_sessions)
                messages = opencode_adapter.fetch_messages_for_sessions(
                    conn, [s["id"] for s in sessions], message_since,
                    limit_messages)
            else:
                sessions = opencode_adapter.fetch_sessions_updated_since(
                    conn, session_since, limit_sessions)
                messages = opencode_adapter.fetch_messages_created_since(
                    conn, message_since, limit_messages)
            try:
                # Review M6: parts rows are fetched only as a coverage count.
                # Content always comes from session_message.data (complete for
                # all eras); parts are a recent-only normalized split and are
                # never parsed for signals here.
                parts_seen = 0
                if st.has_parts_table:
                    assistant_ids = [m["id"] for m in messages if m["type"] == "assistant"]
                    if assistant_ids:
                        parts_seen = opencode_adapter.count_parts_for_messages(
                            conn, assistant_ids)
            except sqlite3.DatabaseError:
                parts_seen = 0
        except sqlite3.OperationalError as exc:
            if opencode_adapter._is_locked_error(exc):
                return self._finish_run(run_id, "locked", error=str(exc)[:300],
                                        started=started)
            return self._finish_run(run_id, "failed", error=str(exc)[:300],
                                    started=started)
        finally:
            conn.close()

        needle = (project_contains or "").strip()
        session_by_id = {s["id"]: s for s in sessions}
        if needle:
            lowered = needle.lower()
            session_by_id = {
                k: v for k, v in session_by_id.items()
                if lowered in str(v["directory"] or "").lower()
                or lowered in str((projects.get(v["project_id"]) or {}).get("worktree") or "").lower()
                or lowered in str((projects.get(v["project_id"]) or {}).get("name") or "").lower()
            }
            messages = [m for m in messages if m["session_id"] in session_by_id]

        signals: list[dict[str, Any]] = []
        for m in messages:
            sess = session_by_id.get(m["session_id"])
            if sess is None:
                continue
            parsed = opencode_adapter.parse_message(m["type"], m["data"])
            if parsed.get("parse_error") and m["type"] not in ("assistant", "user"):
                continue
            text = parsed.get("excerpt") or ""
            tools = parsed.get("tool_calls") or []
            ref = f"opencode:{m['session_id']}:{m['seq']}"
            for sig in opencode_adapter.extract_signals(
                    ref, text, tools, sess["directory"],
                    {"session_id": m["session_id"], "seq": m["seq"],
                     "msg_type": m["type"], "run_id": run_id}):
                signals.append({
                    "id": _signal_id(ref, sig.signal_type, sig.value_digest),
                    "run_id": run_id, "source_kind": SOURCE_KIND,
                    "source_ref": ref, "signal_type": sig.signal_type,
                    "value": sig.value[:500], "value_digest": sig.value_digest,
                    "evidence_class": sig.evidence_class,
                    "provenance": dict(sig.provenance), "observed_at": now_iso()})

        with self._database.session() as session:
            existing = set()
            if signals:
                ids = list({s["id"] for s in signals})
                for i in range(0, len(ids), 500):
                    chunk = ids[i:i + 500]
                    rows = session.query(orm.WoSignal.id).filter(
                        orm.WoSignal.id.in_(chunk)).all()
                    existing.update(r[0] for r in rows)
            new_signals = [s for s in signals if s["id"] not in existing]
            # Second in-memory dedupe: identical (ref,type,digest) twice in one run.
            seen: set[str] = set()
            unique_new: list[dict[str, Any]] = []
            for s in new_signals:
                if s["id"] not in seen:
                    seen.add(s["id"])
                    unique_new.append(s)
            for s in unique_new:
                session.add(orm.WoSignal(**s))
            # Advance checkpoints only on success; keep max (time,id) observed.
            max_sess = self._max_cursor(
                [(s["time_updated"], s["id"]) for s in session_by_id.values()])
            max_msg = self._max_cursor(
                [(m["time_created"], m["id"]) for m in messages])
            if max_sess[0] >= 0:
                self._upsert_checkpoint(session, SESSION_CURSOR, *max_sess)
            if max_msg[0] >= 0:
                self._upsert_checkpoint(session, MESSAGE_CURSOR, *max_msg)
            self._upsert_source(session, st)

        window_to = max([m["time_created"] for m in messages] or [0])
        return self._finish_run(
            run_id, "completed", started=started,
            sessions_seen=len(session_by_id), messages_seen=len(messages),
            parts_seen=parts_seen, signals_produced=len(signals),
            signals_new=len(unique_new),
            truncated=len(sessions) >= limit_sessions or len(messages) >= limit_messages,
            window_from_ms=min(session_since, message_since), window_to_ms=window_to)

    @staticmethod
    def _max_cursor(pairs: list[tuple[int, str]]) -> tuple[int, str]:
        best: tuple[int, str] = (-1, "")
        for t, i in pairs:
            if (int(t), str(i)) > (best[0], best[1]):
                best = (int(t), str(i))
        return best

    def _upsert_checkpoint(self, session: Any, key: str, value_ms: int,
                           tiebreak: str) -> None:
        row = session.get(orm.WoCheckpoint, {"source_kind": SOURCE_KIND,
                                             "cursor_key": key})
        if row is None:
            session.add(orm.WoCheckpoint(
                source_kind=SOURCE_KIND, cursor_key=key,
                cursor_value_ms=int(value_ms), tiebreak_id=str(tiebreak),
                observed_at=now_iso()))
        elif (int(value_ms), str(tiebreak)) > (int(row.cursor_value_ms), row.tiebreak_id):
            row.cursor_value_ms = int(value_ms)
            row.tiebreak_id = str(tiebreak)
            row.observed_at = now_iso()

    def _upsert_source(self, session: Any, st: Any) -> None:
        now = now_iso()
        row = session.query(orm.WoObservationSource).filter(
            orm.WoObservationSource.kind == SOURCE_KIND,
            orm.WoObservationSource.identity == st.source_path).one_or_none()
        fingerprint = f"sessions={st.sessions};messages={st.messages};parts={st.parts}"
        if row is None:
            session.add(orm.WoObservationSource(
                id=uuid.uuid4().hex[:16], kind=SOURCE_KIND,
                identity=st.source_path, fingerprint=fingerprint,
                last_seen_at=now, created_at=now, updated_at=now))
        else:
            row.fingerprint = fingerprint
            row.last_seen_at = now
            row.updated_at = now

    def _finish_run(self, run_id: str, status: str, *, started: float,
                    error: str = "", sessions_seen: int = 0,
                    messages_seen: int = 0, parts_seen: int = 0,
                    signals_produced: int = 0, signals_new: int = 0,
                    truncated: bool = False, window_from_ms: int = 0,
                    window_to_ms: int = 0) -> dict[str, Any]:
        now = now_iso()
        with self._database.session() as session:
            run = session.get(orm.WoObservationRun, run_id)
            if run is not None:
                run.status = status
                run.error = error[:500]
                run.sessions_seen = sessions_seen
                run.messages_seen = messages_seen
                run.parts_seen = parts_seen
                run.signals_produced = signals_produced
                run.window_from_ms = window_from_ms
                run.window_to_ms = window_to_ms
                run.finished_at = now
        return {"run_id": run_id, "status": status, "error": error,
                "sessions_seen": sessions_seen, "messages_seen": messages_seen,
                "parts_seen": parts_seen, "signals_produced": signals_produced,
                "signals_new": signals_new, "truncated": truncated,
                "window_from_ms": window_from_ms, "window_to_ms": window_to_ms,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "model_calls": 0, "model_cost": 0}

    # -- queries -----------------------------------------------------------
    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._database.session() as session:
            rows = (session.query(orm.WoObservationRun)
                    .order_by(orm.WoObservationRun.created_at.desc())
                    .limit(max(1, min(limit, 200))).all())
            return [self._run_read(r) for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._database.session() as session:
            row = session.get(orm.WoObservationRun, run_id)
            return self._run_read(row) if row else None

    @staticmethod
    def _run_read(r: Any) -> dict[str, Any]:
        return {"run_id": r.id, "source_kind": r.source_kind, "status": r.status,
                "window_from_ms": r.window_from_ms, "window_to_ms": r.window_to_ms,
                "sessions_seen": r.sessions_seen, "messages_seen": r.messages_seen,
                "parts_seen": r.parts_seen, "signals_produced": r.signals_produced,
                "error": r.error, "started_at": r.started_at,
                "finished_at": r.finished_at, "created_at": r.created_at}

    def get_checkpoints(self) -> dict[str, dict[str, Any]]:
        with self._database.session() as session:
            return self._read_checkpoints(session)

    def query_signals(self, *, signal_type: str | None = None,
                      source_ref: str | None = None,
                      limit: int = 200) -> list[dict[str, Any]]:
        with self._database.session() as session:
            q = session.query(orm.WoSignal).order_by(orm.WoSignal.observed_at.desc())
            if signal_type:
                q = q.filter(orm.WoSignal.signal_type == signal_type)
            if source_ref:
                q = q.filter(orm.WoSignal.source_ref.like(f"{source_ref}%"))
            rows = q.limit(max(1, min(limit, 500))).all()
            return [{"id": r.id, "run_id": r.run_id, "source_kind": r.source_kind,
                     "source_ref": r.source_ref, "signal_type": r.signal_type,
                     "value": r.value, "value_digest": r.value_digest,
                     "evidence_class": r.evidence_class, "provenance": r.provenance,
                     "observed_at": r.observed_at} for r in rows]

    def coverage(self) -> dict[str, Any]:
        """Source inventory vs stored checkpoints, runs and signal mix."""
        st = opencode_adapter.status(self._opencode_db_path)
        with self._database.session() as session:
            checkpoints = self._read_checkpoints(session)
            try:
                signal_count = session.query(orm.WoSignal).count()
                run_count = session.query(orm.WoObservationRun).count()
            except Exception:
                signal_count = run_count = -1
        try:
            type_counts: dict[str, int] = {}
            if st.available:
                conn = opencode_adapter._connect_ro(self._opencode_db_path)
                try:
                    type_counts = opencode_adapter.message_type_counts(conn)
                finally:
                    conn.close()
        except Exception:
            type_counts = {}
        return {"source": {"available": st.available, "reason": st.reason,
                           "error": st.error, "sessions": st.sessions,
                           "messages": st.messages, "parts": st.parts,
                           "has_parts_table": st.has_parts_table},
                "message_types": type_counts,
                "checkpoints": checkpoints,
                "stored_runs": run_count, "stored_signals": signal_count,
                "model_calls": 0}

    # -- git reuse ---------------------------------------------------------
    def git_status_for_directories(self, directories: list[str]) -> list[dict[str, Any]]:
        """Resolve observed working directories against indexed git repos.

        Read-only: ``resolve_identity`` runs git plumbing only; repository
        rows come from the existing ``git_repositories`` index (no second
        history system).
        """
        out: list[dict[str, Any]] = []
        with self._database.session() as session:
            for directory in directories[:100]:
                item: dict[str, Any] = {"directory": directory, "repo_uid": None,
                                        "indexed": False, "head_sha": None,
                                        "branch": None, "repo_id": None,
                                        "error": ""}
                try:
                    identity = resolve_identity(directory)
                except Exception as exc:
                    item["error"] = f"{type(exc).__name__}: {exc}"[:200]
                    out.append(item)
                    continue
                if identity is None:
                    item["error"] = "unresolvable: not a git repository"
                    out.append(item)
                    continue
                item["repo_uid"] = identity.repo_uid
                row = (session.query(orm.GitRepository)
                       .filter(orm.GitRepository.repo_uid == identity.repo_uid)
                       .one_or_none())
                if row is None and identity.toplevel:
                    row = (session.query(orm.GitRepository)
                           .filter(orm.GitRepository.path == identity.toplevel)
                           .one_or_none())
                if row is not None:
                    item.update({"indexed": True, "repo_id": row.id,
                                 "head_sha": row.head_sha, "branch": row.branch})
                out.append(item)
        return out
