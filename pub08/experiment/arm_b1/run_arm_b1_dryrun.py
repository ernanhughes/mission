"""PUB-08 batch 4 — Arm B1 Ch1 dry run ($0, zero dispatches).

Reconcile -> plan revalidate (reuse frozen plan-ch1.json when the
revision is unchanged) -> package (7 expected) -> per-package
``transform automate --dry-run`` with prompt/passage/obligation SHAs ->
hull layer (one span per package) -> no-op merge gate on O.

Reads (read-only): Jev Ch1, pub06/ch01 frozen records, worker catalogue.
Writes: ONLY this directory (arm_b1/): dry-run.json + dryrun_out/ CLI
out-dirs. Never modifies Jev / pub06 / pub07 / mission docs / catalog.

Loud-halt conditions (non-zero exit, no silent correction): any freeze
drift; live reconcile states != frozen; boundary not executable or !=
frozen boundary-ch1.json; package set != frozen (ids/op_refs/spans/
hashes/blocked); hull != expected spans; any prompt-SHA drift between
the two dry-run passes (re-freeze comparison).

Run with the writer venv python from anywhere:
  C:\\Projects\\writer\\venv\\Scripts\\python.exe run_arm_b1_dryrun.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MISSION = HERE.parents[2]
PUB06 = MISSION / "pub06" / "ch01"
JEV_ROOT = Path(r"C:\books\jev")
O_PATH = JEV_ROOT / "content" / "books" / "jev" / "01-chapter.md"
FREEZE = MISSION / "pub08" / "experiment" / "freeze.json"
OUT_JSON = HERE / "dry-run.json"
OUT_DIRS = HERE / "dryrun_out"

EXPECTED_HULLS = {
    "passage:Four words we keep apart": {"start_line": 392, "end_line": 396},
    "passage:Path 1: the predicate": {"start_line": 101, "end_line": 122},
    "passage:Paths 2 and 3: generate, then parse": {
        "start_line": 237, "end_line": 317},
    "passage:What we measured, and what we did not": {
        "start_line": 405, "end_line": 420},
    "passage:Where this leaves the argument": {
        "start_line": 509, "end_line": 518},
}

FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"HALT: {msg}", file=sys.stderr)


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def main() -> int:
    sys.path.insert(0, r"C:\Projects\writer\packages\writer-core")
    sys.path.insert(0, r"C:\Projects\writer\packages\writer-cli")
    from typer.testing import CliRunner
    from writer_cli.main import app
    from writer_core.analysis import publication_hull_merge as hm

    record: dict = {"runner": "pub08/experiment/arm_b1/run_arm_b1_dryrun.py",
                    "live_model_dispatches": 0,
                    "spend_usd": 0.0}
    run = CliRunner()

    # ---- 1. Freeze reconfirmation (live bytes vs freeze.json + design) ----
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    checks: dict = {}
    o_raw = O_PATH.read_bytes()
    o_sha = hashlib.sha256(o_raw).hexdigest()
    checks["O_sha_match_freeze"] = (
        o_sha == freeze["frozen_inputs"]["O"]["raw_sha256"])
    checks["O_bytes_match_freeze"] = (
        len(o_raw) == freeze["frozen_inputs"]["O"]["bytes"])
    h_path = Path(freeze["frozen_inputs"]["H"]["path"])
    checks["H_sha_match_freeze"] = (
        sha256_bytes(h_path) == freeze["frozen_inputs"]["H"]["raw_sha256"])
    for name, rel in (("publication_automation",
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
        live = sha256_bytes(Path(r"C:\Projects\writer") / rel)
        checks[f"module_{name}_match_freeze"] = (
            live == freeze["writer"]["frozen_modules"][name]["sha256"])
    plan_sha = sha256_bytes(PUB06 / "plan-ch1.json")
    pkgs_sha = sha256_bytes(PUB06 / "packages-ch1.json")
    adj_sha = sha256_bytes(PUB06 / "adjudications-ch1.json")
    checks["plan_sha_match_design_cb34c18e"] = plan_sha.startswith("cb34c18e")
    checks["packages_sha_match_design_ba7f869c"] = pkgs_sha.startswith("ba7f869c")
    checks["adjudications_sha_match_design_188d843f"] = adj_sha.startswith(
        "188d843f")
    cat_sha = sha256_bytes(Path(freeze["price_catalogue"]["path"]))
    checks["catalogue_sha_match_freeze"] = (
        cat_sha == freeze["price_catalogue"]["sha256"])
    record["freeze_reconfirmation"] = {"checks": checks,
                                       "drift": [k for k, v in checks.items()
                                                 if not v]}
    if any(not v for v in checks.values()):
        fail(f"freeze drift: {[k for k, v in checks.items() if not v]}")
        OUT_JSON.write_text(json.dumps(record, indent=1), encoding="utf-8")
        return 2

    o_lines = o_raw.decode("utf-8").splitlines()
    record["O"] = {"bytes": len(o_raw), "lines": len(o_lines),
                   "raw_sha256": o_sha}

    # ---- 2. Reconcile live ----
    res = run.invoke(app, ["reconcile", "chapter", "jev", "01-chapter",
                           "--book-root", str(JEV_ROOT), "--json"])
    if res.exit_code != 0:
        fail(f"live reconcile failed: {res.output[-500:]}")
        OUT_JSON.write_text(json.dumps(record, indent=1), encoding="utf-8")
        return 2
    recon = json.loads(res.output)["result"]
    live_states = {v["claim_id"]: v["state"] for v in recon["verdicts"]}
    frozen_states = json.loads(
        (PUB06 / "reconcile-states-ch1.json").read_text(encoding="utf-8"))
    plan_doc = json.loads((PUB06 / "plan-ch1.json").read_text(
        encoding="utf-8"))["result"]
    plan_states = {}
    for entry in (plan_doc.get("inputs") or {}).get("reconcile_states") or []:
        cid, _, state = entry.rpartition(":")
        plan_states[cid] = state
    record["reconcile"] = {
        "inventory_revision": recon["summary"]["inventory_revision"],
        "repo_revision": recon["summary"]["repo_revision"],
        "n_claims": len(live_states),
        "live_states_match_frozen_file": live_states == frozen_states,
        "live_states_match_plan_inputs": live_states == plan_states,
        "plan_inventory_rev": plan_doc.get("inventory_rev"),
    }
    if live_states != frozen_states or live_states != plan_states:
        fail("reconcile revision changed: live states != frozen/plan states")

    # ---- 3. Plan revalidate: reuse frozen plan-ch1.json iff unchanged ----
    common = ["--book-root", str(JEV_ROOT),
              "--plan", str(PUB06 / "plan-ch1.json"),
              "--reconcile-states", str(PUB06 / "reconcile-states-ch1.json"),
              "--inventory-digest",
              (PUB06 / "inventory-digest-ch1.txt").read_text(
                  encoding="utf-8").strip(),
              "--evidence-rev", "jev@live",
              "--adjudications", str(PUB06 / "adjudications-ch1.json")]
    chk = run.invoke(app, ["transform", "check", "jev", "01-chapter"]
                     + common + ["--json"])
    chk_res = json.loads(chk.output)["result"]
    frozen_boundary = json.loads(
        (PUB06 / "boundary-ch1.json").read_text(encoding="utf-8"))["result"]
    live_fp = hashlib.sha256(
        (o_raw.decode("utf-8")).encode("utf-8")).hexdigest()
    from writer_core.analysis.publication_transformation import (
        canonical_candidate_bytes as _canon)
    live_canon_fp = hashlib.sha256(_canon(o_raw.decode("utf-8"))).hexdigest()
    record["plan_revalidate"] = {
        "plan": "pub06/ch01/plan-ch1.json (frozen; reused, not re-planned)",
        "reuse_decision": ("reused frozen plan-ch1.json: live O canonical "
                           "fingerprint == plan source_fingerprint AND live "
                           "reconcile states == plan-bound states (no flips)"),
        "live_O_canonical_fp": live_canon_fp,
        "plan_source_fingerprint": plan_doc.get("source_fingerprint"),
        "fingerprint_match": live_canon_fp == plan_doc.get("source_fingerprint"),
        "executable": chk_res.get("executable"),
        "violations_match_frozen": (
            [(v.get("code"), v.get("op_id"), v.get("severity"))
             for v in chk_res.get("violations", [])]
            == [(v.get("code"), v.get("op_id"), v.get("severity"))
                for v in frozen_boundary.get("violations", [])]),
        "op_verdicts_match_frozen": (
            chk_res.get("op_verdicts") == frozen_boundary.get("op_verdicts")),
        "binding_digest_match_frozen": (
            chk_res.get("binding_digest")
            == frozen_boundary.get("binding_digest")),
        "binding_digest": chk_res.get("binding_digest"),
    }
    if not (chk_res.get("executable")
            and live_canon_fp == plan_doc.get("source_fingerprint")
            and record["plan_revalidate"]["violations_match_frozen"]
            and record["plan_revalidate"]["op_verdicts_match_frozen"]
            and record["plan_revalidate"]["binding_digest_match_frozen"]):
        fail("plan revalidation diverged from frozen boundary-ch1.json")

    # ---- 4. Package live: 7 expected, identical to frozen ----
    pkg = run.invoke(app, ["transform", "package", "jev", "01-chapter"]
                     + common + ["--json"])
    if pkg.exit_code != 0:
        fail(f"live package compile failed: {pkg.output[-500:]}")
        OUT_JSON.write_text(json.dumps(record, indent=1), encoding="utf-8")
        return 2
    live_pkgs = json.loads(pkg.output)["result"]["packages"]
    frozen_pkgs = json.loads(
        (PUB06 / "packages-ch1.json").read_text(encoding="utf-8"))["result"]["packages"]
    pkg_rows = []
    for live_p, frozen_p in zip(live_pkgs, frozen_pkgs):
        same = (live_p.get("package_id") == frozen_p.get("package_id")
                and live_p.get("op_refs") == frozen_p.get("op_refs")
                and live_p.get("source_spans") == frozen_p.get("source_spans")
                and live_p.get("package_hash") == frozen_p.get("package_hash")
                and live_p.get("blocked") == frozen_p.get("blocked"))
        pkg_rows.append({"package_id": live_p.get("package_id"), "identical": same,
                         "n_spans": len(live_p.get("source_spans") or []),
                         "n_ops": len(live_p.get("op_refs") or []),
                         "blocked": live_p.get("blocked")})
    record["package"] = {"n_packages": len(live_pkgs),
                         "expected": 7,
                         "packages_identical_to_frozen": all(
                             r["identical"] for r in pkg_rows),
                         "packages": pkg_rows}
    if len(live_pkgs) != 7 or not all(r["identical"] for r in pkg_rows):
        fail("live package set diverged from frozen packages-ch1.json")

    # ---- 5. Per-package automate --dry-run, two passes (re-freeze) ----
    def _dry_packages(pass_out: Path):
        entries = {}
        for live_p in live_pkgs:
            pid = live_p.get("package_id")
            out = run.invoke(
                app, ["transform", "automate", "jev", "01-chapter",
                      "--package-id", pid,
                      "--out-dir", str(pass_out / pid.replace(":", "_")),
                      "--dry-run", "--json"] + common)
            env = json.loads(out.output)
            row = {"exit_code": out.exit_code, "cli_ok": env.get("ok"),
                   "errors": env.get("errors")}
            if out.exit_code == 0:
                ed = (env.get("result") or {}).get("editorial") or {}
                rv = (env.get("result") or {}).get("review") or {}
                row.update({
                    "status": "dry_run_ok",
                    "passage_sha256": ed.get("passage_sha256"),
                    "prompt_sha256": sha256_text(ed.get("prompt") or ""),
                    "review_prompt_sha256": sha256_text(rv.get("prompt") or ""),
                    "obligations_sha256": sha256_json(
                        live_p.get("preservation_obligations") or []),
                    "n_obligations": len(
                        live_p.get("preservation_obligations") or []),
                })
            else:
                row.update({"status": "refused",
                            "refusal": (env.get("errors") or [{}])[0].get(
                                "message"),
                            "obligations_sha256": sha256_json(
                                live_p.get("preservation_obligations") or []),
                            "n_obligations": len(
                                live_p.get("preservation_obligations") or []),
                            "obligations_note": ("compile-level (no dry-run "
                                                 "payload: production refuses "
                                                 "before preparing it)")})
            entries[pid] = row
        return entries

    pass1 = _dry_packages(OUT_DIRS / "pass1")
    pass2 = _dry_packages(OUT_DIRS / "pass2")
    drift = {pid: (pass1[pid].get("prompt_sha256"),
                   pass2[pid].get("prompt_sha256"))
             for pid in pass1
             if pass1[pid].get("prompt_sha256") != pass2[pid].get("prompt_sha256")}
    record["automate_dry_run"] = {
        "passes": 2,
        "zero_dispatches_note": ("--dry-run returns before build_runtime()/ "
                                 "run_typed_task wiring "
                                 "(transform.py dry-run block); no Worker "
                                 "POST, no provider call in either pass"),
        "prompt_sha_drift_pass1_vs_pass2": drift,
        "packages": pass1,
    }
    if drift:
        fail(f"prompt-SHA drift vs re-frozen values (pass1 vs pass2): {drift} "
             f"-- NO silent correction; halting")

    # ---- 6. Hull layer: exactly one span per mutating package ----
    hull_rows = []
    for live_p in live_pkgs:
        pid = live_p.get("package_id")
        if not (live_p.get("op_refs") or []):
            hull_rows.append({"package_id": pid, "status": "skipped_no_ops",
                              "hull_span": None})
            continue
        hull = hm.compile_hull_span(live_p)
        expected = EXPECTED_HULLS.get(pid)
        hull_rows.append({"package_id": pid, "status": "single_span",
                          "spans_in": len(live_p.get("source_spans") or []),
                          "hull_span": hull,
                          "expected_hull_span": expected,
                          "match": hull == expected,
                          "op_refs": live_p.get("op_refs")})
    preview = hm.preview_merge(o_lines, live_pkgs)
    record["hull"] = {
        "gate": "dry-run shows exactly one span per package",
        "packages": hull_rows,
        "all_hulls_match_expected": all(
            r.get("match", True) for r in hull_rows),
        "preview_single_span_rows": sum(
            1 for r in preview if r["status"] == "single_span"),
    }
    if not all(r.get("match", True) for r in hull_rows):
        fail("hull span != expected Ch1 hull for: "
             f"{[r['package_id'] for r in hull_rows if not r.get('match', True)]}")

    # ---- 7. No-op merge gate on live O ----
    # O worktree bytes are CRLF (core.autocrlf checkout artifact); the
    # authoritative repo blob is LF. The merge serialises LF-canonical
    # (production Fix G form), so the strict byte-identity gate is drawn
    # against the BLOB; the worktree comparison must differ ONLY by the
    # 562 CR removals and is recorded verbatim, never elided.
    import subprocess as _sp
    blob = _sp.run(["git", "show",
                    "HEAD:content/books/jev/01-chapter.md"],
                   capture_output=True, cwd=str(JEV_ROOT)).stdout
    merged, lineage = hm.merge_region_replacements(o_lines, [])
    merged_bytes = hm.canonical_merge_bytes(merged)
    crlf_only = (o_raw.replace(b"\r\n", b"\n") == merged_bytes)
    record["noop_merge_gate"] = {
        "merged_sha256": hashlib.sha256(merged_bytes).hexdigest(),
        "O_blob_sha256": hashlib.sha256(blob).hexdigest(),
        "O_worktree_raw_sha256": o_sha,
        "O_worktree_newlines": {
            "crlf": o_raw.count(b"\r\n"),
            "lone_lf": o_raw.count(b"\n") - o_raw.count(b"\r\n")},
        "byte_identical_to_authoritative_blob": merged_bytes == blob,
        "worktree_diff_is_crlf_normalisation_only": crlf_only,
        "merged_lines_match_O_lines": merged == o_lines,
        "n_lines": len(merged),
    }
    if merged_bytes != blob:
        fail("no-op merge did NOT reproduce authoritative O blob byte-for-byte")
    if not crlf_only:
        fail("no-op merge vs worktree differs by MORE than CRLF normalisation")

    record["verdict"] = ("GO_DRY_RUN" if not FAILURES else "HALT")
    record["failures"] = FAILURES
    OUT_JSON.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(json.dumps({k: record[k] for k in
                      ("verdict", "failures")}, indent=1))
    if "automate_dry_run" in record:
        for pid, row in record["automate_dry_run"]["packages"].items():
            print(f"  {pid}: {row.get('status')}"
                  + (f" prompt={row.get('prompt_sha256', '')[:12]}..."
                     if row.get("status") == "dry_run_ok"
                     else f" ({row.get('refusal')})"))
    return 0 if not FAILURES else 3


if __name__ == "__main__":
    raise SystemExit(main())
