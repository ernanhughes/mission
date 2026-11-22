"""Versioned blog-editorial rubric (MC-WEBSITES-POSTS-01).

A dedicated blog-writing rubric, not the book-chapter rubric. Overall score
is the plain sum of dimension scores (maximum 1000). Editorial evaluation is
kept distinct from independent factual verification: reading an article never
establishes that its external claims are true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RUBRIC_ID = "blog-editorial-v1"
RUBRIC_VERSION = 1
PROMPT_VERSION = "1"
MAX_TOTAL = 1000

AGGREGATION_METHOD = "sum_dimensions_v1"

EVALUATION_DECISIONS = ("ACCEPT", "REJECT", "DEFER", "INVESTIGATE")


@dataclass(frozen=True, slots=True)
class RubricDimension:
    id: str
    label: str
    max_points: int
    guidance: str


DIMENSIONS: tuple[RubricDimension, ...] = (
    RubricDimension(
        id="thesis_purpose",
        label="Thesis and purpose",
        max_points=150,
        guidance="A clear, specific thesis stated early; the reader knows what the article is for and what it will deliver.",
    ),
    RubricDimension(
        id="substance_depth",
        label="Substance and depth",
        max_points=175,
        guidance="Real content beyond surface observations: mechanisms, trade-offs, worked detail, or novel framing — not filler.",
    ),
    RubricDimension(
        id="argument_reasoning",
        label="Argument and reasoning",
        max_points=150,
        guidance="Claims follow from stated premises; objections are anticipated; logic holds under scrutiny.",
    ),
    RubricDimension(
        id="evidence_attribution",
        label="Evidence and attribution",
        max_points=150,
        guidance="Assertions that need support carry it: data, citations, code, or clearly-marked reasoning. Sources are attributed, not asserted.",
    ),
    RubricDimension(
        id="structure_flow",
        label="Structure and flow",
        max_points=100,
        guidance="Headings earn their place; sections build in order; transitions carry the reader forward.",
    ),
    RubricDimension(
        id="clarity_precision",
        label="Clarity and precision",
        max_points=100,
        guidance="Exact language; defined terms; no hedging where commitment is owed and no false precision where evidence is thin.",
    ),
    RubricDimension(
        id="reader_value",
        label="Reader value",
        max_points=100,
        guidance="A practitioner finishes able to do or decide something they could not before.",
    ),
    RubricDimension(
        id="style_economy",
        label="Style and economy",
        max_points=75,
        guidance="No wasted words; voice serves the argument; every paragraph justifies its length.",
    ),
)


def dimension_map() -> dict[str, RubricDimension]:
    return {dim.id: dim for dim in DIMENSIONS}


def validate_scores(scores: dict[str, Any]) -> tuple[int, dict[str, int], list[str]]:
    """Validate dimension scores. Returns (total, cleaned, errors).

    Unknown dimensions are errors, never silently dropped. Out-of-range
    values are errors, never clamped.
    """
    known = dimension_map()
    errors: list[str] = []
    cleaned: dict[str, int] = {}
    for key, value in (scores or {}).items():
        dim = known.get(str(key))
        if dim is None:
            errors.append(f"Unknown rubric dimension: {key!r}")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"Non-numeric score for dimension {key!r}: {value!r}")
            continue
        points = int(value)
        if float(value) != points:
            errors.append(f"Non-integral score for dimension {key!r}: {value!r}")
            continue
        if points < 0 or points > dim.max_points:
            errors.append(
                f"Score for dimension {key!r} out of range 0..{dim.max_points}: {points}"
            )
            continue
        cleaned[str(key)] = points
    missing = [dim.id for dim in DIMENSIONS if dim.id not in cleaned]
    if missing:
        errors.append(f"Missing dimension scores: {', '.join(missing)}")
    total = sum(cleaned.values()) if not errors else 0
    return total, cleaned, errors


def validate_total(total: int) -> bool:
    return 0 <= int(total) <= MAX_TOTAL


def quote_anchored(source_text: str, quote: str) -> bool:
    """Check a finding's quoted passage occurs verbatim in the source.

    Normalises whitespace only. A failed anchor must be reported as
    unanchored, never given a fabricated position.
    """
    if not quote or not quote.strip():
        return False
    normalise = " ".join(source_text.split())
    needle = " ".join(quote.split())
    return needle in normalise
