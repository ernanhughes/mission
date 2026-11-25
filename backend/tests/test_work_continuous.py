"""WORK-OUTCOME-01 W6: continuous assurance tests.

Requirement recovery provenance, finding aggregation + severity policy,
stale evaluation detection. Deterministic; no model calls.
"""

from mission_control.work_observation import grouping as gp
from mission_control.work_observation import req_sources as rs
from mission_control.work_observation import staleness as st


# -- req_sources -----------------------------------------------------------

def test_episode_key_from_title() -> None:
    assert rs._episode_key("ep:task:AI-CORE-08C", "Whatever") == "AI-CORE-08C"
    assert rs._episode_key("ep:x", "Achieve AI-CORE-05 now") == "AI-CORE-05"


def test_resolve_candidates_flags_review_sibling(tmp_path) -> None:
    d = tmp_path / "repo" / "docs" / "design"
    d.mkdir(parents=True)
    (d / "AI-CORE-08C-R1-CONTRACTS.md").write_text("# contracts", encoding="utf-8")
    (d / "AI-CORE-08C-R1-REVIEW.md").write_text("# review", encoding="utf-8")
    out = rs.resolve_candidates(tmp_path / "repo", "ep:task:AI-CORE-08C",
                                "Achieve AI-CORE-08C")
    assert len(out) == 2
    contracts = [c for c in out if "CONTRACTS" in c.path][0]
    assert contracts.has_review_sibling is True
    assert contracts.suggested_authority == "accepted_proposal-candidate"
    assert contracts.digest != ""


def test_resolve_candidates_unknown_without_match(tmp_path) -> None:
    d = tmp_path / "repo" / "docs" / "design"
    d.mkdir(parents=True)
    (d / "UNRELATED.md").write_text("x", encoding="utf-8")
    out = rs.resolve_candidates(tmp_path / "repo", "ep:task:AI-CORE-99",
                                "Achieve AI-CORE-99")
    assert out == []


# -- grouping ---------------------------------------------------------------

def _f(fid, kind="unsupported_claim", severity="major", title="t",
        status="suspected", ep="ep:1", proj="ai"):
    return {"id": fid, "episode_id": ep, "project_key": proj, "kind": kind,
            "severity": severity, "status": status, "title": title,
            "claim_text": ""}


def test_gap_classes() -> None:
    assert gp.gap_class_for("verification_gap",
                            "Unverified test report: 214 passed") == \
        "missing_test_evidence"
    assert gp.gap_class_for("unsupported_claim",
                            "Unsupported completion claim: merged") == \
        "missing_merge_provenance"
    assert gp.gap_class_for("unsupported_claim",
                            "Unsupported completion claim: pushing") == \
        "missing_push_proof"
    assert gp.gap_class_for("missing_requirement", "x") == "missing_requirement"


def test_identical_titles_group_distinct_wordings_split() -> None:
    a = _f("f1", title="Unsupported completion claim: merged into main and pushed")
    b = _f("f2", title="Unsupported completion claim: merged into main and pushed")
    c = _f("f3", title="Unsupported completion claim: 279 tests pass now")
    groups = gp.build_groups([a, b, c])
    assert len(groups) == 2
    big = [g for g in groups if g["member_count"] == 2][0]
    assert set(big["member_ids"]) == {"f1", "f2"}
    assert big["status"] == "open"
    assert big["severity"] == "major"
    assert big["sample_title"].startswith("Unsupported completion claim")


def test_group_severity_is_max_and_resolved_status() -> None:
    a = _f("f1", severity="minor", status="resolved", title="same t")
    b = _f("f2", severity="major", status="resolved", title="same t")
    groups = gp.build_groups([a, b])
    assert groups[0]["severity"] == "major"
    assert groups[0]["status"] == "resolved"


def test_reconcile_downgrades_uncontested_only(tmp_path, runtime) -> None:
    from mission_control import models as orm
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        session.add(orm.WoFinding(
            id="f-old", episode_id="ep:1", kind="unsupported_claim",
            severity="major", status="suspected",
            title="Unsupported completion claim: merged",
            rationale="commit assertion without resolvable reference",
            evidence_refs=[], next_action="x"))
        session.add(orm.WoFinding(
            id="f-contra", episode_id="ep:1", kind="unsupported_claim",
            severity="major", status="suspected",
            title="Unsupported completion claim: contradicted by tests",
            rationale="contradicted by execution record R",
            evidence_refs=[], next_action="x"))
    with database.session() as session:
        changed = gp.reconcile_severity_policy(session)
    assert [c["finding_id"] for c in changed] == ["f-old"]
    with database.session() as session:
        assert session.get(orm.WoFinding, "f-old").severity == "minor"
        assert session.get(orm.WoFinding, "f-contra").severity == "major"
        changed2 = gp.reconcile_severity_policy(session)
    assert changed2 == []
    database.dispose()


# -- staleness ---------------------------------------------------------------

def test_mark_stale_rejects_unknown_reason(tmp_path, runtime) -> None:
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        out = st.mark_stale(session, "ep:1", "whatever", "t")
    assert out["status"] == "rejected"
    database.dispose()


def test_stale_lifecycle_and_queue(tmp_path, runtime) -> None:
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        assert st.get_state(session, "ep:9")["queue_status"] == "unevaluated"
        st.mark_stale(session, "ep:9", "new_commit", "t1")
    with database.session() as session:
        s = st.get_state(session, "ep:9")
        assert (s["stale"], s["stale_reason"], s["queue_status"]) == \
            (1, "new_commit", "stale")
        st.refresh_after_eval(session, "ep:9", "a1", "t2")
    with database.session() as session:
        s = st.get_state(session, "ep:9")
        assert (s["stale"], s["queue_status"],
                s["last_assessment_id"]) == (0, "current", "a1")
        assert st.select_queue(session) == []
    database.dispose()


# -- manual requirement recovery -----------------------------------------------

def _extract_svc(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.work_observation.extract import ExtractionService

    database = Database(runtime)
    apply_migrations(database)
    return ExtractionService(database, tmp_path / "oc.db"), database


def test_manual_requirement_requires_provenance(tmp_path, runtime) -> None:
    from mission_control import models as orm

    svc, database = _extract_svc(tmp_path, runtime)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:r", project_key="p", title="R",
                                  kind="task", status="established"))
    assert svc.record_requirement_manual(
        episode_id="ep:r", text="The system shall score consistently.",
        authority="inferred", source_digest="d", authority_basis="b")[
        "status"] == "rejected"
    assert svc.record_requirement_manual(
        episode_id="ep:r", text="The system shall score consistently.",
        authority="explicit_user", source_digest="",
        authority_basis="")["status"] == "rejected"
    out = svc.record_requirement_manual(
        episode_id="ep:r", text="The system shall score consistently.",
        authority="explicit_user", source_kind="session_message",
        source_path="opencode:ses1:3", source_digest="abc123",
        authority_basis="first user message commissions scoring",
        reviewer="w6a")
    assert out["status"] == "completed"
    reqs = svc.list_requirements(episode_id="ep:r")
    assert len(reqs) == 1 and reqs[0]["authority"] == "explicit_user"
    assert reqs[0]["state"] == "accepted"
    srcs = svc.list_requirement_sources(episode_id="ep:r")
    assert len(srcs) == 1 and srcs[0]["digest"] == "abc123"
    database.dispose()


# -- continuous pass + auto flag -----------------------------------------------

def _dbs(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    return database


def test_run_pass_manual_deterministic_only(tmp_path, runtime) -> None:
    from mission_control.work_observation import continuous as cont

    database = _dbs(tmp_path, runtime)

    class Obs:
        def run_observation(self, **kw):
            assert kw.get("limit_sessions") == 500
            return {"status": "completed", "triaged": 3}

    class Eps:
        def run_reconstruction(self, **kw):
            return {"status": "completed"}

    class Ev:
        def __init__(self):
            self.calls = []

        def eval_queue(self, limit=20):
            return [{"episode_id": "ep:1", "queue_status": "stale"}]

        def evaluate_episode(self, eid, semantic=True):
            self.calls.append((eid, semantic))
            return {"status": "completed", "model_calls": 0}

        def persist_groups(self):
            return {"status": "completed", "groups": 0,
                    "groups_created": 0, "memberships_added": 0}

    ev = Ev()
    out = cont.run_pass(database, {"observation": Obs(), "episodes": Eps(),
                                   "evaluation": ev},
                        project_contains="ai")
    assert out["status"] == "completed"
    assert out["observed"] == {"status": "completed", "triaged": 3}
    assert out["evaluated"] == ["ep:1"]
    assert ev.calls == [("ep:1", False)]
    assert out["semantic_calls"] == 0
    database.dispose()


def test_run_pass_records_outages_without_raising(tmp_path, runtime) -> None:
    from mission_control.work_observation import continuous as cont

    database = _dbs(tmp_path, runtime)

    class Bad:
        def run_observation(self, **kw):
            raise RuntimeError("source down")

    out = cont.run_pass(database, {"observation": Bad()}, project_contains="ai")
    assert out["status"] == "completed"
    assert any("observation" in b for b in out["blocked"])
    database.dispose()


def test_auto_flag_defaults_off_and_toggles(tmp_path, runtime) -> None:
    from mission_control.work_observation.evaluate import EvaluationService

    database = _dbs(tmp_path, runtime)
    svc = EvaluationService(database)
    assert svc.get_auto()["auto_enabled"] is False
    assert svc.get_auto()["paid_budget_usd"] == 0.0
    svc.set_auto(True)
    assert svc.get_auto()["auto_enabled"] is True
    svc.set_auto(False)
    assert svc.get_auto()["auto_enabled"] is False
    database.dispose()


def test_explicit_user_objective_requires_session_source(tmp_path, runtime) -> None:
    svc, database = _extract_svc(tmp_path, runtime)
    from mission_control import models as orm

    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:v", project_key="p", title="V",
                                  kind="task", status="established"))
        session.add(orm.WoEpisodeAssociation(
            id="asv", episode_id="ep:v", assoc_type="session",
            target_ref="opencode:s1", method="explicit", confidence="explicit",
            reason="r", signals=[], recon_version=1, valid=1))
    packet = {"objectives": [{"text": "Achieve V", "authority": "explicit_user",
                              "sources": [{"kind": "episode",
                                           "ref": "ep:v"}]}],
              "requirements": [], "claims": [], "evidence_links": []}
    _, problems = svc._validate_model_output("ep:v", packet)
    assert any("without session source" in p for p in problems)
    packet["objectives"][0]["sources"] = [{"kind": "session",
                                           "ref": "opencode:s1"}]
    packet["objectives"][0]["text"] = "Do the real user ask from s1"
    _, problems = svc._validate_model_output("ep:v", packet)
    assert problems == []
    database.dispose()


def test_source_candidates_falls_back_to_project_repo(tmp_path, runtime) -> None:
    from mission_control import models as orm

    svc, database = _extract_svc(tmp_path, runtime)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:fb", project_key="Projects/ai",
                                  title="AI-CORE-99", kind="task",
                                  status="established"))
        session.add(orm.GitRepository(id="gr1", path=str(tmp_path / "ai")))
    (tmp_path / "ai" / "docs" / "design").mkdir(parents=True)
    (tmp_path / "ai" / "docs" / "design" / "AI-CORE-99-PLAN.md").write_text(
        "# plan", encoding="utf-8")
    out = svc.source_candidates("ep:fb")
    assert out["status"] == "completed"
    assert any("AI-CORE-99-PLAN.md" in c["path"] for c in out["candidates"])
    database.dispose()


def test_recon_persist_cross_scope_rerun_is_idempotent(tmp_path, runtime) -> None:
    """W6C regression: same episode ids under a different scope string must
    upsert, never bulk-INSERT into a PK collision."""
    from mission_control import models as orm
    from mission_control.work_observation.episodes import EpisodeService
    from mission_control.work_observation.reconstruct import (
        EpisodeRec, ReconResult)

    database = _dbs(tmp_path, runtime)
    svc = EpisodeService(database, tmp_path / "oc.db")
    with database.session() as session:
        session.add(orm.WoEpisode(
            id="ep:task:X", project_key="Projects/ai", title="X",
            kind="task", status="established", first_seen_ms=1,
            last_seen_ms=2, source_digest="d", version=1))
    res = ReconResult(episodes=[EpisodeRec(
        id="ep:task:X", kind="task", title="X", project_key="ai",
        status="established", first_ms=1, last_ms=2, source_digest="d")],
        associations=[])
    assert svc._persist("run1", "ai", res, []) == 0
    with database.session() as session:
        rows = session.query(orm.WoEpisode).filter(
            orm.WoEpisode.id == "ep:task:X").all()
        assert len(rows) == 1
        # second run under yet another scope: still one row
        assert svc._persist("run2", "other", res, []) == 0
        assert len(session.query(orm.WoEpisode).filter(
            orm.WoEpisode.id == "ep:task:X").all()) == 1
    database.dispose()


def test_safejson_normalizes_pg_text_to_containers() -> None:
    """W9A: TEXT-column DDL returns raw strings on PG; SafeJSON coerces."""
    from mission_control.models import SafeJSONDict, SafeJSONList

    lst, dct = SafeJSONList(), SafeJSONDict()
    assert lst.process_result_value('["a", "b"]', None) == ["a", "b"]
    assert lst.process_result_value(["a"], None) == ["a"]
    assert lst.process_result_value(None, None) == []
    assert lst.process_result_value("not json", None) == []
    assert lst.process_result_value('{"a": 1}', None) == []
    assert dct.process_result_value('{"a": 1}', None) == {"a": 1}
    assert dct.process_result_value(None, None) == {}
    import json as _json

    assert _json.loads(lst.process_bind_param(["x"], None)) == ["x"]
    assert _json.loads(dct.process_bind_param({"x": 1}, None)) == {"x": 1}


def test_reconcile_resolved_closes_satisfied_requirements(tmp_path, runtime) -> None:
    from mission_control import models as orm
    from mission_control.work_observation.evaluate import EvaluationService

    database = _dbs(tmp_path, runtime)
    svc = EvaluationService(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:z", project_key="p", title="Z",
                                  kind="task", status="established"))
        session.add(orm.WoRequirement(
            id="rqz", episode_id="ep:z", text="Keep the gate closed always",
            authority="explicit_user", mandatory=True, kind="functional",
            state="accepted", version=1, extractor="human-reviewed"))
        session.add(orm.WoFinding(
            id="fz", episode_id="ep:z", requirement_id="rqz",
            kind="missing_requirement", severity="major", status="suspected",
            title="Unverified requirement", rationale="r",
            evidence_refs=[], next_action="supply evidence"))
        session.add(orm.WoRequirementAssessment(
            id="az", episode_id="ep:z", requirement_id="rqz",
            verdict="satisfied_reported", rationale="linked",
            method="deterministic", evaluator="deterministic"))
    out = svc.reconcile_resolved()
    assert out["status"] == "rejected"
    out = svc.reconcile_resolved(actor="system", reason="x")
    assert out["status"] == "rejected"
    out = svc.reconcile_resolved(actor="w7-human",
                                 reason="intermediate run superseded by satisfied assessments")
    assert out["resolved"] == 1
    with database.session() as session:
        row = session.get(orm.WoFinding, "fz")
        assert row.status == "resolved"
        assert "satisfied_reported" in row.closure_evidence
    assert svc.reconcile_resolved(actor="w7-human", reason="recheck")["resolved"] == 0
    database.dispose()


def test_auto_link_stores_resolvable_refs(tmp_path, runtime) -> None:
    """W6A regression: mechanical SHA links must resolve in
    _evidence_for_requirements (full uid:sha refs), lifting the requirement
    to satisfied_reported instead of silent insufficient_evidence."""
    from mission_control import models as orm
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.work_observation.evaluate import EvaluationService

    database = Database(runtime)
    apply_migrations(database)
    svc = EvaluationService(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:l", project_key="p", title="L",
                                  kind="task", status="established"))
        session.add(orm.WoRequirement(
            id="rq1", episode_id="ep:l", text="Ship fix at abc1234567890",
            authority="explicit_user", mandatory=True, kind="functional",
            state="accepted", version=1, extractor="human-reviewed"))
        session.add(orm.WoEpisodeAssociation(
            id="as1", episode_id="ep:l", assoc_type="commit",
            target_ref="git-1:abc1234567890def1234567890abcdef12",
            method="explicit", confidence="explicit", reason="r",
            signals=[], recon_version=1, valid=1))
    out = svc.evaluate_episode("ep:l", semantic=False)
    assert out["status"] == "completed"
    with database.session() as session:
        links = session.query(orm.WoEvidenceLink).filter(
            orm.WoEvidenceLink.requirement_id == "rq1").all()
        assert links and all(":" in li.evidence_ref for li in links)
        verdicts = [r.verdict for r in session.query(
            orm.WoRequirementAssessment).filter(
            orm.WoRequirementAssessment.requirement_id == "rq1").all()]
    assert verdicts and all(v == "satisfied_reported" for v in verdicts)
    database.dispose()


def test_remote_ref_link_resolves_as_cited_not_verified(tmp_path, runtime) -> None:
    """W8D: remote containment citations resolve (reported), never verify."""
    from mission_control import models as orm
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations
    from mission_control.work_observation.evaluate import EvaluationService

    database = Database(runtime)
    apply_migrations(database)
    svc = EvaluationService(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:rr", project_key="p", title="R",
                                  kind="task", status="established"))
        session.add(orm.WoRequirement(
            id="rqr", episode_id="ep:rr",
            text="The fix is present on the remote ref", authority="explicit_user",
            mandatory=True, kind="functional", state="accepted", version=1,
            extractor="human-reviewed"))
        session.add(orm.WoEvidenceLink(
            id="lr", requirement_id="rqr", evidence_kind="remote_ref",
            evidence_ref="origin/main@https://example.invalid/repo.git contains abc",
            source_digest="human-attested:t", method="human-reviewed",
            confidence="moderate"))
    out = svc.evaluate_episode("ep:rr", semantic=False)
    assert out["status"] == "completed"
    with database.session() as session:
        verdicts = [r.verdict for r in session.query(
            orm.WoRequirementAssessment).filter(
            orm.WoRequirementAssessment.requirement_id == "rqr").all()]
    assert verdicts == ["satisfied_reported"]
    database.dispose()


def test_new_policy_marks_completion_claim_minor(tmp_path, runtime) -> None:
    from mission_control import models as orm
    from mission_control.work_observation.evaluate import EvaluationService
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    svc = EvaluationService(database)
    with database.session() as session:
        session.add(orm.WoEpisode(id="ep:n", project_key="p", title="N",
                                  kind="task", status="established"))
        session.add(orm.WoClaim(id="cn1", episode_id="ep:n", claimant="assistant",
                                text="merged into main and pushed",
                                scope="s", source_ref="opensis:s1:1"))
    out = svc.evaluate_episode("ep:n", semantic=False)
    assert out["status"] == "completed"
    with database.session() as session:
        rows = session.query(orm.WoFinding).filter(
            orm.WoFinding.episode_id == "ep:n").all()
        assert [(r.kind, r.severity) for r in rows] == [
            ("unsupported_claim", "minor")]
    database.dispose()
