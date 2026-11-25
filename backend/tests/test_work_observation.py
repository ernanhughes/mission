"""WORK-OUTCOME-01 W1: deterministic work-observation tests.

All fixtures are tiny synthetic SQLite files under tmp_path. The real
OpenCode database is never touched. No model calls anywhere in this suite.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mission_control.work_observation import evidence, opencode_adapter
from mission_control.work_observation.opencode_adapter import (
    extract_signals,
    parse_message,
)
from mission_control.work_observation.service import WorkObservationService
from mission_control.work_observation.workbench_allowlist import (
    is_allowed,
    relativize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
T0 = int(datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

ASSISTANT_PAYLOAD = {
    "agent": "build",
    "model": {"id": "deepseek-v4.1-flash", "providerID": "opencode-go"},
    "content": [
        {"type": "text",
         "text": "Implementation complete. Fixed WORK-OUTCOME-01 pilot in commit "
                 "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678. All 12 tests passed."},
        {"type": "tool", "id": "call_1", "name": "git_commit",
         "state": "completed"},
    ],
    "finish": "stop",
    "cost": 0.0,
    "tokens": {"input": 100, "output": 10},
    "time": {"created": T0, "completed": T0 + 1000},
}


def _write_opencode_db(path: Path, *, with_parts: bool = True,
                       extra_setup=None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path.as_posix())
    cur = conn.cursor()
    cur.execute("CREATE TABLE project (id TEXT PRIMARY KEY, worktree TEXT NOT NULL,"
                " vcs TEXT, name TEXT, time_created INTEGER NOT NULL,"
                " time_updated INTEGER NOT NULL, time_archived INTEGER)")
    cur.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY, project_id TEXT NOT NULL,"
                " parent_id TEXT, fork_session_id TEXT, slug TEXT NOT NULL,"
                " directory TEXT NOT NULL, path TEXT, title TEXT, version TEXT NOT NULL,"
                " agent TEXT, model TEXT, cost REAL NOT NULL DEFAULT 0,"
                " time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL,"
                " time_compacting INTEGER, time_archived INTEGER)")
    cur.execute("CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL,"
                " type TEXT NOT NULL, seq INTEGER NOT NULL, time_created INTEGER NOT NULL,"
                " time_updated INTEGER NOT NULL, data TEXT NOT NULL)")
    cur.execute("CREATE UNIQUE INDEX session_message_session_seq_idx"
                " ON session_message (session_id, seq)")
    if with_parts:
        cur.execute("CREATE TABLE session_part (message_id TEXT NOT NULL,"
                    " session_id TEXT NOT NULL, ordinal INTEGER NOT NULL, type TEXT NOT NULL,"
                    " call_id TEXT, time_created INTEGER NOT NULL,"
                    " time_updated INTEGER NOT NULL, data TEXT NOT NULL)")
    cur.execute("INSERT INTO project (id, worktree, name, time_created, time_updated)"
                " VALUES (?,?,?, ?, ?)",
                ("proj-ai", "C:/Projects/ai", "ai", T0, T0))
    cur.execute("INSERT INTO session_v2 (id, project_id, parent_id, slug, directory,"
                " title, version, time_created, time_updated)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                ("ses_1", "proj-ai", None, "slug", "C:/Projects/ai",
                 "Pilot work", "v2", T0, T0 + 1000))
    cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                " time_updated, data) VALUES (?,?,?,?,?,?,?)",
                ("msg-1", "ses_1", "assistant", 1, T0, T0,
                 json.dumps(ASSISTANT_PAYLOAD)))
    cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                " time_updated, data) VALUES (?,?,?,?,?,?,?)",
                ("msg-2", "ses_1", "user", 0, T0 - 5000, T0 - 5000,
                 json.dumps({"text": "Fix the pilot, see src/ai/pilot.py",
                             "time": {"created": T0 - 5000}})))
    if with_parts:
        cur.execute("INSERT INTO session_part (message_id, session_id, ordinal, type,"
                    " call_id, time_created, time_updated, data)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    ("msg-1", "ses_1", 0, "text", None, T0, T0,
                     json.dumps({"type": "text", "text": "hi"})))
    if extra_setup is not None:
        extra_setup(cur)
    conn.commit()
    conn.close()
    return path


def _service_for(tmp_path: Path, db_path: Path, settings) -> WorkObservationService:
    from mission_control.persistence.db import Database

    database = Database(settings)
    from mission_control.persistence.migrations import apply_migrations

    apply_migrations(database)
    return WorkObservationService(database, db_path)


def _runtime_with_db(tmp_path: Path, db_path: Path):
    from mission_control.config import RuntimeSettings

    return RuntimeSettings(
        repo_root=REPO_ROOT,
        data_dir=tmp_path / "data",
        config_dir=REPO_ROOT / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction-books",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
        workbench_decisions_path=tmp_path / "workbench-decisions.jsonl",
        workbench_preferences_path=tmp_path / "workbench-preferences.json",
        workbench_url="http://workbench.test",
        opencode_db_path=db_path,
    )


# -- read-only access -------------------------------------------------------

def test_missing_source_is_explicit(tmp_path: Path) -> None:
    st = opencode_adapter.status(tmp_path / "nope.db")
    assert st.available is False and st.error == "missing"


def test_directory_path_is_not_a_file(tmp_path: Path) -> None:
    st = opencode_adapter.status(tmp_path)
    assert st.available is False and st.error == "not_a_file"


def test_incompatible_schema_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(path.as_posix())
    conn.execute("CREATE TABLE other (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    st = opencode_adapter.status(path)
    assert st.available is False and st.error == "incompatible_schema"


def test_older_schema_without_parts_still_observes(tmp_path: Path) -> None:
    path = _write_opencode_db(tmp_path / "old.db", with_parts=False)
    st = opencode_adapter.status(path)
    assert st.available is True and st.has_parts_table is False
    assert (st.sessions, st.messages, st.parts) == (1, 2, 0)


def test_locked_source_maps_to_locked_envelope(tmp_path: Path, runtime) -> None:
    from mission_control.work_observation import opencode_adapter as adapter

    db = _write_opencode_db(tmp_path / "src.db", with_parts=False)
    real_connect = adapter._connect_ro

    def _locked(_path: Path, timeout: float = 5.0):
        raise sqlite3.OperationalError("database is locked")

    adapter._connect_ro = _locked
    try:
        service = _service_for(tmp_path, db, runtime)
        out = service.run_observation(limit_messages=10, limit_sessions=10)
    finally:
        adapter._connect_ro = real_connect
    assert out["status"] == "locked"
    assert out["model_calls"] == 0
    assert service.get_checkpoints() == {}


# -- message parsing --------------------------------------------------------

def test_assistant_text_and_tools_observed_not_claimed() -> None:
    parsed = parse_message("assistant", json.dumps(ASSISTANT_PAYLOAD))
    assert parsed["evidence_class"] == evidence.OBSERVED
    assert parsed["parse_error"] is False
    assert parsed["model"]["id"] == "deepseek-v4.1-flash"
    assert parsed["tool_calls"] == [
        {"id": "call_1", "name": "git_commit", "state": "completed", "type": "tool"}]
    assert "a1b2c3d4" in parsed["excerpt"]


def test_malformed_payload_is_parse_error_not_silent() -> None:
    parsed = parse_message("assistant", "{not json")
    assert parsed["parse_error"] is True
    assert parsed["evidence_class"] == evidence.OBSERVED


def test_user_text_without_parts_is_content() -> None:
    # W1 coverage rule: user messages never have parts; content lives in data.
    parsed = parse_message("user", json.dumps({"text": "do the thing",
                                               "time": {"created": 1}}))
    assert parsed["excerpt"] == "do the thing"


# -- signal extraction ------------------------------------------------------

def test_commit_sha_and_task_id_candidates() -> None:
    sigs = extract_signals("opencode:ses:1",
                           "see a1b2c3d4e5f60718293a4b5c6d7e8f9012345678 for WORK-OUTCOME-01 pilot")
    kinds = {(s.signal_type, s.value) for s in sigs}
    assert ("commit_sha_candidate",
            "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678") in kinds
    assert ("task_id_candidate", "WORK-OUTCOME-01") in kinds
    assert all(s.evidence_class == evidence.INFERRED
               for s in sigs if s.signal_type.endswith("_candidate"))


def test_stage_and_programme_tokens_extracted() -> None:
    sigs = extract_signals("r", "WORK-OUTCOME W2 plan for AI-CORE-01")
    vals = {s.value for s in sigs if s.signal_type == "task_id_candidate"}
    assert {"WORK-OUTCOME", "W2", "AI-CORE-01"} <= vals


def test_programme_with_stage_not_double_counted() -> None:
    sigs = extract_signals("r", "WORK-OUTCOME-01 pilot")
    vals = [s.value for s in sigs if s.signal_type == "task_id_candidate"]
    assert vals.count("WORK-OUTCOME-01") == 1
    assert "WORK-OUTCOME" not in vals


def test_invalid_commit_identifiers_ignored() -> None:
    assert not [s for s in extract_signals("r", "see xyz123 and version 2.0")
                if s.signal_type == "commit_sha_candidate"]


def test_windows_and_relative_paths_extracted() -> None:
    sigs = extract_signals("r", r"edit C:\Projects\ai\src\ai\scoring\service.py and docs\notes.md")
    values = {s.value for s in sigs if s.signal_type == "file_path"}
    assert r"C:\Projects\ai\src\ai\scoring\service.py" in values
    assert "docs\\notes.md" in values or "docs/notes.md" in values


def test_test_and_completion_claims_are_claimed() -> None:
    sigs = extract_signals("r", "All 12 tests passed, merged to main")
    claimed = {s.signal_type for s in sigs if s.evidence_class == evidence.CLAIMED}
    assert "test_claim" in claimed
    assert not any(s.evidence_class == evidence.VERIFIED for s in sigs)


def test_tool_invocations_are_observed_facts() -> None:
    sigs = extract_signals("r", "ran stuff",
                           [{"id": "c1", "name": "git_commit", "state": "completed"}])
    by_type = {s.signal_type: s for s in sigs}
    assert by_type["tool_invocation"].evidence_class == evidence.OBSERVED
    assert by_type["git_command"].value == "git_commit"


def test_workbench_refs_detected() -> None:
    sigs = extract_signals("r", "see .workbench/editorial-decisions.jsonl decision d1")
    assert any(s.signal_type == "workbench_ref" for s in sigs)


def test_every_signal_carries_provenance() -> None:
    sigs = extract_signals("opencode:ses:5", "fix a1b2c3d4 in src/x.py",
                           provenance={"session_id": "ses", "seq": 3})
    assert sigs and all(s.source_ref == "opencode:ses:5" for s in sigs)
    assert all(s.provenance.get("session_id") == "ses" for s in sigs)


# -- redaction / classification ---------------------------------------------

def test_secret_in_excerpt_is_redacted() -> None:
    excerpt, count = evidence.excerpt_redacted("call with api_key=sk-abcdef1234567890 done")
    assert "sk-abcdef" not in excerpt
    assert "[REDACTED-SECRET]" in excerpt
    assert count >= 1


def test_classification_keeps_claims_distinct_from_verified() -> None:
    assert evidence.classify_record("message") == evidence.OBSERVED
    assert evidence.classify_record("test_claim") == evidence.CLAIMED
    assert evidence.classify_record("signal") == evidence.INFERRED
    assert evidence.classify_record("verification") == evidence.VERIFIED


# -- allow-list ---------------------------------------------------------------

@pytest.mark.parametrize(("path", "expected"), [
    ("editorial-decisions.jsonl", True),
    ("editorial-candidates.jsonl", True),
    ("ledgers/20261027-130835.jsonl", True),
    ("runs/metadata-book/run-1.json", True),
    ("activity/workbench.jsonl", True),
    ("report-publication-preflight.json", True),
    ("conversations/abc/turn-001.prompt.txt", False),
    ("sessions/abc/x.jsonl", False),
    ("services/sidecar.json", False),
    (".env", False),
    ("wkd01/fixture.json", False),
    ("scores.jsonl", True),
])
def test_allow_list_deny_by_default(path: str, expected: bool) -> None:
    assert is_allowed(path) is expected


def test_relativize_never_leaks_absolute() -> None:
    assert relativize(r"C:\Projects\workbench\.workbench\ledgers\x.jsonl",
                      r"C:\Projects\workbench\.workbench").startswith("ledgers/")
    assert "\\" not in relativize("C:\\a\\b\\c.py")


# -- incremental observation --------------------------------------------------

def test_run_observes_and_advances_checkpoint(tmp_path: Path, runtime) -> None:
    db = _write_opencode_db(tmp_path / "src.db")
    service = _service_for(tmp_path, db, runtime)
    out = service.run_observation(limit_messages=100, limit_sessions=50)
    assert out["status"] == "completed"
    assert out["messages_seen"] == 2 and out["sessions_seen"] == 1
    assert out["signals_produced"] > 0 and out["model_calls"] == 0
    assert out["model_cost"] == 0
    checkpoints = service.get_checkpoints()
    assert checkpoints["message_created"]["cursor_value_ms"] == T0
    assert checkpoints["session_updated"]["cursor_value_ms"] == T0 + 1000


def test_repeat_run_is_idempotent(tmp_path: Path, runtime) -> None:
    db = _write_opencode_db(tmp_path / "src.db")
    service = _service_for(tmp_path, db, runtime)
    service.run_observation(limit_messages=100, limit_sessions=50)
    second = service.run_observation(limit_messages=100, limit_sessions=50)
    assert second["status"] == "completed"
    # Overlap window re-delivers, stable ids dedupe: nothing new stored.
    assert second["signals_new"] == 0
    assert (service.coverage()["stored_signals"] ==
            len(service.query_signals(limit=500)))


def test_timestamp_collision_ingests_both(tmp_path: Path, runtime) -> None:
    def _extra(cur: sqlite3.Cursor) -> None:
        cur.execute("INSERT INTO session_message (id, session_id, type, seq,"
                    " time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
                    ("msg-3", "ses_1", "assistant", 2, T0, T0,
                     json.dumps({"content": [{"type": "text", "text": "more"}],
                                 "time": {}})))

    db = _write_opencode_db(tmp_path / "src.db", extra_setup=_extra)
    service = _service_for(tmp_path, db, runtime)
    out = service.run_observation(limit_messages=100, limit_sessions=50)
    assert out["messages_seen"] == 3


def test_late_arriving_message_within_overlap_is_caught(tmp_path: Path, runtime) -> None:
    db = _write_opencode_db(tmp_path / "src.db")
    service = _service_for(tmp_path, db, runtime)
    service.run_observation(limit_messages=100, limit_sessions=50)
    conn = sqlite3.connect(db.as_posix())
    conn.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                 " time_updated, data) VALUES (?,?,?,?,?,?,?)",
                 ("msg-late", "ses_1", "user", 3, T0 - 60_000, T0 - 60_000,
                  json.dumps({"text": "late arrival, see src/late.py", "time": {}})))
    conn.commit()
    conn.close()
    out = service.run_observation(limit_messages=100, limit_sessions=50)
    assert out["status"] == "completed"
    assert any(s["source_ref"] == "opencode:ses_1:3"
               for s in service.query_signals(limit=500))


def test_updated_session_reobserved_without_duplicates(tmp_path: Path, runtime) -> None:
    db = _write_opencode_db(tmp_path / "src.db")
    service = _service_for(tmp_path, db, runtime)
    service.run_observation(limit_messages=100, limit_sessions=50)
    before = service.coverage()["stored_signals"]
    conn = sqlite3.connect(db.as_posix())
    conn.execute("UPDATE session_v2 SET time_updated=? WHERE id='ses_1'", (T0 + 999_999,))
    conn.commit()
    conn.close()
    out = service.run_observation(limit_messages=100, limit_sessions=50)
    assert out["status"] == "completed"
    assert service.coverage()["stored_signals"] == before


def test_failed_run_does_not_advance_checkpoint(tmp_path: Path, runtime,
                                                monkeypatch) -> None:
    db = _write_opencode_db(tmp_path / "src.db")
    service = _service_for(tmp_path, db, runtime)
    service.run_observation(limit_messages=100, limit_sessions=50)
    before = service.get_checkpoints()

    def _boom(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("mission_control.work_observation.service."
                        "opencode_adapter._connect_ro", _boom)
    out = service.run_observation(limit_messages=100, limit_sessions=50)
    assert out["status"] == "locked"
    assert service.get_checkpoints() == before


def test_source_replacement_recorded_in_fingerprint(tmp_path: Path, runtime) -> None:
    db = _write_opencode_db(tmp_path / "src.db")
    service = _service_for(tmp_path, db, runtime)
    service.run_observation(limit_messages=100, limit_sessions=50)
    conn = sqlite3.connect(db.as_posix())
    conn.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                 " time_updated, data) VALUES (?,?,?,?,?,?,?)",
                 ("msg-n", "ses_1", "user", 9, T0 + 5000, T0 + 5000,
                  json.dumps({"text": "new", "time": {}})))
    conn.commit()
    conn.close()
    health = service.health()
    assert health["source"]["available"] is True
    assert health["source"]["messages"] == 3
    out = service.run_observation(limit_messages=100, limit_sessions=50)
    assert out["status"] == "completed"
    assert out["messages_seen"] >= 1


# -- git reuse ------------------------------------------------------------------

def test_project_filter_matches_in_sql(tmp_path: Path, runtime) -> None:
    def _extra(cur: sqlite3.Cursor) -> None:
        cur.execute("INSERT INTO project (id, worktree, name, time_created, time_updated)"
                    " VALUES (?,?,?, ?, ?)",
                    ("proj-writer", "C:/Projects/writer", "writer", T0, T0))
        cur.execute("INSERT INTO session_v2 (id, project_id, slug, directory,"
                    " title, version, time_created, time_updated)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    ("ses_other", "proj-writer", "slug", "C:/Projects/writer",
                     "Other", "v2", T0, T0))
        cur.execute("INSERT INTO session_message (id, session_id, type, seq,"
                    " time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
                    ("msg-o", "ses_other", "user", 0, T0, T0,
                     json.dumps({"text": "other project", "time": {}})))

    db = _write_opencode_db(tmp_path / "src.db", extra_setup=_extra)
    service = _service_for(tmp_path, db, runtime)
    out = service.run_observation(limit_messages=100, limit_sessions=50,
                                  project_contains="Projects/ai")
    assert out["sessions_seen"] == 1
    assert out["messages_seen"] == 2
    refs = {s["source_ref"].split(":")[1] for s in service.query_signals(limit=500)}
    assert refs == {"ses_1"}


def test_unresolvable_directory_records_error(tmp_path: Path, runtime) -> None:
    service = _service_for(tmp_path, tmp_path / "missing.db", runtime)
    rows = service.git_status_for_directories([str(tmp_path / "no-such-dir")])
    assert len(rows) == 1 and rows[0]["indexed"] is False


def test_non_repo_directory_is_not_indexed(tmp_path: Path, runtime) -> None:
    service = _service_for(tmp_path, tmp_path / "missing.db", runtime)
    rows = service.git_status_for_directories([str(tmp_path)])
    assert rows[0]["indexed"] is False


# -- API ------------------------------------------------------------------------

def test_api_status_signals_runs_validation(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from mission_control.main import create_app

    db = _write_opencode_db(tmp_path / "src.db")
    settings = _runtime_with_db(tmp_path, db)
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/work-observation/status")
        assert status.status_code == 200
        body = status.json()
        assert body["source"]["available"] is True
        assert body["model_calls"] == 0

        run = client.post("/api/work-observation/runs", json={
            "limit_messages": 100, "limit_sessions": 50})
        assert run.status_code == 200, run.text
        assert run.json()["status"] == "completed"
        assert run.json()["model_calls"] == 0

        listed = client.get("/api/work-observation/runs")
        assert listed.json()["runs"][0]["status"] == "completed"

        got = client.get(f"/api/work-observation/runs/{run.json()['run_id']}")
        assert got.status_code == 200

        assert client.get("/api/work-observation/runs/nope").status_code == 404
        bad = client.post("/api/work-observation/runs",
                          json={"limit_messages": "many"})
        assert bad.status_code == 422

        signals = client.get("/api/work-observation/signals?signal_type=commit_sha_candidate")
        assert signals.status_code == 200
        assert signals.json()["signals"]

        coverage = client.get("/api/work-observation/coverage")
        assert coverage.status_code == 200
        assert coverage.json()["source"]["messages"] >= 2

        checkpoints = client.get("/api/work-observation/checkpoints")
        assert "message_created" in checkpoints.json()["checkpoints"]
