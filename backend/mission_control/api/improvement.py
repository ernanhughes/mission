"""Mission-owned governance and bounded interface for Stephanie improvement.

Historical projections remain read-only. Live operations use only fixed,
allowlisted Stephanie CLI commands and an explicitly isolated run root; raw AI
responses and evaluator contents are not exposed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from mission_control.improvement.stephanie_cli import StephanieCli
from mission_control.work_observation.proposals import scope_hash_of

router = APIRouter(prefix="/api/improvement", tags=["improvement"])


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str = Field(min_length=1, max_length=64)
    episode_id: str = Field(min_length=1, max_length=160)
    finding_id: str = Field(min_length=1, max_length=64)


class ExperimentAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: str = Field(pattern=r"^mission-[a-f0-9]{24}$")
    objective_id: str = Field(min_length=1, max_length=64)


class ExperimentDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str = Field(min_length=1, max_length=64)
    envelope_id: str = Field(min_length=1, max_length=64)
    investigation_id: str = Field(pattern=r"^mission-[a-f0-9]{24}$")


class OutcomeDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str = Field(min_length=1, max_length=64)
    decision: str = Field(pattern=r"^(accepted|rejected)$")
    actor: str = Field(min_length=1, max_length=80)
    rationale: str = Field(default="", max_length=500)


def _service(request: Request, name: str):
    service = getattr(request.app.state, name, None)
    if service is None:
        raise HTTPException(status_code=503, detail=f"Mission {name} is unavailable")
    return service


@router.get("/integration")
def improvement_integration_status() -> dict[str, Any]:
    """Describe the configured local Stephanie interface without inference."""
    return {"mission_to_stephanie": StephanieCli().describe(),
            "worker_execution": {"status": "available_after_sc4_authorization",
                                 "reason": "Fixed Stephanie SC3 fixture runner; requires exact approved Mission proposal and bound active Work Envelope"},
            "praxis": {"status": "stephanie_owned_after_dispatch",
                       "reason": "SC3 runs independent evaluation and Praxis over actual Worker fixture outputs"}}


@router.get("/investigations")
def improvement_investigations() -> dict[str, Any]:
    cli = StephanieCli()
    if not cli.available:
        return {"status": "unavailable", "investigations": []}
    return {"status": "available", "investigations": cli.list_investigations()}


@router.post("/investigations")
def request_investigation(request: Request, payload: InvestigationRequest) -> dict[str, Any]:
    """Ask Stephanie for deterministic investigation of an approved Mission finding."""
    proposals = _service(request, "proposal_service")
    proposal = proposals.get_proposal(payload.proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such Mission proposal")
    if proposal.get("status") != "approved" or proposal.get("action_category") != "REQUEST_USER_DECISION":
        raise HTTPException(status_code=409, detail="An approved Mission decision request is required")
    if proposal.get("episode_id") != payload.episode_id or payload.finding_id not in proposal.get("finding_ids", []):
        raise HTTPException(status_code=409, detail="The finding is outside the approved Mission proposal")
    expected_scope_hash = scope_hash_of(proposal["action_category"], proposal["scope"],
        proposal["exclusions"], proposal["acceptance_criteria"], proposal["version"])
    if proposal.get("scope_hash") != expected_scope_hash:
        raise HTTPException(status_code=409, detail="Mission proposal scope is stale; renewed review is required")

    evaluation = _service(request, "evaluation_service")
    finding = next((row for row in evaluation.list_findings(episode_id=payload.episode_id, limit=500)
                    if row.get("id") == payload.finding_id and row.get("status") == "open"), None)
    if finding is None:
        raise HTTPException(status_code=409, detail="The Mission finding is missing or no longer open")
    episodes = _service(request, "episode_service").list_episodes(limit=200)
    episode = next((row for row in episodes if row.get("id") == payload.episode_id), None)
    if episode is None:
        raise HTTPException(status_code=404, detail="No such Mission episode")
    snapshot = {
        "episode_id": episode["id"], "project_key": episode.get("project_key") or "",
        "episode_title": episode.get("title") or "", "finding_id": finding["id"],
        "finding_title": finding.get("title") or "", "finding_kind": finding.get("kind") or "",
        "finding_severity": finding.get("severity") or "", "finding_status": finding.get("status") or "",
        "finding_rationale": finding.get("rationale") or "",
        "evidence_refs": finding.get("evidence_refs") or [],
        "next_action": finding.get("next_action") or "",
    }
    cli = StephanieCli()
    if not cli.available:
        raise HTTPException(status_code=503, detail=cli.describe()["reason"])
    try:
        result = cli.investigate(snapshot)
    except RuntimeError as exc:
        code = 504 if "unknown" in str(exc).lower() or "timeout" in str(exc).lower() else 502
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return {"status": "completed", "proposal_id": payload.proposal_id,
            "source_snapshot_digest": _digest(snapshot), "investigation": result}


@router.get("/investigations/{investigation_id}")
def get_improvement_investigation(request: Request, investigation_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"mission-[a-f0-9]{24}", investigation_id):
        raise HTTPException(status_code=404, detail="No such investigation")
    cli = StephanieCli()
    if not cli.available:
        raise HTTPException(status_code=503, detail=cli.describe()["reason"])
    record = next((row for row in cli.list_investigations()
                   if row.get("investigation_id") == investigation_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="No such investigation")
    cli = StephanieCli()
    result = cli.experiment_result(investigation_id)
    state = cli.experiment_state(investigation_id)
    query_parts = [record.get("source_identity", ""), record.get("result", "")]
    hypothesis = record.get("hypothesis") or {}
    if isinstance(hypothesis, dict):
        query_parts.extend([hypothesis.get("statement", ""), hypothesis.get("rationale", "")])
    experience_status = "available"
    try:
        retained_experience = cli.retrieve_experience(investigation_id, " ".join(map(str, query_parts))[:500])
    except (RuntimeError, OSError, ValueError):
        retained_experience = []
        experience_status = "unavailable"
    human_decisions = []
    proposals = getattr(request.app.state, "proposal_service", None)
    if proposals is not None:
        for item in proposals.list_proposals(limit=500):
            if item.get("action_category") != "REQUEST_USER_DECISION":
                continue
            try:
                scope = json.loads(item.get("scope") or "")
            except (TypeError, json.JSONDecodeError):
                continue
            if scope.get("investigation_id") != investigation_id:
                continue
            full = proposals.get_proposal(item["id"])
            for event in (full or {}).get("events", []):
                prefix = "MISSION_SC4_OUTCOME_DECISION_V1:"
                if event.get("reason", "").startswith(prefix):
                    try:
                        decision = json.loads(event["reason"][len(prefix):])
                    except json.JSONDecodeError:
                        continue
                    human_decisions.append(decision)
    return {"investigation": record, "experiment_state": state.get("status"),
            "experiment_state_evidence": state, "experiment_result": result,
            "retained_experience": {"status": experience_status,
                                    "source": "Stephanie CaseBook via isolated sc3-retrieve",
                                    "records": retained_experience},
            "human_decisions": human_decisions}


@router.post("/investigations/{investigation_id}/decision")
def record_improvement_outcome_decision(request: Request, investigation_id: str,
                                        payload: OutcomeDecisionRequest) -> dict[str, Any]:
    if not re.fullmatch(r"mission-[a-f0-9]{24}", investigation_id):
        raise HTTPException(status_code=404, detail="No such investigation")
    cli = StephanieCli()
    if not cli.available:
        raise HTTPException(status_code=503, detail=cli.describe()["reason"])
    result = cli.experiment_result(investigation_id)
    if result is None:
        raise HTTPException(status_code=409, detail="A verified completed experiment result is required")
    record, experiment = _frozen_experiment(cli, investigation_id)
    if (result.get("experiment_id") != experiment.get("experiment_id")
            or result.get("candidate_id") != experiment.get("candidate_id")
            or result.get("protocol_digest") != experiment.get("protocol_digest")):
        raise HTTPException(status_code=409, detail="Retained result does not match the frozen experiment")
    proposals = _service(request, "proposal_service")
    proposal = proposals.get_proposal(payload.proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such Mission authorization proposal")
    if proposal.get("status") not in {"approved", "queued", "running", "reported_complete"} or proposal.get("action_category") != "REQUEST_USER_DECISION":
        raise HTTPException(status_code=409, detail="The approved experiment decision proposal is required")
    if proposal.get("scope_hash") != scope_hash_of(proposal["action_category"], proposal["scope"],
            proposal["exclusions"], proposal["acceptance_criteria"], proposal["version"]):
        raise HTTPException(status_code=409, detail="Mission authorization scope is stale")
    try:
        scope = json.loads(proposal["scope"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail="Proposal is not an SC4 experiment authorization") from exc
    if (scope.get("schema_version") != "mission.sc4-experiment-authorization.v1"
            or scope.get("investigation_id") != investigation_id
            or scope.get("experiment_id") != experiment.get("experiment_id")
            or scope.get("candidate_id") != experiment.get("candidate_id")
            or scope.get("candidate_digest") != experiment.get("candidate_digest")
            or scope.get("protocol_digest") != experiment.get("protocol_digest")):
        raise HTTPException(status_code=409, detail="Authorization is not bound to this candidate and frozen protocol")
    expected_ref = (f"stephanie-sc3://{investigation_id}/{experiment['experiment_id']}/"
                    f"{experiment['protocol_digest']}/{_digest(result)}")
    if not any(link.get("route") == "stephanie-sc3" and link.get("external_ref") == expected_ref
               and link.get("status") == "reported_complete" for link in proposal.get("executions", [])):
        raise HTTPException(status_code=409, detail="The Mission Work Outcome has no matching completed experiment link")
    decision_evidence = {"schema_version": "mission.sc4-outcome-decision.v1",
        "investigation_id": investigation_id, "source_identity": record.get("source_identity"),
        "source_digest": record.get("source_digest"), "candidate_id": experiment.get("candidate_id"),
        "candidate_digest": experiment.get("candidate_digest"), "experiment_id": experiment.get("experiment_id"),
        "protocol_digest": experiment.get("protocol_digest"), "result_digest": _digest(result),
        "mission_proposal_id": proposal["id"], "mission_proposal_version": proposal["version"],
        "mission_scope_hash": proposal["scope_hash"], "production_promotion_authorized": False}
    outcome = proposals.record_sc4_outcome_decision(proposal["id"], actor=payload.actor,
        decision=payload.decision, evidence=decision_evidence, rationale=payload.rationale)
    if outcome.get("status") in {"rejected", "unknown_proposal", "conflict"}:
        raise HTTPException(status_code=409, detail=outcome.get("error", outcome["status"]))
    return outcome


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _current_source_snapshot(request: Request, episode_id: str, finding_id: str) -> dict[str, Any]:
    findings = _service(request, "evaluation_service").list_findings(episode_id=episode_id, limit=500)
    finding = next((row for row in findings if row.get("id") == finding_id and row.get("status") == "open"), None)
    if finding is None:
        raise HTTPException(status_code=409, detail="The source finding is missing or no longer open")
    episodes = _service(request, "episode_service").list_episodes(limit=200)
    episode = next((row for row in episodes if row.get("id") == episode_id), None)
    if episode is None:
        raise HTTPException(status_code=409, detail="The source episode is no longer available")
    return {"episode_id": episode["id"], "project_key": episode.get("project_key") or "",
            "episode_title": episode.get("title") or "", "finding_id": finding["id"],
            "finding_title": finding.get("title") or "", "finding_kind": finding.get("kind") or "",
            "finding_severity": finding.get("severity") or "", "finding_status": finding.get("status") or "",
            "finding_rationale": finding.get("rationale") or "", "evidence_refs": finding.get("evidence_refs") or [],
            "next_action": finding.get("next_action") or ""}


def _frozen_experiment(cli: StephanieCli, investigation_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    record = next((row for row in cli.list_investigations()
                   if row.get("investigation_id") == investigation_id), None)
    if record is None or record.get("status") != "completed":
        raise HTTPException(status_code=404, detail="No completed investigation")
    experiment = next(iter(record.get("proposed_experiments") or []), None)
    if not isinstance(experiment, dict):
        raise HTTPException(status_code=409, detail="This investigation has no executable frozen experiment")
    root = cli.investigation_root(investigation_id)
    try:
        candidate = _read(root, "candidate.json")
        protocol = _read(root, "frozen-protocol.json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Frozen experiment artifacts are unavailable") from exc
    if (candidate.get("candidate_id") != experiment.get("candidate_id")
            or _digest(candidate) != experiment.get("candidate_digest")
            or protocol.get("experiment_id") != experiment.get("experiment_id")
            or protocol.get("protocol_digest") != experiment.get("protocol_digest")
            or _digest({k: v for k, v in protocol.items() if k != "protocol_digest"}) != experiment.get("protocol_digest")
            or protocol.get("candidate_digest") != experiment.get("candidate_digest")):
        raise HTTPException(status_code=409, detail="Frozen experiment integrity check failed")
    return record, experiment


@router.post("/experiment-authorizations")
def request_experiment_authorization(request: Request,
                                    payload: ExperimentAuthorizationRequest) -> dict[str, Any]:
    """Create a Work Corrective proposal bound to one immutable SC3 fixture."""
    cli = StephanieCli()
    if not cli.available:
        raise HTTPException(status_code=503, detail=cli.describe()["reason"])
    record, experiment = _frozen_experiment(cli, payload.investigation_id)
    episode_id = record["source_snapshot"]["episode_id"]
    finding_id = record["source_snapshot"]["finding_id"]
    if _digest(_current_source_snapshot(request, episode_id, finding_id)) != record.get("source_digest"):
        raise HTTPException(status_code=409, detail="Mission source evidence changed; create a new investigation")
    objectives = _service(request, "intent_service").list_objectives(episode_id=episode_id, limit=500)
    objective = next((row for row in objectives if row.get("id") == payload.objective_id
                      and row.get("episode_id") == episode_id), None)
    if objective is None:
        raise HTTPException(status_code=409, detail="Work Objective must belong to the finding's Mission episode")
    scope_doc = {"schema_version": "mission.sc4-experiment-authorization.v1",
                 "investigation_id": payload.investigation_id,
                 "source_identity": record["source_identity"], "source_digest": record["source_digest"],
                 "candidate_id": experiment["candidate_id"], "candidate_digest": experiment["candidate_digest"],
                 "experiment_id": experiment["experiment_id"], "protocol_digest": experiment["protocol_digest"],
                 "resource_limits": experiment.get("resource_limits"),
                 "authorized_requirement_refs": [], "authorized_repositories": [],
                 "acceptance_policy_ref": "w6b-v1",
                 "objective_id": objective["id"], "objective_version": objective["version"],
                 "objective_digest": _digest({"id": objective["id"], "text": objective["text"], "version": objective["version"]}),
                 "episode_id": episode_id,
                 "finding_id": finding_id, "provider_policy": "deterministic fixture; no model calls",
                 "promotion_authorized": False}
    service = _service(request, "proposal_service")
    eligible = [row for row in service.list_proposals(episode_id=episode_id, limit=500)
                if row.get("status") == "approved" and row.get("action_category") == "REQUEST_USER_DECISION"
                and finding_id in row.get("finding_ids", [])]
    if len(eligible) != 1:
        raise HTTPException(status_code=409, detail="Exactly one approved Work Corrective proposal must cover this finding")
    proposal_id = eligible[0]["id"]
    changed = service.edit_scope(proposal_id,
        objective=f"Run frozen SC3 fixture {experiment['experiment_id']} once; no promotion.",
        scope=_canonical(scope_doc),
        exclusions="No production promotion; no model calls; no alternate candidate or protocol; one dispatch only.",
        acceptance_criteria="Record actual isolated Worker, independent evaluator and Praxis outputs, including failures and resource observations.")
    if changed.get("status") not in ("completed", "no_change"):
        raise HTTPException(status_code=409, detail=changed.get("error", "Mission could not revise the proposal scope"))
    return {"status": "decision_requested", "proposal_id": proposal_id,
            "scope": scope_doc, "approval_route": "existing Work Corrective human review"}


@router.post("/experiments/dispatch")
def dispatch_improvement_experiment(request: Request,
                                    payload: ExperimentDispatchRequest) -> dict[str, Any]:
    """Run only the exact experiment frozen into an approved proposal/envelope."""
    cli = StephanieCli()
    if not cli.available:
        raise HTTPException(status_code=503, detail=cli.describe()["reason"])
    proposals = _service(request, "proposal_service")
    proposal = proposals.get_proposal(payload.proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such Mission authorization proposal")
    if proposal.get("status") not in {"approved", "queued", "running", "reported_complete"} or proposal.get("action_category") != "REQUEST_USER_DECISION":
        raise HTTPException(status_code=409, detail="A human-approved Work Corrective decision or its existing dispatch record is required")
    if proposal.get("scope_hash") != scope_hash_of(
            proposal["action_category"], proposal["scope"], proposal["exclusions"],
            proposal["acceptance_criteria"], proposal["version"]):
        raise HTTPException(status_code=409, detail="Authorization scope is stale")
    try:
        scope = json.loads(proposal["scope"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail="Proposal is not an SC4 experiment authorization") from exc
    if not isinstance(scope, dict) or scope.get("schema_version") != "mission.sc4-experiment-authorization.v1":
        raise HTTPException(status_code=409, detail="Proposal is not an SC4 experiment authorization")
    if scope.get("investigation_id") != payload.investigation_id or proposal.get("episode_id") != scope.get("episode_id") or scope.get("finding_id") not in proposal.get("finding_ids", []):
        raise HTTPException(status_code=409, detail="Authorization is for a different Mission investigation")
    objective = next((row for row in _service(request, "intent_service").list_objectives(
        episode_id=scope.get("episode_id"), limit=500) if row.get("id") == scope.get("objective_id")), None)
    if (objective is None or objective.get("status") != "current"
            or objective.get("version") != scope.get("objective_version")
            or _digest({"id": objective.get("id"), "text": objective.get("text"), "version": objective.get("version")}) != scope.get("objective_digest")):
        raise HTTPException(status_code=409, detail="Authorized Work Objective changed after review")
    record, experiment = _frozen_experiment(cli, payload.investigation_id)
    if _digest(_current_source_snapshot(request, scope["episode_id"], scope["finding_id"])) != scope.get("source_digest"):
        raise HTTPException(status_code=409, detail="Mission source evidence changed after approval")
    expected = {"schema_version": "mission.sc4-experiment-authorization.v1",
                "investigation_id": payload.investigation_id,
                "source_identity": record["source_identity"], "source_digest": record["source_digest"],
                "candidate_id": experiment["candidate_id"], "candidate_digest": experiment["candidate_digest"],
                "experiment_id": experiment["experiment_id"], "protocol_digest": experiment["protocol_digest"],
                "resource_limits": experiment.get("resource_limits"),
                "authorized_requirement_refs": [], "authorized_repositories": [],
                "acceptance_policy_ref": "w6b-v1",
                "objective_id": scope.get("objective_id"), "objective_version": scope["objective_version"],
                "objective_digest": scope["objective_digest"], "episode_id": scope["episode_id"],
                "finding_id": scope["finding_id"], "provider_policy": "deterministic fixture; no model calls",
                "promotion_authorized": False}
    if _canonical(scope) != _canonical(expected):
        raise HTTPException(status_code=409, detail="Approved authority does not match current frozen experiment")
    envelope_service = _service(request, "envelope_service")
    envelope = next((row for row in envelope_service.list_envelopes(episode_id=scope["episode_id"], limit=500)
                     if row.get("id") == payload.envelope_id), None)
    expected_auth = f"proposal:{proposal['id']}@v{proposal['version']}:{proposal['scope_hash']}"
    if (envelope is None or envelope.get("status") != "active"
            or envelope.get("objective_ref") != scope["objective_id"]
            or envelope.get("authorization_ref") != expected_auth
            or envelope.get("originating_findings", []) != [scope["finding_id"]]):
        raise HTTPException(status_code=409, detail="An active Work Envelope bound to this approved decision is required")
    dispatch_ref = (f"stephanie-sc3://{payload.investigation_id}/{experiment['experiment_id']}/"
                    f"{experiment['protocol_digest']}")
    reservation = envelope_service.reserve_stephanie_dispatch(
        envelope_id=payload.envelope_id, proposal_id=proposal["id"],
        expected_scope=_canonical(expected), external_ref=dispatch_ref)
    if reservation.get("status") not in ("reserved", "duplicate"):
        raise HTTPException(status_code=409, detail=reservation.get("error", "Mission dispatch reservation failed"))
    try:
        result = cli.dispatch_experiment(payload.investigation_id,
            candidate_id=experiment["candidate_id"], candidate_digest=experiment["candidate_digest"],
            experiment_id=experiment["experiment_id"], protocol_digest=experiment["protocol_digest"])
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        code = 504 if "unknown" in str(exc).lower() or "timeout" in str(exc).lower() else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    artifact = cli.experiment_result(payload.investigation_id)
    if (artifact is None or artifact.get("experiment_id") != experiment["experiment_id"]
            or artifact.get("candidate_id") != experiment["candidate_id"]
            or artifact.get("protocol_digest") != experiment["protocol_digest"]):
        raise HTTPException(status_code=504, detail="Experiment dispatch completed without a verifiable retained result; reconcile the existing claim")
    result_digest = _digest(artifact)
    link = envelope_service.link_verified_stephanie_execution(
        envelope_id=payload.envelope_id, proposal_id=proposal["id"],
        external_ref=dispatch_ref + "/" + result_digest,
        status="reported_complete")
    if link.get("status") not in ("completed", "duplicate"):
        raise HTTPException(status_code=409, detail="Experiment result is retained, but Work Outcome linkage needs reconciliation: " + link.get("error", link.get("status", "unknown")))
    return {"status": "completed", "proposal_id": proposal["id"],
            "envelope_id": payload.envelope_id, "investigation_id": payload.investigation_id,
            "work_outcome_execution_id": link.get("execution_id"),
            "experiment": result, "result_digest": result_digest, "promotion_authorized": False}


def _default_root() -> Path:
    mission_root = Path(__file__).resolve().parents[3]
    return mission_root.parent / "stephanie" / "data" / "stephanie_convergence03_ai_integrated"


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read(root: Path, name: str) -> Any:
    path = root / name
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise FileNotFoundError(name)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha_file(root: Path, name: str) -> str:
    path = root / name
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise FileNotFoundError(name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@router.get("/records")
def improvement_records() -> dict[str, Any]:
    """Return a digest-checked projection of the isolated SC3 snapshot."""
    configured = os.environ.get("MISSION_CONTROL_STEPHANIE_ARTIFACT_ROOT")
    root = Path(configured).expanduser().resolve() if configured else _default_root().resolve()
    required = ("frozen-protocol.json", "candidate.json", "ai-hypothesis.json", "integrated-results.json", "experiences.json", "ai/ai-executions.json", "mission-projection-manifest.json")
    if not root.is_dir() or any(not (root / name).is_file() for name in required):
        return {"status": "unavailable", "source": "isolated_sc3_artifacts", "reason": "Stephanie SC3 artifact snapshot is unavailable"}
    try:
        protocol = _read(root, "frozen-protocol.json")
        candidate = _read(root, "candidate.json")
        ai_hypothesis = _read(root, "ai-hypothesis.json")
        ai_trace = _read(root, "ai/ai-executions.json")
        result = _read(root, "integrated-results.json")
        experiences = _read(root, "experiences.json")
        manifest = _read(root, "mission-projection-manifest.json")
        if (not all(isinstance(x, dict) for x in (protocol, candidate, ai_hypothesis, result))
                or not isinstance(experiences, list) or not isinstance(ai_trace, list)):
            raise ValueError("unexpected artifact shape")
        hypothesis = ai_hypothesis.get("hypothesis")
        protocol_digest = protocol.get("protocol_digest")
        candidate_ok = protocol.get("candidate_digest") == _digest(candidate)
        protocol_ok = protocol_digest == _digest({k: v for k, v in protocol.items() if k != "protocol_digest"})
        hypothesis_ok = (isinstance(hypothesis, dict)
                         and ai_hypothesis.get("hypothesis_digest") == _digest(hypothesis)
                         and candidate.get("hypothesis") == hypothesis
                         and protocol.get("hypothesis_digest") == ai_hypothesis.get("hypothesis_digest"))
        manifest_files = manifest.get("files") if isinstance(manifest, dict) else None
        manifest_without_digest = {k: v for k, v in manifest.items() if k != "manifest_digest"} if isinstance(manifest, dict) else {}
        manifest_ok = (manifest.get("schema_version") == "mission.sc4-artifact-snapshot.v1"
                       and isinstance(manifest_files, dict)
                       and manifest.get("manifest_digest") == _digest(manifest_without_digest)
                       and all(manifest_files.get(name) == _sha_file(root, name) for name in required[:-1]))
        if not (candidate_ok and protocol_ok and hypothesis_ok
                and manifest_ok
                and result.get("protocol_digest") == protocol_digest
                and result.get("candidate_id") == candidate.get("candidate_id")):
            return {"status": "integrity_error", "source": "isolated_sc3_artifacts",
                    "integrity": {"snapshot_manifest": manifest_ok, "protocol": protocol_ok,
                                  "candidate": candidate_ok, "hypothesis": hypothesis_ok}}
        comparisons = []
        for item in result.get("praxis_comparisons", []):
            if not isinstance(item, dict):
                continue
            comparison = item.get("praxis") or {}
            resource = item.get("resource_comparison") or {}
            comparisons.append({"scenario": item.get("scenario"),
                "decision": comparison.get("decision"), "recommendation": item.get("recommendation"),
                "baseline_invocations": resource.get("baseline_invocations"),
                "candidate_invocations": resource.get("candidate_invocations"),
                "additional_compute": resource.get("additional_compute"),
                "cost_status": resource.get("cost_status", "unknown")})
        retained = [{"candidate_id": x.get("candidate_id"), "experiment_id": x.get("experiment_id"),
            "outcome": x.get("outcome"), "recommendation": x.get("recommendation"),
            "decision_status": x.get("decision_status"), "reuse_eligible": x.get("reuse_eligible"),
            "limitations": x.get("limitations"), "execution_reference_count": len(x.get("worker_execution_refs", [])),
            "evaluation_references": x.get("independent_evaluation_refs", [])}
            for x in experiences if isinstance(x, dict)]
        return {"status": "available", "source": "isolated_sc3_artifacts", "operational_record": False,
            "integrity": {"snapshot_manifest": True, "manifest_digest": manifest.get("manifest_digest"),
                          "snapshot_created_at": manifest.get("created_at"),
                          "qualification": "post-hoc SC4 snapshot consistency; not a signature or independent source attestation"},
            "formal_acceptance": result.get("formal_acceptance", "UNKNOWN"),
            "actual_worker_model_invocations": result.get("actual_model_invocations"),
            "mission_writes": result.get("mission_writes"),
            "experiment": {"experiment_id": result.get("experiment_id"), "protocol_digest": protocol_digest,
                "qualification": result.get("qualification"), "worker_source_commit": (result.get("worker") or {}).get("worker_source_commit"),
                "comparisons": comparisons, "execution_failure": result.get("C6_execution_failure"),
                "invalid_candidate": result.get("C7_invalid_candidate")},
            "candidate": {"candidate_id": candidate.get("candidate_id"), "name": candidate.get("name"),
                "intervention": candidate.get("intervention"), "parameters": candidate.get("parameters"),
                "hypothesis": hypothesis, "digest": protocol.get("candidate_digest")},
            "hypothesis_inference": {"model": ai_hypothesis.get("model"), "request_id": ai_hypothesis.get("request_id"),
                "authority": ai_hypothesis.get("authority"), "evaluator_in_context": ai_hypothesis.get("protected_evaluator_in_context"),
                "raw_response_present": any(isinstance(row, dict) and row.get("raw_response") is not None for row in ai_trace),
                "raw_response_exposed": False},
            "retained_experience": retained}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "unavailable", "source": "isolated_sc3_artifacts",
                "reason": "Stephanie SC3 artifact snapshot could not be read safely"}
