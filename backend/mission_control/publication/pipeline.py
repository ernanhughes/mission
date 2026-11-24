"""Book production pipeline projection (MC-BOOK-PIPELINE-01, M1).

Read-only foundation for the Mission Control production dashboard.

Ownership rule (architectural decision, M1):
Mission Control owns the dashboard and coordination state. Writer owns the
analysis and its artifacts. Neither system maintains a second, competing
definition of whether a chapter operation completed: every cell below traces
to a real Writer artifact plus an exact digest comparison, or to an explicit
absence of evidence.

Scope (M1 only):
- a small versioned stage registry (no plugin framework, no DB tables);
- per-chapter read-only artifact projection for verified digest-bound stages;
- deterministic chapter -> book aggregation with explicit dimensions;
- no execution, no writes to manuscripts, Writer artifacts, publication
  state, approvals, or settings.

Digest contracts (authoritative per stage, never interchangeable):
- ``mri``: ``snapshot_hash`` = sha256 of chapter text as read by Python
  ``Path.read_text(encoding="utf-8")`` (universal newlines), hex, no prefix.
  Replicates Writer's own reuse check
  (``writer_cli/commands/mri.py::_chapter_outputs_fresh``).
- ``editing``: ``source_fingerprint`` = sha256 of raw file bytes, hex.
  Replicates ``editing/engine.py::_sha256(raw)``.
- ``validation``: ``source_digest`` = Writer's frontmatter-stripped digest
  with ``sha256:`` prefix. Replicates
  ``publication/fingerprint.py::writer_source_digest`` (same algorithm the
  publishing workbench uses).
- Book-level ``manuscript-v1`` fingerprint (CRLF->LF manifest) is reported
  for context and is NOT compared against per-stage digests.

Freshness in M1 covers the source-text binding only. Metadata canonical
hashes, prompt/alignment versions, and model versions pinned in stored
provenance are recorded but not recomputed (recomputing them requires
running Writer); this limitation is stated on every MRI cell.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mission_control.publication.fingerprint import (
    fingerprint_manuscript,
    writer_source_digest,
)
from mission_control.writer_registry import (
    WriterBookDefinition,
    load_writer_registry,
    resolve_registry_path,
)

PIPELINE_REGISTRY_VERSION = "pipeline-stages-v1"

#: Writer's own convention (writer_cli/commands/mri.py): these stems are
#: never chapters even when they match the chapter glob.
NON_CHAPTER_STEMS = frozenset({"_index", "index"})

#: Fallback codes that are the normal, expected behaviour of a deterministic
#: MRI run (no provider available by policy, so the engine uses its
#: deterministic section observer, reducer fallback, and reference-section
#: handling). Presence of ONLY these codes is expected deterministic mode,
#: not an execution anomaly. Anything else is a genuine warning.
EXPECTED_DETERMINISTIC_WARNINGS = frozenset(
    {
        "chapter_reducer_fallback",
        "deterministic_section_observer",
        "reference_section",
    }
)

#: Refuse to parse stored artifacts larger than this (read-only guard).
MAX_ARTIFACT_BYTES = 50_000_000

#: Explicit override for the Writer editing summary store (tests, pilot).
EDITING_SUMMARY_ENV = "MISSION_CONTROL_WRITER_EDITING_SUMMARY"

#: In-process parsed-document cache (M2). Keys are
#: (path, mtime_ns, size): any Writer rewrite changes mtime (ns resolution)
#: or size, so a hit always means byte-identical content. Only successful
#: parses are cached; errors are re-read every time. Process-local only:
#: a server restart starts cold, never stale. FIFO-capped.
_DOC_CACHE: dict[tuple[str, int, int], Any] = {}
_DOC_CACHE_MAX = 2000


def _cache_key(path: Path) -> tuple[str, int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path), int(stat.st_mtime_ns), int(stat.st_size))


def _load_json_cached(path: Path) -> tuple[Any | None, str | None]:
    """Parse-once-per-content JSON loader with mtime+size invalidation.

    Same read guard as :func:`_load_json_artifact`; a cache hit is only
    possible for byte-identical content, so invalidation needs no TTL.
    """
    key = _cache_key(path)
    if key is not None and key in _DOC_CACHE:
        return _DOC_CACHE[key], None
    doc, error = _load_json_artifact(path)
    if error is None and key is not None:
        if len(_DOC_CACHE) >= _DOC_CACHE_MAX:
            _DOC_CACHE.pop(next(iter(_DOC_CACHE)))
        _DOC_CACHE[key] = doc
    return doc, error


# ---------------------------------------------------------------------------
# Stage registry
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StageDefinition:
    stage_id: str
    name: str
    description: str
    owner: str
    scope: str
    applicability: str
    freshness_method: str
    prerequisites: str
    presentation_order: int
    availability: str  # implemented | planned | unavailable
    availability_reason: str
    # M4A execution class: automatic = allowlisted for automatic maintenance
    # (verified deterministic, local-only, no manuscript writes); governed =
    # needs explicit per-run authorization; unavailable = no provider.
    execution_class: str = "governed"
    execution_note: str = ""
    ui_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "scope": self.scope,
            "applicability": self.applicability,
            "freshness_method": self.freshness_method,
            "prerequisites": self.prerequisites,
            "presentation_order": self.presentation_order,
            "availability": self.availability,
            "availability_reason": self.availability_reason,
            "execution_class": self.execution_class,
            "execution_note": self.execution_note,
            "ui_actions": list(self.ui_actions),
        }


STAGE_DEFINITIONS: list[StageDefinition] = [
    StageDefinition(
        stage_id="metadata",
        name="Metadata",
        description=(
            "Chapter metadata declarations (metadata/*.yaml). M1 checks "
            "existence and YAML validity only; the contract outcome is not "
            "evaluated without running Writer."
        ),
        owner="writer",
        scope="chapter",
        applicability=(
            "Applies when the Writer registry configures a metadata "
            "directory for the book. Books without one report "
            "not_applicable."
        ),
        freshness_method=(
            "No source binding is evaluated in M1, so freshness is always "
            "unknown when a declaration exists. Absence is missing, never "
            "current."
        ),
        prerequisites="None for the M1 existence check.",
        presentation_order=10,
        availability="implemented",
        availability_reason="Declaration files and YAML validity are verifiable read-only.",
        execution_class="governed",
        execution_note=(
            "Not automatic: existence checks alone cannot verify analysis "
            "freshness, and contract evaluation needs a verified stored "
            "outcome contract first."
        ),
        ui_actions=["open_writer_metadata", "refresh_analysis_m3"],
    ),
    StageDefinition(
        stage_id="mri",
        name="MRI",
        description=(
            "Chapter observation and technical alignment reports "
            "(.writer/mri/<project>/<stem>.mri.json)."
        ),
        owner="writer",
        scope="chapter",
        applicability="Applies to every applicable chapter (chapter text only).",
        freshness_method=(
            "Exact comparison of stored snapshot_hash against sha256 of the "
            "live chapter text (Writer read_text semantics). Source-text "
            "binding only; metadata canonical hashes and prompt/alignment "
            "versions are recorded, not recomputed, in M1."
        ),
        prerequisites="None for observation. Full alignment additionally "
        "needs a valid technical contract (evaluated by Writer, not by M1).",
        presentation_order=20,
        availability="implemented",
        availability_reason="Stored reports carry snapshot_hash; recomputation is exact.",
        execution_class="automatic",
        execution_note=(
            "Allowlisted for automatic maintenance (M4A): verified "
            "deterministic operation, local-only, writes Writer-owned "
            "reports, never modifies manuscripts."
        ),
        ui_actions=["open_writer_mri", "rerun_deterministic_mri_m3", "compare_reports_m5"],
    ),
    StageDefinition(
        stage_id="patterns",
        name="Patterns",
        description=(
            "Deterministic prose-pattern observation "
            "(POST /api/artifacts/observe). No stored artifacts exist, so "
            "M1 cannot project it."
        ),
        owner="writer",
        scope="chapter",
        applicability="Chapter text only, when executed.",
        freshness_method="Not projected in M1 (no stored evidence to compare).",
        prerequisites="None.",
        presentation_order=30,
        availability="planned",
        availability_reason=(
            "HTTP-only response with no stored artifact; requires M3 "
            "execution with result persistence before projection."
        ),
        execution_class="governed",
        execution_note=(
            "Not automatic: no stored artifact exists, so Mission Control "
            "cannot independently verify the outcome yet."
        ),
        ui_actions=["run_patterns_m3"],
    ),
    StageDefinition(
        stage_id="strengthening",
        name="Strengthening",
        description=(
            "Controlled improvement experiments and campaigns. Model-backed "
            "and gated; not projected in M1."
        ),
        owner="writer",
        scope="chapter",
        applicability="Requires a strengthening: declaration section plus lexicon.",
        freshness_method="Not projected in M1.",
        prerequisites="Metadata declaration with strengthening contract; lexicon.",
        presentation_order=40,
        availability="planned",
        availability_reason="Model spend and approval gates; M5 work.",
        execution_class="governed",
        execution_note="Model-backed and editorial: never automatic.",
        ui_actions=["open_writer_campaign", "request_strengthening_m5"],
    ),
    StageDefinition(
        stage_id="editing",
        name="Editing",
        description=(
            "Read-only readability audits (Writer editing summary/index "
            "stores). Writer writes report artifacts only; manuscripts are "
            "never touched."
        ),
        owner="writer",
        scope="chapter",
        applicability="Applies to every applicable chapter (markdown sources).",
        freshness_method=(
            "Exact comparison of the stored per-chapter source_fingerprint "
            "against sha256 of the live file bytes."
        ),
        prerequisites="None.",
        presentation_order=50,
        availability="implemented",
        availability_reason="Summary/index stores carry per-chapter sha256 fingerprints.",
        execution_class="governed",
        execution_note=(
            "Not automatic: audits are author-facing review signals with "
            "human cadence semantics; auto-running them is not verified."
        ),
        ui_actions=["open_writer_editing", "compare_reports_m5"],
    ),
    StageDefinition(
        stage_id="validation",
        name="Validation",
        description=("Stored Writer validation runs (.writer/validation/chapters/*.json)."),
        owner="writer",
        scope="chapter",
        applicability=(
            "Applies when the Writer registry enables validation for the "
            "book. Books without it report not_applicable."
        ),
        freshness_method=(
            "Exact comparison of the stored source_digest against "
            "writer_source_digest recomputed from the live chapter "
            "(frontmatter-stripped, sha256: prefix)."
        ),
        prerequisites="Validation contract in the Writer registry.",
        presentation_order=60,
        availability="implemented",
        availability_reason=(
            "Stored runs carry machine_status and source_digest; the digest "
            "algorithm is already replicated in Mission Control."
        ),
        execution_class="governed",
        execution_note=(
            "Not automatic: validation profiles may invoke model-backed "
            "runtimes and human-gated checks; not verified spend-free."
        ),
        ui_actions=["run_writer_validate_m3"],
    ),
    StageDefinition(
        stage_id="graph",
        name="Graph",
        description=(
            "Technical/cognitive graph artifacts. Provider wiring is "
            "unverified per book; not projected in M1."
        ),
        owner="writer",
        scope="chapter",
        applicability="Only where a graph provider is verified for the book.",
        freshness_method="Not projected in M1.",
        prerequisites="Verified graph provider and path resolution (M6).",
        presentation_order=70,
        availability="unavailable",
        availability_reason=(
            "Chapter semantic graph path resolution and cognitive graph "
            "population are unverified per book. Never report as available "
            "until a per-book verification passes."
        ),
        execution_class="unavailable",
        execution_note="No verified provider; never scheduled.",
        ui_actions=[],
    ),
]

STAGES_BY_ID = {stage.stage_id: stage for stage in STAGE_DEFINITIONS}
IMPLEMENTED_STAGE_IDS = [
    stage.stage_id for stage in STAGE_DEFINITIONS if stage.availability == "implemented"
]


def list_stages() -> dict[str, Any]:
    """Versioned registry payload (no book I/O)."""
    return {
        "registry_version": PIPELINE_REGISTRY_VERSION,
        "stages": [
            stage.to_dict()
            for stage in sorted(STAGE_DEFINITIONS, key=lambda s: s.presentation_order)
        ],
    }


# ---------------------------------------------------------------------------
# Chapter discovery (mirrors Writer's own chapter rules)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ChapterRef:
    chapter_id: str
    filename: str
    path: Path


def discover_chapters(definition: WriterBookDefinition) -> tuple[list[ChapterRef], dict[str, Any]]:
    """List applicable chapters: registry pattern minus Writer exclusions.

    Mirrors Writer's CLI discovery (``writer_cli/commands/mri.py``):
    glob pattern, ``exclude_prefixes`` from the registry entry, and
    ``_NON_CHAPTER_STEMS`` (``_index``/``index`` are never chapters).
    """
    info: dict[str, Any] = {
        "chapter_dir": str(definition.chapter_dir),
        "pattern": definition.chapter_pattern,
        "exclude_prefixes": list(definition.exclude_prefixes),
    }
    try:
        if not definition.chapter_dir.is_dir():
            info["error"] = f"Chapter directory is not available: {definition.chapter_dir}."
            return [], info
        entries = sorted(
            (p for p in definition.chapter_dir.iterdir() if p.is_file()),
            key=lambda p: p.name,
        )
    except OSError as exc:
        info["error"] = f"Chapter directory cannot be listed: {exc}."
        return [], info
    chapters: list[ChapterRef] = []
    skipped: list[str] = []
    for path in entries:
        if not fnmatch.fnmatch(path.name, definition.chapter_pattern):
            continue
        if path.stem in NON_CHAPTER_STEMS:
            skipped.append(f"{path.name} (non-chapter stem)")
            continue
        lowered = path.name.lower()
        if any(
            lowered.startswith(str(prefix).lower())
            for prefix in definition.exclude_prefixes
            if str(prefix)
        ):
            skipped.append(f"{path.name} (exclude_prefixes)")
            continue
        chapters.append(ChapterRef(chapter_id=path.stem, filename=path.name, path=path))
    info["applicable_count"] = len(chapters)
    info["skipped"] = skipped
    return chapters, info


# ---------------------------------------------------------------------------
# Digest helpers (exact Writer replicas; see module docstring)
# ---------------------------------------------------------------------------


def mri_snapshot_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_mri_snapshot(chapter_path: Path) -> tuple[str | None, str | None]:
    """sha256 of chapter text under Writer read_text semantics."""
    try:
        text = chapter_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"Chapter is unreadable: {exc}."
    return mri_snapshot_of_text(text), None


def read_raw_sha256(chapter_path: Path) -> tuple[str | None, str | None]:
    try:
        raw = chapter_path.read_bytes()
    except OSError as exc:
        return None, f"Chapter is unreadable: {exc}."
    return hashlib.sha256(raw).hexdigest(), None


def _mtime_iso(path: Path) -> str:
    try:
        return (
            datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except OSError:
        return ""


def _load_json_artifact(path: Path) -> tuple[Any | None, str | None]:
    try:
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            return None, f"Artifact exceeds the {MAX_ARTIFACT_BYTES}-byte read guard."
    except OSError as exc:
        return None, f"Artifact cannot be statted: {exc}."
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, f"Artifact is not readable JSON: {exc}."


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------


def _base_cell(
    stage_id: str,
    project_id: str,
    chapter: ChapterRef,
    *,
    applicable: bool = True,
    not_applicable_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "project_id": project_id,
        "chapter_id": chapter.chapter_id,
        "chapter_path": str(chapter.path),
        "applicable": applicable,
        "not_applicable_reason": not_applicable_reason,
        "result": "unknown",
        "freshness": "unknown",
        "has_evidence": False,
        "artifact_ref": "",
        "stored_digest": None,
        "live_digest": None,
        "digest_match": None,
        "digest_algorithm": None,
        "observed_at": "",
        "executed_at": "",
        "provider": "writer",
        "stage_version": None,
        "diagnostics": "",
        "detail": {},
    }


def read_metadata_cell(
    project_id: str, chapter: ChapterRef, metadata_dir: Path | None
) -> dict[str, Any]:
    cell = _base_cell("metadata", project_id, chapter)
    cell["digest_algorithm"] = "none-in-m1 (no source binding evaluated)"
    if metadata_dir is None:
        cell["applicable"] = False
        cell["not_applicable_reason"] = "No metadata directory is configured for this book."
        cell["result"] = "unavailable"
        return cell
    declaration = metadata_dir / f"{chapter.chapter_id}.yaml"
    if not declaration.is_file():
        cell["diagnostics"] = (
            f"No declaration at {declaration}: no qualifying evidence. "
            "Add a declaration before contract evaluation."
        )
        return cell
    cell["has_evidence"] = True
    cell["artifact_ref"] = str(declaration)
    cell["observed_at"] = _mtime_iso(declaration)
    key = _cache_key(declaration)
    if key is not None and key in _DOC_CACHE:
        payload = _DOC_CACHE[key]
    else:
        try:
            import yaml as _yaml

            payload = _yaml.safe_load(declaration.read_text(encoding="utf-8"))
        except Exception as exc:
            cell["result"] = "failed"
            cell["diagnostics"] = f"Declaration is not valid YAML: {exc}."
            cell["detail"] = {"declaration": str(declaration)}
            return cell
        if key is not None:
            if len(_DOC_CACHE) >= _DOC_CACHE_MAX:
                _DOC_CACHE.pop(next(iter(_DOC_CACHE)))
            _DOC_CACHE[key] = payload
    if not isinstance(payload, dict):
        cell["result"] = "failed"
        cell["diagnostics"] = "Declaration parses but is not a YAML mapping."
        cell["detail"] = {"declaration": str(declaration)}
        return cell
    cell["diagnostics"] = (
        "Declaration is present and parses; the contract outcome was not "
        "evaluated in M1 (read-only, no Writer execution). Freshness is "
        "unknown because no source binding is evaluated in M1."
    )
    cell["detail"] = {
        "declaration": str(declaration),
        "top_level_keys": sorted(str(k) for k in payload.keys())[:20],
    }
    return cell


def _mri_reports_dir(repo_roots: list[Path], project_id: str) -> tuple[Path | None, list[str]]:
    checked: list[str] = []
    for root in repo_roots:
        candidate = root / ".writer" / "mri" / project_id
        checked.append(str(candidate))
        try:
            if candidate.is_dir():
                return candidate, checked
        except OSError:
            continue
    return None, checked


def read_mri_cell(
    project_id: str,
    chapter: ChapterRef,
    reports_dir: Path | None,
    checked: list[str],
) -> dict[str, Any]:
    cell = _base_cell("mri", project_id, chapter)
    cell["digest_algorithm"] = "snapshot:sha256-utf8-text (Writer read_text semantics)"
    # The live digest is always computed when the chapter is readable, even
    # without a stored report: automation decisions need the current input
    # identity to detect changes and to debounce mid-save edits.
    live, read_error = read_mri_snapshot(chapter.path)
    cell["live_digest"] = live
    if reports_dir is None:
        cell["diagnostics"] = (
            "No MRI report directory observed at "
            + ("; ".join(checked) if checked else "(no repository roots)")
            + ". No qualifying evidence."
            if live is not None
            else (read_error or "Chapter is unreadable.")
        )
        return cell
    report_path = reports_dir / f"{chapter.chapter_id}.mri.json"
    if not report_path.is_file():
        cell["diagnostics"] = (
            f"No MRI report at {report_path}: chapter not covered until evaluated."
            if live is not None
            else (read_error or "Chapter is unreadable.")
        )
        cell["detail"] = {"checked": checked}
        return cell
    report, error = _load_json_cached(report_path)
    cell["has_evidence"] = True
    cell["artifact_ref"] = str(report_path)
    cell["observed_at"] = _mtime_iso(report_path)
    if error is not None or not isinstance(report, dict):
        cell["diagnostics"] = f"MRI report exists but {error or 'is not a JSON object'}."
        return cell
    stored = report.get("snapshot_hash")
    provenance = report.get("provenance") if isinstance(report.get("provenance"), dict) else {}
    cell["executed_at"] = str(provenance.get("generated_at") or "")
    cell["stored_digest"] = str(stored) if stored else None
    if not stored:
        cell["diagnostics"] = (
            "MRI report has no snapshot_hash: present without verifiable "
            "binding, so freshness is unknown."
        )
        cell["detail"] = {"provenance_keys": sorted(provenance.keys())}
        return cell
    if live is None:
        cell["diagnostics"] = read_error or "Chapter is unreadable."
        return cell
    cell["digest_match"] = stored == live
    alignment = report.get("alignment") if isinstance(report.get("alignment"), dict) else {}
    stage_status = (
        provenance.get("stage_status") if isinstance(provenance.get("stage_status"), dict) else {}
    )
    finding_counts = {
        "declared_not_observed": len(alignment.get("declared_not_observed") or [])
        if isinstance(alignment.get("declared_not_observed"), list)
        else 0,
        "observed_not_declared": len(alignment.get("observed_not_declared") or [])
        if isinstance(alignment.get("observed_not_declared"), list)
        else 0,
        "uncertainty_flags": len(alignment.get("uncertainty_flags") or [])
        if isinstance(alignment.get("uncertainty_flags"), list)
        else 0,
    }
    statuses = [str(v).lower() for v in stage_status.values()]
    observer_error = provenance.get("observer_error")
    # "skipped" is a policy-disabled stage (e.g. the quality judge is
    # explicitly "none"), not a failure and not missing analysis. It is
    # neutral: a run whose stages all pass (or are skipped by policy)
    # completed its analysis. At least one pass/ok is required so a fully
    # skipped report stays pending rather than passed.
    ok_states = {"pass", "ok", "skipped"}
    if observer_error or any(s in ("fail", "failed", "error") for s in statuses):
        cell["result"] = "failed"
    elif (
        statuses
        and all(s in ok_states for s in statuses)
        and any(s in ("pass", "ok") for s in statuses)
    ):
        cell["result"] = "passed"
    else:
        cell["result"] = "pending"
    total_findings = sum(finding_counts.values())
    if cell["digest_match"]:
        cell["freshness"] = "current"
        state_note = "matches the live chapter exactly"
    else:
        cell["freshness"] = "stale"
        state_note = "no longer matches the live chapter"
    issue_note = (
        f" Analysis completed with {total_findings} recorded finding(s); "
        "findings are analysis signal, not a health grade."
        if total_findings
        else " No findings recorded in the alignment block."
    )
    contract_state = alignment.get("contract") or (report.get("contract"))
    cell["diagnostics"] = (
        f"Stored snapshot {state_note}."
        + issue_note
        + (f" Contract: {contract_state}." if contract_state else "")
        + " M1 verifies the source-text binding only; stored "
        "metadata_sha256 and prompt/alignment versions are recorded, not "
        "recomputed (recomputing them requires running Writer)."
    )
    cell["stage_version"] = str(provenance.get("alignment_version") or "") or None
    stored_warnings = provenance.get("warnings")
    warning_list = (
        [str(w) for w in stored_warnings if isinstance(w, str)]
        if isinstance(stored_warnings, list)
        else []
    )
    unexpected_warnings = [w for w in warning_list if w not in EXPECTED_DETERMINISTIC_WARNINGS]
    cell["detail"] = {
        "observer_mode": provenance.get("observer_mode"),
        "quality_model": provenance.get("quality_model"),
        "stage_status": stage_status,
        "finding_counts": finding_counts,
        "stored_metadata_sha256": provenance.get("metadata_sha256"),
        "stored_metadata_version": provenance.get("metadata_version"),
        "stored_observer_prompt_version": provenance.get("observer_prompt_version"),
        "stored_alignment_version": provenance.get("alignment_version"),
        "warnings": warning_list,
        "unexpected_warnings": unexpected_warnings,
        "expected_deterministic_mode": (
            provenance.get("observer_mode") == "deterministic"
            and provenance.get("quality_model") == "none"
            and provenance.get("semantic_model") in (None, "none")
            and not unexpected_warnings
        ),
        "md_report": str(reports_dir / f"{chapter.chapter_id}.mri.md"),
    }
    return cell


def _editing_summary_candidates(
    settings: Any,
    registry_source: Path | None,
    repo_roots: list[Path],
) -> tuple[Path | None, dict[str, Any]]:
    """Resolve the Writer editing summary store without executing anything.

    Candidate order is deterministic and every checked path is reported:
    explicit env override, per-book stores, then the Writer checkout store
    found by walking up from the registry file.
    """
    info: dict[str, Any] = {"checked": [], "selected": None}
    override = (os.environ.get(EDITING_SUMMARY_ENV) or "").strip()
    if override:
        info["checked"].append(override)
        candidate = Path(override)
        try:
            if candidate.is_file():
                info["selected"] = str(candidate)
                return candidate, info
        except OSError:
            pass
        info["error"] = f"Override {override} is not a readable file."
        return None, info
    for root in repo_roots:
        candidate = root / ".writer" / "editing" / "summary.json"
        info["checked"].append(str(candidate))
        try:
            if candidate.is_file():
                info["selected"] = str(candidate)
                return candidate, info
        except OSError:
            continue
    if registry_source is not None:
        try:
            current = registry_source.parent
        except (OSError, ValueError):
            current = None
        seen = 0
        while current is not None and seen < 8:
            candidate = current / ".writer" / "editing" / "summary.json"
            info["checked"].append(str(candidate))
            try:
                if candidate.is_file():
                    info["selected"] = str(candidate)
                    return candidate, info
            except OSError:
                pass
            parent = current.parent
            if parent == current:
                break
            current = parent
            seen += 1
    info["error"] = "No Writer editing summary store observed."
    return None, info


def _parse_editing_doc(
    summary_path: Path | None,
) -> tuple[Any | None, str | None]:
    """Parse the editing summary store once; callers share the result.

    Uses the mtime+size-keyed document cache: each distinct store file is
    parsed at most once per content version. Any rewrite misses the cache
    and is re-read, so no TTL or manual invalidation is needed.
    """
    if summary_path is None:
        return None, None
    return _load_json_cached(summary_path)


_UNSET: Any = object()


def read_editing_cells(
    project_id: str,
    chapters: list[ChapterRef],
    summary_path: Path | None,
    summary_info: dict[str, Any],
    preloaded: Any = _UNSET,
) -> list[dict[str, Any]]:
    """Project editing cells for every chapter from one loaded summary store.

    ``preloaded`` may carry an already-parsed store document (or its parse
    error) so multi-book overviews parse each distinct store file only once.
    When omitted, the store is parsed here exactly once.
    """
    cells: list[dict[str, Any]] = []
    if summary_path is None:
        for chapter in chapters:
            cell = _base_cell("editing", project_id, chapter)
            cell["digest_algorithm"] = "source_fingerprint:sha256-raw-bytes"
            cell["diagnostics"] = (
                "No Writer editing summary store observed at "
                + ("; ".join(summary_info.get("checked", [])) or "(no candidates)")
                + ". No qualifying evidence."
            )
            cells.append(cell)
        return cells
    if preloaded is _UNSET:
        summary, error = _load_json_artifact(summary_path)
    else:
        summary, error = preloaded
    if error is not None or not isinstance(summary, dict):
        for chapter in chapters:
            cell = _base_cell("editing", project_id, chapter)
            cell["digest_algorithm"] = "source_fingerprint:sha256-raw-bytes"
            cell["has_evidence"] = True
            cell["artifact_ref"] = str(summary_path)
            cell["diagnostics"] = f"Editing store exists but {error or 'is not a JSON object'}."
            cells.append(cell)
        return cells
    books = summary.get("books") if isinstance(summary.get("books"), list) else []
    entry = next(
        (b for b in books if isinstance(b, dict) and str(b.get("project_id")) == project_id),
        None,
    )
    if entry is None:
        for chapter in chapters:
            cell = _base_cell("editing", project_id, chapter)
            cell["digest_algorithm"] = "source_fingerprint:sha256-raw-bytes"
            cell["diagnostics"] = (
                f"Editing store {summary_path} holds no entry for {project_id!r}: "
                "chapter not covered until audited."
            )
            cell["detail"] = {"store": str(summary_path)}
            cells.append(cell)
        return cells
    by_stem: dict[str, dict[str, Any]] = {}
    for item in entry.get("chapters") or []:
        if not isinstance(item, dict):
            continue
        for key in ("source_path", "relative_path", "chapter_id"):
            raw = str(item.get(key) or "")
            if raw:
                by_stem[Path(raw.replace("\\", "/")).stem] = item
    for chapter in chapters:
        cell = _base_cell("editing", project_id, chapter)
        cell["digest_algorithm"] = "source_fingerprint:sha256-raw-bytes"
        item = by_stem.get(chapter.chapter_id)
        if item is None:
            cell["diagnostics"] = (
                f"Chapter is not listed in editing report "
                f"{entry.get('report_id')}: not covered until audited."
            )
            cell["detail"] = {
                "store": str(summary_path),
                "report_id": entry.get("report_id"),
            }
            cells.append(cell)
            continue
        cell["has_evidence"] = True
        cell["artifact_ref"] = str(summary_path)
        cell["executed_at"] = str(entry.get("last_checked") or summary.get("generated_at") or "")
        stored = item.get("source_fingerprint")
        cell["stored_digest"] = str(stored) if stored else None
        live, read_error = read_raw_sha256(chapter.path)
        cell["live_digest"] = live
        if not stored:
            cell["diagnostics"] = (
                "Editing entry has no source_fingerprint: present without "
                "verifiable binding, so freshness is unknown."
            )
            cells.append(cell)
            continue
        if live is None:
            cell["diagnostics"] = read_error or "Chapter is unreadable."
            cells.append(cell)
            continue
        cell["digest_match"] = stored == live
        cell["freshness"] = "current" if cell["digest_match"] else "stale"
        readable = bool(item.get("readable", True))
        if not readable:
            cell["diagnostics"] = "Editing entry is marked unreadable; outcome unknown."
            cells.append(cell)
            continue
        cell["result"] = "passed"
        risk = item.get("highest_risk") if isinstance(item.get("highest_risk"), dict) else {}
        state_note = (
            "matches the live file exactly"
            if cell["digest_match"]
            else "no longer matches the live file"
        )
        cell["diagnostics"] = (
            f"Stored fingerprint {state_note}. Audit completed"
            + (
                f" with status {item.get('status')}/{item.get('status_band')}"
                if item.get("status")
                else ""
            )
            + (
                f"; highest risk: {risk.get('label') or risk.get('subdimension')}"
                if risk.get("label") or risk.get("subdimension")
                else ""
            )
            + ". Findings are analysis signal, not a health grade."
        )
        cell["detail"] = {
            "store": str(summary_path),
            "report_id": entry.get("report_id"),
            "chapter_status": item.get("status"),
            "status_band": item.get("status_band"),
            "highest_risk": risk,
            "profile": entry.get("profile"),
        }
        cells.append(cell)
    return cells


def _validation_reports(
    repo_roots: list[Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Map chapter stem -> stored validation report (first root wins)."""
    reports: dict[str, dict[str, Any]] = {}
    checked: list[str] = []
    for root in repo_roots:
        chapters_dir = root / ".writer" / "validation" / "chapters"
        checked.append(str(chapters_dir))
        try:
            if not chapters_dir.is_dir():
                continue
            files = sorted(p for p in chapters_dir.iterdir() if p.is_file() and p.suffix == ".json")
        except OSError:
            continue
        for path in files[:500]:
            data, error = _load_json_cached(path)
            if error is not None or not isinstance(data, dict):
                reports.setdefault(
                    path.stem,
                    {"__unreadable__": True, "__path__": str(path), "__error__": error},
                )
                continue
            chapter_ref = str(data.get("chapter_path") or "")
            stems = {path.stem}
            if chapter_ref:
                stems.add(Path(chapter_ref.replace("\\", "/")).stem)
            for stem in stems:
                reports.setdefault(stem, {**data, "__path__": str(path)})
    return reports, checked


def read_validation_cell(
    project_id: str,
    chapter: ChapterRef,
    reports: dict[str, dict[str, Any]],
    checked: list[str],
    *,
    validation_enabled: bool,
) -> dict[str, Any]:
    cell = _base_cell("validation", project_id, chapter)
    cell["digest_algorithm"] = "writer_source_digest (frontmatter-stripped, sha256: prefix)"
    if not validation_enabled:
        cell["applicable"] = False
        cell["not_applicable_reason"] = (
            "Validation is not enabled for this book in the Writer registry."
        )
        cell["result"] = "unavailable"
        return cell
    data = reports.get(chapter.chapter_id)
    if data is None:
        cell["diagnostics"] = (
            "No stored validation report for this chapter at "
            + ("; ".join(checked) if checked else "(no repository roots)")
            + ": chapter not covered until validated."
        )
        cell["detail"] = {"checked": checked}
        return cell
    cell["has_evidence"] = True
    cell["artifact_ref"] = str(data.get("__path__", ""))
    if data.get("__unreadable__"):
        cell["diagnostics"] = f"Validation report exists but {data.get('__error__')}."
        return cell
    status = str(data.get("machine_status") or "UNKNOWN").upper()
    if status in ("FAIL", "ERROR", "BLOCKED"):
        cell["result"] = "failed"
    elif status == "PASS":
        cell["result"] = "passed"
    else:
        cell["result"] = "pending"
    cell["executed_at"] = str(data.get("executed_at") or data.get("observed_at") or "")
    stored_digest = data.get("source_digest")
    cell["stored_digest"] = str(stored_digest) if stored_digest else None
    chapter_ref = str(data.get("chapter_path") or "")
    live_path = chapter.path
    if chapter_ref:
        candidate = Path(chapter_ref)
        if not candidate.is_absolute():
            for root in (live_path.parent, live_path.parent.parent):
                attempt = root / Path(chapter_ref.replace("/", os.sep))
                try:
                    if attempt.is_file():
                        live_path = attempt
                        break
                except OSError:
                    continue
    if not stored_digest or not chapter_ref:
        cell["diagnostics"] = (
            f"Stored validation state is {status} but carries no verifiable "
            "source binding: freshness is unknown."
        )
        cell["detail"] = {"machine_status": status}
        return cell
    try:
        live_text = live_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        cell["diagnostics"] = f"Live chapter is unreadable, cannot compare: {exc}."
        return cell
    try:
        live_digest = writer_source_digest(live_text)
    except Exception as exc:
        cell["diagnostics"] = f"Digest recomputation failed, cannot compare: {exc}."
        return cell
    cell["live_digest"] = live_digest
    cell["digest_match"] = stored_digest == live_digest
    cell["freshness"] = "current" if cell["digest_match"] else "stale"
    state_note = (
        "matches the live chapter exactly"
        if cell["digest_match"]
        else "no longer matches the live chapter"
    )
    cell["diagnostics"] = f"Stored validation state is {status}; the stored digest {state_note}."
    cell["detail"] = {"machine_status": status}
    return cell


# ---------------------------------------------------------------------------
# Aggregation (explicit dimensions, no double counting)
# ---------------------------------------------------------------------------


def summarize_stage(cells: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [c for c in cells if c.get("applicable", True)]
    current = sum(1 for c in applicable if c.get("freshness") == "current")
    stale = sum(1 for c in applicable if c.get("freshness") == "stale")
    missing = sum(
        1 for c in applicable if not c.get("has_evidence") and c.get("freshness") != "stale"
    )
    # Unknown = applicable cells neither current, stale, nor missing. This
    # is a true partition: every applicable cell lands in exactly one bucket
    # (current, stale, missing, unknown), so the counts always sum to the
    # applicable total.
    unknown = len(applicable) - current - stale - missing
    total = len(applicable)
    coverage_fraction = (current / total) if total else None
    return {
        "applicable": total,
        "with_evidence": sum(1 for c in applicable if c.get("has_evidence")),
        "current": current,
        "stale": stale,
        "missing": missing,
        "unknown": unknown,
        "passed": sum(1 for c in applicable if c.get("result") == "passed"),
        "failed": sum(1 for c in applicable if c.get("result") == "failed"),
        "pending": sum(1 for c in applicable if c.get("result") == "pending"),
        "coverage": f"{current}/{total} current" if total else "0/0",
        "coverage_fraction": coverage_fraction,
        "fully_current": bool(total) and current == total,
        "partition_note": (
            "current+stale+missing+unknown == applicable (partition, no "
            "double counting). passed/failed/pending are orthogonal result "
            "tallies over the same cells."
        ),
    }


# ---------------------------------------------------------------------------
# Book pipeline
# ---------------------------------------------------------------------------


def _repo_roots(definition: WriterBookDefinition) -> list[Path]:
    roots: list[Path] = []
    for candidate in (definition.repo_path, definition.project_root):
        try:
            path = Path(candidate)
        except (OSError, TypeError):
            continue
        if path not in roots:
            roots.append(path)
    return roots


def _book_title(session: Any | None, project_id: str, definition: WriterBookDefinition) -> str:
    """Best-effort display title; never raises, never invents."""
    if session is not None:
        try:
            from mission_control.models import Book as _Book
            from mission_control.models import Project as _Project

            project = session.get(_Project, project_id)
            if project is not None and getattr(project, "name", None):
                return str(project.name)
            from sqlalchemy import select as _select

            book = session.scalar(_select(_Book).where(_Book.project_id == project_id))
            if book is not None and getattr(book, "title", None):
                return str(book.title)
        except Exception:
            pass
    return definition.title


def _project_matrices(
    definition: WriterBookDefinition,
    project_id: str,
    chapters: list[ChapterRef],
    discovery: dict[str, Any],
    repo_roots: list[Path],
    editing_path: Path | None,
    editing_info: dict[str, Any],
    editing_doc: tuple[Any | None, str | None] | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Shared read-only core: full chapter×stage cells plus per-stage summaries.

    ``editing_doc`` is the once-parsed editing store for this request (or
    None when ``editing_path`` is None); parsed here when omitted so the
    single-book path keeps its exactly-once behavior.
    """
    source_available = not discovery.get("error")
    mri_dir, mri_checked = _mri_reports_dir(repo_roots, project_id)
    validation_reports, validation_checked = _validation_reports(repo_roots)

    matrix: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}

    for stage in sorted(STAGE_DEFINITIONS, key=lambda s: s.presentation_order):
        if stage.availability != "implemented":
            cells = []
            for chapter in chapters:
                cell = _base_cell(stage.stage_id, project_id, chapter)
                cell["applicable"] = True
                cell["result"] = "unavailable"
                cell["diagnostics"] = (
                    f"Stage {stage.stage_id!r} is {stage.availability}: {stage.availability_reason}"
                )
                cells.append(cell)
            matrix[stage.stage_id] = cells
            summaries[stage.stage_id] = {
                "applicable": len(chapters),
                "with_evidence": 0,
                "current": 0,
                "stale": 0,
                "missing": 0,
                "unknown": 0,
                "passed": 0,
                "failed": 0,
                "pending": 0,
                "coverage": f"0/{len(chapters)} current" if chapters else "0/0",
                "coverage_fraction": 0.0 if chapters else None,
                "fully_current": False,
                "availability": stage.availability,
                "availability_reason": stage.availability_reason,
                "partition_note": "Stage is not projected in M1; no evidence was read.",
            }
            continue
        if not source_available:
            cells = []
            for chapter in chapters:
                cell = _base_cell(stage.stage_id, project_id, chapter)
                cell["diagnostics"] = str(discovery.get("error"))
                cells.append(cell)
            matrix[stage.stage_id] = cells
            summary = summarize_stage(cells)
            summary["availability"] = stage.availability
            summaries[stage.stage_id] = summary
            continue
        if stage.stage_id == "metadata":
            cells = [
                read_metadata_cell(project_id, chapter, definition.metadata_dir)
                for chapter in chapters
            ]
        elif stage.stage_id == "mri":
            cells = [
                read_mri_cell(project_id, chapter, mri_dir, mri_checked) for chapter in chapters
            ]
        elif stage.stage_id == "editing":
            if editing_doc is None:
                editing_doc = _parse_editing_doc(editing_path)
            cells = read_editing_cells(
                project_id, chapters, editing_path, editing_info, preloaded=editing_doc
            )
        elif stage.stage_id == "validation":
            cells = [
                read_validation_cell(
                    project_id,
                    chapter,
                    validation_reports,
                    validation_checked,
                    validation_enabled=definition.validation_enabled
                    or bool(definition.validation_checks),
                )
                for chapter in chapters
            ]
        else:  # pragma: no cover - registry/reader mismatch guard
            cells = []
            for chapter in chapters:
                cell = _base_cell(stage.stage_id, project_id, chapter)
                cell["result"] = "unavailable"
                cell["diagnostics"] = (
                    f"Stage {stage.stage_id!r} is registered implemented but has "
                    "no M1 reader; reporting unavailable rather than inventing "
                    "results."
                )
                cells.append(cell)
        matrix[stage.stage_id] = cells
        summary = summarize_stage(cells)
        summary["availability"] = stage.availability
        summaries[stage.stage_id] = summary
    return matrix, summaries


def get_book_pipeline(session: Any | None, settings: Any | None, project_id: str) -> dict[str, Any]:
    """Read-only chapter-by-stage projection for one book.

    Never writes. Never executes Writer. Unknowns are preserved: anything
    that cannot be established from a real artifact plus an exact digest
    comparison is reported unknown, never passed or failed.
    """
    try:
        snapshot = load_writer_registry(resolve_registry_path(settings))
    except Exception as exc:
        return {
            "project_id": project_id,
            "known": False,
            "diagnostics": f"Writer registry could not be loaded: {exc}.",
            "registry_version": PIPELINE_REGISTRY_VERSION,
        }
    definition = snapshot.books.get(project_id) if snapshot else None
    if definition is None:
        return {
            "project_id": project_id,
            "known": False,
            "diagnostics": (
                "Book is not registered in the Writer registry. Register the "
                "book in Writer or confirm canonical identity."
            ),
            "registry_version": PIPELINE_REGISTRY_VERSION,
            "registry_source": str(snapshot.source_path) if snapshot else None,
        }

    title = _book_title(session, project_id, definition)
    chapters, discovery = discover_chapters(definition)
    repo_roots = _repo_roots(definition)
    editing_path, editing_info = _editing_summary_candidates(
        settings, snapshot.source_path, repo_roots
    )
    matrix, summaries = _project_matrices(
        definition,
        project_id,
        chapters,
        discovery,
        repo_roots,
        editing_path,
        editing_info,
        None,
    )
    try:
        source_fp = fingerprint_manuscript(definition.chapter_dir, definition.chapter_pattern)
    except Exception as exc:
        source_fp = {"ok": False, "diagnostics": f"Fingerprint failed: {exc}."}

    return {
        "project_id": project_id,
        "known": True,
        "book_title": title or definition.title,
        "registry_version": PIPELINE_REGISTRY_VERSION,
        "registry_source": str(snapshot.source_path) if snapshot else None,
        "chapter_dir": str(definition.chapter_dir),
        "chapter_pattern": definition.chapter_pattern,
        "profile": definition.profile,
        "validation_enabled": definition.validation_enabled,
        "human_approval_required": definition.human_approval_required,
        "source_fingerprint": source_fp,
        "fingerprint_note": (
            "manuscript-v1 (CRLF->LF manifest) describes the chapter scope as "
            "a whole. Per-stage digests use their own authoritative "
            "algorithms and are never compared against this fingerprint."
        ),
        "discovery": discovery,
        "chapters": [
            {
                "chapter_id": c.chapter_id,
                "filename": c.filename,
                "path": str(c.path),
            }
            for c in chapters
        ],
        "stages": [
            stage.to_dict()
            for stage in sorted(STAGE_DEFINITIONS, key=lambda s: s.presentation_order)
        ],
        "summaries": summaries,
        "matrix": {
            stage_id: [
                {
                    "chapter_id": c["chapter_id"],
                    "result": c["result"],
                    "freshness": c["freshness"],
                    "has_evidence": c["has_evidence"],
                    "applicable": c["applicable"],
                    "artifact_ref": c["artifact_ref"],
                }
                for c in cells
            ]
            for stage_id, cells in matrix.items()
        },
        "refresh_note": (
            "Read-only projection of stored Writer evidence. Nothing was "
            "validated, built, audited, or published to produce this view."
        ),
    }


def get_stage_detail(
    session: Any | None, settings: Any | None, project_id: str, stage_id: str
) -> dict[str, Any] | None:
    """Full per-chapter evidence for one stage, or None when unknown."""
    stage = STAGES_BY_ID.get(stage_id)
    if stage is None:
        return None
    if stage.availability != "implemented":
        return {
            "project_id": project_id,
            "stage": stage.to_dict(),
            "registry_version": PIPELINE_REGISTRY_VERSION,
            "cells": [],
            "diagnostics": (
                f"Stage {stage_id!r} is {stage.availability}: {stage.availability_reason}"
            ),
        }
    try:
        snapshot = load_writer_registry(resolve_registry_path(settings))
    except Exception as exc:
        return {
            "project_id": project_id,
            "stage": stage.to_dict(),
            "registry_version": PIPELINE_REGISTRY_VERSION,
            "cells": [],
            "diagnostics": f"Writer registry could not be loaded: {exc}.",
        }
    definition = snapshot.books.get(project_id) if snapshot else None
    if definition is None:
        return None
    chapters, discovery = discover_chapters(definition)
    if discovery.get("error"):
        return {
            "project_id": project_id,
            "stage": stage.to_dict(),
            "registry_version": PIPELINE_REGISTRY_VERSION,
            "cells": [],
            "diagnostics": str(discovery.get("error")),
        }
    repo_roots = _repo_roots(definition)
    if stage_id == "metadata":
        cells = [
            read_metadata_cell(project_id, chapter, definition.metadata_dir) for chapter in chapters
        ]
    elif stage_id == "mri":
        mri_dir, mri_checked = _mri_reports_dir(repo_roots, project_id)
        cells = [read_mri_cell(project_id, chapter, mri_dir, mri_checked) for chapter in chapters]
    elif stage_id == "editing":
        editing_path, editing_info = _editing_summary_candidates(
            settings, snapshot.source_path, repo_roots
        )
        cells = read_editing_cells(project_id, chapters, editing_path, editing_info)
    elif stage_id == "validation":
        reports, checked = _validation_reports(repo_roots)
        cells = [
            read_validation_cell(
                project_id,
                chapter,
                reports,
                checked,
                validation_enabled=definition.validation_enabled
                or bool(definition.validation_checks),
            )
            for chapter in chapters
        ]
    else:  # pragma: no cover - registry/reader mismatch guard
        cells = []
    return {
        "project_id": project_id,
        "stage": stage.to_dict(),
        "registry_version": PIPELINE_REGISTRY_VERSION,
        "summary": summarize_stage(cells),
        "cells": cells,
    }


def get_pipeline_overview(session: Any | None, settings: Any | None) -> dict[str, Any]:
    """Cross-book production overview: per-book summaries, no full matrices.

    Read-only. Each distinct editing summary store is parsed at most once
    per request (books sharing a store share the parse); per-book MRI and
    validation reads are unchanged. Per-book ``elapsed_ms`` timings are
    included so the frontend cost can be measured, not guessed.
    """
    started = time.perf_counter()
    try:
        snapshot = load_writer_registry(resolve_registry_path(settings))
    except Exception as exc:
        return {
            "registry_version": PIPELINE_REGISTRY_VERSION,
            "registry_source": None,
            "book_count": 0,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "books": [],
            "diagnostics": f"Writer registry could not be loaded: {exc}.",
        }
    registry_source = str(snapshot.source_path) if snapshot else None
    store_docs: dict[str, tuple[Any | None, str | None]] = {}
    rows: list[dict[str, Any]] = []
    for project_id in sorted(snapshot.books):
        definition = snapshot.books[project_id]
        book_started = time.perf_counter()
        chapters, discovery = discover_chapters(definition)
        repo_roots = _repo_roots(definition)
        editing_path, editing_info = _editing_summary_candidates(
            settings, snapshot.source_path, repo_roots
        )
        store_key = str(editing_path) if editing_path is not None else "__none__"
        if store_key not in store_docs:
            store_docs[store_key] = (
                _parse_editing_doc(editing_path) if editing_path is not None else (None, None)
            )
        _matrix, summaries = _project_matrices(
            definition,
            project_id,
            chapters,
            discovery,
            repo_roots,
            editing_path,
            editing_info,
            store_docs[store_key],
        )
        rows.append(
            {
                "project_id": project_id,
                "book_title": _book_title(session, project_id, definition),
                "known": True,
                "profile": definition.profile,
                "applicable_chapters": len(chapters),
                "discovery_error": discovery.get("error"),
                "chapter_dir": str(definition.chapter_dir),
                "validation_enabled": definition.validation_enabled,
                "human_approval_required": definition.human_approval_required,
                "elapsed_ms": int((time.perf_counter() - book_started) * 1000),
                "summaries": summaries,
            }
        )
    return {
        "registry_version": PIPELINE_REGISTRY_VERSION,
        "registry_source": registry_source,
        "book_count": len(rows),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "stages": [
            stage.to_dict()
            for stage in sorted(STAGE_DEFINITIONS, key=lambda s: s.presentation_order)
        ],
        "books": rows,
        "refresh_note": (
            "Read-only cross-book summaries. Open one book for the full "
            "chapter-by-stage matrix and evidence detail."
        ),
    }
