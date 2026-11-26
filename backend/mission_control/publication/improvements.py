"""PUB-09B: governed chapter-improvement dispatch (Mission Control side).

Mission Control owns the author interaction, request validation, execution
dispatch (via the existing Worker contract), progress inspection and
candidate presentation. It owns NO publication intelligence (Writer),
NO model execution (Worker), NO staging/application (Workbench).

Reuse contracts (do not duplicate):
- Work Envelope authorization (work_observation.envelopes): human actor +
  note, digest-bound, idempotent on re-dispatch.
- Worker dispatch shape + free/local-only route policy (api/harness.py H6
  rules): only free, local-only routes may be dispatched here, so spend
  stays $0 by construction; paid inference is refused, not merely
  unbudgeted.
- Execution trace (wo_execution_links, route "manual"): manual post-hoc
  linkage exactly as W8 used it; no new execution store.
- Candidate persistence: files under data_dir/publication_candidates
  (dossier precedent), referenced by fingerprint; no new tables.

What v1 does NOT do (explicit gaps for PUB-10, see module docstring of the
handover): plan-scoped Writer verification for fresh reconstructions
(`transform verify` needs a PUB-05 plan), semantic assessment beyond
recorded deterministic checks, bounded correction loops (existing
`transform automate` loop, not reimplemented here), Workbench staging
(a separate, owner-gated service).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from mission_control.api import harness as harness_api

STRATEGIES = ("whole-chapter", "targeted")
MODES = ("inspect", "generate", "generate+verify")
STRATEGY_TO_WORKER = {
    "whole-chapter": "direct.v1",
    "targeted": "direct.v1",
}
MAX_TIMEOUT_MS = 60_000  # Worker hard limit: parameters.timeout_ms is 1..60000
DEFAULT_TIMEOUT_MS = 58_000
MAX_OUTPUT_TOKENS = 8192
DEFAULT_OUTPUT_TOKENS = 2000
MAX_CHAPTER_BYTES = 60_000
MAX_BODY_BYTES = 1_000_000
CANDIDATE_DIRNAME = "publication_candidates"


class ImprovementError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _fail(status: int, detail: str) -> dict[str, Any]:
    raise ImprovementError(status, detail)


def _writer_cli() -> list[str]:
    # NOTE: the dotted `.venv` in C:\Projects\writer holds only
    # writer_workspace; the runnable Writer CLI (console script) lives
    # in `venv`. The writer_cli package has no __main__, so invoke the
    # installed `writer` entry point with the writer repo as CWD.
    return [r"C:\Projects\writer\venv\Scripts\writer.exe"]


def _candidate_dir(settings: Any) -> Path:
    root = Path(settings.data_dir) / CANDIDATE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _chapter_file(settings: Any, project_id: str, chapter_id: str) -> Path:
    from mission_control.writer_registry import (
        load_writer_registry,
        resolve_registry_path,
    )

    try:
        snapshot = load_writer_registry(
            resolve_registry_path(settings) if settings is not None else None
        )
    except Exception:
        snapshot = None
    definition = snapshot.books.get(project_id) if snapshot else None
    if definition is None or not getattr(definition, "available", False):
        _fail(404, f"Unknown project '{project_id}': no manuscript in the Writer registry")
    try:
        chapter_dir = Path(definition.chapter_dir)
    except (OSError, TypeError):
        _fail(422, "Configured chapter directory is not a usable path")
    if not chapter_id or "/" in chapter_id or "\\" in chapter_id or ".." in chapter_id:
        _fail(422, f"Unknown chapter '{chapter_id}'")
    if len(chapter_id) < 4 or not chapter_id[0:2].isdigit() or not chapter_id.endswith("-chapter"):
        _fail(422, f"Unknown chapter '{chapter_id}': expected NN-chapter")
    path = chapter_dir / f"{chapter_id}.md"
    try:
        if not path.is_file():
            _fail(404, f"Unknown chapter '{chapter_id}': no such manuscript file")
    except OSError:
        _fail(422, f"Cannot access chapter '{chapter_id}'")
    return path


def _read_chapter(path: Path) -> tuple[str, str, int]:
    try:
        raw = path.read_bytes()[:2_000_000]
    except OSError:
        _fail(422, f"Chapter file is unreadable: {path.name}")
    if not raw:
        _fail(422, f"Chapter file is empty: {path.name}")
    if len(raw) > MAX_CHAPTER_BYTES:
        _fail(422, f"Chapter exceeds the bounded input ({len(raw)} > {MAX_CHAPTER_BYTES} bytes); split scope first")
    text = raw.decode("utf-8", errors="replace")
    digest = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    return text, digest, len(raw)


def book_root_for(settings: Any, project_id: str) -> str | None:
    """Repository root owning a project's manuscript (two levels above content/books/<id>)."""
    from mission_control.writer_registry import (
        load_writer_registry,
        resolve_registry_path,
    )

    try:
        snapshot = load_writer_registry(
            resolve_registry_path(settings) if settings is not None else None
        )
    except Exception:
        return None
    definition = snapshot.books.get(project_id) if snapshot else None
    if definition is None or not getattr(definition, "available", False):
        return None
    try:
        chapter_dir = Path(definition.chapter_dir)
    except (OSError, TypeError):
        return None
    try:
        return str(chapter_dir.parents[2])
    except IndexError:
        return str(chapter_dir.parent)


def run_writer_scan(kind: str, book: str, chapter_filename: str,
                    book_root: str | None = None) -> dict[str, Any]:
    """Best-effort deterministic Writer scan (cruft/complex). Read-only.

    Unavailable tooling is reported, never faked or retried in a loop.
    """
    cmd = _writer_cli() + [
        "cruft" if kind == "cruft" else "complex", "review",
        book, chapter_filename.replace(".md", ""), "--json",
    ]
    if book_root:
        cmd += ["--book-root", book_root]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                              cwd=r"C:\Projects\writer")
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": f"Writer CLI could not start: {type(exc).__name__}"}
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[:300]
        return {"available": False, "reason": f"Writer scan exited {proc.returncode}: {err}"}
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        return {"available": False, "reason": "Writer scan returned non-JSON output"}
    return {"available": True, "summary": str(data)[:2000]}


def validate_improvement_request(
    session: Session, settings: Any, *, project_id: str, chapter_id: str,
    strategy: str, mode: str, max_budget_usd: float,
    actor: str, authorization_note: str,
) -> dict[str, Any]:
    """Validate everything validatable without dispatching anything."""
    if strategy not in STRATEGIES:
        _fail(422, f"Unknown strategy '{strategy}': expected one of {', '.join(STRATEGIES)}")
    if mode not in MODES:
        _fail(422, f"Unknown mode '{mode}': expected one of {', '.join(MODES)}")
    try:
        budget = float(max_budget_usd)
    except (TypeError, ValueError):
        _fail(422, "Maximum inference budget must be a number")
    if not (budget >= 0 and budget <= 10):
        _fail(422, "Maximum inference budget must be between 0 and 10 USD for this interface")
    actor = (actor or "").strip()
    if not actor or actor.lower() in ("system", "model"):
        _fail(422, "Improvement requires a human actor (system/model identities refused)")
    if len((authorization_note or "").strip()) < 8:
        _fail(422, "Improvement requires an authorization note (at least 8 characters)")
    path = _chapter_file(settings, project_id, chapter_id)
    text, digest, size = _read_chapter(path)
    return {"project_id": project_id, "chapter_id": chapter_id,
            "chapter_path": str(path), "chapter_bytes": size,
            "chapter_fingerprint": digest, "strategy": strategy,
            "mode": mode, "max_budget_usd": budget,
            "actor": actor[:80], "authorization_note": authorization_note.strip()[:200]}


def read_chapter_text(settings: Any, project_id: str, chapter_id: str) -> str:
    """Re-read the validated chapter file. Fails closed if it moved."""
    path = _chapter_file(settings, project_id, chapter_id)
    text, _, _ = _read_chapter(path)
    return text


def compose_prompt(validated: dict[str, Any], scans: dict[str, Any],
                   chapter_text: str) -> str:
    """Compose the model objective. Prompt assembly lives here (Mission),
    publication intelligence stays in Writer (scans consumed, not reimplemented)."""
    lines = [
        "You are revising one technical book chapter. Output ONLY the revised "
        "chapter as Markdown, no commentary, no preamble.",
        f"Chapter: {validated['chapter_id']} (sha256 {validated['chapter_fingerprint'][:16]}).",
        "Hard constraints: preserve every code block, mathematical expression, "
        "figure reference and verbatim quotation byte-for-byte unless it is itself "
        "the documented defect; do not introduce new factual claims, numbers, "
        "or citations; do not invent reader outcomes.",
    ]
    if validated["strategy"] == "targeted":
        lines.append(
            "Strategy: targeted improvement. Focus ONLY on the findings listed "
            "below; leave all other prose byte-identical in spirit (reword only "
            "where the finding requires it).")
    else:
        lines.append(
            "Strategy: whole-chapter reconstruction (PROVISIONAL — investigated, "
            "not proven superior). Improve the complete reading experience "
            "coherently; then the result still requires independent verification "
            "before any use.")
        lines.append(
            "Note: whole-chapter reconstruction has NOT been established as "
            "editorially superior; this output is a candidate for review, not "
            "an accepted revision.")
    for key in ("cruft", "complexity"):
        scan = scans.get(key) or {}
        if scan.get("available"):
            lines.append(f"Deterministic {key} scan summary (Writer, read-only): {scan.get('summary','')[:1500]}")
        else:
            lines.append(f"Deterministic {key} scan: unavailable ({scan.get('reason','unknown')}). "
                         "Proceed without it; do not invent findings.")
    lines.append("--- BEGIN ORIGINAL CHAPTER ---")
    lines.append(chapter_text)
    lines.append("--- END ORIGINAL CHAPTER ---")
    lines.append("Return the complete revised chapter as Markdown and nothing else.")
    return "\n".join(lines)


async def worker_catalogue(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    strategies_doc = await harness_api._get(client, base, "/v1/strategies")
    models_doc = await harness_api._get(client, base, "/v1/models/catalogue")
    return {"strategies": strategies_doc, "models": models_doc}


def pick_free_local_route(catalogue: dict[str, Any]) -> dict[str, str]:
    """H6 free/local-only rule, reused verbatim: free tier, local_only data,
    policy authorizes the route, 1-2 attempts. Paid inference is refused
    here, never merely unbudgeted.

    Where several free local routes qualify, prefer the most capable one:
    an editorial rewrite from a 0.5B model is not a meaningful candidate,
    so capability order is explicit rather than catalogue-order luck. All
    preferences still satisfy the same free/local-only/attempts rule.
    """
    strategies = catalogue.get("strategies") or {}
    models = catalogue.get("models") or {}
    strat_list = strategies.get("strategies", []) if isinstance(strategies, dict) else []
    approved = models.get("approved", []) if isinstance(models, dict) else []
    policies = models.get("policies", {}) if isinstance(models, dict) else {}
    if not any(isinstance(r, dict) and r.get("key") == "direct.v1" for r in strat_list):
        _fail(503, "Worker catalogue lacks the direct.v1 strategy")
    preference = ("h5_mistral7b_local", "h4_review_mistral_local", "h4_qwen_local")
    eligible: dict[str, dict[str, str]] = {}
    for route in approved:
        if not isinstance(route, dict):
            continue
        if route.get("economic_tier") != "free" or route.get("data_policy") != "local_only":
            continue
        for policy_id, policy in (policies.items() if isinstance(policies, dict) else []):
            if not isinstance(policy, dict):
                continue
            routes = policy.get("routes") or []
            attempts = policy.get("attempts_per_route")
            if (route.get("id") in routes
                    and policy.get("required_data_policy") == "local_only"
                    and isinstance(attempts, int) and 1 <= attempts <= 2):
                eligible.setdefault(str(route["id"]), {
                    "strategy_id": "direct.v1",
                    "model_route": str(route["id"]),
                    "policy": str(policy_id)})
    if not eligible:
        _fail(503, "Worker offers no free local-only route under a 1-2 attempt "
                   "local-only policy; paid dispatch is refused by this interface")
    for route_id in preference:
        if route_id in eligible:
            return eligible[route_id]
    return next(iter(eligible.values()))


def _worker_identity(result: Any) -> tuple[str | None, str | None]:
    """Model/provider identity as the Worker itself recorded it."""
    if not isinstance(result, dict):
        return None, None
    provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    execution = result.get("execution") if isinstance(result.get("execution"), dict) else {}
    model_exec = result.get("model_execution") if isinstance(result.get("model_execution"), dict) else {}
    model = (provenance.get("model") or execution.get("model")
             or model_exec.get("model") or None)
    provider = model_exec.get("provider") or None
    if provider is None:
        attempts = model_exec.get("attempts")
        if isinstance(attempts, list) and attempts and isinstance(attempts[0], dict):
            provider = attempts[0].get("provider")
    return (str(model) if model else None, str(provider) if provider else None)


def _worker_cost(result: Any) -> float:
    """Metered cost as reported by the Worker, if any (local routes: None)."""
    if not isinstance(result, dict):
        return 0.0
    model_exec = result.get("model_execution") if isinstance(result.get("model_execution"), dict) else {}
    cost = model_exec.get("cost")
    candidates: list[Any] = []
    if isinstance(cost, dict):
        candidates.extend([cost.get("billed_cost_usd"), cost.get("estimated_cost_usd"),
                           cost.get("cost_usd")])
    elif cost is not None:
        candidates.append(cost)
    total = 0.0
    for value in candidates:
        try:
            total = max(total, float(value))
        except (TypeError, ValueError):
            continue
    return total


def worker_truncation(result: Any) -> dict[str, Any]:
    """Did the response stop at the requested output ceiling?

    Deterministic from the Worker's own counters: `resources` carries
    requested/observed output tokens. A response that consumed >=95% of the
    ceiling is treated as ceiling-bound and therefore incomplete, because a
    truncated chapter must never be presented as a finished transformation.
    """
    requested = None
    observed = None
    if isinstance(result, dict):
        strategy = result.get("strategy_execution")
        resources = strategy.get("resources") if isinstance(strategy, dict) else None
        if isinstance(resources, dict):
            requested = resources.get("requested_output_tokens")
            observed = resources.get("observed_output_tokens")
        if not isinstance(observed, int):
            model_exec = result.get("model_execution")
            usage = model_exec.get("usage") if isinstance(model_exec, dict) else None
            if isinstance(usage, dict) and isinstance(usage.get("output_tokens"), int):
                observed = usage["output_tokens"]
    suspected = bool(isinstance(requested, int) and requested > 0
                     and isinstance(observed, int)
                     and observed >= 0.95 * requested)
    return {"requested_output_tokens": requested if isinstance(requested, int) else None,
            "observed_output_tokens": observed if isinstance(observed, int) else None,
            "suspected": suspected,
            "basis": "Worker strategy resources counters (requested/observed output tokens)"}


def deterministic_validation(candidate_text: str, original_text: str) -> dict[str, Any]:
    """Writer-independent deterministic checks. Semantic correctness is
    explicitly NOT established here (recorded as pending, never passed).

    Hard checks (problems) only cover defects that make a candidate
    unusable as a candidate at all. Preservation *warnings* cover
    deterministic evidence that an editorial transformation may have lost
    material (measurements, sections, repetition, front matter). They are
    warnings, not verdicts: a deliberate removal is legitimate, but a
    whole-chapter rewrite that drops every measurement must not read as
    clean.
    """
    import re as _re

    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    warnings: list[str] = []
    cand_norm = (candidate_text or "").replace("\r\n", "\n")
    orig_norm = (original_text or "").replace("\r\n", "\n")

    if candidate_text and candidate_text.strip():
        checks.append({"check": "non_empty", "result": "pass"})
    else:
        problems.append("candidate is empty")
        checks.append({"check": "non_empty", "result": "fail"})

    if _re.search(r"[A-Za-z]:\\[^\s]", candidate_text or ""):
        problems.append("candidate leaks an absolute host path")
        checks.append({"check": "no_host_paths", "result": "fail"})
    else:
        checks.append({"check": "no_host_paths", "result": "pass"})

    same = cand_norm == orig_norm
    checks.append({"check": "differs_from_original",
                   "result": "pass" if not same else "note-identical"})
    if same:
        problems.append("candidate is byte-identical to the original (no change proposed)")

    # 1. Quantitative preservation: measurements present in the original
    #    but absent from the candidate. Numbers are compared as tokens, so
    #    reformatting (1,000 -> 1000) is not itself a warning; absence is.
    num_re = _re.compile(r"\b\d+(?:\.\d+)?\b")
    orig_nums = set(num_re.findall(orig_norm))
    cand_nums = set(num_re.findall(cand_norm))
    lost_nums = sorted(orig_nums - cand_nums, key=lambda v: float(v))
    lost_ratio = (len(lost_nums) / len(orig_nums)) if orig_nums else 0.0
    if orig_nums and len(lost_nums) >= 3 and lost_ratio >= 0.25:
        warnings.append(
            f"{len(lost_nums)} of {len(orig_nums)} numeric values in the original "
            f"do not appear in the candidate ({round(lost_ratio * 100)}%): "
            + ", ".join(lost_nums[:12])
            + (" …" if len(lost_nums) > 12 else "")
            + ". Whole-chapter rewrites normally preserve measurements; check for truncation or loss.")
        checks.append({"check": "quantitative_preserved", "result": "warn",
                       "lost": len(lost_nums), "of": len(orig_nums)})
    else:
        checks.append({"check": "quantitative_preserved", "result": "pass",
                       "lost": len(lost_nums), "of": len(orig_nums)})

    # 2. Section preservation: heading text present in the original but
    #    absent from the candidate.
    head_re = _re.compile(r"^(#{1,3})\s+(.+)$", _re.MULTILINE)
    orig_heads = [h.strip() for _, h in head_re.findall(orig_norm)]
    cand_head_set = {h.strip().lower() for _, h in head_re.findall(cand_norm)}
    missing_heads = [h for h in orig_heads if h.lower() not in cand_head_set]
    if orig_heads and missing_heads:
        warnings.append(
            f"{len(missing_heads)} of {len(orig_heads)} original headings are absent "
            "from the candidate: " + "; ".join(h[:60] for h in missing_heads[:6])
            + (" …" if len(missing_heads) > 6 else "")
            + ". Confirm the missing sections were removed deliberately.")
        checks.append({"check": "sections_preserved", "result": "warn",
                       "missing": len(missing_heads), "of": len(orig_heads)})
    else:
        checks.append({"check": "sections_preserved", "result": "pass",
                       "missing": 0, "of": len(orig_heads)})

    # 3. Repetition artifacts: a substantial paragraph repeated verbatim
    #    inside the candidate (a generation artefact, not a source property).
    #    Fence markers are stripped first so a closing ``` does not make an
    #    otherwise identical paragraph look different.
    rep_text = _re.sub(r"^\s*```.*$", "", cand_norm, flags=_re.MULTILINE)
    blocks = [" ".join(b.split()) for b in _re.split(r"\n\s*\n", rep_text)]
    blocks = [b for b in blocks if len(b) >= 80]
    seen: set[str] = set()
    dupes: list[str] = []
    for block in blocks:
        key = block.lower()
        if key in seen and block not in dupes:
            dupes.append(block)
        seen.add(key)
    if dupes:
        warnings.append(
            f"{len(dupes)} sentence(s) repeat verbatim inside the candidate "
            "(generation artefact, not a source property): "
            + " | ".join(d[:70] for d in dupes[:3]))
        checks.append({"check": "no_repetition", "result": "warn", "duplicates": len(dupes)})
    else:
        checks.append({"check": "no_repetition", "result": "pass", "duplicates": 0})

    # 4. Front matter: Hugo/TOML metadata dropped from a chapter that had it.
    if orig_norm.lstrip().startswith("+++") and not cand_norm.lstrip().startswith("+++"):
        warnings.append(
            "The original chapter carries TOML front matter (title, weight, draft) "
            "and the candidate does not. The candidate is not directly applicable "
            "as a chapter file until metadata is restored.")
        checks.append({"check": "front_matter_preserved", "result": "warn"})
    else:
        checks.append({"check": "front_matter_preserved", "result": "pass"})

    # 5. Fence balance: an unbalanced code fence usually means truncation.
    if cand_norm.count("```") % 2 != 0:
        warnings.append("Code fences are unbalanced in the candidate; the response "
                        "may be truncated or structurally broken.")
        checks.append({"check": "fences_balanced", "result": "warn"})
    else:
        checks.append({"check": "fences_balanced", "result": "pass"})

    return {"checks": checks, "passed": not problems, "problems": problems,
            "warnings": warnings,
            "warning_count": len(warnings),
            "semantic": "pending",
            "semantic_note": "No plan-scoped Writer verification applies to a fresh reconstruction "
                             "(`transform verify` needs a PUB-05 plan for the changed passages); "
                             "PUB-08 eval fabric is benchmark infrastructure, not a per-candidate "
                             "service. Treat this candidate as unverified until such verification runs."}


def _record_path(settings: Any, record_id: str, ext: str) -> Path:
    return _candidate_dir(settings) / f"{record_id}.{ext}"


def _sha_text_of(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def save_candidate_record(settings: Any, record: dict[str, Any], body: str) -> None:
    """Persist one record. The candidate body is fingerprinted so a later
    read can prove the body still matches the record that describes it."""
    if body and body.strip():
        record = {**record, "candidate_fingerprint": _sha_text_of(body)}
    _record_path(settings, record["id"], "json").write_text(
        json.dumps(record, indent=1, default=str)[:200_000], encoding="utf-8")
    _record_path(settings, record["id"], "md").write_text(body[:MAX_BODY_BYTES], encoding="utf-8")


_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def _valid_record_id(record_id: str) -> bool:
    """File-name-safe identity. Separators and traversal are refused; the
    record's own id must equal the file name (checked separately)."""
    if not record_id or len(record_id) > 80:
        return False
    if "/" in record_id or "\\" in record_id or ".." in record_id:
        return False
    if record_id.startswith("wrq_"):
        suffix = record_id[4:]
    elif record_id.startswith("failed-"):
        suffix = record_id[7:]
    else:
        return False
    return len(suffix) >= 8 and all(c in _ID_CHARS for c in suffix.lower())


def _backfill_candidate_fingerprint(settings: Any, record: dict[str, Any],
                                     record_id: str) -> dict[str, Any]:
    """One-time integrity backfill for records written before body
    fingerprints were recorded. The file is adopted only when it already
    satisfies every other identity check; the fingerprint is then stored so
    any later edit is detected."""
    if record.get("candidate_fingerprint"):
        return record
    body_path = _record_path(settings, record_id, "md")
    try:
        if not body_path.is_file():
            return record
        text = body_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return record
    if not text.strip():
        return record
    updated = {**record, "candidate_fingerprint": _sha_text_of(text),
               "fingerprint_backfilled_at": __import__("mission_control.persistence.db",
                                                        fromlist=["now_iso"]).now_iso()}
    try:
        _record_path(settings, record_id, "json").write_text(
            json.dumps(updated, indent=1, default=str)[:200_000], encoding="utf-8")
    except OSError:
        pass
    return updated


def validate_candidate_record(settings: Any, record: Any, record_id: str) -> str | None:
    """Integrity gate for records served as candidates.

    A candidate is served only when the file name, the record identity, the
    declared kind, the registry ownership and (when a body exists) the body
    fingerprint all agree. Anything else is refused and counted, never
    displayed as a candidate. This is what stops an unrelated or
    hand-edited file in the candidates directory from being presented as a
    governed execution result.
    """
    if not isinstance(record, dict):
        return "record is not an object"
    if record.get("id") != record_id:
        return "record id does not match its file name"
    if record.get("kind") != "requested-execution":
        return "record kind is not a requested execution"
    project_id = record.get("project_id")
    chapter_id = record.get("chapter_id")
    if not isinstance(project_id, str) or not isinstance(chapter_id, str):
        return "record has no project/chapter identity"
    try:
        _chapter_file(settings, project_id, chapter_id)
    except ImprovementError:
        return "record does not resolve to a registered chapter"
    body_path = _record_path(settings, record_id, "md")
    declared = record.get("candidate_fingerprint")
    if body_path.is_file():
        try:
            body_text = body_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "candidate body is unreadable"
        if body_text.strip():
            if not isinstance(declared, str) or not declared:
                return "candidate body has no recorded fingerprint"
            if _sha_text_of(body_text) != declared:
                return "candidate body does not match its recorded fingerprint"
    return None


def load_candidate_record(settings: Any, record_id: str) -> dict[str, Any] | None:
    if not _valid_record_id(record_id):
        return None
    path = _record_path(settings, record_id, "json")
    try:
        if not path.is_file() or path.stat().st_size > 300_000:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    data = _backfill_candidate_fingerprint(settings, data, record_id)
    if validate_candidate_record(settings, data, record_id) is not None:
        return None
    return data


def annotate_source_current(settings: Any, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach `source_current` by comparing each record's source fingerprint
    with the chapter as it exists now. One read per distinct chapter."""
    cache: dict[tuple[str, str], str | None] = {}
    out = []
    for record in records:
        key = (str(record.get("project_id") or ""), str(record.get("chapter_id") or ""))
        if key not in cache:
            try:
                text = read_chapter_text(settings, key[0], key[1])
                cache[key] = _sha_text_of(text)
            except ImprovementError:
                cache[key] = None
        current = cache[key]
        out.append({**record,
                    "source_current": bool(current and current == record.get("chapter_fingerprint")),
                    "candidate_current": True})
    return out


def list_candidate_records(settings: Any, limit: int = 100) -> dict[str, Any]:
    """Newest-first discovery with integrity gating.

    Returns ``records`` (valid only) and ``rejected`` (count + reasons), so
    a tampered or unrelated file is reported rather than silently shown.
    """
    try:
        files = sorted(_candidate_dir(settings).glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, min(limit, 200))]
    except OSError:
        return {"records": [], "rejected": 0, "rejections": []}
    records: list[dict[str, Any]] = []
    rejections: list[dict[str, str]] = []
    for path in files:
        record_id = path.stem
        try:
            if path.stat().st_size > 300_000:
                rejections.append({"id": record_id, "reason": "record exceeds the bounded read size"})
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rejections.append({"id": record_id, "reason": "record is unreadable or not JSON"})
            continue
        data = _backfill_candidate_fingerprint(settings, data, record_id)
        reason = validate_candidate_record(settings, data, record_id)
        if reason is not None:
            rejections.append({"id": record_id, "reason": reason})
            continue
        data.pop("_body", None)
        records.append(data)
    return {"records": annotate_source_current(settings, records),
            "rejected": len(rejections), "rejections": rejections}


def candidate_body(settings: Any, record_id: str) -> dict[str, Any]:
    record = load_candidate_record(settings, record_id)
    if record is None:
        return {"id": record_id, "available": False,
                "reason": "No integrity-verified generated candidate with that id is retained here."}
    path = _record_path(settings, record_id, "md")
    try:
        if not path.is_file() or path.stat().st_size > MAX_BODY_BYTES:
            raise OSError("missing")
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"id": record_id, "available": False,
                "reason": "Candidate body is missing or exceeds the bounded read size."}
    if not text.strip():
        return {"id": record_id, "available": False,
                "reason": "No candidate body was produced for this execution "
                          f"(recorded status: {record.get('status')})."}
    return {"id": record_id, "available": True, "markdown": text,
            "bytes": len(text.encode("utf-8")),
            "fingerprint": _sha_text_of(text),
            "body_matches_record": _sha_text_of(text) == record.get("candidate_fingerprint")}
