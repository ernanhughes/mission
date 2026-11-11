"""EXPO-02 Stage C4/C6: compare deterministic-only, semantic-only, hybrid.

Reads scripts/expo02/passages.jsonl + semantic_results.jsonl (rep=0).
Writes scripts/expo02/calibration_report.json + calibration_report.md.

Labels are PROVISIONAL (single implementer-reviewer; language revised samples
are byte-identical to as-found). UNCERTAIN labels are excluded from
precision/recall and reported separately. No thresholds are retuned here.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
POSITIVE = {"EXPO_COMPRESSION", "EXPO_INTERRUPTION", "MIXED"}


def is_positive(label: str | None) -> bool | None:
    if label in POSITIVE:
        return True
    if label == "NO_ISSUE":
        return False
    return None


def main() -> None:
    passages = {p["id"]: p for p in
                (json.loads(line) for line in (BASE / "passages.jsonl").read_text(encoding="utf-8").splitlines())}
    sem = {}
    raw_count = 0
    for line in (BASE / "semantic_results.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        raw_count += 1
        if r.get("rep", 0) == 0:
            sem[r["id"]] = r
    print(f"passages={len(passages)} semantic_rows={raw_count} unique_ids={len(sem)}")

    rows = []
    for pid, p in sorted(passages.items()):
        s = sem.get(pid)
        det_pos = True if p["rule_flagged"] else False
        sem_pos = (s["verdict"] in POSITIVE) if s and s.get("status") == "ok" else None
        sem_invalid = bool(s and s.get("validation_state") in ("INVALID_EVIDENCE", "PROVIDER_ERROR"))
        hybrid_pos = bool(det_pos and sem_pos) if sem_pos is not None else None
        rows.append({
            "id": pid, "selection": p["selection"], "label": p["provisional_label"],
            "det": det_pos, "det_subtype": p["rule_subtype"],
            "sem": sem_pos, "sem_verdict": (s or {}).get("verdict"),
            "sem_severity": (s or {}).get("severity"),
            "sem_invalid": sem_invalid,
            "sem_state": (s or {}).get("validation_state"),
            "hybrid": hybrid_pos,
        })

    def pr(name: str, pred_key: str):
        adjud = [r for r in rows if is_positive(r["label"]) is not None and r[pred_key] is not None]
        tp = sum(1 for r in adjud if r[pred_key] and is_positive(r["label"]))
        fp = sum(1 for r in adjud if r[pred_key] and not is_positive(r["label"]))
        fn = sum(1 for r in adjud if not r[pred_key] and is_positive(r["label"]))
        tn = sum(1 for r in adjud if not r[pred_key] and not is_positive(r["label"]))
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        return {"approach": name, "n_adjudicated": len(adjud), "tp": tp, "fp": fp,
                "fn": fn, "tn": tn,
                "precision": round(prec, 3) if prec is not None else None,
                "recall": round(rec, 3) if rec is not None else None}

    approaches = [pr("deterministic-only", "det"), pr("semantic-only", "sem"), pr("hybrid", "hybrid")]

    fps_det = [r["id"] for r in rows if r["det"] and is_positive(r["label"]) is False]
    fns_det = [r["id"] for r in rows if not r["det"] and is_positive(r["label"]) is True]
    fps_sem = [r["id"] for r in rows if r["sem"] and is_positive(r["label"]) is False]
    fns_sem = [r["id"] for r in rows if r["sem"] is False and is_positive(r["label"]) is True]
    uncertain = [r["id"] for r in rows if r["label"] == "UNCERTAIN"]
    invalid = [r["id"] for r in rows if r["sem_invalid"]]
    missing = [pid for pid in passages if pid not in sem]

    by_subtype = {}
    for verdict in sorted({r["sem_verdict"] for r in rows if r.get("sem_verdict")}):
        by_subtype[verdict] = Counter(r["label"] for r in rows if r["sem_verdict"] == verdict)

    usage_in = sum(
        ((json.loads(open(f, encoding="utf-8").read()).get("usage") or {}).get("input_tokens")) or 0
        for f in BASE.glob("cache/*.json")
    )
    lat = []
    for f in BASE.glob("cache/*.json"):
        d = json.loads(open(f, encoding="utf-8").read())
        if d.get("latency_s"):
            lat.append(d["latency_s"])

    report = {
        "n_passages": len(passages),
        "n_semantic_evaluated": len(sem),
        "n_missing": len(missing),
        "missing_ids": missing,
        "approaches": approaches,
        "deterministic_false_positives": fps_det,
        "deterministic_false_negatives": fns_det,
        "semantic_false_positives": fps_sem,
        "semantic_false_negatives": fns_sem,
        "uncertain_excluded": uncertain,
        "invalid_evidence_ids": invalid,
        "semantic_verdict_by_provisional_label": {k: dict(v) for k, v in by_subtype.items()},
        "total_input_tokens": usage_in,
        "rule_semantic_agreement": {},
        "latency_s": {"n": len(lat), "mean": round(sum(lat) / len(lat), 1) if lat else None,
                      "max": max(lat) if lat else None},
        "note": "All labels provisional (implementer single-reviewer). UNCERTAIN excluded from P/R. "
                "No validated accuracy claimed; no thresholds retuned.",
    }
    (BASE / "calibration_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# EXPO-02 Calibration Report (provisional)", "",
             f"Passages: {len(passages)}; semantically evaluated: {len(sem)}; missing: {len(missing)}.",
             "", "## Approach comparison (UNCERTAIN excluded, provisional labels)",
             "", "| Approach | n | TP | FP | FN | TN | Precision | Recall |",
             "|---|---|---|---|---|---|---|---|"]
    for a in approaches:
        lines.append(f"| {a['approach']} | {a['n_adjudicated']} | {a['tp']} | {a['fp']} | {a['fn']} | {a['tn']} | {a['precision']} | {a['recall']} |")
    lines += ["",
              f"Deterministic false positives (flagged but provisionally clean): {', '.join(fps_det) or 'none'}",
              f"Deterministic false negatives (missed but provisionally positive): {', '.join(fns_det) or 'none'}",
              f"Semantic false positives: {', '.join(fps_sem) or 'none'}",
              f"Semantic false negatives: {', '.join(fns_sem) or 'none'}",
              f"UNCERTAIN (excluded): {', '.join(uncertain)}",
              f"Invalid evidence / provider errors: {', '.join(invalid) or 'none'}",
              "", "## Detector agreement (adjudicated subset with semantic result)", ""]
    both = [r for r in rows if is_positive(r["label"]) is not None and r["sem"] is not None]
    agree = sum(1 for r in both if r["det"] == r["sem"])
    report["rule_semantic_agreement"] = {
        "agree": agree, "n": len(both),
        "rate": round(agree / len(both), 3) if both else None,
    }
    lines.append(f"rule-vs-semantic agreement: {agree}/{len(both)}")
    lines.append(f"rule-positive rate: {sum(1 for r in both if r['det'])}/{len(both)}; "
                 f"semantic-positive rate: {sum(1 for r in both if r['sem'])}/{len(both)}")
    lines.append("hybrid blind spot (semantic-positive but rule-negative; reachable only via sampling, not screening): "
                 + (", ".join(r["id"] for r in both if r["sem"] and not r["det"]) or "none"))
    lines += ["", "## Semantic verdicts by provisional label", ""]
    for verdict, counter in sorted(by_subtype.items()):
        lines.append(f"- {verdict}: {dict(counter)}")
    lines += ["", f"Total input tokens: {usage_in}; latency mean/max: {report['latency_s']}"]
    lines += ["", report["note"]]
    (BASE / "calibration_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
