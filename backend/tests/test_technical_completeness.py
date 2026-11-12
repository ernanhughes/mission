"""MC-QUALITY-03C: regions, coverage, requirements, gaps, objectives."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from mission_control.models import TechnicalClaim
from mission_control.persistence.db import Database
from mission_control.technical import service as tech


def _units(prefix="S"):
    return [
        {"title": f"{prefix} one", "char_span": [0, 100], "byte_span": [0, 100],
         "id": "u1", "editable": True, "bounded": True},
        {"title": f"{prefix} two", "char_span": [100, 300], "byte_span": [100, 300],
         "id": "u2", "editable": True, "bounded": True},
    ]


def _chapter(tmp_path, name="01-chapter.md"):
    target = tmp_path / name
    target.write_text("The engine releases the sequence on completion.\n", encoding="utf-8")
    return str(target)


def _claim_id(client: TestClient, path: str, **overrides):
    body = {
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": path, "source_revision": "r" * 64,
        "source_excerpt": "The engine releases the sequence on completion.",
        "claim_text": "The engine releases the sequence on completion.",
        "claim_type": "IMPLEMENTATION", "epistemic_role": "OBSERVED",
    }
    body.update(overrides)
    return client.post("/api/technical/claims", json=body).json()["id"]


def test_regions_sync_is_idempotent(client: TestClient, tmp_path, runtime) -> None:
    path = _chapter(tmp_path)
    rev = hashlib.sha256(open(path, "rb").read()).hexdigest()
    first = client.post("/api/technical/regions/sync", params={
        "project_id": "inference", "chapter_id": "01-chapter.md",
        "source_path": path, "source_hash": rev},
        json=[{**u, "chapter_hash": rev} for u in _units()]).json()
    second = client.post("/api/technical/regions/sync", params={
        "project_id": "inference", "chapter_id": "01-chapter.md",
        "source_path": path, "source_hash": rev},
        json=[{**u, "chapter_hash": rev} for u in _units()]).json()
    assert [r["id"] for r in first] == [r["id"] for r in second]
    assert len(first) == 2


def test_coverage_cap_recorded_not_completed(client: TestClient, tmp_path, runtime) -> None:
    path = _chapter(tmp_path)
    rev = hashlib.sha256(open(path, "rb").read()).hexdigest()
    regions = client.post("/api/technical/regions/sync", params={
        "project_id": "inference", "chapter_id": "01-chapter.md",
        "source_path": path, "source_hash": rev},
        json=[{**_units()[0], "chapter_hash": rev}]).json()
    rid = regions[0]["id"]
    database = Database(runtime)
    with database.session() as session:
        cov = tech.record_coverage(
            session, region_id=rid, source_hash=rev, requested_limit=40,
            returned_count=40, status="LIMIT_REACHED", limit_reached=True)
        session.commit()
        assert cov.status == "LIMIT_REACHED"
        assert cov.limit_reached is True
    listed = client.get("/api/technical/completeness/01-chapter.md?project_id=inference").json()
    assert listed["regions_total"] >= 1
    assert listed["regions_capped"] >= 1
    assert listed["claims_total"] >= 0


def test_requirement_lifecycle_and_waiver_rule(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    cid = _claim_id(client, path)
    created = client.post("/api/technical/requirements", json={
        "claim_id": cid, "requirement_key": "run_record", "label": "Run record",
        "requirement_type": "experiment", "acceptance_rule": "recorded run",
        "rationale": "reproducibility"}).json()
    assert created["applicability"] == "UNDETERMINED"
    bad = client.post("/api/technical/requirements/xxx/status", json={"satisfaction": "DONE"})
    assert bad.status_code in (400, 404, 422)
    waived = client.post(f"/api/technical/requirements/{created['id']}/status",
                         json={"satisfaction": "WAIVED_WITH_RATIONALE"})
    assert waived.status_code == 422
    ok = client.post(f"/api/technical/requirements/{created['id']}/status", json={
        "satisfaction": "WAIVED_WITH_RATIONALE", "waived_reason": "illustrative example"})
    assert ok.json()["satisfaction"] == "WAIVED_WITH_RATIONALE"
    linked = client.get(f"/api/technical/claims/{cid}/requirements").json()
    assert any(r["waived_reason"] == "illustrative example" for r in linked)


def test_shared_evidence_and_contradiction(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    first = _claim_id(client, path)
    second = client.post("/api/technical/claims", json={
        "project_id": "inference", "book_id": "book-inference", "chapter_id": "01-chapter.md",
        "source_path": path, "source_revision": "r" * 64,
        "source_excerpt": "The engine releases the sequence on completion, always.",
        "claim_text": "The engine always releases the sequence on completion.",
        "claim_type": "IMPLEMENTATION", "epistemic_role": "OBSERVED"}).json()["id"]
    ev = client.post("/api/technical/evidence", json={
        "claim_id": first, "evidence_type": "source_file",
        "source_location": path, "verification_status": "SUPPORTED_BY_EXECUTED_EVIDENCE"}).json()
    link = client.post("/api/technical/requirement-links", json={
        "requirement_id": client.post("/api/technical/requirements", json={
            "claim_id": second, "requirement_key": "run_record", "label": "R",
            "requirement_type": "experiment"}).json()["id"],
        "evidence_id": ev["id"], "relation": "contradicts",
        "note": "same artifact, opposing reading"}).json()
    assert link["relation"] == "contradicts"
    claim_link = client.post("/api/technical/claim-links", json={
        "from_claim_id": first, "to_claim_id": second, "relation": "contradicts",
        "note": "universal vs observed reading"})
    assert claim_link.status_code == 201
    self_link = client.post("/api/technical/claim-links", json={
        "from_claim_id": first, "to_claim_id": first, "relation": "depends_on"})
    assert self_link.status_code in (400, 422)


def test_gap_lifecycle_and_review(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    cid = _claim_id(client, path)
    gap = client.post("/api/technical/gaps", json={
        "project_id": "inference", "chapter_id": "01-chapter.md", "claim_id": cid,
        "gap_type": "NOT_SEARCHED", "title": "Unexamined test suite",
        "detail": "examples/ not yet searched", "searched_scope": "chapter text only",
        "priority_rationale": "blocks verification of implementation claims"}).json()
    assert gap["status"] == "OPEN"
    bad = client.post("/api/technical/gaps", json={
        "chapter_id": "01-chapter.md", "gap_type": "NOPE"})
    assert bad.status_code in (400, 422)
    decided = client.post("/api/technical/reviews", json={
        "finding_id": gap["id"], "decision": "DEFER",
        "reviewer": "author", "source_digest": "r" * 64})
    assert decided.status_code == 201
    assert decided.json()["decision"] == "DEFER"
    resolved = client.post(f"/api/technical/gaps/{gap['id']}/status", json={"status": "RESOLVED"})
    assert resolved.json()["status"] == "RESOLVED"


def test_objectives_provisional_and_linked(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    cid = _claim_id(client, path)
    obj = client.post("/api/technical/objectives", json={
        "project_id": "inference", "chapter_id": "01-chapter.md",
        "statement": "Establish the request lifecycle vocabulary."}).json()
    assert obj["source"] == "inferred"
    assert obj["status"] == "proposed"
    link = client.post("/api/technical/objectives/link", json={
        "objective_id": obj["id"], "claim_id": cid, "role": "supports"})
    assert link.status_code == 201
    bad = client.post("/api/technical/objectives", json={
        "chapter_id": "01-chapter.md", "statement": "x", "source": "oracle"})
    assert bad.status_code in (400, 422)


def test_completeness_report_and_stale_detection(client: TestClient, tmp_path, runtime) -> None:
    from mission_control.quality.service import resolve_book_root  # noqa: F401 (contract probe)

    root = tmp_path / "book"
    root.mkdir()
    chapter = root / "01-chapter.md"
    chapter.write_text("Alpha claim here.\n", encoding="utf-8")
    database = Database(runtime)
    with database.session() as session:
        from mission_control.models import Book
        book = session.query(Book).filter_by(project_id="inference").one_or_none()
        assert book is not None
        book.manuscript_paths = [str(root)]
        session.commit()
    regions = client.post("/api/technical/regions/sync", params={
        "project_id": "inference", "chapter_id": "01-chapter.md",
        "source_path": str(chapter), "source_hash": "h1"},
        json=[{**_units()[0], "chapter_hash": "h1"}]).json()
    assert len(regions) == 1
    report = client.get(
        f"/api/technical/completeness/01-chapter.md?project_id=inference&book_root={root}").json()
    assert report["regions_total"] == 1
    assert report["regions_not_started"] == 1
    assert report["assessment"] in ("NOT_ASSESSED", "PARTIAL")
