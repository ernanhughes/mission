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


# ---------------------------------------------------------------------------
# Passage-level reference-review workflow (MC-QUALITY-04A-04-00 F).
#
# The 24 frozen passages are source-verified but their semantic reference
# labels remain ai_draft_awaiting_human_review. These packets present each
# passage with sliced (never paraphrased) context and the provisional draft
# label for independent review. Verdicts and provenance live in the packet;
# precision/recall stay NOT_MEASURED until human labels exist
# (adjudicated_metrics above already excludes unassessed claims).

REVIEW_VERDICTS = (
    "ACCEPT_LABEL", "CORRECT_LABEL", "REJECT_LABEL", "SPLIT_CLAIM",
    "MERGE_DUPLICATE", "NEEDS_CONTEXT", "ABSTAIN",
)

REVIEW_PROVENANCE = (
    "HUMAN_REVIEW", "AI_ASSISTED_REVIEW", "AWAITING_REVIEW",
)


def build_review_packet(passage: dict, chapter_text: str, live_revision: str,
                        *, context_chars: int = 800) -> dict:
    """Assemble one passage review packet. Slices context, never paraphrases.

    Coordinate convention: chapter_text must be DECODED text (raw bytes
    decoded as UTF-8 with CRLF preserved), because frozen char_spans are
    decoded offsets. Context spans are therefore decoded coordinates too.
    """
    text = passage.get("text", "")
    lo, hi = passage.get("char_span", [0, 0])
    segment = chapter_text[lo:hi] if 0 <= lo < hi <= len(chapter_text) else ""
    match = bool(segment) and segment == text
    excerpt_at = chapter_text.find(text) if text else -1
    if excerpt_at >= 0:
        clo = max(0, excerpt_at - context_chars)
        chi = min(len(chapter_text), excerpt_at + len(text) + context_chars)
        plo = chapter_text.rfind("\n\n", 0, clo)
        plo = 0 if plo < 0 else plo + 2
        phi = chapter_text.find("\n\n", chi)
        phi = len(chapter_text) if phi < 0 else phi
        context = {"text": chapter_text[plo:phi], "char_span": [plo, phi],
                   "passage_offset_in_context": [excerpt_at - plo,
                                                 excerpt_at + len(text) - plo]}
    else:
        context = {"text": "", "char_span": [0, 0], "passage_offset_in_context": [0, 0]}
    return {
        "passage_id": passage.get("passage_id", ""),
        "chapter_id": passage.get("chapter_id", ""),
        "frozen_char_span": [lo, hi],
        "frozen_text": text,
        "live_chapter_revision": live_revision,
        "integrity": {
            "span_in_range": 0 <= lo < hi <= len(chapter_text),
            "text_matches_frozen_span": match,
            "excerpt_anchored": excerpt_at >= 0,
            "excerpt_multiple_occurrences": chapter_text.count(text) > 1 if excerpt_at >= 0 else False,
        },
        "surrounding_source_context": context,
        "draft_label_provisional": passage.get("draft_label", {}),
        "draft_provenance": passage.get("label_provenance", "ai_draft_awaiting_human_review"),
        "reviews": [],
        "status": "AWAITING_REVIEW",
    }


def record_review_verdict(packet: dict, *, verdict: str, reviewer: str,
                          rationale: str = "") -> dict:
    """Append one review verdict to a packet (pure; returns the packet).

    Provenance rule: HUMAN_REVIEW is recorded only when the reviewer string
    identifies a human ("human:<id>"); agent-assisted work is AI_ASSISTED.
    Disagreements are preserved as a list, never auto-merged. A packet with
    any HUMAN_REVIEW verdict leaves AWAITING_REVIEW; mixed or provisional
    states stay explicit.
    """
    if verdict not in REVIEW_VERDICTS:
        raise ValueError(f"unknown review verdict {verdict!r}")
    if not reviewer or not reviewer.strip():
        raise ValueError("reviewer identity is required")
    provenance = "HUMAN_REVIEW" if reviewer.startswith("human:") else "AI_ASSISTED_REVIEW"
    updated = dict(packet)
    reviews = list(updated.get("reviews", []))
    reviews.append({"verdict": verdict, "reviewer": reviewer,
                    "reviewer_provenance": provenance, "rationale": rationale[:500]})
    updated["reviews"] = reviews
    if any(r["reviewer_provenance"] == "HUMAN_REVIEW" for r in reviews):
        updated["status"] = "HUMAN_REVIEWED"
    else:
        updated["status"] = "AI_ASSISTED_REVIEW"
    return updated


def review_status(packets: list[dict]) -> dict:
    """Aggregate review-state counts for the benchmark status artifact."""
    counts: dict[str, int] = {}
    for packet in packets:
        status = packet.get("status", "AWAITING_REVIEW")
        counts[status] = counts.get(status, 0) + 1
    return {"packets_total": len(packets), "by_status": counts,
            "precision": "NOT_MEASURED", "recall": "NOT_MEASURED",
            "note": ("Semantic precision/recall require completed HUMAN_REVIEWED "
                     "labels; provisional and AI-assisted states never qualify.")}
