from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

EVIDENCE = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02b")
LABELS_DIR = EVIDENCE / "labels"
LABELS_DIR.mkdir(parents=True, exist_ok=True)
SOURCE = Path(r"e:\Users\ernan\Downloads\WRT-EDIT-02B-review-completed.csv")
FROZEN = LABELS_DIR / "WRT-EDIT-02B-review-completed-set1.csv"
CALIBRATION = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a\calibration-passages.json")
FINDINGS = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a\finding-index.csv")
JOINED = LABELS_DIR / "reviewed-labels-joined.csv"
SUMMARY = LABELS_DIR / "agreement-summary.json"
CROSS_TABS = LABELS_DIR / "agreement-cross-tabs.csv"
MANIFEST = LABELS_DIR / "LABEL-MANIFEST.json"

# Preserve the submitted file byte-for-byte before any analysis.
FROZEN.write_bytes(SOURCE.read_bytes())
source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()

rows = list(csv.DictReader(FROZEN.open(encoding="utf-8-sig", newline="")))
assert len(rows) == 50, len(rows)
assert [row["passage_id"] for row in rows] == [f"P{i:02d}" for i in range(1, 51)]
reviewed = [
    row
    for row in rows
    if any(
        (row.get(field) or "").strip()
        for field in (
            "overall_readability_1_5",
            "density",
            "fragmentation",
            "rhythm",
            "lexical_difficulty",
            "structural_clarity",
            "genuine_issue",
            "notes",
        )
    )
]
reviewed_ids = [row["passage_id"] for row in reviewed]
assert len(reviewed_ids) == 10, reviewed_ids
assert len(set(reviewed_ids)) == 10

passages = json.loads(CALIBRATION.read_text(encoding="utf-8"))["passages"]
passage_by_id = {passage["passage_id"]: passage for passage in passages}
assert set(reviewed_ids) <= set(passage_by_id)

finding_severity: defaultdict[str, Counter[str]] = defaultdict(Counter)
for finding in csv.DictReader(FINDINGS.open(encoding="utf-8", newline="")):
    if finding.get("chapter_id"):
        finding_severity[finding["chapter_id"]][finding["severity"]] += 1

DIMENSIONS = (
    "paragraph_load",
    "sentence_load",
    "fragmentation",
    "rhythm",
    "lexical_accessibility",
    "section_structure",
)
HUMAN_FIELDS = (
    "overall_readability_1_5",
    "density",
    "fragmentation",
    "rhythm",
    "lexical_difficulty",
    "structural_clarity",
    "genuine_issue",
    "notes",
)
ALLOWED = {
    "overall_readability_1_5": {"1", "2", "3", "4", "5"},
    "density": {"too_dense", "appropriate", "too_sparse"},
    "fragmentation": {"too_fragmented", "appropriate", "too_continuous"},
    "rhythm": {"too_uniform", "appropriate", "too_irregular"},
    "lexical_difficulty": {"low", "moderate", "high"},
    "structural_clarity": {"clear", "mixed", "unclear"},
    "genuine_issue": {"yes", "no", "unsure"},
}

missing_fields = []
invalid_fields = []
for row in reviewed:
    for field, allowed in ALLOWED.items():
        value = (row.get(field) or "").strip()
        if not value:
            missing_fields.append({"passage_id": row["passage_id"], "field": field})
        elif value not in allowed:
            invalid_fields.append(
                {"passage_id": row["passage_id"], "field": field, "value": value}
            )

joined_rows = []
for row in reviewed:
    pid = row["passage_id"]
    passage = passage_by_id[pid]
    chapter_id = passage["chapter_id"]
    scores = {
        dimension: (passage["chapter_scores"].get(dimension) or {}).get("score")
        for dimension in DIMENSIONS
    }
    bands = {
        dimension: (passage["chapter_scores"].get(dimension) or {}).get("band")
        for dimension in DIMENSIONS
    }
    flags = [
        dimension
        for dimension, band in bands.items()
        if band in {"review", "high"}
    ]
    severities = finding_severity[chapter_id]
    joined = {
        "passage_id": pid,
        "project_id": passage["project_id"],
        "profile": passage["profile"],
        "chapter_id": chapter_id,
        "chapter_title": passage["chapter_title"],
        "relative_path": passage["relative_path"],
        "reviewer": row["reviewer"],
        **{field: (row.get(field) or "").strip() for field in HUMAN_FIELDS},
        **{f"writer_{dimension}_score": scores[dimension] for dimension in DIMENSIONS},
        **{f"writer_{dimension}_band": bands[dimension] for dimension in DIMENSIONS},
        "writer_flagged_dimensions": ";".join(flags),
        "writer_flag_count": len(flags),
        "writer_any_review_flag": bool(flags),
        "writer_high_finding_count": severities.get("high", 0),
        "writer_medium_finding_count": severities.get("medium", 0),
        "writer_low_finding_count": severities.get("low", 0),
        "writer_high_finding": severities.get("high", 0) > 0,
        "writer_min_dimension_score": min(
            [score for score in scores.values() if score is not None], default=None
        ),
        "writer_mean_dimension_score": (
            round(
                sum(score for score in scores.values() if score is not None)
                / len([score for score in scores.values() if score is not None]),
                1,
            )
            if any(score is not None for score in scores.values())
            else None
        ),
    }
    joined_rows.append(joined)

with JOINED.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(joined_rows[0].keys()))
    writer.writeheader()
    writer.writerows(joined_rows)


def rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        average = (index + 1 + end) / 2.0
        for position in range(index, end):
            ranks[order[position]] = average
        index = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - mean_left) ** 2 for a in left)
        * sum((b - mean_right) ** 2 for b in right)
    )
    return round(numerator / denominator, 3) if denominator else None


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(rank(left), rank(right))


human_overall = [int(row["overall_readability_1_5"]) for row in joined_rows]
writer_min = [row["writer_min_dimension_score"] for row in joined_rows]
writer_mean = [row["writer_mean_dimension_score"] for row in joined_rows]
writer_flags = [row["writer_flag_count"] for row in joined_rows]
correlations = {
    "human_overall_vs_writer_min": spearman(human_overall, writer_min),
    "human_overall_vs_writer_mean": spearman(human_overall, writer_mean),
    "human_overall_vs_writer_flag_count": spearman(human_overall, writer_flags),
}

# Dimension cross-tabs. These are descriptive, not scores.
def count_pairs(human_field: str, writer_band: str) -> Counter:
    return Counter((row[human_field] or "missing", row[writer_band] or "missing") for row in joined_rows)


cross_tabs = {
    "density": count_pairs("density", "writer_paragraph_load_band"),
    "fragmentation": count_pairs("fragmentation", "writer_fragmentation_band"),
    "rhythm": count_pairs("rhythm", "writer_rhythm_band"),
    "lexical_difficulty": count_pairs("lexical_difficulty", "writer_lexical_accessibility_band"),
    "structural_clarity": count_pairs("structural_clarity", "writer_section_structure_band"),
}

with CROSS_TABS.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["dimension", "human_label", "writer_band", "count"])
    for dimension, pairs in cross_tabs.items():
        for (human, band), count in sorted(pairs.items()):
            writer.writerow([dimension, human, band, count])


def confusion(flag_key: str) -> dict:
    tp = fn = fp = tn = unsure_flagged = unsure_unflagged = 0
    for row in joined_rows:
        human = row["genuine_issue"]
        writer_flag = bool(row[flag_key])
        if human == "yes":
            tp += int(writer_flag)
            fn += int(not writer_flag)
        elif human == "no":
            fp += int(writer_flag)
            tn += int(not writer_flag)
        elif human == "unsure":
            unsure_flagged += int(writer_flag)
            unsure_unflagged += int(not writer_flag)
    precision = round(tp / (tp + fp), 3) if tp + fp else None
    recall = round(tp / (tp + fn), 3) if tp + fn else None
    accuracy = round((tp + tn) / (tp + fn + fp + tn), 3) if tp + fn + fp + tn else None
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "unsure_flagged": unsure_flagged,
        "unsure_unflagged": unsure_unflagged,
        "precision": precision,
        "recall": recall,
        "accuracy": accuracy,
    }


def by_profile() -> dict:
    out = {}
    for profile in sorted({row["profile"] for row in joined_rows}):
        subset = [row for row in joined_rows if row["profile"] == profile]
        tp = fn = fp = tn = unsure_flagged = unsure_unflagged = 0
        for row in subset:
            if row["genuine_issue"] == "yes":
                tp += int(row["writer_any_review_flag"])
                fn += int(not row["writer_any_review_flag"])
            elif row["genuine_issue"] == "no":
                fp += int(row["writer_any_review_flag"])
                tn += int(not row["writer_any_review_flag"])
            elif row["genuine_issue"] == "unsure":
                unsure_flagged += int(row["writer_any_review_flag"])
                unsure_unflagged += int(not row["writer_any_review_flag"])
        out[profile] = {
            "passages": len(subset),
            "human_yes": sum(1 for row in subset if row["genuine_issue"] == "yes"),
            "human_no": sum(1 for row in subset if row["genuine_issue"] == "no"),
            "human_unsure": sum(1 for row in subset if row["genuine_issue"] == "unsure"),
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "unsure_flagged": unsure_flagged,
            "unsure_unflagged": unsure_unflagged,
        }
    return out


genre_rows = []
for profile in sorted({row["profile"] for row in joined_rows}):
    subset = [row for row in joined_rows if row["profile"] == profile]
    genre_rows.append(
        {
            "profile": profile,
            "passages": len(subset),
            "human_yes": sum(1 for row in subset if row["genuine_issue"] == "yes"),
            "writer_flagged": sum(1 for row in subset if row["writer_any_review_flag"]),
            "human_no": sum(1 for row in subset if row["genuine_issue"] == "no"),
            "human_unsure": sum(1 for row in subset if row["genuine_issue"] == "unsure"),
        }
    )

summary = {
    "schema": "wrt-edit-02b.pilot-agreement.v1",
    "source_file": str(SOURCE),
    "frozen_file": str(FROZEN),
    "source_sha256": source_hash,
    "reviewer": joined_rows[0]["reviewer"],
    "reviewer_status": "AI-assisted with prior diagnostic exposure; not blind human ground truth",
    "rows_total": len(rows),
    "reviewed": len(joined_rows),
    "reviewed_ids": reviewed_ids,
    "missing_fields": missing_fields,
    "invalid_fields": invalid_fields,
    "human_counts": {
        "overall": dict(Counter(row["overall_readability_1_5"] for row in joined_rows)),
        "density": dict(Counter(row["density"] for row in joined_rows)),
        "fragmentation": dict(Counter(row["fragmentation"] or "missing" for row in joined_rows)),
        "rhythm": dict(Counter(row["rhythm"] for row in joined_rows)),
        "lexical": dict(Counter(row["lexical_difficulty"] for row in joined_rows)),
        "structural": dict(Counter(row["structural_clarity"] for row in joined_rows)),
        "genuine": dict(Counter(row["genuine_issue"] for row in joined_rows)),
    },
    "writer_flag_counts": dict(Counter(row["writer_flag_count"] for row in joined_rows)),
    "genre": by_profile(),
    "genre_rows": genre_rows,
    "genuine_issue_confusion_any_review_flag": confusion("writer_any_review_flag"),
    "genuine_issue_confusion_any_high_finding": confusion("writer_high_finding"),
    "correlations": correlations,
    "cross_tabs": {
        dimension: [
            {"human_label": human, "writer_band": band, "count": count}
            for (human, band), count in sorted(pairs.items())
        ]
        for dimension, pairs in cross_tabs.items()
    },
    "per_passage": joined_rows,
}
SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
MANIFEST.write_text(
    json.dumps(
        {
            "schema": "wrt-edit-02b.label-manifest.v1",
            "source_file": str(SOURCE),
            "frozen_file": str(FROZEN),
            "sha256": source_hash,
            "rows_total": len(rows),
            "reviewed": len(joined_rows),
            "reviewed_ids": reviewed_ids,
            "reviewer": joined_rows[0]["reviewer"],
            "reviewer_status": "AI-assisted with prior diagnostic exposure",
            "missing_fields": missing_fields,
            "invalid_fields": invalid_fields,
        },
        indent=2,
    ),
    encoding="utf-8",
)

print("frozen", FROZEN)
print("sha256", source_hash)
print("reviewed", len(joined_rows), reviewed_ids)
print("missing", missing_fields)
print("invalid", invalid_fields)
print("genre", json.dumps(by_profile(), indent=2))
print(
    "confusion any review flag",
    json.dumps(summary["genuine_issue_confusion_any_review_flag"], indent=2),
)
print(
    "confusion any high finding",
    json.dumps(summary["genuine_issue_confusion_any_high_finding"], indent=2),
)
print("correlations", correlations)
print("cross tabs")
for dimension, pairs in cross_tabs.items():
    print(" ", dimension, dict(pairs))
