"""EXPO-02 Stage C1/C2: build the calibration passage set (texts + rule screening).

Outputs scripts/expo02/passages.jsonl with one record per passage:
  id, source, chapter, start_line, end_line, text, sha,
  selection (author_nominated | flagged | random_seed42 | purposive | language | synthetic),
  rule_flagged, rule_subtype, compression, interruption,
  provisional_label (null until adjudicated), label_basis, rationale

Labels/rationale are filled separately and every label stays provisional
until an independent reviewer adjudicates (see labels.json + CALIBRATION doc).
Deterministic thresholds are NOT retuned on this set (spec C2).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

WRITER_RT = Path("C:/Projects/writer/packages/writer-runtime")
WRITER_CORE = Path("C:/Projects/writer/packages/writer-core")
sys.path.insert(0, str(WRITER_RT))
sys.path.insert(0, str(WRITER_CORE))

from writer_runtime.domains.artifact.artifact_engine.context import (  # noqa: E402
    ArtifactAnalysisContext,
)
from writer_runtime.domains.artifact.artifact_engine.detectors.expository_overload import (  # noqa: E402
    ExpositoryOverloadDetector,
    _content_tokens,
    _is_protected_paragraph,
)

INFERENCE = Path("C:/books/inference/content/books/inference")
LANGUAGE = Path("C:/books/language/content/books/language")
LANG_REV = Path("C:/books/language/experiments/LANG-SELF-01/candidates")

OUT = Path(__file__).resolve().parent / "passages.jsonl"

CHAPTERS = ["01-chapter.md", "39-chapter.md", "43-chapter.md"]


def units_for(chapter_path: Path):
    text = chapter_path.read_text(encoding="utf-8")
    ctx = ArtifactAnalysisContext.from_text(text, chapter_path.name, "technical")
    det = ExpositoryOverloadDetector()
    paras = [
        p for p in ctx.paragraphs
        if not p.is_heading and not p.is_separator and p.word_count > 0
        and not _is_protected_paragraph(p.raw)
    ]
    sections, current = [], []
    for p in paras:
        if current and p.start_line_no - current[-1].end_line_no > 6:
            sections.append(current)
            current = []
        current.append(p)
    if current:
        sections.append(current)
    cands = []
    for sec in sections:
        for p in sec:
            cands.append([p])
        for i in range(len(sec) - 1):
            cands.append(sec[i:i + 2])
    units = []
    for window in cands:
        words = sum(p.word_count for p in window)
        if words < det.min_prose_words:
            continue
        sents = []
        for p in window:
            sents.extend(
                ctx.sentences[si].raw for si in p.sentence_indices
                if 0 <= si < len(ctx.sentences)
            )
        feats = det._paragraph_features("\n\n".join(p.raw for p in window), sents)
        union: set = set()
        for p in window:
            union.update(_content_tokens(p.raw))
        feats["distinct_concepts"] = len(union)
        from writer_runtime.domains.artifact.artifact_engine.detectors.expository_overload import (
            _CONCRETE_RE,
        )
        concrete_paras = sum(1 for p in window if _CONCRETE_RE.search(p.raw))
        comp = (
            feats["distinct_concepts"] / 12.0
            + feats["long_sentences"] * 1.2
            + max(0, feats["words"] - 120) / 80.0
            + feats["relative_clauses"] * 0.4
            + feats["parentheticals"] * 0.6
            + (1.5 if concrete_paras == 0 and feats["words"] >= 120 else 0.0)
        )
        intr = (
            feats["qualifications"] * 1.0
            + feats["contrasts"] * 0.8
            + feats["defensive"] * 1.5
            + feats["conditions"] * 0.5
            + feats["transitions"] * 0.7
            + feats["negations"] * 0.15
        )
        flagged = comp >= det.compression_threshold or intr >= det.interruption_threshold
        subtype = (
            "MIXED" if (comp >= det.compression_threshold and intr >= det.interruption_threshold)
            else "EXPO_COMPRESSION" if comp >= det.compression_threshold
            else "EXPO_INTERRUPTION" if intr >= det.interruption_threshold
            else "NONE"
        )
        start = window[0].start_line_no
        end = window[-1].end_line_no
        passage_text = "\n\n".join(p.raw for p in window)
        units.append({
            "chapter": chapter_path.name,
            "start_line": start,
            "end_line": end,
            "text": passage_text,
            "sha": hashlib.sha256(passage_text.encode()).hexdigest()[:16],
            "rule_flagged": flagged,
            "rule_subtype": subtype,
            "compression": round(comp, 2),
            "interruption": round(intr, 2),
            "words": feats["words"],
            "sentences": feats["sentences"],
        })
    # Deduplicate identical spans (1-para units also appear inside pairs? no, spans differ)
    seen, uniq = set(), []
    for u in units:
        key = (u["start_line"], u["end_line"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(u)
    return uniq


def main() -> None:
    rng = random.Random(42)
    records: list[dict] = []

    def add(rec: dict) -> dict:
        rec["id"] = f"P{len(records) + 1:02d}"
        rec["provisional_label"] = None
        rec["label_basis"] = "unadjudicated"
        rec["rationale"] = ""
        records.append(rec)
        return rec

    per_chapter = {c: units_for(INFERENCE / c) for c in CHAPTERS}

    # 1. Author-nominated motivating opening: Ch01 lines ~16-18 region.
    ch01 = per_chapter["01-chapter.md"]
    opener = min(
        (u for u in ch01 if u["start_line"] <= 18 <= u["end_line"] or u["start_line"] in (16, 17, 18)),
        key=lambda u: (u["start_line"], u["end_line"]),
        default=None,
    )
    if opener is None:
        raise RuntimeError("motivating opening unit not found")
    add({**{k: opener[k] for k in ("chapter", "start_line", "end_line", "text", "sha",
            "rule_flagged", "rule_subtype", "compression", "interruption", "words", "sentences")},
         "source": "inference-01-opening", "selection": "author_nominated"})

    # 2. Other flagged units across the three chapters (cap 8, prefer 1-para + variety).
    flagged = [u for c in CHAPTERS for u in per_chapter[c]
               if u["rule_flagged"] and not (u["chapter"] == "01-chapter.md" and u["start_line"] == opener["start_line"] and u["end_line"] == opener["end_line"])]
    flagged.sort(key=lambda u: (u["chapter"], u["start_line"]))
    for u in flagged[:8]:
        add({**{k: u[k] for k in ("chapter", "start_line", "end_line", "text", "sha",
                "rule_flagged", "rule_subtype", "compression", "interruption", "words", "sentences")},
             "source": f"inference-{u['chapter']}", "selection": "flagged"})

    # 3. Random unflagged units, seed 42 (false-negative probe frame).
    unflagged = [u for c in CHAPTERS for u in per_chapter[c] if not u["rule_flagged"]]
    print(f"sampling frame: {len(unflagged)} unflagged units across {CHAPTERS}")
    for u in rng.sample(unflagged, min(10, len(unflagged))):
        add({**{k: u[k] for k in ("chapter", "start_line", "end_line", "text", "sha",
                "rule_flagged", "rule_subtype", "compression", "interruption", "words", "sentences")},
             "source": f"inference-{u['chapter']}", "selection": "random_seed42"})

    # 4. Purposive near-miss units: highest pressure among unflagged.
    near = sorted(unflagged, key=lambda u: max(u["compression"], u["interruption"]), reverse=True)
    taken = {(r["start_line"], r["end_line"], r["chapter"]) for r in records}
    count = 0
    for u in near:
        if (u["start_line"], u["end_line"], u["chapter"]) in taken:
            continue
        add({**{k: u[k] for k in ("chapter", "start_line", "end_line", "text", "sha",
                "rule_flagged", "rule_subtype", "compression", "interruption", "words", "sentences")},
             "source": f"inference-{u['chapter']}", "selection": "purposive"})
        taken.add((u["start_line"], u["end_line"], u["chapter"]))
        count += 1
        if count >= 7:
            break

    # 5/6. Language as-found vs revised candidates (independent samples).
    def paras_of(path: Path, n: int, seed: int):
        text = path.read_text(encoding="utf-8")
        ctx = ArtifactAnalysisContext.from_text(text, path.name, "technical")
        ps = [p for p in ctx.paragraphs
              if not p.is_heading and not p.is_separator and p.word_count >= 40
              and not _is_protected_paragraph(p.raw)]
        r = random.Random(seed)
        return r.sample(ps, min(n, len(ps)))

    lang_chs = ["02-chapter.md", "04-chapter.md", "05-chapter.md"]
    for ch in lang_chs:
        for p in paras_of(LANGUAGE / ch, 2, 7):
            t = p.raw
            add({"chapter": ch, "start_line": p.start_line_no, "end_line": p.end_line_no,
                 "text": t, "sha": hashlib.sha256(t.encode()).hexdigest()[:16],
                 "rule_flagged": False, "rule_subtype": "NONE", "compression": 0.0,
                 "interruption": 0.0, "words": p.word_count,
                 "sentences": len(p.sentence_indices),
                 "source": f"language-{ch}-as-found", "selection": "language"})
    rev_map = {"02-chapter.md": "ch02-language-mediated-revision.md",
               "04-chapter.md": "ch04-language-mediated-revision.md",
               "05-chapter.md": "ch05-language-mediated-revision.md"}
    for ch, rev in rev_map.items():
        rp = LANG_REV / rev
        if not rp.exists():
            print(f"missing revised candidate {rev}; skipping")
            continue
        for p in paras_of(rp, 2, 7):
            t = p.raw
            add({"chapter": rev, "start_line": p.start_line_no, "end_line": p.end_line_no,
                 "text": t, "sha": hashlib.sha256(t.encode()).hexdigest()[:16],
                 "rule_flagged": False, "rule_subtype": "NONE", "compression": 0.0,
                 "interruption": 0.0, "words": p.word_count,
                 "sentences": len(p.sentence_indices),
                 "source": f"language-{rev}", "selection": "language"})

    # 7. Synthetic controls (labels by construction).
    SYN = [
        ("SYN-01 dense-clear NO_ISSUE", "NO_ISSUE",
         "The forward pass evaluates the network on the input tensor. "
         "For a transformer, each layer applies attention, a feed-forward block, and normalisation in sequence. "
         "The output is a score for every vocabulary item at the final position. "
         "Example: with a vocabulary of 50,000 tokens, one forward pass returns 50,000 logits."),
        ("SYN-02 dense-clear NO_ISSUE", "NO_ISSUE",
         "Greedy decoding selects the highest-scoring token at each step and appends it to the input. "
         "The next forward pass therefore conditions on all previously selected tokens. "
         "Example: generating sixteen tokens requires sixteen sequential forward passes plus one for the prompt."),
        ("SYN-03 necessary-caveat NO_ISSUE", "NO_ISSUE",
         "Repeatability was measured under one fixed condition: temperature zero on the recorded CPU. "
         "This result must not be read as a benchmark, because only one configuration ran. "
         "A benchmark claim would require the matched, recorded workload described in the measurement chapter."),
        ("SYN-04 necessary-caveat NO_ISSUE", "NO_ISSUE",
         "Calibration requires a specified prediction target and an empirical test. "
         "Token probabilities alone do not establish that a sentence is true. "
         "Do not treat the model's confidence as a calibrated probability without that test."),
        ("SYN-05 pedagogical-repetition NO_ISSUE", "NO_ISSUE",
         "Performance asks how long the computation took. Quality asks whether the text was useful. "
         "Correctness asks whether the implementation followed its rule. "
         "A fast run can still be unhelpful, and a repeatable run can still be wrong, "
         "so the three questions return deliberately throughout the book."),
        ("SYN-06 purposive UNCERTAIN", "UNCERTAIN",
         "It depends. Sometimes the cache helps a lot. Sometimes it does not help at all. "
         "Things change. Results vary. It is complicated. There are trade-offs. "
         "More work is needed. The details matter. Context decides."),
        ("SYN-07 purposive UNCERTAIN", "UNCERTAIN",
         "The thing is fast. It is also slow. It depends on what you mean by fast. "
         "Fast for whom? Slow compared to what? Hard to say. It works well, mostly. "
         "Except when it doesn't. Which happens."),
        ("SYN-08 interruption EXPO_INTERRUPTION", "EXPO_INTERRUPTION",
         "Before explaining batching, note this is not a benchmark and must not be quoted as one, "
         "and do not conclude the scheduler is optimal, because optimality would require a proof we do not have, "
         "although the basic idea is simple: group requests together. "
         "But even that description, which sounds straightforward, should not be mistaken for an implementation, "
         "since the implementation details, which we have not verified, could differ in ways that matter, "
         "so keep all of that in mind while reading the next sentence: batching shares one model pass across requests."),
    ]
    for tag, label, text in SYN:
        add({"chapter": "synthetic", "start_line": 0, "end_line": 0,
             "text": text, "sha": hashlib.sha256(text.encode()).hexdigest()[:16],
             "rule_flagged": False, "rule_subtype": "NONE", "compression": 0.0,
             "interruption": 0.0, "words": len(text.split()),
             "sentences": text.count("."),
             "source": f"synthetic-{tag.split()[0]}", "selection": "synthetic",
             "provisional_label": label, "label_basis": "construction",
             "rationale": f"Synthetic control constructed as {label}."})

    with OUT.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} passages to {OUT}")


if __name__ == "__main__":
    main()
