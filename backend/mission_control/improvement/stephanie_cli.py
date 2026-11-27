"""Allowlisted adapter for Stephanie's bounded local CLI.

Only fixed investigation, retrieval, dispatch, and reconciliation operations
are callable here. The adapter never accepts a command, executable, working
directory, or root from an HTTP caller. It requires an explicitly configured
isolated run root.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class StephanieCli:
    def __init__(self, *, stephanie_root: Path | None = None,
                 run_root: Path | None = None, python: Path | None = None) -> None:
        projects_root = Path(__file__).resolve().parents[3].parent
        self.stephanie_root = (stephanie_root or Path(os.environ.get(
            "MISSION_CONTROL_STEPHANIE_ROOT", str(projects_root / "stephanie")))).resolve()
        configured_run_root = run_root or (Path(os.environ["MISSION_CONTROL_STEPHANIE_RUN_ROOT"])
                                            if os.environ.get("MISSION_CONTROL_STEPHANIE_RUN_ROOT") else None)
        self.run_root = configured_run_root.resolve() if configured_run_root else None
        configured_python = python or (Path(os.environ["MISSION_CONTROL_STEPHANIE_PYTHON"])
                                        if os.environ.get("MISSION_CONTROL_STEPHANIE_PYTHON") else None)
        self.python = (configured_python.resolve() if configured_python else
                       self.stephanie_root / "venv" / "Scripts" / "python.exe")

    @property
    def available(self) -> bool:
        return bool(self.run_root and self.python.is_file()
                    and self._run_root_is_isolated()
                    and (self.stephanie_root / "stephanie" / "improvement" / "cli.py").is_file()
                    and (self.stephanie_root.parent / "praxis" / "praxis").is_dir()
                    and (self.stephanie_root.parent / "ai" / "src" / "ai").is_dir())

    def describe(self) -> dict[str, Any]:
        if not self.available:
            missing = ("isolated run root is not configured" if not self.run_root else
                       "configured run root overlaps an application/source checkout" if not self._run_root_is_isolated() else
                       "CLI runtime or shared source checkout is unavailable")
            return {"status": "unavailable", "interface": "local allowlisted Stephanie CLI",
                    "reason": missing, "execution_authority": "none"}
        return {"status": "available", "interface": "local allowlisted Stephanie CLI",
                "workflow": "deterministic source-bound Mission investigation",
                "execution_authority": "investigation only; no experiment dispatch"}

    def _run_root_is_isolated(self) -> bool:
        if self.run_root is None:
            return False
        try:
            root = self.run_root.resolve()
            projects = self.stephanie_root.parent
            # Writable run data must live outside every application source
            # checkout, including Stephanie's historical/operational data.
            for name in ("mission", "stephanie", "worker", "praxis", "ai"):
                checkout = projects / name
                if root == checkout or root.is_relative_to(checkout.resolve()):
                    return False
            historical = self.stephanie_root / "data"
            if root == historical.resolve() or root.is_relative_to(historical.resolve()):
                return False
            return True
        except (OSError, RuntimeError):
            return False

    def investigate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.available or self.run_root is None:
            raise RuntimeError("Stephanie investigation CLI is unavailable or has no isolated run root")
        if len(json.dumps(snapshot, ensure_ascii=False)) > 24_000:
            raise ValueError("source snapshot exceeds the 24 KB interface bound")
        source_id = f"mission:episode/{snapshot['episode_id']}/finding/{snapshot['finding_id']}"
        source_digest = _digest(snapshot)
        investigation_id = "mission-" + _digest({"source_identity": source_id,
                                                  "source_digest": source_digest})[:24]
        self.run_root.mkdir(parents=True, exist_ok=True)
        # Stephanie's SC3 artifacts (candidate, protocol, execution claim and
        # result) are root-scoped. Give every Mission investigation its own
        # isolated root so one finding can never overwrite another's freeze.
        investigation_root = self.run_root / "investigations" / investigation_id
        investigation_root.mkdir(parents=True, exist_ok=True)
        claim_dir = self.run_root / "claims"
        claim_dir.mkdir(parents=True, exist_ok=True)
        claim_path = claim_dir / f"{investigation_id}.json"
        if claim_path.exists():
            existing = next((row for row in self.list_investigations()
                             if row.get("investigation_id") == investigation_id), None)
            if existing is not None and existing.get("source_digest") == source_digest:
                return existing
            raise RuntimeError("investigation state is UNKNOWN after a prior dispatch claim; reconcile before retry")
        claim = {"schema_version": "mission.stephanie-investigation-claim.v1",
                 "investigation_id": investigation_id, "source_digest": source_digest,
                 "status": "dispatch_may_have_started"}
        try:
            descriptor = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("investigation state is UNKNOWN after a concurrent dispatch claim") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(claim, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        incoming = investigation_root / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        source_file = incoming / f"{investigation_id}.json"
        encoded = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if source_file.exists() and source_file.read_text(encoding="utf-8") != encoded:
            raise RuntimeError("investigation input identity collision")
        if not source_file.exists():
            temp = source_file.with_suffix(".json.tmp")
            temp.write_text(encoded, encoding="utf-8")
            temp.replace(source_file)
        try:
            completed = subprocess.run(
                [str(self.python), "-m", "stephanie.improvement.cli", "--root",
                 str(investigation_root), "mission-investigate", str(source_file)],
                cwd=str(self.stephanie_root), env=self._child_environment(),
                capture_output=True, text=True, timeout=30, check=False,
                shell=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Stephanie investigation state is unknown after the 30-second timeout; retrieve before retrying") from exc
        if completed.returncode != 0:
            raise RuntimeError("Stephanie investigation failed: " + (completed.stderr or "CLI returned nonzero")[-1200:])
        if len(completed.stdout) > 1_000_000:
            raise RuntimeError("Stephanie investigation response exceeded the 1 MB bound")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Stephanie CLI returned malformed investigation JSON") from exc
        if result.get("investigation_id") != investigation_id or result.get("source_digest") != _digest(snapshot):
            raise RuntimeError("Stephanie result identity does not match the Mission source snapshot")
        claim.update({"status": "completed", "result_digest": _digest(result)})
        temp_claim = claim_path.with_suffix(".json.tmp")
        temp_claim.write_text(json.dumps(claim, sort_keys=True) + "\n", encoding="utf-8")
        temp_claim.replace(claim_path)
        return result

    def list_investigations(self) -> list[dict[str, Any]]:
        if not self.run_root:
            return []
        results: list[dict[str, Any]] = []
        parent = self.run_root / "investigations"
        if not parent.is_dir():
            return results
        for path in sorted(parent.glob("mission-*/investigations.json")):
            if path.stat().st_size > 5_000_000:
                continue
            rows = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                results.extend(row for row in rows if isinstance(row, dict))
        return results[-100:]

    def investigation_root(self, investigation_id: str) -> Path:
        if not self.run_root or not re.fullmatch(r"mission-[a-f0-9]{24}", investigation_id):
            raise ValueError("invalid investigation identity")
        root = (self.run_root / "investigations" / investigation_id).resolve()
        if not root.is_relative_to(self.run_root / "investigations"):
            raise ValueError("investigation path escapes configured root")
        return root

    def dispatch_experiment(self, investigation_id: str, *,
                            candidate_id: str, candidate_digest: str,
                            experiment_id: str, protocol_digest: str) -> dict[str, Any]:
        """Dispatch one already-authorized, exact frozen SC3 experiment.

        Mission validates its Work Corrective decision and Work Envelope
        before calling this fixed CLI operation. A local exclusive claim is
        retained on every outcome, including timeout, so retry is forbidden.
        """
        if not self.available:
            raise RuntimeError("Stephanie experiment runtime is unavailable")
        root = self.investigation_root(investigation_id)
        protocol = json.loads((root / "frozen-protocol.json").read_text(encoding="utf-8"))
        candidate = json.loads((root / "candidate.json").read_text(encoding="utf-8"))
        if (protocol.get("protocol_digest") != protocol_digest
                or _digest({k: v for k, v in protocol.items() if k != "protocol_digest"}) != protocol_digest
                or protocol.get("candidate_digest") != candidate_digest
                or protocol.get("experiment_id") != experiment_id
                or candidate.get("candidate_id") != candidate_id
                or _digest(candidate) != candidate_digest):
            raise ValueError("approved experiment identity no longer matches frozen artifacts")
        claims = self.run_root / "dispatch-claims"
        claims.mkdir(parents=True, exist_ok=True)
        claim_path = claims / f"{experiment_id}.json"
        claim = {"schema_version": "mission.stephanie-dispatch-claim.v1",
                 "investigation_id": investigation_id, "candidate_id": candidate_id,
                 "candidate_digest": candidate_digest, "experiment_id": experiment_id,
                 "protocol_digest": protocol_digest, "status": "dispatch_may_have_started"}
        if claim_path.exists():
            previous = json.loads(claim_path.read_text(encoding="utf-8"))
            if any(previous.get(key) != claim.get(key) for key in (
                    "investigation_id", "candidate_id", "candidate_digest", "experiment_id", "protocol_digest")):
                raise RuntimeError("experiment claim identity conflicts; state is UNKNOWN")
            if previous.get("status") == "completed":
                saved = self.experiment_result(investigation_id)
                if (saved is not None and saved.get("experiment_id") == experiment_id
                        and saved.get("protocol_digest") == protocol_digest
                        and saved.get("candidate_id") == candidate_id
                        and _digest(saved) == previous.get("result_digest")):
                    return {"status": "complete", "experiment_id": experiment_id,
                            "protocol_digest": protocol_digest, "candidate_id": candidate_id,
                            "result_digest": previous["result_digest"], "reconciled": True}
            saved = self._read_experiment_artifact(investigation_id)
            if (saved is not None and saved.get("experiment_id") == experiment_id
                    and saved.get("protocol_digest") == protocol_digest
                    and saved.get("candidate_id") == candidate_id):
                result_digest = _digest(saved)
                previous.update({"status": "completed", "result_digest": result_digest,
                                 "reconciled_from_sc3_claim": True})
                tmp_claim = claim_path.with_suffix(".json.tmp")
                tmp_claim.write_text(json.dumps(previous, sort_keys=True) + "\n", encoding="utf-8")
                tmp_claim.replace(claim_path)
                return {"status": "complete", "experiment_id": experiment_id,
                        "protocol_digest": protocol_digest, "candidate_id": candidate_id,
                        "result_digest": result_digest, "reconciled": True}
            # Reconciliation invokes no Worker API. It only validates a full
            # saved Worker result/ledger set and finishes Praxis/retention.
            if (root / "worker-results.json").is_file() and (root / "sc3-run.claim").is_file():
                try:
                    recovery = subprocess.run(
                        [str(self.python), "-m", "stephanie.improvement.cli", "--root",
                         str(root), "sc3-reconcile"], cwd=str(self.stephanie_root),
                        env=self._child_environment(), capture_output=True, text=True,
                        timeout=120, check=False, shell=False)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("SC3 reconciliation remains UNKNOWN; Worker will not be retried") from exc
                if recovery.returncode == 0 and len(recovery.stdout) <= 1_000_000:
                    try:
                        recovered = json.loads(recovery.stdout)
                    except json.JSONDecodeError:
                        recovered = {}
                    reconciled_artifact = self._read_experiment_artifact(investigation_id)
                    if (recovered.get("status") in {"reconciled", "already_completed"}
                            and reconciled_artifact is not None
                            and reconciled_artifact.get("experiment_id") == experiment_id
                            and reconciled_artifact.get("protocol_digest") == protocol_digest
                            and reconciled_artifact.get("candidate_id") == candidate_id):
                        result_digest = _digest(reconciled_artifact)
                        previous.update({"status": "completed", "result_digest": result_digest,
                                         "reconciled_from_worker_ledger": True})
                        tmp_claim = claim_path.with_suffix(".json.tmp")
                        tmp_claim.write_text(json.dumps(previous, sort_keys=True) + "\n", encoding="utf-8")
                        tmp_claim.replace(claim_path)
                        return {"status": "complete", "experiment_id": experiment_id,
                                "protocol_digest": protocol_digest, "candidate_id": candidate_id,
                                "result_digest": result_digest, "reconciled": True}
            raise RuntimeError("experiment dispatch is already claimed; state is UNKNOWN and must be reconciled, never retried")
        try:
            fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("experiment dispatch is already claimed; state is UNKNOWN, never retry") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(claim, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            result = subprocess.run(
                [str(self.python), "-m", "stephanie.improvement.cli", "--root",
                 str(root), "sc3-run"], cwd=str(self.stephanie_root),
                env=self._child_environment(), capture_output=True, text=True,
                timeout=180, check=False, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("experiment dispatch outcome is UNKNOWN after timeout; reconcile from Worker ledger") from exc
        if result.returncode != 0:
            raise RuntimeError("Stephanie experiment failed or is UNKNOWN: " +
                               (result.stderr or "CLI returned nonzero")[-1200:])
        if len(result.stdout) > 1_000_000:
            raise RuntimeError("Stephanie experiment response exceeded the 1 MB bound")
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Stephanie returned malformed experiment result; state is UNKNOWN") from exc
        if response.get("experiment_id") != experiment_id or response.get("status") != "complete":
            raise RuntimeError("Stephanie experiment identity/status mismatch; state is UNKNOWN")
        artifact = self._read_experiment_artifact(investigation_id)
        if (artifact is None or artifact.get("experiment_id") != experiment_id
                or artifact.get("protocol_digest") != protocol_digest
                or artifact.get("candidate_id") != candidate_id):
            raise RuntimeError("experiment output artifact is unavailable or has mismatched identity; state is UNKNOWN")
        result_digest = _digest(artifact)
        claim.update({"status": "completed", "result_digest": result_digest})
        tmp = claim_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(claim, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(claim_path)
        return {**response, "result_digest": result_digest}

    def experiment_result(self, investigation_id: str) -> dict[str, Any] | None:
        result = self._read_experiment_artifact(investigation_id)
        if result is None:
            return None
        if self.run_root is None or not result.get("experiment_id"):
            return None
        claim_path = self.run_root / "dispatch-claims" / f"{result['experiment_id']}.json"
        if not claim_path.is_file():
            return None
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        if (claim.get("status") != "completed"
                or claim.get("investigation_id") != investigation_id
                or claim.get("candidate_id") != result.get("candidate_id")
                or claim.get("protocol_digest") != result.get("protocol_digest")
                or claim.get("result_digest") != _digest(result)):
            return None
        return result

    def retrieve_experience(self, investigation_id: str, query: str) -> list[dict[str, Any]]:
        """Read bounded retained experience through Stephanie's fixed CLI."""
        if not self.available:
            raise RuntimeError("Stephanie experience retrieval is unavailable")
        if not re.fullmatch(r"mission-[a-f0-9]{24}", investigation_id):
            raise ValueError("invalid investigation identity")
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("experience query must contain 1–500 characters")
        root = self.investigation_root(investigation_id)
        try:
            completed = subprocess.run(
                [str(self.python), "-m", "stephanie.improvement.cli", "--root",
                 str(root), "sc3-retrieve", query.strip()],
                cwd=str(self.stephanie_root), env=self._child_environment(),
                capture_output=True, text=True, timeout=15, check=False, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Stephanie experience retrieval timed out") from exc
        if completed.returncode != 0:
            raise RuntimeError("Stephanie experience retrieval failed: " +
                               (completed.stderr or "CLI returned nonzero")[-800:])
        if len(completed.stdout) > 256_000:
            raise RuntimeError("Stephanie experience response exceeded the 256 KB bound")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Stephanie returned malformed experience JSON") from exc
        if not isinstance(result, list) or len(result) > 100 or any(not isinstance(row, dict) for row in result):
            raise RuntimeError("Stephanie returned an invalid experience collection")
        return result

    def _read_experiment_artifact(self, investigation_id: str) -> dict[str, Any] | None:
        root = self.investigation_root(investigation_id)
        path = root / "integrated-results.json"
        if not path.is_file() or path.stat().st_size > 5_000_000:
            return None
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            return None
        sc3_claim_path = root / "sc3-run.claim"
        if not sc3_claim_path.is_file():
            return None
        sc3_claim = json.loads(sc3_claim_path.read_text(encoding="utf-8"))
        if (sc3_claim.get("status") != "completed"
                or sc3_claim.get("experiment_id") != result.get("experiment_id")
                or sc3_claim.get("protocol_digest") != result.get("protocol_digest")
                or sc3_claim.get("integrated_results_sha256") != _digest_file(path)):
            return None
        worker_ledger = root / "worker" / "worker-execution-ledger.jsonl"
        if (not worker_ledger.is_file() or worker_ledger.stat().st_size > 10_000_000
                or _digest_file(worker_ledger) != result.get("worker_ledger_sha256")):
            return None
        return result

    def experiment_state(self, investigation_id: str) -> dict[str, Any]:
        root = self.investigation_root(investigation_id)
        result = self.experiment_result(investigation_id)
        if result is not None:
            return {"status": "completed", "experiment_id": result.get("experiment_id"),
                    "worker_ledger_sha256": result.get("worker_ledger_sha256"),
                    "worker_ledger_record_count": result.get("worker_ledger_record_count")}
        sc3_claim_path = root / "sc3-run.claim"
        worker_ledger = root / "worker" / "worker-execution-ledger.jsonl"
        if not sc3_claim_path.is_file():
            return {"status": "not_dispatched"}
        try:
            records = len(worker_ledger.read_text(encoding="utf-8").splitlines()) if worker_ledger.is_file() else 0
        except OSError:
            records = None
        return {"status": "unknown", "worker_ledger_present": worker_ledger.is_file(),
                "worker_ledger_records": records,
                "reconcilable_without_worker_retry": (root / "worker-results.json").is_file(),
                "reason": "SC3 completion claim, result digest, or Worker ledger integrity is unresolved"}

    def _child_environment(self) -> dict[str, str]:
        """Pass runtime essentials only; never inherit application secrets."""
        allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE")
        env = {key: os.environ[key] for key in allowed if os.environ.get(key)}
        root = self.stephanie_root
        env["PYTHONPATH"] = os.pathsep.join(str(path) for path in
            (root, root.parent / "praxis", root.parent / "ai" / "src"))
        # Shared only across per-investigation roots under this configured
        # isolated Mission run directory; never the operational SIS database.
        if self.run_root is not None:
            memory_root = self.run_root / "memory"
            memory_root.mkdir(parents=True, exist_ok=True)
            env["MISSION_CONTROL_STEPHANIE_MEMORY_ROOT"] = str(memory_root)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

