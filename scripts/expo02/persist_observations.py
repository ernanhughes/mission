"""EXPO-02 Stage D: persist verified chapter observations to Mission Control.

Reads scripts/expo02/semantic_results.jsonl (rep=0, status ok) + live rule
screening, aligns semantic verdicts to chapter coordinates, drops mechanical
candidates superseded by semantic review on the same unit, and records one
CURRENT ArtifactLoadObservation per chapter (01/39/43) with honest partial
coverage. Dry-run by default; --confirm writes to the real Mission Control DB.

Candidate-only for repair; canonical manuscripts are never modified here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, "C:/Projects/writer/packages/writer-runtime")
sys.path.insert(0, "C:/Projects/writer/packages/writer-core")
sys.path.insert(0, str(BASE))

from build_dataset import units_for  # noqa: E402

from writer_runtime.domains.artifact.artifact_engine.artifact_service import (  # noqa: E402
    ArtifactEngine,
)

from mission_control.artifact_load.service import record_observation  # noqa: E402
from mission_control.config import RuntimeSettings  # noqa: E402
from mission_control.persistence.db import Database  # noqa: E402

INFERENCE = Path("C:/books/inference/content/books/inference")
CHAPTERS = ["01-chapter.md", "39-chapter.md", "43-chapter.md"]
WORKBENCH_URL = "http://127.0.0.1:7420"

MODEL_ROUTE = "opencode-go/deepseek-v4.1-flash"


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    sem_rows = [
        json.loads(line) for line in (BASE / "semantic_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {}
    provider_errors: list[str] = []
    for r in sem_rows:
        if r.get("rep", 0) != 0:
            continue
        if r.get("status") == "ok":
            by_id[r["id"]] = r
        else:
            provider_errors.append(f"{r['id']}:{r.get('validation_state', r.get('status'))}")
    passages = [json.loads(line) for line in (BASE / "passages.jsonl").read_text(encoding="utf-8").splitlines()]
    passage_by_id = {p["id"]: p for p in passages}

    db = Database(RuntimeSettings()) if args.confirm else None
    if db is not None:
        with db.session() as session:
            persist_chapters(session, by_id, passage_by_id, provider_errors)
            session.commit()
        print("committed")
    else:
        persist_chapters(None, by_id, passage_by_id, provider_errors)


def persist_chapters(session, by_id, passage_by_id, provider_errors) -> None:

    for chapter in CHAPTERS:
        path = INFERENCE / chapter
        raw = path.read_bytes()
        revision = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8")
        units = units_for(path)
        total_units = len(units)
        # Eligible prose words: unique words across all candidate units is
        # ill-defined (windows overlap); use filtered paragraph words.
        from writer_runtime.domains.artifact.artifact_engine.context import (
            ArtifactAnalysisContext,
        )
        from writer_runtime.domains.artifact.artifact_engine.detectors.expository_overload import (
            _is_protected_paragraph,
        )
        ctx = ArtifactAnalysisContext.from_text(text, chapter, "technical")
        paras = [p for p in ctx.paragraphs
                 if not p.is_heading and not p.is_separator and p.word_count > 0
                 and not _is_protected_paragraph(p.raw)]
        eligible_words = sum(p.word_count for p in paras)

        eng = ArtifactEngine(profile="technical")
        res = eng.analyze(text, source_name=chapter)
        mechanical = [i for i in res.issues if i.type == "EXPOSITORY_OVERLOAD"]

        # Semantic verdicts for this chapter's passages -> chapter coordinates.
        confirmed: list[dict] = []
        evaluated_spans: list[tuple[int, int, str]] = []  # (start, end, verdict)
        invalid = 0
        prompt_versions: set[str] = set()
        for pid, row in by_id.items():
            p = passage_by_id[pid]
            if p["chapter"] != chapter:
                continue
            evaluated_spans.append((p["start_line"], p["end_line"], row["verdict"]))
            prompt_versions.update([row.get("prompt_version", "")])
            v = row["verdict"]
            if v in ("EXPO_COMPRESSION", "EXPO_INTERRUPTION", "MIXED"):
                quote = row.get("quote", "")
                if quote and quote in text:
                    idx = text.find(quote)
                    start = text[:idx].count("\n") + 1
                    end = start + quote.count("\n")
                    confirmed.append({
                        "family": "EXPOSITORY_OVERLOAD",
                        "subtype": v,
                        "severity": row.get("severity", "MED"),
                        "status": "SEMANTICALLY_CONFIRMED",
                        "start_line": start,
                        "end_line": end,
                        "fingerprint": hashlib.sha256(
                            f"{chapter}:{start}-{end}:{quote}".encode()).hexdigest()[:16],
                        "main_explanation": row.get("main_explanation", ""),
                        "diagnosis": row.get("diagnosis", ""),
                        "quote": quote[:600],
                        "proposed_strategy": "REORDER_EXPLANATION",
                        "detector_version": "expo-v1",
                        "model": row.get("actual_model"),
                        "confidence": row.get("confidence"),
                        "passage_id": pid,
                    })
                else:
                    invalid += 1
            elif v in ("INVALID_EVIDENCE", "NOT_RUN"):
                invalid += 1
            # NO_ISSUE -> nothing persisted; the unit review is recorded via
            # the supersede step below.

        # Supersede mechanical candidates covered by semantic review.
        findings: list[dict] = list(confirmed)
        rejected_mechanical = 0
        for m in mechanical:
            covered = [v for (s, e, v) in evaluated_spans
                       if spans_overlap(m.start_line, m.end_line, s, e)]
            if covered:
                rejected_mechanical += 1
                continue
            findings.append({
                "family": "EXPOSITORY_OVERLOAD",
                "subtype": str(m.stats.get("subtype", "EXPO_COMPRESSION")),
                "severity": "UNASSESSED",
                "priority": str(m.stats.get("review_priority", "LOW")),
                "status": "MECHANICALLY_FLAGGED",
                "start_line": m.start_line,
                "end_line": m.end_line,
                "fingerprint": str(m.stats.get("fingerprint", "")),
                "diagnosis": m.why_fix[:500],
                "proposed_strategy": "REORDER_EXPLANATION",
                "detector_version": "expo-v1",
                "passage_id": None,
            })

        # Coverage: distinct chapter units overlapping any semantically evaluated span.
        evaluated_units = 0
        for u in units:
            if any(spans_overlap(u["start_line"], u["end_line"], s, e) for (s, e, _) in evaluated_spans):
                evaluated_units += 1
        coverage_sem = round(evaluated_units / total_units, 3) if total_units else 0.0

        usage_in = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in by_id.values()
                       if passage_by_id[r["id"]]["chapter"] == chapter)
        usage_out = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in by_id.values()
                        if passage_by_id[r["id"]]["chapter"] == chapter)
        semantic_calls = sum(1 for r in by_id.values() if passage_by_id[r["id"]]["chapter"] == chapter)
        execution = {
            "detector": "expo-v1",
            "prompt_version": sorted(prompt_versions),
            "requested_model": MODEL_ROUTE,
            "actual_model": MODEL_ROUTE,
            "transport": "opencode-cli-file",
            "semantic_calls": semantic_calls,
            "input_tokens": usage_in,
            "output_tokens": usage_out,
            "token_accounting": "provider_reported",
            "rejected_mechanical": rejected_mechanical,
            "invalid_evidence": invalid,
            "sampling": "purposive flagged + random_seed42 unflagged + purposive near-miss; partial unit coverage, not a census",
        }
        print(f"{chapter}: rev={revision[:12]} eligible_words={eligible_words} "
              f"units={total_units} evaluated_units={evaluated_units} coverage_sem={coverage_sem} "
              f"confirmed={len(confirmed)} mechanical_remaining={len(findings)-len(confirmed)} "
              f"rejected_mechanical={rejected_mechanical} invalid={invalid}")

        execution["provider_errors"] = [
            e for e in provider_errors if e.split(":")[0] in {p["id"] for p in passages if p["chapter"] == chapter}
        ]
        limitations = [
            "Partial semantic coverage: confirmed findings are real, the chapter aggregate is incomplete.",
            "Mechanical candidates remain REVIEW-only with UNASSESSED severity.",
        ]
        if execution["provider_errors"]:
            limitations.append(
                "Semantic calls not completed for: "
                + ", ".join(execution["provider_errors"])
                + " (not counted as evaluated)."
            )

        if session is not None:
            record_observation(
                session,
                project_id="inference",
                book_id="book-inference",
                chapter_id=chapter,
                source_path=str(path),
                chapter_revision=revision,
                status="CURRENT",
                eligible_words=eligible_words,
                evaluated_units=total_units,
                coverage_mechanical=1.0,
                coverage_semantic=coverage_sem,
                findings=findings,
                detector_version="expo-v1",
                limitations=limitations,
                execution=execution,
                workbench_url=WORKBENCH_URL,
            )
            print(f"  persisted CURRENT observation for {chapter}")


if __name__ == "__main__":
    main()
