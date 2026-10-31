from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from writer_runtime.domains.editing.parser import parse_manuscript

ROOT = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a")
STORE = Path(r"C:\Projects\writer\.writer\editing")
AUDIT = ROOT / "audit-all.json"
REGISTRY_AUDIT = ROOT / "registry-audit.json"

audit = json.loads(AUDIT.read_text(encoding="utf-8"))["result"]
profiles = {
    row["project_id"]: row["profile"]
    for row in json.loads(REGISTRY_AUDIT.read_text(encoding="utf-8"))["rows"]
}
reports = {}
for book in audit["books"]:
    if book.get("report_id"):
        reports[book["project_id"]] = json.loads(
            (STORE / "reports" / f"{book['report_id']}.json").read_text(encoding="utf-8")
        )

# (project, chapter order, extraction mode, primary category, tags)
SELECTIONS = [
    # Technical: 30 passages, 11 high / 8 medium / 11 low.
    ("language", 23, "fragmented", "fragmented_sequence", ["technical", "dense_prose"]),
    ("language", 3, "long", "long_dense", ["technical", "lexical"]),
    ("pi", 0, "ordinary", "short_technical_explanation", ["technical"]),
    ("agents-from-first-principles", 0, "ordinary", "ordinary_prose", ["technical"]),
    ("context", 24, "ordinary", "ordinary_prose", ["technical"]),
    ("context", 5, "long", "long_dense", ["technical"]),
    ("memory", 19, "fragmented", "fragmented_sequence", ["technical", "capstone"]),
    ("memory", 14, "structured", "structured_teaching", ["technical"]),
    ("applied-ai", 25, "structured", "structured_teaching", ["technical"]),
    ("debugging-ai", 21, "long", "long_dense", ["technical"]),
    ("debugging-ai", 52, "ordinary", "ordinary_prose", ["technical"]),
    ("context", 21, "long", "lexical_difficulty", ["technical"]),
    ("embeddings-from-first-principles", 18, "ordinary", "long_dense", ["technical"]),
    ("browser-ai-from-first-principles", 11, "fragmented", "fragmented_sequence", ["technical"]),
    ("browser-ai-from-first-principles", 10, "structured", "structured_teaching", ["technical"]),
    ("dspy-from-first-principles", 17, "structured", "structured_teaching", ["technical"]),
    ("dspy-from-first-principles", 16, "structured", "structured_teaching", ["technical"]),
    ("hallucination-from-first-principles", 0, "fragmented", "fragmented_sequence", ["technical"]),
    ("hallucination-from-first-principles", 15, "ordinary", "ordinary_prose", ["technical"]),
    ("pytorch-from-first-principles", 15, "fragmented", "fragmented_sequence", ["technical"]),
    ("pytorch-from-first-principles", 7, "structured", "structured_teaching", ["technical"]),
    ("agents-from-first-principles", 1, "ordinary", "ordinary_prose", ["technical"]),
    ("digital-life", 3, "fragmented", "fragmented_sequence", ["technical", "duplicate_canonical"]),
    ("digital-life", 14, "long", "long_dense", ["technical"]),
    ("advanced-agents-from-first-principles", 0, "structured", "structured_teaching", ["technical"]),
    ("applied-ai", 28, "ordinary", "ordinary_prose", ["technical"]),
    ("agent-architectures", 13, "long", "lexical_difficulty", ["technical"]),
    ("cellular-automata-from-first-principles", 0, "code_adjacent", "code_adjacent", ["technical"]),
    ("freestyle-cognition", 15, "uniform", "uniform_cadence", ["technical"]),
    ("models-from-first-principles", 0, "code_adjacent", "code_adjacent", ["technical"]),
    # Fiction: 20 passages, 13 high / 6 medium / 1 low.
    ("latent", 15, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("latent", 12, "dialogue", "fiction_dialogue", ["fiction"]),
    ("latent", 0, "fragmented", "fiction_fragmented", ["fiction"]),
    ("coin", 3, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("coin", 0, "dialogue", "fiction_dialogue", ["fiction"]),
    ("softwear", 1, "dialogue", "fiction_dialogue", ["fiction"]),
    ("softwear", 16, "long", "fiction_dense", ["fiction", "paragraph_density"]),
    ("axiom_zero", 12, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("axiom_zero", 4, "dialogue", "fiction_dialogue", ["fiction"]),
    ("becoming_alice", 0, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("becoming_alice", 7, "dialogue", "fiction_dialogue", ["fiction"]),
    ("collapse", 5, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("collapse", 11, "dialogue", "fiction_dialogue", ["fiction"]),
    ("goblins", 20, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("goblins", 2, "dialogue", "fiction_dialogue", ["fiction"]),
    ("techno_prophet", 10, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("projection", 36, "dialogue", "fiction_dialogue", ["fiction"]),
    ("projection", 45, "fiction_narrative", "fiction_narrative", ["fiction"]),
    ("projection", 25, "dialogue", "fiction_dialogue", ["fiction"]),
    ("projection", 0, "long", "fiction_dense", ["fiction", "paragraph_density"]),
]

chapters = {}
for project_id, report in reports.items():
    for chapter in report["chapters"]:
        chapters[(project_id, chapter["order"])] = chapter


def paragraph_metrics(paragraphs):
    lengths = [paragraph.word_count for paragraph in paragraphs]
    return {
        "paragraph_count": len(paragraphs),
        "words": lengths,
        "median_paragraph_words": round(statistics.median(lengths), 1) if lengths else 0,
        "sentence_counts": [len(paragraph.sentences) for paragraph in paragraphs],
        "line_start": paragraphs[0].line_start if paragraphs else None,
        "line_end": paragraphs[-1].line_end if paragraphs else None,
    }


def choose(chapter, mode, raw):
    parsed = parse_manuscript(raw, fallback_title=chapter["title"])
    paragraphs = parsed.paragraphs
    if not paragraphs:
        raise RuntimeError(f"No prose paragraphs in {chapter['source_path']} ({mode})")
    if mode == "long":
        return [max(paragraphs, key=lambda paragraph: paragraph.word_count)], parsed, None
    if mode == "fragmented":
        window = None
        for index in range(len(paragraphs) - 5):
            if all(paragraph.word_count <= 25 for paragraph in paragraphs[index : index + 6]):
                window = paragraphs[index : index + 6]
                break
        if window is None:
            order = sorted(range(len(paragraphs)), key=lambda index: paragraphs[index].word_count)
            indexes = sorted(order[: min(6, len(paragraphs))])
            window = [paragraphs[index] for index in indexes]
        return window, parsed, None
    if mode == "uniform":
        best = None
        for index in range(len(paragraphs) - 5):
            window = paragraphs[index : index + 6]
            lengths = [paragraph.word_count for paragraph in window]
            spread = max(lengths) - min(lengths)
            if best is None or spread < best[0]:
                best = (spread, window)
        return (best[1] if best else paragraphs[:6]), parsed, None
    if mode == "code_adjacent":
        lines = raw.splitlines()
        fence_start = None
        fence_end = None
        for index, line in enumerate(lines):
            if re.match(r"^\s*(```|~~~)", line):
                if fence_start is None:
                    fence_start = index + 1
                else:
                    fence_end = index + 1
                    break
        before = [p for p in paragraphs if p.line_end < (fence_start or 1)]
        after = [p for p in paragraphs if fence_end and p.line_start > fence_end]
        window = []
        if before:
            window.extend(before[-2:])
        if after:
            window.extend(after[:2])
        if not window:
            window = paragraphs[:3]
        return window, parsed, {
            "code_fence_start_line": fence_start,
            "code_fence_end_line": fence_end,
        }
    if mode == "structured":
        candidates = parsed.sections[1:] if len(parsed.sections) > 1 else parsed.sections
        candidates = [section for section in candidates if section.paragraph_count >= 2]
        if candidates:
            section = max(
                candidates,
                key=lambda item: sum(
                    paragraph.word_count
                    for paragraph in paragraphs
                    if paragraph.section_index == item.index
                ),
            )
            section_paragraphs = [
                p for p in paragraphs if p.section_index == section.index
            ]
            window = section_paragraphs[:6]
        else:
            window = paragraphs[:6]
        return window, parsed, {"section": window[0].text[:100] if window else None}
    if mode == "dialogue":
        def is_note(paragraph):
            stripped = paragraph.text.strip()
            return (
                stripped.startswith("*(")
                or (stripped.startswith("*") and stripped.endswith("*"))
                or re.match(r"^\(?(?:Forward|Second|Third|Fourth) book\.", stripped)
                is not None
            )
        quoted = [
            index
            for index, paragraph in enumerate(paragraphs)
            if not is_note(paragraph)
            and paragraph.word_count >= 12
            and re.search(r'["“”]', paragraph.text)
        ]
        window = None
        for index in quoted:
            candidate = [paragraphs[index]]
            for offset in (1, 2, 3):
                next_index = index + offset
                if next_index < len(paragraphs) and not is_note(paragraphs[next_index]):
                    candidate.append(paragraphs[next_index])
            window = candidate
            break
        if window is None:
            window = [
                p
                for p in paragraphs
                if not is_note(p) and p.word_count >= 20
            ][:2] or paragraphs[:2]
        return window, parsed, None
    if mode == "fiction_narrative":
        def is_note(paragraph):
            stripped = paragraph.text.strip()
            return (
                stripped.startswith("*(")
                or (stripped.startswith("*") and stripped.endswith("*"))
                or re.match(r"^\(?(?:Forward|Second|Third|Fourth) book\.", stripped)
                is not None
            )
        window = [
            p for p in paragraphs if not is_note(p) and p.word_count >= 20
        ][:2] or paragraphs[:2]
        return window, parsed, None
    window = [p for p in paragraphs if p.word_count >= 25][:2] or paragraphs[:2]
    return window, parsed, None


passages = []
form_rows = []
for number, (project_id, order, mode, category, tags) in enumerate(SELECTIONS, 1):
    chapter = chapters[(project_id, order)]
    raw = Path(chapter["source_path"]).read_text(encoding="utf-8", errors="replace")
    window, parsed, extra = choose(chapter, mode, raw)
    text = "\n\n".join(paragraph.text for paragraph in window)
    if len(text) > 1600:
        text = text[:1590].rsplit(" ", 1)[0] + "…"
    dimensions = {
        dimension["id"]: {
            "score": dimension["score"],
            "band": dimension["status_band"],
            "finding_codes": dimension["finding_codes"],
        }
        for dimension in chapter["dimensions"]
    }
    scores = [dimension["score"] for dimension in chapter["dimensions"] if dimension["score"] is not None]
    stratum = "high" if min(scores) < 40 else ("medium" if min(scores) < 80 else "low")
    passage = {
        "passage_id": f"P{number:02d}",
        "project_id": project_id,
        "profile": profiles.get(project_id, "unknown"),
        "chapter_id": chapter["chapter_id"],
        "chapter_title": chapter["title"],
        "chapter_order": chapter["order"],
        "source_path": chapter["source_path"],
        "relative_path": chapter["relative_path"],
        "category": category,
        "tags": tags,
        "extraction_mode": mode,
        "diagnostic_stratum": stratum,
        "chapter_scores": dimensions,
        "chapter_finding_codes": chapter["finding_codes"],
        "paragraph_metrics": paragraph_metrics(window),
        "section": extra.get("section") if extra else None,
        "code_fence_start_line": extra.get("code_fence_start_line") if extra else None,
        "code_fence_end_line": extra.get("code_fence_end_line") if extra else None,
        "text": text,
        "limitations": [
            "Writer dimensions are chapter-level; passage labels are not independent literary judgments.",
            "Excerpts omit most of the chapter and surrounding context.",
            "Paragraph and sentence metrics exclude code, tables, headings and lists.",
        ],
    }
    passages.append(passage)
    form_rows.append(
        {
            "passage_id": passage["passage_id"],
            "reviewer": "",
            "overall_readability_1_5": "",
            "density": "",
            "fragmentation": "",
            "rhythm": "",
            "lexical_difficulty": "",
            "structural_clarity": "",
            "genuine_issue": "",
            "notes": "",
        }
    )

(ROOT / "calibration-passages.json").write_text(
    json.dumps(
        {
            "schema": "wrt-edit-02a.calibration-passages.v2",
            "passage_count": len(passages),
            "diagnostic_key": "writer-editing-report-v1 chapter scores; no passage-level ground truth",
            "distinct_manuscripts": 27,
            "duplicate_registration_excluded": "programmer_ie",
            "passages": passages,
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
with (ROOT / "calibration-review-template.csv").open(
    "w", encoding="utf-8", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=list(form_rows[0].keys()))
    writer.writeheader()
    writer.writerows(form_rows)

print("passages", len(passages))
print("strata", Counter(p["diagnostic_stratum"] for p in passages))
print("categories", Counter(p["category"] for p in passages))
print("profiles", Counter(p["profile"] for p in passages))
for passage in passages:
    print(
        passage["passage_id"],
        passage["profile"],
        passage["project_id"],
        passage["chapter_order"],
        passage["category"],
        passage["diagnostic_stratum"],
        passage["paragraph_metrics"]["words"],
        passage["text"][:70].replace("\n", " "),
    )
