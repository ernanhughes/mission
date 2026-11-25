"""WORK-OUTCOME-01 W9E: project policy levels + capability gates.

Policies live in the existing settings key/value store; no new policy
infrastructure. Registration never enables anything; every gate fails
closed for unknown levels/capabilities.
"""


def _db(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    return database


def test_default_policy_is_manual_evaluation_for_ai() -> None:
    from mission_control.work_observation.policies import get_policy

    database = _db(*_tmp())
    with database.session() as session:
        doc = get_policy(session, "ai")
    assert doc["level"] == "manual_evaluation"
    assert doc["source"] == "default"
    database.dispose()


def test_unknown_project_is_disabled() -> None:
    from mission_control.work_observation.policies import get_policy

    database = _db(*_tmp())
    with database.session() as session:
        doc = get_policy(session, "some-other-repo")
    assert doc["level"] == "disabled"
    database.dispose()


def test_capability_ladder() -> None:
    from mission_control.work_observation.policies import allows

    assert allows("disabled", "observe") is False
    assert allows("observe", "observe") is True
    assert allows("observe", "reconstruct") is False
    assert allows("reconstruct", "reconstruct") is True
    assert allows("reconstruct", "evaluate_manual") is False
    assert allows("manual_evaluation", "evaluate_manual") is True
    assert allows("manual_evaluation", "evaluate_mechanical") is False
    assert allows("continuous_mechanical", "evaluate_mechanical") is True
    assert allows("continuous_mechanical", "evaluate_semantic") is False
    assert allows("continuous_semantic", "evaluate_semantic") is True
    assert allows("bogus", "observe") is False
    assert allows("observe", "bogus") is False


def test_set_policy_requires_human_and_roundtrips() -> None:
    from mission_control.work_observation.policies import get_policy, set_policy

    database = _db(*_tmp())
    with database.session() as session:
        assert set_policy(session, "ai", "observe")["status"] == "rejected"
        assert set_policy(session, "ai", "observe",
                          actor="system")["status"] == "rejected"
        assert set_policy(session, "ai", "nonsense",
                          actor="w9-human")["status"] == "rejected"
        out = set_policy(session, "ai", "continuous_mechanical",
                         lookback_days=14, actor="w9-human")
        assert out["status"] == "completed"
    with database.session() as session:
        doc = get_policy(session, "ai")
    assert doc["level"] == "continuous_mechanical"
    assert doc["lookback_days"] == 14
    assert doc["source"] == "explicit"
    database.dispose()


def test_policy_gates_continuous_pass(tmp_path, runtime) -> None:
    from mission_control.work_observation import continuous as cont
    from mission_control.work_observation.policies import PolicyService

    database = _db(tmp_path, runtime)
    policies = PolicyService(database)

    class Obs:
        called = False

        def run_observation(self, **kw):
            Obs.called = True
            return {"status": "completed"}

    class Ev:
        def eval_queue(self, limit=20):
            return []

        def persist_groups(self):
            return {"status": "completed"}

    with database.session() as session:
        from mission_control.work_observation.policies import set_policy

        set_policy(session, "blocked-repo", "disabled", actor="w9-human")

    Obs.called = False
    out = cont.run_pass(database, {"observation": Obs(),
                                   "evaluation": Ev(),
                                   "policies": policies},
                        project_contains="blocked-repo")
    assert Obs.called is False
    assert "observation:policy_disallows" in out["blocked"]

    Obs.called = False
    out = cont.run_pass(database, {"observation": Obs(),
                                   "evaluation": Ev(),
                                   "policies": policies},
                        project_contains="ai")
    assert Obs.called is True
    assert "observation:policy_disallows" not in out["blocked"]
    database.dispose()


def test_explicit_policy_changes_gate_outcome(tmp_path, runtime) -> None:
    """W9 review F7: prove an EXPLICIT policy drives the gate, not the
    default. Set the pilot to disabled → observation blocked; set an
    unknown project to observe → observation allowed."""
    from mission_control.work_observation import continuous as cont
    from mission_control.work_observation.policies import (
        PolicyService, set_policy)

    database = _db(tmp_path, runtime)
    policies = PolicyService(database)

    class Obs:
        def __init__(self):
            self.called = False

        def run_observation(self, **kw):
            self.called = True
            return {"status": "completed"}

    class Ev:
        def eval_queue(self, limit=20):
            return []

        def persist_groups(self):
            return {"status": "completed"}

    # baseline: default manual_evaluation allows observation
    obs = Obs()
    cont.run_pass(database, {"observation": obs, "evaluation": Ev(),
                             "policies": policies},
                  project_contains="ai")
    assert obs.called is True

    # explicit downgrade of the SAME project blocks observation
    with database.session() as session:
        set_policy(session, "ai", "disabled", actor="w9-human")
    obs = Obs()
    out = cont.run_pass(database, {"observation": obs, "evaluation": Ev(),
                                   "policies": policies},
                        project_contains="ai")
    assert obs.called is False
    assert "observation:policy_disallows" in out["blocked"]

    # explicit upgrade of an UNKNOWN project allows observation
    with database.session() as session:
        set_policy(session, "brand-new-repo", "observe", actor="w9-human")
    obs = Obs()
    out = cont.run_pass(database, {"observation": obs, "evaluation": Ev(),
                                   "policies": policies},
                        project_contains="brand-new-repo")
    assert obs.called is True
    assert "observation:policy_disallows" not in out["blocked"]

    # and the mechanical evaluation skip is recorded, not silent
    with database.session() as session:
        set_policy(session, "ai", "reconstruct", actor="w9-human")
    out = cont.run_pass(database, {"observation": Obs(), "evaluation": Ev(),
                                   "policies": policies},
                        project_contains="ai")
    assert "evaluate_mechanical:policy_disallows" in out["blocked"]
    database.dispose()


def test_semantic_never_allowed_without_policy_service(tmp_path, runtime) -> None:
    """W9 review F1: an omitted policy service must not grant semantic."""
    from mission_control.work_observation import continuous as cont

    database = _db(tmp_path, runtime)

    class Obs:
        def run_observation(self, **kw):
            return {"status": "completed"}

    class Ev:
        def __init__(self):
            self.semantic_flags = []

        def eval_queue(self, limit=20):
            return [{"episode_id": "ep1"}]

        def evaluate_episode(self, eid, semantic=True):
            self.semantic_flags.append(semantic)
            return {"status": "completed", "model_calls": 0}

        def persist_groups(self):
            return {"status": "completed"}

    ev = Ev()
    out = cont.run_pass(database, {"observation": Obs(), "evaluation": ev},
                        project_contains="ai", allow_semantic=True)
    assert ev.semantic_flags == [False]
    assert "semantic:policy_disallows" in out["blocked"]
    database.dispose()


def test_scope_canonicalisation_maps_path_spellings(tmp_path, runtime) -> None:
    """W9 review F10: 'work/ai' and 'Projects/ai' resolve to the ai policy."""
    from mission_control.work_observation.policies import (
        PolicyService, resolve_project_key)

    database = _db(tmp_path, runtime)
    with database.session() as session:
        assert resolve_project_key(session, "work/ai") == "ai"
        assert resolve_project_key(session, "Projects/ai") == "ai"
        assert resolve_project_key(session, "ai") == "ai"
        assert resolve_project_key(session, "unknown/repo") == "unknown/repo"
    gate = PolicyService(database).gate("work/ai", "observe")
    assert gate["allowed"] is True and gate["resolved_key"] == "ai"
    database.dispose()


def test_manual_endpoint_respects_policy(client, monkeypatch) -> None:
    """W9 review F3: a scoped manual run on a disabled project is refused."""
    from mission_control.work_observation.policies import PolicyService

    policies = PolicyService(client.app.state.database)
    out = policies.set("blocked-manual", "disabled", actor="w9-human")
    assert out["status"] == "completed"
    resp = client.post("/api/work-observation/runs",
                       json={"project_contains": "blocked-manual"})
    assert resp.status_code == 403
    payload = resp.json()
    message = (payload.get("detail") or payload.get("error", {}).get("message")
               or "")
    assert "policy does not permit" in message


def test_policy_api_roundtrip(client) -> None:
    body = client.get("/api/work-evaluation/policies").json()
    assert body["levels"][0] == "disabled"
    assert client.get("/api/work-evaluation/policies/project/ai"
                      ).json()["level"] == "manual_evaluation"
    assert client.post("/api/work-evaluation/policies",
                       json={"project_key": "ai", "level": "observe"}
                       ).status_code == 422
    gate = client.get(
        "/api/work-evaluation/policies/gate/observe?project_key=ai").json()
    assert gate["allowed"] is True
    g2 = client.get(
        "/api/work-evaluation/policies/gate/evaluate_semantic"
        "?project_key=ai").json()
    assert g2["allowed"] is False


def _tmp():
    import pathlib
    import tempfile
    from mission_control.config import RuntimeSettings

    tmp = pathlib.Path(tempfile.mkdtemp())
    rt = RuntimeSettings(
        repo_root=pathlib.Path("C:/Projects/mission"),
        data_dir=tmp / "data", config_dir=tmp,
        frontend_dist=tmp / "dist", book_root=tmp / "books",
        fiction_book_root=tmp / "fb", host="127.0.0.1", port=8799,
        start_monitor=False, seed_defaults=False,
        workbench_decisions_path=tmp / "d.jsonl",
        workbench_preferences_path=tmp / "p.json",
        workbench_url="http://w.test", opencode_db_path=tmp / "oc.db")
    return tmp, rt
