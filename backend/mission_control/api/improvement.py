"""Read-only Mission view over Stephanie's isolated SC3 artifact store.

This adapter never launches Stephanie, models, Worker, or Praxis. It projects
bounded, digest-checked historical evidence and deliberately excludes raw AI
responses and evaluator contents.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/improvement", tags=["improvement"])


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
