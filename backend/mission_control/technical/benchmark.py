"""Paired-strategy extraction benchmark (MC-QUALITY-04A-03C, preparation).

Deterministic scoring only. Automated metrics cover span anchoring,
quotation validity, duplication and coverage. Precision/recall against
labelled passages require a human adjudication file; unadjudicated claims
are reported as unassessed, never counted as correct.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def overlaps(a_start: int | None, a_end: int | None, b_start: int, b_end: int) -> bool:
    if a_start is None or a_end is None:
        return False
    return a_start < b_end and a_end > b_start


def automated_metrics(passages: list[dict], claims: list[dict]) -> dict:
    """Span/quote/duplicate metrics. No human judgment involved."""
    anchored = [c for c in claims
                if c.get("source_char_start") is not None and c.get("source_char_end") is not None]
    total = len(claims)
    exact = sum(1 for c in claims if c.get("anchor_method") == "exact")
    normalized = sum(1 for c in claims if c.get("anchor_method") == "normalized")
    unanchored = total - len(anchored)
    valid_quotes = sum(1 for c in claims if c.get("quote_validated"))
    # Duplicate candidates: same normalized text or same excerpt.
    seen_text: dict[str, str] = {}
    seen_quote: dict[str, str] = {}
    dup_pairs = 0
    for c in claims:
        key_t, key_q = norm(c.get("claim_text")), norm(c.get("source_excerpt"))
        if key_t and key_t in seen_text:
            dup_pairs += 1
        else:
            seen_text.setdefault(key_t, c.get("id", ""))
        if key_q and key_q in seen_quote:
            dup_pairs += 1
        else:
            seen_quote.setdefault(key_q, c.get("id", ""))
    # Passage hit coverage: fraction of passages touched by >=1 anchored claim.
    hits = 0
    for passage in passages:
        lo, hi = passage["char_span"]
        if any(overlaps(c.get("source_char_start"), c.get("source_char_end"), lo, hi)
               for c in anchored):
            hits += 1
    # Line-location completeness among anchored claims.
    with_lines = sum(1 for c in anchored
                     if c.get("source_start_line") is not None
                     and c.get("source_end_line") is not None)
    return {
        "claims_total": total,
        "anchored": len(anchored),
        "anchor_exact": exact,
        "anchor_normalized": normalized,
        "unanchored": unanchored,
        "quote_validated": valid_quotes,
        "quote_validity_rate": (valid_quotes / total) if total else None,
        "duplicate_candidate_pairs": dup_pairs,
        "passages_total": len(passages),
        "passages_touched": hits,
        "passage_hit_rate": (hits / len(passages)) if passages else None,
        "anchored_with_lines": with_lines,
    }


def adjudicated_metrics(passages: list[dict], claims: list[dict],
                        adjudications: list[dict]) -> dict:
    """Precision/recall from a human adjudication file.

    Each adjudication: {claim_id, passage_id, verdict} with verdict in
    {supports, partial, unrelated}. Claims without adjudication are
    unassessed and excluded from both denominators; the report states
    the unassessed count explicitly.
    """
    by_claim = {c.get("id"): c for c in claims}
    passage_assertions = {p["passage_id"]: p.get("draft_label", {}).get("n_assertions", 0)
                          for p in passages}
    assessed = unassessed = supports = partial = 0
    covered: dict[str, int] = {}
    for adjudication in adjudications:
        verdict = adjudication.get("verdict")
        if verdict not in ("supports", "partial", "unrelated"):
            continue
        assessed += 1
        if verdict == "supports":
            supports += 1
        elif verdict == "partial":
            partial += 1
        if verdict in ("supports", "partial"):
            covered[adjudication.get("passage_id", "")] = \
                covered.get(adjudication.get("passage_id", ""), 0) + 1
    judged_ids = {a.get("claim_id") for a in adjudications
                  if a.get("verdict") in ("supports", "partial", "unrelated")}
    unassessed = sum(1 for c in claims if c.get("id") not in judged_ids)
    total_assertions = sum(passage_assertions.values())
    # Recall denominator uses labelled assertions; recall is reported only
    # when every passage with assertions has adjudication coverage.
    return {
        "claims_assessed": assessed,
        "claims_unassessed": unassessed,
        "precision_supports": (supports / assessed) if assessed else None,
        "precision_supports_or_partial": ((supports + partial) / assessed) if assessed else None,
        "labelled_assertions": total_assertions,
        "assertions_covered": sum(covered.values()),
        "recall_note": ("recall requires full adjudication coverage; "
                        f"{unassessed} claims unassessed" if unassessed
                        else "full adjudication coverage"),
    }


def comparison_report(strategy_a: dict, strategy_b: dict) -> dict:
    """Head-to-head table from two metric dicts. Measured values only;
    missing inputs stay null, never zero-filled."""
    rows = {}
    keys = set(strategy_a) | set(strategy_b)
    for key in sorted(keys):
        rows[key] = {"A": strategy_a.get(key), "B": strategy_b.get(key)}
    return {"metrics": rows,
            "note": "Unmeasured or unassessed cells are null, not zero."}
