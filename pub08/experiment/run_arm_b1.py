"""PUB-08 batch 5a — Arm B1 live runner (coordinator-executed, $0 here).

Executes Arm B1 (design Sec. 2.3 steps 4-7 + Sec. 5 prerequisites):
five hull packages (hulls 101-122, 237-317, 405-420, 392-396, 509-518),
each one editorial (paid, ``default_deepseek_go``) + one review ($0,
``default_haiku_go``) + at most two review-driven editorial corrections;
then a deterministic bottom-up merge onto O via the batch-4 hull/merge
module.

THIS FILE PERFORMS LIVE DISPATCHES WHEN RUN AS ``__main__``. It is
written (not executed) in batch 5a and executed later by the coordinator
in a credential-bearing shell. Importing it is side-effect free: all
live wiring (``writer_runtime``, ``writer_cli``) is lazy inside
``main()``. The batch-5a fake-gate
(``tests/core/test_pub08_arm_b1_gate.py``) imports only the pure helpers
(``run_b1_package``, ``aggregate_check``, ``build_merged_candidate``,
frozen comparators) with fake dispatch callables: zero live calls.

Production seam (identical shape to the ``transform automate`` live
path): ``run_typed_task`` through
``publication_automation.dispatch_task`` via a ``_dispatch`` closure
with ``domain="publication"``, ``operation_id=<package_id>``,
``stage_id="pub08-b1"``. One shot per attempt: a failed dispatch
(malformed/truncated/transport) is a recorded failure, never retried.
An invalid review verdict halts the package, recorded, never redriven.

Hard stops (design Sec. 5), all fail-closed with exact position:
  1. aggregate + projection > $1.00 (prior actuals + completed B1
     actuals + $0.050 worst-case projection, via the batch-1 spend
     wrapper ``publication_spend.check_aggregate_spend_guard``);
  2. arm > 2x band (cumulative B1 actuals > $0.100 = 2 x $0.050 top);
  3. any frozen-hash change (module bytes, O/H/catalogue bytes,
     obligations SHA per package, editorial prompt SHA where the
     dry-run froze one);
  4. two consecutive package failures (dispatch failures count:
     ``any paid dispatch failing twice`` needs no retry to trip it).

Per-package records go to ``pub08/experiment/arm_b1/<slug>/``:
``program.json``, ``verification.json``, ``ledger.json``,
``region.json``, ``prompt_shas.json``. Final merge writes
``pub08/experiment/arm_b1/candidate.md`` (LF + single trailing
newline) + ``merge-record.json`` (per-package fingerprints, lineage,
ledger actuals summed, prompt SHAs re-compared to dry-run.json).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from writer_core.analysis import publication_automation as auto
from writer_core.analysis import publication_hull_merge as hm
from writer_core.analysis import publication_spend as spend

RUNNER_ID = "pub08/experiment/run_arm_b1.py"
BATCH = "pub08-arm-b1-v0.1"

PROGRAMME_CAP_USD = 1.00
#: Worst-case per-package projection: B band-top $0.050 (design Sec. 4).
WORST_CASE_PROJECTION_USD = 0.050
BAND_TOP_USD = 0.050
BAND_2X_USD = 0.100
MAX_CORRECTIONS_PER_PACKAGE = 2
MAX_CONSECUTIVE_FAILURES = 2

HERE = Path(__file__).resolve().parent
EXP = HERE
ARM_B1_DIR = EXP / "arm_b1"
DRY_RUN_JSON = ARM_B1_DIR / "dry-run.json"
FREEZE_JSON = EXP / "freeze.json"

#: Execution order per the batch brief (merge itself sorts bottom-up,
#: so order only matters for spend/consecutive-failure accounting).
PACKAGE_ORDER: list[dict[str, Any]] = [
    {"package_id": "passage:Path 1: the predicate",
     "hull": {"start_line": 101, "end_line": 122}},
    {"package_id": "passage:Paths 2 and 3: generate, then parse",
     "hull": {"start_line": 237, "end_line": 317}},
    {"package_id": "passage:What we measured, and what we did not",
     "hull": {"start_line": 405, "end_line": 420}},
    {"package_id": "passage:Four words we keep apart",
     "hull": {"start_line": 392, "end_line": 396}},
    {"package_id": "passage:Where this leaves the argument",
     "hull": {"start_line": 509, "end_line": 518}},
]


# ---------------------------------------------------------------------------
# Pure SHAs (same digest forms as the batch-4 dry run)
# ---------------------------------------------------------------------------


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True,
                                  separators=(",", ":")))


def obligations_sha(obligations: list[dict[str, Any]] | None) -> str:
    return sha256_json(list(obligations or []))


def slug_for(package_id: str) -> str:
    return (package_id.replace("passage:", "passage_")
            .replace(":", "_").replace(" ", "_"))


# ---------------------------------------------------------------------------
# Aggregate spend wrapper (batch-1 library; cap $1.00)
# ---------------------------------------------------------------------------


def aggregate_check(prior_ledgers: list[Any],
                    completed_ledgers: list[Any] | None = None,
                    projected_cost_usd: float = WORST_CASE_PROJECTION_USD,
                    cap_usd: float = PROGRAMME_CAP_USD) -> dict[str, Any]:
    """Programme-level pre-dispatch gate: aggregate actuals + projection.

    ``prior_ledgers`` are programme priors (e.g. Arm A1 actuals);
    ``completed_ledgers`` are B1 packages already dispatched this run.
    Returns the wrapper verdict dict (``allowed`` False means DO NOT
    dispatch, with the exact position recorded).
    """
    priors = list(prior_ledgers or []) + list(completed_ledgers or [])
    return spend.check_aggregate_spend_guard(
        priors, projected_cost_usd=projected_cost_usd, cap_usd=cap_usd)


def ledger_actuals(ledger: dict[str, Any] | None) -> float:
    try:
        return float((ledger or {}).get("total_cost_usd") or 0.0)
    except (TypeError, ValueError):
        return float("nan")


# ---------------------------------------------------------------------------
# Frozen-hash comparators (dry-run.json is the freeze for SHAs)
# ---------------------------------------------------------------------------


def frozen_row_for(dry_run: dict[str, Any],
                   package_id: str) -> dict[str, Any] | None:
    pkgs = ((dry_run or {}).get("automate_dry_run") or {}).get("packages")
    if isinstance(pkgs, dict):
        row = pkgs.get(package_id)
        if isinstance(row, dict):
            return row
    return None


def check_frozen_shas(package_id: str,
                      live_obligations_sha: str,
                      live_prompt_sha: str,
                      frozen_row: dict[str, Any] | None) -> list[str]:
    """Compare live SHAs against the dry-run freeze; return drift reasons.

    Obligations SHA must always match (frozen for all 5 packages).
    Editorial prompt SHA must match wherever the dry run froze one
    (the two single-span packages whose hull == span); hull-expanded
    packages carry no frozen prompt (production refused before preparing
    one) and record theirs as new.
    """
    drift: list[str] = []
    if not isinstance(frozen_row, dict):
        return [f"no frozen dry-run row for {package_id!r}"]
    want_obl = frozen_row.get("obligations_sha256")
    if live_obligations_sha != want_obl:
        drift.append(f"obligations_sha drift for {package_id!r}: "
                     f"live {live_obligations_sha[:12]} vs frozen "
                     f"{str(want_obl)[:12]}")
    want_prompt = frozen_row.get("prompt_sha256")
    if want_prompt is not None and live_prompt_sha != want_prompt:
        drift.append(f"prompt_sha drift for {package_id!r}: "
                     f"live {live_prompt_sha[:12]} vs frozen "
                     f"{str(want_prompt)[:12]}")
    return drift


# ---------------------------------------------------------------------------
# Review excerpt (replacement region only; mirrors Fix A lineage scoping)
# ---------------------------------------------------------------------------


def review_excerpt(final_lines: list[str],
                   final_lineage: list[dict[str, Any]],
                   hull: dict[str, int]) -> tuple[list[str], dict[str, int]]:
    disp = [int(e.get("line", 0)) for e in (final_lineage or [])
            if isinstance(e, dict) and e.get("origin") == "dispatch"]
    if disp:
        start, end = min(disp), max(disp)
    else:
        start = int(hull.get("start_line", 1))
        end = int(hull.get("end_line", start))
    start = max(1, start)
    end = min(len(final_lines), max(start, end))
    return final_lines[start - 1:end], {"start_line": start,
                                        "end_line": end}


# ---------------------------------------------------------------------------
# Per-package B1 program (fake-injectable; one shot per attempt)
# ---------------------------------------------------------------------------


def run_b1_package(
        *,
        dispatch_fn: Callable[..., Any],
        package: dict[str, Any],
        hull_span: dict[str, int],
        passage_lines: list[str],
        chapter_lines: list[str],
        directions: str = "",
        obligations: list[dict[str, Any]] | None = None,
        verify_fn: Callable[[list[str]], dict[str, Any]],
        frozen_row: dict[str, Any] | None = None,
        max_corrections: int = MAX_CORRECTIONS_PER_PACKAGE,
        pre_dispatch_guard: Callable[[], Optional[str]] | None = None,
        out_dir: Path | str | None = None,
        resume_program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one hull package: editorial + review + <=2 bounded fixes.

    Every dispatch goes through the injected ``dispatch_fn`` exactly
    once per attempt (the production ``_dispatch`` closure in live runs,
    a fake in tests). Dispatch failures (malformed/truncated/transport),
    assembly failures and spend-guard halts are terminal for the
    package: recorded, never redriven. Validation failures and verify
    failures consume ONE failure-driven correction within the shared
    ``max_corrections`` budget (production parity: the production
    program spends corrections on verify failures, not only on review
    ``request_changes``); only ``request_changes`` consumes further
    review-driven corrections. The final re-review verdict stands as
    recorded. ``resume_program`` continues a halted package record
    (same package/hull/passage/obligations SHAs verified first) with
    its remaining budget instead of redispatching attempt 1.

    ``pre_dispatch_guard`` returns a halt reason (or None); it is
    consulted before EVERY dispatch (Fix C posture).
    """
    package_id = str(package.get("package_id", "?"))
    op_ids = list(package.get("op_refs") or [])
    passage_text = "\n".join(passage_lines)
    obl = list(obligations or [])
    obl_sha = obligations_sha(obl)
    passage_sha = sha256_text(passage_text)

    program: dict[str, Any] = {
        "program_schema": "writer.automation.b1_program.v1",
        "batch": BATCH,
        "package_id": package_id,
        "hull_span": dict(hull_span),
        "passage_sha256": passage_sha,
        "obligations_sha256": obl_sha,
        "iterations": [],
        "review_rounds": [],
        "corrections": 0,
        "outcome": "not_run",
        "ledger": None,
    }
    ledger_rows: list[dict[str, Any]] = []
    attempt_no = {"editorial": 0, "verification": 0}

    if resume_program is not None:
        # Continue a halted record instead of redispatching attempt 1.
        # Identity first: package, hull, passage and obligations must be
        # byte-identical to the recorded run, and budget must remain.
        rp = resume_program
        if (rp.get("package_id") != package_id
                or rp.get("hull_span") != dict(hull_span)
                or rp.get("passage_sha256") != passage_sha
                or rp.get("obligations_sha256") != obl_sha):
            return {"package_id": package_id, "outcome": "resume_mismatch",
                    "resumed": False,
                    "detail": "record identity != live inputs; refused "
                              "without dispatch"}
        if rp.get("outcome") not in ("editorial_invalid", "verify_failed"):
            return {"package_id": package_id, "outcome": "resume_rejected",
                    "resumed": False,
                    "detail": f"only validation/verify failures resume; "
                              f"record outcome is {rp.get('outcome')}"}
        if (rp.get("corrections") or 0) >= max_corrections:
            return {"package_id": package_id,
                    "outcome": "resume_budget_exhausted", "resumed": False,
                    "detail": "no correction budget remains"}
        program = rp
        program["resumed"] = True
        program["resume_segment"] = (
            "failure-driven correction under coordinator amendment "
            "2026-11-25 (production parity: production spends "
            "corrections on validation/verify failures)")
        program["superseded_outcome"] = rp.get("outcome")
        for entry in ((program.get("ledger") or {}).get("entries") or []):
            ledger_rows.append(entry)
            role = entry.get("role")
            try:
                attempt_no[role] = max(attempt_no.get(role, 0),
                                       int(entry.get("attempt") or 0))
            except (TypeError, ValueError):
                pass

    def _guarded(kind: str) -> Optional[str]:
        if pre_dispatch_guard is None:
            return None
        try:
            return pre_dispatch_guard()
        except Exception as exc:
            return f"{kind} guard error: {exc}"

    def _dispatch_once(payload: dict[str, Any], dto: Any,
                       role: str) -> dict[str, Any]:
        halt = _guarded(role)
        if halt:
            return {"halted": True, "halt_reason": halt}
        record = auto.dispatch_task(dispatch_fn, payload, dto, role=role)
        attempt_no[role] = attempt_no.get(role, 0) + 1
        try:
            ledger_rows.append(auto.ledger_entry(
                {**record, "attempt": attempt_no[role]}, role=role))
        except Exception:
            ledger_rows.append({"role": role, "status": "ledger_failed"})
        return {"halted": False, "record": record}

    def _finish(outcome: str) -> dict[str, Any]:
        program["outcome"] = outcome
        program["ledger"] = auto.build_dispatch_ledger(ledger_rows)
        if out_dir is not None:
            _write_package_records(Path(out_dir), program)
        return program

    # ---- frozen-hash gate (zero dispatches on drift) ----
    payload1 = auto.prepare_editorial_task(
        package, passage_lines, directions=directions,
        obligations=obl, attempt=1)
    # Determinism pin: preparing twice must give the same prompt.
    payload1_b = auto.prepare_editorial_task(
        package, passage_lines, directions=directions,
        obligations=obl, attempt=1)
    if payload1["prompt"] != payload1_b["prompt"]:
        program["frozen_drift"] = ["editorial prompt non-deterministic"]
        return _finish("halted_prompt_drift")
    prompt_sha = sha256_text(payload1["prompt"])
    program["prompt_sha256"] = prompt_sha
    if frozen_row is not None:
        drift = check_frozen_shas(package_id, obl_sha, prompt_sha,
                                  frozen_row)
        if drift:
            program["frozen_drift"] = drift
            return _finish("halted_prompt_drift")

    def _editorial_round(*, attempt: int,
                         prior_failure: Optional[str]) -> dict[str, Any]:
        payload = auto.prepare_editorial_task(
            package, passage_lines, directions=directions,
            obligations=obl, attempt=attempt,
            prior_failure=prior_failure)
        if attempt == 1:
            assert payload["prompt"] == payload1["prompt"]
        else:
            program.setdefault("correction_prompt_shas", []).append(
                sha256_text(payload["prompt"]))
        got = _dispatch_once(
            payload, auto.EditorialCandidateResponse, "editorial")
        if got["halted"]:
            return {"ok": False, "terminal": "halted_spend_guard",
                    "halt_reason": got["halt_reason"], "attempt": attempt}
        record = got["record"]
        iteration: dict[str, Any] = {"attempt": attempt,
                                     "dispatch": record}
        program["iterations"].append(iteration)
        if not record.get("succeeded"):
            iteration["outcome"] = "dispatch_failed"
            return {"ok": False, "terminal": "editorial_dispatch_failed",
                    "attempt": attempt}
        reasons = auto.validate_editorial_output(
            record.get("typed"), op_ids, passage_text)
        iteration["validation_reasons"] = reasons
        if reasons:
            iteration["outcome"] = "invalid_typed_output"
            return {"ok": False, "terminal": "editorial_invalid",
                    "attempt": attempt}
        try:
            cand_lines, lineage = auto.assemble_candidate(
                chapter_lines, hull_span,
                record["typed"]["replacement_lines"],
                dispatch_ref=f"b1:{package_id}", paragraph_breaks=True)
        except Exception as exc:
            iteration["outcome"] = "assembly_failed"
            iteration["assembly_error"] = str(exc)
            return {"ok": False, "terminal": "assembly_failed",
                    "attempt": attempt}
        iteration["assembled_lines"] = len(cand_lines)
        report = verify_fn(cand_lines)
        iteration["verify_verdict"] = report.get("verdict")
        iteration["verify_failed"] = report.get("checks_failed")
        failed_checks = [c for c in (report.get("checks") or [])
                         if not c.get("passed", True)]
        iteration["verify_failed_checks"] = [
            f"{c.get('check')}:"
            f"{((c.get('span') or {}).get('start_line'))}-"
            f"{((c.get('span') or {}).get('end_line'))}:"
            f"{str(c.get('detail', ''))[:200]}"
            for c in failed_checks][:8]
        if report.get("verdict") != "pass":
            iteration["outcome"] = "verify_failed"
            return {"ok": False, "terminal": "verify_failed",
                    "attempt": attempt}
        iteration["outcome"] = "verified_pass"
        # Re-stamp the dispatch ref already carried by assemble; bind
        # the row to the verified bytes (Fix D posture).
        for entry in lineage:
            if entry.get("origin") == "dispatch":
                entry["dispatch_ref"] = (
                    f"b1:{package_id}#attempt{attempt}")
        return {"ok": True, "lines": cand_lines, "lineage": lineage,
                "attempt": attempt}

    def _failure_text(term: str, iteration: dict[str, Any]) -> str:
        """Exact failure feedback for a failure-driven correction."""
        if term == "editorial_invalid":
            reasons = iteration.get("validation_reasons") or []
            return ("editorial validation failed: "
                    + "; ".join(str(r) for r in reasons))[:800]
        checks = iteration.get("verify_failed_checks") or []
        return ("verification failed: " + "; ".join(checks))[:800]

    def _synthetic_failure_review(term: str,
                                  iteration: dict[str, Any]
                                  ) -> dict[str, Any]:
        return {"verdict": "request_changes",
                "driven_by": ("validation" if term == "editorial_invalid"
                              else "verify"),
                "synthetic_failure_review": True,
                "prior_failure": _failure_text(term, iteration)}

    def _review_round(lines: list[str],
                      lineage: list[dict[str, Any]]) -> dict[str, Any]:
        excerpt, excerpt_range = review_excerpt(lines, lineage, hull_span)
        excerpt_text = "\n".join(excerpt)
        payload = auto.prepare_review_task(
            package_id, op_ids, passage_lines, excerpt,
            obligations=obl)
        program.setdefault("review_prompt_shas", []).append(
            sha256_text(payload["prompt"]))
        got = _dispatch_once(
            payload, auto.EditorialReviewResponse, "verification")
        if got["halted"]:
            return {"verdict": "halted_spend_guard",
                    "halt_reason": got["halt_reason"],
                    "review_excerpt_range": excerpt_range,
                    "review_excerpt_sha256": sha256_text(excerpt_text)}
        record = got["record"]
        if not record.get("succeeded"):
            return {"dispatch": record, "validation_reasons": [],
                    "verdict": "review_dispatch_failed",
                    "review_excerpt_range": excerpt_range,
                    "review_excerpt_sha256": sha256_text(excerpt_text)}
        reasons = auto.validate_review_output(
            record.get("typed"), passage_text, excerpt_text)
        if reasons:
            return {"dispatch": record,
                    "validation_reasons": reasons, "verdict": "invalid",
                    "review_excerpt_range": excerpt_range,
                    "review_excerpt_sha256": sha256_text(excerpt_text)}
        return {"dispatch": record, "validation_reasons": [],
                "verdict": (record.get("typed") or {}).get("verdict"),
                "review_excerpt_range": excerpt_range,
                "review_excerpt_sha256": sha256_text(excerpt_text)}

    if resume_program is not None:
        # Continued record: the last iteration already failed terminally.
        # Recompute its exact failure text live (deterministic; no stale
        # trust) and enter the shared correction loop below.
        last = program["iterations"][-1]
        term = program.get("superseded_outcome")
        if term == "editorial_invalid":
            reasons = auto.validate_editorial_output(
                (last.get("dispatch") or {}).get("typed"), op_ids,
                passage_text)
            last["validation_reasons"] = reasons
        elif term == "verify_failed":
            asm = auto.assemble_candidate(
                chapter_lines, hull_span,
                ((last.get("dispatch") or {}).get("typed") or {})
                .get("replacement_lines", []),
                dispatch_ref=f"b1:{package_id}#resume-reverify",
                paragraph_breaks=True)
            rep = verify_fn(list(asm[0]))
            failed = [c for c in (rep.get("checks") or [])
                      if not c.get("passed", True)]
            last["verify_verdict"] = rep.get("verdict")
            last["verify_failed"] = rep.get("checks_failed")
            last["verify_failed_checks"] = [
                f"{c.get('check')}:"
                f"{((c.get('span') or {}).get('start_line'))}-"
                f"{((c.get('span') or {}).get('end_line'))}:"
                f"{str(c.get('detail', ''))[:200]}"
                for c in failed][:8]
        review = _synthetic_failure_review(term, last)
        program["corrections"] = program.get("corrections", 0)
    else:
        first = _editorial_round(attempt=1, prior_failure=None)
        if not first.get("ok"):
            term = first.get("terminal")
            if term not in ("editorial_invalid", "verify_failed"):
                return _finish(term)
            # Production parity (coordinator amendment 2026-11-25): the
            # production program spends corrections on validation/verify
            # failures, not only on review request_changes.
            review = _synthetic_failure_review(
                term, program["iterations"][-1])
        else:
            state_lines: list[str] = first["lines"]
            state_lineage: list[dict[str, Any]] = first["lineage"]
            program["final_lines"] = state_lines
            program["final_lineage"] = state_lineage

            review = _review_round(state_lines, state_lineage)
            program["review_rounds"].append(review)
            if review["verdict"] in ("halted_spend_guard",
                                     "review_dispatch_failed", "invalid"):
                terminal = {"halted_spend_guard": "halted_spend_guard",
                            "review_dispatch_failed": "review_dispatch_failed",
                            "invalid": "review_invalid"}[review["verdict"]]
                return _finish(terminal)
            if review["verdict"] != "request_changes":
                # "accept" succeeds; "abstain" (or anything else) is
                # terminal and recorded as-is, never redriven.
                program["region"] = _region_body(
                    package_id, hull_span, state_lines, state_lineage)
                return _finish("review_accepted"
                               if review["verdict"] == "accept"
                               else f"review_{review['verdict']}")

    corrections = program.get("corrections", 0)
    while (review["verdict"] == "request_changes"
           and corrections < max_corrections):
        corrections += 1
        program["corrections"] = corrections
        if review.get("synthetic_failure_review"):
            prior = str(review.get("prior_failure", ""))[:800]
            driven = review.get("driven_by", "validation")
        else:
            prior = ("reviewer requested changes: "
                     + str(((review.get("dispatch") or {}).get("typed")
                            or {}).get("rationale", ""))[:500])
            driven = "review"
        nxt = _editorial_round(attempt=len(program["iterations"]) + 1,
                               prior_failure=prior)
        program.setdefault("review_corrections", []).append(
            {"attempt": nxt.get("attempt"), "driven_by": driven,
             "outcome": ("verified_pass" if nxt.get("ok")
                         else nxt.get("terminal"))})
        if not nxt.get("ok"):
            return _finish(nxt["terminal"])
        state_lines = nxt["lines"]
        state_lineage = nxt["lineage"]
        program["final_lines"] = state_lines
        program["final_lineage"] = state_lineage
        review = _review_round(state_lines, state_lineage)
        program["review_rounds"].append(review)
        if review["verdict"] in ("halted_spend_guard",
                                 "review_dispatch_failed", "invalid"):
            terminal = {"halted_spend_guard": "halted_spend_guard",
                        "review_dispatch_failed":
                            "review_dispatch_failed",
                        "invalid": "review_invalid"}[review["verdict"]]
            return _finish(terminal)
        if review["verdict"] != "request_changes":
            break
    # The final re-review verdict stands as recorded (no further round).
    if review["verdict"] == "accept":
        program["region"] = _region_body(package_id, hull_span,
                                         state_lines, state_lineage)
        return _finish("review_accepted")
    return _finish(f"review_{review['verdict']}")


def _region_body(package_id: str, hull: dict[str, int],
                 lines: list[str],
                 lineage: list[dict[str, Any]]) -> dict[str, Any]:
    """Dispatch-region body (with paragraph-break blanks) for merging."""
    body = [ln for ln, meta in zip(lines, lineage)
            if isinstance(meta, dict) and meta.get("origin") == "dispatch"]
    return {"package_id": package_id,
            "span": {"start_line": int(hull["start_line"]),
                     "end_line": int(hull["end_line"])},
            "replacement_lines": body,
            "replacement_sha256": sha256_text("\n".join(body))}


def _write_package_records(out_dir: Path, program: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "program.json").write_text(
        json.dumps(program, indent=1, default=str), encoding="utf-8")
    final = program.get("final_lines") or []
    verify_note = None
    for it in program.get("iterations", []):
        if it.get("verify_verdict") is not None:
            verify_note = {"verdict": it.get("verify_verdict"),
                           "checks_failed": it.get("verify_failed")}
    (out_dir / "verification.json").write_text(
        json.dumps(verify_note or {"verdict": "missing"},
                   indent=1, default=str), encoding="utf-8")
    (out_dir / "ledger.json").write_text(
        json.dumps(program.get("ledger") or {}, indent=1, default=str),
        encoding="utf-8")
    if program.get("region") is not None:
        (out_dir / "region.json").write_text(
            json.dumps(program["region"], indent=1), encoding="utf-8")
    (out_dir / "prompt_shas.json").write_text(
        json.dumps({"prompt_sha256": program.get("prompt_sha256"),
                    "correction_prompt_shas": program.get(
                        "correction_prompt_shas", []),
                    "review_prompt_shas": program.get(
                        "review_prompt_shas", []),
                    "passage_sha256": program.get("passage_sha256"),
                    "obligations_sha256": program.get(
                        "obligations_sha256")}, indent=1),
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Deterministic merge (batch-4 module as library)
# ---------------------------------------------------------------------------


def build_merged_candidate(
        original_lines: list[str],
        package_results: list[dict[str, Any]],
        *,
        expected_base_sha256: str | None = None,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    """Bottom-up merge of successful package regions onto O.

    Only results carrying a ``region`` (review-accepted) contribute;
    failed packages keep O bytes. Overlapping/out-of-range regions are
    refused by the merge module (no silent precedence).
    """
    regions = [r["region"] for r in (package_results or [])
               if isinstance(r, dict) and isinstance(r.get("region"), dict)]
    merged, lineage = hm.merge_region_replacements(
        original_lines, regions,
        expected_base_sha256=expected_base_sha256)
    return merged, lineage, hm.merge_report(merged, lineage)


def consecutive_halt(failures_in_a_row: int) -> bool:
    return failures_in_a_row >= MAX_CONSECUTIVE_FAILURES


def _disk_ledger_sum(base_dir: Path) -> dict[str, Any]:
    """Authoritative B1 actuals: sum every package ledger.json on disk.

    The in-memory ``completed_ledgers`` only covers the current
    ``--resume`` segment; stood-down/failed packages from prior
    segments live only on disk. Guards use the in-memory figure live
    (fail-closed direction would be the disk figure; both are far
    under the cap — recorded, not silently merged).
    """
    total_cost = 0.0
    total_n = 0
    per_package: dict[str, Any] = {}
    for ledger_path in sorted(base_dir.glob("passage_*/ledger.json")):
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = ledger_path.parent.name
        per_package[slug] = {
            "dispatch_count": ledger.get("dispatch_count", 0),
            "total_cost_usd": ledger.get("total_cost_usd", 0.0),
        }
        total_n += int(ledger.get("dispatch_count", 0) or 0)
        try:
            total_cost += float(ledger.get("total_cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            pass
    return {"dispatch_count": total_n,
            "total_cost_usd": total_cost,
            "per_package": per_package}


# ---------------------------------------------------------------------------
# Live entry point (coordinator-executed; NOT run in batch 5a)
# ---------------------------------------------------------------------------


def main() -> int:
    import sys as _sys
    _sys.path.insert(0, r"C:\Projects\writer\packages\writer-core")
    _sys.path.insert(0, r"C:\Projects\writer\packages\writer-cli")
    _sys.path.insert(0, r"C:\Projects\writer\packages\writer-runtime")
    from typer.testing import CliRunner as _Runner
    from writer_cli.main import app as _app
    from writer_runtime import build_runtime as _build_runtime
    from writer_runtime.domains.models.typed_task import (
        run_typed_task as _run_typed_task)
    from writer_core.analysis.publication_transformation import (
        build_preservation_context as _build_pres,
        canonical_candidate_bytes as _canon_bytes,
        compile_work_packages as _compile_pkgs,
        revalidate_at_boundary as _reval,
        verify_candidate as _verify,
    )

    failures: list[str] = []
    run = _Runner()
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    dry_run = json.loads(DRY_RUN_JSON.read_text(encoding="utf-8"))
    JEV = Path(r"C:\books\jev")
    O_PATH = JEV / "content" / "books" / "jev" / "01-chapter.md"
    PUB06 = HERE.parents[1] / "pub06" / "ch01"

    def _halt(msg: str) -> int:
        failures.append(msg)
        print(f"HALT: {msg}", file=_sys.stderr)
        (ARM_B1_DIR / "run-record.json").write_text(
            json.dumps({"runner": RUNNER_ID, "verdict": "HALT",
                        "failures": failures}, indent=1),
            encoding="utf-8")
        return 3

    # ---- frozen module/hash reconfirmation (hard stop 3) ----
    o_raw = O_PATH.read_bytes()
    o_sha = hashlib.sha256(o_raw).hexdigest()
    if o_sha != freeze["frozen_inputs"]["O"]["raw_sha256"]:
        return _halt("O bytes changed vs freeze")
    checks: dict[str, bool] = {}
    for name, rel in (
            ("publication_automation",
             "packages/writer-core/writer_core/analysis/publication_automation.py"),
            ("publication_transformation",
             "packages/writer-core/writer_core/analysis/publication_transformation.py"),
            ("publication_pedagogy",
             "packages/writer-core/writer_core/analysis/publication_pedagogy.py"),
            ("publication_cruft",
             "packages/writer-core/writer_core/analysis/publication_cruft.py"),
            ("publication_complexity",
             "packages/writer-core/writer_core/analysis/publication_complexity.py"),
            ("evidence_reconciliation",
             "packages/writer-core/writer_core/analysis/evidence_reconciliation.py"),
            ("transform_cli",
             "packages/writer-cli/writer_cli/commands/transform.py")):
        live = hashlib.sha256(
            (Path(r"C:\Projects\writer") / rel).read_bytes()).hexdigest()
        checks[name] = (
            live == freeze["writer"]["frozen_modules"][name]["sha256"])
    if not all(checks.values()):
        return _halt("frozen module hash change: "
                     f"{[k for k, v in checks.items() if not v]}")

    # ---- programme priors: Arm A1 actuals (fail closed if unreadable) ----
    try:
        a1 = json.loads((EXP / "arm_a_r1" / "dispatch-record.json")
                        .read_text(encoding="utf-8"))
        prior_cost = float((a1.get("provenance") or {}).get("cost_usd"))
    except Exception as exc:
        return _halt(f"priors unreadable (A1 dispatch record): {exc}")
    prior_ledgers = [{"total_cost_usd": prior_cost}]
    print(f"prior actuals: ${prior_cost:.7f} (Arm A1)")

    # ---- live reconcile/check/package (same compile as the dry run) ----
    # Production parity note (coordinator fix 2026-11-25, fail-closed halt
    # diagnosed): the CLI reads chapter text via Path.read_text(), whose
    # universal newlines normalize the CRLF checkout artifact to LF. The
    # runner previously passed binary-decoded text (CRs intact), which
    # the LF-bound plan correctly rejected as stale. Raw bytes are still
    # pinned to freeze above, so no content change can hide behind this.
    o_text = O_PATH.read_text(encoding="utf-8")
    chapter_lines = o_text.splitlines()
    common = ["--book-root", str(JEV),
              "--plan", str(PUB06 / "plan-ch1.json"),
              "--reconcile-states",
              str(PUB06 / "reconcile-states-ch1.json"),
              "--inventory-digest",
              (PUB06 / "inventory-digest-ch1.txt").read_text(
                  encoding="utf-8").strip(),
              "--evidence-rev", "jev@live",
              "--adjudications", str(PUB06 / "adjudications-ch1.json")]
    plan_doc = json.loads((PUB06 / "plan-ch1.json").read_text(
        encoding="utf-8"))["result"]
    states_doc = json.loads((PUB06 / "reconcile-states-ch1.json")
                            .read_text(encoding="utf-8"))
    if isinstance(states_doc, dict) and "result" in states_doc:
        states_doc = states_doc["result"]
    # Adjudications unwrap mirrors the CLI (transform.py: lines 122-123,
    # 192-193): the file envelope carries {"adjudicated_by", ...,
    # "adjudications": [...]}; the boundary takes the list. Passing the
    # envelope yields spurious "adjudication_unbound" isolating notes.
    adj_doc = json.loads((PUB06 / "adjudications-ch1.json").read_text(
        encoding="utf-8"))
    adj_list = (adj_doc.get("adjudications") if isinstance(adj_doc, dict)
                else adj_doc) or None
    boundary = _reval(plan_doc, o_text, evidence_rev="jev@live",
                      inventory_digest=(PUB06 / "inventory-digest-ch1.txt")
                      .read_text(encoding="utf-8").strip(),
                      reconcile_states=states_doc,
                      adjudications=adj_list,
                      book_id="jev", chapter_id="01-chapter")
    if not boundary.get("executable"):
        return _halt("boundary not executable live")
    compiled = _compile_pkgs(
        plan_doc, o_text,
        adjudications=adj_list,
        boundary=boundary, evidence_rev="jev@live",
        inventory_digest=(PUB06 / "inventory-digest-ch1.txt").read_text(
            encoding="utf-8").strip(),
        reconcile_states=states_doc,
        book_id="jev", chapter_id="01-chapter")
    by_id = {p.get("package_id"): p for p in compiled["packages"]
             if isinstance(p, dict)}
    plan_ops = {o.get("id"): o for o in plan_doc.get("operations", [])
                if isinstance(o, dict)}
    preservation = _build_pres(plan_doc, None)
    no_change = [((o.get("target") or {}).get("span") or {})
                 for o in plan_doc.get("operations", [])
                 if isinstance(o, dict) and o.get("type") == "NO_CHANGE"
                 and ((o.get("target") or {}).get("span") or {})
                 .get("start_line")]

    def _verify_live(lines: list[str]) -> dict[str, Any]:
        return _verify("\n".join(lines), o_text, compiled,
                       preservation, no_change_spans=no_change,
                       book_id="jev", chapter_id="01-chapter")

    # ---- production seam (same _dispatch shape as transform automate) ----
    runtime = _build_runtime()
    models = runtime.require("models")

    def _dispatch(*, task: str, prompt: str, dto: Any,
                  metadata: Any = None,
                  context_for_provenance: Any = None) -> Any:
        return _run_typed_task(
            models, task=task, prompt=prompt, dto=dto,
            domain="publication", operation_id="pub08-b1-package",
            stage_id="pub08-b1", metadata=dict(metadata or {}),
            context_for_provenance=context_for_provenance)

    results: list[dict[str, Any]] = []
    completed_ledgers: list[dict[str, Any]] = []
    stood_down: list[dict[str, Any]] = []
    b1_actuals = 0.0
    consec_failures = 0
    resume_mode = "--resume" in (sys.argv[1:])
    if resume_mode:
        # Segment 2 under the amended protocol (coordinator-authorized):
        # the halt rule fired correctly on segment 1; the counter
        # restarts here and every resumed package is re-gated below.
        print("RESUME segment: consecutive-failure counter reset by "
              "coordinator authorization (protocol amendment recorded in "
              "STATE); prior halted records preserved as "
              "program.segment1-halted.json")

    for spec in PACKAGE_ORDER:
        pid = spec["package_id"]
        hull = spec["hull"]
        pkg = by_id.get(pid)
        if pkg is None or pkg.get("blocked"):
            return _halt(f"package missing/blocked live: {pid}")
        prior_path = ARM_B1_DIR / slug_for(pid) / "program.json"
        resume_program = None
        decision_path = ARM_B1_DIR / slug_for(pid) / "DECISION.json"
        if decision_path.exists():
            # Coordinator stand-down: recorded failed, never redriven.
            # Stood-down packages are prior-segment history, not new
            # failures: they skip the run and do not increment the
            # consecutive-failure counter (recorded in merge record).
            try:
                decision = json.loads(decision_path.read_text(
                    encoding="utf-8"))
            except Exception as exc:
                return _halt(f"unreadable DECISION for {pid}: {exc}")
            if (isinstance(decision, dict)
                    and decision.get("decision") == "stand_failed"):
                stood_down.append({"package_id": pid,
                                   "decision": decision})
                print(f"{pid}: stood down by coordinator decision "
                      f"(recorded failed, no redrive)")
                continue
            return _halt(f"unknown DECISION for {pid}: {decision!r}"[:200])
        if prior_path.exists():
            try:
                prior = json.loads(prior_path.read_text(encoding="utf-8"))
            except Exception as exc:
                return _halt(f"unreadable prior record for {pid}: {exc}")
            prior_outcome = prior.get("outcome") if isinstance(
                prior, dict) else None
            if prior_outcome == "review_accepted":
                results.append(prior)
                ledger = prior.get("ledger") or {}
                completed_ledgers.append(ledger)
                actual = ledger_actuals(ledger)
                b1_actuals += actual if actual == actual else 0.0
                print(f"{pid}: review_accepted (prior record kept, "
                      f"no redispatch)")
                consec_failures = 0
                continue
            if (isinstance(prior, dict) and prior_outcome in
                    ("editorial_invalid", "verify_failed") and resume_mode
                    and (prior.get("corrections") or 0)
                    < MAX_CORRECTIONS_PER_PACKAGE):
                seg1 = prior_path.with_name("program.segment1-halted.json")
                if not seg1.exists():
                    seg1.write_text(prior_path.read_text(encoding="utf-8"),
                                    encoding="utf-8")
                resume_program = prior
                print(f"{pid}: resuming {prior_outcome} record with "
                      f"failure-driven correction "
                      f"(halted record kept at {seg1.name})")
            else:
                # Any other terminal outcome (spend halt, dispatch
                # failure, review_invalid, budget-exhausted resume) is
                # recorded as-is and never redriven.
                results.append(prior if isinstance(prior, dict) else {})
                ledger = (prior.get("ledger") or {} if isinstance(
                    prior, dict) else {})
                completed_ledgers.append(ledger)
                actual = ledger_actuals(ledger)
                b1_actuals += actual if actual == actual else 0.0
                print(f"{pid}: prior {prior_outcome} stands "
                      f"(no redrive by rule)")
                consec_failures += 1
                if consecutive_halt(consec_failures):
                    return _halt(f"two consecutive package failures "
                                 f"(last: {pid} -> {prior_outcome})")
                continue
        # Hard stop 1 (cap): manual aggregate check BEFORE any dispatch.
        verdict = aggregate_check(prior_ledgers, completed_ledgers,
                                  WORST_CASE_PROJECTION_USD,
                                  PROGRAMME_CAP_USD)
        if not verdict.get("allowed"):
            return _halt(
                f"aggregate spend guard: priors "
                f"${verdict.get('aggregate_actuals_usd', float('nan')):.6f} "
                f"+ projection ${WORST_CASE_PROJECTION_USD:.3f} exceeds cap "
                f"${PROGRAMME_CAP_USD:.2f} before {pid}: HALT with zero "
                f"new dispatch")
        print(f"aggregate check {pid}: priors "
              f"${verdict['aggregate_actuals_usd']:.6f} + "
              f"${WORST_CASE_PROJECTION_USD:.3f} <= "
              f"${PROGRAMME_CAP_USD:.2f} OK "
              f"(remaining ${verdict.get('remaining_usd', 0.0):.6f})")
        op_ids = list(pkg.get("op_refs") or [])
        directions = "; ".join(
            str((plan_ops.get(oid) or {}).get("rationale", ""))
            for oid in op_ids)
        obligations = list(pkg.get("preservation_obligations") or [])
        live_hull = hm.compile_hull_span(pkg)
        if live_hull != hull:
            return _halt(f"hull drift for {pid}: live {live_hull} vs "
                         f"expected {hull}")
        passage = hm.hull_passage_lines(chapter_lines, live_hull)
        frozen_row = frozen_row_for(dry_run, pid)

        def _guard() -> Optional[str]:
            v = aggregate_check(prior_ledgers, completed_ledgers,
                                WORST_CASE_PROJECTION_USD,
                                PROGRAMME_CAP_USD)
            if not v.get("allowed"):
                return ("aggregate cap would be exceeded "
                        f"(actuals ${v.get('aggregate_actuals_usd'):.6f} + "
                        f"projection ${WORST_CASE_PROJECTION_USD:.3f})")
            return None

        program = run_b1_package(
            dispatch_fn=_dispatch, package=pkg, hull_span=live_hull,
            passage_lines=passage, chapter_lines=chapter_lines,
            directions=directions, obligations=obligations,
            verify_fn=_verify_live, frozen_row=frozen_row,
            max_corrections=MAX_CORRECTIONS_PER_PACKAGE,
            pre_dispatch_guard=_guard,
            out_dir=ARM_B1_DIR / slug_for(pid),
            resume_program=resume_program)
        results.append(program)
        ledger = program.get("ledger") or {}
        completed_ledgers.append(ledger)
        actual = ledger_actuals(ledger)
        b1_actuals += actual if actual == actual else 0.0
        ok = program.get("outcome") == "review_accepted"
        consec_failures = 0 if ok else consec_failures + 1
        print(f"{pid}: {program.get('outcome')} "
              f"(ledger ${actual:.6f}; B1 cumulative ${b1_actuals:.6f}; "
              f"consec_failures={consec_failures})")
        # Hard stop 2 (2x band).
        if b1_actuals > BAND_2X_USD:
            return _halt(f"arm >2x band: B1 cumulative ${b1_actuals:.6f} "
                         f"> ${BAND_2X_USD:.3f}")
        # Hard stop 4 (two consecutive failures).
        if consecutive_halt(consec_failures):
            return _halt(f"two consecutive package failures "
                         f"(last: {pid} -> {program.get('outcome')})")

    # ---- final deterministic merge onto O ----
    expected_base = hashlib.sha256(
        hm.canonical_merge_bytes(chapter_lines)).hexdigest()
    merged, lineage, report = build_merged_candidate(
        chapter_lines, results, expected_base_sha256=expected_base)
    candidate_bytes = hm.canonical_merge_bytes(merged)
    (ARM_B1_DIR / "candidate.md").write_bytes(candidate_bytes)
    # Merge-time prompt-SHA re-comparison (HALT on any drift).
    frozen_prompts = {pid: (frozen_row_for(dry_run, pid) or {}).get(
        "prompt_sha256") for pid in [s["package_id"]
                                     for s in PACKAGE_ORDER]}
    live_prompts = {r.get("package_id"): r.get("prompt_sha256")
                    for r in results}
    drift = {pid: (live_prompts.get(pid), frozen_prompts.get(pid))
             for pid in frozen_prompts
             if frozen_prompts.get(pid) is not None
             and live_prompts.get(pid) != frozen_prompts.get(pid)}
    if drift:
        return _halt(f"merge-time prompt-SHA drift vs dry-run: {drift}")
    merge_record = {
        "runner": RUNNER_ID,
        "batch": BATCH,
        "merge_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "n_lines": len(merged),
        "canonical_form": "LF + single trailing newline",
        "accounting_note": ("b1_packages sums in-memory completed_ledgers "
                            "(this segment only across --resume runs); "
                            "disk sum below across all package ledger.json "
                            "files is authoritative (coordinator correction "
                            "2026-11-25)."),
        "ledger_actuals_usd_disk_sum": _disk_ledger_sum(ARM_B1_DIR),
        "per_package": [
            {"package_id": r.get("package_id"),
             "outcome": r.get("outcome"),
             "hull_span": r.get("hull_span"),
             "prompt_sha256": r.get("prompt_sha256"),
             "passage_sha256": r.get("passage_sha256"),
             "obligations_sha256": r.get("obligations_sha256"),
             "region_sha256": ((r.get("region") or {})
                               .get("replacement_sha256")),
             "ledger_cost_usd": ledger_actuals(r.get("ledger")),
             "ledger_dispatches": ((r.get("ledger") or {})
                                   .get("dispatch_count"))}
            for r in results
        ],
        "lineage_report": report,
        "stood_down_by_decision": stood_down,
        "ledger_actuals_usd": {
            "prior_A1": prior_cost,
            "b1_packages": b1_actuals,
            "total": prior_cost + b1_actuals,
        },
        "prompt_sha_drift_vs_dry_run": drift,
        "aggregate_guard": aggregate_check(
            prior_ledgers, completed_ledgers, 0.0, PROGRAMME_CAP_USD),
        "failures": failures,
        "verdict": "GO_B1_MERGED" if not failures else "HALT",
    }
    (ARM_B1_DIR / "merge-record.json").write_text(
        json.dumps(merge_record, indent=1, default=str), encoding="utf-8")
    (ARM_B1_DIR / "run-record.json").write_text(
        json.dumps({"runner": RUNNER_ID, "verdict": "GO_B1_MERGED",
                    "failures": failures}, indent=1), encoding="utf-8")
    print(f"merged {len(merged)} lines; B1 actuals ${b1_actuals:.6f}; "
          f"total ${prior_cost + b1_actuals:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
