from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from writer_core.projects.paths import load_registry
from writer_runtime.projects.manuscript_scope import ProjectManuscriptResolver

ROOT = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a")
STORE = Path(r"C:\Projects\writer\.writer\editing")
AUDIT = ROOT / "audit-all.json"
ANALYSIS = ROOT / "cross-book-analysis.json"
REGISTRY_AUDIT = ROOT / "registry-audit.json"

audit = json.loads(AUDIT.read_text(encoding="utf-8"))
analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
registry_audit = json.loads(REGISTRY_AUDIT.read_text(encoding="utf-8"))
profiles = {row["project_id"]: row["profile"] for row in registry_audit["rows"]}

registry = load_registry()
resolver = ProjectManuscriptResolver(registry=registry)
chapter_hashes: dict[str, dict[str, str]] = {}
for project in registry.list_active():
    try:
        paths = resolver.list_chapter_paths(project.key)
    except Exception:
        paths = []
    files = {}
    for path in paths:
        if (
            path.is_file()
            and path.suffix.lower() in {".md", ".markdown"}
            and not path.stem.startswith("_")
        ):
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    chapter_hashes[project.key] = files

project_ids = sorted(chapter_hashes)
duplicate_pairs = []
for index, left in enumerate(project_ids):
    for right in project_ids[index + 1 :]:
        left_hashes = set(chapter_hashes[left].values())
        right_hashes = set(chapter_hashes[right].values())
        overlap = left_hashes & right_hashes
        if overlap and len(overlap) >= min(len(left_hashes), len(right_hashes)) * 0.5:
            duplicate_pairs.append(
                {
                    "left": left,
                    "right": right,
                    "left_chapters": len(left_hashes),
                    "right_chapters": len(right_hashes),
                    "identical_chapter_hashes": len(overlap),
                    "identical_share_of_smaller": round(
                        len(overlap) / min(len(left_hashes), len(right_hashes)), 3
                    ),
                }
            )

# The Digital Life manuscript is registered twice. Keep the C:\books copy as canonical.
duplicate_groups = []
for pair in duplicate_pairs:
    if {pair["left"], pair["right"]} == {"digital-life", "programmer_ie"}:
        duplicate_groups.append(
            {
                "projects": ["digital-life", "programmer_ie"],
                "canonical": "digital-life",
                "duplicate": "programmer_ie",
                "reason": (
                    "The Digital Life manuscript is registered twice. The C:\\books "
                    "copy is treated as canonical; programmer_ie is a legacy/publication "
                    "copy with one extra chapter and a revised chapter 04."
                ),
                "identical_chapter_hashes": pair["identical_chapter_hashes"],
                "digital_life_chapters": pair["left_chapters"],
                "programmer_ie_chapters": pair["right_chapters"],
            }
        )

excluded = {group["duplicate"] for group in duplicate_groups}
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

distinct_books = [book for book in books if book["project_id"] not in excluded]
distinct_reports = [reports[book["project_id"]] for book in distinct_books]
severities: Counter[str] = Counter()
dimension_bands: defaultdict[str, Counter[str]] = defaultdict(Counter)
profile_summary: defaultdict[str, dict] = defaultdict(
    lambda: {
        "books": 0,
        "chapters": 0,
        "findings": 0,
        "severities": Counter(),
        "dimension_bands": defaultdict(Counter),
    }
)
for book in distinct_books:
    report = reports[book["project_id"]]
    profile = profiles.get(book["project_id"], "unknown")
    profile_summary[profile]["books"] += 1
    profile_summary[profile]["chapters"] += len(report["chapters"])
    profile_summary[profile]["findings"] += len(report["findings"])
    for finding in report["findings"]:
        severities[finding["severity"]] += 1
        profile_summary[profile]["severities"][finding["severity"]] += 1
    for chapter in report["chapters"]:
        for dimension in chapter["dimensions"]:
            dimension_bands[dimension["id"]][dimension["status_band"]] += 1
            profile_summary[profile]["dimension_bands"][dimension["id"]][
                dimension["status_band"]
            ] += 1

distinct_summary = {
    "registered_projects": len(books),
    "distinct_projects": len(distinct_books),
    "excluded_project_ids": sorted(excluded),
    "registered_chapters": sum(len(report["chapters"]) for report in reports.values()),
    "distinct_chapters": sum(len(report["chapters"]) for report in distinct_reports),
    "registered_findings": sum(len(report["findings"]) for report in reports.values()),
    "distinct_findings": sum(len(report["findings"]) for report in distinct_reports),
    "severities": dict(severities),
    "dimension_bands": {key: dict(value) for key, value in dimension_bands.items()},
    "profile_summary": {
        profile: {
            "books": data["books"],
            "chapters": data["chapters"],
            "findings": data["findings"],
            "severities": dict(data["severities"]),
            "dimension_bands": {
                key: dict(value) for key, value in data["dimension_bands"].items()
            },
        }
        for profile, data in sorted(profile_summary.items())
    },
}

analysis["duplicates"] = {
    "schema": "wrt-edit-02a.duplicate-content.v1",
    "groups": duplicate_groups,
    "pairs": duplicate_pairs,
}
analysis["distinct_summary"] = distinct_summary
ANALYSIS.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

duplicate_evidence = {
    "schema": "wrt-edit-02a.duplicate-content.v1",
    "groups": duplicate_groups,
    "pairs": duplicate_pairs,
    "chapter_hashes": {
        project_id: hashes
        for project_id, hashes in chapter_hashes.items()
        if project_id in {"digital-life", "programmer_ie"}
    },
}
(ROOT / "duplicate-content.json").write_text(
    json.dumps(duplicate_evidence, indent=2), encoding="utf-8"
)

print("duplicate groups", json.dumps(duplicate_groups, indent=2))
print("distinct summary", json.dumps({k: distinct_summary[k] for k in ("registered_projects", "distinct_projects", "registered_chapters", "distinct_chapters", "registered_findings", "distinct_findings", "severities")}, indent=2))
