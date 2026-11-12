"""MC-QUALITY-04A-04-00 Workstream G: evidence-requirement safety tests."""

import pytest

from mission_control.core.errors import ValidationProblem
from mission_control.technical import service as tech


def test_absence_assertion_without_scope_rejected():
    with pytest.raises(ValidationProblem):
        tech.require_searched_scope("MISSING_LOCAL_ARTIFACT", "")
    with pytest.raises(ValidationProblem):
        tech.require_searched_scope("EXPERIMENT_NOT_RUN", None)
    with pytest.raises(ValidationProblem):
        tech.require_searched_scope("MISSING_LOCAL_ARTIFACT", "   ")


def test_absence_assertion_with_scope_allowed():
    tech.require_searched_scope("MISSING_LOCAL_ARTIFACT", "searched repo/tests for x")
    tech.require_searched_scope("EXPERIMENT_NOT_RUN", "checked lab notebook 2026-11")


def test_not_searched_never_requires_scope():
    for scope in ("", None, "   ", "anything"):
        tech.require_searched_scope("NOT_SEARCHED", scope)
    tech.require_searched_scope("EXTRACTION_COVERAGE_GAP", "")


def test_record_gap_enforces_scope_rule(tmp_path, runtime, client):
    from mission_control.persistence.db import Database
    from mission_control.schemas import TechnicalGapCreate

    database = Database(runtime)
    with database.session() as session:
        with pytest.raises(ValidationProblem):
            tech.record_gap(session, TechnicalGapCreate(
                chapter_id="01-chapter.md", gap_type="MISSING_LOCAL_ARTIFACT",
                title="missing file", searched_scope=""))
        gap = tech.record_gap(session, TechnicalGapCreate(
            chapter_id="01-chapter.md", gap_type="NOT_SEARCHED",
            title="unexamined suite", searched_scope="chapter text only"))
        session.commit()
        assert gap.id.startswith("tgap:")
        scoped = tech.record_gap(session, TechnicalGapCreate(
            chapter_id="01-chapter.md", gap_type="EXPERIMENT_NOT_RUN",
            title="experiment absent", searched_scope="checked appendix B"))
        session.commit()
        assert scoped.gap_type == "EXPERIMENT_NOT_RUN"


def test_false_satisfaction_distinctions_stay_explicit():
    # Symbol-existence vs behavior-verified and source-cited vs claim-
    # supported are reviewer judgments, not mechanical states: the vocabulary
    # keeps them distinct (UNSATISFIED vs NOT_ASSESSED vs waived-with-reason).
    assert "UNSATISFIED" in tech.REQUIREMENT_SATISFACTION
    assert "NOT_ASSESSED" in tech.REQUIREMENT_SATISFACTION
    assert "WAIVED_WITH_RATIONALE" in tech.REQUIREMENT_SATISFACTION
    assert "NOT_SEARCHED" in tech.GAP_TYPES
