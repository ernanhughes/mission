"""PUB-08 evaluation recovery track 1 — probe-scoring instrument v0.2.

Type-aware deterministic replacement for the frozen-key containment scorer
(``run_eval_judges.score_probe``: casefolded whole-expected-substring rule).

Why the old rule is defective (development incidents F1/F2/F4, public set):
  - F2 key "8 match the label" vs correct "8 of the 10 answered test cases
    matched the label." — morphological variant (matched vs match) fails
    whole-string containment although the number, match-concept and label
    concept are all stated.
  - F4 key "...tokens and every call..." vs correct "...tokens, and every
    call..." — a presentation-level comma breaks containment although both
    quantity clauses are stated.
  - F1/F3/F5/F11/F12/E1-E3 correct paraphrases fail for the same class of
    reason (inserted content words, reordered clauses, punctuation).

v0.2 scores per probe ANSWER TYPE derived from the frozen key
(``probe-key.json``, read-only; key bytes never modified here):

  counts-pair (F1)   numbers bound to verbs; number-words accepted;
                     order-free; both clauses required.
  match-count (F2)   number 8 + match-stem (match/matched/correct);
                     wrong number or no match-concept fails.
  exact-payload (F3) compact-JSON containment of {"refund_approved": true};
                     identifiers case-sensitive, key order material,
                     internal JSON whitespace presentation-level; markdown
                     fences/backticks stripped (transport framing only).
  cost-latency (F4)  zero-token clause + under-4-microseconds clause;
                     units convertible (microseconds/us/4e-06 s).
  guarantee (F5)     structure-concept + correctness-concept + negator
                     scoping the correctness claim; lost negation fails.
  rate (F6)          0.148 + %|percent; wrong magnitude or bare number fails.
  range (F7)         26-80 + %|percent, both bounds; one bound fails.
  saturation (F8)    200 + label*; hedge optional (reader probe, not a
                     certainty gate); wrong number/unit fails.
  index-size (F9)    50 + MB (unit case-sensitive: MB != mb); sentence-case
                     "Around" is presentation-level and passes.
  dataset-win (F10)  2 + 3 + dataset*; wrong numbers or no dataset fails.
  ticket-pair (F11)  t11 + t60, exact lowercase, t11 before t60;
                     case change or reorder fails.
  schema-order (F12) refund_approved + reason, exact snake case, order
                     material; case change or reorder fails.
  epistemic (E1-E3)  negator + question concept; unnegated affirmation of
                     the denied claim fails.

Indiscriminate normalization is a defect: the calibration set
(``probe_scoring_v02_calibration.json``) proves every correct variant
passes AND every incorrect variant (wrong number/unit, lost negation,
altered modality, case-sensitive mismatch, misordered sequence, missing
concept) still fails.

Reuse-first provenance (Writer, read-only; nothing copied blind):
  - quantity-unit spirit: ``writer_runtime...revision.quantity_units``
    (``normalize_quantity_unit``/``quantity_unit_token``: case-sensitive
    unit symbols, plural/hyphen forms, NON_UNIT_WORDS). This module
    imports ``normalize_quantity_unit`` when importable and falls back
    to a frozen copy otherwise; equivalence is asserted in calibration.
  - number inventory spirit (digits + number-words, percentages, ranges):
    ``...revision.semantic_loss._extract_numbers`` /
    ``_normalize_number_words`` / ``_NUM_RE``.
  - negation/modality inventory: ``...semantic_loss._extract_markers``
    (must/should/may/cannot/can/never/not + two-word markers).
  - identifier inventory (case-sensitive snake/Camel): ``..._extract_identifiers``.
  - transport-framing-only recovery: ``models.typed_task`` laws 2/3/6/7
    (validation failure reported, never repaired, never redispatched) —
    recovery strips ONLY markdown fences/backticks (transport framing),
    never edits semantic content, never invents fields, never converts
    abstentions.
  - quote-verbatim discipline: ``publication_automation``
    ``validate_editorial_output`` / ``validate_review_output``.
  - controls seam: ``publication_attribution.attribute_finding`` +
    ``_judge_to_disposition`` mapping (reused in the replay script).

$0 / no-live-call: pure stdlib (+ optional read-only Writer import);
zero dispatches, zero spend. Held-out probes (F7-F12) are NOT used to
author these rules (development set = public probes incl. F1/F2/F4
incidents); held-out runs once, frozen, in the replay script.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INSTRUMENT_VERSION = "probe-scoring-v0.2"

# ---------------------------------------------------------------------------
# Optional reuse import (read-only): Writer quantity-unit normalizer.
# ---------------------------------------------------------------------------

_WRITER_QTY = None
try:
    _REPO = Path(__file__).resolve()
    for _cand in (
        _REPO.parents[5] / "writer" / "packages" / "writer-runtime",
    ):
        if (_cand / "writer_runtime" / "__init__.py").exists():
            if str(_cand) not in sys.path:
                sys.path.insert(0, str(_cand))
            break
    from writer_runtime.domains.artifact.artifact_engine.revision import (  # type: ignore
        quantity_units as _WRITER_QTY,
    )
except Exception:  # noqa: BLE001 - fallback is the frozen copy below
    _WRITER_QTY = None

#: Frozen fallback mirror of quantity_units semantics for the units this
#: instrument needs (used only when the Writer import above is unavailable;
#: calibration asserts fallback == Writer import where both exist).
_FALLBACK_UNITS = {
    "mb": "mb", "mbs": "mb",  # millibit: must differ from megabyte "MB"
    "gb": "GB", "gbs": "GB",
    "us": "us", "\u00b5s": "us", "\u03bcs": "us",
    "microsecond": "microseconds", "microseconds": "microseconds",
    "label": "labels", "labels": "labels",
    "ticket": "tickets", "tickets": "tickets",
    "dataset": "datasets", "datasets": "datasets",
}


def normalize_unit(unit: str) -> str | None:
    """Comparable unit token (Writer reuse-first, frozen fallback)."""
    if _WRITER_QTY is not None:
        try:
            return _WRITER_QTY.normalize_quantity_unit(unit)
        except Exception:  # noqa: BLE001 - fall through to frozen copy
            pass
    u = (unit or "").strip().strip(".,;:!?\"'`")
    if not u:
        return None
    if u == "MB":
        return "MB"
    if u in ("MB", "mb"):
        return u  # case-sensitive pair: megabyte vs millibit stay distinct
    low = u.lower()
    if low in ("mb",):
        return "mb"  # unreachable (handled above); kept explicit
    return _FALLBACK_UNITS.get(low, low if low not in (
        "has", "is", "are", "and", "the", "of", "a", "an") else None)


# ---------------------------------------------------------------------------
# Presentation-level normalization (transport framing only).
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITAL_RE = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
_BACKTICK_RE = re.compile(r"`([^`\n]*)`")
_WS_RE = re.compile(r"\s+")


def strip_transport_framing(text: str) -> str:
    """Remove markdown transport framing only (fences/backticks/emphasis).

    Never edits semantic content: no stemming, no stop-word removal, no
    unit conversion, no case folding here (case handled per answer type).
    """
    t = text or ""
    m = _FENCE_RE.match(t.strip())
    if m:
        t = m.group(1)
    t = _BACKTICK_RE.sub(r"\1", t)
    t = _MD_BOLD_RE.sub(r"\1", t)
    t = _MD_ITAL_RE.sub(r"\1", t)
    return t


def collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip())


def norm_ci(text: str) -> str:
    """Case-insensitive presentation form: collapsed whitespace + casefold."""
    return collapse_ws(text).casefold()


# ---------------------------------------------------------------------------
# Structured-response recovery (malformed fenced-JSON only).
# ---------------------------------------------------------------------------

_REQUIRED_PROBE_KEYS = {"probe_id", "answer"}
_REQUIRED_CHECKLIST_KEYS = {"criterion_id", "verdict"}
_REQUIRED_ASSIST_KEYS = {"pair", "question_id", "preferred"}


def recover_fenced_json(raw: str, required_keys: set[str]) -> dict:
    """Deterministically recover ONE fenced bare-JSON payload.

    Accepts: exactly one outer ``` / ```json fence pair (or bare JSON)
    around a single JSON object containing every required key.
    Refuses (returns {"ok": False, ...}, never invents): truncated input
    (ellipsis/pydantic elision markers), JSON parse failure, missing keys,
    non-object payloads. Truncation at ANY position is unrecoverable —
    a partial object is never completed.
    """
    result: dict = {"ok": False, "payload": None, "reason": ""}
    t = raw or ""
    if "..." in t:
        result["reason"] = "refused: truncation marker '...' — bytes incomplete"
        return result
    if "…" in t:
        result["reason"] = "refused: unicode ellipsis — bytes incomplete"
        return result
    m = _FENCE_RE.match(t.strip())
    inner = m.group(1) if m else t.strip()
    if not inner:
        result["reason"] = "refused: empty payload"
        return result
    try:
        obj = json.loads(inner)
    except Exception as exc:  # noqa: BLE001 - reported, never repaired
        result["reason"] = f"refused: JSON parse failed ({type(exc).__name__})"
        return result
    if not isinstance(obj, dict):
        result["reason"] = "refused: payload is not a JSON object"
        return result
    missing = [k for k in required_keys if k not in obj]
    if missing:
        result["reason"] = f"refused: missing keys {missing}"
        return result
    result.update(ok=True, payload=obj, reason="recovered: fenced/bare JSON parsed")
    return result


# ---------------------------------------------------------------------------
# Number words (frozen mirror of semantic_loss._NUMBER_WORDS subset).
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "twenty": 20, "thirty": 30,
    "fifty": 50, "sixty": 60, "eighty": 80, "hundred": 100,
}


def _numbers_in(text: str) -> list[float]:
    """Digit + number-word inventory (semantic_loss number spirit)."""
    t = norm_ci(strip_transport_framing(text))
    out: list[float] = []
    for m in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?", t):
        try:
            out.append(float(m.group(0)))
        except ValueError:
            continue
    for w, v in _NUMBER_WORDS.items():
        if re.search(r"\b" + re.escape(w) + r"\b", t):
            out.append(float(v))
    return out


def _has_number(text: str, want: float) -> bool:
    return any(abs(n - want) < 1e-9 for n in _numbers_in(text))


_NEG_RE = re.compile(
    r"\b(no|not|never|n't|neither|nor|unobserved|untested|"
    r"not_observed|cannot|can't|couldn't|didn't|doesn't|isn't|wasn't)\b",
    re.IGNORECASE,
)


def _has_negation(text: str) -> bool:
    return bool(_NEG_RE.search(strip_transport_framing(text or "")))


# ---------------------------------------------------------------------------
# Per-type scorers. Each returns (verdict, rule_id, evidence).
# verdict in {"correct", "incorrect"} — never abstain: abstentions live in
# the recorded response status, never converted by scoring.
# ---------------------------------------------------------------------------

def _score_F1(answer: str):
    t = norm_ci(strip_transport_framing(answer))
    m_ans = re.search(r"\banswer(?:ed|s|ing)?\b[^.]{0,40}?\b(ten|10)\b", t)
    m_dec = re.search(r"\bdeclin(?:ed|e|es)?\b[^.]{0,40}?\b(ten|10)\b", t)
    # also accept "returned None (declined) on the other 10" shape
    if not m_dec:
        m_dec = re.search(r"declin(?:ed|e|es)?[^.]{0,60}?\b(ten|10)\b", t)
    if m_ans and m_dec:
        return ("correct", "F1:counts-pair",
                f"answered->10, declined->10 in {answer[:80]!r}...")
    # wrong-number diagnosis for the reason string
    nums = _numbers_in(answer)
    return ("incorrect", "F1:counts-pair-missing",
            f"requires answered=10 AND declined=10; numbers seen={nums}")


def _score_F2(answer: str):
    t = norm_ci(strip_transport_framing(answer))
    has8 = _has_number(answer, 8)
    has_match = bool(re.search(r"\bmatch(?:ed|es|ing)?\b|\bcorrect\b", t))
    if has8 and has_match:
        return ("correct", "F2:number+match-stem",
                "8 + match/matched/correct present")
    return ("incorrect", "F2:number+match-stem-missing",
            f"requires 8 + match-stem; has8={has8} match={has_match}")


def _score_F3(answer: str):
    inner = strip_transport_framing(answer)
    compact = re.sub(r"\s+", "", inner)
    if '{"refund_approved":true}' in compact:
        return ("correct", "F3:exact-payload",
                "compact JSON payload present, identifiers case-exact, order exact")
    return ("incorrect", "F3:exact-payload-missing",
            "compact {\"refund_approved\":true} absent "
            "(case/order/value must be exact; single quotes fail)")


def _score_F4(answer: str):
    inner = strip_transport_framing(answer)
    t = norm_ci(inner)
    zero_tok = bool(re.search(r"\b(zero|0|no)\s+tokens?\b", t))
    micro = ("microsecond" in t or re.search(r"(?<![\w])(\u00b5s|\u03bcs|us)\b", t)
             is not None)
    has4 = _has_number(answer, 4)
    under = bool(re.search(r"\b(under|below|less than|<|took under)\b", t)) or "<" in inner
    sci = bool(re.search(r"<\s*4\s*e-0*6", inner.replace(" ", "")))
    latency = (micro and has4 and under) or sci
    if zero_tok and latency:
        return ("correct", "F4:zero-tokens+latency",
                "zero-token clause + under-4-microseconds clause (unit-convertible)")
    return ("incorrect", "F4:clause-missing",
            f"requires zero-tokens AND under-4us; zero={zero_tok} latency={latency}")


def _score_F5(answer: str):
    inner = strip_transport_framing(answer)
    t = norm_ci(inner)
    has_struct = "structur" in t
    # Frozen correctness-concept synonyms (key: "correctness"): correct*,
    # right (= "the right answer"), accurate/accuracy. Minimal set: each
    # still requires the structure concept AND a scoping negator, so
    # "guarantees structure and accuracy" (no negator) still fails.
    has_corr = bool(re.search(r"\bcorrect\w*|\bright\b|\baccura\w*", t))
    has_neg = _has_negation(answer)
    toks = re.sub(r"[^a-z'\s]", " ", t).split()
    scoped = False
    for i, tok in enumerate(toks):
        if (tok.startswith("correct") or tok in ("right", "accuracy", "accurate")):
            window = toks[max(0, i - 12):i]
            if any(w in ("not", "n't", "never", "no", "cannot", "rather")
                   or w.endswith("n't") for w in window):
                scoped = True
    if has_struct and has_corr and scoped:
        return ("correct", "F5:structure+negated-correctness",
                "structure + correctness + negator scoping correctness")
    return ("incorrect", "F5:concept-or-negation-missing",
            f"requires structure+correctness+negation; s={has_struct} "
            f"c={has_corr} neg-scoped={has_neg and scoped}")


def _score_F6(answer: str):
    inner = strip_transport_framing(answer)
    t = norm_ci(inner)
    if re.search(r"0\.148\s*(%|percent)", t):
        return ("correct", "F6:rate+unit", "0.148 + %/percent present")
    return ("incorrect", "F6:rate+unit-missing",
            f"requires 0.148 with % unit; numbers={_numbers_in(answer)}")


def _score_F7(answer: str):
    inner = strip_transport_framing(answer)
    t = norm_ci(inner)
    if re.search(r"26\s*(?:-|–|—|to)\s*80\s*(%|percent)", t):
        return ("correct", "F7:range+bounds+unit",
                "26-80 bounds + %/percent present")
    return ("incorrect", "F7:range-missing",
            f"requires both bounds 26,80 + %; numbers={_numbers_in(answer)}")


def _score_F8(answer: str):
    t = norm_ci(strip_transport_framing(answer))
    if _has_number(answer, 200) and re.search(r"\blabels?\b", t):
        return ("correct", "F8:number+unit", "200 + label(s) present")
    return ("incorrect", "F8:number+unit-missing",
            "requires 200 + label(s)")


def _score_F9(answer: str):
    inner = strip_transport_framing(answer)
    # MB is case-sensitive (Writer quantity_units: MB/Mb differ).
    if _has_number(answer, 50) and re.search(r"(?<![\w])MB(?![\w])", inner):
        return ("correct", "F9:number+case-sensitive-unit",
                "50 + MB (case-exact) present; sentence-case Around is "
                "presentation-level")
    return ("incorrect", "F9:number+unit-missing",
            "requires 50 + MB case-exact (mb/GB fail)")


def _score_F10(answer: str):
    t = norm_ci(strip_transport_framing(answer))
    if (_has_number(answer, 2) and _has_number(answer, 3)
            and re.search(r"\bdatasets?\b", t)):
        return ("correct", "F10:numbers+concept", "2 + 3 + dataset(s) present")
    return ("incorrect", "F10:numbers+concept-missing",
            "requires 2, 3 + dataset(s)")


def _score_F11(answer: str):
    inner = strip_transport_framing(answer)
    i1 = inner.find("t11")
    i2 = inner.find("t60")
    if i1 != -1 and i2 != -1 and i1 < i2:
        # reject case variants: T11/T60 anywhere is a case-sensitive mismatch
        if re.search(r"T11|T60", inner):
            return ("incorrect", "F11:case-mismatch",
                    "uppercase ticket identifier present (case-sensitive)")
        return ("correct", "F11:ordered-identifiers",
                "t11 + t60 exact lowercase, order material, satisfied")
    if re.search(r"T11|T60", inner):
        return ("incorrect", "F11:case-mismatch",
                "uppercase ticket identifier (case-sensitive)")
    return ("incorrect", "F11:identifiers-or-order-missing",
            f"requires t11 before t60 lowercase; i1={i1} i2={i2}")


def _score_F12(answer: str):
    inner = strip_transport_framing(answer)
    i1 = inner.find("refund_approved")
    i2 = inner.find("reason")
    if i1 != -1 and i2 != -1 and i1 < i2:
        if re.search(r"Refund_approved|REFUND_APPROVED|Reason|REASON", inner):
            return ("incorrect", "F12:case-mismatch",
                    "key case altered (snake_case is case-sensitive)")
        return ("correct", "F12:ordered-keys",
                "refund_approved before reason, case-exact")
    if re.search(r"Refund_approved|REFUND_APPROVED|Reason|REASON", inner):
        return ("incorrect", "F12:case-mismatch",
                "key case altered (snake_case is case-sensitive)")
    return ("incorrect", "F12:keys-or-order-missing",
            f"requires refund_approved before reason; i1={i1} i2={i2}")


def _epistemic(answer: str, concepts: list[str], affirm_terms: list[str],
                rule: str):
    inner = strip_transport_framing(answer)
    t = norm_ci(inner)
    has_neg = _has_negation(answer)
    has_concept = any(c in t for c in concepts)
    # affirmation check: a sentence asserting the denied claim with an
    # AFFIRM verb (measure/test/run/documented) and no negator. Merely
    # observing *other* facts ("payload size is observed") is not an
    # affirmation of the denied claim.
    affirm = False
    for sent in re.split(r"[.!?;]\s*", t):
        if not sent.strip():
            continue
        if any(w in sent for w in affirm_terms):
            if not _NEG_RE.search(sent):
                affirm = True
    if has_neg and has_concept and not affirm:
        return ("correct", rule, "negator + concept, no unnegated affirmation")
    if affirm and not has_neg:
        return ("incorrect", rule + "-affirmed",
                "states the denied claim without negation")
    return ("incorrect", rule + "-missing",
            f"requires negator + concept; neg={has_neg} concept={has_concept}")


def _score_E1(answer: str):
    return _epistemic(answer, ["run", "ran", "executed", "not_observed",
                               "observed", "model-backed", "model backed"],
                      ["run", "ran", "executed"], "E1:negated-run")


def _score_E2(answer: str):
    return _epistemic(answer, ["documented", "third-party", "third party",
                               "3p", "claim"], ["documented"],
                      "E2:negated-documented")


def _score_E3(answer: str):
    return _epistemic(answer, ["measur", "untested", "untest", "observed",
                               "overhead", "prediction"], ["measur", "test"],
                      "E3:negated-measured")


_SCORERS = {
    "F1": _score_F1, "F2": _score_F2, "F3": _score_F3, "F4": _score_F4,
    "F5": _score_F5, "F6": _score_F6, "F7": _score_F7, "F8": _score_F8,
    "F9": _score_F9, "F10": _score_F10, "F11": _score_F11, "F12": _score_F12,
    "E1": _score_E1, "E2": _score_E2, "E3": _score_E3,
}


def score_probe(probe_id: str, answer: str) -> dict:
    """Score one probe answer. Pure + deterministic. Never abstains."""
    fn = _SCORERS.get(probe_id)
    if fn is None:
        raise ValueError(f"unknown probe {probe_id!r}")
    verdict, rule, evidence = fn(answer or "")
    return {"instrument": INSTRUMENT_VERSION, "probe_id": probe_id,
            "verdict": verdict, "rule": rule, "evidence": evidence}
