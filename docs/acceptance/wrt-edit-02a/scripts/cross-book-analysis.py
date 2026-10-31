from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a")
STORE = Path(r"C:\Projects\writer\.writer\editing")
AUDIT = ROOT / "audit-all.json"
REGISTRY_AUDIT = ROOT / "registry-audit.json"

audit = json.loads(AUDIT.read_text(encoding="utf-8"))
registry_audit = json.loads(REGISTRY_AUDIT.read_text(encoding="utf-8"))
profiles = {row["project_id"]: row["profile"] for row in registry_audit["rows"]}

books = [
    book
    for book in audit["result"]["books"]
    if book["status"] not in {"BLOCKED", "NO_MANUSCRIPT"} and book.get("report_id")
]
reports = {
    book["project_id"]: json.loads(
        (STORE / "reports" / f"{book['report_id']}.json").read_text(encoding="utf-8")
    )
    for book in books
}

DIMENSIONS = (
    "paragraph_load",
    "sentence_load",
    "fragmentation",
    "rhythm",
    "lexical_accessibility",
    "section_structure",
)
SEVERITIES = ("high", "medium", "low", "info")

code_counts: Counter[str] = Counter()
severity_counts: Counter[str] = Counter()
dimension_bands: defaultdict[str, Counter[str]] = defaultdict(Counter)
dimension_scores: defaultdict[str, list[float]] = defaultdict(list)
profile_data: defaultdict[str, dict] = defaultdict(
    lambda: {
        "books": 0,
        "chapters": 0,
        "findings": 0,
        "severities": Counter(),
        "code_counts": Counter(),
        "dimension_bands": defaultdict(Counter),
        "dimension_scores": defaultdict(list),
    }
)
book_rows: list[dict] = []
chapter_rows: list[dict] = []
finding_rows: list[dict] = []

for book in books:
    project_id = book["project_id"]
    profile = profiles.get(project_id, "unknown")
    report = reports[project_id]
    findings_by_chapter: defaultdict[str, list[dict]] = defaultdict(list)
    for finding in report["findings"]:
        code_counts[finding["code"]] += 1
        severity_counts[finding["severity"]] += 1
        profile_data[profile]["code_counts"][finding["code"]] += 1
        profile_data[profile]["severities"][finding["severity"]] += 1
        locator = finding.get("locator") or {}
        finding_rows.append(
            {
                "project_id": project_id,
                "profile": profile,
                "report_id": report["report_id"],
                "chapter_id": finding.get("chapter_id") or "",
                "code": finding["code"],
                "severity": finding["severity"],
                "relative_path": locator.get("relative_path") or "",
                "line_start": locator.get("line_start") or "",
                "line_end": locator.get("line_end") or "",
                "section": locator.get("section_title") or "",
                "reason": finding["reason"],
            }
        )
        if finding.get("chapter_id"):
            findings_by_chapter[finding["chapter_id"]].append(finding)

    for chapter in report["chapters"]:
        chapter_findings = findings_by_chapter.get(chapter["chapter_id"], [])
        high_medium = sum(
            1 for finding in chapter_findings if finding["severity"] in {"high", "medium"}
        )
        dimensions = {dimension["id"]: dimension for dimension in chapter["dimensions"]}
        flagged = [
            dimension["id"]
            for dimension in chapter["dimensions"]
            if dimension["status_band"] in {"review", "high"}
        ]
        for dimension in chapter["dimensions"]:
            dimension_bands[dimension["id"]][dimension["status_band"]] += 1
            profile_data[profile]["dimension_bands"][dimension["id"]][
                dimension["status_band"]
            ] += 1
            if dimension["score"] is not None:
                dimension_scores[dimension["id"]].append(dimension["score"])
                profile_data[profile]["dimension_scores"][dimension["id"]].append(
                    dimension["score"]
                )
        row = {
            "project_id": project_id,
            "profile": profile,
            "report_id": report["report_id"],
            "chapter_id": chapter["chapter_id"],
            "chapter_order": chapter["order"],
            "title": chapter["title"],
            "relative_path": chapter["relative_path"],
            "word_count": chapter["word_count"],
            "paragraph_count": chapter["paragraph_count"],
            "sentence_count": chapter["sentence_count"],
            "status": chapter["status"],
            "status_band": chapter["status_band"],
            "flagged_dimensions": flagged,
            "high_medium_findings": high_medium,
            "all_findings": len(chapter_findings),
            "finding_codes": chapter["finding_codes"],
            "scores": {
                dimension["id"]: dimension["score"]
                for dimension in chapter["dimensions"]
            },
            "bands": {
                dimension["id"]: dimension["status_band"]
                for dimension in chapter["dimensions"]
            },
            "metrics": {
                dimension["id"]: {
                    key: dimension["raw_metrics"].get(key)
                    for key in (
                        "median_paragraph_words",
                        "p90_paragraph_words",
                        "longest_paragraph_words",
                        "p90_sentence_words",
                        "longest_sentence_words",
                        "short_percent",
                        "one_sentence_percent",
                        "max_consecutive_short_run",
                        "uniform_paragraph_share",
                        "iqr_words",
                        "narrow_distribution",
                        "flesch_reading_ease",
                        "estimated_flesch_kincaid_grade",
                        "section_count",
                        "heading_density_per_1000_words",
                        "trivial_sections",
                        "longest_section_words",
                    )
                }
                for dimension in chapter["dimensions"]
            },
        }
        chapter_rows.append(row)

    profile_data[profile]["books"] += 1
    profile_data[profile]["chapters"] += len(report["chapters"])
    profile_data[profile]["findings"] += len(report["findings"])
    book_rows.append(
        {
            "project_id": project_id,
            "profile": profile,
            "report_id": report["report_id"],
            "title": report["book"]["title"],
            "chapters": len(report["chapters"]),
            "findings": len(report["findings"]),
            "high_medium_findings": sum(
                1
                for finding in report["findings"]
                if finding["severity"] in {"high", "medium"}
            ),
            "highest_risk": report["readability"]["highest_risk"],
            "subdimensions": {
                dimension["id"]: {
                    "worst_score": dimension["worst_score"],
                    "worst_band": dimension["worst_band"],
                    "worst_chapter_id": dimension["worst_chapter_id"],
                    "chapters_flagged": dimension["chapters_flagged"],
                }
                for dimension in report["readability"]["subdimensions"]
            },
        }
    )


def risk_key(row: dict) -> tuple:
    severity = (
        2
        if any(band == "high" for band in row["bands"].values())
        else (1 if any(band == "review" for band in row["bands"].values()) else 0)
    )
    return (
        -row["high_medium_findings"],
        -severity,
        min([score for score in row["scores"].values() if score is not None], default=101),
    )


high_risk = sorted(chapter_rows, key=risk_key)[:50]
high_risk_by_book: dict[str, list[dict]] = {}
for project_id in {row["project_id"] for row in chapter_rows}:
    rows = [row for row in chapter_rows if row["project_id"] == project_id]
    rows.sort(key=lambda row: (-row["high_medium_findings"], min([s for s in row["scores"].values() if s is not None], default=101), row["chapter_order"]))
    high_risk_by_book[project_id] = rows[:3]


def compact(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "project_id",
            "profile",
            "chapter_id",
            "chapter_order",
            "title",
            "relative_path",
            "scores",
            "bands",
            "metrics",
            "high_medium_findings",
            "finding_codes",
        )
    }


artifacts = {
    "section_density_0": [
        compact(row)
        for row in chapter_rows
        if row["scores"].get("section_structure") == 0
        and (row["metrics"]["section_structure"].get("section_count") or 0) >= 50
    ][:30],
    "fragmentation_0_short_median": [
        compact(row)
        for row in chapter_rows
        if row["scores"].get("fragmentation") == 0
        and (row["metrics"]["paragraph_load"].get("median_paragraph_words") or 99) < 10
    ][:30],
    "lexical_0_low_fre": [
        compact(row)
        for row in chapter_rows
        if row["scores"].get("lexical_accessibility") == 0
        and (row["metrics"]["lexical_accessibility"].get("flesch_reading_ease") or 99) < 20
    ][:30],
    "language_paragraph_watch": [
        compact(row)
        for row in chapter_rows
        if row["project_id"] == "language"
        and row["bands"].get("paragraph_load") == "watch"
    ][:30],
    "fiction_fragmentation_high": [
        compact(row)
        for row in chapter_rows
        if row["profile"] == "fiction"
        and row["bands"].get("fragmentation") == "high"
    ][:30],
    "technical_short_paragraphs": [
        compact(row)
        for row in chapter_rows
        if row["profile"] == "technical"
        and (row["metrics"]["paragraph_load"].get("median_paragraph_words") or 99) < 10
    ][:30],
    "long_section_high": [
        compact(row)
        for row in chapter_rows
        if "READABILITY.LONG_SECTION" in row["finding_codes"]
    ][:30],
}


def summarize_profile(data: dict) -> dict:
    return {
        "books": data["books"],
        "chapters": data["chapters"],
        "findings": data["findings"],
        "severities": dict(data["severities"]),
        "code_counts": dict(data["code_counts"]),
        "dimension_bands": {
            key: dict(value) for key, value in data["dimension_bands"].items()
        },
        "dimension_score_stats": {
            key: {
                "count": len(values),
                "min": min(values),
                "median": round(statistics.median(values), 1),
                "max": max(values),
            }
            for key, values in data["dimension_scores"].items()
        },
    }


output = {
    "schema": "wrt-edit-02a.cross-book-analysis.v2",
    "audit_report_ids": {book["project_id"]: book["report_id"] for book in books},
    "projects": book_rows,
    "profile_summary": {
        profile: summarize_profile(data)
        for profile, data in sorted(profile_data.items())
    },
    "code_counts": dict(code_counts),
    "severity_counts": dict(severity_counts),
    "dimension_bands": {key: dict(value) for key, value in dimension_bands.items()},
    "dimension_score_stats": {
        key: {
            "count": len(values),
            "min": min(values),
            "median": round(statistics.median(values), 1),
            "max": max(values),
        }
        for key, values in dimension_scores.items()
    },
    "high_risk_chapters": high_risk,
    "high_risk_by_book": high_risk_by_book,
    "artifacts": artifacts,
    "chapter_count": len(chapter_rows),
    "finding_count": len(finding_rows),
}
(ROOT / "cross-book-analysis.json").write_text(
    json.dumps(output, indent=2), encoding="utf-8"
)

chapter_fields = [
    "project_id",
    "profile",
    "report_id",
    "chapter_id",
    "chapter_order",
    "title",
    "relative_path",
    "word_count",
    "paragraph_count",
    "sentence_count",
    "status",
    "finding_codes",
    "high_medium_findings",
]
for dimension in DIMENSIONS:
    chapter_fields.extend([f"{dimension}_score", f"{dimension}_band"])
with (ROOT / "chapter-baseline.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=chapter_fields)
    writer.writeheader()
    for row in chapter_rows:
        flat = {
            key: row[key]
            for key in (
                "project_id",
                "profile",
                "report_id",
                "chapter_id",
                "chapter_order",
                "title",
                "relative_path",
                "word_count",
                "paragraph_count",
                "sentence_count",
                "status",
                "finding_codes",
                "high_medium_findings",
            )
        }
        flat["finding_codes"] = ";".join(row["finding_codes"])
        for dimension in DIMENSIONS:
            flat[f"{dimension}_score"] = row["scores"].get(dimension)
            flat[f"{dimension}_band"] = row["bands"].get(dimension)
        writer.writerow(flat)
with (ROOT / "finding-index.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(finding_rows[0].keys()))
    writer.writeheader()
    writer.writerows(finding_rows)

print("books", len(books), "chapters", len(chapter_rows), "findings", len(finding_rows))
print("severities", dict(severity_counts))
print("profiles", {profile: data["books"] for profile, data in profile_data.items()})
print("artifacts", {key: len(value) for key, value in artifacts.items()})
