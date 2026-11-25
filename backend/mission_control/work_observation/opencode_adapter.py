"""Read-only OpenCode observation adapter (WORK-OUTCOME-01 W1).

Primary content source is ``session_message.data`` (complete for all eras).
``session_part`` is a recent-only normalized supplement (populated only for
sessions active since ~2026-11-23; 0% coverage before) and must never be the
sole content basis — see W1-HISTORICAL-COVERAGE-REPORT.

Discipline (mirrors ``opencode_cost``): open ``file:...?mode=ro`` per batch,
close immediately, bounded queries, explicit unavailable envelopes
(``missing`` / ``not_a_file`` / ``incompatible_schema`` / ``locked``),
never silent zero, no writes, no model calls.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from mission_control.work_observation import evidence

_REQUIRED_TABLES = ("session_v2", "session_message", "project")
_OPTIONAL_TABLES = ("session_part",)

MAX_ROWS_PER_QUERY = 5000
PART_CHUNK = 500

_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
_TASK_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+-\d+[A-Z0-9]*)\b")
# Stage tokens (W1, W2) and bare programme names (WORK-OUTCOME) do not match
# the task pattern above. They are weak candidates by design: explicit
# programme roots only (W8 instrumentation replaces this heuristic).
_STAGE_RE = re.compile(r"\b(W\d{1,3})\b")
_PROGRAMME_RE = re.compile(r"\b(WORK-OUTCOME|MC-COST|MC-CULTIVATION)(?![-\d])")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]+")
_REL_PATH_RE = re.compile(
    r"(?<![\w/\\.])([\w\-.]+[\\/][\w\-.]+[\w\-.\\/]*\."
    r"(py|ts|tsx|js|jsx|md|sql|yaml|yml|toml|json|ps1|cmd|sh|rs|go|java|cs|css|html))\b"
)
_GIT_CMD_RE = re.compile(r"\bgit\s+[a-z][a-z\-]*")
_WORKBENCH_RE = re.compile(
    r"(\.workbench[\\/]?[\w\-.\\/]*|editorial-decisions[\w\-.]*|"
    r"workbench\.receipt[/\d.]*|candidate_sha256|content_sha256)"
)
_TEST_CLAIM_RE = re.compile(
    r"(\d+\s+(?:passed|failed|skipped|tests?\b)[^\n]{0,120})", re.IGNORECASE
)
_MERGE_CLAIM_RE = re.compile(
    r"(merged?\s+(?:to|into)\s+[^\n]{0,80}|implementation\s+complete[^\n]{0,80}|"
    r"all\s+tests?\s+passed[^\n]{0,80})",
    re.IGNORECASE,
)


@dataclass
class SourceStatus:
    available: bool
    source_path: str
    reason: str
    error: str | None = None
    sessions: int = 0
    messages: int = 0
    parts: int = 0
    has_parts_table: bool = False


def _connect_ro(db_path: Path, timeout: float = 5.0) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def _is_locked_error(exc: BaseException) -> bool:
    return "database is locked" in str(exc).casefold()


def status(db_path: Path) -> SourceStatus:
    """Schema compatibility check + aggregate inventory. Read-only."""
    posix = db_path.as_posix()
    if not db_path.exists():
        return SourceStatus(False, posix, "OpenCode database path does not exist",
                            error="missing")
    if not db_path.is_file():
        return SourceStatus(False, posix, "OpenCode database path is not a file",
                            error="not_a_file")
    try:
        conn = _connect_ro(db_path)
    except sqlite3.OperationalError as exc:
        if _is_locked_error(exc):
            return SourceStatus(False, posix, "OpenCode database is temporarily locked "
                                "(live WAL writer). Retry shortly.", error="locked")
        return SourceStatus(False, posix, f"Cannot open OpenCode database: {exc}"[:300],
                            error="open_failed")
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in _REQUIRED_TABLES if t not in tables]
        if missing:
            return SourceStatus(False, posix,
                                f"Incompatible OpenCode schema: missing tables: {missing}",
                                error="incompatible_schema")
        has_parts = "session_part" in tables
        sessions = conn.execute("SELECT COUNT(*) FROM session_v2").fetchone()[0]
        messages = conn.execute("SELECT COUNT(*) FROM session_message").fetchone()[0]
        parts = (conn.execute("SELECT COUNT(*) FROM session_part").fetchone()[0]
                 if has_parts else 0)
        return SourceStatus(True, posix, "ok", sessions=sessions,
                            messages=messages, parts=parts, has_parts_table=has_parts)
    except sqlite3.OperationalError as exc:
        if _is_locked_error(exc):
            return SourceStatus(False, posix, "OpenCode database is temporarily locked "
                                "(live WAL writer). Retry shortly.", error="locked")
        return SourceStatus(False, posix, f"OpenCode query failed: {exc}"[:300],
                            error="query_failed")
    finally:
        conn.close()


def _parse_data(data_text: Any) -> tuple[dict[str, Any] | None, bool]:
    if not isinstance(data_text, str) or not data_text:
        return None, True
    try:
        parsed = json.loads(data_text)
    except (ValueError, TypeError):
        return None, True
    if not isinstance(parsed, dict):
        return None, True
    return parsed, False


def parse_message(msg_type: str, data_text: Any) -> dict[str, Any]:
    """Normalize one message payload. Never raises; malformed → parse_error.

    Returns a small metadata dict (excerpt + digests), never the full body:
    ``{kind, excerpt, digest, model, cost, tokens, tool_calls, parse_error}``.
    """
    parsed, failed = _parse_data(data_text)
    if failed or parsed is None:
        raw = data_text if isinstance(data_text, str) else ""
        excerpt, _ = evidence.excerpt_redacted(raw[:2000])
        return {"kind": "message", "evidence_class": evidence.OBSERVED,
                "parse_error": True, "excerpt": excerpt,
                "digest": evidence.digest_text(raw[:4000])}
    out: dict[str, Any] = {"kind": "message", "evidence_class": evidence.OBSERVED,
                           "parse_error": False}
    out["digest"] = evidence.digest_text(
        data_text if isinstance(data_text, str) else json.dumps(parsed, sort_keys=True))
    if msg_type == "assistant":
        model = parsed.get("model") or {}
        out["model"] = {k: model.get(k) for k in ("id", "providerID", "variant")}
        out["cost"] = parsed.get("cost")
        out["tokens"] = parsed.get("tokens")
        blocks = parsed.get("content") or []
        texts: list[str] = []
        tools: list[dict[str, Any]] = []
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text" and isinstance(block.get("text"), str):
                    texts.append(block["text"])
                elif btype in {"tool", "tool_call", "tool_use"} or "name" in block:
                    tools.append({k: block.get(k) for k in
                                  ("id", "name", "state", "type")})
        out["tool_calls"] = tools
        joined = "\n".join(texts)
        out["excerpt"], out["redactions"] = evidence.excerpt_redacted(joined)
    elif msg_type == "user":
        text = parsed.get("text") if isinstance(parsed.get("text"), str) else ""
        out["excerpt"], out["redactions"] = evidence.excerpt_redacted(text)
        files = parsed.get("files")
        out["attached_files"] = files if isinstance(files, list) else []
    else:
        text = ""
        for key in ("text", "description", "summary", "reason"):
            if isinstance(parsed.get(key), str):
                text = parsed[key]
                break
        out["excerpt"], out["redactions"] = evidence.excerpt_redacted(text)
    return out


@dataclass
class Signal:
    """A candidate association signal. W1 extracts only; W2 assigns confidence."""
    signal_type: str
    value: str
    value_digest: str
    source_ref: str
    evidence_class: str = evidence.INFERRED
    provenance: dict[str, Any] = field(default_factory=dict)


def _clean_path(value: str) -> str:
    return value.rstrip(".,;:!?)]}'\"").strip()


def extract_signals(source_ref: str, text: str | None,
                    tool_calls: Iterable[dict[str, Any]] | None = None,
                    directory: str | None = None,
                    provenance: dict[str, Any] | None = None) -> list[Signal]:
    """Deterministic candidate-signal extraction. No promotion to relationships."""
    base = dict(provenance or {})
    if directory:
        base["directory"] = directory
    signals: list[Signal] = []
    tools = list(tool_calls or [])
    haystack = text or ""
    for match in _SHA_RE.finditer(haystack):
        value = match.group(0)
        if len(set(value)) < 4:
            continue
        signals.append(Signal("commit_sha_candidate", value,
                              evidence.digest_text(value), source_ref,
                              provenance={**base, "pattern": "hex7_40"}))
    for match in _TASK_ID_RE.finditer(haystack):
        value = match.group(1)
        signals.append(Signal("task_id_candidate", value,
                              evidence.digest_text(value), source_ref,
                              provenance={**base, "pattern": "programme_id"}))
    for match in _STAGE_RE.finditer(haystack):
        value = match.group(1)
        signals.append(Signal("task_id_candidate", value,
                              evidence.digest_text(value), source_ref,
                              provenance={**base, "pattern": "stage_token"}))
    for match in _PROGRAMME_RE.finditer(haystack):
        value = match.group(1)
        signals.append(Signal("task_id_candidate", value,
                              evidence.digest_text(value), source_ref,
                              provenance={**base, "pattern": "programme_name"}))
    for match in _WIN_PATH_RE.finditer(haystack):
        value = _clean_path(match.group(0))
        signals.append(Signal("file_path", value, evidence.digest_text(value),
                              source_ref,
                              provenance={**base, "pattern": "windows_path"}))
    for match in _REL_PATH_RE.finditer(haystack):
        value = _clean_path(match.group(1))
        signals.append(Signal("file_path", value, evidence.digest_text(value),
                              source_ref,
                              provenance={**base, "pattern": "repo_relative"}))
    for match in _GIT_CMD_RE.finditer(haystack):
        value = match.group(0)
        signals.append(Signal("git_command", value, evidence.digest_text(value),
                              source_ref, provenance={**base, "pattern": "git_cmd"}))
    for tool in tools:
        name = str(tool.get("name") or "")
        if not name:
            continue
        signals.append(Signal("tool_invocation", name,
                              evidence.digest_text(name), source_ref,
                              evidence_class=evidence.OBSERVED,
                              provenance={**base, "tool_id": tool.get("id"),
                                          "tool_state": tool.get("state")}))
        if "git" in name.lower():
            signals.append(Signal("git_command", name,
                                  evidence.digest_text(name), source_ref,
                                  provenance={**base, "pattern": "tool_name_git"}))
    for match in _WORKBENCH_RE.finditer(haystack):
        value = match.group(1)[:200]
        signals.append(Signal("workbench_ref", value,
                              evidence.digest_text(value), source_ref,
                              provenance={**base, "pattern": "workbench"}))
    if haystack:
        for match in _TEST_CLAIM_RE.finditer(haystack):
            value = match.group(1).strip()[:200]
            excerpt, _ = evidence.excerpt_redacted(value)
            signals.append(Signal("test_claim", excerpt,
                                  evidence.digest_text(value), source_ref,
                                  evidence_class=evidence.CLAIMED,
                                  provenance={**base, "pattern": "test_claim"}))
        for match in _MERGE_CLAIM_RE.finditer(haystack):
            value = match.group(1).strip()[:200]
            excerpt, _ = evidence.excerpt_redacted(value)
            signals.append(Signal("completion_claim", excerpt,
                                  evidence.digest_text(value), source_ref,
                                  evidence_class=evidence.CLAIMED,
                                  provenance={**base, "pattern": "completion_claim"}))
    return signals


def fetch_sessions_updated_since(conn: sqlite3.Connection, since_ms: int,
                                 limit: int = MAX_ROWS_PER_QUERY,
                                 offset: int = 0) -> list[sqlite3.Row]:
    """Sessions ordered by (time_updated, id) — stable resume key. Bounded."""
    return conn.execute(
        "SELECT id, project_id, parent_id, fork_session_id, slug, directory, path,"
        " title, version, agent, model, cost, time_created, time_updated,"
        " time_compacting, time_archived"
        " FROM session_v2 WHERE time_updated > ?"
        " ORDER BY time_updated ASC, id ASC LIMIT ? OFFSET ?",
        (since_ms, limit, offset)).fetchall()


def fetch_messages_created_since(conn: sqlite3.Connection, since_ms: int,
                                 limit: int = MAX_ROWS_PER_QUERY,
                                 offset: int = 0,
                                 types: Iterable[str] | None = None) -> list[sqlite3.Row]:
    """Messages ordered by (time_created, id). Optional type filter. Bounded."""
    if types:
        placeholders = ",".join("?" for _ in types)
        return conn.execute(
            f"SELECT id, session_id, type, seq, time_created, time_updated, data"
            f" FROM session_message WHERE time_created > ? AND type IN ({placeholders})"
            f" ORDER BY time_created ASC, id ASC LIMIT ? OFFSET ?",
            (since_ms, *list(types), limit, offset)).fetchall()
    return conn.execute(
        "SELECT id, session_id, type, seq, time_created, time_updated, data"
        " FROM session_message WHERE time_created > ?"
        " ORDER BY time_created ASC, id ASC LIMIT ? OFFSET ?",
        (since_ms, limit, offset)).fetchall()


def count_parts_for_messages(conn: sqlite3.Connection,
                             message_ids: list[str]) -> int:
    """Coverage count of parts for explicit message ids. Content is never
    read here — session_message.data is the content source (review M6)."""
    total = 0
    for i in range(0, len(message_ids), PART_CHUNK):
        chunk = message_ids[i:i + PART_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        row = conn.execute(
            f"SELECT COUNT(*) FROM session_part WHERE message_id IN ({placeholders})",
            chunk).fetchone()
        total += int(row[0]) if row else 0
    return total


def fetch_parts_for_messages(conn: sqlite3.Connection,
                             message_ids: list[str]) -> list[sqlite3.Row]:
    """Parts for explicit message ids, chunked. Empty list → []."""
    out: list[sqlite3.Row] = []
    for i in range(0, len(message_ids), PART_CHUNK):
        chunk = message_ids[i:i + PART_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        out.extend(conn.execute(
            f"SELECT message_id, session_id, ordinal, type, call_id,"
            f" time_created, time_updated, data"
            f" FROM session_part WHERE message_id IN ({placeholders})"
            f" ORDER BY message_id ASC, ordinal ASC", chunk).fetchall())
    return out


def fetch_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, worktree, vcs, name, time_created, time_updated, time_archived"
        " FROM project ORDER BY id ASC").fetchall()


def _like_escape(needle: str) -> str:
    return needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def fetch_sessions_matching(conn: sqlite3.Connection, needle: str, since_ms: int,
                            limit: int = MAX_ROWS_PER_QUERY) -> list[sqlite3.Row]:
    """Sessions whose directory, worktree or project name matches (SQL-side).

    The unfiltered global scan cannot serve project-scoped pilots: the first N
    global rows may contain zero pilot sessions. Filtering in SQL keeps the
    (time_updated, id) resume key intact within the filtered set.
    """
    like = f"%{_like_escape(needle)}%"
    return conn.execute(
        "SELECT s.id, s.project_id, s.parent_id, s.fork_session_id, s.slug,"
        " s.directory, s.path, s.title, s.version, s.agent, s.model, s.cost,"
        " s.time_created, s.time_updated, s.time_compacting, s.time_archived"
        " FROM session_v2 AS s LEFT JOIN project AS p ON p.id = s.project_id"
        " WHERE s.time_updated > ? AND (s.directory LIKE ? ESCAPE '\\'"
        " OR p.worktree LIKE ? ESCAPE '\\' OR p.name LIKE ? ESCAPE '\\')"
        " ORDER BY s.time_updated ASC, s.id ASC LIMIT ?",
        (since_ms, like, like, like, limit)).fetchall()


def fetch_messages_for_sessions(conn: sqlite3.Connection, session_ids: list[str],
                                since_ms: int,
                                limit: int = MAX_ROWS_PER_QUERY) -> list[sqlite3.Row]:
    """Messages for explicit sessions ordered by (time_created, id)."""
    if not session_ids:
        return []
    out: list[sqlite3.Row] = []
    remaining = limit
    for i in range(0, len(session_ids), PART_CHUNK):
        if remaining <= 0:
            break
        chunk = session_ids[i:i + PART_CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        out.extend(conn.execute(
            f"SELECT id, session_id, type, seq, time_created, time_updated, data"
            f" FROM session_message WHERE session_id IN ({placeholders})"
            f" AND time_created > ? ORDER BY time_created ASC, id ASC LIMIT ?",
            (*chunk, since_ms, remaining)).fetchall())
        remaining = limit - len(out)
    return out


def message_type_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {r["type"]: r["c"] for r in conn.execute(
        "SELECT type, COUNT(*) AS c FROM session_message GROUP BY type")}
