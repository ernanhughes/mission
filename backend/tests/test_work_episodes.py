"""WORK-OUTCOME-01 W2: deterministic reconstruction tests.

Engine tests use synthetic in-memory records. Service/API tests use tiny
synthetic SQLite fixtures (opencode DB under tmp_path + ORM git rows). The
real OpenCode database is never touched. No model calls anywhere.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from mission_control.work_observation.reconstruct import (
    check_cycle,
    classify_task_id,
    episode_id_for_task,
    reconstruct,
    CommitRec,
    EpisodeRec,
    SessionRec,
)

T0 = 1790000000000


def _sess(sid: str, parent: str | None = None, repo: str | None = "git-1",
          tasks: list[str] | None = None, shas: list[str] | None = None,
          files: list[str] | None = None, tools: list[str] | None = None,
          directory: str = "C:/Projects/ai") -> tuple[SessionRec, dict]:
    sigs: dict[str, list[str]] = {}
    if tasks:
        sigs["task_id_candidate"] = list(tasks)
    if shas:
        sigs["commit_sha_candidate"] = list(shas)
    if files:
        sigs["file_path"] = list(files)
    if tools:
        sigs["tool_invocation"] = list(tools)
    return (SessionRec(id=sid, parent_id=parent, directory=directory,
                       worktree="C:/Projects/ai", repo_uid=repo, title=sid,
                       first_ms=T0, last_ms=T0 + 1000),
            {sid: sigs})


def _commit(sha: str, repo: str | None = "git-1",
            files: list[str] | None = None) -> CommitRec:
    return CommitRec(repo_uid=repo, sha=sha, message="m", time_ms=T0 + 500,
                     files=list(files or []))


# -- task identifiers ---------------------------------------------------------

def test_shared_task_groups_sessions() -> None:
    s1, g1 = _sess("s1", tasks=["AI-CORE-01"])
    s2, g2 = _sess("s2", tasks=["AI-CORE-01"])
    g1.update(g2)
    res = reconstruct([s1, s2], g1, [])
    eps = [e for e in res.episodes if e.kind == "task"]
    assert len(eps) == 1 and sorted(eps[0].session_ids) == ["s1", "s2"]
    assert eps[0].id == episode_id_for_task("AI-CORE-01")


def test_one_session_two_objectives() -> None:
    s, g = _sess("s1", tasks=["AI-CORE-01", "AI-CORE-02"])
    res = reconstruct([s], g, [])
    kinds = sorted(e.id for e in res.episodes if e.kind == "task")
    assert kinds == [episode_id_for_task("AI-CORE-01"),
                     episode_id_for_task("AI-CORE-02")]
    refs = [a.target_ref for a in res.associations if a.assoc_type == "session"]
    assert refs.count("opencode:s1") == 2


def test_task_classification() -> None:
    assert classify_task_id("WORK-OUTCOME-01") == "task"
    assert classify_task_id("W1") == "stage"
    assert classify_task_id("AI-CORE-08C") == "task"
    assert classify_task_id("WORK-OUTCOME") == "programme"
    assert classify_task_id("TEST-123") == "artefact"
    assert classify_task_id("SES_ABC") == "artefact"


def test_fixture_task_ids_rejected() -> None:
    s, g = _sess("s1", tasks=["TEST-123", "SES_X"])
    res = reconstruct([s], g, [])
    assert [e for e in res.episodes if e.kind == "task"] == []
    assert any(a.method == "rejected" and a.reason == "task-id-artefact-or-fixture"
               for a in res.associations)


# -- commits --------------------------------------------------------------------

def test_explicit_commit_same_repo() -> None:
    sha = "a" * 40
    s, g = _sess("s1", shas=[sha])
    res = reconstruct([s], g, [_commit(sha)])
    links = [a for a in res.associations if a.assoc_type == "commit"]
    assert len(links) == 1
    assert links[0].method == "explicit" and links[0].confidence == "explicit"
    assert links[0].reason == "sha-resolved-same-repo"


def test_mentioned_but_unexecuted_commit_abstains() -> None:
    s, g = _sess("s1", shas=["b" * 40])
    res = reconstruct([s], g, [_commit("c" * 40)])
    assert [a for a in res.associations if a.assoc_type == "commit"] == []
    assert any(a.reason == "sha-unresolved-no-object" for a in res.associations)
    assert "s1" in res.unresolved_session_ids


def test_cross_repo_commit_is_candidate_not_explicit() -> None:
    sha = "d" * 40
    s, g = _sess("s1", repo="git-1", shas=[sha])
    res = reconstruct([s], g, [_commit(sha, repo="git-2")])
    links = [a for a in res.associations if a.assoc_type == "commit"]
    assert len(links) == 1
    assert links[0].method == "candidate" and links[0].confidence == "weak"
    assert links[0].reason == "sha-resolved-other-repo"


def test_ambiguous_abbreviated_sha_abstains() -> None:
    s, g = _sess("s1", tasks=["AI-CORE-01"], shas=["ab12cd"])
    c1 = _commit("ab12cd" + "0" * 34)
    c2 = _commit("ab12cd" + "f" * 34)
    res = reconstruct([s], g, [c1, c2])
    assert [a for a in res.associations if a.assoc_type == "commit"] == []
    assert any(a.reason == "ambiguous-abbreviated-sha" for a in res.associations)


def test_unique_abbreviated_sha_resolves() -> None:
    s, g = _sess("s1", tasks=["AI-CORE-01"], shas=["ab12cd"])
    res = reconstruct([s], g, [_commit("ab12cd" + "0" * 34)])
    links = [a for a in res.associations if a.assoc_type == "commit"]
    assert len(links) == 1 and links[0].method == "explicit"


# -- temporal + file overlap ----------------------------------------------------

def test_timestamp_only_never_links() -> None:
    s1, g1 = _sess("s1")
    s2 = SessionRec(id="s2", parent_id=None, directory="C:/Projects/ai",
                    worktree="C:/Projects/ai", repo_uid="git-1", title="s2",
                    first_ms=T0 + 10, last_ms=T0 + 20)
    g1["s2"] = {}
    res = reconstruct([s1, s2], g1, [])
    sess_links = [a for a in res.associations if a.assoc_type == "session"]
    assert sess_links and all("unresolved" in a.episode_id for a in sess_links)
    assert sorted(res.unresolved_session_ids) == ["s1", "s2"]


def test_common_file_alone_is_insufficient() -> None:
    s, g = _sess("s1", files=["README.md"])
    res = reconstruct([s], g, [_commit("e" * 40, files=["README.md"])])
    assert [a for a in res.associations if a.assoc_type == "commit"] == []
    assert "s1" in res.unresolved_session_ids


def test_distinctive_file_overlap_links_candidate() -> None:
    s, g = _sess("s1", files=["src/ai/scoring/service.py", "src/ai/scoring/rank.py"])
    c = _commit("f" * 40, files=["src/ai/scoring/service.py",
                                 "src/ai/scoring/rank.py", "README.md"])
    res = reconstruct([s], g, [c])
    links = [a for a in res.associations if a.assoc_type == "commit"]
    assert len(links) == 1 and links[0].method == "candidate"


def test_file_overlap_wrong_repo_ignored() -> None:
    s, g = _sess("s1", repo="git-1", files=["src/x.py"])
    res = reconstruct([s], g, [_commit("0" * 40, repo="git-2", files=["src/x.py"])])
    assert [a for a in res.associations if a.assoc_type == "commit"] == []


# -- review / hierarchy / non-code ----------------------------------------------

def test_review_session_links_review_of() -> None:
    s1, g1 = _sess("s1", tasks=["AI-CORE-01"])
    s2, g2 = _sess("s2", tasks=["AI-CORE-01"], tools=["cocoder_review"])
    g1.update(g2)
    res = reconstruct([s1, s2], g1, [])
    reviews = [a for a in res.associations if a.assoc_type == "review_of"]
    assert len(reviews) == 1 and reviews[0].target_ref == "opencode:s2"
    # Correction resolution is never inferred in W2.
    assert not any("resolv" in a.reason for a in res.associations)


def test_programme_stage_hierarchy() -> None:
    s, g = _sess("s1", tasks=["WORK-OUTCOME", "W1"])
    res = reconstruct([s], g, [])
    by_id = {e.id: e for e in res.episodes}
    child = by_id[episode_id_for_task("W1")]
    assert child.parent_id == episode_id_for_task("WORK-OUTCOME")
    assert by_id[episode_id_for_task("WORK-OUTCOME")].kind == "programme"
    assert child.kind == "stage"


def test_cycle_rejected() -> None:
    eps = {"a": EpisodeRec("a", "task", "A", "", parent_id="b"),
           "b": EpisodeRec("b", "task", "B", "", parent_id=None)}
    assert check_cycle(eps, "b", "a") is True
    assert check_cycle(eps, "b", "c") is False
    assert check_cycle(eps, "a", "a") is True


def test_research_without_commits_is_episode() -> None:
    s, g = _sess("s1", tasks=["AI-CORE-09"], files=["docs/research/plan.md"])
    res = reconstruct([s], g, [])
    eps = [e for e in res.episodes if e.kind == "task"]
    assert len(eps) == 1
    assert [a for a in res.associations if a.assoc_type == "commit"] == []


def test_uncommitted_files_form_cluster_without_commits() -> None:
    s, g = _sess("s1", files=["src/new_feature.py"])
    res = reconstruct([s], g, [])
    assert "s1" in res.unresolved_session_ids
    bucket = [e for e in res.episodes if e.kind == "unresolved"]
    assert len(bucket) == 1


def test_missing_evidence_stays_unresolved() -> None:
    s, g = _sess("s1")
    res = reconstruct([s], g, [])
    assert res.unresolved_session_ids == ["s1"]
    assert res.stats["abstained"] >= 0


def test_conflicting_signals_both_recorded() -> None:
    s, g = _sess("s1", tasks=["AI-CORE-01"], shas=["1" * 40], repo="git-1")
    res = reconstruct([s], g, [_commit("1" * 40, repo="git-2")])
    kinds = {a.assoc_type for a in res.associations if a.episode_id}
    assert "session" in kinds and "commit" in kinds  # no forced merge


def test_identity_stable_across_runs() -> None:
    s, g = _sess("s1", tasks=["AI-CORE-01"])
    r1 = reconstruct([s], dict(g), [])
    r2 = reconstruct([s], dict(g), [])
    assert [e.id for e in r1.episodes] == [e.id for e in r2.episodes]


def test_single_generic_file_never_moderate() -> None:
    # Review M3: one generic file + automatic temporal proximity → weak max.
    s, g = _sess("s1", files=["src/utils.py"])
    c = _commit("1" * 40, files=["src/utils.py"])
    res = reconstruct([s], g, [c])
    links = [a for a in res.associations if a.assoc_type == "commit"]
    assert len(links) == 1
    assert links[0].confidence == "weak"


def test_http_and_cve_shaped_ids_rejected() -> None:
    # Review M1: error codes and CVE ids are not work.
    for junk in ("HTTP-500", "CVE-2024-1234", "ERROR-404"):
        s, g = _sess("s1", tasks=[junk])
        res = reconstruct([s], g, [])
        assert [e for e in res.episodes if e.kind == "task"] == []
        assert any(a.reason == "task-id-artefact-or-fixture"
                   for a in res.associations)


def test_lone_task_mention_is_weak_candidate() -> None:
    # Review M1: a single uncorroborated mention seeds a candidate, not an
    # explicit episode membership.
    s, g = _sess("s1", tasks=["AI-CORE-99"])
    res = reconstruct([s], g, [])
    links = [a for a in res.associations
             if a.assoc_type == "session" and a.episode_id]
    assert len(links) == 1
    assert links[0].method == "candidate" and links[0].confidence == "weak"
    assert links[0].reason == "lone-task-mention"


def test_short_hex_without_corroboration_rejected() -> None:
    # Review M2: a bare 7-hex token (version number, colour) must not resolve
    # even on a coincidental unique-prefix match.
    s, g = _sess("s1", shas=["abcdef1"])
    res = reconstruct([s], g, [_commit("abcdef1" + "0" * 33)])
    assert [a for a in res.associations if a.assoc_type == "commit"] == []
    assert any(a.reason == "short-sha-uncorroborated" for a in res.associations)


def test_artefact_task_does_not_corroborate_short_sha() -> None:
    # Re-review minor 2: junk task ids must not unblock short-sha resolution.
    s, g = _sess("s1", tasks=["HTTP-500"], shas=["abcdef1"])
    res = reconstruct([s], g, [_commit("abcdef1" + "0" * 33)])
    assert [a for a in res.associations if a.assoc_type == "commit"] == []
    assert any(a.reason == "short-sha-uncorroborated" for a in res.associations)


def test_rejection_reasons_accumulate_not_collapse(tmp_path, runtime) -> None:
    # Re-review minor 1: two refusals on one association key keep both reasons.
    import types

    from mission_control import models as orm
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.work_observation.episodes import EpisodeService
    from mission_control.work_observation.reconstruct import (
        AssociationRec,
        EpisodeRec,
    )

    database = Database(runtime)
    apply_migrations(database)
    service = EpisodeService(database, tmp_path / "oc.db")
    bucket = EpisodeRec(id="ep:unresolved:p", kind="unresolved",
                        title="bucket", project_key="p",
                        session_ids=[], first_ms=0, last_ms=0)
    bucket.source_digest = "test"
    mk = lambda reason: AssociationRec(  # noqa: E731
        episode_id="ep:unresolved:p", assoc_type="signal",
        target_ref="opencode:s1", method="rejected", confidence="weak",
        reason=reason, signals=[])
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:unresolved:p", project_key="p",
                                  title="bucket", kind="unresolved"))
    left = types.SimpleNamespace(episodes=[bucket], associations=[mk("r-one")])
    assert service._persist("run1", "p", left, []) == 1
    right = types.SimpleNamespace(episodes=[bucket], associations=[mk("r-two")])
    assert service._persist("run2", "p", right, []) == 0
    with database.session() as session:
        rows = session.query(orm.WoEpisodeAssociation).all()
        assert len(rows) == 1
        assert "r-one" in rows[0].reason and "r-two" in rows[0].reason
    database.dispose()


def test_chain_and_task_coexist_with_links() -> None:
    s1, g1 = _sess("s1", tasks=["AI-CORE-01"])
    s2 = SessionRec(id="s2", parent_id="s1", directory="C:/Projects/ai",
                    worktree="C:/Projects/ai", repo_uid="git-1", title="s2",
                    first_ms=T0, last_ms=T0 + 1)
    g1["s2"] = dict(g1["s1"])
    res = reconstruct([s1, s2], g1, [])
    kinds = sorted({e.kind for e in res.episodes})
    assert "task" in kinds and "chain" in kinds


# -- service + persistence ------------------------------------------------------

DAY = "2026-11-22"
T1 = int(datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


def _write_oc_db(path, sessions) -> None:
    import pathlib

    path = pathlib.Path(path)
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
                " VALUES ('p1','C:/work/ai','ai',?,?)", (T1, T1))
    for sid, parent, directory, msgs in sessions:
        cur.execute("INSERT INTO session_v2 (id, project_id, parent_id, slug, directory,"
                    " title, version, time_created, time_updated)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (sid, "p1", parent, "s", directory, sid, "v2", T1, T1 + 1000))
        for seq, (mtype, payload) in enumerate(msgs):
            cur.execute("INSERT INTO session_message (id, session_id, type, seq,"
                        " time_created, time_updated, data) VALUES (?,?,?,?,?,?,?)",
                        (f"{sid}-{seq}", sid, mtype, seq, T1, T1, json.dumps(payload)))
    conn.commit()
    conn.close()


def _svc(tmp_path, oc_db, settings):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.work_observation.episodes import EpisodeService
    from mission_control.work_observation.service import WorkObservationService

    database = Database(settings)
    apply_migrations(database)
    # W1→W2 pipeline: observation populates wo_signals first (real code path).
    obs = WorkObservationService(database, oc_db)
    result = obs.run_observation(limit_messages=5000, limit_sessions=500)
    assert result["status"] == "completed", result
    assert result["signals_produced"] > 0, result
    return EpisodeService(database, oc_db), database


def _runtime_ep(tmp_path, oc_db):
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
        opencode_db_path=oc_db,
    )


def _seed_git(database, repo_path: str, commits: list[tuple[str, int]]) -> None:
    from mission_control import models as orm

    with database.session() as session:
        session.add(orm.GitRepository(id="gr1", path=repo_path, repo_uid="git-1"))
        session.flush()
        for sha, ts in commits:
            session.add(orm.GitCommit(repo_id="gr1", sha=sha, committer_ts=ts))


def _assistant_text(text: str, tools: list[str] | None = None) -> dict:
    content = [{"type": "text", "text": text}]
    for i, name in enumerate(tools or []):
        content.append({"type": "tool", "id": f"c{i}", "name": name,
                        "state": "completed"})
    return {"content": content, "model": {"id": "m"}, "time": {}}


SHA_A = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def test_service_task_episode_with_commit(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc, [
        ("s1", None, "C:/work/ai", [("assistant", _assistant_text(
            f"Doing AI-CORE-01 in {SHA_A}"))]),
        ("s2", None, "C:/work/ai", [("assistant", _assistant_text(
            "Continuing AI-CORE-01"))]),
    ])
    service, database = _svc(tmp_path, oc, runtime)
    _seed_git(database, "C:/work/ai", [(SHA_A, T1)])
    out = service.run_reconstruction(project_contains="work/ai", limit_sessions=50)
    assert out["status"] == "completed"
    assert out["model_calls"] == 0
    eps = service.list_episodes(project_key="work/ai")
    tasks = [e for e in eps if e["kind"] == "task"]
    assert len(tasks) == 1 and sorted(
        service.get_episode(tasks[0]["id"])["associations"],
        key=lambda a: a["target_ref"])
    got = service.get_episode(tasks[0]["id"])
    targets = {(a["assoc_type"], a["target_ref"], a["method"]) for a in got["associations"]}
    assert ("session", "opencode:s1", "explicit") in targets
    assert ("session", "opencode:s2", "explicit") in targets
    assert ("commit", f"git-1:{SHA_A}", "explicit") in targets


def test_service_idempotent_replay(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc, [("s1", None, "C:/work/ai",
                       [("assistant", _assistant_text("AI-CORE-02 work"))])])
    service, _ = _svc(tmp_path, oc, runtime)
    first = service.run_reconstruction(project_contains="work/ai")
    second = service.run_reconstruction(project_contains="work/ai")
    assert first["status"] == second["status"] == "completed"
    assert second["associations_made"] == 0
    eps = service.list_episodes(project_key="work/ai", kind="task")
    assert len(eps) == 1


def test_service_incremental_join(tmp_path, runtime) -> None:
    from mission_control.work_observation.service import WorkObservationService

    oc = tmp_path / "oc.db"
    _write_oc_db(oc, [("s1", None, "C:/work/ai",
                       [("assistant", _assistant_text("AI-CORE-03 start"))])])
    service, database = _svc(tmp_path, oc, runtime)
    service.run_reconstruction(project_contains="work/ai")
    conn = sqlite3.connect(oc.as_posix())
    conn.execute("INSERT INTO session_v2 (id, project_id, parent_id, slug, directory,"
                 " title, version, time_created, time_updated)"
                 " VALUES ('s9','p1',NULL,'s','C:/work/ai','s9','v2',?,?)",
                 (T1 + 5000, T1 + 6000))
    conn.execute("INSERT INTO session_message (id, session_id, type, seq, time_created,"
                 " time_updated, data) VALUES ('s9-0','s9','assistant',0,?,?,?)",
                 (T1 + 5000, T1 + 5000, json.dumps(_assistant_text("AI-CORE-03 more"))))
    conn.commit()
    conn.close()
    # New source rows need W1 observation before reconstruction can see them.
    obs = WorkObservationService(database, oc)
    assert obs.run_observation(limit_messages=5000)["status"] == "completed"
    out = service.run_reconstruction(project_contains="work/ai")
    assert out["status"] == "completed"
    eps = service.list_episodes(project_key="work/ai", kind="task")
    assert len(eps) == 1
    got = service.get_episode(eps[0]["id"])
    refs = {a["target_ref"] for a in got["associations"] if a["assoc_type"] == "session"}
    assert {"opencode:s1", "opencode:s9"} <= refs


def test_service_interrupted_run(tmp_path, runtime, monkeypatch) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc, [("s1", None, "C:/work/ai",
                       [("assistant", _assistant_text("AI-CORE-04"))])])
    service, _ = _svc(tmp_path, oc, runtime)

    def _boom(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("mission_control.work_observation.episodes."
                        "opencode_adapter._connect_ro", _boom)
    out = service.run_reconstruction(project_contains="work/ai")
    assert out["status"] == "locked"
    assert service.list_episodes(project_key="work/ai") == []


def test_service_hierarchy_and_supersession(tmp_path, runtime) -> None:
    oc = tmp_path / "oc.db"
    _write_oc_db(oc, [("s1", None, "C:/work/ai",
                       [("assistant", _assistant_text("WORK-OUTCOME and W2 plan"))])])
    service, _ = _svc(tmp_path, oc, runtime)
    service.run_reconstruction(project_contains="work/ai")
    eps = {e["id"]: e for e in service.list_episodes(project_key="work/ai")}
    child = eps.get("ep:task:W2")
    assert child is not None and child["parent_id"] == "ep:task:WORK-OUTCOME"


def test_api_episodes_validation(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from mission_control.main import create_app

    oc = tmp_path / "oc.db"
    _write_oc_db(oc, [("s1", None, "C:/work/ai",
                       [("assistant", _assistant_text("AI-CORE-05 work"))])])
    settings = _runtime_ep(tmp_path, oc)
    with TestClient(create_app(settings)) as client:
        obs = client.post("/api/work-observation/runs",
                          json={"limit_messages": 5000, "limit_sessions": 500})
        assert obs.status_code == 200 and obs.json()["status"] == "completed"
        run = client.post("/api/work-episodes/runs",
                          json={"project_contains": "work/ai", "limit_sessions": 50})
        assert run.status_code == 200, run.text
        assert run.json()["status"] == "completed"
        listed = client.get("/api/work-episodes?project_key=work/ai&limit=10&offset=0")
        assert listed.status_code == 200 and listed.json()["episodes"]
        eid = listed.json()["episodes"][0]["id"]
        assert client.get(f"/api/work-episodes/{eid}").status_code == 200
        assert client.get("/api/work-episodes/nope").status_code == 404
        assert client.post("/api/work-episodes/runs",
                           json={"limit_sessions": "many"}).status_code == 422
        assert client.get("/api/work-episodes/unresolved?project_key=work/ai"
                          ).status_code == 200
        assert client.get("/api/work-episodes/coverage").status_code == 200
