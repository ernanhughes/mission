from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mission_control.api import improvement


def _sha(value):
    return improvement._digest(value)


def _write_snapshot(root):
    root.mkdir(parents=True, exist_ok=True)
    hypothesis = {"statement": "A bounded hypothesis from source evidence.", "rationale": "One sanitized source fact supports inspection.",
                  "uncertainty": "Effectiveness remains unknown.", "evidence_ids": ["worker-source-1"]}
    candidate = {"candidate_id": "candidate-1", "name": "bounded candidate", "intervention": "Inspect one existing strategy.",
                 "parameters": {"strategy_id": "adaptive.v1"}, "hypothesis": hypothesis}
    ai_hypothesis = {"hypothesis": hypothesis, "hypothesis_digest": _sha(hypothesis), "model": "local", "request_id": "req-1",
                     "authority": "hypothesis_only", "protected_evaluator_in_context": False}
    protocol = {"candidate_digest": _sha(candidate), "hypothesis_digest": ai_hypothesis["hypothesis_digest"],
                "resource_limits": {"max_output_tokens": 128}}
    protocol["protocol_digest"] = _sha(protocol)
    result = {"protocol_digest": protocol["protocol_digest"], "candidate_id": candidate["candidate_id"],
              "experiment_id": "exp-1", "formal_acceptance": "UNKNOWN", "actual_model_invocations": 0,
              "mission_writes": 0, "qualification": "deterministic fixture", "worker": {"worker_source_commit": "head"},
              "praxis_comparisons": [{"scenario": "C4", "praxis": {"decision": "insufficient_evidence"},
                  "recommendation": "insufficient_evidence", "resource_comparison": {"cost_status": "unknown"}}],
              "C6_execution_failure": {"result_status": "FAILED", "inference_executed": "UNKNOWN"},
              "C7_invalid_candidate": {"rejected_before_execution": True}}
    files = {"candidate.json": candidate, "ai-hypothesis.json": ai_hypothesis,
             "frozen-protocol.json": protocol, "integrated-results.json": result,
             "experiences.json": [{"candidate_id": "candidate-1", "experiment_id": "exp-1", "outcome": "retain",
                                   "recommendation": "retain", "decision_status": "NOT_PROMOTED", "reuse_eligible": False,
                                   "limitations": "fixture only", "worker_execution_refs": ["wrq-1"],
                                   "independent_evaluation_refs": ["praxis-c1.json"]}]}
    for name, value in files.items():
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    (root / "ai").mkdir(exist_ok=True)
    (root / "ai" / "ai-executions.json").write_text(json.dumps([{"raw_response": "private"}]), encoding="utf-8")
    tracked = ("frozen-protocol.json", "candidate.json", "ai-hypothesis.json", "integrated-results.json", "experiences.json", "ai/ai-executions.json")
    manifest = {"schema_version": "mission.sc4-artifact-snapshot.v1", "created_at": "2026-11-25T00:00:00Z",
                "files": {name: improvement._sha_file(root, name) for name in tracked}}
    manifest["manifest_digest"] = _sha(manifest)
    (root / "mission-projection-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _client(monkeypatch, root):
    monkeypatch.setenv("MISSION_CONTROL_STEPHANIE_ARTIFACT_ROOT", str(root))
    app = FastAPI()
    app.include_router(improvement.router)
    return TestClient(app)


def test_improvement_reads_digest_checked_sc3_projection_without_raw_output(tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    response = _client(monkeypatch, tmp_path).get("/api/improvement/records")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["operational_record"] is False
    assert body["formal_acceptance"] == "UNKNOWN"
    assert body["experiment"]["comparisons"][0]["decision"] == "insufficient_evidence"
    assert body["retained_experience"][0]["decision_status"] == "NOT_PROMOTED"
    assert body["hypothesis_inference"]["raw_response_exposed"] is False
    assert '"raw_response":' not in json.dumps(body)
    assert body["hypothesis_inference"]["raw_response_present"] is True


def test_improvement_rejects_tampered_candidate_snapshot(tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    candidate = json.loads((tmp_path / "candidate.json").read_text())
    candidate["intervention"] = "mutated"
    (tmp_path / "candidate.json").write_text(json.dumps(candidate))
    body = _client(monkeypatch, tmp_path).get("/api/improvement/records").json()
    assert body["status"] == "integrity_error"
    assert body["integrity"]["candidate"] is False


def test_improvement_rejects_tampered_comparison_or_experience_after_snapshot(tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    results = json.loads((tmp_path / "integrated-results.json").read_text())
    results["praxis_comparisons"][0]["praxis"]["decision"] = "retain"
    (tmp_path / "integrated-results.json").write_text(json.dumps(results))
    body = _client(monkeypatch, tmp_path).get("/api/improvement/records").json()
    assert body["status"] == "integrity_error"
    assert body["integrity"]["snapshot_manifest"] is False


def test_improvement_rejects_tampered_experience_after_snapshot(tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    experiences = json.loads((tmp_path / "experiences.json").read_text())
    experiences[0]["recommendation"] = "promote"
    (tmp_path / "experiences.json").write_text(json.dumps(experiences))
    body = _client(monkeypatch, tmp_path).get("/api/improvement/records").json()
    assert body["status"] == "integrity_error"
    assert body["integrity"]["snapshot_manifest"] is False


def test_improvement_reports_raw_response_absence_from_trace_content(tmp_path, monkeypatch):
    _write_snapshot(tmp_path)
    (tmp_path / "ai" / "ai-executions.json").write_text(json.dumps([{"status": "ok", "raw_response": None}]))
    tracked = ("frozen-protocol.json", "candidate.json", "ai-hypothesis.json", "integrated-results.json", "experiences.json", "ai/ai-executions.json")
    manifest = {"schema_version": "mission.sc4-artifact-snapshot.v1", "created_at": "2026-11-25T00:00:00Z",
                "files": {name: improvement._sha_file(tmp_path, name) for name in tracked}}
    manifest["manifest_digest"] = _sha(manifest)
    (tmp_path / "mission-projection-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    body = _client(monkeypatch, tmp_path).get("/api/improvement/records").json()
    assert body["status"] == "available"
    assert body["hypothesis_inference"]["raw_response_present"] is False


def test_improvement_reports_missing_snapshot_as_unavailable(tmp_path, monkeypatch):
    body = _client(monkeypatch, tmp_path / "missing").get("/api/improvement/records").json()
    assert body["status"] == "unavailable"
    assert "could not be read" not in body["reason"]
