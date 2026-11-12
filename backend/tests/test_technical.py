"""MC-QUALITY-03B: technical claim inventory, evidence and verification contracts."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.persistence.db import Database
from mission_control.technical import service as tech


def _chapter(tmp_path: Path, name: str = "01-chapter.md") -> str:
    text = (
        "+++\ntitle = \"Alpha\"\n+++\n\n"
        "The engine releases the sequence on completion.\n"
        "\n"
        "A KV cache avoids recomputing past attention keys.\n"
    )
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return str(target)


def _claim(path: str, revision: str = "r" * 64, **overrides):
    body = {
        "project_id": "inference",
        "book_id": "book-inference",
        "chapter_id": "01-chapter.md",
        "source_path": path,
        "source_revision": revision,
        "source_excerpt": "The engine releases the sequence on completion.",
        "claim_text": "The engine releases the sequence on completion.",
        "claim_type": "IMPLEMENTATION",
        "epistemic_role": "OBSERVED",
        "qualifications": ["in this configuration"],
    }
    body.update(overrides)
    return body


def test_record_claim_validates_exact_quote(client: TestClient, tmp_path, runtime) -> None:
    path = _chapter(tmp_path)
    created = client.post("/api/technical/claims", json=_claim(path, quote_validated=True))
    assert created.status_code == 201, created.text
    assert created.json()["quote_validated"] is True


def test_record_claim_flags_unverifiable_quote(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    created = client.post(
        "/api/technical/claims",
        json=_claim(path, source_excerpt="The engine never releases anything.", quote_validated=True),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["quote_validated"] is False
    assert body["source_excerpt"] == "The engine never releases anything."


def test_record_claim_rejects_unknown_taxonomy(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    bad = client.post("/api/technical/claims", json=_claim(path, claim_type="VIBE"))
    assert bad.status_code in (400, 422)
    bad2 = client.post("/api/technical/claims", json=_claim(path, epistemic_role="PROVEN"))
    assert bad2.status_code in (400, 422)


def test_compound_claims_stay_separate(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    first = client.post("/api/technical/claims", json=_claim(path)).json()
    second = client.post(
        "/api/technical/claims",
        json=_claim(path, claim_text="A KV cache avoids recomputing past attention keys.",
                    source_excerpt="A KV cache avoids recomputing past attention keys.",
                    claim_type="ARCHITECTURAL", epistemic_role="OBSERVED"),
    ).json()
    assert first["id"] != second["id"]
    listed = client.get("/api/technical/claims?project_id=inference&chapter_id=01-chapter.md").json()
    assert {c["id"] for c in listed} >= {first["id"], second["id"]}


def test_evidence_and_verification_lifecycle(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    claim = client.post("/api/technical/claims", json=_claim(path, quote_validated=True)).json()
    assert claim["derived_state"] == "current"
    evidence = client.post("/api/technical/evidence", json={
        "claim_id": claim["id"], "evidence_type": "source_file",
        "source_location": path, "source_revision": "r" * 64,
        "discovery_method": "file_ref_scan", "verification_method": "exists_check",
        "verification_status": "SUPPORTED_BY_EXECUTED_EVIDENCE",
    }).json()
    assert evidence["id"].startswith("tev:")
    verification = client.post("/api/technical/verifications", json={
        "claim_id": claim["id"], "evidence_id": evidence["id"], "method": "deterministic",
        "status": "VERIFIED_DETERMINISTICALLY", "detail": "file exists on disk",
    }).json()
    assert verification["status"] == "VERIFIED_DETERMINISTICALLY"
    assert verification["method"] == "deterministic"
    detail = client.get(f"/api/technical/chapters/01-chapter.md?project_id=inference").json()
    assert detail["claims_total"] == 1
    assert detail["by_status"] == {"VERIFIED_DETERMINISTICALLY": 1}
    assert detail["by_method"] == {"deterministic": 1}
    overview = client.get("/api/technical/overview?project_id=inference").json()
    assert overview["claims_total"] >= 1


def test_contradictory_evidence_preserved(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    claim = client.post("/api/technical/claims", json=_claim(path, quote_validated=True)).json()
    first = client.post("/api/technical/evidence", json={
        "claim_id": claim["id"], "evidence_type": "source_file", "source_location": path,
        "verification_status": "SUPPORTED_BY_DOCUMENTATION"}).json()
    client.post("/api/technical/verifications", json={
        "claim_id": claim["id"], "evidence_id": first["id"], "method": "documentary",
        "status": "SUPPORTED_BY_DOCUMENTATION", "detail": "supported"})
    second = client.post("/api/technical/evidence", json={
        "claim_id": claim["id"], "evidence_type": "test_result", "source_location": "tests/x",
        "verification_status": "CONTRADICTED_BY_EVIDENCE", "limitations": "one failing case"}).json()
    client.post("/api/technical/verifications", json={
        "claim_id": claim["id"], "evidence_id": second["id"], "method": "deterministic",
        "status": "CONTRADICTED_BY_EVIDENCE", "detail": "counter-evidence"})
    verifications = client.get(f"/api/technical/claims/{claim['id']}/verifications").json()
    assert {v["status"] for v in verifications} == {"SUPPORTED_BY_DOCUMENTATION", "CONTRADICTED_BY_EVIDENCE"}
    detail = client.get("/api/technical/chapters/01-chapter.md?project_id=inference").json()
    assert detail["claims_unresolved"] == 1


def test_stale_source_detected(client: TestClient, tmp_path, runtime) -> None:
    path = _chapter(tmp_path)
    claim = client.post("/api/technical/claims", json=_claim(path, quote_validated=True)).json()
    assert claim["derived_state"] == "current"
    Path(path).write_text(Path(path).read_text(encoding="utf-8") + "\nMore.\n", encoding="utf-8")
    listed = client.get("/api/technical/claims?project_id=inference&chapter_id=01-chapter.md").json()
    assert listed and all(c["derived_state"] == "current" for c in listed)  # stored rows unchanged
    # Freshness is derived against a supplied revision:
    from mission_control.technical.service import to_claim_read, get_claim
    from mission_control.persistence.db import Database

    database = Database(runtime)
    with database.session() as session:
        record = get_claim(session, claim["id"])
        assert to_claim_read(record, current_revision="s" * 64).derived_state == "stale"


def test_review_actions_on_claims(client: TestClient, tmp_path) -> None:
    path = _chapter(tmp_path)
    claim = client.post("/api/technical/claims", json=_claim(path, quote_validated=True)).json()
    decided = client.post("/api/technical/reviews", json={
        "finding_id": claim["id"], "decision": "INVESTIGATE",
        "reason": "check against executed backend", "reviewer": "author",
        "source_digest": claim["source_revision"],
    })
    assert decided.status_code == 201, decided.text
    assert decided.json()["decision"] == "INVESTIGATE"
    bad = client.post("/api/technical/reviews", json={"finding_id": claim["id"], "decision": "SHIP_IT"})
    assert bad.status_code in (400, 422)


def test_technical_campaign_api_scopes_by_assessment_type(client: TestClient, tmp_path, runtime) -> None:
    root = tmp_path / "book3"
    root.mkdir()
    (root / "01-chapter.md").write_text("Alpha.\n", encoding="utf-8")
    database = Database(runtime)
    with database.session() as session:
        from mission_control.models import Book

        book = session.get(Book, "book-math")
        assert book is not None
        book.manuscript_paths = [str(root)]
        session.commit()
    created = client.post("/api/technical/campaigns", json={
        "project_id": "math", "mode": "selected", "chapters": ["01-chapter.md"]}).json()
    assert created["assessment_type"] == "technical"
    assert created["chapter_selection"] == ["01-chapter.md"]
    second = client.post("/api/technical/campaigns", json={
        "project_id": "math", "mode": "selected", "chapters": ["01-chapter.md"]})
    assert second.status_code in (400, 409, 422)
    listed = client.get("/api/technical/campaigns?project_id=math").json()
    assert {c["id"] for c in listed} == {created["id"]}
    fetched = client.get(f"/api/technical/campaigns/{created['id']}").json()
    assert fetched["id"] == created["id"]
    stopped = client.post(f"/api/technical/campaigns/{created['id']}/stop").json()
    assert stopped["status"] == "partial"
    resumed = client.post(f"/api/technical/campaigns/{created['id']}/resume").json()
    assert resumed["status"] == "pending"


def test_run_campaign_persists_claims_and_skips_completed(client: TestClient, tmp_path, runtime) -> None:
    from mission_control.technical.service import run_technical_campaign

    root = tmp_path / "book"
    root.mkdir()
    (root / "01-chapter.md").write_text("The engine releases the sequence on completion.\n", encoding="utf-8")
    (root / "02-chapter.md").write_text("Caches save work.\n", encoding="utf-8")
    database = Database(runtime)

    def evaluate_fn(chapter_id: str) -> dict:
        text = (root / chapter_id).read_text(encoding="utf-8")
        import hashlib

        revision = hashlib.sha256(text.encode()).hexdigest()
        return {
            "claims": [{
                "source_path": str(root / chapter_id),
                "chapter_revision": revision,
                "source_quote": text.strip(),
                "claim_text": text.strip(),
                "claim_type": "FACTUAL",
                "epistemic_role": "OBSERVED",
                "assumptions": [], "qualifications": [],
            }],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    with database.session() as session:
        from mission_control.quality.service import create_campaign
        from mission_control.schemas import QualityCampaignCreate

        campaign = create_campaign(session, QualityCampaignCreate(
            project_id="inference", book_id="book-inference", book_root=str(root),
            mode="selected", chapters=["01-chapter.md", "02-chapter.md"],
            model="m", assessment_type="technical"))
        session.commit()
        campaign_id = campaign.id
    record = run_technical_campaign(database.session, campaign_id, evaluate_fn)
    assert record.status == "completed"
    assert record.completed == 2 and record.failed == 0
    listed = client.get("/api/technical/claims?project_id=inference").json()
    assert len([c for c in listed if c["campaign_id"] == campaign_id]) == 2

    # Resume skips completed chapters without duplicating claims.
    calls: list[str] = []

    def counting_fn(chapter_id: str) -> dict:
        calls.append(chapter_id)
        return evaluate_fn(chapter_id)

    # Re-running a completed campaign is an idempotent no-op.
    record2 = run_technical_campaign(database.session, campaign_id, counting_fn)
    assert record2.status == "completed"
    assert calls == []
    listed2 = client.get("/api/technical/claims?project_id=inference").json()
    assert len([c for c in listed2 if c["campaign_id"] == campaign_id]) == 2


def test_run_campaign_isolates_failure(client: TestClient, tmp_path, runtime) -> None:
    from mission_control.technical.service import run_technical_campaign

    root = tmp_path / "book2"
    root.mkdir()
    (root / "01-chapter.md").write_text("Fine claim here.\n", encoding="utf-8")
    (root / "02-chapter.md").write_text("Other claim here.\n", encoding="utf-8")
    database = Database(runtime)
    with database.session() as session:
        from mission_control.quality.service import create_campaign
        from mission_control.schemas import QualityCampaignCreate

        campaign = create_campaign(session, QualityCampaignCreate(
            project_id="inference", book_id="book-inference", book_root=str(root),
            mode="selected", chapters=["01-chapter.md", "02-chapter.md"],
            model="m", assessment_type="technical"))
        session.commit()
        campaign_id = campaign.id

    def evaluate_fn(chapter_id: str) -> dict:
        if chapter_id == "01-chapter.md":
            raise RuntimeError("model exploded")
        import hashlib

        text = (root / chapter_id).read_text(encoding="utf-8")
        return {"claims": [{
            "source_path": str(root / chapter_id),
            "chapter_revision": hashlib.sha256(text.encode()).hexdigest(),
            "source_quote": text.strip(), "claim_text": text.strip(),
            "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
            "assumptions": [], "qualifications": [],
        }]}

    record = run_technical_campaign(database.session, campaign_id, evaluate_fn)
    assert record.status == "partial"
    assert (record.completed, record.failed) == (1, 1)
