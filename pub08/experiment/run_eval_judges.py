"""PUB-08 batch 7a — eval model-judges runner (coordinator-executed, $0 here).

Executes the model-mediated evaluation dimensions over the batch-6
blind pack (``pub08/experiment/eval/blind-pack.json``:
T1=B1/T2=A1/T3=H/T4=O, seed 20261125):

- 8-criterion editorial checklist x N labeled texts (default_haiku_go),
  verdict + verbatim quote or explicit abstain;
- 12 fact + 3 epistemic probes x N labeled texts with frozen-key
  scoring (9 public + 6 held-out; held-out runs ONCE: the runner
  refuses when ``probe-key.json`` consumption ``model_reader_runs`` != 0,
  consumes (writes back 1) before dispatching, then runs once);
- NC2/NC3/NC7a control judgements x N labeled texts through the batch-1
  attribution builder's injected-judge seam (live judge dispatches via
  run_typed_task; dispatch failure/malformed verdict fail-closes to
  UNRESOLVED_ATTRIBUTION, recorded, never retried);
- 30 adjudication assists: 6 blind label-pairs x 5 frozen pairwise
  questions (top-level list, not per text).

THIS FILE PERFORMS LIVE DISPATCHES WHEN RUN AS ``__main__``. It is
written (not executed) in batch 7a and executed later by the coordinator
in a credential-bearing shell. Importing it is side-effect free: all
live wiring (``writer_runtime``, ``writer_cli``, batch-1 fixture module)
is lazy inside ``main()``. The batch-7a fake-gate
(``tests/core/test_pub08_eval_judges_gate.py``) imports only the pure
helpers/builders with fake dispatch callables: zero live calls.

Production seam (identical shape to the ``transform automate`` live
path): ``run_typed_task`` through ``publication_automation.dispatch_task``
via a ``_dispatch`` closure with ``domain="publication"``,
``operation_id=<item-id>``, ``stage_id="pub08-eval"``. One shot per item:
a malformed/truncated/failed dispatch is a recorded abstain/fail, never
retried. Route is ``default_haiku_go`` ONLY.

Hard stops (all fail-closed with the exact position):
  1. aggregate + projection > $1.00 (priors + completed actuals +
     $0.16 worst-case projection, via the batch-1 spend wrapper
     ``publication_spend.check_aggregate_spend_guard``) — checked before
     the first dispatch and re-checked before EVERY dispatch;
  2. ANY result provenance reporting ``cost_usd > 0`` (or unparseable
     cost) halts the whole batch immediately — never silently escalate,
     never fall back to a paid model;
  3. ANY result whose observed route != ``default_haiku_go``
     (route must positively confirm; missing route halts too);
  4. ANY prompt framing leaking an arm identity halts before dispatch;
  5. held-out probes requested while the consumption counter != 0.

Output: ``pub08/experiment/eval/model-judgements.json`` keyed by LABEL
only (no arm identities anywhere in the file): per-label checklist /
probe / control records, top-level adjudication assists, per-call
costs/tokens + batch totals. Full prompts/texts are NOT duplicated
(prompt SHAs only; texts are frozen in blind-pack + candidate files).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field

from writer_core.analysis import publication_attribution as attr
from writer_core.analysis import publication_automation as auto
from writer_core.analysis import publication_spend as spend

RUNNER_ID = "pub08/experiment/run_eval_judges.py"
BATCH = "pub08-eval-judges-v0.1"
STAGE_ID = "pub08-eval"
MODEL_OVERRIDE = "default_haiku_go"

PROGRAMME_CAP_USD = 1.00
#: Worst-case pre-dispatch projection for the whole judges batch
#: (134 calls x full-text prompts at metered fallback rates, rounded up).
WORST_CASE_PROJECTION_USD = 0.16

EVAL_TASKS = {
    "checklist": "publication.eval.checklist",
    "probe": "publication.eval.probe",
    "control": "publication.eval.control",
    "assist": "publication.eval.assist",
}

HERE = Path(__file__).resolve().parent
EXP = HERE
EVAL_DIR = EXP / "eval"
BLIND_PACK_PATH = EVAL_DIR / "blind-pack.json"
PROBE_KEY_PATH = EVAL_DIR / "probe-key.json"
MODEL_JUDGEMENTS_PATH = EVAL_DIR / "model-judgements.json"

O_PATH = Path(r"C:\books\jev\content\books\jev\01-chapter.md")
H_PATH = Path(r"C:\Projects\mission\pub06\ch01\01-chapter-candidate.md")
A1_PATH = EXP / "arm_a_r1" / "candidate.md"
B1_PATH = EXP / "arm_b1" / "candidate.md"
A1_DISPATCH_RECORD = EXP / "arm_a_r1" / "dispatch-record.json"
B1_MERGE_RECORD = EXP / "arm_b1" / "merge-record.json"

#: Arm -> candidate file (resolved via blind-pack label->arm mapping).
ARM_CANDIDATE_FILES = {"O": O_PATH, "H": H_PATH, "A1": A1_PATH,
                       "B1": B1_PATH}

CONTROLS_FIXTURES_MODULE = (
    r"C:\Projects\writer\tests\core"
    r"\test_publication_attribution_controls.py")

# ---------------------------------------------------------------------------
# Frozen mirrors (batch-6 freeze; live run re-verifies against the key file)
# ---------------------------------------------------------------------------

#: 8-criterion editorial checklist (frozen definitions, batch-6 gate).
CHECKLIST: list[dict[str, str]] = [
    {"id": "C1", "name": "no_new_factual_claims",
     "rule": ("No sentence presenting unobserved model-backed work as "
              "established; verbatim quote or abstain.")},
    {"id": "C2", "name": "numbers_units_intact",
     "rule": ("Measurement numbers/units unchanged; verbatim quote or "
              "abstain.")},
    {"id": "C3", "name": "certainty_preserved",
     "rule": ("No strengthened hedges / ledger-type upgrades; verbatim "
              "quote or abstain.")},
    {"id": "C4", "name": "citations_intact",
     "rule": ("arXiv IDs / citations byte-intact where NO_CHANGE; "
              "verbatim quote or abstain.")},
    {"id": "C5", "name": "code_blocks_intact",
     "rule": ("Code/table/figure blocks byte-identical where NO_CHANGE; "
              "verbatim quote or abstain.")},
    {"id": "C6", "name": "honest_record_intact",
     "rule": ("OBSERVED / NOT_OBSERVED / Not-yet-run markers not dropped; "
              "verbatim quote or abstain.")},
    {"id": "C7", "name": "no_redundant_synthesis",
     "rule": ("No floor-is-real-style gloss adding nothing; verbatim "
              "quote or abstain.")},
    {"id": "C8", "name": "clarity_no_new_obscurity",
     "rule": ("Edits do not add obscurity; model judgement only, abstain "
              "without live call.")},
]

#: 12 fact + 3 epistemic probes (frozen mirror of probe-key.json content).
PROBE_MIRROR: list[dict[str, str]] = [
    {"id": "F1", "visibility": "public",
     "question": ("On the test split, how many tickets did the predicate "
                  "answer vs decline?"),
     "expected": "answered 10 and declined 10"},
    {"id": "F2", "visibility": "public",
     "question": "Of the answered test cases, how many matched the label?",
     "expected": "8 match the label"},
    {"id": "F3", "visibility": "public",
     "question": "What exact 25-character payload does the caller read?",
     "expected": '{"refund_approved": true}'},
    {"id": "F4", "visibility": "public",
     "question": "What did the predicate cost in tokens and latency?",
     "expected": ("generated zero tokens and every call took under "
                  "4 microseconds")},
    {"id": "F5", "visibility": "public",
     "question": ("What does constrained decoding guarantee, per Willard "
                  "et al. as quoted?"),
     "expected": "Structure, not correctness"},
    {"id": "F6", "visibility": "public",
     "question": ("What JSON parse-error rate does Tam et al. report for "
                  "LLaMA 3 8B on one task?"),
     "expected": "0.148%"},
    {"id": "F7", "visibility": "heldout",
     "question": "What inference cost/latency reduction does LMQL report?",
     "expected": "26-80%"},
    {"id": "F8", "visibility": "heldout",
     "question": ("After how many labels does fine-tuning performance "
                  "begin to saturate (Bucher et al.)?"),
     "expected": "around 200 labels"},
    {"id": "F9", "visibility": "heldout",
     "question": ("How large is the naively built Outlines index for an "
                  "augmented Python grammar?"),
     "expected": "around 50 MB"},
    {"id": "F10", "visibility": "heldout",
     "question": ("On how many reasoning datasets did plain natural "
                  "language still beat CFG-constrained output?"),
     "expected": "2 of 3 reasoning datasets"},
    {"id": "F11", "visibility": "heldout",
     "question": ("Which two tickets were inside the policy but labelled "
                  "decline?"),
     "expected": "t11 and t60"},
    {"id": "F12", "visibility": "heldout",
     "question": ("Which key ordering does the preregistered schema use "
                  "(harmful per Tam et al. s4.1)?"),
     "expected": "refund_approved first and reason second"},
    {"id": "E1", "visibility": "public",
     "question": "Did the model-backed arms run in this chapter?",
     "expected": "No \u2014 NOT_OBSERVED"},
    {"id": "E2", "visibility": "public",
     "question": "Is the Jev contract stated as documented fact?",
     "expected": "No \u2014 third-party claim, not DOCUMENTED"},
    {"id": "E3", "visibility": "public",
     "question": "Is generation overhead measured here?",
     "expected": "No \u2014 prediction stands untested"},
]

HELDOUT_IDS = [p["id"] for p in PROBE_MIRROR
               if p["visibility"] == "heldout"]
PUBLIC_IDS = [p["id"] for p in PROBE_MIRROR
              if p["visibility"] == "public"]

#: Semantic controls needing a model judge (deterministic NC1/NC4/NC5/NC6
#: are already covered by the batch-6 deterministic profiles, $0).
CONTROL_IDS = ["NC2", "NC3", "NC7a"]

#: 5 frozen pairwise adjudication questions (6 blind pairs x 5 = 30).
ASSIST_QUESTIONS: list[dict[str, str]] = [
    {"id": "Q1", "name": "numbers_fidelity",
     "question": ("Considering ONLY the preservation of measurement "
                  "numbers, quantities and units: which text preserves "
                  "them more faithfully? Quote the decisive lines.")},
    {"id": "Q2", "name": "certainty_fidelity",
     "question": ("Considering ONLY hedges and evidential certainty (no "
                  "strengthened claims, no upgraded evidence types): "
                  "which text preserves them better? Quote the decisive "
                  "lines.")},
    {"id": "Q3", "name": "editorial_clarity",
     "question": ("Which text reads more clearly without adding obscurity "
                  "or redundant gloss? Quote the decisive lines.")},
    {"id": "Q4", "name": "probe_support",
     "question": ("Which text better supports correct answers to factual "
                  "reading questions about the chapter's measurements? "
                  "Quote the decisive lines.")},
    {"id": "Q5", "name": "overall_preference",
     "question": ("Overall: applying the dominance rule (prefer one text "
                  "only if it is at least as good on every hard gate and "
                  "better on at least two dimensions; otherwise tie): is "
                  "either text preferred? Answer tie unless the difference "
                  "is concrete and quotable.")},
]

#: Tokens that must never appear in prompt framing (judges get label+text
#: only; arm identities are never interpolated by the builders below).
FORBIDDEN_FRAMING_TOKENS = [
    "arm_a", "arm_b", "arm_c", "Arm A", "Arm B", "Arm C", "Arm H",
    "arm A", "arm B", "arm H", "arm O", "PUB-06", "PUB-07", "PUB-08",
    "pub06", "pub07", "pub08", "DeepSeek", "deepseek", "Muse-authored",
    "CONFLICTED", "candidate.md", "blind-pack", "run_arm",
    "transformation-record", "source chapter", "original chapter",
    "generated candidate", "human candidate", "written by",
    "model-written", "human-written",
]

#: Strict tokens additionally scanned in FULL prompts (framing + text).
#: Each must first be verified absent from every labeled text; tokens
#: found in a text are skipped with a recorded note (they arrive via the
#: frozen candidate bytes, not via the prompt).
FORBIDDEN_STRICT_TOKENS = [
    "arm_a", "arm_b", "arm_c", "PUB-06", "PUB-07", "PUB-08",
    "DeepSeek", "deepseek", "Muse-authored", "CONFLICTED",
    "candidate.md", "blind-pack", "run_arm", "transformation-record",
]

LABEL_RE = re.compile(r"^T\d+$")

PAIR_LABEL_RE = re.compile(r"^T\d+/T\d+$")

JUDGE_VERDICTS = ("introduced", "strengthened", "weakened",
                  "redundant_synthesis", "no_change", "unknown")


def _label_parts(label: str) -> list[str] | None:
    if LABEL_RE.match(label):
        return [label]
    if PAIR_LABEL_RE.match(label):
        return label.split("/")
    return None


# ---------------------------------------------------------------------------
# Domain-owned Pydantic contracts (Writer owns; Worker enforces)
# ---------------------------------------------------------------------------

class ChecklistJudgeResponse(BaseModel):
    """One editorial-checklist verdict from the haiku judge."""

    criterion_id: str = Field(...)
    verdict: Literal["pass", "flag", "abstain"] = Field(...)
    quote: str = Field(default="")
    rationale: str = Field(default="")


class ProbeReaderResponse(BaseModel):
    """One probe answer from the haiku reader."""

    probe_id: str = Field(...)
    answer: str = Field(default="")
    supporting_quote: str = Field(default="")


class ControlJudgeResponse(BaseModel):
    """One semantic-control verdict from the haiku judge."""

    control_id: str = Field(...)
    verdict: Literal["introduced", "strengthened", "weakened",
                     "redundant_synthesis", "no_change", "unknown"] = Field(...)
    rationale: str = Field(default="")
    quote: str = Field(default="")


class AdjudicationAssistResponse(BaseModel):
    """One pairwise adjudication assist from the haiku judge."""

    pair: str = Field(...)
    question_id: str = Field(...)
    preferred: Literal["A", "B", "tie", "abstain"] = Field(...)
    rationale: str = Field(default="")
    quotes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Fail-closed halt errors (carry the exact position; never retried)
# ---------------------------------------------------------------------------

class EvalHaltError(ValueError):
    """Base halt: carries the exact item position."""

    def __init__(self, position: str, reason: str) -> None:
        super().__init__(f"HALT at {position}: {reason}")
        self.position = position
        self.reason = reason


class CostHaltError(EvalHaltError):
    """A call reported cost_usd > 0 (or unparseable cost)."""


class RouteHaltError(EvalHaltError):
    """A call did not positively confirm the haiku-only route."""


class BlindLeakError(EvalHaltError):
    """A prompt framing leaked an arm identity."""


class SpendHaltError(EvalHaltError):
    """Aggregate actuals + projection exceeded the programme cap."""


class HeldoutRefusedError(EvalHaltError):
    """Held-out probes requested while the consumption counter != 0."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True,
                                  separators=(",", ":")))


def aggregate_check(prior_ledgers: list[Any],
                    completed_ledgers: list[Any] | None = None,
                    projected_cost_usd: float = WORST_CASE_PROJECTION_USD,
                    cap_usd: float = PROGRAMME_CAP_USD) -> dict[str, Any]:
    """Programme-level pre-dispatch gate (batch-1 spend wrapper)."""
    priors = list(prior_ledgers or []) + list(completed_ledgers or [])
    return spend.check_aggregate_spend_guard(
        priors, projected_cost_usd=projected_cost_usd, cap_usd=cap_usd)


def _norm(text: str) -> str:
    """Frozen scoring form: collapse whitespace, strip, casefold."""
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def score_probe(expected: str, answer: str) -> dict[str, Any]:
    """Frozen-key scoring: normalized expected must be contained.

    Single frozen rule (matches the batch-6 deterministic proxy):
    case-insensitive reflow-tolerant containment of the whole expected
    string. A paraphrase that drops the key tokens scores incorrect —
    recorded as measurement, never retried.
    """
    exp, ans = _norm(expected), _norm(answer or "")
    correct = bool(exp) and exp in ans
    return {"score": "correct" if correct else "incorrect",
            "method": "frozen-key containment (norm expected in norm answer)"}


def extract_cost_route(record: dict[str, Any]) -> dict[str, Any]:
    """Pull cost/tokens/route/model from a dispatch_task record."""
    provenance = record.get("provenance") or {}
    usage = dict(provenance.get("usage") or {})
    usage.pop("raw", None)
    raw = record.get("raw_response") or {}
    route: Optional[str] = None
    model: Optional[str] = None
    try:
        exec_block = raw.get("worker_model_execution") or {}
        attempts = exec_block.get("attempts") or []
        if attempts and isinstance(attempts[0], dict):
            route = attempts[0].get("route") or None
            model = (attempts[0].get("model")
                     or (attempts[0].get("observed") or {}).get("model"))
        if not route:
            route = (exec_block.get("requested") or {}).get("route")
        if not model:
            model = raw.get("observed_model")
    except Exception:
        route, model = None, None
    return {"cost_usd": provenance.get("cost_usd"),
            "total_tokens": usage.get("total_tokens"),
            "latency_ms": provenance.get("latency_ms"),
            "writer_execution_id": provenance.get("writer_execution_id"),
            "route": route, "model": model}


def check_cost_and_route(record: dict[str, Any],
                          *, position: str) -> dict[str, Any]:
    """Fail-closed meter + route pin. Raises on ANY violation.

    - ``cost_usd`` missing (None) is recorded ``cost_unknown`` and the
      run continues (no spend observed); present-but-unparseable or > 0
      halts immediately with the exact position.
    - route must positively equal ``default_haiku_go``; absent or
      different halts immediately (never silently escalate, never fall
      back to a paid model).
    """
    info = extract_cost_route(record)
    raw_cost = info["cost_usd"]
    if raw_cost is None:
        info["cost_status"] = "cost_unknown"
        info["cost_usd"] = None
    else:
        try:
            cost = float(raw_cost)
        except (TypeError, ValueError):
            raise CostHaltError(position, (
                f"unparseable cost_usd {raw_cost!r}: HALT, cannot verify "
                f"$0 spend"))
        info["cost_usd"] = cost
        if cost > 0:
            raise CostHaltError(position, (
                f"metered cost_usd ${cost:.7f} > $0 on route "
                f"{info.get('route')}: HALT the whole batch, no fallback"))
        info["cost_status"] = "metered_zero"
    if info.get("route") != MODEL_OVERRIDE:
        raise RouteHaltError(position, (
            f"route {info.get('route')!r} != {MODEL_OVERRIDE!r}: HALT, "
            f"haiku-only route violated (no escalation, no fallback)"))
    return info


def check_blinding(items: list[dict[str, Any]],
                   texts_by_label: dict[str, str]) -> dict[str, Any]:
    """Verify no prompt leaks an arm identity; raise BlindLeakError.

    ``items`` carry ``item_id``/``label``/``framing``/``prompt``. Framing
    (everything the runner adds around the text) is scanned for every
    forbidden token; the full prompt is additionally scanned for the
    strict list, restricted to tokens verified absent from all texts.
    """
    if not items:
        raise BlindLeakError("batch", "no prompt items built")
    present_in_texts = set()
    for tok in FORBIDDEN_STRICT_TOKENS:
        for text in texts_by_label.values():
            if tok in (text or ""):
                present_in_texts.add(tok)
                break
    skipped = sorted(present_in_texts)
    for item in items:
        label = str(item.get("label", ""))
        parts = _label_parts(label)
        if parts is None:
            raise BlindLeakError(str(item.get("item_id", "?")), (
                f"label {label!r} is not a blind label (T<int> or "
                "T<int>/T<int> pair)"))
        framing = str(item.get("framing", ""))
        for part in parts:
            if part not in framing:
                raise BlindLeakError(
                    str(item.get("item_id", "?")),
                    "framing does not carry its blind label")
        for tok in FORBIDDEN_FRAMING_TOKENS:
            if tok in framing:
                raise BlindLeakError(str(item.get("item_id", "?")), (
                    f"framing leaks arm identity token {tok!r}"))
        prompt = str(item.get("prompt", ""))
        for tok in FORBIDDEN_STRICT_TOKENS:
            if tok in skipped:
                continue
            if tok in prompt:
                raise BlindLeakError(str(item.get("item_id", "?")), (
                    f"prompt leaks arm identity token {tok!r}"))
    return {"items_checked": len(items),
            "strict_tokens_skipped_in_texts": skipped,
            "verdict": "BLIND"}


# ---------------------------------------------------------------------------
# Prompt builders (pure; take LABEL only, never arm identities)
# ---------------------------------------------------------------------------

def build_checklist_prompt(label: str, text: str,
                           criterion: dict[str, str]) -> dict[str, str]:
    cid = criterion["id"]
    framing_head = (
        "You are an editorial judge for a blinded chapter evaluation. "
        f"You see ONE text labeled {label}. Judge only what is on the "
        "page; do not guess at provenance.\n\n"
        f"Criterion {cid} — {criterion['name']}: {criterion['rule']}")
    framing_tail = (
        "Output contract (JSON object ONLY, no prose outside it): "
        '{"criterion_id": "...", "verdict": "pass" | "flag" | "abstain", '
        '"quote": "verbatim excerpt supporting the verdict, or empty '
        'string", "rationale": "..."}. Verdict pass only if the criterion '
        "holds on the page; flag only with a verbatim quote demonstrating "
        "the violation; otherwise abstain with rationale. Every non-empty "
        f"quote must occur verbatim in TEXT {label}.")
    framing = framing_head + "\n\n" + framing_tail
    prompt = (framing_head + f"\n\nTEXT {label}:\n{text}\n\n"
              + framing_tail)
    return {"item_id": f"{label}:checklist:{cid}", "label": label,
            "prompt": prompt, "framing": framing,
            "operation_id": f"pub08-eval:{label}:checklist:{cid}"}


def build_probe_prompt(label: str, text: str,
                       probe: dict[str, str]) -> dict[str, str]:
    pid = probe["id"]
    framing_head = (
        "You are a reader in a blinded comprehension check. You see ONE "
        f"text labeled {label}. Answer ONLY from what TEXT {label} "
        "states; do not use outside knowledge. If the text does not "
        "state the answer, say so explicitly.\n\n"
        f"Question {pid}: {probe['question']}")
    framing_tail = (
        "Output contract (JSON object ONLY): "
        '{"probe_id": "...", "answer": "the answer in one short sentence, '
        'or \'NOT STATED IN TEXT\'", "supporting_quote": "verbatim excerpt '
        f'from TEXT {label} grounding the answer, or empty string"}}.')
    framing = framing_head + "\n\n" + framing_tail
    prompt = (framing_head + f"\n\nTEXT {label}:\n{text}\n\n"
              + framing_tail)
    return {"item_id": f"{label}:probe:{pid}", "label": label,
            "prompt": prompt, "framing": framing,
            "operation_id": f"pub08-eval:{label}:probe:{pid}"}


def build_control_prompt(label: str, text: str, control_id: str, *,
                         kind: str, candidate_quote: str,
                         original_quote: str = "") -> dict[str, str]:
    kind_line = f"Kind: {kind}."
    if kind == "paired_wording":
        kind_line += (f" Reference wording: {original_quote!r}. "
                      f"Candidate wording: {candidate_quote!r}.")
    else:
        kind_line += f" Quoted passage: {candidate_quote!r}."
    framing_head = (
        "You are a semantic judge for a blinded attribution check on ONE "
        f"text labeled {label}. Decide ONLY whether the quoted passage "
        "states new, strengthened, weakened, or merely restated content. "
        "Do not guess at provenance.\n\n"
        + kind_line)
    framing_tail = (
        "Output contract (JSON object ONLY): "
        '{"control_id": "...", "verdict": one of "introduced" | '
        '"strengthened" | "weakened" | "redundant_synthesis" | "no_change" '
        '| "unknown", "rationale": "...", "quote": "the decisive excerpt"}. '
        "Rules: introduced = the passage states a new factual claim not "
        "present in the reference wording or elsewhere in the labeled "
        "text outside the quoted passage; strengthened = it hardens a "
        "upgrades evidence; weakened = it softens or drops force; "
        "redundant_synthesis = it adds only a certainty gloss restating "
        "what the passage already establishes; no_change = none of the "
        "above; unknown = cannot decide (abstain). "
        "Verdict unknown unless the evidence is quotable.")
    framing = framing_head + "\n\n" + framing_tail
    prompt = (framing_head + f"\n\nTEXT {label}:\n{text}\n\n"
              + framing_tail)
    return {"item_id": f"{label}:control:{control_id}", "label": label,
            "prompt": prompt, "framing": framing,
            "operation_id": f"pub08-eval:{label}:control:{control_id}"}


def build_assist_prompt(label_a: str, label_b: str, text_a: str,
                        text_b: str,
                        question: dict[str, str]) -> dict[str, str]:
    qid = question["id"]
    pair = f"{label_a}v{label_b}"
    framing_head = (
        "You are assisting a blinded pairwise adjudication. You see TWO "
        f"texts labeled {label_a} and {label_b}. You do not know which "
        "source produced either; do not guess at provenance.\n\n"
        f"Question {qid} — {question['name']}: {question['question']}")
    framing_tail = (
        "Output contract (JSON object ONLY): "
        '{"pair": "...", "question_id": "...", "preferred": "A" | "B" | '
        '"tie" | "abstain", "rationale": "...", "quotes": ["verbatim '
        "excerpts from either text\"]}. Preferred A means the first text "
        f"({label_a}); B means the second ({label_b}). Every quote must "
        "occur verbatim in one of the two texts.")
    framing = framing_head + "\n\n" + framing_tail
    prompt = (framing_head + f"\n\nTEXT {label_a}:\n{text_a}\n\n"
              f"TEXT {label_b}:\n{text_b}\n\n" + framing_tail)
    return {"item_id": f"{pair}:assist:{qid}",
            "label": f"{label_a}/{label_b}", "pair": pair,
            "prompt": prompt, "framing": framing,
            "operation_id": f"pub08-eval:{pair}:assist:{qid}"}


# ---------------------------------------------------------------------------
# Per-item runners (pure; one shot per item; malformed = recorded, no retry)
# ---------------------------------------------------------------------------

def _payload(operation_id: str, task: str,
             prompt: str) -> dict[str, Any]:
    return {"task_kind": "publication_eval",
            "task": task,
            "model_override": MODEL_OVERRIDE,
            "package_id": operation_id,
            "operation_id": operation_id,
            "prompt": prompt,
            "attempt": 1,
            "dispatched": False}


def _call_record(dispatch_fn: Callable[..., Any],
                 payload: dict[str, Any], dto: Any,
                 role: str) -> dict[str, Any]:
    return auto.dispatch_task(dispatch_fn, payload, dto, role=role)


def run_checklist_item(dispatch_fn: Callable[..., Any], *,
                       label: str, text: str,
                       criterion: dict[str, str]) -> dict[str, Any]:
    """One checklist judgement. Quote-or-abstain enforced deterministically."""
    built = build_checklist_prompt(label, text, criterion)
    position = built["item_id"]
    record = _call_record(
        dispatch_fn, _payload(built["operation_id"],
                              EVAL_TASKS["checklist"], built["prompt"]),
        ChecklistJudgeResponse, role="checklist")
    meter = check_cost_and_route(record, position=position)
    out: dict[str, Any] = {"item_id": position, "label": label,
                           "criterion_id": criterion["id"],
                           "prompt_sha256": sha256_text(built["prompt"]),
                           "operation_id": built["operation_id"],
                           "meter": meter,
                           "dispatch_error": record.get("error"),
                           "dispatch_error_kind": record.get("error_kind")}
    if not record.get("succeeded") or not isinstance(record.get("typed"),
                                                     dict):
        out.update({"status": "abstain_malformed",
                    "verdict": "abstain", "quote": "",
                    "quote_verbatim": False,
                    "rationale": ("malformed/truncated/failed dispatch: "
                                  f"{record.get('error_kind')}; recorded, "
                                  "never retried")})
        return out
    typed = record["typed"]
    verdict = typed.get("verdict", "abstain")
    quote = str(typed.get("quote") or "")
    if verdict not in ("pass", "flag"):
        out.update({"status": "abstain",
                    "verdict": "abstain", "quote": "",
                    "quote_verbatim": False,
                    "rationale": str(typed.get("rationale") or "")})
        return out
    if quote and quote in text:
        out.update({"status": "judged", "verdict": verdict,
                    "quote": quote, "quote_verbatim": True,
                    "rationale": str(typed.get("rationale") or "")})
    else:
        out.update({"status": "coerced_abstain",
                    "verdict": "abstain", "quote": "",
                    "quote_verbatim": False,
                    "rationale": ("judge returned "
                                  f"{verdict!r} without a verbatim quote "
                                  "from the text: coerced to abstain "
                                  "(quote-or-abstain rule), never retried; "
                                  f"original rationale: "
                                  f"{str(typed.get('rationale') or '')}"[:400])})
    return out


def run_probe_item(dispatch_fn: Callable[..., Any], *,
                   label: str, text: str,
                   probe: dict[str, str]) -> dict[str, Any]:
    """One probe read + frozen-key scoring."""
    built = build_probe_prompt(label, text, probe)
    position = built["item_id"]
    record = _call_record(
        dispatch_fn, _payload(built["operation_id"],
                              EVAL_TASKS["probe"], built["prompt"]),
        ProbeReaderResponse, role="probe")
    meter = check_cost_and_route(record, position=position)
    out: dict[str, Any] = {"item_id": position, "label": label,
                           "probe_id": probe["id"],
                           "visibility": probe["visibility"],
                           "prompt_sha256": sha256_text(built["prompt"]),
                           "operation_id": built["operation_id"],
                           "meter": meter,
                           "dispatch_error": record.get("error"),
                           "dispatch_error_kind": record.get("error_kind")}
    if not record.get("succeeded") or not isinstance(record.get("typed"),
                                                     dict):
        out.update({"status": "fail_malformed", "answer": "",
                    "supporting_quote": "",
                    "supporting_quote_verbatim": False,
                    "score": "fail_malformed",
                    "score_reason": ("malformed/truncated/failed dispatch: "
                                     f"{record.get('error_kind')}; recorded, "
                                     "never retried")})
        return out
    typed = record["typed"]
    answer = str(typed.get("answer") or "")
    squote = str(typed.get("supporting_quote") or "")
    scored = score_probe(probe["expected"], answer)
    out.update({"status": "scored", "answer": answer,
                "supporting_quote": squote,
                "supporting_quote_verbatim": bool(squote)
                and squote in text,
                "score": scored["score"], "score_method": scored["method"],
                "score_reason": ("frozen-key containment vs key "
                                 f"{probe['id']}")})
    return out


def _control_setup(text: str, original_text: str, control_id: str,
                   fixtures: dict[str, str]) -> dict[str, Any] | None:
    """Build the (candidate_text, quote, pair) setup; None = unassessable.

    Mirrors the run_arm_c1 construction: NC2/NC7a inject the absent
    fixture into an in-memory copy (recorded as constructed) or use the
    text as-is when the fixture is already present (recorded as natural);
    NC3 replaces the original wording with the strengthened form.
    """
    if control_id == "NC2":
        quote = fixtures["nc2"]
        if quote in original_text:
            return None  # fixture drift: present in O, cannot attribute
        if quote in text:
            return {"candidate_text": text, "quote": quote,
                    "original_quote": "", "candidate_quote": quote,
                    "kind": "new_text", "setup": "natural"}
        return {"candidate_text": text + "\n" + quote, "quote": quote,
                "original_quote": "", "candidate_quote": quote,
                "kind": "new_text", "setup": "constructed"}
    if control_id == "NC7a":
        quote = fixtures["nc7a"]
        if quote in original_text:
            return None
        if quote in text:
            return {"candidate_text": text, "quote": quote,
                    "original_quote": "", "candidate_quote": quote,
                    "kind": "new_text", "setup": "natural"}
        return {"candidate_text": text + "\n" + quote, "quote": quote,
                "original_quote": "", "candidate_quote": quote,
                "kind": "new_text", "setup": "constructed"}
    if control_id == "NC3":
        orig, streng = fixtures["nc3_original"], fixtures["nc3_strengthened"]
        if streng in original_text:
            return None  # fixture drift
        if orig in text and streng not in text:
            return {"candidate_text": text.replace(orig, streng, 1),
                    "quote": streng, "original_quote": orig,
                    "candidate_quote": streng, "kind": "paired_wording",
                    "setup": "constructed"}
        if streng in text and orig not in text:
            return {"candidate_text": text, "quote": streng,
                    "original_quote": orig, "candidate_quote": streng,
                    "kind": "paired_wording", "setup": "natural"}
        return None  # neither wording present: unassessable, no dispatch
    raise ValueError(f"unknown control {control_id!r}")


def run_control_item(dispatch_fn: Callable[..., Any], *,
                     label: str, text: str, original_text: str,
                     control_id: str,
                     fixtures: dict[str, str]) -> dict[str, Any]:
    """One control judgement via the attribution builder's injected seam."""
    setup = _control_setup(text, original_text, control_id, fixtures)
    position = f"{label}:control:{control_id}"
    base: dict[str, Any] = {"item_id": position, "label": label,
                            "control_id": control_id}
    if setup is None:
        base.update({"status": "abstain_unassessable",
                     "disposition": "unresolved_attribution",
                     "dispatches": 0, "meter": None,
                     "reason": ("fixture setup impossible on this text "
                                "(wording absent/drifted): zero dispatches, "
                                "fail closed")})
        return base
    built = build_control_prompt(
        label, setup["candidate_text"], control_id, kind=setup["kind"],
        candidate_quote=setup["candidate_quote"],
        original_quote=setup["original_quote"])
    calls: list[dict[str, Any]] = []

    def _live_judge(query: dict[str, Any]) -> dict[str, Any]:
        if calls:
            return {"verdict": "unknown", "judge": "live",
                    "rationale": ("judge already consumed for this item "
                                  "(one shot; no second call)")}
        calls.append(dict(query or {}))
        record = _call_record(
            dispatch_fn, _payload(built["operation_id"],
                                  EVAL_TASKS["control"], built["prompt"]),
            ControlJudgeResponse, role="control")
        meter = check_cost_and_route(record, position=position)
        base["meter"] = meter
        base["prompt_sha256"] = sha256_text(built["prompt"])
        base["operation_id"] = built["operation_id"]
        base["dispatch_error"] = record.get("error")
        base["dispatch_error_kind"] = record.get("error_kind")
        if not record.get("succeeded") or not isinstance(
                record.get("typed"), dict):
            return {"verdict": "unknown", "judge": "live",
                    "rationale": ("control dispatch "
                                  f"{record.get('error_kind')}: fail closed "
                                  "to unresolved_attribution, never "
                                  "retried")}
        typed = record["typed"]
        verdict = str(typed.get("verdict") or "unknown")
        if verdict not in JUDGE_VERDICTS:
            return {"verdict": "unknown", "judge": "live",
                    "rationale": (f"malformed verdict {verdict!r}: fail "
                                  "closed, never retried")}
        return {"verdict": verdict, "judge": "live",
                "rationale": str(typed.get("rationale") or "")}

    rec = attr.attribute_finding(
        quote=setup["quote"], original_text=original_text,
        candidate_text=setup["candidate_text"],
        original_quote=setup["original_quote"] or None,
        candidate_quote=setup["candidate_quote"],
        semantic_judge=_live_judge)
    base.update({"status": "judged" if calls else "abstain_no_judge_call",
                 "setup": setup["setup"], "kind": setup["kind"],
                 "dispatches": len(calls),
                 "disposition": rec.get("disposition"),
                 "reason": rec.get("reason"),
                 "evidence": rec.get("evidence"),
                 "judge": rec.get("judge")})
    base.setdefault("meter", None)
    return base


def run_assist_item(dispatch_fn: Callable[..., Any], *,
                    label_a: str, label_b: str, text_a: str, text_b: str,
                    question: dict[str, str]) -> dict[str, Any]:
    """One pairwise adjudication assist (quotes verified, verdict kept)."""
    built = build_assist_prompt(label_a, label_b, text_a, text_b, question)
    position = built["item_id"]
    record = _call_record(
        dispatch_fn, _payload(built["operation_id"],
                              EVAL_TASKS["assist"], built["prompt"]),
        AdjudicationAssistResponse, role="assist")
    meter = check_cost_and_route(record, position=position)
    out: dict[str, Any] = {"item_id": position, "pair": built["pair"],
                           "question_id": question["id"],
                           "prompt_sha256": sha256_text(built["prompt"]),
                           "operation_id": built["operation_id"],
                           "meter": meter,
                           "dispatch_error": record.get("error"),
                           "dispatch_error_kind": record.get("error_kind")}
    if not record.get("succeeded") or not isinstance(record.get("typed"),
                                                     dict):
        out.update({"status": "abstain_malformed", "preferred": "abstain",
                    "rationale": ("malformed/truncated/failed dispatch: "
                                  f"{record.get('error_kind')}; recorded, "
                                  "never retried"), "quotes": [],
                    "quotes_verbatim": []})
        return out
    typed = record["typed"]
    quotes = [str(q) for q in (typed.get("quotes") or [])]
    verbatim = [bool(q) and (q in text_a or q in text_b) for q in quotes]
    out.update({"status": "assisted",
                "preferred": typed.get("preferred", "abstain"),
                "preferred_labels": {"A": label_a, "B": label_b,
                                     "tie": None, "abstain": None},
                "rationale": str(typed.get("rationale") or ""),
                "quotes": quotes, "quotes_verbatim": verbatim})
    return out


# ---------------------------------------------------------------------------
# Probe-key handling (held-out single consumption)
# ---------------------------------------------------------------------------

def read_probe_key(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def probe_key_mirror_ok(key: dict[str, Any]) -> list[str]:
    """Compare live key probes against the frozen mirror; drift reasons."""
    live = key.get("probes") or []
    drift: list[str] = []
    if len(live) != len(PROBE_MIRROR):
        drift.append(f"probe count {len(live)} != frozen {len(PROBE_MIRROR)}")
    want = {p["id"]: p for p in PROBE_MIRROR}
    for entry in live:
        pid = entry.get("id")
        ref = want.get(pid)
        if ref is None:
            drift.append(f"unknown probe {pid!r}")
            continue
        for field in ("visibility", "question", "expected"):
            if entry.get(field) != ref[field]:
                drift.append(f"probe {pid} field {field} drifted")
    want_ids = {p["id"] for p in PROBE_MIRROR}
    for pid in want_ids - {e.get("id") for e in live if isinstance(e, dict)}:
        drift.append(f"frozen probe {pid} missing from key")
    return drift


def heldout_allowed(key: dict[str, Any]) -> bool:
    """Held-out budget: exactly one model-reader run, ever."""
    try:
        return int((key.get("consumption") or {}).get(
            "model_reader_runs", 0)) == 0
    except (TypeError, ValueError):
        return False


def consume_heldout(key_path: Path | str) -> dict[str, Any]:
    """Burn the single held-out run BEFORE dispatching (fail-closed).

    Re-reads the file, requires the counter still 0 AND the probes list
    byte-identical (SHA) to the just-read key, then writes back
    ``model_reader_runs = 1``. Any interruption after this point still
    counts as the one run: a retry refuses.
    """
    path = Path(key_path)
    key = json.loads(path.read_text(encoding="utf-8"))
    if not heldout_allowed(key):
        raise HeldoutRefusedError("heldout-consume", (
            "consumption counter != 0: held-out probes already consumed; "
            "refusing a second run"))
    before_sha = sha256_json(key.get("probes") or [])
    consumption = dict(key.get("consumption") or {})
    consumption["model_reader_runs"] = 1
    key["consumption"] = consumption
    if sha256_json(key.get("probes") or []) != before_sha:
        raise HeldoutRefusedError("heldout-consume",
                                  "probes changed during consume; refusing")
    path.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return key


# ---------------------------------------------------------------------------
# Full sweep (pure; main() wires live paths + writes the file)
# ---------------------------------------------------------------------------

def run_full_batch(*, dispatch_fn: Callable[..., Any],
                   texts_by_label: dict[str, str],
                   probe_key: dict[str, Any],
                   fixtures: dict[str, str],
                   original_label: str,
                   priors: list[Any],
                   include_heldout: bool,
                   key_path_for_consume: Path | str | None = None,
                   projection_usd: float = WORST_CASE_PROJECTION_USD,
                   cap_usd: float = PROGRAMME_CAP_USD,
                   prompt_sink: list[dict[str, Any]] | None = None,
                   ) -> dict[str, Any]:
    """Run every eval item once through the injected dispatch callable.

    Raises the fail-closed halts (spend/cost/route/blinding/held-out)
    with the exact position; malformed single items are recorded
    abstain/fail and the sweep continues.
    """
    labels = sorted(texts_by_label)
    if original_label not in texts_by_label:
        raise EvalHaltError("batch",
                            f"original label {original_label!r} not in texts")
    probes = [dict(p) for p in (probe_key.get("probes") or [])]
    if include_heldout:
        if not heldout_allowed(probe_key):
            raise HeldoutRefusedError("batch", (
                "held-out requested with consumption counter != 0"))
        if key_path_for_consume is not None:
            probe_key = consume_heldout(key_path_for_consume)
    wanted = [p for p in probes
              if include_heldout or p.get("visibility") != "heldout"]

    # Pre-dispatch aggregate gate (priors + worst-case projection).
    guard = aggregate_check(list(priors or []), [], projection_usd, cap_usd)
    if not guard.get("allowed"):
        raise SpendHaltError("batch:pre-dispatch", (
            f"priors ${guard.get('aggregate_actuals_usd', float('nan')):.6f} "
            f"+ projection ${projection_usd:.3f} > cap ${cap_usd:.2f}: "
            "HALT with zero dispatches"))

    items: list[dict[str, Any]] = []
    for label in labels:
        for criterion in CHECKLIST:
            items.append(("checklist", label, criterion))
    for label in labels:
        for probe in wanted:
            items.append(("probe", label, probe))
    for label in labels:
        for control_id in CONTROL_IDS:
            items.append(("control", label, control_id))
    pairs = sorted(combinations(labels, 2))
    for (la, lb) in pairs:
        for question in ASSIST_QUESTIONS:
            items.append(("assist", la, lb, question))

    # Build every prompt first; blinding gate before ANY dispatch.
    prompt_metas: list[dict[str, Any]] = []
    for item in items:
        kind = item[0]
        if kind == "checklist":
            _, label, criterion = item
            prompt_metas.append(build_checklist_prompt(
                label, texts_by_label[label], criterion))
        elif kind == "probe":
            _, label, probe = item
            prompt_metas.append(build_probe_prompt(
                label, texts_by_label[label], probe))
        elif kind == "control":
            _, label, control_id = item
            setup = _control_setup(texts_by_label[label],
                                   texts_by_label[original_label],
                                   control_id, fixtures)
            if setup is None:
                prompt_metas.append({
                    "item_id": f"{label}:control:{control_id}",
                    "label": label, "prompt": "", "framing": None,
                    "operation_id": "",
                    "unassessable": True})
            else:
                prompt_metas.append(build_control_prompt(
                    label, setup["candidate_text"], control_id,
                    kind=setup["kind"],
                    candidate_quote=setup["candidate_quote"],
                    original_quote=setup["original_quote"]))
        else:
            _, la, lb, question = item
            prompt_metas.append(build_assist_prompt(
                la, lb, texts_by_label[la], texts_by_label[lb], question))
    if prompt_sink is not None:
        prompt_sink.extend(prompt_metas)
    check_blinding([m for m in prompt_metas if not m.get("unassessable")],
                   texts_by_label)

    completed: list[dict[str, Any]] = []
    checklist: dict[str, dict[str, Any]] = {label: {} for label in labels}
    probes_out: dict[str, dict[str, Any]] = {label: {} for label in labels}
    controls: dict[str, dict[str, Any]] = {label: {} for label in labels}
    assists: list[dict[str, Any]] = []
    failures: list[str] = []

    for meta, item in zip(prompt_metas, items):
        kind = item[0]
        # Per-dispatch spend re-gate (conservative: full projection).
        gate = aggregate_check(list(priors or []),
                               [{"total_cost_usd": _completed_cost(
                                   completed)}],
                               projection_usd, cap_usd)
        if not gate.get("allowed"):
            raise SpendHaltError(str(meta.get("item_id", "?")), (
                "aggregate cap would be exceeded mid-batch: HALT with zero "
                "further dispatches"))
        try:
            if kind == "checklist":
                _, label, criterion = item
                res = run_checklist_item(
                    dispatch_fn, label=label,
                    text=texts_by_label[label], criterion=criterion)
                checklist[label][criterion["id"]] = res
            elif kind == "probe":
                _, label, probe = item
                res = run_probe_item(
                    dispatch_fn, label=label,
                    text=texts_by_label[label], probe=probe)
                probes_out[label][probe["id"]] = res
            elif kind == "control":
                _, label, control_id = item
                # Unassessable setups short-circuit inside
                # run_control_item with zero dispatches.
                res = run_control_item(
                    dispatch_fn, label=label,
                    text=texts_by_label[label],
                    original_text=texts_by_label[original_label],
                    control_id=control_id, fixtures=fixtures)
                controls[label][control_id] = res
            else:
                _, la, lb, question = item
                res = run_assist_item(
                    dispatch_fn, label_a=la, label_b=lb,
                    text_a=texts_by_label[la], text_b=texts_by_label[lb],
                    question=question)
                assists.append(res)
        except EvalHaltError as exc:
            failures.append(str(exc))
            raise
        completed.append(meta)
    totals = _totals(checklist, probes_out, controls, assists)
    return {"checklist": checklist, "probes": probes_out,
            "controls": controls, "assists": assists,
            "failures": failures, "totals": totals,
            "aggregate_guard": gate}


def _completed_cost(completed: list[dict[str, Any]]) -> float:
    # Completed metas carry no cost (costs live in item records); the
    # per-dispatch gate re-checks priors + full projection, so actuals
    # tracked here are informational ($0 route: always 0.0 unless a
    # metered call slipped past — which halts instead).
    _ = completed
    return 0.0


def _meter_cost(item: dict[str, Any]) -> float:
    try:
        return float((item.get("meter") or {}).get("cost_usd") or 0.0)
    except (TypeError, ValueError):
        return float("nan")


def _meter_tokens(item: dict[str, Any]) -> int:
    try:
        return int((item.get("meter") or {}).get("total_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _totals(checklist: dict[str, dict[str, Any]],
            probes_out: dict[str, dict[str, Any]],
            controls: dict[str, dict[str, Any]],
            assists: list[dict[str, Any]]) -> dict[str, Any]:
    calls = succeeded = abstained = failed = 0
    total_cost = 0.0
    total_tokens = 0
    for bucket in (list(checklist.values()) + list(probes_out.values())
                   + list(controls.values())):
        for res in bucket.values():
            calls += 1
            total_cost += _meter_cost(res)
            total_tokens += _meter_tokens(res)
            status = str(res.get("status", ""))
            if status in ("judged", "scored", "assisted"):
                succeeded += 1
            elif "malformed" in status or "fail" in status:
                failed += 1
            else:
                abstained += 1
    for res in assists:
        calls += 1
        total_cost += _meter_cost(res)
        total_tokens += _meter_tokens(res)
        status = str(res.get("status", ""))
        if status == "assisted":
            succeeded += 1
        elif "malformed" in status:
            failed += 1
        else:
            abstained += 1
    return {"calls": calls, "succeeded": succeeded,
            "abstained": abstained, "failed": failed,
            "total_cost_usd": total_cost, "total_tokens": total_tokens}


# ---------------------------------------------------------------------------
# Live entry point (coordinator-executed; NOT run in batch 7a)
# ---------------------------------------------------------------------------

def main() -> int:
    import sys as _sys
    _sys.path.insert(0, r"C:\Projects\writer\packages\writer-core")
    _sys.path.insert(0, r"C:\Projects\writer\packages\writer-cli")
    _sys.path.insert(0, r"C:\Projects\writer\packages\writer-runtime")
    from typer.testing import CliRunner as _Runner
    from writer_cli.main import app as _app
    from writer_runtime import build_runtime as _build_runtime
    from writer_runtime.domains.models.typed_task import (
        run_typed_task as _run_typed_task)
    import importlib.util as _ilu

    failures: list[str] = []

    def _halt(msg: str) -> int:
        failures.append(msg)
        print(f"HALT: {msg}", file=_sys.stderr)
        return 3

    # ---- frozen inputs ----
    try:
        blind_pack = json.loads(BLIND_PACK_PATH.read_text(encoding="utf-8"))
        probe_key = read_probe_key(PROBE_KEY_PATH)
    except Exception as exc:
        return _halt(f"unreadable frozen eval inputs: {exc}")
    drift = probe_key_mirror_ok(probe_key)
    if drift:
        return _halt(f"probe-key drift vs frozen mirror: {drift[:5]}")
    mapping = blind_pack.get("mapping") or {}
    if not mapping:
        return _halt("blind-pack mapping missing/empty")
    for label, arm in mapping.items():
        if not LABEL_RE.match(str(label)):
            return _halt(f"blind-pack label {label!r} is not a blind label")
        if arm not in ARM_CANDIDATE_FILES:
            return _halt(f"blind-pack arm {arm!r} has no frozen file")
    try:
        _spec = _ilu.spec_from_file_location(
            "eval_ctrl_fixtures", CONTROLS_FIXTURES_MODULE)
        _mod = _ilu.module_from_spec(_spec)
        _sys.modules["eval_ctrl_fixtures"] = _mod
        _spec.loader.exec_module(_mod)
        fixtures = {"nc2": _mod.NC2_QUOTE,
                    "nc3_original": _mod.NC3_ORIGINAL,
                    "nc3_strengthened": _mod.NC3_STRENGTHENED,
                    "nc7a": _mod.NC7A_QUOTE}
    except Exception as exc:
        return _halt(f"control fixtures unloadable: {exc}")

    # ---- texts by label (arm identities never enter prompts) ----
    # Coordinator fix 2026-11-25: the blind pack froze RAW FILE BYTES
    # SHAs (O and H worktrees are CRLF checkout artifacts). Hash raw
    # bytes for identity; decode + explicit CRLF->LF for prompt use.
    # (Same CRLF class as the B1 runner halt; no arm bytes changed —
    # all four raws match the frozen file_shas.)
    texts_by_label: dict[str, str] = {}
    label_sha: dict[str, str] = {}
    try:
        for label, arm in mapping.items():
            path = ARM_CANDIDATE_FILES[arm]
            raw = Path(path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != (
                    blind_pack.get("file_sha256") or {}).get(arm):
                return _halt(f"text SHA drift for {label} "
                             f"(arm bytes changed)")
            text = raw.decode("utf-8").replace("\r\n", "\n")
            texts_by_label[str(label)] = text
            label_sha[str(label)] = hashlib.sha256(raw).hexdigest()
    except Exception as exc:
        return _halt(f"candidate texts unreadable: {exc}")
    for label, arm in mapping.items():
        want_label = (blind_pack.get("label_sha256") or {}).get(label)
        if label_sha[str(label)] != want_label:
            return _halt(f"label SHA drift for {label}")
    original_label = next((lbl for lbl, arm in mapping.items()
                           if arm == "O"), None)
    if original_label is None:
        return _halt("no O arm in blind-pack mapping")
    o_text = texts_by_label[str(original_label)]
    # Coordinator fix 2026-11-25: NC3_ORIGINAL is genuine O text (the
    # hedge the control strengthens) — it MUST be present; its absence
    # means O drifted. Only the invented/strengthened variants must be
    # absent. The previous code halted on the original's presence,
    # which is backwards.
    if fixtures["nc3_original"] not in o_text:
        return _halt("control fixture nc3_original absent from O: drift")
    for name, quote in (("nc2", fixtures["nc2"]),
                        ("nc7a", fixtures["nc7a"])):
        if quote in o_text:
            return _halt(f"control fixture {name} present in O: drift")
    if fixtures["nc3_strengthened"] in o_text:
        return _halt("NC3_STRENGTHENED present in O: drift")

    # ---- priors + pre-dispatch aggregate check (exact arithmetic) ----
    try:
        a1 = json.loads(A1_DISPATCH_RECORD.read_text(encoding="utf-8"))
        prior_a1 = float((a1.get("provenance") or {}).get("cost_usd"))
        b1 = json.loads(B1_MERGE_RECORD.read_text(encoding="utf-8"))
        prior_b1 = float((b1.get("ledger_actuals_usd") or {}).get(
            "b1_packages"))
    except Exception as exc:
        return _halt(f"priors unreadable (A1/B1 records): {exc}")
    priors = [{"total_cost_usd": prior_a1},
              {"total_cost_usd": prior_b1}]
    verdict = aggregate_check(priors, [], WORST_CASE_PROJECTION_USD,
                              PROGRAMME_CAP_USD)
    if not verdict.get("allowed"):
        return _halt(
            f"aggregate spend guard: priors "
            f"${verdict.get('aggregate_actuals_usd', float('nan')):.6f} "
            f"+ projection ${WORST_CASE_PROJECTION_USD:.3f} exceeds cap "
            f"${PROGRAMME_CAP_USD:.2f}: HALT with zero dispatches")
    print(f"priors: A1 ${prior_a1:.7f} + B1 ${prior_b1:.7f} = "
          f"${prior_a1 + prior_b1:.7f}; + projection "
          f"${WORST_CASE_PROJECTION_USD:.3f} <= ${PROGRAMME_CAP_USD:.2f} OK "
          f"(remaining ${verdict.get('remaining_usd', 0.0):.6f})")

    # ---- held-out single-consumption gate (consume BEFORE dispatching) ----
    if not heldout_allowed(probe_key):
        return _halt("held-out consumption counter != 0: refusing a "
                      "second held-out run")

    # ---- production seam (same _dispatch shape as transform automate) ----
    runtime = _build_runtime()
    models = runtime.require("models")

    def _dispatch(*, task: str, prompt: str, dto: Any,
                  metadata: Any = None,
                  context_for_provenance: Any = None) -> Any:
        operation_id = str((metadata or {}).get("operation_id")
                           or (metadata or {}).get("package_id")
                           or "pub08-eval")
        return _run_typed_task(
            models, task=task, prompt=prompt, dto=dto,
            domain="publication", operation_id=operation_id,
            stage_id=STAGE_ID, metadata=dict(metadata or {}),
            context_for_provenance=context_for_provenance)

    _ = _Runner(), _app  # live CLI surface available; seam is run_typed_task

    prompt_metas: list[dict[str, Any]] = []
    try:
        sweep = run_full_batch(
            dispatch_fn=_dispatch, texts_by_label=texts_by_label,
            probe_key=probe_key, fixtures=fixtures,
            original_label=str(original_label), priors=priors,
            include_heldout=True, key_path_for_consume=PROBE_KEY_PATH,
            prompt_sink=prompt_metas)
    except EvalHaltError as exc:
        return _halt(str(exc))

    output = {
        "runner": RUNNER_ID,
        "batch": BATCH,
        "stage_id": STAGE_ID,
        "route": MODEL_OVERRIDE,
        "blind_pack_sha256": blind_pack.get("pack_sha256"),
        "blind_seed": blind_pack.get("seed"),
        "probe_key_probes_sha256": sha256_json(probe_key.get("probes")
                                               or []),
        "consumption_after_run": {"model_reader_runs": 1},
        "priors_usd": {"A1": prior_a1, "B1_packages": prior_b1,
                       "aggregate": prior_a1 + prior_b1},
        "projection_usd": WORST_CASE_PROJECTION_USD,
        "cap_usd": PROGRAMME_CAP_USD,
        "aggregate_guard": sweep.get("aggregate_guard"),
        "counts": {
            "labels": sorted(texts_by_label),
            "checklist_per_text": len(CHECKLIST),
            "probes_per_text": len(PROBE_MIRROR),
            "controls_per_text": len(CONTROL_IDS),
            "assist_questions": len(ASSIST_QUESTIONS),
        },
        "texts": {label: {"label_sha256": label_sha[label],
                          "bytes": len(texts_by_label[label].encode(
                              "utf-8")),
                          "lines": len(texts_by_label[label].splitlines())}
                  for label in sorted(texts_by_label)},
        "checklist": sweep["checklist"],
        "probes": sweep["probes"],
        "controls": sweep["controls"],
        "adjudication_assists": sweep["assists"],
        "totals": sweep["totals"],
        "failures": sweep["failures"],
        "verdict": ("GO_MODEL_JUDGED" if not sweep["failures"]
                    else "HALT"),
    }
    MODEL_JUDGEMENTS_PATH.write_text(
        json.dumps(output, indent=1, default=str), encoding="utf-8")
    print(f"wrote {MODEL_JUDGEMENTS_PATH} "
          f"({sweep['totals']['calls']} calls, "
          f"${sweep['totals']['total_cost_usd']:.7f}, "
          f"{sweep['totals']['total_tokens']} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
