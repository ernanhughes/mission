"""MC-PROJECTS-QUALITY-02: rubric, charter, evidence, evaluation, findings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.models import (
    Project,
    ProjectRepository,
    Repository,
    Setting,
    SoftwareEvaluation,
    SoftwareFinding,
)
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import repository_id, seed_defaults
from mission_control.quality_software import rubric as _rubric
from mission_control.quality_software import service as _service


def _database(runtime: RuntimeSettings) -> Database:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    return database


def _repo_dir(base: Path, name: str, *, readme: str = "# Tool\nA useful tool.\n") -> Path:
    repo = base / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text(readme, encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='tool'\n", encoding="utf-8")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_main.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (repo / "node_modules").mkdir(exist_ok=True)
    (repo / "node_modules" / "junk.js").write_text("x" * 100, encoding="utf-8")
    return repo


def _project_with_repo(session, path: Path, *, classification: str = "executable_application") -> str:
    project = Project(
        id="sw-tool", name="tool", description="A useful tool.", kind="supporting",
        status="active", origin="auto-discovered", created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    session.add(project)
    repo = Repository(
        id=repository_id(str(path)), path=str(path), name=path.name,
        classification=classification, confidence=0.8, evidence=["fixture"],
        source_root=str(path.parent), is_git=False, accessible=True, candidate=False,
        first_seen_at="2026-01-01T00:00:00+00:00", last_observed_at="2026-01-02T00:00:00+00:00",
    )
    session.add(repo)
    session.flush()
    session.add(ProjectRepository(project_id="sw-tool", repository_id=repo.id, role="primary"))
    session.flush()
    return "sw-tool"


def _assessed(weight: int, score: int, refs: list[str]) -> dict:
    return {
        "state": "assessed", "score": score, "confidence": 0.8,
        "rationale": "cited evidence", "positives": ["good"], "findings": [],
        "assumptions": [], "unknowns": [], "evidence_refs": refs,
    }


def _full_assessed(refs: list[str], score_fn=None) -> dict:
    out = {}
    for dim in _rubric.DIMENSIONS:
        score = score_fn(dim) if score_fn else dim["weight"] // 2
        out[dim["id"]] = _assessed(dim["weight"], score, refs)
    return out


# ------------------------------------------------------------------- rubric


def test_rubric_totals_1000_with_documented_weights() -> None:
    assert _rubric.TOTAL_WEIGHT == 1000
    assert {d["id"] for d in _rubric.DIMENSIONS} == {
        "purpose", "correctness", "testing", "architecture", "maintainability",
        "security", "operations", "documentation", "usage", "delivery",
    }


def test_aggregate_requires_purpose_correctness_and_coverage() -> None:
    refs = ["repo:/x"]
    dims = _full_assessed(refs)
    assert _rubric.aggregate(dims)["valid"] is True
    assert _rubric.aggregate(dims)["overall"] is not None

    abstained = _full_assessed(refs)
    abstained["purpose"] = {**_assessed(150, 0, refs), "state": "abstained", "score": None}
    assert _rubric.aggregate(abstained)["overall"] is None

    sparse = _full_assessed(refs)
    for dim_id in ("testing", "architecture", "maintainability"):
        sparse[dim_id] = {"state": "abstained", "score": None, "confidence": 0.0,
                          "rationale": "no evidence", "positives": [], "assumptions": [],
                          "unknowns": ["unknown"], "evidence_refs": []}
    assert _rubric.aggregate(sparse)["overall"] is None  # 7 assessed < 8


def test_aggregate_excludes_na_from_denominator() -> None:
    refs = ["repo:/x"]
    dims = _full_assessed(refs)
    dims["usage"] = {"state": "na", "score": None, "confidence": 0.0,
                     "rationale": "standalone CLI", "positives": [], "assumptions": [],
                     "unknowns": [], "na_reason": "no ecosystem integration surface",
                     "evidence_refs": []}
    stats = _rubric.aggregate(dims)
    assert stats["valid"] is True
    assert stats["max_attainable"] == 950
    assert stats["overall"] is not None and stats["overall"] <= 950


def test_validation_rejects_contract_violations() -> None:
    refs = {"repo:/x"}
    dims = _full_assessed(["repo:/x"])
    del dims["security"]
    with pytest.raises(_rubric.RubricProblem):
        _rubric.validate_dimensions(dims, refs)
    dims = _full_assessed(["repo:/x"])
    dims["security"]["score"] = 9999
    with pytest.raises(_rubric.RubricProblem):
        _rubric.validate_dimensions(dims, refs)
    dims = _full_assessed(["repo:/x"])
    dims["security"]["evidence_refs"] = ["nope:missing"]
    with pytest.raises(_rubric.RubricProblem):
        _rubric.validate_dimensions(dims, refs)
    dims = _full_assessed(["repo:/x"])
    dims["security"]["rationale"] = ""
    with pytest.raises(_rubric.RubricProblem):
        _rubric.validate_dimensions(dims, refs)


# ------------------------------------------------------------------ charter


def test_charter_draft_confirm_supersede(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            _project_with_repo(session, repo)
            draft = _service.create_charter(session, "sw-tool", {"purpose": "v1"})
            assert draft.status == "draft" and draft.revision == 1
            confirmed = _service.confirm_charter(session, draft.id)
            assert confirmed.status == "confirmed"
            second = _service.create_charter(session, "sw-tool", {"purpose": "v2"})
            assert second.revision == 2 and second.supersedes == draft.id
            _service.confirm_charter(session, second.id)
            assert session.get(_service.SoftwareCharter, draft.id).status == "archived"
            current = _service.current_charter(session, "sw-tool")
            assert current["revision"] == 2 and current["status"] == "confirmed"
    finally:
        database.dispose()


def test_propose_charter_is_unconfirmed(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            _project_with_repo(session, repo)
            draft = _service.propose_charter(session, "sw-tool")
            assert draft["status"] == "draft"
            assert "UNCONFIRMED" in draft["note"]
            assert _service.current_charter(session, "sw-tool") is None
    finally:
        database.dispose()


# ------------------------------------------------------------------ evidence


def test_evidence_bounded_redacted_fingerprinted(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool", readme="# Tool\npassword = hunter2-secret\n")
            _project_with_repo(session, repo)
            (repo / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
            from mission_control.quality_software.evidence import collect_evidence

            manifest = collect_evidence(session, "sw-tool", inspect_dir=None)
        assert manifest["contract"] == "software-evidence-v1"
        assert "hunter2" not in json.dumps(manifest)
        assert manifest["docs"].get("agents_present") is True
        assert not any("node_modules" in f["path"] for f in manifest["files"])
        assert manifest["tests"]["files"] >= 1
        assert manifest["fingerprint"]
        ids = {item["id"] for item in manifest["evidence"]}
        assert "repo:" + str(repo).replace("\\", "/") in ids and "doc:README.md" in ids
        with database.session() as session:
            from mission_control.quality_software.evidence import collect_evidence as collect

            again = collect(session, "sw-tool", inspect_dir=None)
        assert again["fingerprint"] == manifest["fingerprint"]
    finally:
        database.dispose()


def test_evidence_rejects_book_projects(runtime: RuntimeSettings) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            from mission_control.quality_software.evidence import collect_evidence

            with pytest.raises(ValueError):
                collect_evidence(session, "language", inspect_dir=None)
    finally:
        database.dispose()


# --------------------------------------------------------------- evaluation


def _model_dim_document(dim_id: str, ref: str) -> dict:
    dim = next(d for d in _rubric.DIMENSIONS if d["id"] == dim_id)
    doc = {
        "state": "assessed",
        "score": dim["weight"] // 2,
        "confidence": 0.8,
        "rationale": "cited evidence",
        "positives": ["good"],
        "findings": [],
        "assumptions": [],
        "unknowns": [],
        "evidence_refs": [ref],
    }
    if dim_id == "correctness":
        doc["findings"] = [{
            "severity": "high", "component": "src/main.py", "title": "Unchecked edge",
            "expected": "handles empty input", "observed": "crashes on empty input",
            "impact": "reliability", "proposal": "guard clause", "verification": "unit test",
            "evidence_refs": [ref],
        }]
    return doc


def test_request_duplicate_guard_and_force(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            _project_with_repo(session, repo)
            first = _service.request_evaluation(session, "sw-tool", model="m", inspect_dir=None)
            second = _service.request_evaluation(session, "sw-tool", model="m", inspect_dir=None)
            assert first.id == second.id
            third = _service.request_evaluation(session, "sw-tool", model="m", force=True, inspect_dir=None)
            assert third.id != first.id
            assert third.previous_evaluation_id == second.id
    finally:
        database.dispose()


def test_execute_persists_scores_and_dedupes_findings(runtime: RuntimeSettings, tmp_path: Path, monkeypatch) -> None:
    import mission_control.research.inference as inference

    async def fake_complete(session, *, model, messages, route=None):
        import re as _re

        text = messages[1]["content"]
        assert "software-eval-v1" in text
        match = _re.search(r'"dimension"\s*:\s*\{\s*"id"\s*:\s*"([a-z_]+)"', text)
        dim_id = match.group(1) if match else "purpose"
        ids = sorted({m.group(1) for m in _re.finditer(r'"id"\s*:\s*"([^"]+)"', text) if "/" in m.group(1) or ":" in m.group(1)})
        ref = ids[0] if ids else "repo:/x"
        return {"content": json.dumps(_model_dim_document(dim_id, ref)), "model": model, "route": route or "local", "usage": {}}

    monkeypatch.setattr(inference, "complete_chat", fake_complete)
    monkeypatch.setattr(inference, "resolve_model", lambda session, requested: ("m", "local"))
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
        with database.session() as session:
            row = _service.request_evaluation(session, pid, model="m", inspect_dir=None)
            evaluation_id = row.id
        import asyncio

        service = _service.SoftwareQualityService(database)
        asyncio.run(service.execute_evaluation(evaluation_id))
        with database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            assert row.status == "completed"
            assert row.overall is not None and row.overall <= 1000
            assert row.observed_model == "m"
            findings = session.scalars(select(SoftwareFinding)).all()
            assert len(findings) == 1
            assert findings[0].severity == "high"
            # Re-extracting the same evaluation is idempotent.
            service._extract_findings(session, evaluation_id)
            assert len(session.scalars(select(SoftwareFinding)).all()) == 1
    finally:
        database.dispose()


def test_execute_rejects_malformed_output(runtime: RuntimeSettings, tmp_path: Path, monkeypatch) -> None:
    import mission_control.research.inference as inference

    async def fake_complete(session, *, model, messages, route=None):
        return {"content": "Great code! 10/10, ship it.", "model": model, "route": "local", "usage": {}}

    monkeypatch.setattr(inference, "complete_chat", fake_complete)
    monkeypatch.setattr(inference, "resolve_model", lambda session, requested: ("m", "local"))
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
        with database.session() as session:
            evaluation_id = _service.request_evaluation(session, pid, model="m", inspect_dir=None).id
        import asyncio

        asyncio.run(_service.SoftwareQualityService(database).execute_evaluation(evaluation_id))
        with database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            assert row.status == "failed"
            assert row.overall is None
            assert "contract violation" in (row.error or "")
    finally:
        database.dispose()


def test_execute_blocked_without_ai(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        # Pin the denied state explicitly: seed defaults ship AI-on, so the
        # blocked path must be tested by disabling AI, not ambient defaults.
        with database.session() as session:
            setting = session.get(Setting, "ai")
            assert setting is not None and isinstance(setting.value, dict)
            setting.value = {**setting.value, "enabled": False, "consent": False}
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
        with database.session() as session:
            evaluation_id = _service.request_evaluation(session, pid, model="", inspect_dir=None).id
        import asyncio

        asyncio.run(_service.SoftwareQualityService(database).execute_evaluation(evaluation_id))
        with database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            assert row.status == "blocked"
            assert row.overall is None
    finally:
        database.dispose()


# ------------------------------------------------------------------ reviews


def _completed_eval(session, project_id: str) -> str:
    """Persist a finished evaluation with validated dimensions (no model calls)."""
    from mission_control.quality_software.rubric import aggregate, validate_dimensions

    row = _service.request_evaluation(session, project_id, model="m", inspect_dir=None)
    manifest = row.evidence_manifest
    ids = {item.get("id", "") for item in manifest.get("evidence", [])} - {""}
    assert ids, "manifest has no evidence ids"
    ref = sorted(ids)[0]
    dims = {dim["id"]: _model_dim_document(dim["id"], ref) for dim in _rubric.DIMENSIONS}
    row.dimensions = validate_dimensions(dims, ids)
    row.status = "completed"
    stats = aggregate(row.dimensions)
    row.overall = stats["overall"]
    row.max_attainable = stats["max_attainable"]
    row.coverage_percent = stats["coverage_percent"]
    row.uncertainty = "limited history"
    row.limitations = ["no live run"]
    row.completed_at = "2026-01-03T00:00:00+00:00"
    session.flush()
    return row.id


def test_prompt_package_stays_within_windows_argv_limit(runtime: RuntimeSettings, tmp_path: Path) -> None:
    import json as _json

    from mission_control.quality_software.evidence import build_compact_evidence, fit_package
    from mission_control.quality_software.service import _build_dimension_prompts

    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            # Bloated tree: many files plus a big README.
            for index in range(300):
                (repo / f"mod_{index:03d}.py").write_text("x = 1\n", encoding="utf-8")
            (repo / "README.md").write_text("# Tool\n" + ("lorem ipsum dolor sit amet. " * 500), encoding="utf-8")
            pid = _project_with_repo(session, repo)
            row = _service.request_evaluation(session, pid, model="m", inspect_dir=None)
            compact = build_compact_evidence(dict(row.evidence_manifest))
            package = {"evidence": compact}
            fitted = fit_package(package)
            assert len(_json.dumps(fitted)) <= 26000
            calls = _build_dimension_prompts(dict(row.evidence_manifest), None)
            assert len(calls) == 10
            for call in calls:
                assert len(call["prompt"]) <= 7500, call["dimension"]
                assert call["evidence_ids"], call["dimension"]
    finally:
        database.dispose()


def test_freshness_goes_stale_on_new_evidence_and_charter(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            charter = _service.create_charter(session, pid, {"purpose": "v1"})
            _service.confirm_charter(session, charter.id)
            evaluation_id = _completed_eval(session, pid)
            from mission_control.quality_software.service import evaluation_freshness, get_evaluation

            assert evaluation_freshness(session, get_evaluation(session, evaluation_id))["state"] == "current"
            # New file changes the evidence fingerprint.
            (repo / "extra.py").write_text("x = 1\n", encoding="utf-8")
            stale = evaluation_freshness(session, get_evaluation(session, evaluation_id))
            assert stale["state"] == "stale"
            # Charter revision change is flagged even when evidence is unchanged.
            _service.create_charter(session, pid, {"purpose": "v2"})
            with_charter = evaluation_freshness(session, get_evaluation(session, evaluation_id))
            assert any("charter" in reason for reason in with_charter["reasons"])
    finally:
        database.dispose()


def test_independent_review_agree_disagree(runtime: RuntimeSettings, tmp_path: Path, monkeypatch) -> None:
    import mission_control.research.inference as inference

    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            evaluation_id = _completed_eval(session, pid)
            row = session.get(SoftwareEvaluation, evaluation_id)
            row.observed_model = "m"
            session.flush()
            service = _service.SoftwareQualityService(database)
            service._extract_findings(session, evaluation_id)
            finding = session.scalars(select(SoftwareFinding)).one()
            finding_id = finding.id
            _service.review_finding(session, finding_id, decision="ACCEPT", reason="owner agrees")
            review = service.request_eval_review(session, evaluation_id, model="other")
            review_id = review.id
            session.flush()

        async def fake_review(session, *, model, messages, route=None):
            assert "software-review-v1" in messages[1]["content"]
            return {"content": json.dumps({
                "verdict": "partial",
                "rationale": "evidence supports most claims",
                "finding_verdicts": [{"finding_id": finding_id, "verdict": "agree", "rationale": "cited"}],
            }), "model": model, "route": "local", "usage": {}}

        monkeypatch.setattr(inference, "complete_chat", fake_review)
        monkeypatch.setattr(inference, "resolve_model", lambda session, requested: ("reviewer", "local"))
        import asyncio

        asyncio.run(_service.SoftwareQualityService(database).execute_eval_review(review_id))
        with database.session() as session:
            from mission_control.models import SoftwareEvalReview

            stored = session.get(SoftwareEvalReview, review_id)
            assert stored.status == "completed" and stored.verdict == "partial"
            assert stored.finding_verdicts[0]["finding_id"] == finding_id
            # High severity + owner ACCEPT + independent agree => verified.
            assert _service.finding_verified(session, session.get(SoftwareFinding, finding_id)) is True
            from mission_control.cultivation.service import create_goal

            create_goal(session, {"id": "g-software", "name": "Software", "category": "software",
                                  "target_value": 10, "measurement_type": "count",
                                  "qualifying_stage": "published"})
            _service.resolve_finding(session, finding_id, ["tests/test_main.py"])
            _service.confirm_resolution(session, finding_id, note="tests pass")
            assert session.get(SoftwareFinding, finding_id).status == "resolved"
            result = _service.report_progress(
                session, project_id=pid, goal_id="g-software", finding_id=finding_id)
            assert result["verified"] is True
    finally:
        database.dispose()


def test_same_model_review_rejected(runtime: RuntimeSettings, tmp_path: Path, monkeypatch) -> None:
    import mission_control.research.inference as inference

    async def fail(session, *, model, messages, route=None):
        raise AssertionError("must not call the model for identical-model review")

    monkeypatch.setattr(inference, "complete_chat", fail)
    monkeypatch.setattr(inference, "resolve_model", lambda session, requested: ("m", "local"))
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            evaluation_id = _completed_eval(session, pid)
            review = _service.SoftwareQualityService(database).request_eval_review(session, evaluation_id, model="m")
            session.flush()
            review_id = review.id
        with database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            row.observed_model = "m"
            session.flush()
        import asyncio

        asyncio.run(_service.SoftwareQualityService(database).execute_eval_review(review_id))
        with database.session() as session:
            from mission_control.models import SoftwareEvalReview

            stored = session.get(SoftwareEvalReview, review_id)
            assert stored.status == "failed"
            assert "different model" in (stored.error or "")
    finally:
        database.dispose()


# ------------------------------------------------------------------ findings


def test_finding_lifecycle_gates(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            evaluation_id = _completed_eval(session, pid)
            _service.SoftwareQualityService(database)._extract_findings(session, evaluation_id)
            finding = session.scalars(select(SoftwareFinding)).one()
            assert finding.status == "proposed"
            with pytest.raises(Exception):
                _service.resolve_finding(session, finding.id, ["x"])
            _service.review_finding(session, finding.id, decision="ACCEPT", reason="confirmed")
            assert session.get(SoftwareFinding, finding.id).status == "accepted"
            # High severity needs independent corroboration: owner ACCEPT alone is not verified.
            assert _service.finding_verified(session, session.get(SoftwareFinding, finding.id)) is False
            _service.start_finding_work(session, finding.id)
            with pytest.raises(Exception):
                _service.confirm_resolution(session, finding.id)
            _service.resolve_finding(session, finding.id, ["tests/test_main.py"])
            assert session.get(SoftwareFinding, finding.id).status == "needs_verification"
            _service.confirm_resolution(session, finding.id, note="tests pass")
            assert session.get(SoftwareFinding, finding.id).status == "resolved"
            _service.reopen_finding(session, finding.id, reason="regressed")
            assert session.get(SoftwareFinding, finding.id).status == "reopened"
    finally:
        database.dispose()


def test_high_severity_needs_independent_agree(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            evaluation_id = _completed_eval(session, pid)
            _service.SoftwareQualityService(database)._extract_findings(session, evaluation_id)
            finding = session.scalars(select(SoftwareFinding)).one()
            assert finding.severity == "high"
            _service.review_finding(session, finding.id, decision="ACCEPT", reason="ok")
            assert _service.finding_verified(session, session.get(SoftwareFinding, finding.id)) is False
    finally:
        database.dispose()


def test_prompt_requires_accepted_findings(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            evaluation_id = _completed_eval(session, pid)
            _service.SoftwareQualityService(database)._extract_findings(session, evaluation_id)
            finding = session.scalars(select(SoftwareFinding)).one()
            with pytest.raises(Exception):
                _service.build_improvement_prompt(session, pid, [finding.id])
            _service.review_finding(session, finding.id, decision="ACCEPT", reason="ok")
            text = _service.build_improvement_prompt(session, pid, [finding.id], scope="batch-1")
            assert "do not fix anything outside this list" in text
            saved = _service.save_prompt(session, pid, [finding.id], "batch-1", text, {"by": "test"})
            assert saved.finding_ids == [finding.id]
            assert len(_service.list_prompts(session, pid)) == 1
    finally:
        database.dispose()


# --------------------------------------------------------------- cultivation


def test_cultivation_refuses_unverified_and_records_verified(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = _database(runtime)
    try:
        with database.session() as session:
            from mission_control.cultivation.service import create_goal

            create_goal(session, {"id": "g-software", "name": "Software", "category": "software",
                                  "target_value": 10, "measurement_type": "count",
                                  "qualifying_stage": "published"})
            repo = _repo_dir(tmp_path, "tool")
            pid = _project_with_repo(session, repo)
            evaluation_id = _completed_eval(session, pid)
            # A bare score is an observation, never verified progress.
            result = _service.report_progress(
                session, project_id=pid, goal_id="g-software", evaluation_id=evaluation_id)
            assert result["verified"] is False
            _service.SoftwareQualityService(database)._extract_findings(session, evaluation_id)
            finding = session.scalars(select(SoftwareFinding)).one()
            with pytest.raises(Exception):
                _service.report_progress(
                    session, project_id=pid, goal_id="g-software", finding_id=finding.id)
            _service.review_finding(session, finding.id, decision="ACCEPT", reason="ok")
            _service.resolve_finding(session, finding.id, ["tests/test_main.py"])
            _service.confirm_resolution(session, finding.id)
            # high severity still needs independent agree
            with pytest.raises(Exception):
                _service.report_progress(
                    session, project_id=pid, goal_id="g-software", finding_id=finding.id)
    finally:
        database.dispose()


# --------------------------------------------------------------------- API


def test_api_charter_evidence_queue_flow(client: TestClient, tmp_path: Path) -> None:
    # Pin the denied state explicitly: seed defaults ship AI-on, so the
    # honest-blocked assertion needs AI disabled, not ambient defaults.
    revoked = client.patch("/api/settings", json={"ai": {"enabled": False, "consent": False}})
    assert revoked.status_code == 200, revoked.text
    repo = _repo_dir(tmp_path, "widget")
    created = client.post("/api/projects", json={
        "name": "Widget", "description": "A widget.", "kind": "supporting",
        "repository_path": str(repo)})
    assert created.status_code == 201, created.text
    pid = created.json()["id"]

    draft = client.post("/api/software-quality/charters/propose", params={"project_id": pid})
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"

    saved = client.post("/api/software-quality/charters", json={
        "project_id": pid, "purpose": "Do widget things.", "users": "owners",
        "capabilities": ["widget"], "interfaces": [], "acceptance": ["works"],
        "non_goals": [], "constraints": [], "lifecycle": "active",
        "dependencies": [], "verification_expectations": "tests pass",
        "evidence_refs": [], "provenance": {}})
    assert saved.status_code == 201, saved.text
    charter_id = saved.json()["id"]

    confirmed = client.post(f"/api/software-quality/charters/{charter_id}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"

    evidence = client.get("/api/software-quality/evidence", params={"project_id": pid})
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["fingerprint"]
    assert "hunter2" not in evidence.text

    requested = client.post("/api/software-quality/evaluations", json={"project_id": pid, "model": ""})
    assert requested.status_code == 201, requested.text
    evaluation_id = requested.json()["id"]

    import time

    deadline = time.time() + 30
    final = None
    while time.time() < deadline:
        current = client.get(f"/api/software-quality/evaluations/{evaluation_id}").json()
        if current["evaluation"]["status"] in {"blocked", "failed", "completed", "partial"}:
            final = current
            break
        time.sleep(0.5)
    assert final is not None, "evaluation never reached a terminal state"
    # No model is configured in tests: honest blocked state, never a fake score.
    assert final["evaluation"]["status"] == "blocked"
    assert final["evaluation"]["overall"] is None
