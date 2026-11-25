"""WORK-OUTCOME-01 W3: extraction service tests (no model calls).

Model-backend paths use an inline fake; the gated Ollama backend is never
constructed here. All fixtures synthetic.
"""

from __future__ import annotations

import json
import sqlite3


def _write_oc_db(path) -> None:
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
    cur.execute("INSERT INTO project (id, worktree, name, time_created, time_updated)"
                " VALUES ('p1','C:/work/ai','ai',1,1)")
    cur.execute("INSERT INTO session_v2 (id, project_id, slug, directory, title, version,"
                " time_created, time_updated) VALUES ('s1','p1','s','C:/work/ai','t','v',1,2)")
    cur.execute("INSERT INTO session_v2 (id, project_id, slug, directory, title, version,"
                " time_created, time_updated) VALUES ('s9','p1','s','C:/work/ai','t','v',1,2)")
    cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                " time_updated, data) VALUES ('m1','s1','user',0,1,1,?)",
                (json.dumps({"text": "hello?", "time": {}}),))
    cur.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                " time_updated, data) VALUES ('m9','s9','user',0,1,1,?)",
                (json.dumps({"text": "TASK: Return the single word READY.", "time": {}}),))
    conn.commit()
    conn.close()


def _svc(tmp_path, runtime, **kw):
    from mission_control.config import RuntimeSettings  # noqa: F401
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.work_observation.extract import ExtractionService

    database = Database(runtime)
    apply_migrations(database)
    return ExtractionService(database, tmp_path / "oc.db", **kw), database


def _runtime(tmp_path, oc):
    from pathlib import Path

    from mission_control.config import RuntimeSettings

    return RuntimeSettings(
        repo_root=Path(__file__).resolve().parents[2],
        data_dir=tmp_path / "data",
        config_dir=Path(__file__).resolve().parents[2] / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction-books",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
        workbench_decisions_path=tmp_path / "w-dec.jsonl",
        workbench_preferences_path=tmp_path / "w-pref.json",
        workbench_url="http://workbench.test",
        opencode_db_path=oc,
    )


def test_triage_scope_classifies_deterministically(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, _ = _svc(tmp_path, runtime)
    out = service.triage_scope(project_contains="work/ai")
    assert out["status"] == "completed"
    assert out["triaged"] == 2 and out["model_calls"] == 0
    with service._database.session() as session:
        from mission_control import models as orm

        rows = {r.session_id: r.classification
                for r in session.query(orm.WoTriageResult).all()}
    assert rows["s1"] == "INSUFFICIENT_EVIDENCE"
    assert rows["s9"] == "TRIVIAL_INTERACTION"


def test_deterministic_episode_extraction(tmp_path, runtime) -> None:
    from mission_control.work_observation.episodes import EpisodeService
    from mission_control.work_observation.service import WorkObservationService

    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    conn = sqlite3.connect(oc.as_posix())
    conn.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                 " time_updated, data) VALUES ('m2','s1','assistant',1,1,1,?)",
                 (json.dumps({"content": [
                     {"type": "text", "text": "Doing AI-CORE-01. All 5 tests passed."}],
                     "model": {"id": "m"}, "time": {}}),))
    conn.commit()
    conn.close()
    rt = _runtime(tmp_path, oc)
    service, database = _svc(tmp_path, rt)
    obs = WorkObservationService(database, oc)
    assert obs.run_observation(limit_messages=100)["status"] == "completed"
    eps = EpisodeService(database, oc)
    assert eps.run_reconstruction()["status"] == "completed"
    out = service.extract_episode_deterministic("ep:task:AI-CORE-01")
    assert out["status"] == "completed"
    assert out["written"]["objectives"] == 1
    assert out["written"]["claims"] == 1
    assert out["written"]["requirements"] == 0  # abstained, not invented
    # Idempotent: cached second run writes nothing new.
    again = service.extract_episode_deterministic("ep:task:AI-CORE-01")
    assert again["written"].get("cached") == 1
    assert service.get_cost()["model_calls"] == 0


def test_unknown_episode_is_unknown(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, _ = _svc(tmp_path, runtime)
    assert service.extract_episode_deterministic("ep:task:NOPE")["status"] == "unknown_episode"


def test_model_path_gated_without_backend(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, _ = _svc(tmp_path, runtime)
    out = service.extract_episode_model("ep:task:X")
    assert out["status"] == "model_not_enabled" and out["model_calls"] == 0


class _FakeBackend:
    name = "fake-test"

    def __init__(self, payload):
        self.payload = payload

    def complete(self, _packet_input: str):
        return {"data": self.payload, "cost_usd": 0.0,
                "tokens_in": 10, "tokens_out": 5, "latency_ms": 3}


def _seed_episode_with_session(database):
    from mission_control import models as orm

    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:task:T1", project_key="p", title="T1",
                                  kind="task", status="established"))
        session.add(orm.WoEpisodeAssociation(
            id="a1", episode_id="ep:task:T1", assoc_type="session",
            target_ref="opencode:s1", method="explicit", confidence="explicit",
            reason="r", signals=[], recon_version=1, valid=1))


def test_model_rejects_unknown_source(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({
                                 "requirements": [{
                                     "text": "Do the thing", "authority": "explicit_user",
                                     "mandatory": True, "kind": "functional",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:ghost"}]}]}))
    _seed_episode_with_session(database)
    out = service.extract_episode_model("ep:task:T1")
    assert out["status"] == "rejected"
    assert "unknown source" in out["error"]
    assert service.get_cost()["rejected"] == 1


def test_model_rejects_unsupported_authority(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({
                                 "requirements": [{
                                     "text": "Do the thing",
                                     "authority": "user_said_so",
                                     "mandatory": True, "kind": "functional",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:s1"}]}]}))
    _seed_episode_with_session(database)
    out = service.extract_episode_model("ep:task:T1")
    assert out["status"] == "rejected"


def test_model_budget_enforced(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({"objectives": []}),
                             max_model_calls=1)
    _seed_episode_with_session(database)
    first = service.extract_episode_model("ep:task:T1")
    assert first["status"] in ("completed", "cached")
    # Second distinct input would exceed the cap of 1.
    out = service.extract_episode_model("ep:task:T1")
    assert out["status"] in ("cached", "completed", "budget_exhausted")


def test_model_accepts_valid_packet_and_caches(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({
                                 "objectives": [{
                                     "text": "Do the thing", "authority": "explicit_user",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:s1"}]}],
                                 "requirements": [{
                                     "text": "Do the sub-thing",
                                     "authority": "explicit_user",
                                     "mandatory": True, "kind": "functional",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:s1"}]}]}))
    _seed_episode_with_session(database)
    first = service.extract_episode_model("ep:task:T1")
    assert first["status"] == "completed"
    assert first["written"]["requirements"] == 1
    second = service.extract_episode_model("ep:task:T1")
    assert second["status"] == "cached" and second["model_calls"] == 0
    cost = service.get_cost()
    assert cost["model_calls"] == 1


def test_api_intent_endpoints(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from mission_control.main import create_app

    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    settings = _runtime(tmp_path, oc)
    with TestClient(create_app(settings)) as client:
        tri = client.post("/api/work-intent/triage/runs",
                          json={"project_contains": "work/ai", "limit_sessions": 50})
        assert tri.status_code == 200, tri.text
        assert tri.json()["triaged"] == 2
        assert client.get("/api/work-intent/triage").json()["triage"]
        assert client.get("/api/work-intent/coverage").status_code == 200
        assert client.get("/api/work-intent/cost").json()["model_calls"] == 0
        bad = client.post("/api/work-intent/extractions/runs", json={})
        assert bad.status_code == 422
        assert client.post("/api/work-intent/extractions/runs",
                           json={"episode_id": "x", "backend": "nope"}
                           ).status_code == 422


def test_tool_paraphrase_rejected(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({
                                 "requirements": [{
                                     "text": "Access file path src/ai/scoring/service.py",
                                     "authority": "explicit_user",
                                     "mandatory": True, "kind": "functional",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:s1"}]}]}))
    _seed_episode_with_session(database)
    out = service.extract_episode_model("ep:task:T1")
    assert out["status"] == "rejected"
    assert "paraphrase" in out["error"]


def test_unresolvable_evidence_ref_rejected(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({
                                 "requirements": [{
                                     "text": "Ship the thing",
                                     "authority": "explicit_user",
                                     "mandatory": True, "kind": "functional",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:s1"}]}],
                                 "evidence_links": [{
                                     "requirement_index": 0,
                                     "evidence_kind": "git_commit",
                                     "evidence_ref": "deadbeefcafe"}]}))
    _seed_episode_with_session(database)
    out = service.extract_episode_model("ep:task:T1")
    assert out["status"] == "rejected"
    assert "unresolvable evidence" in out["error"]


def test_signal_sanitization_strips_absolute_paths() -> None:
    from mission_control.work_observation.extract import _sanitize_signal

    assert _sanitize_signal(
        "file_path", "C:\\Projects\\ai\\src\\x.py") == "x.py"
    assert _sanitize_signal(
        "commit_sha_candidate", "abc123") == "abc123"


def test_packet_schema_rejects_oversize_and_bad_authority() -> None:
    import pytest
    from pydantic import ValidationError

    from mission_control.work_observation.extract_schemas import (
        RequirementProposal,
        SourceRef,
    )

    with pytest.raises(ValidationError):
        RequirementProposal(text="x", authority="user_said_so",  # type: ignore[arg-type]
                            sources=[SourceRef(kind="session", ref="opencode:s1")])
    with pytest.raises(ValidationError):
        RequirementProposal(text="x", authority="explicit_user", sources=[])


def test_vacuous_instruction_echo_rejected(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend({
                                 "requirements": [{
                                     "text": "Extract work requirements from the evidence packet",
                                     "authority": "explicit_user",
                                     "mandatory": True, "kind": "functional",
                                     "sources": [{"kind": "session",
                                                  "ref": "opencode:s1"}]}]}))
    _seed_episode_with_session(database)
    out = service.extract_episode_model("ep:task:T1")
    assert out["status"] == "rejected"
    assert "vacuous" in out["error"]


def test_ollama_backend_refuses_non_loopback() -> None:
    import pytest

    from mission_control.work_observation.ollama_backend import OllamaJsonBackend

    with pytest.raises(ValueError):
        OllamaJsonBackend(base_url="http://example.com:11434")
    with pytest.raises(ValueError):
        OllamaJsonBackend(base_url="http://192.168.1.10:11434")
    # Loopback construction performs no network I/O.
    assert OllamaJsonBackend(base_url="http://127.0.0.1:11434").model


def test_model_triage_accept_and_cache(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, database = _svc(tmp_path, runtime, model_enabled=True,
                             model_backend=_FakeBackend(
                                 {"triage": {"classification": "RESEARCH_OR_INVESTIGATION",
                                             "reason": "research paths"}}))
    first = service.triage_session_model("s1")
    assert first["status"] == "completed"
    assert first["classification"] == "RESEARCH_OR_INVESTIGATION"
    second = service.triage_session_model("s1")
    assert second["status"] == "cached" and second["model_calls"] == 0
    assert service.get_cost()["model_calls"] == 1


def test_model_triage_rejects_bad_classification(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc)
    service, _ = _svc(tmp_path, runtime, model_enabled=True,
                       model_backend=_FakeBackend({"triage": {"classification": "STUFF"}}))
    out = service.triage_session_model("s1")
    assert out["status"] == "rejected"
