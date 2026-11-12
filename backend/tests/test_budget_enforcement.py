"""MC-QUALITY-04A-04-00 Workstream A: hard budget-enforcement regression battery.

Covers: exact-fit dispatch, per-dimension refusal, no cross-arm transfers,
duplicate/double-count prevention, interruption recovery, retry accounting,
provider-overrun + unmetered violations, durable ledger replay (incl. the
04A-03E B1 overshoot), and opt-in runner integration. Deterministic only.
"""

import pytest

from mission_control.core.errors import ValidationProblem
from mission_control.technical import service as tech


def _account(**over):
    caps = {"max_calls": 44, "max_input": 230000, "max_output": 85000}
    caps.update(over)
    return tech.BudgetAccount(label="B1-test", **caps)


# --- unit: reservation discipline -------------------------------------------

def test_exact_fit_dispatch_allowed():
    account = _account(max_calls=1, max_input=100, max_output=50)
    account.reserve("r1", est_in=100, out_cap=50)
    assert account.complete("r1", actual_in=100, actual_out=50) is True
    assert (account.used_calls, account.used_in, account.used_out) == (1, 100, 50)
    assert account.violations == []


def test_insufficient_output_headroom_refused_without_state_change():
    account = _account()
    account.reserve("r1", est_in=5000, out_cap=80000)
    account.complete("r1", actual_in=5000, actual_out=80000)
    with pytest.raises(ValidationProblem):
        account.reserve("r2", est_in=100, out_cap=5001)
    assert account.refusals == 1
    assert account.used_out == 80000
    assert account._reserved == {}


def test_insufficient_input_headroom_refused():
    account = _account(max_input=100)
    with pytest.raises(ValidationProblem):
        account.reserve("r1", est_in=101, out_cap=1)
    assert account.refusals == 1
    assert account.used_calls == 0


def test_call_budget_exhausted_refused():
    account = _account(max_calls=1, max_input=10**9, max_output=10**9)
    account.reserve("r1", est_in=1, out_cap=1)
    account.complete("r1", actual_in=1, actual_out=1)
    with pytest.raises(ValidationProblem):
        account.reserve("r2", est_in=1, out_cap=1)


def test_no_cross_arm_transfers():
    arm_a = tech.BudgetAccount(label="A", max_calls=8, max_input=100000, max_output=45000)
    arm_b = tech.BudgetAccount(label="B1", max_calls=44, max_input=230000, max_output=85000)
    arm_a.reserve("a1", est_in=100000, out_cap=45000)
    arm_a.complete("a1", actual_in=100000, actual_out=45000)
    # Arm A exhausted; arm B unaffected and arm A caps immutable (no borrow API).
    with pytest.raises(ValidationProblem):
        arm_a.reserve("a2", est_in=1, out_cap=1)
    assert not hasattr(arm_a, "borrow") and not hasattr(arm_a, "transfer")
    arm_b.reserve("b1", est_in=10, out_cap=10)
    assert arm_b.complete("b1", actual_in=10, actual_out=10) is True


def test_duplicate_reservation_key_rejected():
    account = _account()
    account.reserve("r1", est_in=10, out_cap=10)
    with pytest.raises(ValidationProblem):
        account.reserve("r1", est_in=10, out_cap=10)
    account.complete("r1", actual_in=10, actual_out=10)
    with pytest.raises(ValidationProblem):
        account.reserve("r1", est_in=10, out_cap=10)


def test_interrupted_reservation_cancelled_without_consuming_call():
    account = _account()
    account.reserve("r1", est_in=5000, out_cap=5000)
    assert account.cancel("r1") is True
    assert (account.used_calls, account.used_in, account.used_out) == (0, 0, 0)
    # Crash-recovery replays are safe: repeats are no-ops.
    assert account.cancel("r1") is False
    assert account.cancel("never-reserved") is False
    # A fresh reservation for the same work unit proceeds normally.
    account.reserve("r1-retry", est_in=5000, out_cap=5000)
    assert account.complete("r1-retry", actual_in=1, actual_out=1) is True


def test_retry_after_failure_consumes_a_new_call():
    account = _account()
    account.reserve("r1", est_in=100, out_cap=100)
    assert account.complete("r1", actual_in=50, actual_out=0, metered=True) is True
    assert account.used_calls == 1
    account.reserve("r1-retry", est_in=100, out_cap=100)
    assert account.complete("r1-retry", actual_in=60, actual_out=70) is True
    assert account.used_calls == 2
    assert account.used_out == 70


def test_provider_overrun_recorded_not_silenced():
    account = _account()
    account.reserve("r1", est_in=100, out_cap=100)
    assert account.complete("r1", actual_in=100, actual_out=500) is True
    assert account.used_out == 500
    assert account.violations == [{
        "kind": "provider-overrun", "key": "r1",
        "detail": "actual 500 exceeded reserved maximum 100"}]


def test_unmetered_response_consumes_call_and_violates():
    account = _account()
    account.reserve("r1", est_in=100, out_cap=100)
    assert account.complete("r1", actual_in=0, actual_out=0, metered=False) is True
    assert account.used_calls == 1
    assert [v["kind"] for v in account.violations] == ["unmetered-response"]


def test_duplicate_completion_never_double_counts():
    account = _account()
    account.reserve("r1", est_in=100, out_cap=100)
    assert account.complete("r1", actual_in=100, actual_out=90) is True
    assert account.complete("r1", actual_in=100, actual_out=90) is False
    assert (account.used_calls, account.used_in, account.used_out) == (1, 100, 90)
    assert [v["kind"] for v in account.violations] == ["duplicate-completion"]


def test_completion_without_reservation_rejected():
    account = _account()
    with pytest.raises(ValidationProblem):
        account.complete("ghost", actual_in=1, actual_out=1)


def test_state_round_trip_and_replay():
    account = _account()
    account.reserve("r1", est_in=100, out_cap=100)
    account.complete("r1", actual_in=100, actual_out=90)
    account.reserve("r2", est_in=50, out_cap=50)
    state = account.to_state()
    revived = tech.BudgetAccount.from_state(state)
    assert revived.to_state() == state
    # Replay continues exactly: r2 settles, r3 reserves against remainder.
    assert revived.complete("r2", actual_in=50, actual_out=50) is True
    assert (revived.used_calls, revived.used_in, revived.used_out) == (2, 150, 140)


def test_b1_overshoot_replay_is_refused_and_detectable():
    # 04A-03E historical: B1 reached 86,548 output against an 85,000 cap
    # because dispatch never reserved a bounded maximum. Under reservation
    # discipline the offending dispatch is refused; a post-hoc import of the
    # historical ledger is flagged by ceiling_breaches().
    account = _account()
    account.used_calls = 30
    account.used_in = 160000
    account.used_out = 84000
    with pytest.raises(ValidationProblem):
        account.reserve("b1-next-region", est_in=5000, out_cap=4738)
    assert account.refusals == 1
    # Historical import path: reconstruct, then detect the breach.
    legacy = tech.BudgetAccount.from_state({
        "label": "B1", "max_calls": 44, "max_input": 230000, "max_output": 85000,
        "used_calls": 33, "used_in": 173421, "used_out": 86548,
        "reserved": {}, "settled": [], "refusals": 0, "violations": []})
    assert legacy.used_out == 86548
    assert legacy.over_ceiling() == ["output"]


# --- runner integration (isolated tmp DB, mock evaluate_fn) ------------------

def _campaign(tmp_path, runtime, chapters):
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


def _claims(chapter):
    return {"claims": [{
        "source_path": chapter, "chapter_revision": "r" * 64,
        "source_quote": "Content.", "claim_text": "Claim from %s." % chapter,
        "claim_type": "FACTUAL", "epistemic_role": "OBSERVED",
        "assumptions": [], "qualifications": []}]}


def test_runner_gates_and_settles_per_chapter(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime, ["01-chapter.md", "02-chapter.md"])

    def evaluate_fn(chapter_id):
        out = _claims(chapter_id)
        out["usage"] = {"input_tokens": 100, "output_tokens": 40}
        return out

    budget = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=200)
    estimates = {"01-chapter.md": {"est_in": 100, "out_cap": 40},
                 "02-chapter.md": {"est_in": 100, "out_cap": 40}}
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget, estimates=estimates)
    assert record.status == "completed"
    assert (budget.used_calls, budget.used_in, budget.used_out) == (2, 200, 80)
    assert budget.violations == []
    assert record.usage["budget"]["used_calls"] == 2


def test_runner_refuses_chapter_over_remaining_budget(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime, ["01-chapter.md", "02-chapter.md"])

    def evaluate_fn(chapter_id):
        out = _claims(chapter_id)
        out["usage"] = {"input_tokens": 100, "output_tokens": 90}
        return out

    budget = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=100)
    estimates = {"01-chapter.md": {"est_in": 100, "out_cap": 90},
                 "02-chapter.md": {"est_in": 100, "out_cap": 90}}
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget, estimates=estimates)
    assert record.status == "partial"
    assert (record.completed, record.failed) == (1, 1)
    assert "budget refused" in record.usage["failures"]["02-chapter.md"]
    assert budget.used_calls == 1 and budget.refusals == 1


def test_runner_records_unmetered_violation(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime, ["01-chapter.md"])

    def evaluate_fn(chapter_id):
        return _claims(chapter_id)  # no usage: unmetered

    budget = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=200)
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget,
                                         estimates={"01-chapter.md": {"est_in": 10, "out_cap": 10}})
    assert record.status == "completed"
    assert [v["kind"] for v in budget.violations] == ["unmetered-response"]
    assert budget.used_calls == 1


def test_runner_exception_still_consumes_call(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime, ["01-chapter.md"])

    def evaluate_fn(chapter_id):
        raise RuntimeError("model exploded")

    budget = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=200)
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget,
                                         estimates={"01-chapter.md": {"est_in": 10, "out_cap": 10}})
    assert record.status == "partial"
    assert budget.used_calls == 1
    assert [v["kind"] for v in budget.violations] == ["unmetered-response"]


def test_runner_without_estimates_runs_ungated(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime, ["01-chapter.md"])

    def evaluate_fn(chapter_id):
        out = _claims(chapter_id)
        out["usage"] = {"input_tokens": 5, "output_tokens": 5}
        return out

    budget = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=200)
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=budget, estimates=None)
    assert record.status == "completed"
    assert budget.used_calls == 0 and budget.refusals == 0


def test_runner_resume_skips_done_without_reserving(tmp_path, runtime, client):
    database, campaign_id, _ = _campaign(tmp_path, runtime, ["01-chapter.md", "02-chapter.md"])
    seen: list[str] = []

    def evaluate_fn(chapter_id):
        seen.append(chapter_id)
        out = _claims(chapter_id)
        out["usage"] = {"input_tokens": 10, "output_tokens": 10}
        return out

    first = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=200)
    estimates = {"01-chapter.md": {"est_in": 10, "out_cap": 10},
                 "02-chapter.md": {"est_in": 10, "out_cap": 10}}
    record = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                         budget=first, estimates=estimates)
    assert record.status == "completed" and seen == ["01-chapter.md", "02-chapter.md"]
    # Completed campaigns rerun as idempotent no-ops: no new reservations.
    second = tech.BudgetAccount(label="arm", max_calls=4, max_input=1000, max_output=200)
    record2 = tech.run_technical_campaign(database.session, campaign_id, evaluate_fn,
                                          budget=second, estimates=estimates)
    assert record2.status == "completed" and seen == ["01-chapter.md", "02-chapter.md"]
    assert second.used_calls == 0
