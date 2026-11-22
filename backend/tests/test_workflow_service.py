from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_control.config import RuntimeSettings
from mission_control.integrations.store import upsert_resources
from mission_control.adapters.base import ResourceSeed
from mission_control.models import IntegrationRecord
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.workflows.sandbox import SandboxResult
from mission_control.workflows.service import WorkerRequestError, WorkflowService

CORRECT_CODE = '''def reduce_trace(events):
    if not events:
        return []
    reduced = [events[0]]
    for event in events[1:-1]:
        if event != reduced[-1]:
            reduced.append(event)
    reduced.append(events[-1])
    return reduced
'''

TESTS = '''from tracelite.reduce import reduce_trace

def test_empty_trace():
    assert reduce_trace([]) == []

def test_removes_consecutive_duplicates():
    events = [{"step": "a"}, {"step": "a"}, {"step": "b"}]
    assert reduce_trace(events) == [{"step": "a"}, {"step": "b"}]

def test_preserves_first_and_last():
    events = [{"step": "start"}, {"step": "middle"}, {"step": "end"}]
    result = reduce_trace(events)
    assert result[0] == events[0]
    assert result[-1] == events[-1]

def test_reduces_duplicate_heavy_fixture():
    events = [{"step": "a"}] * 10 + [{"step": "b"}] * 10 + [{"step": "c"}]
    assert reduce_trace(events) == [{"step": "a"}, {"step": "b"}, {"step": "c"}]

def test_does_not_mutate_input():
    events = [{"step": "a"}, {"step": "a"}, {"step": "b"}]
    original = list(events)
    reduce_trace(events)
    assert events == original
'''

MEASURE = '''import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracelite.reduce import reduce_trace

events = [{"step": "a"}] * 10 + [{"step": "b"}] * 10 + [{"step": "c"}]
reduced = reduce_trace(events)
payload = {
    "baseline_events": len(events),
    "reduced_events": len(reduced),
    "reduction_ratio": round(1 - (len(reduced) / len(events)), 4),
    "expected_reduced_events": 3,
    "meets_reduction_target": len(reduced) == 3,
}
print(json.dumps(payload))
raise SystemExit(0 if payload["meets_reduction_target"] else 1)
'''


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def _sandbox(root: Path) -> Path:
    repo = root / "sandbox"
    (repo / "tracelite").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts").mkdir()
    (repo / ".gitignore").write_text(
        "__pycache__/\n.pytest_cache/\n.opencode/\n.cocoder/\n", encoding="utf-8"
    )
    (repo / "tracelite" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "tracelite" / "reduce.py").write_text(
        "def reduce_trace(events):\n    return list(events)\n", encoding="utf-8"
    )
    (repo / "tests" / "test_reduce.py").write_text(TESTS, encoding="utf-8")
    (repo / "scripts" / "measure.py").write_text(MEASURE, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        "baseline",
    )
    return repo


def _brightness_sandbox(root: Path) -> Path:
    repo = root / "brightness-sandbox"
    (repo / "brightness").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts").mkdir()
    (repo / "fixtures").mkdir()
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (repo / "brightness" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "brightness" / "analyze.py").write_text(
        "def analyze_frames(paths):\n    return [{'width': 2, 'height': 2, 'mean': 0.0, 'max': 0} for _p in paths]\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_analyze.py").write_text(
        "from brightness.analyze import analyze_frames\n"
        "def test_means():\n    assert [x['mean'] for x in analyze_frames(['a','b'])] == [0.0, 128.0]\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "measure.py").write_text("print('{}')\n", encoding="utf-8")
    for index, value in enumerate((0, 128, 255)):
        (repo / "fixtures" / f"frame{index}.gray").write_bytes(bytes([value]) * 4)
    (repo / "evidence.json").write_text(
        json.dumps(
            {
                "schema": "mc11.fixture-evidence.v1",
                "id": "brightness-fixture-v1",
                "title": "Synthetic brightness progression",
                "intention": "Measure brightness without altering media.",
                "expected": {"means": [0.0, 128.0, 255.0], "max": [0, 128, 255], "monotonic": True},
                "uncertainty": ["Synthetic fixture only."],
            }
        ),
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-q",
        "-m",
        "baseline brightness",
    )
    return repo


def _settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        repo_root=Path("C:/Projects/mission"),
        data_dir=tmp_path / "data",
        config_dir=Path("C:/Projects/mission/config"),
        frontend_dist=tmp_path / "dist",
    )


def _seed_next(session, external_id: str = "opp-1") -> str:
    upsert_resources(
        session,
        "next",
        [
            ResourceSeed(
                resource_type="next_opportunity",
                external_id=external_id,
                title="TraceLite: Efficient Trace Reduction",
                summary="A bounded proxy candidate.",
                state="NEW",
                evidence=["next:fixture"],
                data={
                    "queue_type": "validated",
                    "what_discovered": "Repeated trace events can be compacted.",
                    "simplest_experiment": "Reduce consecutive duplicate events.",
                    "falsification": "No reduction.",
                },
            )
        ],
    )
    return session.query(IntegrationRecord).filter_by(external_id=external_id).one().id


class FakeWorker:
    def __init__(
        self,
        output: str | None = None,
        status: str = "AWAITING_ACCEPTANCE",
        delay: float = 0.0,
    ) -> None:
        self.calls = 0
        self.delay = delay
        self.output = output or json.dumps(
            {
                "schema": "mc10.patch.v1",
                "files": [{"path": "tracelite/reduce.py", "content": CORRECT_CODE}],
                "summary": "Implemented duplicate compaction.",
                "expected_result": "tests pass",
            }
        )
        self.status = status

    async def run(self, request, timeout_seconds):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return {
            "schema": "worker.work-result.v1",
            "request_id": f"wrq_test_{self.calls}",
            "status": self.status,
            "output": self.output,
            "execution": {"backend": "direct", "model": "qwen2.5-coder:latest"},
            "message": "fixture worker",
        }


class FakeWorkWorker:
    """Fixture for the canonical Worker opencode-work result shape."""

    def __init__(
        self,
        *,
        status: str = "ACCEPTED",
        acceptance_outcome: str = "ACCEPTED",
        include_acceptance: bool = True,
        include_ids: bool = True,
        output: str = CORRECT_CODE,
    ) -> None:
        self.status = status
        self.acceptance_outcome = acceptance_outcome
        self.include_acceptance = include_acceptance
        self.include_ids = include_ids
        self.output = output
        self.calls = 0
        self.request: dict | None = None

    async def run(self, request, timeout_seconds):
        self.calls += 1
        self.request = request
        response = (
            Path(request["workspace"]["root"])
            / request["parameters"]["response_artifact_path"]
        )
        response.parent.mkdir(parents=True, exist_ok=True)
        response.write_text(self.output, encoding="utf-8")
        acceptance = (
            {
                "schema": "opencode.acceptance.v1",
                "acceptance_id": "ac_fixture" if self.include_ids else None,
                "work_id": "wk_fixture" if self.include_ids else None,
                "run_id": "wr_fixture" if self.include_ids else None,
                "outcome": self.acceptance_outcome,
                "reason": "fixture acceptance",
                "checks": [],
                "proof_id": "pf_fixture" if self.include_ids else None,
            }
            if self.include_acceptance
            else {}
        )
        work = {
            "schema": "opencode.work.v1",
            "work_id": "wk_fixture" if self.include_ids else None,
            "work_version": 1,
        }
        run = {
            "schema": "opencode.work.run.v1",
            "run_id": "wr_fixture" if self.include_ids else None,
            "state": "AWAITING_ACCEPTANCE",
            "ops": [],
            "unresolved": [],
        }
        return {
            "schema": "worker.work-result.v1",
            "request_id": "wrq_work_fixture" if self.include_ids else None,
            "work_id": work["work_id"],
            "run_id": run["run_id"],
            "acceptance_id": acceptance.get("acceptance_id"),
            "status": self.status,
            "output": {
                "work": work,
                "run": run,
                **({"acceptance": acceptance} if acceptance else {}),
                "model_execution": {
                    "status": "SUCCEEDED",
                    "execution_id": "model-fixture",
                    "requested": {
                        "route": "default_deepseek_go",
                        "model": "opencode-go/deepseek-v4.1-flash",
                    },
                    "observed": {
                        "provider": "opencode-go",
                        "model": "deepseek-v4.1-flash",
                    },
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            },
            "execution": {
                "backend": "opencode-work",
                "model": "opencode-go/deepseek-v4.1-flash",
            },
            "artifacts": [
                {"id": "ev_fixture", "schema": "opencode.evidence.v1", "kind": "evidence"},
                {"id": "vr_fixture", "schema": "opencode.verification.v1", "kind": "verification"},
                {"id": "pf_fixture", "schema": "opencode.proof.v1", "kind": "proof"},
            ],
            "provenance": {
                "work_id": work["work_id"],
                "worker_request_id": "wrq_work_fixture" if self.include_ids else None,
                "project_id": "fixture-project",
                "edge_record_ids": ["edge_fixture"],
            },
            "message": "fixture work result",
        }


class FakeSandbox:
    """Deterministic stand-in for the Docker boundary in unit tests."""

    def describe(self):
        return {
            "backend": "test-fixture",
            "network": "none",
            "repository_mount": "read-only",
        }

    def run(self, repository: Path, command: list[str], *, timeout_seconds: float):
        trace_file = repository / "tracelite" / "reduce.py"
        is_brightness = not trace_file.exists()
        if is_brightness:
            content = (repository / "brightness" / "analyze.py").read_text(encoding="utf-8")
            correct = "sum(bytes_data)" in content or "sum(data)" in content
        else:
            content = trace_file.read_text(encoding="utf-8")
            correct = "result = []" in content or "reduced = [events[0]]" in content
        if "pytest" in command:
            return SandboxResult(
                exit_code=0 if correct else 1,
                stdout="5 passed" if correct else "2 failed, 3 passed",
                stderr="",
                duration_seconds=0.01,
                backend="test-fixture",
                image="test-fixture",
                limits=self.describe(),
            )
        if is_brightness:
            metrics = {
                "frames": 3,
                "expected_means": [0.0, 128.0, 255.0],
                "observed_means": [0.0, 128.0, 255.0] if correct else [0.0, 0.0, 0.0],
                "expected_max": [0, 128, 255],
                "observed_max": [0, 128, 255] if correct else [0, 0, 0],
                "monotonic": True,
                "within_tolerance": correct,
                "meets_target": correct,
            }
        else:
            metrics = {
                "baseline_events": 21,
                "reduced_events": 3 if correct else 21,
                "reduction_ratio": 0.8571 if correct else 0.0,
                "expected_reduced_events": 3,
                "meets_reduction_target": correct,
            }
        return SandboxResult(
            exit_code=0 if correct else 1,
            stdout=json.dumps(metrics),
            stderr="",
            duration_seconds=0.01,
            backend="test-fixture",
            image="test-fixture",
            limits=self.describe(),
        )


class FakeReviewIntegration:
    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        self.calls = 0

    async def start_action(self, application_id, action_id, parameters, confirm):
        self.calls += 1
        return SimpleNamespace(
            id="exec-review-fixture",
            status="queued",
            artifact_ref=str(self.artifact),
            error=None,
            output="",
        )

    def get_execution(self, execution_id):
        return SimpleNamespace(
            id=execution_id,
            status="succeeded",
            artifact_ref=str(self.artifact),
            error=None,
            output="review complete",
        )


def _review_artifact(path: Path, findings: list[dict] | None = None) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "changed_files": ["tracelite/reduce.py"],
                "findings": findings or [],
            }
        ),
        encoding="utf-8",
    )
    return path


def _service(tmp_path: Path, worker: FakeWorker, artifact: Path):
    settings = _settings(tmp_path)
    settings.ensure_directories()
    database = Database(settings)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, settings)
        record_id = _seed_next(session, "opp-1")
        _seed_next(session, "opp-2")
    export = settings.data_dir / "integrations" / "next" / "next-research-export-v1.json"
    export.parent.mkdir(parents=True)
    opportunities = []
    for external_id in ("opp-1", "opp-2"):
        opportunities.append(
            {
                "id": external_id,
                "title": "TraceLite: Efficient Trace Reduction",
                "status": "NEW",
                "queue_type": "validated",
                "score": 78.0,
                "what_discovered": "Repeated trace events can be compacted.",
                "simplest_experiment": "Reduce consecutive duplicate events.",
                "falsification": "No reduction.",
                "items": [],
                "evidence_gaps": None,
            }
        )
    export.write_text(
        json.dumps(
            {
                "schema": "next-research-export-v1",
                "generated_at": "2026-10-24T00:00:00+00:00",
                "source": {"application": "next", "read_only": True},
                "opportunities": opportunities,
                "runs": [],
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )
    integration = FakeReviewIntegration(artifact)
    service = WorkflowService(
        database,
        settings,
        integration,
        worker_client=worker,
        sandbox_runner=FakeSandbox(),  # type: ignore[arg-type]
    )
    return service, record_id, database


def test_workflow_approval_execution_review_decision_and_idempotency(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorker()
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(record_id)
        assert created.status == "proposed"
        assert created.proposal["scope"] == ["tracelite/reduce.py"]
        assert created.proposal["baseline"]["tests"]["passed"] is False
        assert created.proposal["baseline"]["measurement"]["metrics"]["reduced_events"] == 21
        assert created.language_intention["schema"] == "language.intention.v0"

        with pytest.raises(Exception):
            service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=False)
        approved = service.approve(
            created.id, confirm=True, approved_by="user", scope_acknowledged=True
        )
        assert approved.status == "approved"
        assert approved.approval_hash

        executed = asyncio.run(service.execute(created.id, confirm=True))
        assert executed.status == "executed"
        assert executed.worker_request_id == "wrq_test_1"
        assert executed.measurement["passed"] is True
        assert executed.measurement["comparison"]["after_reduced_events"] == 3
        assert executed.result_commit
        assert _git(sandbox, "show", "--name-only", "--format=", "HEAD").strip() == "tracelite/reduce.py"
        with pytest.raises(Exception, match="completed CoCoder review"):
            service.decide(created.id, decision="accept", reason="too early")

        reviewed = asyncio.run(service.review(created.id))
        assert reviewed.status == "reviewed"
        assert reviewed.adverse_review is False
        assert reviewed.review_summary["findings"] == 0

        decided = service.decide(
            created.id, decision="accept", reason="Deterministic proxy passed."
        )
        assert decided.status == "decided"
        assert decided.final_decision == "accept"

        replay = service.create(record_id)
        assert replay.id == created.id
        replayed_execute = asyncio.run(service.execute(created.id, confirm=True))
        assert replayed_execute.id == created.id
        assert worker.calls == 1

        new_attempt = service.create(record_id, force_new=True)
        assert new_attempt.id != created.id
        assert new_attempt.baseline_commit == created.baseline_commit
        assert _git(sandbox, "rev-parse", "HEAD").strip() == created.baseline_commit
        assert f"mc11-result-{created.id}" in _git(sandbox, "tag", "--list", "mc11-*")
    finally:
        database.dispose()


def test_scope_expansion_and_stale_approval_are_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorker(
        output=json.dumps(
            {
                "schema": "mc10.patch.v1",
                "files": [
                    {"path": "tracelite/reduce.py", "content": CORRECT_CODE},
                    {"path": "tests/test_reduce.py", "content": "malicious"},
                ],
                "summary": "expanded",
                "expected_result": "none",
            }
        )
    )
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(record_id)
        service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=True)
        failed = asyncio.run(service.execute(created.id, confirm=True))
        assert failed.status == "failed"
        assert "exactly one file" in (failed.failure or "")
        assert not (sandbox / "tests" / "test_reduce.py").read_text(encoding="utf-8").startswith("malicious")

        with database.session() as session:
            second_record_id = session.query(IntegrationRecord).filter_by(
                external_id="opp-2"
            ).one().id
        second = service.create(second_record_id)
        service.approve(second.id, confirm=True, approved_by="user", scope_acknowledged=True)
        (sandbox / "README.md").write_text("changed after approval", encoding="utf-8")
        _git(sandbox, "add", "README.md")
        _git(
            sandbox,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            "drift",
        )
        with pytest.raises(Exception, match="stale"):
            asyncio.run(service.execute(second.id, confirm=True))
    finally:
        database.dispose()


BRIGHTNESS_CODE = '''def analyze_frames(paths):
    results = []
    for path in paths:
        with open(path, "rb") as handle:
            data = handle.read()
        results.append({"width": 2, "height": 2, "mean": sum(data) / len(data), "max": max(data)})
    return results
'''


def test_brightness_template_generalises_and_records_language_observation(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _brightness_sandbox(tmp_path)
    monkeypatch.setenv(
        "MC11_SANDBOX_BRIGHTNESS_OBSERVATION_V1", str(sandbox)
    )
    artifact = _review_artifact(tmp_path / "review-brightness.json")
    worker = FakeWorker(
        output=BRIGHTNESS_CODE,
    )
    service, _, database = _service(tmp_path, worker, artifact)
    try:
        created = service.create(None, template="brightness_observation_v1")
        assert created.status == "proposed"
        assert created.template == "brightness_observation_v1"
        assert created.next_external_id == "brightness-fixture-v1"
        assert created.proposal["scope"] == ["brightness/analyze.py"]
        assert created.proposal["baseline"]["tests"]["passed"] is False
        assert created.language_intention["schema"] == "language.intention.v0"

        service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=True)
        executed = asyncio.run(service.execute(created.id, confirm=True))
        assert executed.status == "executed"
        assert executed.measurement["passed"] is True
        assert executed.measurement["comparison"]["observed_means"] == [0.0, 128.0, 255.0]
        assert len(executed.language_observations) == 1
        observation = executed.language_observations[0]
        assert observation.schema_name == "language.observation.v1"
        assert observation.constraint_result == "pass"
        assert {item["id"] for item in observation.properties} == {
            "mean_brightness",
            "max_brightness",
            "monotonic_progression",
        }

        reviewed = asyncio.run(service.review(created.id))
        assert reviewed.status == "reviewed"
        decided = service.decide(
            created.id, decision="accept", reason="Fixture measurement passed."
        )
        assert decided.final_decision == "accept"
        associated = service.associate_project(created.id, "language")
        assert associated.project_id == "language"
        timeline = service.project_timeline("language")
        assert any(
            workflow.id == created.id for workflow in timeline["workflows"]
        )
        assert len(timeline["observations"]) >= 1
    finally:
        database.dispose()


def test_modified_approved_file_is_rejected_before_worker(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorker()
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(record_id)
        service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=True)
        (sandbox / "tracelite" / "reduce.py").write_text(
            "def reduce_trace(events):\n    return events\n", encoding="utf-8"
        )
        with pytest.raises(Exception, match="approved file changed"):
            asyncio.run(service.execute(created.id, confirm=True))
        assert worker.calls == 0
    finally:
        database.dispose()


def test_cancellation_is_truthful_at_the_next_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorker(delay=0.25)
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(record_id)
        service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=True)

        async def scenario():
            task = asyncio.create_task(service.execute(created.id, confirm=True))
            await asyncio.sleep(0.08)
            service.cancel(created.id, "Stop the experiment")
            return await task

        result = asyncio.run(scenario())
        assert result.status == "cancelled"
        assert result.cancel_requested is True
        assert result.cancelled_at
        assert any(event.event_type == "cancelled" for event in result.events)
        assert worker.calls == 1
        assert _git(sandbox, "status", "--porcelain").strip() == ""
        assert _git(sandbox, "rev-parse", "HEAD").strip() == created.baseline_commit
    finally:
        database.dispose()


def test_duplicate_execute_command_is_rejected_while_active(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorker(delay=0.2)
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(record_id)
        service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=True)

        async def scenario():
            first = asyncio.create_task(service.execute(created.id, confirm=True))
            await asyncio.sleep(0.05)
            with pytest.raises(Exception, match="already executing"):
                await service.execute(created.id, confirm=True)
            return await first

        result = asyncio.run(scenario())
        assert result.status == "executed"
        assert worker.calls == 1
    finally:
        database.dispose()


def test_adverse_review_blocks_automatic_accept_until_override(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(
        tmp_path / "review-adverse.json",
        [
            {
                "finding_id": "F-high",
                "severity": "high",
                "title": "Exception handling widened",
                "statement": "A broad exception boundary.",
            }
        ],
    )
    worker = FakeWorker()
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(record_id)
        service.approve(created.id, confirm=True, approved_by="user", scope_acknowledged=True)
        asyncio.run(service.execute(created.id, confirm=True))
        reviewed = asyncio.run(service.review(created.id))
        assert reviewed.adverse_review is True
        with pytest.raises(Exception):
            service.decide(created.id, decision="accept", reason="looks fine")
        overridden = service.decide(
            created.id,
            decision="accept",
            reason="Human explicitly accepts the known finding.",
            override_adverse=True,
        )
        assert overridden.final_decision == "accept"
        assert overridden.override_adverse is True
    finally:
        database.dispose()

def test_opencode_work_backend_preserves_authoritative_ids_and_acceptance(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorkWorker()
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(
            record_id,
            worker_backend="opencode-work",
            worker_model="default_deepseek_go",
            worker_timeout_seconds=120,
        )
        assert created.proposal["worker"]["backend"] == "opencode-work"
        assert created.proposal["worker"]["model"] == "default_deepseek_go"
        assert created.proposal["worker"]["policy"] == "default"
        assert created.proposal["worker"]["response_artifact_path"] == (
            ".opencode/mc-worker-response.txt"
        )
        assert created.proposal["worker"]["success"][0]["check"]["type"] == "file_exists"
        assert worker.calls == 0

        with pytest.raises(Exception, match="status proposed"):
            asyncio.run(service.execute(created.id, confirm=True))
        assert worker.calls == 0

        service.approve(
            created.id, confirm=True, approved_by="integration-test", scope_acknowledged=True
        )
        executed = asyncio.run(service.execute(created.id, confirm=True))
        assert executed.status == "executed"
        assert executed.worker_request_id == "wrq_work_fixture"
        assert executed.worker_work_id == "wk_fixture"
        assert executed.worker_run_id == "wr_fixture"
        assert executed.worker_acceptance_id == "ac_fixture"
        assert executed.worker_acceptance_outcome == "ACCEPTED"
        assert executed.worker_result["work"]["acceptance"]["outcome"] == "ACCEPTED"
        assert executed.worker_result["artifacts"][0]["id"] == "ev_fixture"
        assert executed.worker_result["provenance"]["edge_record_ids"] == ["edge_fixture"]
        assert executed.worker_result["model_execution"]["observed"]["model"] == "deepseek-v4.1-flash"
        assert worker.calls == 1
        request = worker.request
        assert request is not None
        assert request["execution"] == {
            "backend": "opencode-work",
            "model": "default_deepseek_go",
            "policy": "default",
        }
        assert request["metadata"]["correlation_id"] == created.id
        assert request["metadata"]["workflow_id"] == created.id
        assert request["success"][0]["check"] == {
            "type": "file_exists",
            "path": ".opencode/mc-worker-response.txt",
        }
        assert request["options"] == {"acceptance": "automatic"}
        assert not (sandbox / ".opencode" / "mc-worker-response.txt").exists()
    finally:
        database.dispose()


def test_opencode_work_rejection_is_not_parsed_as_a_patch(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorkWorker(
        status="REJECTED",
        acceptance_outcome="REJECTED",
        output="not a patch",
    )
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(
            record_id, worker_backend="opencode-work", force_new=True
        )
        service.approve(
            created.id, confirm=True, approved_by="integration-test", scope_acknowledged=True
        )
        failed = asyncio.run(service.execute(created.id, confirm=True))
        assert failed.status == "failed"
        assert "WORK_ACCEPTANCE_REJECTED" in (failed.failure or "")
        assert failed.worker_work_id == "wk_fixture"
        assert failed.worker_acceptance_outcome == "REJECTED"
        assert failed.patch == {}
        assert "return list(events)" in (sandbox / "tracelite" / "reduce.py").read_text(
            encoding="utf-8"
        )
    finally:
        database.dispose()


def test_opencode_work_acceptance_without_ids_is_blocked_not_fabricated(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorkWorker(
        status="ACCEPTED",
        acceptance_outcome="ACCEPTED",
        include_acceptance=False,
        include_ids=False,
    )
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(
            record_id, worker_backend="opencode-work", force_new=True
        )
        service.approve(
            created.id, confirm=True, approved_by="integration-test", scope_acknowledged=True
        )
        failed = asyncio.run(service.execute(created.id, confirm=True))
        assert failed.status == "failed"
        assert "WORK_ACCEPTANCE_MISSING" in (failed.failure or "")
        assert failed.worker_request_id is None
        assert failed.worker_work_id is None
        assert failed.worker_run_id is None
        assert failed.worker_acceptance_id is None
        assert failed.worker_result["work"]["work_id"] is None
    finally:
        database.dispose()


def test_opencode_work_unavailable_is_explicit_and_not_retried(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")

    class UnavailableWorker:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, request, timeout_seconds):
            self.calls += 1
            raise WorkerRequestError(
                "WORKER_UNAVAILABLE", "Worker is not reachable at fixture"
            )

    worker = UnavailableWorker()
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(
            record_id, worker_backend="opencode-work", force_new=True
        )
        service.approve(
            created.id, confirm=True, approved_by="integration-test", scope_acknowledged=True
        )
        failed = asyncio.run(service.execute(created.id, confirm=True))
        assert failed.status == "failed"
        assert failed.worker_status == "WORKER_UNAVAILABLE"
        assert failed.worker_request_id is None
        assert failed.worker_work_id is None
        assert failed.worker_result["availability"]["worker_result_available"] is False
        assert "WORKER_UNAVAILABLE" in (failed.failure or "")
        assert worker.calls == 1
        assert any(event.event_type == "worker_unavailable" for event in failed.events)
    finally:
        database.dispose()

def test_opencode_work_timeout_is_classified_without_a_verdict(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")

    class TimeoutWorker:
        async def run(self, request, timeout_seconds):
            raise WorkerRequestError(
                "WORKER_TIMEOUT", "Worker did not respond within fixture seconds"
            )

    service, record_id, database = _service(tmp_path, TimeoutWorker(), artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        created = service.create(
            record_id, worker_backend="opencode-work", force_new=True
        )
        service.approve(
            created.id, confirm=True, approved_by="integration-test", scope_acknowledged=True
        )
        failed = asyncio.run(service.execute(created.id, confirm=True))
        assert failed.status == "failed"
        assert failed.worker_status == "WORKER_TIMEOUT"
        assert failed.worker_acceptance_id is None
        assert failed.worker_acceptance_outcome is None
        assert failed.worker_result["availability"]["worker_result_available"] is False
    finally:
        database.dispose()

def test_custom_worker_success_is_approved_and_forwarded(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    worker = FakeWorkWorker(
        status="REJECTED",
        acceptance_outcome="REJECTED",
    )
    service, record_id, database = _service(tmp_path, worker, artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    custom = [
        {
            "id": "exact-response",
            "description": "response must match the declared value",
            "check": {
                "type": "file_content_equals",
                "path": ".opencode/mc-worker-response.txt",
                "value": "declared-value-that-does-not-match",
            },
        }
    ]
    try:
        created = service.create(
            record_id,
            worker_backend="opencode-work",
            worker_success=custom,
            force_new=True,
        )
        assert created.proposal["worker"]["success"] == custom
        service.approve(
            created.id, confirm=True, approved_by="integration-test", scope_acknowledged=True
        )
        failed = asyncio.run(service.execute(created.id, confirm=True))
        assert failed.status == "failed"
        assert "WORK_ACCEPTANCE_REJECTED" in (failed.failure or "")
        assert worker.request is not None
        assert worker.request["success"] == custom
    finally:
        database.dispose()


def test_worker_success_rejects_paths_outside_the_workspace(
    tmp_path: Path, monkeypatch
) -> None:
    sandbox = _sandbox(tmp_path)
    monkeypatch.setenv("MC10_SANDBOX", str(sandbox))
    artifact = _review_artifact(tmp_path / "review.json")
    service, record_id, database = _service(tmp_path, FakeWorkWorker(), artifact)
    monkeypatch.setenv(
        "MC10_NEXT_EXPORT",
        str(_settings(tmp_path).data_dir / "integrations" / "next" / "next-research-export-v1.json"),
    )
    try:
        with pytest.raises(Exception, match="stay inside"):
            service.create(
                record_id,
                worker_backend="opencode-work",
                worker_success=[
                    {
                        "description": "escape",
                        "check": {
                            "type": "file_exists",
                            "path": "../outside.txt",
                        },
                    }
                ],
            )
    finally:
        database.dispose()
