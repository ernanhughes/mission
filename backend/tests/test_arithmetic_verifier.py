"""MC-PRAXIS-15 arithmetic verifier fixtures (engineering, not ground truth)."""
from __future__ import annotations

from mission_control.technical.arithmetic_verifier import (
    verify_proposition,
)


def _base(**overrides) -> dict:
    proposition = {
        "claim_id": "tclaim:0123456789abcdef",
        "source_revision": "rev",
        "source_span": "line 1",
        "kind": "equality",
        "left": {"op": "add", "left": {"const": "4"},
                 "right": {"op": "div", "left": {"const": "16"},
                           "right": {"const": "128"}}},
        "right": {"const": "4.125"},
        "tolerance": "0.0001",
        "units": "bits_per_weight",
        "fidelity": "candidate",
        "evidence_refs": ["chapter.md:1"],
    }
    proposition.update(overrides)
    return proposition


def test_true_and_false_equality() -> None:
    assert verify_proposition(_base())["proposition_holds"] is True
    assert verify_proposition(_base(right={"const": "4.2"}))[
        "proposition_holds"] is False


def test_percent_and_tolerance_boundary() -> None:
    base = _base(kind="percent", numerator="2", denominator="2304",
                 expected="0.09", tolerance="0.005")
    assert verify_proposition(base)["proposition_holds"] is True
    tight = {**base, "tolerance": "0.001"}
    assert verify_proposition(tight)["proposition_holds"] is False


def test_product_ratio_interval_and_comparison() -> None:
    assert verify_proposition(_base(kind="product", factors=["3", "5", "6"],
                                    expected="90", tolerance="0"))[
        "proposition_holds"] is True
    assert verify_proposition(_base(kind="ratio", numerator="186",
                                    denominator="127", expected="1.46",
                                    tolerance="0.005"))["proposition_holds"] is True
    assert verify_proposition(_base(kind="interval", value="0.25",
                                    low="0.185", high="0.408"))[
        "proposition_holds"] is True
    assert verify_proposition(_base(kind="comparison", op=">",
                                    left={"const": "2"},
                                    right={"const": "1"}))[
        "proposition_holds"] is True


def test_division_by_zero_and_unsupported_operator() -> None:
    result = verify_proposition(_base(kind="ratio", numerator="1",
                                      denominator="0", expected="1",
                                      tolerance="0"))
    assert result["execution_status"] in ("error", "unsupported")
    assert result["proposition_holds"] is None

    result = verify_proposition(_base(kind="equality",
                                      left={"op": "eval", "args": []},
                                      right={"const": "1"}))
    assert result["execution_status"] == "unsupported"
    assert "unsupported operator" in " ".join(result["errors"])


def test_oversized_and_malformed_inputs_are_rejected() -> None:
    result = verify_proposition(_base(left={"const": "9" * 40},
                                      right={"const": "1"}))
    assert result["execution_status"] in ("error", "unsupported")
    result = verify_proposition({"kind": "equality"})
    assert result["execution_status"] == "unsupported"
    assert result["proposition_holds"] is None


def test_fidelity_separates_proposition_from_claim_truth() -> None:
    candidate = verify_proposition(_base())
    assert candidate["proposition_holds"] is True
    assert candidate["claim_level_truth"] is None
    adjudicated = verify_proposition(_base(fidelity="adjudicated"))
    assert adjudicated["claim_level_truth"] is True


def test_deterministic_replay_digest() -> None:
    first = verify_proposition(_base())
    second = verify_proposition(_base())
    assert first["proposition_digest"] == second["proposition_digest"]
    assert first["computed_exact"] == second["computed_exact"]
