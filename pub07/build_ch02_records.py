"""PUB-07 fix-batch record assembly for the Ch2 re-run (D-PUB-81, Fix F).

Reads a successful `transform automate` out-dir (candidate.md,
program.json, verification.json, transformation-record.json,
staged.json) plus the live chapter bytes (read-only) and writes:

- proposal.json (Workbench bridge record + freshness check)
- approval-decision.json (author-side record with Fix F supersede notes)
- program.json annotation (labeled author-side, not dispatch output)

Plus a disposable-fixture proof with the real
`C:\\books\\jev\\scripts\\apply_edits.py` (forward apply == candidate
bytes, reverse apply == pristine bytes).

Run ONLY after a successful bounded re-run; refuses otherwise.
Usage (CWD anywhere, workbench src importable)::

    python pub07/build_ch02_records.py <out_dir> <book_chapter_md>

Zero authoritative writes: inputs are read; outputs land in <out_dir>
(candidate + staging + fixtures only, per the fix-batch boundary).
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main(out_dir: str, chapter_md: str) -> int:
    out = Path(out_dir)
    program = _read_json(out / "program.json")
    verification = _read_json(out / "verification.json")
    record = _read_json(out / "transformation-record.json")
    candidate_raw = (out / "candidate.md").read_bytes()
    chapter_raw = Path(chapter_md).read_bytes()

    outcome = program.get("outcome")
    if outcome not in ("review_accepted", "verified_pass"):
        print(f"REFUSING: program outcome is {outcome!r} "
              f"(expected review_accepted or verified_pass). "
              f"Record the outcome, do not assemble records.")
        return 1
    if verification.get("verdict") != "pass":
        print("REFUSING: verification verdict is not pass.")
        return 1

    # --- Join checks (Fix D): every link recomputed, never trusted. ---
    chain = record.get("chain", {})
    candidate_fp = hashlib.sha256(_lf_bytes(candidate_raw)).hexdigest()
    assert candidate_fp == chain.get("candidate_fingerprint"), \
        "candidate file bytes do not join the record chain"
    after_fp = (verification.get("after") or {}).get("fingerprint")
    assert after_fp == candidate_fp, \
        f"verification after {after_fp} != candidate {candidate_fp}"

    ledger = record.get("dispatch_ledger") or {}
    assert ledger.get("entries"), "record carries no dispatch ledger"
    assert chain.get("ledger_digest"), "record chain lacks ledger_digest"

    lineage = program.get("editorial_loop", {}).get("final_lineage") or []
    cand_text = _lf_bytes(candidate_raw).decode("utf-8")
    cand_lines = cand_text.split("\n")
    if cand_lines and cand_lines[-1] == "":
        cand_lines = cand_lines[:-1]
    disp = [int(e.get("line", 0)) for e in lineage
            if isinstance(e, dict) and e.get("origin") == "dispatch"]
    assert disp, "no dispatch region in final lineage"
    region = cand_lines[min(disp) - 1:max(disp)]
    region_sha = hashlib.sha256("\n".join(region).encode()).hexdigest()
    bound_rows = [e for e in ledger["entries"]
                  if isinstance(e, dict)
                  and e.get("replacement_sha256") == region_sha]
    assert bound_rows, \
        "no ledger row binds the candidate replacement region"

    # --- Span + chapter binding. ---
    pkg_id = program.get("package_id")
    pkgs = ((record.get("work_packages") or {}).get("packages") or [])
    pkg = next((p for p in pkgs if isinstance(p, dict)
                and p.get("package_id") == pkg_id), None)
    assert pkg is not None, f"package {pkg_id!r} not in record"
    spans = {(s.get("start_line"), s.get("end_line"))
             for s in (pkg.get("source_spans") or []) if isinstance(s, dict)}
    assert len(spans) == 1, f"expected one source span, got {spans}"
    start, end = next(iter(spans))
    chapter_text = _lf_bytes(chapter_raw).decode("utf-8")
    chapter_lines = chapter_text.split("\n")
    source_lines = chapter_lines[start - 1:end]
    assert len(source_lines) == end - start + 1

    try:
        from workbench.publication_proposals import (
            build_candidate_proposal,
            chapter_fingerprint,
            check_proposal_fresh,
            ledger_digest,
            proposal_to_record,
        )
    except ImportError:
        sys.path.insert(0, r"C:\Projects\workbench\src")
        from workbench.publication_proposals import (  # noqa: E402
            build_candidate_proposal,
            chapter_fingerprint,
            check_proposal_fresh,
            ledger_digest,
            proposal_to_record,
        )
    proposal = build_candidate_proposal(
        proposal_id="pub07-ch02-p001",
        chapter_id="02-chapter",
        span={"start_line": start, "end_line": end},
        source_lines=source_lines,
        replacement_lines=region,
        source_fingerprint=chapter_fingerprint(chapter_text),
        plan_id=record.get("plan_id"),
        package_id=pkg_id,
        finding_refs=list(pkg.get("finding_refs") or []),
        verification={"verdict": verification.get("verdict"),
                      "checks_passed": verification.get("checks_passed"),
                      "checks_failed": verification.get("checks_failed")},
        dispatch_ledger=ledger,
        candidate_fingerprint=candidate_fp,
    )
    assert proposal.bound["ledger_digest"] == chain["ledger_digest"], \
        "proposal/record ledger-digest join broken"
    assert (proposal.editorial["record_chain"]["candidate_fingerprint"]
            == chain["candidate_fingerprint"])
    precord = proposal_to_record(proposal)
    precord["freshness_check"] = check_proposal_fresh(
        proposal, chapter_text=chapter_text)
    assert precord["freshness_check"]["fresh"] is True, \
        precord["freshness_check"]
    (out / "proposal.json").write_text(
        json.dumps(precord, indent=1, default=str) + "\n", encoding="utf-8")

    # --- Approval decision (author-side record, Fix F annotations). ---
    ledger_entries = ledger.get("entries", [])
    dispatches = [
        {"cost_usd": e.get("cost_usd"), "model": e.get("model"),
         "provider": e.get("provider"), "role": e.get("role"),
         "route": e.get("route"),
         "writer_execution_id": e.get("writer_execution_id")}
        for e in ledger_entries if isinstance(e, dict)]
    objections = []
    for i, rnd in enumerate(program.get("review_rounds", [])):
        if (rnd.get("verdict") or "") in ("accept",):
            continue
        typed = (rnd.get("dispatch") or {}).get("typed") or {}
        objections.append({
            "round": i + 1,
            "verdict": rnd.get("verdict"),
            "validation": rnd.get("validation_reasons", []),
            "review_excerpt_range": rnd.get("review_excerpt_range"),
            "rationale": typed.get("rationale", "")[:1200],
            "failed_checks": typed.get("failed_checks", []),
        })
    total_cost = ledger.get("total_cost_usd", 0.0) or 0.0
    decision = {
        "decision_id": "pub07-ch02-decision-02",
        "decision": "pending_author_decision",
        "action": "none",
        "approval": {
            "status": "pending_author_decision",
            "approved_by": None,
            "note": ("Candidate-generation autonomy exercised; "
                     "publication-acceptance autonomy NOT exercised. No "
                     "auto-approval, no auto-apply (D-PUB-71)."),
        },
        "supersedes": {
            "prior_decision": ("pub07/ch02-superseded-run1/"
                               "approval-decision.json "
                               "(decision pub07-ch02-decision-01)"),
            "prior_program": "pub07/ch02-superseded-run1/program.json",
            "why": ("Run-1 review excerpts were sliced by the ORIGINAL "
                    "span end (Fix A): round 1 leaked 2 trailing source "
                    "lines, round 2 leaked 8 lines including the source's "
                    "own LLM2Jev paragraph. The run-1 LLM2Jev objection "
                    "was therefore raised against LEAKED SOURCE BYTES, "
                    "not the revision; and the final-round "
                    "quote_not_in_either_passage failure on 'a "
                    "resemblance, not a demonstrated equivalence' was "
                    "spurious (the sentence exists only in the corrected "
                    "text; validation consumed stale whole-chapter bytes, "
                    "Fix B). Both narratives are superseded by this "
                    "re-run's fixed-window review; originals stay visible "
                    "in the archive, never edited."),
            "ledger_213_correction": ("Run-1 rationales miscited the "
                                      "read status ('section 4 read', "
                                      "'section 3.4'). Ledger 2.13 is: "
                                      "abstract + section 1 + section 3.3 "
                                      "PARTIAL read; section 4 NOT read "
                                      "(verified against "
                                      "evidence/ledger.md 2026-11-25). The "
                                      "plan's frozen obligation text keeps "
                                      "its own spelling; this record "
                                      "corrects it without editing the "
                                      "frozen plan."),
            "spend_note": ("4 pre-re-run BLOCKED $0 attempts "
                           "(authentication_failed for opencode-go, "
                           "non-retryable, pre-inference) are NOT "
                           "publication spend; 2 are recorded in "
                           "C:/Temp probe ledgers (cleaned per boundary) "
                           "and all are disclosed in the fix-batch "
                           "report, so no dispatch is unrecorded."),
        },
        "candidate_provenance": {
            "assembly": ("in-memory splice of validated dispatch output "
                         "into byte-copied chapter lines; per-line origin "
                         "lineage in program.json; paragraph breaks "
                         "realised in the bytes (Fix E)"),
            "deterministic_checks": (
                f"verify_candidate {verification.get('checks_passed')}/"
                f"{(verification.get('checks_passed') or 0) + (verification.get('checks_failed') or 0)} "
                f"pass (byte-true, no-change, honesty, cruft/complexity "
                f"deltas informative)"),
            "dispatches": dispatches,
            "editorial_model": "opencode-go/deepseek-v4.1-flash "
                               "(default_deepseek_go, subscription)",
            "review_model": "opencode-go/claude-haiku-5-5 "
                            "(default_haiku_go, independent family)",
            "total_cost_usd": total_cost,
            "total_tokens": ledger.get("total_tokens"),
            "evidence_labels": ("candidate MODEL_JUDGEMENT; review "
                                "INDEPENDENT_REVIEW (disclosed identity, "
                                "separate family); deterministic checks "
                                "MEASURED_TEXT"),
        },
        "correction_loop": {
            "attempts_used": (
                f"editorial {sum(1 for e in ledger_entries if e.get('role') == 'editorial')} "
                f"+ review {sum(1 for e in ledger_entries if e.get('role') == 'verification')} "
                f"= {ledger.get('dispatch_count')} total"),
            "outcome": outcome,
            "spend_policy": program.get("spend_policy"),
        },
        "review_outcome": {
            "final": outcome,
            "rounds": [
                {"validation": r.get("validation_reasons", []),
                 "verdict": r.get("verdict"),
                 "excerpt": r.get("review_excerpt_range")}
                for r in program.get("review_rounds", [])],
        },
        "open_objections": objections,
        "options_for_author": [
            "A) Accept the candidate region pending full-chapter author read.",
            "B) Adjudicate any remaining review point first, then decide.",
            "C) Decline the package; keep source bytes (KEEP) and record "
            "the rationale.",
        ],
        "recommendation": ("Do NOT treat deterministic checks as meaning "
                           "preservation (D-PUB-70/74). Decide on the "
                           "re-run's fixed-window review, not the "
                           "superseded run-1 narrative."),
        "artifacts": {
            "candidate": {
                "path": "pub07/ch02/candidate.md",
                "bytes": len(candidate_raw),
                "fingerprint": candidate_fp,
            },
            "program": (f"pub07/ch02/program.json "
                        f"(outcome {outcome})"),
            "proposal": {
                "id": "pub07-ch02-p001",
                "path": "pub07/ch02/proposal.json",
                "status": "pending",
                "fresh": True,
            },
            "staged": "pub07/ch02/staged.json (design_only, fixture_only)",
            "transformation_record": (
                "pub07/ch02/transformation-record.json "
                "(writer.transform.record.v1 + dispatch_ledger + "
                "chain.ledger_digest)"),
            "verification": (
                f"pub07/ch02/verification.json "
                f"({verification.get('checks_passed')}/"
                f"{(verification.get('checks_passed') or 0) + (verification.get('checks_failed') or 0)} pass)"),
        },
        "safety": [
            "No unsupervised authoritative mutation: Jev tree read-only "
            "in this script (chapter bytes hashed, never written).",
            "No automatic publication approval: status stays "
            "pending_author_decision.",
            "Workbench accept/undo never invoked; proposal "
            "pub07-ch02-p001 stays pending.",
        ],
        "recorded_at": "2026-11-25T00:00:00Z",
    }
    (out / "approval-decision.json").write_text(
        json.dumps(decision, indent=1, default=str) + "\n", encoding="utf-8")

    # --- Program annotation (labeled author-side, not dispatch output). ---
    annotated = copy.deepcopy(program)
    annotated["fix_batch_annotations"] = {
        "added_by": ("PUB-07 fix batch, author-side annotation "
                     "(not model dispatch output; D-PUB-81 Fix F)"),
        "supersedes_program": "pub07/ch02-superseded-run1/program.json",
        "review_windows": [
            {"round": i + 1, "verdict": r.get("verdict"),
             "excerpt_range": r.get("review_excerpt_range"),
             "excerpt_sha256": r.get("review_excerpt_sha256"),
             "validation": r.get("validation_reasons", [])}
            for i, r in enumerate(program.get("review_rounds", []))],
        "canonical_forms": ("after-fp LF+1newline; replacement LF-joined "
                            "no trailing newline; intent paths slash-"
                            "normalised; ledger digest strips latency_ms"),
    }
    (out / "program.json").write_text(
        json.dumps(annotated, indent=1, default=str) + "\n", encoding="utf-8")

    # --- Fixture proof with the real applier (disposable temp copy). ---
    import shutil
    tmp = Path(tempfile.mkdtemp(prefix="pub07fixture"))
    try:
        work = tmp / "02-chapter.md"
        shutil.copyfile(chapter_md, str(work))
        # Work in LF-land: the applier matches text, while the book file
        # on disk holds CRLF bytes. All comparisons below are
        # LF-normalised, and the candidate is canonical LF.
        work.write_bytes(_lf_bytes(work.read_bytes()))
        chapter_lf = _lf_bytes(chapter_raw).decode("utf-8")
        current = "\n".join(source_lines)
        recommended = "\n".join(region)
        edits = ("**Current Text:**\n```\n" + current
                 + "\n```\n\n**Recommended Change:**\n```\n" + recommended
                 + "\n```\n")
        edits_file = tmp / "edits.md"
        edits_file.write_text(edits, encoding="utf-8")
        applier = (r"C:\books\jev\scripts\apply_edits.py")
        diff = subprocess.run(
            [sys.executable, applier, "--edits", str(edits_file),
             "--chapter", str(work), "--diff"],
            capture_output=True, text=True, timeout=120)
        print("--- applier --diff (tail) ---")
        print((diff.stdout + diff.stderr)[-1500:])
        if diff.returncode != 0:
            print("REFUSING: fixture --diff did not accept the edit.")
            return 1
        applied = subprocess.run(
            [sys.executable, applier, "--edits", str(edits_file),
             "--chapter", str(work), "--apply", "--no-backup"],
            capture_output=True, text=True, timeout=120)
        print("--- applier --apply (tail) ---")
        print((applied.stdout + applied.stderr)[-1500:])
        if applied.returncode != 0:
            print("REFUSING: fixture --apply failed.")
            return 1
        got = _lf_bytes(work.read_bytes())
        assert got == _lf_bytes(candidate_raw), \
            "fixture apply bytes != candidate bytes"
        print(f"fixture proof: applied bytes == candidate bytes "
              f"({len(got)} bytes, fp {candidate_fp[:12]}...)")
        reverse = tmp / "edits-reverse.md"
        reverse.write_text(
            "**Current Text:**\n```\n" + recommended
            + "\n```\n\n**Recommended Change:**\n```\n" + current
            + "\n```\n", encoding="utf-8")
        back = subprocess.run(
            [sys.executable, applier, "--edits", str(reverse),
             "--chapter", str(work), "--apply", "--no-backup"],
            capture_output=True, text=True, timeout=120)
        if back.returncode != 0:
            print("REFUSING: fixture reverse-apply failed.")
            return 1
        assert _lf_bytes(work.read_bytes()) == _lf_bytes(chapter_raw), \
            "pristine restore mismatch"
        print("fixture proof: pristine-restore byte-identical")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: proposal + approval-decision + program annotation written; "
          "all joins verified.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: build_ch02_records.py <out_dir> <book_chapter_md>")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
