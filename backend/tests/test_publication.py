"""MC-QUALITY-03D: release gates, preflight adapter, dossier, approval, calibration."""

from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from mission_control.models import TechnicalClaim
from mission_control.persistence.db import Database
from mission_control.publication import policy
from mission_control.publication import service as pub


def _book(tmp_path, chapters: dict[str, str], index: str = "") -> str:
    root = tmp_path / "book"
    root.mkdir(exist_ok=True)
    for name, text in chapters.items():
        (root / name).write_text(text, encoding="utf-8")
    if index:
        (root / "_index.md").write_text(index, encoding="utf-8")
    return str(root)


def _chapter_text(title: str) -> str:
    return f'+++\ntitle = "{title}"\n+++\n\nBody text for {title}.\n'


def _point_project(tmp_path, runtime, book_root: str):
    database = Database(runtime)
    with database.session() as session:
        from mission_control.models import Book
        book = session.query(Book).filter_by(project_id="inference").one_or_none()
        assert book is not None
        book.manuscript_paths = [book_root]
        session.commit()
    return database


def _assess(client: TestClient, **kwargs):
    body = {"project_id": "inference", "technical_scope": "pilot"}
    body.update(kwargs)
    response = client.post("/api/publication/assessments", json=body)
    assert response.status_code == 201, response.text[:400]
    return response.json()


# --- pure policy -----------------------------------------------------------


def _all_pass_results():
    return {g["gate_id"]: policy.PASS for g in policy.GATES}


def test_ready_requires_approval():
    status, _ = policy.derive_readiness(_all_pass_results(), approval_present=True)
    assert status == policy.READY
    status, detail = policy.derive_readiness(_all_pass_results(), approval_present=False)
    assert status == policy.NOT_YET_ASSESSED
    assert "approval" in detail


def test_blocked_on_nonwaivable_fail():
    results = _all_pass_results()
    results["publication_build"] = policy.FAIL
    status, _ = policy.derive_readiness(results, approval_present=True)
    assert status == policy.BLOCKED


def test_unknowns_never_become_ready():
    for state in (policy.NOT_RUN, policy.UNKNOWN, policy.STALE, policy.ERROR):
        results = _all_pass_results()
        results["technical_verification"] = state
        status, _ = policy.derive_readiness(results, approval_present=True)
        assert status == policy.NOT_YET_ASSESSED, state


def test_unwaived_waivable_fail_blocks():
    results = _all_pass_results()
    results["assets_references"] = policy.FAIL
    status, _ = policy.derive_readiness(results, approval_present=True)
    assert status == policy.BLOCKED


def test_accepted_limitation_with_approval_is_qualified_ready():
    results = _all_pass_results()
    results["assets_references"] = policy.WARNING
    status, _ = policy.derive_readiness(results, approval_present=True)
    assert status == policy.READY_WITH_LIMITATIONS


# --- assessment lifecycle --------------------------------------------------


def test_assessment_is_idempotent(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One")})
    _point_project(tmp_path, runtime, root)
    first = _assess(client)
    second = _assess(client)
    assert first["id"] == second["id"]
    assert first["manuscript_fingerprint"] == second["manuscript_fingerprint"]
    third = client.post("/api/publication/assessments?force=true",
                        json={"project_id": "inference"}).json()
    assert third["id"] != first["id"]


def test_index_mismatch_blocks_and_bars_approval(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One")},
                 index="This book has all 99 chapters.\n")
    _point_project(tmp_path, runtime, root)
    report = _assess(client)
    structure = next(g for g in report["gates"] if g["gate_id"] == "chapter_structure")
    assert structure["result"] == "FAIL"
    assert report["assessment_status"] == "BLOCKED"
    bad = client.post("/api/publication/approvals", json={
        "assessment_id": report["id"], "decision": "APPROVE_RELEASE_CANDIDATE"})
    assert bad.status_code in (400, 422)


def test_source_change_marks_assessment_stale(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One")})
    _point_project(tmp_path, runtime, root)
    report = _assess(client)
    assert report["freshness"] == "CURRENT"
    (tmp_path / "book" / "01-chapter.md").write_text(_chapter_text("One, revised"), encoding="utf-8")
    refreshed = client.post(
        f"/api/publication/assessments/{report['id']}/refresh").json()
    assert refreshed["freshness"] == "STALE"


def test_manuscript_untouched_by_assessment(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One"),
                            "02-chapter.md": _chapter_text("Two")})
    _point_project(tmp_path, runtime, root)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (tmp_path / "book").iterdir() if p.is_file()}
    _assess(client)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (tmp_path / "book").iterdir() if p.is_file()}
    assert before == after


def test_history_preserved_by_assessment(client: TestClient, tmp_path, runtime) -> None:
    from mission_control.schemas import TechnicalClaimCreate
    from mission_control.technical import service as tech

    root = _book(tmp_path, {"01-chapter.md": "The engine releases the sequence.\n"})
    database = _point_project(tmp_path, runtime, root)
    path = str(tmp_path / "book" / "01-chapter.md")
    with database.session() as session:
        claim = tech.record_claim(session, TechnicalClaimCreate(
            project_id="inference", book_id="book-inference", chapter_id="01-chapter.md",
            source_path=path, source_revision="r" * 64,
            source_excerpt="The engine releases the sequence.",
            claim_text="The engine releases the sequence.",
            claim_type="IMPLEMENTATION", epistemic_role="OBSERVED"))
        req = tech.record_requirement(session, __import__(
            "mission_control.schemas", fromlist=["TechnicalRequirementCreate"]
        ).TechnicalRequirementCreate(
            claim_id=claim.id, requirement_key="run_record", label="Run record"))
        session.commit()
        n_claims = session.query(TechnicalClaim).count()
    _assess(client)
    with database.session() as session:
        assert session.query(TechnicalClaim).count() == n_claims
        assert tech.get_claim(session, claim.id).claim_text == "The engine releases the sequence."
        assert len(tech.list_requirements(session, claim.id)) == 1


# --- preflight adapter -----------------------------------------------------


def test_preflight_error_on_missing_book(client: TestClient, tmp_path, runtime) -> None:
    _point_project(tmp_path, runtime, str(tmp_path / "no-such-book"))
    response = client.post("/api/publication/assessments",
                           json={"project_id": "inference"})
    assert response.status_code in (400, 422)


def test_preflight_contract_violation_recorded(client: TestClient, tmp_path, runtime, monkeypatch) -> None:
    import workbench.publication as wbpub

    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One")})
    _point_project(tmp_path, runtime, root)
    monkeypatch.setattr(wbpub, "build_preflight", lambda *a, **k: {"schema": "wrong"})
    report = _assess(client)
    preflight_gate = [g for g in report["gates"]
                      if g["gate_id"] in ("chapter_structure", "assets_references")]
    assert all(g["result"] == "ERROR" for g in preflight_gate)
    assert report["assessment_status"] in ("NOT_YET_ASSESSED", "BLOCKED")


# --- issues, approval, calibration -----------------------------------------


def test_issue_waiver_rules(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One")},
                 index="This book has all 99 chapters.\n")
    _point_project(tmp_path, runtime, root)
    report = _assess(client)
    blockers = [i for i in report["issues"] if i["severity"] == "blocker"]
    assert blockers, "expected a blocking issue from the index mismatch"
    nonwaivable = next(i for i in blockers if i["waiver_eligibility"] == "nonwaivable")
    bad = client.post(f"/api/publication/issues/{nonwaivable['id']}/review", json={
        "decision": "ACCEPT LIMITATION", "reviewer": "author"})
    assert bad.status_code in (400, 422)
    ok = client.post(f"/api/publication/issues/{nonwaivable['id']}/review", json={
        "decision": "DEFER", "rationale": "fix index in a follow-up", "reviewer": "author"})
    assert ok.json()["author_review_status"] == "deferred"


def test_calibration_record_and_summary(client: TestClient, tmp_path) -> None:
    from mission_control.persistence.db import Database as _DB  # noqa: F401 (import surface)

    path = tmp_path / "c.md"
    path.write_text("The engine releases the sequence.\n", encoding="utf-8")
    claim_id = client.post("/api/technical/claims", json={
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": str(path), "source_revision": "r" * 64,
        "source_excerpt": "The engine releases the sequence.",
        "claim_text": "The engine releases the sequence.",
        "claim_type": "IMPLEMENTATION", "epistemic_role": "OBSERVED"}).json()["id"]
    req_id = client.post("/api/technical/requirements", json={
        "claim_id": claim_id, "requirement_key": "run_record", "label": "Run record",
        "requirement_type": "experiment"}).json()["id"]
    created = client.post("/api/publication/calibration", json={
        "requirement_id": req_id, "sample_version": 1, "sample_reason": "test",
        "claim_accurate": True, "requirement_applicable": "APPLICABLE",
        "necessary": True, "strictness_ok": True, "satisfied_by_evidence": "no",
        "gap_justified": False, "priority_proportionate": False,
        "would_block": False, "qualification_sufficient": False,
        "verdict": "applicable; gap misclassified", "correction": "retype gap",
        "reviewer": "operator"}).json()
    assert created["requirement_id"] == req_id
    summary = client.get("/api/publication/calibration/summary").json()
    assert summary["reviewed"] >= 1
    assert summary["advisory_only"] is True
    bad = client.post("/api/publication/calibration", json={
        "requirement_id": req_id, "requirement_applicable": "MAYBE"})
    assert bad.status_code in (400, 422)


def test_dossier_files_and_download(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One")})
    _point_project(tmp_path, runtime, root)
    report = _assess(client)
    markdown = client.get(
        f"/api/publication/assessments/{report['id']}/dossier.md").text
    assert "Publication readiness" in markdown
    assert "manuscript_identity" in markdown
    zipped = client.get(f"/api/publication/assessments/{report['id']}/dossier.zip")
    assert zipped.status_code == 200
    assert zipped.headers["content-type"] == "application/zip"
    import io
    import zipfile

    names = zipfile.ZipFile(io.BytesIO(zipped.content)).namelist()
    for expected in ("publication-manifest.json", "release-policy.json",
                     "gate-results.json", "preflight-reference.json",
                     "quality-evidence.json", "release-issues.json",
                     "author-decisions.json", "publication-readiness.md"):
        assert expected in names


def test_unknown_policy_rejected(client: TestClient) -> None:
    bad = client.post("/api/publication/assessments",
                      json={"project_id": "inference", "policy_version": "nope-v9"})
    assert bad.status_code in (400, 422)


def test_pilot_scope_stays_unknown_at_book_level(
    client: TestClient, tmp_path, runtime
) -> None:
    root = _book(tmp_path, {"01-chapter.md": _chapter_text("One"),
                            "02-chapter.md": _chapter_text("Two")})
    _point_project(tmp_path, runtime, root)
    claim_id = client.post("/api/technical/claims", json={
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": str(tmp_path / "book" / "01-chapter.md"), "source_revision": "r" * 64,
        "source_excerpt": "Body text for One.",
        "claim_text": "Body text for One.",
        "claim_type": "FACTUAL", "epistemic_role": "OBSERVED"}).json()["id"]
    assert claim_id
    report = _assess(client)
    gate = next(g for g in report["gates"] if g["gate_id"] == "technical_verification")
    assert gate["result"] == "NOT_RUN"
    assert "1 of 2 chapters" in gate["detail"]
    assert report["assessment_status"] == "NOT_YET_ASSESSED"


def test_reviewed_blocker_fails_release(client: TestClient, tmp_path, runtime) -> None:
    root = _book(tmp_path, {"01-chapter.md": "The engine releases the sequence.\n"})
    _point_project(tmp_path, runtime, root)
    path = str(tmp_path / "book" / "01-chapter.md")
    claim_id = client.post("/api/technical/claims", json={
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": path, "source_revision": "r" * 64,
        "source_excerpt": "The engine releases the sequence.",
        "claim_text": "The engine releases the sequence.",
        "claim_type": "IMPLEMENTATION", "epistemic_role": "OBSERVED"}).json()["id"]
    req_id = client.post("/api/technical/requirements", json={
        "claim_id": claim_id, "requirement_key": "run_record", "label": "Run record",
        "requirement_type": "experiment"}).json()["id"]
    client.post("/api/publication/calibration", json={
        "requirement_id": req_id, "sample_version": 1, "sample_reason": "test",
        "claim_accurate": True, "requirement_applicable": "APPLICABLE",
        "necessary": True, "strictness_ok": True, "satisfied_by_evidence": "no",
        "gap_justified": True, "priority_proportionate": True,
        "would_block": True, "qualification_sufficient": False,
        "verdict": "human-reviewed release blocker", "reviewer": "operator"})
    report = _assess(client)
    gate = next(g for g in report["gates"] if g["gate_id"] == "evidence_completeness")
    assert gate["result"] == "FAIL"
    assert report["assessment_status"] == "BLOCKED"
    blockers = [i for i in report["issues"] if i["issue_type"] == "verified_technical_blocker"]
    assert blockers, "reviewed blocker must surface as a release issue"
