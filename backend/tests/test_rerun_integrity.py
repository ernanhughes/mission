"""MC-QUALITY-04A-04-00 Workstream C: duplicate-rerun and recovery integrity.

Proves the distinctions 04A-03E learned the hard way: request vs attempt vs
accepted observation vs retry vs duplicate; repeated processing must not
double-count claims, usage, or coverage, and must never delete history.
Deterministic only (mock evaluate functions, isolated tmp databases).
"""

from mission_control.technical import service as tech


def _campaign(tmp_path, runtime):
    from mission_control.persistence.db import Database
    from mission_control.quality.service import create_campaign
    from mission_control.schemas import QualityCampaignCreate

    root = tmp_path / "book"
    root.mkdir(exist_ok=True)
    (root / "01-chapter.md").write_text("The engine releases the sequence.\n", encoding="utf-8")
    database = Database(runtime)
    with database.session() as session:
        campaign = create_campaign(session, QualityCampaignCreate(
            project_id="inference", book_id="book-inference", book_root=str(root),
            mode="selected", chapters=["01-chapter.md"],
            model="m", assessment_type="technical"))
        session.commit()
        campaign_id = campaign.id
    return database, campaign_id, root


def _outcome(root, revision="r" * 64, usage=None):
    text = (root / "01-chapter.md").read_text(encoding="utf-8").strip()
    return {"claims": [{
        "source_path": str(root / "01-chapter.md"), "chapter_revision": revision,
        "source_quote": text, "claim_text": text,
        "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
        "assumptions": [], "qualifications": []}],
        "usage": usage or {"input_tokens": 10, "output_tokens": 5}}


def test_two_overlapping_attempts_persist_one_claim_two_runs(tmp_path, runtime, client):
    database, campaign_id, root = _campaign(tmp_path, runtime)
    from mission_control.schemas import TechnicalExtractionRunCreate

    first = tech.run_technical_campaign(database.session, campaign_id,
                                        lambda chapter: _outcome(root))
    assert first.status == "completed"
    with database.session() as session:
        from mission_control.technical.service import record_extraction_run
        run = record_extraction_run(session, TechnicalExtractionRunCreate(
            campaign_id=None, strategy="region_single", chapter_id="01-chapter.md",
            region_ids=["treg:x"], requested_limit=40, returned_count=1,
            accepted_count=1, status="COMPLETED_WITHIN_BUDGET",
            input_tokens=10, output_tokens=5, model_id="m",
            prompt_version="2", source_revision="r" * 64))
        session.commit()
        run_id = run.id
    with database.session() as session:
        claims = tech.list_claims(session, project_id="inference",
                                  chapter_id="01-chapter.md", limit=100)
        mine = [c for c in claims if c.campaign_id == campaign_id]
        assert len(mine) == 1
        runs = tech.list_extraction_runs(session, chapter_id="01-chapter.md", limit=100)
        assert {r.id for r in runs} >= {run_id}
        # History preserved: the second attempt added an audit row, deleted nothing.
        assert sum(1 for r in runs if r.accepted_count == 1) >= 1


def test_duplicate_claim_completion_is_single_row(tmp_path, runtime, client):
    database, campaign_id, root = _campaign(tmp_path, runtime)
    payload = dict(
        project_id="inference", book_id="book-inference", chapter_id="01-chapter.md",
        source_path=str(root / "01-chapter.md"), source_revision="r" * 64,
        source_excerpt="The engine releases the sequence.",
        claim_text="The engine releases the sequence.",
        claim_type="FACTUAL", epistemic_role="OBSERVED", campaign_id=campaign_id)
    from mission_control.schemas import TechnicalClaimCreate
    with database.session() as session:
        first = tech.record_claim(session, TechnicalClaimCreate(**payload))
        session.commit()
        first_id = first.id
    with database.session() as session:
        second = tech.record_claim(session, TechnicalClaimCreate(**payload))
        session.commit()
        assert second.id == first_id
    with database.session() as session:
        rows = [c for c in tech.list_claims(session, project_id="inference",
                                            chapter_id="01-chapter.md", limit=100)
                if c.campaign_id == campaign_id]
        assert len(rows) == 1


def test_interrupted_persist_leaves_chapter_retryable(tmp_path, runtime, client):
    import mission_control.technical.service as svc

    database, campaign_id, root = _campaign(tmp_path, runtime)
    calls: list[str] = []
    real_record_claim = svc.record_claim

    def flaky(*args, **kwargs):
        calls.append("persist")
        if len(calls) == 1:
            raise RuntimeError("crash before persistence finishes")
        return real_record_claim(*args, **kwargs)

    import unittest.mock as mock
    with mock.patch.object(svc, "record_claim", side_effect=flaky):
        record = tech.run_technical_campaign(database.session, campaign_id,
                                             lambda chapter: _outcome(root))
    assert record.status == "partial"
    assert record.failed == 1
    # Resume retries the same chapter and persists exactly one claim.
    with database.session() as session:
        from mission_control.quality.service import resume_campaign
        resume_campaign(session, campaign_id)
        session.commit()
    record2 = tech.run_technical_campaign(database.session, campaign_id,
                                          lambda chapter: _outcome(root))
    assert record2.status == "completed"
    with database.session() as session:
        rows = [c for c in tech.list_claims(session, project_id="inference",
                                            chapter_id="01-chapter.md", limit=100)
                if c.campaign_id == campaign_id]
        assert len(rows) == 1


def test_late_completion_after_failure_persists_once(tmp_path, runtime, client):
    database, campaign_id, root = _campaign(tmp_path, runtime)
    attempts = {"n": 0}

    def evaluate_fn(chapter):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {"status": "ERROR", "error": "transport exploded"}
        return _outcome(root)

    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn)
    assert record.status == "partial" and record.failed == 1
    with database.session() as session:
        from mission_control.quality.service import resume_campaign
        resume_campaign(session, campaign_id)
        session.commit()
    record2 = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn)
    assert record2.status == "completed"
    with database.session() as session:
        rows = [c for c in tech.list_claims(session, project_id="inference",
                                            chapter_id="01-chapter.md", limit=100)
                if c.campaign_id == campaign_id]
        assert len(rows) == 1


def test_reconciliation_is_repeatable_and_never_merges(tmp_path, runtime, client):
    from mission_control.schemas import TechnicalClaimCreate

    database, campaign_id, root = _campaign(tmp_path, runtime)
    with database.session() as session:
        for text in ("Same assertion here.", "Same assertion here.", "Other claim."):
            tech.record_claim(session, TechnicalClaimCreate(
                project_id="inference", book_id="book-inference", chapter_id="01-chapter.md",
                source_path=str(root), source_revision="r" * 64,
                source_excerpt="Quote.", claim_text=text,
                claim_type="FACTUAL", epistemic_role="OBSERVED", campaign_id=campaign_id))
        session.commit()
        rows = [c for c in tech.list_claims(session, project_id="inference",
                                            chapter_id="01-chapter.md", limit=100)
                if c.campaign_id == campaign_id]
    first = tech.find_duplicate_candidates(rows)
    second = tech.find_duplicate_candidates(rows)
    assert first == second and len(first) >= 1
    # Candidates are advisory: nothing merged, nothing deleted.
    with database.session() as session:
        remaining = [c for c in tech.list_claims(session, project_id="inference",
                                                chapter_id="01-chapter.md", limit=100)
                    if c.campaign_id == campaign_id]
        assert len(remaining) == len(rows)


def test_coverage_history_appends_latest_wins(tmp_path, runtime, client):
    database, campaign_id, root = _campaign(tmp_path, runtime)
    with database.session() as session:
        region = tech.sync_regions(
            session, project_id="inference", book_id="book-inference",
            chapter_id="01-chapter.md", source_path=str(root / "01-chapter.md"),
            source_hash="h" * 64,
            units=[{"id": "u1", "title": "intro", "char_span": [0, 10],
                    "chapter_hash": "h" * 64}])
        session.commit()
        region_id = region[0].id
    with database.session() as session:
        tech.record_coverage(session, region_id=region_id, campaign_id=campaign_id,
                             source_hash="h" * 64, extractor_version="v1",
                             model_id="m", prompt_version="1", requested_limit=40,
                             returned_count=0, status="FAILED")
        session.commit()
    with database.session() as session:
        tech.record_coverage(session, region_id=region_id, campaign_id=campaign_id,
                             source_hash="h" * 64, extractor_version="v1",
                             model_id="m", prompt_version="1", requested_limit=40,
                             returned_count=3, status="COMPLETED_WITHIN_BUDGET")
        session.commit()
    with database.session() as session:
        assert tech.latest_coverage(session, region_id).status == "COMPLETED_WITHIN_BUDGET"
        from sqlalchemy import select as _select
        from mission_control.models import TechnicalExtractionCoverage as _Coverage
        history = list(session.scalars(
            _select(_Coverage).where(_Coverage.region_id == region_id)).all())
        assert len(history) == 2


def test_claim_links_to_extraction_run_and_duration_persisted(tmp_path, runtime, client):
    from mission_control.schemas import (
        TechnicalClaimCreate, TechnicalExtractionRunCreate)

    database, campaign_id, root = _campaign(tmp_path, runtime)
    with database.session() as session:
        run = tech.record_extraction_run(session, TechnicalExtractionRunCreate(
            campaign_id=None, strategy="region_single", chapter_id="01-chapter.md",
            region_ids=["treg:x"], requested_limit=40, returned_count=1,
            accepted_count=1, status="COMPLETED_WITHIN_BUDGET",
            input_tokens=120, output_tokens=30, model_id="m", prompt_version="2",
            source_revision="r" * 64, duration_ms=45000, transport="file"))
        session.commit()
        run_id = run.id
        assert run.duration_ms == 45000
        assert run.transport == "file"
    with database.session() as session:
        claim = tech.record_claim(session, TechnicalClaimCreate(
            project_id="inference", book_id="book-inference", chapter_id="01-chapter.md",
            source_path=str(root), source_revision="r" * 64,
            source_excerpt="Quote.", claim_text="Linked claim.",
            claim_type="FACTUAL", epistemic_role="OBSERVED",
            campaign_id=campaign_id, extraction_run_id=run_id))
        session.commit()
        assert claim.extraction_run_id == run_id
        read = tech.to_claim_read(claim)
        assert read.extraction_run_id == run_id


def test_reextraction_keeps_original_run_link(tmp_path, runtime, client):
    from mission_control.schemas import (
        TechnicalClaimCreate, TechnicalExtractionRunCreate)

    database, campaign_id, root = _campaign(tmp_path, runtime)
    with database.session() as session:
        first = tech.record_extraction_run(session, TechnicalExtractionRunCreate(
            campaign_id=None, strategy="region_single", chapter_id="01-chapter.md",
            region_ids=["treg:x"], requested_limit=40, returned_count=1,
            accepted_count=1, status="COMPLETED_WITHIN_BUDGET",
            input_tokens=1, output_tokens=1, model_id="m",
            prompt_version="2", source_revision="r" * 64))
        second = tech.record_extraction_run(session, TechnicalExtractionRunCreate(
            campaign_id=None, strategy="region_grouped", chapter_id="01-chapter.md",
            region_ids=["treg:x"], requested_limit=40, returned_count=1,
            accepted_count=1, status="LIMIT_REACHED",
            input_tokens=2, output_tokens=2, model_id="m",
            prompt_version="2", source_revision="r" * 64))
        session.commit()
        body = dict(project_id="inference", book_id="book-inference",
                    chapter_id="01-chapter.md", source_path=str(root),
                    source_revision="r" * 64, source_excerpt="Quote.",
                    claim_text="Same claim twice.", claim_type="FACTUAL",
                    epistemic_role="OBSERVED", campaign_id=campaign_id)
        one = tech.record_claim(session, TechnicalClaimCreate(
            **body, extraction_run_id=first.id))
        session.commit()
        two = tech.record_claim(session, TechnicalClaimCreate(
            **body, extraction_run_id=second.id))
        session.commit()
        assert two.id == one.id
        # First-write-wins: the original run link stands; both attempts
        # remain auditable in their own run rows.
        assert two.extraction_run_id == first.id


def test_unknown_run_link_rejected(tmp_path, runtime, client):
    import pytest

    from mission_control.core.errors import ValidationProblem
    from mission_control.schemas import TechnicalClaimCreate

    database, campaign_id, root = _campaign(tmp_path, runtime)
    with database.session() as session:
        with pytest.raises(ValidationProblem):
            tech.record_claim(session, TechnicalClaimCreate(
                project_id="inference", book_id="book-inference",
                chapter_id="01-chapter.md", source_path=str(root),
                source_revision="r" * 64, source_excerpt="Quote.",
                claim_text="Orphan link.", claim_type="FACTUAL",
                epistemic_role="OBSERVED", campaign_id=campaign_id,
                extraction_run_id="trun:doesnotexist"))
