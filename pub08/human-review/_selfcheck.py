"""PUB-08 human-review self-check (track 2, preparation only).

Reads the coordinator-held blinding map, then asserts:
 1. each version-W/X/Y/Z.md is byte-identical to its mapped source;
 2. zero forbidden (arm-identifying) tokens in the blinded files
    (version-W/X/Y/Z.md + review-form.md + README.md; map excluded by path);
 3. every local figure/asset reference in each copy is accounted for
    (resolves-missing explicitly listed; missing is REPORTED, not fixed);
 4. consistent presentation markers across the four copies;
 5. no invented human results (form blank, README states none exist yet).

Run: python3 pub08/human-review/_selfcheck.py   (from C:\\Projects\\mission)
"""
import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(r"C:\Projects\mission")
HR = REPO / "pub08" / "human-review"
MAP_PATH = HR / "_mapping.WITHHELD.json"
IN_SCOPE = [HR / f"version-{L}.md" for L in "WXYZ"] + [
    HR / "review-form.md",
    HR / "README.md",
]

LITERALS = [
    "arm_a", "arm_b", "arm_c", "arm-a", "arm-b",
    "pub06", "pub08", "pub-06", "pub-08",
    "dispatch-record", "merge-record", "run-record",
    "dispatch_record", "merge_record",
    "prompt_sha", "passage_sha", "region_sha", "merge_sha",
    "model_prompt_sha", "context_sha", "schema_sha",
    "ledger_actuals", "ledger_cost", "ledger_dir", "ledger_dispatches",
    "cost_usd", "hard_cap", "aggregate_actuals", "aggregate_guard",
    "publication-hull", "publication_hull",
    "verify_failed", "review_accepted", "stand_failed", "stood_down",
    "deepseek", "opencode-go", "default_deepseek", "v4.1-flash",
    "worker_request", "worker_model", "model-exec-", "wrq_", "wk_6b9998",
    "provider-state", "pi-rpc", "failure_domain",
    "20261125", "withheld", "_mapping", "sha256", "sha-256",
    "0.0227055", "0.0402504", "0.047636", "0.0703415",
    "01-chapter-candidate", "arm_a_r1", "arm_b1", "arm_c1",
]
REGEXES = [
    r"\bA1\b",
    r"\bB1\b",
    r"\b[0-9a-f]{64}\b",
    r"\b[0-9A-F]{64}\b",
    r"\barm\s+[OHAB](?:1)?\b",
    r"\bcandidate\s+[OHA](?:1)?\b",
    r"\bversion\s+[OHA](?:1)?\b",
    r"\bsource\s+[OHA](?:1)?\b",
    r"O/H/A1/B1",
]

SITE_STATIC = pathlib.Path(r"C:\books\jev\static")
PUB06_ASSETS = REPO / "pub08" / ".." / "pub06" / "ch01" / "assets"
PUB06_ASSETS = pathlib.Path(r"C:\Projects\mission\pub06\ch01\assets")

failures = []
warnings = []


def check_byte_identity(mapping):
    print("== 1. byte-identity ==")
    for label, info in sorted(mapping.items()):
        src = pathlib.Path(info["source_path"])
        dst = HR / f"version-{label}.md"
        if not dst.exists():
            failures.append(f"missing copy {dst.name}")
            print(f"  {label}: MISSING {dst.name}")
            continue
        sb, db = src.read_bytes(), dst.read_bytes()
        sh_s, sh_d = hashlib.sha256(sb).hexdigest(), hashlib.sha256(db).hexdigest()
        ok = (sb == db) and (sh_d == info["sha256"]) and (len(db) == info["bytes"])
        mark = "OK " if ok else "FAIL"
        print(f"  {label}: {mark} bytes={len(db)} sha256={sh_d[:16]}...")
        if not ok:
            failures.append(f"{label} not byte-identical to mapped source")


def check_forbidden():
    print("== 2. forbidden-token scan (map excluded by path) ==")
    hits = 0
    for path in IN_SCOPE:
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        for lit in LITERALS:
            if lit.lower() in low:
                idx = low.find(lit.lower())
                line = text.count("\n", 0, idx) + 1
                print(f"  HIT {path.name}:{line} literal {lit!r}")
                hits += 1
        for rx in REGEXES:
            for m in re.finditer(rx, text):
                line = text.count("\n", 0, m.start()) + 1
                print(f"  HIT {path.name}:{line} regex {rx!r} -> {m.group()!r}")
                hits += 1
    if hits:
        failures.append(f"{hits} forbidden token hits in blinded files")
    else:
        print("  OK  zero forbidden tokens in W/X/Y/Z + form + README")


def audit_figures():
    print("== 3. figure/asset audit ==")
    img_re = re.compile(r'<img\s+[^>]*src="([^"]+)"')
    href_re = re.compile(r'<a\s+[^>]*href="([^"]+)"')
    for label in "WXYZ":
        text = (HR / f"version-{label}.md").read_text(encoding="utf-8")
        refs = set(img_re.findall(text)) | {
            h for h in href_re.findall(text) if ("fig-" in h or "/images/" in h or "assets/" in h)
        }
        refs |= set(re.findall(r"assets/[^\s\"')]+", text))
        refs |= set(re.findall(r"/images/[^\s\"')]+", text))
        print(f"  version-{label}.md: {len(refs)} reference(s)")
        for r in sorted(refs):
            notes = []
            if r.startswith("/images/"):
                site_hit = SITE_STATIC / r.lstrip("/")
                notes.append(f"site-asset exists={site_hit.exists()} ({site_hit})")
                notes.append(f"review-relative exists={(HR / r.lstrip('/')).exists()} (expected False; not vendored)")
            elif r.startswith("assets/"):
                notes.append(f"source-assets exists={(PUB06_ASSETS / pathlib.Path(r).name).exists()}")
                notes.append(f"review-relative exists={(HR / r).exists()} (expected False; not vendored)")
            else:
                notes.append("non-local reference (reported as-is)")
            print(f"    - {r} :: {'; '.join(notes)}")
            if ("review-relative exists=True" not in "; ".join(notes)) and (
                r.startswith("assets/") or r.startswith("/images/")
            ):
                warnings.append(f"{label}: {r} does not resolve from within human-review/ (reported, not fixed)")


def check_presentation():
    print("== 4. presentation consistency ==")
    first_lines = set()
    for label in "WXYZ":
        text = (HR / f"version-{label}.md").read_text(encoding="utf-8")
        first_lines.add(text.splitlines()[0] if text.splitlines() else "")
        for marker in ['title = "Stop Generating"', "## Limitations", "<figure"]:
            if marker not in text:
                failures.append(f"version-{label}.md missing shared marker {marker!r}")
    if len(first_lines) == 1:
        print(f"  OK  identical first line across all four: {next(iter(first_lines))!r}")
    else:
        warnings.append(f"first lines differ across copies (reported): {sorted(first_lines)}")
    print("  filenames: version-W/X/Y/Z.md (same pattern); files unedited byte-copies")


def check_no_human_results():
    print("== 5. no invented human results ==")
    readme = (HR / "README.md").read_text(encoding="utf-8")
    form = (HR / "review-form.md").read_text(encoding="utf-8")
    if "No human results exist yet." not in readme:
        failures.append("README missing the 'no human results' statement")
    else:
        print("  OK  README states no human results exist yet")
    filled = re.findall(r"^-\s+[WXYZ]:\s*\d", form, re.M) + re.findall(r"\[x\]", form, re.I)
    if filled:
        failures.append(f"review form appears pre-filled: {filled}")
    else:
        print("  OK  review form blank (no ratings/choices filled in)")


def main():
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))["mapping"]
    check_byte_identity(mapping)
    check_forbidden()
    audit_figures()
    check_presentation()
    check_no_human_results()
    print("== summary ==")
    print(f"  failures: {len(failures)}; warnings: {len(warnings)}")
    for w in warnings:
        print(f"  WARN {w}")
    for f in failures:
        print(f"  FAIL {f}")
    if failures:
        print("SELFCHECK: FAIL")
        return 1
    print("SELFCHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
