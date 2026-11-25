"""WORK-OUTCOME-01 W8: work envelope registration + linkage tests.

Deterministic; no model calls, no execution. Unknown refs rejected;
duplicate digests collapse; supersession preserves history.
"""


def _dbs(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    return database


def _seed(tmp_path, runtime):
    from mission_control import models as orm

    database = _dbs(tmp_path, runtime)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:w", project_key="p", title="W",
                                  kind="task", status="established"))
        session.add(orm.WoObjective(id="ob1", episode_id="ep:w",
                                    text="Do W", authority="explicit_user",
                                    status="current", version=1))
        session.add(orm.WoRequirement(
            id="rqw", episode_id="ep:w", objective_id="ob1",
            text="The gate stays closed during W", authority="explicit_user",
            mandatory=True, kind="functional", state="accepted",
            version=1, extractor="human-reviewed"))
        session.add(orm.GitRepository(id="gr1", repo_uid="git-1",
                                      path="C:/repo-one"))
    return database


def _svc(database):
    from mission_control.work_observation.envelopes import EnvelopeService

    return EnvelopeService(database)


def test_register_validates_refs_and_binds_authorization(tmp_path, runtime) -> None:
    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    assert svc.register_envelope(
        episode_id="ep:nope", objective_id="ob1",
        actor="w8-human",
        authorization_note="pilot")["status"] == "unknown_episode"
    assert svc.register_envelope(
        episode_id="ep:w", objective_id="obX",
        actor="w8-human",
        authorization_note="pilot")["status"] == "rejected"
    assert svc.register_envelope(
        episode_id="ep:w", objective_id="ob1",
        requirement_ids=["rq-nope"], actor="w8-human",
        authorization_note="pilot")["status"] == "rejected"
    assert svc.register_envelope(
        episode_id="ep:w", objective_id="ob1")["status"] == "rejected"
    assert svc.register_envelope(
        episode_id="ep:w", objective_id="ob1", actor="system",
        authorization_note="pilot")["status"] == "rejected"
    out = svc.register_envelope(
        episode_id="ep:w", objective_id="ob1", requirement_ids=["rqw"],
        repositories=["git-1"], scope="check the gate",
        acceptance_criteria="gate observed closed",
        originating_findings=[], actor="w8-human",
        authorization_note="W8E pilot charter")
    assert out["status"] == "completed"
    assert len(out["commission_digest"]) == 32
    assert out["requirement_versions"] == [{"id": "rqw", "v": 1}]
    dup = svc.register_envelope(
        episode_id="ep:w", objective_id="ob1", requirement_ids=["rqw"],
        repositories=["git-1"], scope="check the gate",
        acceptance_criteria="gate observed closed",
        actor="w8-human", authorization_note="W8E pilot charter")
    assert dup["status"] == "duplicate"
    database.dispose()


def test_reregister_supersedes_and_links_execution(tmp_path, runtime) -> None:
    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    assert svc.register_envelope(
        episode_id="ep:w", objective_id="ob1", requirement_ids=["rqw"],
        scope="v1 scope", acceptance_criteria="gate closed",
        actor="w8-human", authorization_note="pilot")["status"] == "completed"
    second = svc.register_envelope(
        episode_id="ep:w", objective_id="ob1", requirement_ids=["rqw"],
        scope="v2 scope", acceptance_criteria="gate closed",
        actor="w8-human", authorization_note="pilot")
    assert second["version"] == 2
    rows = svc.list_envelopes(episode_id="ep:w")
    assert sorted(r["status"] for r in rows) == ["active", "superseded"]
    assert svc.link_execution(envelope_id="we:nope")["status"] == \
        "unknown_envelope"
    assert svc.link_execution(
        envelope_id=second["envelope_id"],
        route="worker")["status"] == "rejected"
    # fabricated refs are rejected (W8 review F1): no backing rows here
    assert svc.link_execution(
        envelope_id=second["envelope_id"], route="manual",
        external_ref="pilot run", session_id="ses1",
        commit_sha="abc123",
        status="reported_complete")["status"] == "rejected"
    size = svc.envelope_size_bytes(second["envelope_id"])
    assert size["status"] == "completed"
    assert size["bytes"] < 4096
    assert size["carries_conversation"] is False
    database.dispose()


def test_link_execution_resolves_real_refs(tmp_path, runtime) -> None:
    from mission_control import models as orm

    database = _dbs(tmp_path, runtime)
    svc = _svc(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:l", project_key="p", title="L",
                                  kind="task", status="established"))
        session.add(orm.WoObjective(id="ob", episode_id="ep:l", text="Do L",
                                    authority="explicit_user",
                                    status="current", version=1))
        session.add(orm.WoRequirement(
            id="rql", episode_id="ep:l", objective_id="ob",
            text="Keep the gate closed", authority="explicit_user",
            mandatory=True, kind="functional", state="accepted",
            version=1, extractor="human-reviewed"))
        session.add(orm.WoEpisodeAssociation(
            id="as1", episode_id="ep:l", assoc_type="commit",
            target_ref="git-9:abc1234567890def1234567890abcdef12",
            method="explicit", confidence="explicit", reason="r",
            signals=[], recon_version=1, valid=1))
        session.add(orm.GitRepository(id="gr9", repo_uid="git-9",
                                      path="C:/nonexistent-repo-xyz"))
    # unknown repo rejected (F3)
    assert svc.register_envelope(
        episode_id="ep:l", objective_id="ob", requirement_ids=["rql"],
        repositories=["git-unknown"], actor="w8-human",
        authorization_note="pilot")["status"] == "rejected"
    env = svc.register_envelope(
        episode_id="ep:l", objective_id="ob", requirement_ids=["rql"],
        repositories=["git-9"], actor="w8-human",
        authorization_note="pilot")
    assert env["status"] == "completed"
    eid = env["envelope_id"]
    assert svc.link_execution(
        envelope_id=eid, test_receipt_ref="nope")["status"] == "rejected"
    assert svc.link_execution(
        envelope_id=eid, review_ref="nope")["status"] == "rejected"
    assert svc.link_execution(
        envelope_id=eid, status="whatever")["status"] == "rejected"
    assert svc.link_execution(
        envelope_id=eid, proposal_id="wp:nope")["status"] == "rejected"
    # linked-episode commit resolves without touching git
    out = svc.link_execution(
        envelope_id=eid, proposal_id="",
        commit_sha="abc1234567890def1234567890abcdef12",
        status="reported_complete")
    assert out["status"] == "completed"
    with database.session() as session:
        link = session.get(orm.WoExecutionLink, out["execution_id"])
        assert link.envelope_id == eid
        assert link.status == "reported_complete"
    database.dispose()


def test_json_string_columns_normalize_to_lists() -> None:
    from mission_control.work_observation.envelopes import _jl

    assert _jl(["a"]) == ["a"]
    assert _jl('["git-1", "git-2"]') == ["git-1", "git-2"]
    assert _jl("not json") == []
    assert _jl(None) == []
    assert _jl('{"a": 1}') == []


def test_link_execution_accepts_present_receipt_and_review(tmp_path, runtime) -> None:
    from mission_control import models as orm

    database = _dbs(tmp_path, runtime)
    svc = _svc(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:l", project_key="p", title="L",
                                  kind="task", status="established"))
        session.add(orm.WoObjective(id="ob", episode_id="ep:l", text="Do L",
                                    authority="explicit_user",
                                    status="current", version=1))
        session.add(orm.WoRequirement(
            id="rql", episode_id="ep:l", objective_id="ob",
            text="Keep the gate closed", authority="explicit_user",
            mandatory=True, kind="functional", state="accepted",
            version=1, extractor="human-reviewed"))
        session.add(orm.GitRepository(id="gr9", repo_uid="git-9",
                                      path="C:/nonexistent-repo-xyz"))
        session.add(orm.AitestReceipt(execution_id="exe-test-1",
                                      project_id="p", snapshot_id="s",
                                      status="FULL_PASS"))
        session.add(orm.GitReview(id="grv1", repo_id="gr9", commit_sha="abc123"))
    env = svc.register_envelope(
        episode_id="ep:l", objective_id="ob", requirement_ids=["rql"],
        repositories=["git-9"], actor="w8-human",
        authorization_note="pilot")
    assert env["status"] == "completed"
    eid = env["envelope_id"]
    out = svc.link_execution(
        envelope_id=eid, test_receipt_ref="exe-test-1", review_ref="grv1",
        status="reported_complete")
    assert out["status"] == "completed"
    with database.session() as session:
        link = session.get(orm.WoExecutionLink, out["execution_id"])
        assert link.envelope_id == eid
        assert link.test_receipt_ref == "exe-test-1"
    database.dispose()


def test_envelope_api_roundtrip(tmp_path, runtime, client) -> None:
    out = client.post("/api/work-envelopes", json={})
    assert out.status_code == 422
    assert client.get("/api/work-envelopes").json() == {"envelopes": []}
    assert client.get("/api/work-envelopes/we:nope/size").status_code == 404
