"""WORK-OUTCOME-01 W7: corrective proposal + confirmation tests.

Deterministic; no model calls. Authorization boundaries, version pinning,
duplicate prevention, evidence-bound closure rules.
"""


def _db(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    return database


def _dbs(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    return database


def _seed(tmp_path, runtime):
    from mission_control import models as orm

    database = _db(tmp_path, runtime)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:k", project_key="p", title="K",
                                  kind="task", status="established"))
        session.add(orm.WoFinding(
            id="fk1", episode_id="ep:k", kind="unsupported_claim",
            severity="minor", status="suspected",
            title="Unverified completion claim: merge to main and push",
            rationale="no sha", evidence_refs=[],
            next_action="supply merge SHA"))
        session.add(orm.WoRequirement(
            id="rqk", episode_id="ep:k", text="Keep the gate closed always",
            authority="accepted_proposal", mandatory=True, kind="functional",
            state="accepted", version=1, extractor="human-reviewed"))
    return database


def _svc(database):
    from mission_control.work_observation.proposals import ProposalService

    return ProposalService(database)


def test_create_proposal_derives_gap_first_action(tmp_path, runtime) -> None:
    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    out = svc.create_proposal(episode_id="ep:k", finding_ids=["fk1"])
    assert out["status"] == "completed"
    assert out["action_category"] == "RECOVER_EXISTING_EVIDENCE"
    got = svc.get_proposal(out["proposal_id"])
    assert got["status"] == "draft" and got["version"] == 1
    assert got["finding_ids"] == ["fk1"]
    database.dispose()


def test_create_rejects_cross_episode_and_duplicates(tmp_path, runtime) -> None:
    from mission_control import models as orm

    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:z", project_key="p", title="Z",
                                  kind="task", status="established"))
        session.add(orm.WoFinding(
            id="fz", episode_id="ep:z", kind="defect",
            severity="major", status="suspected", title="X",
            rationale="r", evidence_refs=[], next_action="n"))
    assert svc.create_proposal(
        episode_id="ep:k", finding_ids=["fk1", "fz"])["status"] == "rejected"
    first = svc.create_proposal(episode_id="ep:k", finding_ids=["fk1"])
    dup = svc.create_proposal(episode_id="ep:k", finding_ids=["fk1"])
    assert dup["status"] == "duplicate"
    assert dup["proposal_id"] == first["proposal_id"]
    database.dispose()


def test_approval_requires_human_and_confirm(tmp_path, runtime) -> None:
    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    pid = svc.create_proposal(
        episode_id="ep:k", finding_ids=["fk1"])["proposal_id"]
    assert svc.transition(pid, "ready_for_review")["status"] == "completed"
    assert svc.transition(pid, "approved")["status"] == "rejected"
    assert svc.transition(pid, "approved", confirm=True)["status"] == "rejected"
    out = svc.transition(pid, "approved", actor="reviewer",
                         reason="looks right", confirm=True)
    assert out == {"status": "completed", "proposal_id": pid,
                   "from": "ready_for_review", "to": "approved"}
    assert svc.transition(pid, "draft")["status"] == "rejected"
    database.dispose()


def test_scope_edit_bumps_version_and_voids_approval(tmp_path, runtime) -> None:
    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    pid = svc.create_proposal(
        episode_id="ep:k", finding_ids=["fk1"],
        scope="check the merge")["proposal_id"]
    svc.transition(pid, "ready_for_review")
    svc.transition(pid, "approved", actor="reviewer", reason="ok",
                   confirm=True)
    out = svc.edit_scope(pid, scope="check the merge and rewrite it")
    assert out["status"] == "completed" and out["version"] == 2
    got = svc.get_proposal(pid)
    assert got["status"] == "draft" and got["scope_hash"] != ""
    # old approval hash no longer matches: approval must be re-earned
    assert svc.transition(pid, "approved", actor="reviewer", reason="x",
                          confirm=True)["status"] == "rejected"
    database.dispose()


def test_assemble_commission_has_thirteen_sections(tmp_path, runtime) -> None:
    database = _seed(tmp_path, runtime)
    svc = _svc(database)
    pid = svc.create_proposal(
        episode_id="ep:k", finding_ids=["fk1"],
        objective="Recover the merge SHA")["proposal_id"]
    out = svc.assemble_commission(pid)
    assert out["status"] == "completed"
    assert len(out["sections"]) >= 13
    assert out["sections"][0].startswith("1. Original objective")
    assert any("Stop conditions" in s for s in out["sections"])
    assert svc.assemble_commission("wp:nope")["status"] == "unknown_proposal"
    database.dispose()


def test_confirmation_confirm_and_amend(tmp_path, runtime) -> None:
    from mission_control.work_observation.extract import ExtractionService

    database = _seed(tmp_path, runtime)
    svc = ExtractionService(database, tmp_path / "oc.db")
    assert svc.record_confirmation(
        requirement_id="rqk", decision="confirm",
        reviewer="")["status"] == "rejected"
    out = svc.record_confirmation(
        requirement_id="rqk", decision="confirm", reviewer="w7-human",
        rationale="R1 gate text matches")
    assert out["status"] == "completed"
    assert out["new_requirement_id"] is None
    amend = svc.record_confirmation(
        requirement_id="rqk", decision="amend", reviewer="w7-human",
        amended_text="Keep the gate closed always, including retries")
    assert amend["status"] == "completed"
    assert amend["new_requirement_id"]
    reqs = svc.list_requirements(episode_id="ep:k")
    assert sorted(r["version"] for r in reqs) == [1, 2]
    assert [r for r in reqs if r["version"] == 1][0]["state"] == "superseded"
    confs = svc.list_confirmations(requirement_id="rqk")
    assert [c["decision"] for c in confs] == ["amend", "confirm"]
    database.dispose()


def test_corrective_api_roundtrip(tmp_path, runtime, client) -> None:
    routes = client.get("/api/work-corrective/routes").json()
    assert routes["default"] == "manual"
    assert any(r["route"] == "manual" and r["available"]
               for r in routes["routes"])
    worker = [r for r in routes["routes"] if r["route"] == "worker"][0]
    assert worker["available"] is False
    # no proposals yet
    assert client.get("/api/work-corrective/proposals").json() == {
        "proposals": []}
    assert client.get("/api/work-corrective/proposals/wp:nope").status_code \
        == 404
    bad = client.post("/api/work-corrective/proposals", json={})
    assert bad.status_code == 422
    # confirmations validation
    assert client.post("/api/work-intent/confirmations", json={}).status_code \
        == 422
    assert client.get("/api/work-intent/confirmations").json() == {
        "confirmations": []}


def test_handoff_requires_approved_and_confirm(tmp_path, runtime) -> None:
    database = _dbs(tmp_path, runtime)
    svc = __import__("mission_control.work_observation.proposals",
                      fromlist=["ProposalService"]).ProposalService(database)
    from mission_control import models as orm

    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:h", project_key="p", title="H",
                                  kind="task", status="established"))
        session.add(orm.WoFinding(
            id="fh", episode_id="ep:h", kind="verification_gap",
            severity="minor", status="suspected", title="gap",
            rationale="r", evidence_refs=[], next_action="n"))
    pid = svc.create_proposal(
        episode_id="ep:h", finding_ids=["fh"])["proposal_id"]
    assert svc.record_handoff(pid, "manual")["status"] == "rejected"
    svc.transition(pid, "ready_for_review")
    svc.transition(pid, "approved", actor="w7-human", reason="ok",
                   confirm=True)
    assert svc.record_handoff(pid, "manual", actor="op")["status"] == "rejected"
    out = svc.record_handoff(pid, "manual", actor="op", confirm=True)
    assert out["status"] == "completed"
    assert svc.record_handoff(pid, "worker", confirm=True)["status"] == "rejected"
    assert svc.get_proposal(pid)["status"] == "queued"
    database.dispose()


def test_resolve_and_reopen_finding(tmp_path, runtime) -> None:
    from mission_control import models as orm
    from mission_control.work_observation.evaluate import EvaluationService

    database = _dbs(tmp_path, runtime)
    svc = EvaluationService(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:q", project_key="p", title="Q",
                                  kind="task", status="established"))
        session.add(orm.WoFinding(
            id="fq", episode_id="ep:q", kind="verification_gap",
            severity="minor", status="suspected",
            title="Merge corroborated, push unproven",
            rationale="no remote record", evidence_refs=[], next_action="x"))
    assert svc.resolve_finding("fq", closure_evidence="x",
                               actor="w7")["status"] == "rejected"
    assert svc.resolve_finding("fq", closure_evidence="origin/main contains sha",
                               actor="system")["status"] == "rejected"
    out = svc.resolve_finding(
        "fq",
        closure_evidence="origin/main of https://github.com/ernanhughes/ai.git contains de28820 (verified 2026-11-24)",
        actor="w7-human")
    assert out["status"] == "completed"
    assert svc.resolve_finding(
        "fq", closure_evidence="origin/main contains it",
        actor="w7-human")["status"] == "no_change"
    with database.session() as session:
        row = session.get(orm.WoFinding, "fq")
        assert row.status == "resolved" and "origin/main" in row.closure_evidence
    assert svc.reopen_finding("fq", reason="", actor="")["status"] == "rejected"
    out = svc.reopen_finding("fq", reason="remote rewound", actor="w7-human")
    assert out["status"] == "completed"
    with database.session() as session:
        row = session.get(orm.WoFinding, "fq")
        assert row.status == "suspected" and "reopened" in row.rationale
    database.dispose()


def test_action_taxonomy_never_defaults_to_code(tmp_path, runtime) -> None:
    from mission_control.work_observation.proposals import action_for_finding

    assert action_for_finding("verification_gap") == "RECOVER_EXISTING_EVIDENCE"
    assert action_for_finding("unsupported_claim") == "RECOVER_EXISTING_EVIDENCE"
    assert action_for_finding("missing_requirement") == \
        "RECOVER_OR_CONFIRM_REQUIREMENTS"
    assert action_for_finding("defect") == "INVESTIGATE_SUSPECTED_DEFECT"
    assert action_for_finding("verification_gap",
                              "missing_test_evidence") == "REPRODUCE_VERIFICATION"
    assert action_for_finding("verification_gap",
                              "unresolved_review") == "INDEPENDENT_REVIEW"
    assert action_for_finding("other") == "REQUEST_USER_DECISION"
