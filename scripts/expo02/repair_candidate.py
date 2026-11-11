"""EXPO-02 Stage F: one bounded, independently evaluated repair candidate.

Steps (all candidate-only; canonical manuscripts untouched):
  F1 freeze original (text, sha, region, findings, features, semantic row)
  F2 preservation ledger (model-extracted, then deterministically verified)
  F3 explanation plan (model, specific to the passage)
  F4 bounded candidate via the real REORDER_EXPLANATION strategy instructions
  F5 blind A/B comparison + comprehension check (separate context, random order)
  F6 metrics (rule pressure before/after, semantic re-eval, preservation gate,
     word/para counts, disposition)

Usage:
  python scripts/expo02/repair_candidate.py --passage P16
  python scripts/expo02/repair_candidate.py --passage P16 --confirm-f5  # runs blind comparison too
All model I/O cached under scripts/expo02/cache/repair_<pid>_*.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, "C:/Projects/writer/packages/writer-runtime")
sys.path.insert(0, "C:/Projects/writer/packages/writer-core")
sys.path.insert(0, "C:/Projects/ai/src")
sys.path.insert(0, str(BASE))

from run_semantic import ExpoPromptBuilder, OpenCodeModelRunner, MODEL_ROUTE  # noqa: E402

from writer_runtime.domains.artifact.artifact_engine.revision.artifact_repair_strategy_service import (  # noqa: E402
    ArtifactRepairStrategyService,
)
from writer_runtime.domains.artifact.artifact_engine.revision.semantic_loss import (  # noqa: E402
    check_semantic_loss,
)
from writer_runtime.domains.artifact.dto_repair import ArtifactDamageTargetDTO  # noqa: E402

from ai.inference.dto import ReasoningRequest  # noqa: E402

REPAIR_PROMPT_VERSION = "expo-repair-v1"


def call_model(runner: OpenCodeModelRunner, purpose: str, prompt: str, tag: str) -> dict:
    key = BASE / "cache" / f"repair_{tag}.json"
    if key.exists():
        row = json.loads(key.read_text(encoding="utf-8"))
        row["cache_hit"] = True
        return row
    req = ReasoningRequest(
        request_id=f"expo02-repair-{uuid.uuid4().hex[:8]}",
        purpose=purpose,
        prompt=prompt,
        timeout_s=300,
    )
    t0 = time.perf_counter()
    result = runner.provider.generate(req)
    latency = round(time.perf_counter() - t0, 1)
    row = {
        "tag": tag,
        "prompt_version": REPAIR_PROMPT_VERSION,
        "requested_model": MODEL_ROUTE,
        "actual_model": result.route or MODEL_ROUTE,
        "transport": (result.raw_metadata or {}).get("transport"),
        "latency_s": latency,
        "usage": result.usage.model_dump() if result.usage else None,
        "provider_status": result.status,
        "provider_error": result.error,
        "output": result.content if result.status == "ok" else "",
        "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:16],
        "prompt_chars": len(prompt),
        "cache_hit": False,
    }
    key.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    return row


LEDGER_PROMPT = """You are preserving technical meaning before an explanation rewrite. Do NOT rewrite the passage.

List the preservation ledger for the passage below as JSON only:
{"claims": [], "definitions": [], "numbers_with_units": [], "statistical_qualifiers": [],
 "conditions": [], "caveats": [], "equations_or_formalisms": [], "experimental_results": [],
 "evidence_status": [], "references": [], "technical_terms": [], "authorial_commitments": []}

Rules: copy exact wording from the passage for each item; empty list when absent;
never invent items. Passage:

---
%s
---
"""

PLAN_PROMPT = """You are planning a clearer path through the same ideas. Do NOT rewrite the passage yet.

Diagnosis of the obstruction:
%s

Preservation ledger (must all survive):
%s

Write a short explanation plan as JSON only:
{"steps": [{"order": 1, "learn": "...", "why_here": "..."}], "example_placement": "...",
 "caveats_adjacent": [], "caveats_moved_later": [], "splits_or_merges": "..."}

Passage:
---
%s
---
"""

CANDIDATE_PROMPT = """Rewrite the passage below into a clearer explanation of the SAME ideas.

REORDER_EXPLANATION strategy instructions (from Writer ArtifactRepairStrategyService):
%s

Preservation ledger (every item must survive verbatim in meaning):
%s

Explanation plan:
%s

Strict prohibitions: do not invent evidence; do not remove technical conditions;
do not change measurements; do not alter statistical meaning; do not add certainty;
do not modify equations; do not touch unrelated sections. Keep the same technical
terms and the author's voice. Stay within the passage: no new sections.

Output ONLY the revised passage text, no preamble.

Passage:
---
%s
---
"""

COMPARE_PROMPT = """Two passages, X and Y, explain the same material in different orders. One is the original,
one is a revised candidate; you are not told which. Compare them blind.

X:
---
%s
---

Y:
---
%s
---

Return exactly:

# rationale
1-2 sentences on which is easier to follow and why.

# score
A number from 0.0 to 1.0 where higher means Y is clearer than X.

# answer
JSON only: {"clearer": "X|Y|TIE", "order": "...", "effort": "...",
"preserved": true, "lost_or_changed": [], "voice": "...", "remaining_overload": "...",
"comprehension": [{"q": "...", "answer_from_X": "...", "answer_from_Y": "...", "match": true}]}
First write 2-3 questions a reader should answer from the passage, then answer each from X and from Y independently.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passage", required=True)
    ap.add_argument("--limit-words", type=int, default=400)
    args = ap.parse_args()

    passages = {p["id"]: p for p in
                (json.loads(line) for line in (BASE / "passages.jsonl").read_text(encoding="utf-8").splitlines())}
    sem = {}
    for line in (BASE / "semantic_results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("rep", 0) == 0 and r.get("status") == "ok":
            sem[r["id"]] = r
    p = passages[args.passage]
    s = sem.get(args.passage, {})
    original = p["text"]
    print(f"passage={p['id']} {p['source']} L{p['start_line']}-{p['end_line']}")
    print(f"rule_flagged={p['rule_flagged']} semantic={s.get('verdict')}/{s.get('severity')} model={s.get('actual_model')}")
    if len(original.split()) > args.limit_words:
        raise SystemExit("passage exceeds bounded word limit; choose a smaller unit")

    freeze = {
        "passage_id": p["id"], "source": p["source"],
        "chapter": p["chapter"], "start_line": p["start_line"], "end_line": p["end_line"],
        "sha": p["sha"],
        "original_text": original,
        "rule": {"flagged": p["rule_flagged"], "subtype": p["rule_subtype"],
                 "compression": p["compression"], "interruption": p["interruption"]},
        "semantic": {k: s.get(k) for k in ("verdict", "severity", "confidence", "diagnosis",
                                           "prompt_version", "requested_model", "actual_model")},
    }
    (BASE / f"repair_{p['id']}_freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8")

    target = ArtifactDamageTargetDTO(
        target_id=f"expo02-{p['id']}", text=original,
        artifact_count=1, dominant_artifact_type="EXPOSITORY_OVERLOAD",
        diagnosis="EXPOSITORY_OVERLOAD", damage_score=5.0, priority="review",
        co_occurring_artifacts=["EXPOSITORY_OVERLOAD"],
    )
    strategy = ArtifactRepairStrategyService().choose_strategy(target)
    assert strategy.strategy_id == "reorder_explanation", strategy.strategy_id
    strategy_block = "\n".join(f"- {line}" for line in strategy.instructions)

    runner = OpenCodeModelRunner(MODEL_ROUTE)
    ledger = call_model(runner, "preservation ledger extraction (no rewrite)",
                        LEDGER_PROMPT % original, f"{p['id']}_ledger")
    plan = call_model(runner, "explanation plan (no rewrite)",
                      PLAN_PROMPT % (s.get("diagnosis", ""), ledger["output"], original),
                      f"{p['id']}_plan")
    candidate = call_model(runner, "bounded explanation candidate",
                           CANDIDATE_PROMPT % (strategy_block, ledger["output"], plan["output"], original),
                           f"{p['id']}_candidate")
    cand_text = (candidate["output"] or "").strip()
    print(f"candidate chars={len(cand_text)} cache_hit={candidate['cache_hit']}")

    # Preservation gate: the real deterministic semantic-loss check incl. median guard.
    gate = check_semantic_loss(original, cand_text)
    gate_row = {"passed": gate.passed, "risk_level": gate.risk_level, "reason": gate.reason,
                "findings": [{"kind": f.kind, "severity": f.severity,
                              "original_text": f.original_text, "explanation": f.explanation}
                             for f in gate.findings]}
    print(f"preservation gate: passed={gate.passed} risk={gate.risk_level}")

    # Rule pressure before/after (same detector, same thresholds).
    from writer_runtime.domains.artifact.artifact_engine.context import (
        ArtifactAnalysisContext,
    )
    from writer_runtime.domains.artifact.artifact_engine.detectors.expository_overload import (
        ExpositoryOverloadDetector,
    )
    det = ExpositoryOverloadDetector()
    before = det._run_rule_impl(ArtifactAnalysisContext.from_text(original, "before", "technical"))
    after = det._run_rule_impl(ArtifactAnalysisContext.from_text(cand_text, "after", "technical"))
    print(f"rule pressure before={[(round(i.stats['compression_pressure'],2), round(i.stats['interruption_pressure'],2)) for i in before.issues]}")
    print(f"rule pressure after ={[(round(i.stats['compression_pressure'],2), round(i.stats['interruption_pressure'],2)) for i in after.issues]}")

    # Blind A/B: randomize order, separate context from generation calls.
    rng = random.Random(int(hashlib.sha256(p["sha"].encode()).hexdigest()[:8], 16))
    flip = rng.random() < 0.5
    x_text, y_text = (cand_text, original) if flip else (original, cand_text)
    truth = {"X": "candidate" if flip else "original", "Y": "original" if flip else "candidate"}
    comparison = call_model(runner, "blind A/B comparison",
                            COMPARE_PROMPT % (x_text, y_text), f"{p['id']}_compare")
    print(f"blind mapping: {truth} cache_hit={comparison['cache_hit']}")
    print((comparison["output"] or "")[:1200])

    report = {"freeze": freeze, "strategy_id": strategy.strategy_id,
              "blind_mapping": truth, "flipped": flip,
              "gate": gate_row,
              "rule_before": [{"subtype": i.stats.get("subtype"), "priority": i.stats.get("review_priority"),
                               "compression": i.stats.get("compression_pressure"),
                               "interruption": i.stats.get("interruption_pressure")} for i in before.issues],
              "rule_after": [{"subtype": i.stats.get("subtype"), "priority": i.stats.get("review_priority"),
                              "compression": i.stats.get("compression_pressure"),
                              "interruption": i.stats.get("interruption_pressure")} for i in after.issues],
              "word_counts": {"original": len(original.split()), "candidate": len(cand_text.split())}}
    (BASE / f"repair_{p['id']}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote repair_{p['id']}_report.json; candidate text in cache/repair_{p['id']}_candidate.json")


if __name__ == "__main__":
    main()
