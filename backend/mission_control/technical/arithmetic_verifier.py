"""Bounded arithmetic verifier for registered technical claims.

No eval, imports, filesystem access or arbitrary code. Only a small explicit
proposition language using exact rational arithmetic.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

VERIFIER_VERSION = "mc-arithmetic-verifier-v1"
MAX_NODES = 32
MAX_DEPTH = 8
MAX_CONST_LENGTH = 32
MAX_EXPONENT = 16
MAX_DENOMINATOR = 10**12
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


class PropositionError(ValueError):
    pass


def _number(value: Any) -> Fraction:
    if not isinstance(value, str):
        raise PropositionError("numbers must be decimal strings")
    text = value.strip()
    if not text or len(text) > MAX_CONST_LENGTH or not _NUMBER.match(text):
        raise PropositionError(f"invalid numeric literal: {value!r}")
    try:
        decimal = Decimal(text)
    except InvalidOperation as exc:
        raise PropositionError(f"invalid numeric literal: {value!r}") from exc
    if not decimal.is_finite():
        raise PropositionError("non-finite numbers are not supported")
    if abs(decimal) > Decimal("1e24"):
        raise PropositionError("numeric magnitude exceeds limit")
    return Fraction(decimal)


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _eval(expr: Any, *, depth: int = 0, nodes: list[int] | None = None) -> Fraction:
    nodes = nodes if nodes is not None else [0]
    nodes[0] += 1
    if nodes[0] > MAX_NODES:
        raise PropositionError("expression node limit exceeded")
    if depth > MAX_DEPTH:
        raise PropositionError("expression depth limit exceeded")
    if not isinstance(expr, dict):
        raise PropositionError("expression must be an object")
    if "const" in expr:
        return _number(expr["const"])
    op = expr.get("op")
    if op not in {"add", "sub", "mul", "div", "pow"}:
        raise PropositionError(f"unsupported operator: {op!r}")
    if op == "pow":
        base = _eval(expr.get("base"), depth=depth + 1, nodes=nodes)
        exponent = expr.get("exponent")
        if not isinstance(exponent, int) or isinstance(exponent, bool):
            raise PropositionError("pow exponent must be an integer")
        if exponent < 0 or exponent > MAX_EXPONENT:
            raise PropositionError("pow exponent outside 0..16")
        return base ** exponent
    left = _eval(expr.get("left"), depth=depth + 1, nodes=nodes)
    right = _eval(expr.get("right"), depth=depth + 1, nodes=nodes)
    if op == "add":
        return left + right
    if op == "sub":
        return left - right
    if op == "mul":
        return left * right
    if right == 0:
        raise PropositionError("division by zero")
    if abs(right) > MAX_DENOMINATOR:
        raise PropositionError("denominator exceeds limit")
    return left / right


def _tolerance(value: Any) -> Fraction:
    tolerance = _number(value)
    if tolerance < 0:
        raise PropositionError("tolerance must be non-negative")
    return tolerance


def validate_proposition(proposition: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(proposition, dict):
        return ["proposition must be an object"]
    for key in ("claim_id", "source_revision", "source_span", "kind"):
        if not proposition.get(key):
            errors.append(f"{key} is required")
    if proposition.get("fidelity") not in ("candidate", "adjudicated"):
        errors.append("fidelity must be candidate or adjudicated")
    if not isinstance(proposition.get("evidence_refs"), list):
        errors.append("evidence_refs must be a list")
    kind = proposition.get("kind")
    try:
        if kind == "equality":
            _eval(proposition.get("left"))
            _eval(proposition.get("right"))
            _tolerance(proposition.get("tolerance", "0"))
        elif kind == "product":
            factors = proposition.get("factors")
            if not isinstance(factors, list) or not factors:
                errors.append("product factors must be a non-empty list")
            else:
                for factor in factors:
                    _number(factor)
            _number(proposition.get("expected"))
            _tolerance(proposition.get("tolerance", "0"))
        elif kind == "ratio":
            denominator = _number(proposition.get("denominator"))
            if denominator == 0:
                errors.append("ratio denominator is zero")
            _number(proposition.get("numerator"))
            _number(proposition.get("expected"))
            _tolerance(proposition.get("tolerance", "0"))
        elif kind == "percent":
            denominator = _number(proposition.get("denominator"))
            if denominator == 0:
                errors.append("percent denominator is zero")
            _number(proposition.get("numerator"))
            _number(proposition.get("expected"))
            _tolerance(proposition.get("tolerance", "0"))
        elif kind == "interval":
            value = _number(proposition.get("value"))
            low = _number(proposition.get("low"))
            high = _number(proposition.get("high"))
            if low > high:
                errors.append("interval low exceeds high")
        elif kind == "comparison":
            if proposition.get("op") not in {"<", "<=", ">", ">=", "=="}:
                errors.append("unsupported comparison operator")
            _eval(proposition.get("left"))
            _eval(proposition.get("right"))
        else:
            errors.append(f"unsupported proposition kind: {kind!r}")
    except PropositionError as exc:
        errors.append(str(exc))
    return errors


def verify_proposition(proposition: dict[str, Any]) -> dict[str, Any]:
    errors = validate_proposition(proposition)
    if errors:
        return {
            "schema": "mc-arithmetic-verification.v1",
            "verifier_version": VERIFIER_VERSION,
            "proposition_digest": _digest(proposition),
            "execution_status": "unsupported" if any(
                "unsupported" in error or "must be" in error or "required" in error
                for error in errors) else "error",
            "proposition_holds": None,
            "claim_level_truth": None,
            "errors": errors,
            "assumptions": [],
            "limitations": ["No computation was performed."],
            "evidence_refs": proposition.get("evidence_refs", []),
        }
    kind = proposition["kind"]
    try:
        if kind == "equality":
            left = _eval(proposition["left"])
            right = _eval(proposition["right"])
            computed = left - right
            tolerance = _tolerance(proposition.get("tolerance", "0"))
            holds = abs(computed) <= tolerance
            exact = left
            expected = right
        elif kind == "product":
            exact = Fraction(1)
            for factor in proposition["factors"]:
                exact *= _number(factor)
            expected = _number(proposition["expected"])
            holds = abs(exact - expected) <= _tolerance(
                proposition.get("tolerance", "0"))
        elif kind == "ratio":
            exact = _number(proposition["numerator"]) / _number(
                proposition["denominator"])
            expected = _number(proposition["expected"])
            holds = abs(exact - expected) <= _tolerance(
                proposition.get("tolerance", "0"))
        elif kind == "percent":
            exact = _number(proposition["numerator"]) / _number(
                proposition["denominator"]) * 100
            expected = _number(proposition["expected"])
            holds = abs(exact - expected) <= _tolerance(
                proposition.get("tolerance", "0"))
        elif kind == "interval":
            exact = _number(proposition["value"])
            low = _number(proposition["low"])
            high = _number(proposition["high"])
            expected = None
            holds = low <= exact <= high
        elif kind == "comparison":
            left = _eval(proposition["left"])
            right = _eval(proposition["right"])
            exact = left
            expected = right
            holds = {
                "<": left < right, "<=": left <= right,
                ">": left > right, ">=": left >= right,
                "==": left == right,
            }[proposition["op"]]
        else:  # pragma: no cover - validate_proposition guards
            raise PropositionError("unsupported proposition")
    except PropositionError as exc:
        return {
            "schema": "mc-arithmetic-verification.v1",
            "verifier_version": VERIFIER_VERSION,
            "proposition_digest": _digest(proposition),
            "execution_status": "error",
            "proposition_holds": None,
            "claim_level_truth": None,
            "errors": [str(exc)],
            "assumptions": [],
            "limitations": ["No computation was performed."],
            "evidence_refs": proposition.get("evidence_refs", []),
        }
    decimal_value = float(exact) if exact.denominator else float("nan")
    result = {
        "schema": "mc-arithmetic-verification.v1",
        "verifier_version": VERIFIER_VERSION,
        "proposition_digest": _digest(proposition),
        "proposition_kind": kind,
        "execution_status": "succeeded",
        "proposition_holds": bool(holds),
        "computed_exact": f"{exact.numerator}/{exact.denominator}",
        "computed_decimal": format(Decimal(decimal_value), ".12g")
        if decimal_value == decimal_value else "nan",
        "expected": None if expected is None else f"{expected.numerator}/{expected.denominator}",
        "units": proposition.get("units") or None,
        "tolerance": proposition.get("tolerance", "0"),
        "assumptions": [
            "Operands are interpreted as exact decimal/rational values.",
            "Units are asserted by the proposition; no unit conversion is performed.",
            "The proposition is a candidate interpretation unless fidelity is adjudicated.",
        ],
        "limitations": [
            "The verifier checks the formal proposition, not the source claim's fidelity.",
            "A correct computation does not validate the measurement behind the numbers.",
        ],
        "claim_level_truth": (
            bool(holds) if proposition.get("fidelity") == "adjudicated" else None),
        "evidence_refs": proposition.get("evidence_refs", []),
        "errors": [],
    }
    return result
