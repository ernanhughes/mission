"""WORK-OUTCOME-01 W3: deterministic triage tests (no model calls)."""

from mission_control.work_observation.triage import (
    AMBIGUOUS,
    INSUFFICIENT_EVIDENCE,
    NEEDS_SEMANTIC,
    RESEARCH_OR_INVESTIGATION,
    REVIEW_OR_CORRECTION,
    SUBSTANTIVE_CANDIDATE,
    TRIVIAL_INTERACTION,
    SessionSummary,
    triage,
)


def _base(sid: str = "s1", n: int = 3) -> SessionSummary:
    return SessionSummary(session_id=sid, message_count=n)


def test_probe_session_is_trivial() -> None:
    s = _base(n=2)
    s.user_first = "TASK: Return the single word READY."
    assert triage(s).classification == TRIVIAL_INTERACTION


def test_attached_file_without_execution_is_insufficient() -> None:
    s = _base(n=3)
    s.user_first = ("The full request is in the attached file. Follow it exactly.\n"
                    '<file name="opencode-prompt-x.md">')
    assert triage(s).classification == TRIVIAL_INTERACTION


def test_bare_request_without_signals_is_insufficient() -> None:
    s = _base(n=2)
    s.user_first = "hello, are you there?"
    assert triage(s).classification == INSUFFICIENT_EVIDENCE


def test_empty_request_prefix_is_trivial_probe() -> None:
    s = _base(n=2)
    s.user_first = "REQUEST:"
    assert triage(s).classification == TRIVIAL_INTERACTION


def test_episode_member_is_substantive_candidate() -> None:
    s = _base(n=4000)
    s.in_episode = True
    assert triage(s).classification == SUBSTANTIVE_CANDIDATE


def test_chain_member_is_substantive_candidate() -> None:
    s = _base(n=25)
    s.has_chain = True
    assert triage(s).classification == SUBSTANTIVE_CANDIDATE


def test_task_signal_is_substantive_candidate() -> None:
    s = _base()
    s.has_task = True
    assert triage(s).classification == SUBSTANTIVE_CANDIDATE


def test_review_tools_classify() -> None:
    s = _base()
    s.review_tools = True
    assert triage(s).classification == REVIEW_OR_CORRECTION


def test_claim_without_anchor_is_ambiguous_and_queued() -> None:
    s = _base(n=25)
    s.has_claims = True
    v = triage(s)
    assert v.classification == AMBIGUOUS and v.queued_for_model is True


def test_research_paths_only() -> None:
    s = _base(n=8)
    s.research_files = ["docs/research/plan.md"]
    assert triage(s).classification == RESEARCH_OR_INVESTIGATION


def test_signals_without_home_queue_for_model() -> None:
    s = _base(n=10)
    s.has_files = True
    v = triage(s)
    assert v.classification == NEEDS_SEMANTIC and v.queued_for_model is True


def test_triage_never_invents_objectives() -> None:
    s = _base(n=500)
    v = triage(s)
    assert v.classification in (INSUFFICIENT_EVIDENCE, NEEDS_SEMANTIC)
    assert "objective" not in v.reason
