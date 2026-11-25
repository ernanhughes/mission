"""PUB-08 batch 7b — eval rerun runner (coordinator-executed, $0 here).

Reruns EXACTLY these 19 still-malformed / coerced-abstain items from
``pub08/experiment/eval/model-judgements.json`` (134 records) and nothing
else — held-out budget is CONSUMED (``probe-key.json``
``model_reader_runs == 1``), so held-out probes are never run or touched:

- public probes (11): T1:F1, T2:E1/F1/F3, T3:E3/F2, T4:E2/F1/F3/F4/F5
- checklist malformed (1): T4:C1
- adjudication assists (3): T1vT4:Q4/Q5, T2vT3:Q2
- coerced-abstain checklist (4): T3:C1/C2, T4:C3/C7

Permanently EXCLUDED (held-out, budget consumed): T2:F11, T4:F10, T4:F11.
Any held-out id in the work list is a hard refusal (by id, tested).

Verbatim reuse of ``run_eval_judges.py`` (same module, imported — not
copied): same prompt builders (each rebuilt prompt's SHA256 is verified
against the original record's ``prompt_sha256`` in model-judgements.json,
HALT on any mismatch), same DTOs, same route ``default_haiku_go``, same
$1.00 cap with briefed priors $0.0703 + projection $0.05, same
metered-halt (any ``cost_usd > 0`` halts immediately), same one-shot
semantics (malformed/abstain recorded, never retried).

THIS FILE PERFORMS LIVE DISPATCHES WHEN RUN AS ``__main__``. It is
written (not executed) here and executed later by the coordinator in a
credential-bearing shell. Importing it is side-effect free: all live
wiring is lazy inside ``main()``. The fake-gate
(``tests/core/test_pub08_eval_rerun_gate.py`` in the Writer repo)
imports only the pure helpers with fake dispatch callables: zero live
calls.

Output: ``pub08/experiment/eval/model-judgements-rerun.json`` keyed by
LABEL only (no arm identities), same record schema subset as the
original plus ``supersedes`` links to the original item_ids. The
original ``model-judgements.json`` is NEVER modified.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

RUNNER_ID = "pub08/experiment/run_eval_rerun.py"
BATCH = "pub08-eval-rerun-v0.1"
STAGE_ID = "pub08-eval"
MODEL_OVERRIDE = "default_haiku_go"

PROGRAMME_CAP_USD = 1.00
#: Coordinator-briefed aggregate priors for the rerun + worst-case
#: pre-dispatch projection for the 19 rerun calls. Exact arithmetic:
#: $0.0703 + $0.05 = $0.1203 <= $1.00 (remaining $0.8797).
PRIORS_USD = 0.0703
RERUN_PROJECTION_USD = 0.05

EXP = Path(__file__).resolve().parent
EVAL_DIR = EXP / "eval"
BLIND_PACK_PATH = EVAL_DIR / "blind-pack.json"
PROBE_KEY_PATH = EVAL_DIR / "probe-key.json"
MODEL_JUDGEMENTS_PATH = EVAL_DIR / "model-judgements.json"
RERUN_OUTPUT_PATH = EVAL_DIR / "model-judgements-rerun.json"

if str(EXP) not in sys.path:
    sys.path.insert(0, str(EXP))
# Verbatim reuse: prefer an already-loaded instance of the v0.1 module
# (the fake-gate pre-loads it as "pub08_run_eval_judges") so DTO/halt
# classes stay identical objects; otherwise import it fresh.
_base = sys.modules.get("pub08_run_eval_judges") or sys.modules.get(
    "run_eval_judges")
if _base is None:
    import run_eval_judges as _base  # noqa: E402  (verbatim reuse, not a copy)

assert _base.MODEL_OVERRIDE == MODEL_OVERRIDE
assert _base.STAGE_ID == STAGE_ID

# ---------------------------------------------------------------------------
# Exact-19 work list (full item_ids, same shape as run_eval_judges builders)
# ---------------------------------------------------------------------------

RERUN_PROBES: list[tuple[str, str]] = [
    ("T1", "F1"),
    ("T2", "E1"), ("T2", "F1"), ("T2", "F3"),
    ("T3", "E3"), ("T3", "F2"),
    ("T4", "E2"), ("T4", "F1"), ("T4", "F3"),
    ("T4", "F4"), ("T4", "F5"),
]

RERUN_CHECKLIST: list[tuple[str, str]] = [
    ("T4", "C1"),
    ("T3", "C1"), ("T3", "C2"), ("T4", "C3"), ("T4", "C7"),
]

RERUN_ASSISTS: list[tuple[str, str, str]] = [
    ("T1", "T4", "Q4"), ("T1", "T4", "Q5"), ("T2", "T3", "Q2"),
]

RERUN_ITEM_IDS: tuple[str, ...] = tuple(sorted(
    [f"{label}:probe:{pid}" for label, pid in RERUN_PROBES]
    + [f"{label}:checklist:{cid}" for label, cid in RERUN_CHECKLIST]
    + [f"{la}v{lb}:assist:{qid}" for la, lb, qid in RERUN_ASSISTS]
))
assert len(RERUN_ITEM_IDS) == 19, RERUN_ITEM_IDS

#: Held-out items excluded permanently (budget consumed, 0/1 left).
#: Parametrised by probe id so ANY held-out probe id refuses, not just
#: these three — the three are the ones inside the v0.1 malformed set.
HELDOUT_REFUSED_SHORTHAND = ("T2:F11", "T4:F10", "T4:F11")


def _pid_of_item(item_id: str) -> str | None:
    """Probe id for probe items (both 'T2:probe:F11' and 'T2:F11' forms)."""
    parts = str(item_id).split(":")
    if len(parts) == 3 and parts[1] == "probe":
        return parts[2]
    if len(parts) == 2 and parts[1] in _base.HELDOUT_IDS:
        return parts[1]
    if len(parts) == 2 and parts[1] in _base.PUBLIC_IDS:
        return parts[1]
    return None


def check_item_allowed(item_id: str) -> None:
    """Hard refusal for held-out probe ids (never dispatched, never read)."""
    pid = _pid_of_item(item_id)
    if pid is not None and pid in _base.HELDOUT_IDS:
        raise _base.HeldoutRefusedError(item_id, (
            f"held-out probe {pid!r}: budget consumed "
            "(model_reader_runs==1); refusing"))


def assert_no_heldout(item_ids: list[str] | tuple[str, ...]) -> None:
    for item_id in item_ids:
        check_item_allowed(item_id)


def assert_heldout_consumed(probe_key: dict[str, Any]) -> None:
    """Rerun precondition: the single held-out run is already consumed."""
    try:
        runs = int((probe_key.get("consumption") or {}).get(
            "model_reader_runs", -1))
    except (TypeError, ValueError):
        runs = -1
    if runs != 1:
        raise _base.HeldoutRefusedError("heldout-precondition", (
            f"model_reader_runs=={runs!r}, want exactly 1: refusing — "
            "held-out budget state unexpected, do not dispatch"))


# ---------------------------------------------------------------------------
# Prompt-SHA verification against the original records
# ---------------------------------------------------------------------------

def original_sha_map(mj: dict[str, Any]) -> dict[str, str]:
    """Full item_id -> recorded prompt_sha256 from model-judgements.json."""
    out: dict[str, str] = {}
    for label, bucket in (mj.get("checklist") or {}).items():
        for cid, rec in (bucket or {}).items():
            if isinstance(rec, dict) and rec.get("prompt_sha256"):
                out[str(rec.get("item_id",
                               f"{label}:checklist:{cid}"))] = str(
                    rec["prompt_sha256"])
    for label, bucket in (mj.get("probes") or {}).items():
        for pid, rec in (bucket or {}).items():
            if isinstance(rec, dict) and rec.get("prompt_sha256"):
                out[str(rec.get("item_id",
                               f"{label}:probe:{pid}"))] = str(
                    rec["prompt_sha256"])
    for rec in mj.get("adjudication_assists") or []:
        if isinstance(rec, dict) and rec.get("prompt_sha256"):
            out[str(rec.get("item_id"))] = str(rec["prompt_sha256"])
    return out


def verify_prompt_sha(item_id: str, rebuilt_prompt: str,
                      orig_map: dict[str, str]) -> str:
    """HALT unless the rebuilt prompt hashes to the recorded SHA."""
    want = orig_map.get(item_id)
    if not want:
        raise _base.EvalHaltError(item_id, (
            "no original prompt_sha256 for rerun item: refusing to "
            "dispatch a prompt without a recorded baseline"))
    got = _base.sha256_text(rebuilt_prompt)
    if got != want:
        raise _base.EvalHaltError(item_id, (
            f"rebuilt prompt SHA {got} != recorded {want}: prompt drift, "
            "HALT with zero dispatches on this item"))
    return got


# ---------------------------------------------------------------------------
# Frozen texts loader (same bytes discipline as run_eval_judges.main)
# ---------------------------------------------------------------------------

def load_texts_by_label(
        blind_pack: dict[str, Any]) -> tuple[dict[str, str],
                                             dict[str, str]]:
    """Raw-byte SHA check + CRLF->LF decode, keyed by blind label."""
    mapping = blind_pack.get("mapping") or {}
    texts: dict[str, str] = {}
    label_sha: dict[str, str] = {}
    for label, arm in mapping.items():
        path = _base.ARM_CANDIDATE_FILES[arm]
        raw = Path(path).read_bytes()
        want = (blind_pack.get("file_sha256") or {}).get(arm)
        if hashlib.sha256(raw).hexdigest() != want:
            raise _base.EvalHaltError(str(label), (
                f"text SHA drift for {label} (arm bytes changed)"))
        texts[str(label)] = raw.decode("utf-8").replace("\r\n", "\n")
        label_sha[str(label)] = hashlib.sha256(raw).hexdigest()
    for label in mapping:
        if label_sha[str(label)] != (
                blind_pack.get("label_sha256") or {}).get(str(label)):
            raise _base.EvalHaltError(str(label), "label SHA drift")
    return texts, label_sha


# ---------------------------------------------------------------------------
# Rerun sweep (pure; main() wires live paths + writes the file)
# ---------------------------------------------------------------------------

def _lookup_probe(probe_key: dict[str, Any], pid: str) -> dict[str, str]:
    for entry in probe_key.get("probes") or []:
        if isinstance(entry, dict) and entry.get("id") == pid:
            return {"id": str(entry["id"]),
                    "visibility": str(entry.get("visibility")),
                    "question": str(entry.get("question")),
                    "expected": str(entry.get("expected"))}
    raise _base.EvalHaltError(f"probe:{pid}",
                             f"probe {pid!r} missing from probe-key")


def _lookup_criterion(cid: str) -> dict[str, str]:
    for crit in _base.CHECKLIST:
        if crit["id"] == cid:
            return crit
    raise _base.EvalHaltError(f"checklist:{cid}",
                             f"unknown criterion {cid!r}")


def _lookup_question(qid: str) -> dict[str, str]:
    for question in _base.ASSIST_QUESTIONS:
        if question["id"] == qid:
            return question
    raise _base.EvalHaltError(f"assist:{qid}",
                             f"unknown assist question {qid!r}")


def run_rerun_batch(*, dispatch_fn: Callable[..., Any],
                    texts_by_label: dict[str, str],
                    probe_key: dict[str, Any],
                    orig_map: dict[str, str],
                    priors: list[Any] | None = None,
                    projection_usd: float = RERUN_PROJECTION_USD,
                    cap_usd: float = PROGRAMME_CAP_USD,
                    prompt_sink: list[dict[str, Any]] | None = None,
                    ) -> dict[str, Any]:
    """Rerun exactly the 19 items once each through the injected callable.

    Raises the fail-closed halts (held-out refusal / prompt-SHA mismatch /
    spend / cost / route / blinding) with the exact position; malformed
    single items are recorded abstain/fail and the sweep continues.
    The held-out key is only READ (never consumed or written here).
    """
    assert_no_heldout(list(RERUN_ITEM_IDS))
    assert_heldout_consumed(probe_key)
    drift = _base.probe_key_mirror_ok(probe_key)
    if drift:
        raise _base.EvalHaltError("batch", (
            f"probe-key drift vs frozen mirror: {drift[:3]}"))
    priors = list(priors) if priors is not None else [
        {"total_cost_usd": PRIORS_USD}]

    guard = _base.aggregate_check(priors, [], projection_usd, cap_usd)
    if not guard.get("allowed"):
        raise _base.SpendHaltError("batch:pre-dispatch", (
            f"priors ${guard.get('aggregate_actuals_usd', float('nan')):.6f} "
            f"+ projection ${projection_usd:.3f} > cap ${cap_usd:.2f}: "
            "HALT with zero dispatches"))

    # Build the 19 prompts verbatim via the v0.1 builders; verify each
    # SHA against the recorded baseline BEFORE any dispatch.
    jobs: list[tuple[str, dict[str, Any]]] = []
    for label, pid in RERUN_PROBES:
        probe = _lookup_probe(probe_key, pid)
        if probe["visibility"] != "public":
            raise _base.HeldoutRefusedError(
                f"{label}:probe:{pid}",
                f"probe {pid!r} is not public: refusing")
        built = _base.build_probe_prompt(label, texts_by_label[label],
                                         probe)
        verify_prompt_sha(built["item_id"], built["prompt"], orig_map)
        jobs.append(("probe", built))
    for label, cid in RERUN_CHECKLIST:
        built = _base.build_checklist_prompt(label, texts_by_label[label],
                                             _lookup_criterion(cid))
        verify_prompt_sha(built["item_id"], built["prompt"], orig_map)
        jobs.append(("checklist", built))
    for la, lb, qid in RERUN_ASSISTS:
        built = _base.build_assist_prompt(la, lb, texts_by_label[la],
                                          texts_by_label[lb],
                                          _lookup_question(qid))
        verify_prompt_sha(built["item_id"], built["prompt"], orig_map)
        jobs.append(("assist", built))
    if len(jobs) != 19 or {m["item_id"] for _, m in jobs} != set(
            RERUN_ITEM_IDS):
        raise _base.EvalHaltError("batch", (
            f"rerun scope drift: built {len(jobs)} items, want exactly 19"))

    if prompt_sink is not None:
        prompt_sink.extend([m for _, m in jobs])
    _base.check_blinding([m for _, m in jobs], texts_by_label)

    checklist: dict[str, dict[str, Any]] = {}
    probes_out: dict[str, dict[str, Any]] = {}
    assists: list[dict[str, Any]] = []
    failures: list[str] = []

    for kind, meta in jobs:
        gate = _base.aggregate_check(
            priors, [{"total_cost_usd": 0.0}], projection_usd, cap_usd)
        if not gate.get("allowed"):
            raise _base.SpendHaltError(str(meta.get("item_id", "?")), (
                "aggregate cap would be exceeded mid-batch: HALT with zero "
                "further dispatches"))
        try:
            if kind == "probe":
                label, pid = str(meta["item_id"]).split(":probe:")
                res = _base.run_probe_item(
                    dispatch_fn, label=label,
                    text=texts_by_label[label],
                    probe=_lookup_probe(probe_key, pid))
            elif kind == "checklist":
                label, cid = str(meta["item_id"]).split(":checklist:")
                res = _base.run_checklist_item(
                    dispatch_fn, label=label,
                    text=texts_by_label[label],
                    criterion=_lookup_criterion(cid))
            else:
                pair, qid = str(meta["item_id"]).split(":assist:")
                la, lb = pair.split("v")
                res = _base.run_assist_item(
                    dispatch_fn, label_a=la, label_b=lb,
                    text_a=texts_by_label[la], text_b=texts_by_label[lb],
                    question=_lookup_question(qid))
        except _base.EvalHaltError as exc:
            failures.append(str(exc))
            raise
        res["supersedes"] = meta["item_id"]
        if kind == "probe":
            probes_out.setdefault(res["label"], {})[res["probe_id"]] = res
        elif kind == "checklist":
            checklist.setdefault(res["label"], {})[
                res["criterion_id"]] = res
        else:
            assists.append(res)

    totals = _base._totals(checklist, probes_out, {}, assists)
    return {"checklist": checklist, "probes": probes_out,
            "assists": assists, "failures": failures, "totals": totals,
            "aggregate_guard": gate}


# ---------------------------------------------------------------------------
# Live entry point (coordinator-executed; NOT run here)
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

    failures: list[str] = []

    def _halt(msg: str) -> int:
        failures.append(msg)
        print(f"HALT: {msg}", file=_sys.stderr)
        return 3

    try:
        blind_pack = json.loads(BLIND_PACK_PATH.read_text(encoding="utf-8"))
        probe_key = _base.read_probe_key(PROBE_KEY_PATH)
        mj = json.loads(MODEL_JUDGEMENTS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return _halt(f"unreadable frozen eval inputs: {exc}")
    if _base.probe_key_mirror_ok(probe_key):
        return _halt("probe-key drift vs frozen mirror")
    try:
        assert_heldout_consumed(probe_key)
    except _base.HeldoutRefusedError as exc:
        return _halt(str(exc))
    orig_map = original_sha_map(mj)
    missing = [i for i in RERUN_ITEM_IDS if i not in orig_map]
    if missing:
        return _halt(f"rerun items missing from model-judgements.json: "
                     f"{missing[:5]}")
    try:
        assert_no_heldout(list(RERUN_ITEM_IDS))
    except _base.HeldoutRefusedError as exc:
        return _halt(str(exc))
    mapping = blind_pack.get("mapping") or {}
    if set(mapping) != {"T1", "T2", "T3", "T4"}:
        return _halt("blind-pack mapping unexpected")
    try:
        texts_by_label, label_sha = load_texts_by_label(blind_pack)
    except _base.EvalHaltError as exc:
        return _halt(str(exc))
    except Exception as exc:
        return _halt(f"candidate texts unreadable: {exc}")

    priors = [{"total_cost_usd": PRIORS_USD}]
    verdict = _base.aggregate_check(priors, [], RERUN_PROJECTION_USD,
                                    PROGRAMME_CAP_USD)
    if not verdict.get("allowed"):
        return _halt(
            f"aggregate spend guard: priors ${PRIORS_USD:.6f} + projection "
            f"${RERUN_PROJECTION_USD:.3f} exceeds cap "
            f"${PROGRAMME_CAP_USD:.2f}: HALT with zero dispatches")
    print(f"priors: ${PRIORS_USD:.7f} + projection "
          f"${RERUN_PROJECTION_USD:.3f} <= ${PROGRAMME_CAP_USD:.2f} OK "
          f"(remaining ${verdict.get('remaining_usd', 0.0):.6f}; "
          f"held-out runs=1, no held-out dispatch)")

    runtime = _build_runtime()
    models = runtime.require("models")

    def _dispatch(*, task: str, prompt: str, dto: Any,
                  metadata: Any = None,
                  context_for_provenance: Any = None) -> Any:
        operation_id = str((metadata or {}).get("operation_id")
                           or (metadata or {}).get("package_id")
                           or "pub08-eval-rerun")
        return _run_typed_task(
            models, task=task, prompt=prompt, dto=dto,
            domain="publication", operation_id=operation_id,
            stage_id=STAGE_ID, metadata=dict(metadata or {}),
            context_for_provenance=context_for_provenance)

    _ = _Runner(), _app  # live CLI surface available; seam is run_typed_task

    prompt_metas: list[dict[str, Any]] = []
    try:
        sweep = run_rerun_batch(
            dispatch_fn=_dispatch, texts_by_label=texts_by_label,
            probe_key=probe_key, orig_map=orig_map, priors=priors,
            prompt_sink=prompt_metas)
    except _base.EvalHaltError as exc:
        return _halt(str(exc))

    output = {
        "runner": RUNNER_ID,
        "batch": BATCH,
        "stage_id": STAGE_ID,
        "route": MODEL_OVERRIDE,
        "rerun_of": {"runner": _base.RUNNER_ID, "batch": _base.BATCH,
                     "source_file": "eval/model-judgements.json"},
        "rerun_item_ids": list(RERUN_ITEM_IDS),
        "supersedes": {i: i for i in RERUN_ITEM_IDS},
        "heldout": {"model_reader_runs": 1, "heldout_run": False,
                    "refused_ids": list(HELDOUT_REFUSED_SHORTHAND),
                    "note": ("held-out budget consumed; key only read, "
                             "never written; no held-out dispatch")},
        "priors_usd": PRIORS_USD,
        "projection_usd": RERUN_PROJECTION_USD,
        "cap_usd": PROGRAMME_CAP_USD,
        "aggregate_guard": sweep.get("aggregate_guard"),
        "blind_pack_sha256": blind_pack.get("pack_sha256"),
        "probe_key_probes_sha256": _base.sha256_json(
            probe_key.get("probes") or []),
        "texts": {label: {"label_sha256": label_sha[label],
                           "bytes": len(texts_by_label[label].encode(
                               "utf-8")),
                           "lines": len(
                               texts_by_label[label].splitlines())}
                  for label in sorted(texts_by_label)},
        "checklist": sweep["checklist"],
        "probes": sweep["probes"],
        "adjudication_assists": sweep["assists"],
        "totals": sweep["totals"],
        "failures": sweep["failures"],
        "verdict": ("RERUN_COMPLETE" if not sweep["failures"]
                    else "HALT"),
    }
    RERUN_OUTPUT_PATH.write_text(
        json.dumps(output, indent=1, default=str), encoding="utf-8")
    print(f"wrote {RERUN_OUTPUT_PATH} "
          f"({sweep['totals']['calls']} calls, "
          f"${sweep['totals']['total_cost_usd']:.7f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
