"""Merge adjudicated labels into passages.jsonl (in place)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
recs = [json.loads(line) for line in (BASE / "passages.jsonl").read_text(encoding="utf-8").splitlines()]
labels = json.loads((BASE / "labels.json").read_text(encoding="utf-8"))
SYN_LABELS = {
    "synthetic-SYN-01": ("NO_ISSUE", "Synthetic control constructed as NO_ISSUE."),
    "synthetic-SYN-02": ("NO_ISSUE", "Synthetic control constructed as NO_ISSUE."),
    "synthetic-SYN-03": ("NO_ISSUE", "Synthetic control constructed as NO_ISSUE."),
    "synthetic-SYN-04": ("NO_ISSUE", "Synthetic control constructed as NO_ISSUE."),
    "synthetic-SYN-05": ("NO_ISSUE", "Synthetic control constructed as NO_ISSUE."),
    "synthetic-SYN-06": ("UNCERTAIN", "Synthetic vacuous control; unclear whether this counts as overload."),
    "synthetic-SYN-07": ("UNCERTAIN", "Synthetic vacuous control; unclear whether this counts as overload."),
    "synthetic-SYN-08": ("EXPO_INTERRUPTION", "Synthetic control constructed as EXPO_INTERRUPTION."),
}
for r in recs:
    if r["id"] in labels:
        r["provisional_label"] = labels[r["id"]]["label"]
        r["rationale"] = labels[r["id"]]["rationale"]
        r["label_basis"] = "provisional-single-reviewer (implementer; NOT independent ground truth)"
    elif r["selection"] == "synthetic":
        label, rationale = SYN_LABELS[r["source"]]
        r["provisional_label"] = label
        r["rationale"] = rationale
        r["label_basis"] = "construction (authored as a control)"
with (BASE / "passages.jsonl").open("w", encoding="utf-8") as fh:
    for r in recs:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
missing = [r["id"] for r in recs if not r["provisional_label"]]
print(f"labeled={len(recs) - len(missing)} missing={missing}")
