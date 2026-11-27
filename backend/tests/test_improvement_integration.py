from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mission_control.api import improvement
from mission_control.improvement.stephanie_cli import StephanieCli
from mission_control.work_observation.proposals import scope_hash_of


def _snapshot():
    return {
        "episode_id": "episode-sc4-1", "project_key": "worker",
        "episode_title": "Worker output handling", "finding_id": "finding-sc4-1",
        "finding_title": "Empty output state needs classification", "finding_kind": "defect",
        "finding_severity": "moderate", "finding_status": "open",
        "finding_rationale": "The recorded observation lacks a source-backed outcome classification.",
        "evidence_refs": ["worker:source:sha256:abc"], "next_action": "Inspect the result state mapping.",
    }


@pytest.mark.long
def test_mission_invokes_real_stephanie_cli_with_isolated_root_and_idempotency(tmp_path):
    stephanie_root = Path("C:/Projects/stephanie")
    cli = StephanieCli(stephanie_root=stephanie_root,
                       python=stephanie_root / "venv/Scripts/python.exe",
                       run_root=tmp_path / "stephanie-sc4-isolated")
    assert cli.available

    first = cli.investigate(_snapshot())
    second = cli.investigate(_snapshot())
    other_source = {**_snapshot(), "finding_id": "finding-sc4-2", "finding_title": "A separate isolated observation"}
    third = cli.investigate(other_source)

    assert first["investigation_id"] == second["investigation_id"]
    assert first["source_identity"] == "mission:episode/episode-sc4-1/finding/finding-sc4-1"
    assert first["result"] == "REQUEST_ADDITIONAL_EVIDENCE"
    assert first["candidate"] is None
    assert first["authority"] == "investigation_only; no experiment or execution authority"
    assert third["investigation_id"] != first["investigation_id"]
    assert len(cli.list_investigations()) == 2
    assert cli.investigation_root(first["investigation_id"]) != cli.investigation_root(third["investigation_id"])
    assert not (tmp_path / "stephanie-sc4-isolated" / "worker-results.json").exists()


def test_mission_investigation_requires_approved_scope_and_exact_finding(monkeypatch, tmp_path):
    snapshot = _snapshot()
    proposal = {"id": "wp:approved", "status": "approved", "action_category": "REQUEST_USER_DECISION",
                "episode_id": snapshot["episode_id"], "finding_ids": [snapshot["finding_id"]],
                "scope": "Evidence review and hypothesis proposal only.",
                "exclusions": "No experiment execution.", "acceptance_criteria": "Return source-linked findings.",
                "version": 1}
    proposal["scope_hash"] = scope_hash_of(proposal["action_category"], proposal["scope"],
        proposal["exclusions"], proposal["acceptance_criteria"], proposal["version"])

    class Proposals:
        def get_proposal(self, _proposal_id):
            return proposal

    class Evaluation:
        def list_findings(self, *, episode_id, limit):
            assert episode_id == snapshot["episode_id"] and limit == 500
            return [{"id": snapshot["finding_id"], "status": "open", "title": snapshot["finding_title"],
                     "kind": "defect", "severity": "moderate", "rationale": snapshot["finding_rationale"],
                     "evidence_refs": snapshot["evidence_refs"], "next_action": snapshot["next_action"]}]

    class Episodes:
        def list_episodes(self, *, limit):
            assert limit == 200
            return [{"id": snapshot["episode_id"], "project_key": snapshot["project_key"],
                     "title": snapshot["episode_title"]}]

    class Cli:
        available = True
        def investigate(self, value):
            assert value["finding_id"] == snapshot["finding_id"]
            return {"investigation_id": "mission-" + "1" * 24, "source_digest": improvement._digest(value)}

    monkeypatch.setattr(improvement, "StephanieCli", Cli)
    app = FastAPI()
    app.state.proposal_service = Proposals()
    app.state.evaluation_service = Evaluation()
    app.state.episode_service = Episodes()
    app.include_router(improvement.router)
    client = TestClient(app)

    response = client.post("/api/improvement/investigations", json={
        "proposal_id": proposal["id"], "episode_id": snapshot["episode_id"], "finding_id": snapshot["finding_id"]})
    assert response.status_code == 200
    assert response.json()["investigation"]["source_digest"] == response.json()["source_snapshot_digest"]

    rejected = client.post("/api/improvement/investigations", json={
        "proposal_id": proposal["id"], "episode_id": snapshot["episode_id"], "finding_id": "different-finding"})
    assert rejected.status_code == 409

    proposal["scope"] = "A changed approved scope"
    stale = client.post("/api/improvement/investigations", json={
        "proposal_id": proposal["id"], "episode_id": snapshot["episode_id"], "finding_id": snapshot["finding_id"]})
    assert stale.status_code == 409


def test_cli_adapter_has_no_implicit_writable_run_root(monkeypatch):
    monkeypatch.delenv("MISSION_CONTROL_STEPHANIE_RUN_ROOT", raising=False)
    assert StephanieCli().available is False


def test_uncertain_investigation_claim_is_never_retried(tmp_path, monkeypatch):
    stephanie_root = Path("C:/Projects/stephanie")
    run_root = tmp_path / "unknown-state"
    cli = StephanieCli(stephanie_root=stephanie_root,
                       python=stephanie_root / "venv/Scripts/python.exe",
                       run_root=run_root)
    source = _snapshot()
    source_id = f"mission:episode/{source['episode_id']}/finding/{source['finding_id']}"
    import json
    import hashlib
    source_digest = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    investigation_id = "mission-" + hashlib.sha256(json.dumps({"source_identity": source_id,
        "source_digest": source_digest}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:24]
    claim_dir = run_root / "claims"
    claim_dir.mkdir(parents=True)
    (claim_dir / f"{investigation_id}.json").write_text('{"status":"dispatch_may_have_started"}', encoding="utf-8")

    def forbidden_dispatch(*_args, **_kwargs):
        raise AssertionError("unknown investigations must not be retried")

    monkeypatch.setattr("mission_control.improvement.stephanie_cli.subprocess.run", forbidden_dispatch)
    with pytest.raises(RuntimeError, match="UNKNOWN"):
        cli.investigate(source)


def test_experiment_dispatch_checks_frozen_digests_and_claims_once(tmp_path, monkeypatch):
    import hashlib
    import json
    from types import SimpleNamespace
    from mission_control.improvement.stephanie_cli import _digest

    stephanie_root = Path("C:/Projects/stephanie")
    run_root = tmp_path / "dispatch-root"
    cli = StephanieCli(stephanie_root=stephanie_root,
                       python=stephanie_root / "venv/Scripts/python.exe",
                       run_root=run_root)
    investigation_id = "mission-" + "a" * 24
    root = cli.investigation_root(investigation_id)
    root.mkdir(parents=True)
    candidate = {"candidate_id": "candidate-sc4", "strategy": "adaptive.v1"}
    candidate_digest = _digest(candidate)
    protocol_body = {"experiment_id": "experiment-sc4", "candidate_digest": candidate_digest,
                     "resource_limits": {"requests": 8}}
    protocol = {**protocol_body, "protocol_digest": _digest(protocol_body)}
    (root / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
    (root / "frozen-protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        root_arg = Path(command[command.index("--root") + 1])
        ledger = root_arg / "worker" / "worker-execution-ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text('{"fixture":"execution"}\n', encoding="utf-8")
        artifact = {"experiment_id": "experiment-sc4", "candidate_id": "candidate-sc4",
                    "protocol_digest": protocol["protocol_digest"], "actual_model_invocations": 0,
                    "worker_ledger_sha256": hashlib.sha256(ledger.read_bytes()).hexdigest()}
        artifact_path = root_arg / "integrated-results.json"
        encoded = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        artifact_path.write_text(encoded, encoding="utf-8")
        internal_claim = {"status": "completed", "experiment_id": "experiment-sc4",
                          "protocol_digest": protocol["protocol_digest"],
                          "integrated_results_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest()}
        (root_arg / "sc3-run.claim").write_text(json.dumps(internal_claim), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"status": "complete", "experiment_id": "experiment-sc4"}), stderr="")

    monkeypatch.setattr("mission_control.improvement.stephanie_cli.subprocess.run", fake_run)
    with pytest.raises(ValueError, match="identity no longer matches"):
        cli.dispatch_experiment(investigation_id, candidate_id=candidate["candidate_id"],
            candidate_digest="0" * 64, experiment_id=protocol["experiment_id"],
            protocol_digest=protocol["protocol_digest"])
    with pytest.raises(ValueError, match="identity no longer matches"):
        cli.dispatch_experiment(investigation_id, candidate_id=candidate["candidate_id"],
            candidate_digest=candidate_digest, experiment_id=protocol["experiment_id"],
            protocol_digest="f" * 64)
    response = cli.dispatch_experiment(investigation_id, candidate_id=candidate["candidate_id"],
        candidate_digest=candidate_digest, experiment_id=protocol["experiment_id"],
        protocol_digest=protocol["protocol_digest"])
    assert response["status"] == "complete"
    assert calls[0][0][-1] == "sc3-run"
    assert calls[0][1]["shell"] is False
    assert json.loads((run_root / "dispatch-claims" / "experiment-sc4.json").read_text())["status"] == "completed"
    reconciled = cli.dispatch_experiment(investigation_id, candidate_id=candidate["candidate_id"],
        candidate_digest=candidate_digest, experiment_id=protocol["experiment_id"],
        protocol_digest=protocol["protocol_digest"])
    assert reconciled["reconciled"] is True
    assert len(calls) == 1
    ledger = root / "worker" / "worker-execution-ledger.jsonl"
    saved_ledger = ledger.read_bytes()
    ledger.write_text('{"tampered":true}\n', encoding="utf-8")
    assert cli.experiment_result(investigation_id) is None
    assert cli.experiment_state(investigation_id)["status"] == "unknown"
    ledger.write_bytes(saved_ledger)


@pytest.mark.long
def test_sc4_isolated_mission_to_stephanie_worker_praxis_and_retrieval(client, monkeypatch, tmp_path):
    """Explicit acceptance run: actual Mission, Stephanie, Worker and Praxis code, isolated storage."""
    import json
    import hashlib
    from mission_control import models as orm
    from mission_control.improvement.stephanie_cli import StephanieCli

    run_root = tmp_path / "isolated-sc4-runtime"
    monkeypatch.setenv("MISSION_CONTROL_STEPHANIE_RUN_ROOT", str(run_root))
    monkeypatch.delenv("MISSION_CONTROL_STEPHANIE_PYTHON", raising=False)
    worker_root = Path("C:/Projects/worker")
    source_names = ["src/core/worker.ts", "src/server/server.ts", "src/executors/model.ts",
                    "src/strategies/catalog.ts", "src/strategies/runtime.ts",
                    "src/core/execution-ledger.ts", "src/core/execution-summary.ts"]
    source_files = {name: hashlib.sha256((worker_root / name).read_bytes()).hexdigest() for name in source_names}
    worker_digest = hashlib.sha256(json.dumps(source_files, sort_keys=True).encode()).hexdigest()
    worker_evidence = "worker-strategy-source-" + worker_digest[:12]
    with client.app.state.database.session() as session:
        session.add(orm.WoEpisode(id="ep:sc4-e2e", project_key="worker",
            title="Worker JSON normalization qualification", kind="task", status="established"))
        session.add(orm.WoObjective(id="ob:sc4-e2e", episode_id="ep:sc4-e2e",
            text="Qualify one isolated JSON normalization fixture", authority="explicit_user",
            status="current", version=1))
        for finding_id, title in (("finding:sc4-e2e", "Worker JSON fence normalization needs qualification"),
                                  ("finding:sc4-retrieval", "Worker JSON normalization follow-up")):
            session.add(orm.WoFinding(id=finding_id, episode_id="ep:sc4-e2e",
                kind="worker_json_fence_normalization", severity="moderate", status="open",
                title=title, rationale="A source-bound structured-output case requires a deterministic fixture comparison.",
                evidence_refs=[worker_evidence], next_action="Compare frozen baseline and candidate."))

    def approve_investigation(finding_id: str) -> dict:
        created = client.post("/api/work-corrective/proposals", json={
            "episode_id": "ep:sc4-e2e", "finding_ids": [finding_id],
            "action_category": "REQUEST_USER_DECISION", "objective": "Investigate this source-bound observation",
            "scope": "Bounded deterministic investigation", "exclusions": "No production change or execution",
            "acceptance_criteria": "Source-linked investigation response", "required_verification": "Verify the source identity",
        })
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]
        ready = client.post(f"/api/work-corrective/proposals/{proposal_id}/transition", json={"to_status": "ready_for_review"})
        assert ready.status_code == 200, ready.text
        approved = client.post(f"/api/work-corrective/proposals/{proposal_id}/transition", json={"to_status": "approved", "actor": "isolated-acceptance-owner", "confirm": True})
        assert approved.status_code == 200, approved.text
        return {"proposal_id": proposal_id}

    first_approval = approve_investigation("finding:sc4-e2e")
    investigation_response = client.post("/api/improvement/investigations", json={
        **first_approval, "episode_id": "ep:sc4-e2e", "finding_id": "finding:sc4-e2e"})
    assert investigation_response.status_code == 200, investigation_response.text
    investigation = investigation_response.json()["investigation"]
    assert investigation["candidate"] is not None
    assert investigation["proposed_experiments"]
    experiment = investigation["proposed_experiments"][0]
    assert not (run_root / "worker-results.json").exists()

    authorization = client.post("/api/improvement/experiment-authorizations", json={
        "investigation_id": investigation["investigation_id"], "objective_id": "ob:sc4-e2e"})
    assert authorization.status_code == 200, authorization.text
    auth_id = authorization.json()["proposal_id"]
    no_approval = client.post("/api/improvement/experiments/dispatch", json={
        "proposal_id": auth_id, "envelope_id": "not-yet-authorized",
        "investigation_id": investigation["investigation_id"]})
    assert no_approval.status_code == 409
    for status, extra in (("ready_for_review", {}), ("approved", {"actor": "isolated-acceptance-owner", "confirm": True})):
        transition = client.post(f"/api/work-corrective/proposals/{auth_id}/transition", json={"to_status": status, **extra})
        assert transition.status_code == 200, transition.text
    handoff = client.post(f"/api/work-corrective/proposals/{auth_id}/handoff", json={
        "route": "manual", "actor": "isolated-acceptance-owner", "confirm": True,
        "external_ref": "SC4B bounded fixture dispatch"})
    assert handoff.status_code == 200, handoff.text
    proposal = client.get(f"/api/work-corrective/proposals/{auth_id}").json()["proposal"]
    assert proposal["status"] == "queued"  # approved manual handoff remains dispatchable
    envelope_response = client.post("/api/work-envelopes", json={
        "episode_id": "ep:sc4-e2e", "objective_id": "ob:sc4-e2e",
        "originating_findings": ["finding:sc4-e2e"], "scope": proposal["scope"],
        "acceptance_criteria": proposal["acceptance_criteria"],
        "authorization_proposal_id": auth_id, "programme_id": "STEPHANIE-CONVERGENCE-04", "stage_id": "SC4B"})
    assert envelope_response.status_code == 200, envelope_response.text
    envelope_id = envelope_response.json()["envelope_id"]
    mismatched = client.post("/api/improvement/experiments/dispatch", json={
        "proposal_id": auth_id, "envelope_id": envelope_id,
        "investigation_id": "mission-" + "b" * 24})
    assert mismatched.status_code == 409
    dispatch = client.post("/api/improvement/experiments/dispatch", json={
        "proposal_id": auth_id, "envelope_id": envelope_id,
        "investigation_id": investigation["investigation_id"]})
    assert dispatch.status_code == 200, dispatch.text
    assert dispatch.json()["experiment"]["status"] == "complete"
    assert dispatch.json()["promotion_authorized"] is False
    assert dispatch.json()["work_outcome_execution_id"]
    repeated = client.post("/api/improvement/experiments/dispatch", json={
        "proposal_id": auth_id, "envelope_id": envelope_id,
        "investigation_id": investigation["investigation_id"]})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["work_outcome_execution_id"] == dispatch.json()["work_outcome_execution_id"]
    assert repeated.json()["experiment"]["reconciled"] is True
    experiment_root = StephanieCli(run_root=run_root).investigation_root(investigation["investigation_id"])
    ledger = experiment_root / "worker" / "worker-execution-ledger.jsonl"
    ledger_record_count = len(ledger.read_text(encoding="utf-8").splitlines())
    sc3_claim_path = experiment_root / "sc3-run.claim"
    sc3_claim = json.loads(sc3_claim_path.read_text(encoding="utf-8"))
    sc3_claim["status"] = "dispatch_may_have_started"
    sc3_claim.pop("integrated_results_sha256", None)
    sc3_claim_path.write_text(json.dumps(sc3_claim), encoding="utf-8")
    mission_claim_path = run_root / "dispatch-claims" / f"{experiment['experiment_id']}.json"
    mission_claim = json.loads(mission_claim_path.read_text(encoding="utf-8"))
    mission_claim["status"] = "dispatch_may_have_started"
    mission_claim.pop("result_digest", None)
    mission_claim_path.write_text(json.dumps(mission_claim), encoding="utf-8")
    worker_results_path = experiment_root / "worker-results.json"
    worker_results_bytes = worker_results_path.read_bytes()
    worker_results = json.loads(worker_results_bytes)
    worker_results["results"][0]["response"]["output"] = {"answer": "tampered recovery result"}
    worker_results_path.write_text(json.dumps(worker_results), encoding="utf-8")
    rejected_recovery = client.post("/api/improvement/experiments/dispatch", json={
        "proposal_id": auth_id, "envelope_id": envelope_id,
        "investigation_id": investigation["investigation_id"]})
    assert rejected_recovery.status_code == 504, rejected_recovery.text
    worker_results_path.write_bytes(worker_results_bytes)
    recovered = client.post("/api/improvement/experiments/dispatch", json={
        "proposal_id": auth_id, "envelope_id": envelope_id,
        "investigation_id": investigation["investigation_id"]})
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["experiment"]["reconciled"] is True
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == ledger_record_count
    proposal_record = client.get(f"/api/work-corrective/proposals/{auth_id}").json()["proposal"]
    assert any(link["route"] == "stephanie-sc3" and link["status"] == "reported_complete"
               for link in proposal_record["executions"])
    detail = client.get(f"/api/improvement/investigations/{investigation['investigation_id']}")
    assert detail.status_code == 200
    result = detail.json()["experiment_result"]
    assert detail.json()["retained_experience"]["status"] == "available"
    assert detail.json()["retained_experience"]["records"]
    outcome_decision = client.post(f"/api/improvement/investigations/{investigation['investigation_id']}/decision", json={
        "proposal_id": auth_id, "decision": "accepted", "actor": "SC4 reviewer",
        "rationale": "Accept this fixture result for the bounded investigation."})
    assert outcome_decision.status_code == 200, outcome_decision.text
    assert outcome_decision.json()["decision"]["evidence"]["result_digest"] == improvement._digest(result)
    assert outcome_decision.json()["decision"]["evidence"]["production_promotion_authorized"] is False
    repeated_decision = client.post(f"/api/improvement/investigations/{investigation['investigation_id']}/decision", json={
        "proposal_id": auth_id, "decision": "accepted", "actor": "SC4 reviewer"})
    assert repeated_decision.status_code == 200 and repeated_decision.json()["status"] == "duplicate"
    detail_after_decision = client.get(f"/api/improvement/investigations/{investigation['investigation_id']}")
    assert detail_after_decision.json()["human_decisions"][0]["decision"] == "accepted"
    contradictory_decision = client.post(f"/api/improvement/investigations/{investigation['investigation_id']}/decision", json={
        "proposal_id": auth_id, "decision": "rejected", "actor": "SC4 reviewer"})
    assert contradictory_decision.status_code == 409
    assert result["actual_model_invocations"] == 0
    assert len(result["praxis_comparisons"]) == 5
    assert result["C6_execution_failure"]["scenario"] == "C6"
    assert result["C7_invalid_candidate"]["rejected_before_execution"] is True
    assert (run_root / "investigations" / investigation["investigation_id"] / "retained-experience-retrieval.json").is_file()
    assert (run_root / "memory" / "stephanie-sc3-isolated.sqlite3").is_file()

    second_approval = approve_investigation("finding:sc4-retrieval")
    second = client.post("/api/improvement/investigations", json={
        **second_approval, "episode_id": "ep:sc4-e2e", "finding_id": "finding:sc4-retrieval"})
    assert second.status_code == 200, second.text
    assert second.json()["investigation"]["retrieved_experience"], "subsequent investigation must retrieve retained prior evidence"
    assert len(StephanieCli(run_root=run_root).list_investigations()) == 2
