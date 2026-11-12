"""MC-QUALITY-04A-04-00 Workstream H: campaign crash-simulation and recovery.

Simulates interruption at runner boundaries with mock evaluate functions and
failing session factories, on isolated tmp databases. No model calls.
"""

from mission_control.technical import service as tech


def _campaign(tmp_path, runtime, chapters=("01-chapter.md", "02-chapter.md", "03-chapter.md")):
    from mission_control.persistence.db import Database
    from mission_control.quality.service import create_campaign
    from mission_control.schemas import QualityCampaignCreate

    root = tmp_path / "book"
    root.mkdir(exist_ok=True)
    for chapter in chapters:
        (root / chapter).write_text("Content of %s.\n" % chapter, encoding="utf-8")
    database = Database(runtime)
    with database.session() as session:
        campaign = create_campaign(session, QualityCampaignCreate(
            project_id="inference", book_id="book-inference", book_root=str(root),
            mode="selected", chapters=list(chapters),
            model="m", assessment_type="technical"))
        session.commit()
        campaign_id = campaign.id
    return database, campaign_id, root


def _outcome(chapter, usage=None):
    return {"claims": [{
        "source_path": chapter, "chapter_revision": "r" * 64,
        "source_quote": "Content.", "claim_text": "Claim from %s." % chapter,
        "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
        "assumptions": [], "qualifications": []}],
        "usage": usage or {"input_tokens": 10, "output_tokens": 5}}


def test_stop_mid_campaign_keeps_progress_and_releases_budget(tmp_path, runtime, client):
    from mission_control.quality.service import stop_campaign

    database, campaign_id, _ = _campaign(tmp_path, runtime)

    def evaluate_fn(chapter_id):
        if chapter_id == "02-chapter.md":
            with database.session() as session:
                stop_campaign(session, campaign_id)
        return _outcome(chapter_id)

    budget = tech.BudgetAccount(label="arm", max_calls=10, max_input=10000, max_output=10000)
    estimates = {c: {"est_in": 10, "out_cap": 10}
                 for c in ("01-chapter.md", "02-chapter.md", "03-chapter.md")}
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget, estimates=estimates)
    assert record.status == "partial"
    assert record.completed == 2 and record.failed == 0
    # No stranded reservations: both dispatched chapters settled, the stopped
    # chapter never reserved (stop is checked before reservation).
    assert budget._reserved == {}
    assert budget.used_calls == 2


def test_session_factory_crash_marks_interrupted_and_keeps_progress(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime)
    calls = {"n": 0}
    real_session = database.session

    def flaky_session():
        # Call order: 1 outer, 2 stop-check, 3 heartbeat, 4 claims persist,
        # 5 progress-row write -> crash after chapter 1 claims are committed.
        calls["n"] += 1
        if calls["n"] == 5:
            raise RuntimeError("disk exploded mid-campaign")
        return real_session()

    def evaluate_fn(chapter_id):
        return _outcome(chapter_id)

    record = tech.run_technical_campaign(flaky_session, campaign_id, evaluate_fn)
    assert record.status == "interrupted"
    assert "disk exploded" in (record.error or "")
    with database.session() as session:
        rows = [c for c in tech.list_claims(session, project_id="inference",
                                            chapter_id="01-chapter.md", limit=100)
                if c.campaign_id == campaign_id]
        assert len(rows) == 1


def test_exhausted_budget_stops_arm_with_clear_state(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime)

    def evaluate_fn(chapter_id):
        return _outcome(chapter_id)

    budget = tech.BudgetAccount(label="arm", max_calls=1, max_input=10000, max_output=10000)
    estimates = {c: {"est_in": 10, "out_cap": 10}
                 for c in ("01-chapter.md", "02-chapter.md", "03-chapter.md")}
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget, estimates=estimates)
    assert record.status == "partial"
    assert (record.completed, record.failed) == (1, 2)
    assert all("budget refused" in m for m in record.usage["failures"].values())
    assert budget.used_calls == 1 and budget.refusals == 2


def test_resume_after_interruption_completes_without_rework(tmp_path, runtime, client):
    from mission_control.quality.service import resume_campaign

    database, campaign_id, _ = _campaign(tmp_path, runtime, ("01-chapter.md", "02-chapter.md"))
    seen: list[str] = []

    crashed = {"once": False}

    def flaky(chapter_id):
        seen.append(chapter_id)
        if chapter_id == "02-chapter.md" and not crashed["once"]:
            crashed["once"] = True
            raise RuntimeError("transient runner crash")
        return _outcome(chapter_id)

    budget = tech.BudgetAccount(label="arm", max_calls=10, max_input=10000, max_output=10000)
    estimates = {"01-chapter.md": {"est_in": 10, "out_cap": 10},
                 "02-chapter.md": {"est_in": 10, "out_cap": 10}}
    first = tech.run_technical_campaign(database.session, campaign_id, flaky,
                                        budget=budget, estimates=estimates)
    assert first.status == "partial"
    # The failed chapter consumed its call (failed attempts are billable).
    assert budget.used_calls == 2
    seen.clear()
    with database.session() as session:
        resume_campaign(session, campaign_id)
        session.commit()
    second_budget = tech.BudgetAccount(label="arm", max_calls=10,
                                       max_input=10000, max_output=10000)
    second = tech.run_technical_campaign(database.session, campaign_id, flaky,
                                         budget=second_budget, estimates=estimates)
    assert second.status == "completed"
    assert seen == ["02-chapter.md"]
    assert second_budget.used_calls == 1
